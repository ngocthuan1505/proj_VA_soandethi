import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {chromium} from 'playwright-core';
import JSZip from 'jszip';
import {blank, uid} from '../core.js';
import {ensureBlocks} from '../blocks.js';

const base = process.env.POC_URL || 'http://127.0.0.1:4183';
const out = path.resolve(process.argv[2] || 'outputs/qa-xuat-chia-se');
const kv = base + '/api/kv';
const status = await (await fetch(base + '/api/status')).json();
assert(status.fixture);
assert((await (await fetch(base + '/api/account')).json()).sharedSnapshots);
assert.equal((await (await fetch(kv + '?key=state')).json()).revision, 0);
const exam = blank('Toán');
exam.title = 'Đề thử xuất và chia sẻ';
exam.chat = [{role: 'user', text: 'CHAT_NOI_BO_731'}];
exam.questions = [{
  id: uid(), type: 'essay', v: 1, points: 10, options: [],
  stem: 'Rút gọn phân số $\\frac{1}{2}$.',
  explanation: 'LOI_GIAI_RIENG_731',
  rubric: [{text: 'BAREM_RIENG_731', points: 10}],
}];
exam.questions.push({
  id: uid(), type: 'essay', v: 1, points: 1, options: [],
  stem: 'Tính diện tích hình vuông cạnh 3 cm.', explanation: 'Diện tích là 9 cm vuông.',
});
ensureBlocks(exam);
const saved = await fetch(kv, {
  method: 'PUT',
  headers: {Origin: base, 'Content-Type': 'application/json', 'If-Match': '0'},
  body: JSON.stringify({key: 'state', value: {version: 1, current: exam.id, exams: [exam], prefs: []}}),
});
assert(saved.ok, await saved.text());
await fs.mkdir(out, {recursive: true});
const browser = await chromium.launch({
  executablePath: process.env.BROWSER_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});
