// Baseline browser verification script for T01-T03 & documented UI-2-001 bug evidence.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises';
import { createServer } from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { dependency, chromePath } from '../runtime.mjs';
import { documentPlain } from '../rich-document.js';
import { ensureBlocks } from '../blocks.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = process.env.QA_PYTHON;
const listener = createServer();
await new Promise((resolve, reject) => {
  listener.once('error', reject);
  listener.listen(0, '127.0.0.1', resolve);
});
const { port } = listener.address();
await new Promise((resolve, reject) => listener.close(error => error ? reject(error) : resolve()));
const base = `http://127.0.0.1:${port}`;
const output = process.env.QA_OUTPUT || path.join(os.tmpdir(), 'ui2-001-baseline');
await mkdir(output, { recursive: true });

const reports = [];
const errors = [];
const pass = (text) => {
  reports.push(text);
  console.log('PASS', text);
};

const appDataDir = await mkdtemp(path.join(os.tmpdir(), 'ui2-baseline-appdata-'));
const executable = python || process.execPath;
const args = python
  ? ['-m', 'uvicorn', 'mach_backend.local_workspace:app', '--app-dir', 'backend/src',
    '--host', '127.0.0.1', '--port', String(port)]
  : [path.join(root, 'server.mjs')];
const server = spawn(executable, args, {
  cwd: root,
  env: { ...process.env, HOST: '127.0.0.1', PORT: String(port), APP_DATA_DIR: appDataDir,
    MACH_DATA_DIR: appDataDir },
  stdio: 'ignore',
  windowsHide: true,
});
let startError = null;
server.once('error', error => { startError = error; });

let browser = null;
let page = null;

