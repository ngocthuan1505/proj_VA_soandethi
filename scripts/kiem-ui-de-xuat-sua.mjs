import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {ensureBlocks} from '../blocks.js';
import {documentPlain} from '../rich-document.js';
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
const paragraph = text => ({
  type: 'paragraph', attrs: {id: uid()}, content: [{type: 'text', text}],
});
const cell = (...content) => ({type: 'tableCell', attrs: {id: uid()}, content});
question.richDoc = {
  type: 'doc',
  content: [{type: 'paragraph', attrs: {id: uid()}, content: [
    {type: 'text', text: 'Chọn giá trị ', marks: [{type: 'bold'}]},
    {type: 'text', text: 'sau khi tính '},
    {type: 'mathInline', attrs: {id: uid(), latex: 'x+1', display: false}},
    {type: 'text', text: ' và '},
    {type: 'mathInline', attrs: {id: uid(), latex: 'y+1', display: false}},
    {type: 'text', text: '. Hãy tính kết quả.'},
  ]}, {type: 'paragraph', attrs: {id: uid()}, content: [
    {type: 'text', text: 'Trình bày mỗi bước.'},
    {type: 'text', text: ' Giữ phần cuối.', marks: [{type: 'italic'}]},
  ]}, {type: 'paragraph', attrs: {id: uid()}, content: [
    {type: 'text', text: 'Đoạn độc lập.'},
  ]}, {type: 'table', attrs: {id: uid()}, content: [
    {type: 'tableRow', attrs: {id: uid()}, content: [
      cell(paragraph('Giữ đầu. Chép số.'), paragraph('So sánh đáp số. Giữ đuôi.')),
      cell(paragraph('Ô bên cạnh.'), paragraph('Dòng bên cạnh.')),
    ]},
  ]}],
};
question.stem = documentPlain(question.richDoc);
ensureBlocks(exam);
await save({version: 1, current: exam.id, exams: [exam], prefs: []}, 0);

const browser = await chromium.launch({
  executablePath: process.env.BROWSER_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});