try {
  const page = await browser.newPage({viewport: {width: 1366, height: 830}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base);
  await page.waitForLoadState('networkidle');
  const action = name => page.locator('[data-action="' + name + '"]:visible').first();
  const dialog = page.locator('#dialog');
  const exports = [];
  for (const teacher of [false, true]) {
    for (const format of ['docx', 'pdf', 'html']) {
      await action('export').click();
      await dialog.locator(`[data-action="export-file"][data-teacher="${teacher}"][data-format="${format}"]`).click();
      const link = dialog.locator('.saved-export-link');
      await link.waitFor({timeout: 30000});
      const url = new URL(await link.getAttribute('href'), base).href;
      const response = await page.request.get(url);
      assert(response.ok());
      const data = await response.body();
      const filename = (teacher ? 'giao-vien' : 'hoc-sinh') + '.' + format;
      await fs.writeFile(path.join(out, filename), data);
      exports.push({filename, teacher, format, bytes: data.length});
      if (format === 'html') {
        const opened = await browser.newPage();
        const networkAttempts = [];
        await opened.route(/^https?:/, route => {
          networkAttempts.push(route.request().url());
          return route.abort();
        });
        await opened.goto(pathToFileURL(path.join(out, filename)).href);
        await opened.getByText('Rút gọn phân số', {exact: false}).last().waitFor();
        assert.equal(await opened.locator('math mfrac').count(), 1);
        assert.deepEqual(networkAttempts, []);
        assert.equal(await opened.getByText('LOI_GIAI_RIENG_731').count() > 0, teacher);
        assert.equal(await opened.getByText('CHAT_NOI_BO_731').count(), 0);
        await opened.close();
      }
      await page.keyboard.press('Escape');
    }
  }

  const exportReady = Promise.withResolvers();
  const releaseExport = Promise.withResolvers();
  await page.route(base + '/api/save-export', async route => {
    const reply = await route.fetch();
    exportReady.resolve(reply.status());
    await releaseExport.promise;
    await route.fulfill({response: reply});
  });
  await action('export').click();
  await dialog.locator('[data-action="export-file"][data-teacher="false"][data-format="html"]').click();
  assert.equal(await exportReady.promise, 200);
  await page.keyboard.press('Escape');
  await page.locator('[data-menu="format"]:visible').first().click();
  await action('metadata').click();
  await dialog.getByRole('heading', {name: 'Thông tin đề'}).waitFor();
  releaseExport.resolve();
  await dialog.getByText(/Đã tạo tệp De_thi_/).waitFor();
  await dialog.getByRole('heading', {name: 'Thông tin đề'}).waitFor();
  await page.unroute(base + '/api/save-export');
  await page.keyboard.press('Escape');

  const list = async () => (await (await page.request.get(base + '/api/share?examId=' + exam.id)).json()).shares;
  const openForm = async () => {
    await action('share').click();
    const form = dialog.locator('#share-form');
    await form.waitFor();
    return form;
  };
  let requestGate;
  await page.route(kv, async route => {
    if (route.request().method() === 'PUT' && requestGate) {
      const gate = requestGate;
      requestGate = null;
      gate.started.resolve();
      await gate.release.promise;
    }
    await route.continue();
  });
  const delayedSubmit = async form => {
    const gate = {started: Promise.withResolvers(), release: Promise.withResolvers()};
    requestGate = gate;
    await form.locator('[type=submit]').click();
    await gate.started.promise;
    return gate;
  };
  let form = await openForm();
  let gate = await delayedSubmit(form);
  await page.keyboard.press('Escape');
  const savedAfterClose = page.waitForResponse(r => r.url() === kv && r.request().method() === 'PUT' && r.ok());
  gate.release.resolve();
  await savedAfterClose;
  await page.waitForFunction(() => [...document.querySelectorAll('[data-save-status]')]
    .some(node => /^Đã lưu/.test(node.textContent)));
  assert.deepEqual(await list(), []);

  form = await openForm();
  await form.locator('[name=allowCopy]').uncheck();
  gate = await delayedSubmit(form);
  await form.locator('[name=answers]').check();
  gate.release.resolve();
  const urlField = dialog.locator('#share-url');
  await urlField.waitFor();
  const sharedUrl = new URL(await urlField.inputValue(), base).href;
  const isolated = await browser.newContext();
  const recipient = await isolated.newPage();
  await recipient.goto(sharedUrl);
  await recipient.getByText('Rút gọn phân số', {exact: false}).last().waitFor();
  const publicText = await recipient.locator('body').innerText();
  assert.doesNotMatch(publicText, /LOI_GIAI_RIENG_731|BAREM_RIENG_731|CHAT_NOI_BO_731|Tạo bản sao riêng/);
  await dialog.locator('[data-action=share]').click();
  await dialog.locator('[data-action=revoke-share]').click();
  await dialog.locator('[data-action=revoke-share]').waitFor({state: 'detached'});
  assert.equal((await recipient.reload()).status(), 404);
  await isolated.close();
  assert.deepEqual(await list(), []);
  await page.keyboard.press('Escape');
  await action('export').click();
  const variants = dialog.locator('#export-variants');
  await variants.locator('summary').click();
  for (const checkbox of await variants.getByRole('checkbox').all()) await checkbox.check();
  await variants.locator('select').selectOption('1');
  await dialog.locator('[data-action="export-file"][data-teacher="false"][data-format="html"]').click();
  await dialog.locator('.saved-export-link').waitFor();
  const variantURL = new URL(await dialog.locator('.saved-export-link').getAttribute('href'), base);
  const variantHtml = await (await page.request.get(variantURL.href)).text();
  assert.match(variantHtml, /Mã đề 102/);
  assert(variantHtml.indexOf('Tính diện tích') < variantHtml.indexOf('Rút gọn phân số'));
  assert.doesNotMatch(variantHtml, /LOI_GIAI_RIENG_731|BAREM_RIENG_731|CHAT_NOI_BO_731/);
  await page.keyboard.press('Escape');
  await action('export').click();
  await variants.getByRole('button', {name: 'Bộ PDF'}).click();
  const packLink = dialog.getByRole('link', {name: 'Tải bộ mã đề (.zip)'});
  await packLink.waitFor({timeout: 90000});
  const packResponse = await page.request.get(new URL(await packLink.getAttribute('href'), base).href);
  assert(packResponse.ok());
  const pack = await packResponse.body();
  await fs.writeFile(path.join(out, 'bo-ma-de.pdf.zip'), pack);
  const archive = await JSZip.loadAsync(pack);
  for (const code of [101, 102]) {
    const pdf = await archive.file('HOC_SINH/Ma_' + code + '.pdf').async('nodebuffer');
    assert.equal(pdf.subarray(0, 5).toString(), '%PDF-');
  }
  const key = await archive.file('GIAO_VIEN/Doi_chieu_dap_an.html').async('string');
  assert.match(key, /Mã 101.*Mã 102/);
  assert.match(key, /Xem hướng dẫn chấm <small>\(gốc: 2\)<\/small>/);
  const persisted = await (await page.request.get(kv + '?key=state')).json();
  assert.deepEqual(persisted.value.exams[0].questions.map(q => q.id), exam.questions.map(q => q.id));

  await page.keyboard.press('Escape');
  form = await openForm();
  await form.locator('[name=answers]').check();
  await form.locator('[name=allowCopy]').check();
  await form.locator('[name=community]').check();
  assert(await form.locator('[name=answers]').isDisabled());
  assert.equal(await form.locator('[name=answers]').isChecked(), false);
  await form.getByRole('button', {name: 'Công bố bản học sinh'}).click();
  await urlField.waitFor();
  const publicationUrl = new URL(await urlField.inputValue(), base);
  await dialog.locator('[data-action=share]').click();
  await dialog.getByRole('button', {name: 'Mở kho đề cộng đồng'}).click();
  const filter = dialog.locator('#community-filter');
  await filter.getByLabel('Tìm tên đề').fill('de thu xuat');
  await filter.getByLabel('Môn').fill('toan');
  const searched = page.waitForResponse(r => r.url().includes('/api/community-exams?') &&
    new URL(r.url()).searchParams.get('q') === 'de thu xuat');
  await filter.getByRole('button', {name: 'Tìm đề'}).click();
  assert((await searched).ok());
  const listing = filter.getByRole('article').filter({hasText: exam.title});
  await listing.waitFor();
  assert.equal(await listing.getByRole('link', {name: 'Xem đề'}).getAttribute('href'), publicationUrl.pathname);
  const copyUrl = new URL(await listing.getByRole('link', {name: 'Sao về kho của tôi'}).getAttribute('href'), base);
  await listing.getByRole('button', {name: 'Dùng làm nguồn'}).click();
  await filter.waitFor({state: 'hidden'});
  await page.waitForFunction(async url => {
    const {value} = await (await fetch(url + '?key=state')).json();
    return value.exams[0].docs.some(doc => value.exams[0].assistantSources?.includes(doc.id) &&
      doc.text.includes('Rút gọn phân số') && !/LOI_GIAI_RIENG_731|BAREM_RIENG_731|CHAT_NOI_BO_731/.test(doc.text));
  }, kv);
  await page.goto(copyUrl.href);
  await page.waitForFunction(async ({url, originalId}) => {
    const {value} = await (await fetch(url + '?key=state')).json();
    return value.exams.some(exam => exam.id === originalId) &&
      value.exams.some(exam => exam.id === value.current && exam.id !== originalId && exam.questions.length === 2);
  }, {url: kv, originalId: exam.id});
  const [publication] = await list();
  assert(publication.community && !publication.answers);
  assert((await page.request.post(base + '/api/share/revoke', {
    headers: {Origin: base}, data: {token: publication.token},
  })).ok());
  assert.equal((await page.request.get(publicationUrl.href)).status(), 404);
  assert.deepEqual((await (await page.request.get(base + '/api/community-exams')).json()).exams, []);
  assert.deepEqual(errors, []);
  await fs.writeFile(path.join(out, 'browser-result.json'), JSON.stringify({
    scenario: 'IT-10', exports, closedShareFormCreatedNoLink: true,
    lateAnswerToggleWasIgnored: true, recipientRead: true, revoked: true,
    lateExportPreservedDialog: true,
    variantExportPreservedOriginal: true,
    variantPackPdfWithTeacherKey: true,
    communityPublishedCopiedAttachedAndRevoked: true,
  }, null, 2));
  console.log('IT-10: sáu bản xuất và luồng chia sẻ Chrome/FastAPI đạt.');
} finally {
  await browser.close();
}
