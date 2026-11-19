import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {ensureBlocks} from '../blocks.js';
import {sample, uid} from '../core.js';

const base = process.env.POC_URL || 'http://127.0.0.1:4183';
const output = path.resolve(process.argv[2] || 'outputs/qa-de-xuat-sua');
const kv = base + '/api/kv';
const load = async () => {
  const response = await fetch(kv + '?key=state');
  assert(response.ok);
  return response.json();
};
const save = async (value, revision) => {
  const response = await fetch(kv, {
    method: 'PUT',
    headers: {Origin: base, 'Content-Type': 'application/json', 'If-Match': String(revision)},
    body: JSON.stringify({key: 'state', value}),
  });
  assert(response.ok, await response.text());
};
assert((await (await fetch(base + '/api/status')).json()).fixture);
assert.equal((await load()).revision, 0, 'Dùng kho thử chưa có dữ liệu.');
const exam = sample('Toán');
exam.chat = [];
exam.aiConsent = true;
exam.autoUpdate = false;
exam.fullExam = true;
const question = exam.questions[0];
exam.questions.forEach(item => { item.type = 'essay'; });
question.points = 0.5;
question.rubric = [
  {text: 'Xác định biểu thức.', points: 0.25},
  {text: 'Tính đúng kết quả.', points: 0.25},
];
question.stem = 'Chọn giá trị sau khi tính $x+1$. Hãy tính kết quả.';
question.richDoc = {
  type: 'doc',
  content: [{type: 'paragraph', attrs: {id: uid()}, content: [
    {type: 'text', text: 'Chọn giá trị ', marks: [{type: 'bold'}]},
    {type: 'text', text: 'sau khi tính '},
    {type: 'mathInline', attrs: {id: uid(), latex: 'x+1', display: false}},
    {type: 'text', text: '. Hãy tính kết quả.'},
  ]}],
};
ensureBlocks(exam);
await save({version: 1, current: exam.id, exams: [exam], prefs: []}, 0);

const browser = await chromium.launch({
  executablePath: process.env.BROWSER_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});
try {
  const page = await browser.newPage({viewport: {width: 1366, height: 830}});
  page.setDefaultTimeout(12000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base);
  const action = name => page.locator('[data-action="' + name + '"]:visible').first();
  const dialog = page.locator('#dialog');
  const proposal = page.locator('.proposal-card');
  const editor = page.locator('[data-rich-id="' + question.id + '"][data-rich-field="stem"]');
  const state = async () => (await load()).value.exams[0];
  const saved = () => page.waitForFunction(() => [...document.querySelectorAll('[data-save-status]')]
    .some(node => /^Đã lưu/.test(node.textContent)));
  await action('toggle-ai').waitFor();
  if (!(await page.locator('#chat-input').isVisible())) await action('toggle-ai').click();
  await saved();
  const original = (await state()).questions;
  const send = async text => {
    await page.locator('#chat-input').fill(text);
    await page.locator('#chat-form button[type="submit"]').click();
  };
  const select = async (text, target = editor) => {
    await target.scrollIntoViewIfNeeded();
    await target.locator('.tiptap').evaluate((element, text) => {
      element.focus();
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        const index = node.textContent.indexOf(text);
        if (index < 0) continue;
        const range = document.createRange();
        range.setStart(node, index);
        range.setEnd(node, index + text.length);
        getSelection().removeAllRanges();
        getSelection().addRange(range);
        document.dispatchEvent(new Event('selectionchange'));
        return;
      }
      throw Error('Không tìm thấy vùng chọn.');
    }, text);
    await page.locator('.selection-ask').click();
  };
  const askToEdit = async () => {
    await select('kết quả');
    await send('Sửa phần đang chọn');
    await proposal.waitFor();
    await action('show-block-diff').click();
    await dialog.locator('ins').getByText(/kết quả \(đã sửa\)/).waitFor();
  };

  const setMode = async mode => {
    const options = page.locator('[data-ux-action="options"]');
    await options.click();
    await page.locator('#chat-mode').selectOption(mode);
    await page.keyboard.press('Escape');
  };
  await setMode('ask');
  await send('Giải thích câu này giúp tôi');
  await page.getByText('Giải thích mẫu để kiểm tra chế độ Chỉ hỏi.').waitFor();
  await saved();
  assert.deepEqual((await state()).questions, original);
  await setMode('auto');
  await askToEdit();
  assert.deepEqual((await state()).questions, original);
  await dialog.locator('[data-action="discard-block-patch"]').click();
  assert.deepEqual((await state()).questions, original);

  await askToEdit();
  await dialog.locator('[data-action="apply-block-patch"]').evaluate(button => {
    button.click();
    button.click();
  });
  await action('undo-ai').waitFor();
  await saved();
  const updated = (await state()).questions;
  assert.equal(updated[0].stem, original[0].stem.replace('kết quả', 'kết quả (đã sửa)'));
  assert.equal(updated[0].v, original[0].v + 1);
  assert.deepEqual(updated[0].richDoc.content[0].content.slice(0, 3),
    original[0].richDoc.content[0].content.slice(0, 3));
  assert.deepEqual(updated.slice(1), original.slice(1));
  await action('undo-ai').click();
  await saved();
  assert.deepEqual((await state()).questions, original);

  const rubric = page.locator('[data-rich-id="' + question.id + '"][data-rich-field="rubric"][data-rich-index="1"]');
  await select('kết quả', rubric);
  await send('Sửa bước chấm đang chọn');
  await proposal.waitFor();
  await action('show-block-diff').click();
  await dialog.locator('ins').getByText(/kết quả \(đã sửa\)/).waitFor();
  await dialog.locator('[data-action="apply-block-patch"]').click();
  await action('undo-ai').waitFor();
  await saved();
  const marked = (await state()).questions;
  assert.deepEqual(marked[0].rubric[0], original[0].rubric[0]);
  assert.equal(marked[0].rubric[1].text, 'Tính đúng kết quả (đã sửa).');
  assert.equal(marked[0].rubric[1].points, original[0].rubric[1].points);
  assert.deepEqual(marked[0].richDoc, original[0].richDoc);
  await action('undo-ai').click();
  await saved();
  assert.deepEqual((await state()).questions, original);

  await askToEdit();
  await saved();
  const other = await load();
  other.value.exams[0].title += ' — phiên khác';
  other.value.exams[0].revision++;
  await save(other.value, other.revision);
  const conflict = page.waitForResponse(response => response.url() === kv && response.status() === 409);
  await dialog.locator('[data-action="apply-block-patch"]').click();
  await conflict;
  await page.locator('#toast').getByText(/Chưa đồng bộ đề xuất sửa/).waitFor();
  assert.equal(await action('undo-ai').count(), 0);
  assert.deepEqual((await load()).value, other.value);
  assert.deepEqual(errors, []);
  await fs.mkdir(output, {recursive: true});
  await fs.writeFile(path.join(output, 'result.json'), JSON.stringify({
    scenario: 'IT-06', fixture: true, askPreservedQuestions: true, diffPreservedQuestions: true,
    discardPreservedQuestions: true, repeatedConfirmAppliedOnce: true, richTextPreserved: true,
    undoRestoredQuestions: true, selectedRubricStepOnly: true, staleWriteRejected: true,
    conflictDisplayed: true,
  }, null, 2));
  console.log('IT-06 đạt qua Chrome và FastAPI với phản hồi mẫu.');
} finally {
  await browser.close();
}