try {
  const page = await browser.newPage({viewport: {width: 1366, height: 830}});
  page.setDefaultTimeout(12000);
  const errors = [];
  let confirmations = 0;
  const isConfirm = url => /\/edits\/[^/]+\/confirm$/.test(url);
  page.on('request', request => { if (isConfirm(request.url())) confirmations++; });
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
  const undo = async ({pause = false} = {}) => {
    const started = Promise.withResolvers(), release = Promise.withResolvers();
    const hold = async route => {
      if (route.request().method() === 'PUT') {
        started.resolve();
        await release.promise;
      }
      await route.continue();
    };
    if (pause) await page.route(kv, hold);
    const written = page.waitForResponse(response => response.url() === kv
      && response.request().method() === 'PUT' && response.ok()
      && response.request().postDataJSON().value.exams[0].questions[0].v === original[0].v);
    await action('undo-ai').click();
    if (pause) {
      try {
        await Promise.race([started.promise, written]);
        const labels = await page.locator('[data-save-status]').allTextContents();
        assert(labels.length > 0 && labels.every(label => label === 'Đang lưu…'));
      } finally {
        release.resolve();
      }
    }
    await written;
    if (pause) await page.unroute(kv, hold);
    await saved();
  };
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
    await dialog.locator('.diff-impact-summary').waitFor();
    await dialog.locator('.diff-side-by-side').waitFor();
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

  const selectAcross = async (selector, start, end) => {
    await editor.scrollIntoViewIfNeeded();
    await editor.locator('.tiptap').evaluate((element, args) => {
      element.focus();
      const [first, second] = element.querySelectorAll(args.selector);
      const head = [...first.childNodes].find(node => node.nodeType === Node.TEXT_NODE
        && node.textContent.includes(args.start));
      const tail = [...second.childNodes].find(node => node.nodeType === Node.TEXT_NODE
        && node.textContent.includes(args.end));
      const range = document.createRange();
      range.setStart(head, head.textContent.indexOf(args.start));
      range.setEnd(tail, tail.textContent.indexOf(args.end) + args.end.length);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      document.dispatchEvent(new Event('selectionchange'));
    }, {selector, start, end});
    await page.locator('.selection-ask').click();
  };
  await selectAcross(':scope > p', 'Hãy', 'bước.');
  await send('Viết lại hai đoạn đang chọn');
  await proposal.waitFor();
  await action('show-block-diff').click();
  await dialog.locator('ins').getByText(/Kiểm tra lại/).waitFor();
  const confirmed = page.waitForResponse(response => isConfirm(response.url()) && response.ok());
  await dialog.locator('[data-action="apply-block-patch"]').click();
  await confirmed;
  await action('undo-ai').waitFor();
  const rewritten = (await state()).questions[0];
  assert.equal(rewritten.stem, original[0].stem.replace(
    'Hãy tính kết quả.\nTrình bày mỗi bước.', 'Tính giá trị.\nNêu lý do.\nKiểm tra lại.',
  ));
  const beforeBlocks = original[0].richDoc.content;
  const afterBlocks = rewritten.richDoc.content;
  assert.equal(afterBlocks.length, 5);
  assert.equal(afterBlocks[0].attrs.id, beforeBlocks[0].attrs.id);
  assert.equal(afterBlocks[2].attrs.id, beforeBlocks[1].attrs.id);
  assert.deepEqual(afterBlocks[0].content.slice(0, 3), beforeBlocks[0].content.slice(0, 3));
  assert.deepEqual(afterBlocks[2].content.at(-1), beforeBlocks[1].content.at(-1));
  assert.deepEqual(afterBlocks.at(-1), beforeBlocks.at(-1));
  assert.deepEqual(afterBlocks.at(-2), beforeBlocks.at(-2));
  await undo({pause: true});
  assert.deepEqual((await state()).questions, original);

  await selectAcross('td:first-child p', 'Chép', 'đáp số.');
  await send('Viết lại hai đoạn trong ô bảng đang chọn');
  await proposal.waitFor();
  await action('show-block-diff').click();
  await dialog.locator('ins').getByText(/Kiểm tra lại/).waitFor();
  const tableConfirmation = page.waitForResponse(response => isConfirm(response.url()) && response.ok());
  await dialog.locator('[data-action="apply-block-patch"]').click();
  await tableConfirmation;
  await action('undo-ai').waitFor();
  const afterTableEdit = (await state()).questions[0];
  assert.equal(afterTableEdit.stem, original[0].stem.replace(
    'Chép số.\nSo sánh đáp số.', 'Tính giá trị.\nNêu lý do.\nKiểm tra lại.',
  ));
  const originalTable = beforeBlocks.at(-1), table = afterTableEdit.richDoc.content.at(-1);
  const [originalCell, adjacent] = originalTable.content[0].content;
  const [editedCell, keptAdjacent] = table.content[0].content;
  assert.deepEqual(keptAdjacent, adjacent);
  assert.equal(table.attrs.id, originalTable.attrs.id);
  assert.equal(editedCell.attrs.id, originalCell.attrs.id);
  assert.equal(editedCell.content.length, 3);
  assert.equal(editedCell.content.at(-1).attrs.id, originalCell.content.at(-1).attrs.id);
  await undo();
  assert.deepEqual((await state()).questions, original);

  await selectAcross(':scope > p', 'sau khi tính', 'bước.');
  await send('Viết lại đoạn có công thức đang chọn');
  await proposal.waitFor();
  await action('show-block-diff').click();
  await dialog.locator('ins').getByText(/Nêu cách làm/).waitFor();
  const formulaConfirmation = page.waitForResponse(response => isConfirm(response.url()) && response.ok());
  await dialog.locator('[data-action="apply-block-patch"]').click();
  await formulaConfirmation;
  await action('undo-ai').waitFor();
  const afterFormulaEdit = (await state()).questions[0];
  assert.equal(afterFormulaEdit.stem, original[0].stem.replace(
    'sau khi tính $x+1$ và $y+1$. Hãy tính kết quả.\nTrình bày mỗi bước.',
    'Đánh giá $x+2$ với $y+2$.\nNêu cách làm.',
  ));
  const beforeMath = beforeBlocks[0].content.filter(node => node.type === 'mathInline');
  const afterMath = afterFormulaEdit.richDoc.content[0].content.filter(node => node.type === 'mathInline');
  assert.deepEqual(afterMath, beforeMath.map((node, index) => ({
    ...node,
    attrs: {...node.attrs, latex: ['x+2', 'y+2'][index]},
  })));
  assert.deepEqual(afterFormulaEdit.richDoc.content.at(-1), beforeBlocks.at(-1));
  await undo();
  assert.deepEqual((await state()).questions, original);

  await askToEdit();
  const confirmationsBeforeDoubleClick = confirmations;
  await dialog.locator('[data-action="apply-block-patch"]').evaluate(button => {
    button.click();
    button.click();
  });
  await action('undo-ai').waitFor();
  await saved();
  const updated = (await state()).questions;
  assert.equal(updated[0].stem, original[0].stem.replace('kết quả', 'kết quả (đã sửa)'));
  assert.equal(updated[0].v, original[0].v + 1);
  assert.equal(confirmations, confirmationsBeforeDoubleClick + 1);
  assert.deepEqual(updated[0].richDoc.content[0].content.slice(0, 3),
    original[0].richDoc.content[0].content.slice(0, 3));
  assert.deepEqual(updated.slice(1), original.slice(1));
  await undo();
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
  await undo();
  assert.deepEqual((await state()).questions, original);

  await askToEdit();
  await saved();
  const other = await load();
  other.value.exams[0].title += ' — phiên khác';
  other.value.exams[0].revision++;
  await save(other.value, other.revision);
  const conflict = page.waitForResponse(response => isConfirm(response.url()) && response.status() === 409);
  await dialog.locator('[data-action="apply-block-patch"]').click();
  await conflict;
  await dialog.getByText(/Chưa đồng bộ đề xuất sửa/).waitFor();
  assert.equal(await action('undo-ai').count(), 0);
  assert.deepEqual((await load()).value, other.value);
  assert.deepEqual(errors, []);
  await fs.mkdir(output, {recursive: true});
  await fs.writeFile(path.join(output, 'result.json'), JSON.stringify({
    scenario: 'IT-06', fixture: true, askPreservedQuestions: true, diffPreservedQuestions: true,
    sideBySideDiffVerified: true,
    discardPreservedQuestions: true, repeatedConfirmAppliedOnce: true, richTextPreserved: true,
    undoRestoredQuestions: true, selectedRubricStepOnly: true, staleWriteRejected: true,
    conflictDisplayed: true, pythonConfirmations: confirmations, multilineConfirmedByPython: true,
    nestedTableCellConfirmedByPython: true, mixedFormulaConfirmedByPython: true,
  }, null, 2));
  console.log('IT-06 đạt qua Chrome và FastAPI với phản hồi mẫu.');
} finally {
  await browser.close();
}
