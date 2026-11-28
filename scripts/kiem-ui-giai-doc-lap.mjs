import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {ensureBlocks} from '../blocks.js';
import {blank, uid} from '../core.js';

const base = process.env.POC_URL || 'http://127.0.0.1:4183';
const out = path.resolve(process.argv[2] || 'outputs/qa-giai-doc-lap');
const kv = base + '/api/kv';
const load = async () => (await (await fetch(kv + '?key=state')).json());
assert((await (await fetch(base + '/api/status')).json()).fixture);
assert.equal((await load()).revision, 0, 'Dùng kho thử mới với fixture unsupported.');
const exam = blank('Ngữ văn');
const source = {id: uid(), name: 'Ngữ liệu tự viết', kind: 'text', version: 1, text: 'Mai mở cửa thư viện.'};
const q = {
  id: uid(), v: 1, type: 'mcq', stem: 'Ai mở cửa thư viện?',
  options: ['Mai', 'Lan', 'Hà', 'Bình'], points: 1, answer: 1, answerKnown: true,
  explanation: 'Lời giải cũ dùng để đối chiếu.', rubric: [], source: null,
};
exam.questions = [q];
exam.docs = [source];
exam.assistantSources = [source.id];
ensureBlocks(exam);
const seeded = await fetch(kv, {
  method: 'PUT',
  headers: {Origin: base, 'Content-Type': 'application/json', 'If-Match': '0'},
  body: JSON.stringify({key: 'state', value: {version: 1, current: exam.id, exams: [exam], prefs: []}}),
});
assert(seeded.ok, await seeded.text());
const url = base + '/api/exams/' + exam.id + '/questions/' + q.id + '/check';
const question = async () => (await load()).value.exams[0].questions[0];
const browser = await chromium.launch({
  executablePath: process.env.BROWSER_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});
try {
  const page = await browser.newPage({viewport: {width: 1366, height: 830}});
  page.setDefaultTimeout(12000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base);
  const dialog = page.locator('#dialog');
  const currentQuestion = page.locator('#q-' + q.id);
  const choose = async () => {
    await currentQuestion.locator('.stem-editor .tiptap').click();
    await page.locator('[data-menu="tools"]:visible').first().click();
    await page.locator('[data-action="ai-check"]:visible').first().click();
    await dialog.locator('#question-check-consent').check();
  };
  const run = () => dialog.locator('#question-check-form [type="submit"]').click();
  await choose();
  await dialog.locator('[name="check-source"]').uncheck();
  await run();
  await dialog.getByText(/Bất đồng: đáp án lưu B, giải lại A/).waitFor();
  await dialog.getByText(/Chưa có trích dẫn khớp nguồn/).waitFor();
  const checked = await question();
  assert.equal(checked.v, q.v);
  assert.equal(checked.answer, q.answer);
  assert.equal(checked.explanation, q.explanation);
  assert.equal(checked.check.status, 'review');
  assert(!checked.approval);

  const approvedWrite = page.waitForResponse(r => r.url() === kv && r.request().method() === 'PUT' && r.ok());
  await dialog.locator('[data-action="approve-question"]').click();
  await approvedWrite;
  const approved = await question();
  assert.equal(approved.approval.version, q.v);
  assert.deepEqual(approved.check, checked.check);

  await choose();
  await dialog.locator('[name="check-source"]').uncheck();
  await run();
  await dialog.getByText(/Bất đồng: đáp án lưu B, giải lại A/).waitFor();
  await dialog.locator('[data-use-checked-answer]').click();
  await page.locator('#toast').getByText(/bản mới cần rà soát và duyệt lại/).waitFor();
  const applied = await question();
  assert.equal(applied.v, q.v + 1);
  assert.equal(applied.answer, 0);
  assert.equal(applied.approval, null);
  assert.equal(applied.check.version, applied.v);
  assert(!applied.check.solver);

  await choose();
  const serverError = page.waitForResponse(r => r.url() === url && r.status() === 502);
  await run();
  assert.equal((await (await serverError).json()).detail.code, 'missing_evidence');
  await dialog.getByRole('heading', {name: 'Chưa hoàn tất kiểm câu'}).waitFor();
  assert.deepEqual(await question(), applied);
  await page.keyboard.press('Escape');

  const pending = Promise.withResolvers();
  const release = Promise.withResolvers();
  await page.route(url, async route => {
    const response = await route.fetch();
    pending.resolve(response.status());
    await release.promise;
    await route.fulfill({response});
  });
  await choose();
  await run();
  assert.equal(await pending.promise, 502);
  await page.keyboard.press('Escape');
  await page.locator('[data-menu="format"]:visible').first().click();
  await page.locator('[data-action="metadata"]:visible').first().click();
  await dialog.getByRole('heading', {name: 'Thông tin đề'}).waitFor();
  release.resolve();
  await dialog.getByText(/chưa có trích dẫn/i).waitFor();
  await dialog.getByRole('heading', {name: 'Thông tin đề'}).waitFor();
  assert.deepEqual(await question(), applied);
  assert.deepEqual(errors, []);
  await fs.mkdir(out, {recursive: true});
  await fs.writeFile(path.join(out, 'result.json'), JSON.stringify({
    scenario: 'IT-07', fixture: true, disagreement: true, manualApprovalSeparate: true,
    applyInvalidatedApproval: true, missingEvidenceRejected: true, lateErrorPreservedDialog: true,
  }, null, 2));
  console.log('IT-07 đạt qua Chrome và FastAPI với phản hồi mẫu.');
} finally {
  await browser.close();
}