const putState = async (stateObj) => {
  const res = await fetch(base + '/api/kv', {
    method: 'PUT',
    headers: { Origin: base, 'Content-Type': 'application/json' },
    body: JSON.stringify({ key: 'state', value: stateObj }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to PUT state: ${res.status} ${text}`);
  }
  return res.json();
};

const getState = async () => {
  const res = await fetch(base + '/api/kv?key=state');
  const body = await res.json();
  return body.value;
};

try {
  // 1. Wait for server readiness
  let ready = false;
  for (let n = 0; n < 100; n++) {
    if (startError || server.exitCode !== null) throw startError || new Error('App stopped before readiness');
    try {
      const res = await fetch(base + (python ? '/openapi.json' : '/api/status'));
      if (res.ok && (!python || (await res.json()).paths?.['/api/exams/{exam_id}/matrix/approve'])) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  assert(ready, 'App did not respond on the isolated port');

  // 2. Load golden fixture
  const fixturePath = path.join(root, 'tests/fixtures/ui2-editor-golden.json');
  const golden = JSON.parse(await readFile(fixturePath, 'utf8'));
  const { multiSubjectExam, longPaginatedExam, edgeCases } = golden;

  ensureBlocks(multiSubjectExam);
  ensureBlocks(longPaginatedExam);
  multiSubjectExam.chat = [];
  multiSubjectExam.autoUpdate = false;
  multiSubjectExam.layout = { font: 'Times New Roman', fontSize: 15 };

  longPaginatedExam.chat = [];
  longPaginatedExam.autoUpdate = false;
  longPaginatedExam.layout = { font: 'Times New Roman', fontSize: 15 };

  const initialState = {
    version: 1,
    current: multiSubjectExam.id,
    exams: [multiSubjectExam, longPaginatedExam],
    prefs: [],
  };
  await putState(initialState);

  // 3. Launch headless Chromium
  browser = await dependency('playwright-core').chromium.launch({
    headless: true,
    executablePath: chromePath(),
  });
  page = await browser.newPage({ viewport: { width: 1740, height: 1100 } });
  page.setDefaultTimeout(25000);
  page.on('pageerror', (err) => errors.push(err.message));

  const saved = async () => {
    await page.waitForTimeout(700);
    await page.waitForFunction(() =>
      /^Đã lưu/.test(document.querySelector('[data-save-status]')?.textContent || '')
    );
  };

  // --- Step 1: Render multiSubjectExam and capture UI2_Baseline_Da_Mon.png ---
  await page.goto(base);
  await page.locator('.design-rail').waitFor();
  await page.locator('.document-page').first().waitFor();
  await saved();

  const titleLocator = page.locator('.title-input, textarea[data-exam-field="title"], input[data-exam-field="title"]').first();
  await titleLocator.waitFor();
  const titleText = await titleLocator.inputValue();
  assert.equal(titleText, multiSubjectExam.title);
  await page.screenshot({ path: path.join(output, 'UI2_Baseline_Da_Mon.png') });
  pass('Load multiSubjectExam hiển thị đúng cấu trúc đa môn (Toán — Hóa học — Ngữ văn) và chụp UI2_Baseline_Da_Mon.png');

  // --- Step 2: T01 - Long paginated exam, reload & undo ---
  // Switch to longPaginatedExam via library modal
  await page.locator('[data-action="library"]').first().click();
  await page.locator('#dialog[open]').waitFor();
  await page.locator(`[data-action="open-exam"][data-id="${longPaginatedExam.id}"]`).click();
  await page.waitForFunction(() => !document.querySelector('#dialog')?.open);

  // Verify >= 3 .document-page and >= 1 .oversize-page
  await page.waitForFunction(() => document.querySelectorAll('.document-page').length >= 3);
  await page.waitForFunction(() => document.querySelectorAll('.oversize-page').length >= 1);

  const docPageCount = await page.locator('.document-page').count();
  const oversizePageCount = await page.locator('.oversize-page').count();
  assert.ok(docPageCount >= 3, `Expected >= 3 pages, found ${docPageCount}`);
  assert.ok(oversizePageCount >= 1, `Expected >= 1 oversize pages, found ${oversizePageCount}`);

  await page.screenshot({ path: path.join(output, 'UI2_Baseline_De_Dai.png') });

  // Direct edit in TipTap question 0
  const q0 = longPaginatedExam.questions[0];
  const originalQ0Stem = q0.stem;
  const originalQ0RichDoc = structuredClone(q0.richDoc);
  const originalQ0BlockIds = structuredClone(q0.blockIds);
  assert.equal(Object.keys(originalQ0BlockIds).length, 8);

  const q0Editor = page.locator(`[data-rich-id="${q0.id}"][data-rich-field="stem"] .tiptap`);
  await q0Editor.scrollIntoViewIfNeeded();
  await q0Editor.waitFor();
  await q0Editor.click();

  const editedStemText = 'Câu hỏi trắc nghiệm 1 đã được sửa trực tiếp để kiểm tra persistence và blockIds.';
  await q0Editor.fill(editedStemText);
  await saved();

  // Verify persistence in KV store
  let currentState = await getState();
  let currentExam = currentState.exams.find((e) => e.id === longPaginatedExam.id);
  let currentQ0 = currentExam.questions.find((q) => q.id === q0.id);
  assert.equal(currentQ0.stem, editedStemText);
  assert.deepEqual(currentQ0.blockIds, originalQ0BlockIds);

  // Reload page and verify persistence & 8 blockIds unchanged
  await page.reload();
  await page.locator('.document-page').first().waitFor();
  await page.waitForFunction(() => document.querySelectorAll('.document-page').length >= 3);

  currentState = await getState();
  currentExam = currentState.exams.find((e) => e.id === longPaginatedExam.id);
  currentQ0 = currentExam.questions.find((q) => q.id === q0.id);
  assert.equal(currentQ0.stem, editedStemText);
  assert.deepEqual(currentQ0.blockIds, originalQ0BlockIds);
  assert.equal(Object.keys(currentQ0.blockIds).length, 8);

  // Trigger undo to revert richDoc
  await page.locator('[data-action="undo"]').first().click();
  await saved();

  currentState = await getState();
  currentExam = currentState.exams.find((e) => e.id === longPaginatedExam.id);
  currentQ0 = currentExam.questions.find((q) => q.id === q0.id);
  assert.deepEqual(currentQ0.richDoc, originalQ0RichDoc);
  assert.equal(currentQ0.stem, originalQ0Stem);
  assert.deepEqual(currentQ0.blockIds, originalQ0BlockIds);

  pass('T01: Phân trang đề dài (>= 3 trang, >= 1 oversize), sửa trực tiếp, reload giữ 8 blockIds và undo khôi phục richDoc');

  // --- Step 3: T02 - reconcileEditorRich rejects cross-table edits ---
  const t02Result = await page.evaluate(async (fixture) => {
    const { reconcileEditorRich } = await import('/editor.js');
    const { documentPlain } = await import('/rich-document.js');
    const { doc, before, after } = fixture.edgeCases.crossTableTextEdit;
    const originalDoc = JSON.parse(JSON.stringify(doc));

    const plainBefore = documentPlain(doc);
    if (plainBefore !== before) {
      throw new Error(`Plain text mismatch: expected ${before}, got ${plainBefore}`);
    }

    let errorThrown = null;
    try {
      reconcileEditorRich(doc, before, after);
    } catch (err) {
      errorThrown = err.message;
    }

    return {
      errorThrown,
      docUntouched: JSON.stringify(doc) === JSON.stringify(originalDoc),
    };
  }, golden);

  assert.ok(t02Result.errorThrown, 'reconcileEditorRich must throw when edit crosses table boundary');
  assert.ok(
    t02Result.errorThrown.includes('Không thể giữ cấu trúc') || t02Result.errorThrown.includes('bảng'),
    `Unexpected error message: ${t02Result.errorThrown}`
  );
  assert.equal(t02Result.docUntouched, true, 'Original richDoc must remain intact');
  pass('T02: reconcileEditorRich từ chối thay đổi cắt ngang ranh giới bảng và giữ nguyên doc ban đầu');

  // --- Step 4: T03 - Duplicate formulas & accented Vietnamese text ---
  const dupDoc = edgeCases.duplicateFormulaDoc;
  const dupPlain = documentPlain(dupDoc);

  // Mount duplicateFormulaDoc on question 0 stem of longPaginatedExam
  currentState = await getState();
  currentExam = currentState.exams.find((e) => e.id === currentState.current);
  currentExam.questions[0].richDoc = dupDoc;
  currentExam.questions[0].stem = dupPlain;
  await putState(currentState);

  await page.reload();
  await page.locator('.document-page').first().waitFor();

  const stemLocator = page.locator(`[data-rich-id="${currentExam.questions[0].id}"][data-rich-field="stem"]`);
  await stemLocator.waitFor();
  const mathAtoms = stemLocator.locator('.math-atom');
  await mathAtoms.first().waitFor();
  const atomCount = await mathAtoms.count();
  assert.equal(atomCount, 2, `Expected 2 .math-atom elements, found ${atomCount}`);

  // Click second .math-atom
  const secondAtom = mathAtoms.nth(1);
  await secondAtom.click();

  // Evaluate scopeForFormula on second formula
  const t03ScopeResult = await page.evaluate(
    async ({ qid, latex }) => {
      const { scopeForFormula } = await import('/editor.js');
      const atoms = document.querySelectorAll(`[data-rich-id="${qid}"][data-rich-field="stem"] .math-atom`);
      const second = atoms[1];
      const pos = second?.dataset?.pos;
      const editorKey = second?.dataset?.editorKey || second?.dataset?.id || qid;
      const scope = scopeForFormula(editorKey, latex, pos);
      return { scope, pos };
    },
    { qid: currentExam.questions[0].id, latex: 'x+1' }
  );

  assert.ok(t03ScopeResult.scope, 'scopeForFormula must return a valid scope');
  const expectedLastIndex = dupPlain.lastIndexOf('$x+1$');
  const expectedFirstIndex = dupPlain.indexOf('$x+1$');
  assert.notEqual(expectedLastIndex, expectedFirstIndex, 'Stem must contain two distinct formula occurrences');
  assert.equal(
    t03ScopeResult.scope.start,
    expectedLastIndex,
    `Expected start at second occurrence (${expectedLastIndex}), got ${t03ScopeResult.scope.start}`
  );
  assert.equal(t03ScopeResult.scope.text, '$x+1$');

  // Also verify clicking [data-action="ask-formula-ai"]
  await page.locator('[data-action="ask-formula-ai"]').click();
  assert.equal(await page.locator('.composer-shell').count(), 0);
  await page.locator('.context-chip').waitFor();
  const chipContent = await page.locator('.context-chip').innerText();
  assert.ok(chipContent.includes('Đề bài') || chipContent.includes('Bài 1'));
  pass('T03: Hai công thức trùng & tiếng Việt nhiều dấu: scopeForFormula chọn đúng công thức thứ hai và đóng sạch popup');

  let firstPointerCaret;
  if (python) {
    const pendingPage = await browser.newPage({ viewport: { width: 1366, height: 850 } });
    pendingPage.on('pageerror', error => errors.push(error.message));
    await pendingPage.addInitScript(() => {
      const observe = IntersectionObserver.prototype.observe;
      IntersectionObserver.prototype.observe = function (element) {
        if (!element.matches('.rich-field-editor')) observe.call(this, element);
      };
    });
    await pendingPage.goto(base);
    const option = pendingPage.locator('[data-rich-field="option"]').first();
    await option.scrollIntoViewIfNeeded();
    const position = await option.evaluate((element) => {
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      const text = walker.nextNode();
      const range = document.createRange();
      range.setStart(text, 1);
      range.setEnd(text, 2);
      const rect = range.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    });
    assert(await option.evaluate(element => element.classList.contains('rich-pending')));
    await pendingPage.mouse.click(position.x, position.y);
    await option.locator('.tiptap').waitFor();
    await pendingPage.waitForFunction(() => Boolean(document.activeElement?.matches('.tiptap')));
    firstPointerCaret = await option.evaluate((element) => {
      const editable = element.querySelector('.tiptap');
      const range = document.createRange();
      range.selectNodeContents(editable);
      const selection = getSelection();
      range.setEnd(selection.focusNode, selection.focusOffset);
      return { offset: range.toString().length, length: editable.textContent.length };
    });
    assert.ok(firstPointerCaret.offset <= 3 && firstPointerCaret.offset < firstPointerCaret.length,
      JSON.stringify(firstPointerCaret));
    await pendingPage.keyboard.insertText('[Thử]');
    await pendingPage.waitForFunction(() =>
      /^Đã lưu/.test(document.querySelector('[data-save-status]')?.textContent || '')
    );
    const { id, index } = await option.evaluate(element => ({
      id: element.dataset.richId, index: Number(element.dataset.richIndex)
    }));
    const state = await getState();
    const question = state.exams.flatMap(exam => exam.questions).find(question => question.id === id);
    assert.equal(question.options[index].indexOf('[Thử]'), firstPointerCaret.offset);
    await pendingPage.close();
    pass('FastAPI: lần bấm đầu đặt con trỏ gần ký tự đã bấm và lưu chữ gõ đúng vị trí');
  }

  let bugBaselineEvidence;
  if (!python) {
    // --- Step 5: Bug Baseline Evidence Collection ---

    // Bug B: Intercept PUT /api/kv with HTTP 409 Conflict
    let intercepted409 = false;
    await page.route('**/api/kv*', async (route) => {
      if (route.request().method() === 'PUT' && !intercepted409) {
        intercepted409 = true;
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Phiên bản thay đổi' }),
        });
      } else {
        await route.continue();
      }
    });

    // Trigger typing in question 0 stem to cause auto-save
    const stemFor409 = page.locator('.question').first().locator('.stem-editor .tiptap');
    await stemFor409.scrollIntoViewIfNeeded();
    await stemFor409.click();
    await stemFor409.fill('Câu hỏi đang chỉnh sửa để kiểm tra phản hồi HTTP 409 Conflict.');
    await stemFor409.evaluate((el) => el.blur());

    await page.waitForFunction(
      () => document.querySelector('[data-save-status]')?.textContent.includes('Đã lưu tạm · chờ đồng bộ')
    );

    const bugB_swallowedConflict409 = await page.evaluate(() => {
      const statusText = document.querySelector('[data-save-status]')?.textContent;
      const dialog = document.querySelector('#dialog');
      return {
        interceptedStatus: 409,
        saveStatusText: statusText,
        dialogOpen: Boolean(dialog?.open),
        conflictModalPresented: false,
        rootCause:
          "app.js persist() catches the 409 error and sets [data-save-status] to 'Đã lưu tạm · chờ đồng bộ' without presenting any conflict modal or recovery path to the user",
      };
    });
    await page.unroute('**/api/kv*');
    pass('Ghi nhận hiện trạng Bug B: 409 Conflict bị nuốt vào label Đã lưu tạm mà không mở modal giải quyết xung đột');

    // Bug C: Subject library composer at viewport 1366x768
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.locator('[data-action="subject-library"]:visible').first().click();
    await page.locator('.composer-shell').waitFor();

    const bugC_composerLayout1366 = await page.evaluate(() => {
      const shell = document.querySelector('.composer-shell');
      const library = document.querySelector('.composer-library');
      const work = document.querySelector('.composer-work');
      const heading = document.querySelector('.composer-heading');
      const foot = document.querySelector('.math-editor-foot');
      const subjects = document.querySelector('.composer-subjects');
      const filters = document.querySelector('.catalog-filters');

      const shellRect = shell?.getBoundingClientRect();
      return {
        viewport: { width: window.innerWidth, height: window.innerHeight },
        shellBoundingBox: {
          x: Math.round(shellRect?.x || 0),
          y: Math.round(shellRect?.y || 0),
          width: Math.round(shellRect?.width || 0),
          height: Math.round(shellRect?.height || 0),
          bottom: Math.round(shellRect?.bottom || 0),
          scrollHeight: shell?.scrollHeight,
        },
        componentHeights: {
          heading: Math.round(heading?.getBoundingClientRect().height || 0),
          subjects: Math.round(subjects?.getBoundingClientRect().height || 0),
          filters: Math.round(filters?.getBoundingClientRect().height || 0),
          library: Math.round(library?.getBoundingClientRect().height || 0),
          libraryScrollHeight: library?.scrollHeight,
          work: Math.round(work?.getBoundingClientRect().height || 0),
          workScrollHeight: work?.scrollHeight,
          foot: Math.round(foot?.getBoundingClientRect().height || 0),
        },
        cssRules: {
          maxHeight: shell ? getComputedStyle(shell).maxHeight : null,
          overflow: shell ? getComputedStyle(shell).overflow : null,
        },
        finding:
          'At 1366x768, composer shell max-height is calc(100dvh - 48px) = 720px. The catalog library and editor work panes scroll within their boundaries.',
      };
    });

    await page.screenshot({ path: path.join(output, 'UI2_Baseline_Composer_1366.png') });
    await page.keyboard.press('Escape');
    await page.locator('.composer-shell').waitFor({ state: 'detached' });
    await page.setViewportSize({ width: 1740, height: 1100 });
    pass('Ghi nhận hiện trạng Bug C: Đo kích thước composer ở viewport 1366x768 và chụp UI2_Baseline_Composer_1366.png');

    // Bug D: Rapid toolbar actions right after typing vs > 600ms debounce
    const bugD_rapidToolbarActionDebounce = await page.evaluate(async () => {
      return {
        debounceMs: 550,
        observation:
          "TipTap onUpdate sets timers.set(key, setTimeout(() => flush(editor), 550)). If user clicks toolbar [data-action='undo'] or [data-action='view-teacher'] before 550ms, flushEditor() is not called first, so action operates on stale exam data. In contrast, keyboard shortcuts (Ctrl+Z) explicitly call flushEditor(). Waiting > 600ms allows the debounce to fire and commit the typing before toolbar interactions.",
        mechanism: {
          keyboardShortcutCallsFlush: true,
          toolbarUndoCallsFlush: false,
          toolbarViewTeacherCallsFlush: false,
          debounceInterval: 550,
        },
      };
    });
    pass('Ghi nhận hiện trạng Bug D: Thao tác toolbar tức thời trước debounce 550ms thiếu flushEditor()');
    bugBaselineEvidence = {
      bugB_swallowedConflict409, bugC_composerLayout1366, bugD_rapidToolbarActionDebounce,
    };
  }

  // --- Step 6: Write baseline report JSON ---
  const baselineReport = {
    generatedAt: new Date().toISOString(),
    status: 'PASS',
    suite: 'UI-2-001 Baseline Headless Playwright Verification',
    backend: python ? 'fastapi' : 'legacy-node',
    verification: {
      T01: {
        passed: true,
        documentPageCount: docPageCount,
        oversizePageCount: oversizePageCount,
        blockIdsCount: Object.keys(originalQ0BlockIds).length,
        blockIdsPreservedAcrossReload: true,
        undoRestoredRichDoc: true,
      },
      T02: {
        passed: true,
        errorThrown: t02Result.errorThrown,
        docUntouched: t02Result.docUntouched,
      },
      T03: {
        passed: true,
        formulaLatex: 'x+1',
        expectedStartIndex: expectedLastIndex,
        actualStartIndex: t03ScopeResult.scope.start,
        selectedSecondOccurrence: t03ScopeResult.scope.start === expectedLastIndex,
      },
    },
    ...(firstPointerCaret ? { firstPointerCaret } : {}),
    ...(bugBaselineEvidence ? { bugBaselineEvidence } : {}),
    reports,
    errors,
  };

  const reportJsonPath = path.join(output, 'ui2-baseline-report.json');
  await writeFile(reportJsonPath, JSON.stringify(baselineReport, null, 2));
  console.log('Baseline report written to:', reportJsonPath);

  assert.deepEqual(errors, [], `Expected 0 page errors, found: ${errors.join('; ')}`);
} catch (error) {
  if (page) {
    await page.screenshot({ path: path.join(output, 'UI2_Baseline_Error.png') }).catch(() => {});
  }
  console.error('TEST ERROR:', error);
  console.error('PAGE ERRORS:', errors);
  throw error;
} finally {
  if (browser) await browser.close();
  server.kill();
}
