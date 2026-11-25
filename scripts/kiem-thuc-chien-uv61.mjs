// E2E thực chiến người thật UV61: 10 môn K-12, 4 ma trận khó, Phòng thi 3 học sinh + Audio + CV 7991 + .xlsx, Kết nối 2 tầng & SSE.
import assert from 'node:assert/strict';
import {execFileSync, spawn} from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import {chromium} from 'playwright-core';

const ROOT = process.cwd();
const PYTHON_EXE = process.env.QA_PYTHON || path.join(ROOT, 'backend', '.venv', 'Scripts', 'python.exe');
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);
const DEFAULT_EVIDENCE_DIR =
  'C:\\Users\\nguye\\.gemini\\antigravity\\brain\\f3eea969-4834-47f8-8318-93e7d029e582\\qa-uv61-evidence';
const SCREENSHOT_DIR = path.resolve(process.env.QA_SCREENSHOT_DIR || DEFAULT_EVIDENCE_DIR);

function findChrome() {
  for (const p of CHROME_CANDIDATES) {
    if (fs.existsSync(p)) return p;
  }
  throw new Error(`Không tìm thấy Chrome/Edge trong: ${CHROME_CANDIDATES.join(', ')}`);
}

async function freePort() {
  return await new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const addr = srv.address();
      const port = typeof addr === 'object' && addr ? addr.port : 0;
      srv.close((err) => (err ? reject(err) : resolve(port)));
    });
  });
}

function makeSilentWavBuffer(durationSec = 0.25, sampleRate = 8000) {
  const numSamples = Math.max(800, Math.round(sampleRate * durationSec));
  const buf = Buffer.alloc(44 + numSamples);
  buf.write('RIFF', 0, 'ascii');
  buf.writeUInt32LE(36 + numSamples, 4);
  buf.write('WAVE', 8, 'ascii');
  buf.write('fmt ', 12, 'ascii');
  buf.writeUInt32LE(16, 16); // PCM subchunk size
  buf.writeUInt16LE(1, 20); // PCM format
  buf.writeUInt16LE(1, 22); // mono
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate, 28); // byte rate
  buf.writeUInt16LE(1, 32); // block align
  buf.writeUInt16LE(8, 34); // bits per sample
  buf.write('data', 36, 'ascii');
  buf.writeUInt32LE(numSamples, 40);
  buf.fill(0x80, 44); // unsigned 8-bit PCM silence
  return buf;
}

async function startIsolatedServer(port, dataDir, {fixtureCase = null} = {}) {
  const args = fixtureCase
    ? [
        '-c',
        [
          'import pathlib, runpy, sys, uvicorn',
          'sys.path[:0] = [r"backend/src", r"backend/tests"]',
          'fixture = runpy.run_path(r"scripts/chay-fixture-poc.py")["FixtureCase"]',
          'from mach_backend.local_workspace import create_app',
          `app = create_app(pathlib.Path(sys.argv[1]), agent_call=fixture(${JSON.stringify(fixtureCase)}))`,
          `uvicorn.run(app, host="127.0.0.1", port=${port}, log_level="warning")`,
        ].join('; '),
        dataDir,
      ]
    : [
        '-m',
        'uvicorn',
        'mach_backend.local_workspace:app',
        '--app-dir',
        path.join(ROOT, 'backend', 'src'),
        '--host',
        '127.0.0.1',
        '--port',
        String(port),
      ];
  const proc = spawn(PYTHON_EXE, args, {
    cwd: ROOT,
    env: {
      ...process.env,
      MACH_DATA_DIR: dataDir,
      PYTHONPATH: path.join(ROOT, 'backend', 'src'),
      NO_PROXY: '127.0.0.1,localhost',
      PYTHONIOENCODING: 'utf-8',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let logs = '';
  proc.stdout?.on('data', (c) => {
    logs += c.toString();
  });
  proc.stderr?.on('data', (c) => {
    logs += c.toString();
  });

  const baseUrl = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (proc.exitCode !== null) {
      throw new Error(`Uvicorn thoát sớm (${proc.exitCode}):\n${logs}`);
    }
    try {
      const res = await fetch(`${baseUrl}/api/status`);
      if (res.ok) {
        const body = await res.json();
        if (body?.matrixPython) return {proc, baseUrl, getLogs: () => logs};
      }
    } catch {
      // retry
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  await stopServer(proc);
  throw new Error(`Timeout chờ /api/status trên ${baseUrl}:\n${logs}`);
}

async function stopServer(proc) {
  if (!proc || proc.exitCode !== null) return;
  proc.kill();
  await new Promise((resolve) => {
    const t = setTimeout(() => {
      try {
        if (process.platform === 'win32' && proc.pid) {
          spawn('taskkill', ['/pid', String(proc.pid), '/f', '/t'], {stdio: 'ignore'});
        } else {
          proc.kill('SIGKILL');
        }
      } catch {
        // ignore
      }
      resolve();
    }, 3000);
    proc.once('exit', () => {
      clearTimeout(t);
      resolve();
    });
  });
}

function attachTelemetry(page, label, buckets) {
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      buckets.consoleErrors.push(`[${label}] ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => {
    buckets.pageErrors.push(`[${label}] ${err.message}`);
  });
  page.on('response', (res) => {
    if (res.status() >= 500) {
      buckets.http5xx.push(`[${label}] ${res.status()} ${res.url()}`);
    }
  });
}

async function waitSaved(page) {
  await page.waitForFunction(
    () => /^Đã lưu/.test(document.querySelector('[data-save-status]')?.textContent?.trim() || ''),
    {timeout: 12000},
  );
}

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, {recursive: true});
  const tmpData = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-uv61-real-'));
  const wavBytes = makeSilentWavBuffer(0.25, 8000);
  const wavFilePath = path.join(tmpData, 'nghe-toan9-uv61.wav');
  fs.writeFileSync(wavFilePath, wavBytes);
  const xlsxOutPath = path.join(tmpData, 'ket-qua-phong-thi.xlsx');

  const port = await freePort();
  const {proc, baseUrl, getLogs} = await startIsolatedServer(port, tmpData);
  const buckets = {consoleErrors: [], pageErrors: [], http5xx: []};
  let browser = null;
  let sseProc = null;
  let sseData = null;

  const shot = async (page, filename) => {
    const outPath = path.join(SCREENSHOT_DIR, filename);
    await page.screenshot({path: outPath, fullPage: false});
    return outPath;
  };

  try {
    browser = await chromium.launch({
      executablePath: findChrome(),
      headless: true,
    });

    const corpusDir = path.join(ROOT, 'tests', 'fixtures', 'school-corpus');
    const corpusExams = [];
    for (let i = 1; i <= 10; i++) {
      const code = `SC-${String(i).padStart(2, '0')}`;
      const raw = JSON.parse(fs.readFileSync(path.join(corpusDir, `${code}.json`), 'utf8'));
      raw.chat = Array.isArray(raw.chat) ? raw.chat : [];
      corpusExams.push({code, exam: raw});
    }

    // Tạo 1 đề kiểm tra lập ma trận ngược có xung đột điểm để xác minh .matrix-kpi-row + #matrix-reverse-warnings
    const reverseWarnExamId = '11111111-1111-4111-8111-111111111161';
    const reverseWarnExam = {
      id: reverseWarnExamId,
      title: 'Đề rà soát ma trận ngược nhiều mức điểm',
      school: 'TRƯỜNG THCS BÌNH MINH',
      department: 'Tổ Toán',
      subject: 'Toán',
      grade: '9',
      minutes: 45,
      workflowStatus: 'draft',
      revision: 1,
      updated: Date.now(),
      docs: [],
      data: [],
      quote: {text: '', chosen: null, versions: []},
      matrix: [{topic: 'Hàm số và đồ thị', type: 'mcq', targets: [4, 0, 0, 0]}],
      matrixConfirmed: false,
      appliedPrefs: [],
      chat: [],
      history: [],
      undo: [],
      redo: [],
      questions: [1, 2, 3, 4].map((pts, idx) => ({
        id: `rev-q-${idx + 1}`,
        v: 1,
        type: 'mcq',
        stem: `Câu ${idx + 1}: Khảo sát hàm số bậc nhất trường hợp ${idx + 1}.`,
        options: ['Phương án A', 'Phương án B', 'Phương án C', 'Phương án D'],
        answer: 0,
        answerKnown: true,
        points: pts,
        topic: 'Hàm số và đồ thị',
        level: 0,
        explanation: 'Giải thích mẫu.',
      })),
    };

    const teacherCtx = await browser.newContext({
      viewport: {width: 1440, height: 900},
      acceptDownloads: true,
    });
    const teacherPage = await teacherCtx.newPage();
    teacherPage.setDefaultTimeout(20000);
    attachTelemetry(teacherPage, 'teacher', buckets);

    // Nạp audio mẫu cho SC-06 trước khi tải trang
    const wavDataUri = `data:audio/wav;base64,${wavBytes.toString('base64')}`;
    const putAudio = await teacherPage.request.put(`${baseUrl}/api/kv`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {key: 'file:48d8617b-539b-553a-8b5f-edd7048e5327', value: wavDataUri},
    });
    assert(putAudio.ok(), await putAudio.text());

    const seedState = {
      version: 1,
      current: corpusExams[0].exam.id,
      exams: [...corpusExams.map((c) => c.exam), reverseWarnExam],
      prefs: [],
    };
    const putState = await teacherPage.request.put(`${baseUrl}/api/kv`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {key: 'state', value: seedState},
    });
    assert(putState.ok(), await putState.text());

    await teacherPage.goto(baseUrl, {waitUntil: 'networkidle'});
    await teacherPage.locator('.paper .question').first().waitFor();
    await teacherPage.evaluate(() => document.fonts?.ready);
    await teacherPage.waitForTimeout(300);

    // =========================================================================
    // 1. KIỂM TRA LAYOUT 3 VIEWPORTS & 10 MÔN K-12
    // =========================================================================
    const checkViewportShell = async (vpName) => {
      return await teacherPage.evaluate((label) => {
        const vw = window.innerWidth;
        const overflowX = document.documentElement.scrollWidth > vw + 1;
        const saved = document.querySelector('.saved');
        const savedRect = saved?.getBoundingClientRect();
        const savedVisible = Boolean(savedRect && savedRect.width > 20 && savedRect.height > 12);
        const pageJump = document.querySelector('#page-jump');
        const pjRect = pageJump?.getBoundingClientRect();
        const pjStyle = pageJump ? getComputedStyle(pageJump) : null;
        const header = document.querySelector('header.top');
        const headerRect = header?.getBoundingClientRect();
        const bankBtn = document.querySelector('.design-rail [data-action="question-bank"]');
        const bankRect = bankBtn?.getBoundingClientRect();
        return {
          label,
          vw,
          overflowX,
          savedVisible,
          savedText: saved?.textContent?.trim() || '',
          pageJumpVal: pageJump?.value || '',
          pageJumpWidth: pjRect ? Math.round(pjRect.width) : 0,
          pageJumpHeight: pjRect ? Math.round(pjRect.height) : 0,
          pageJumpPadLeft: pjStyle?.paddingLeft || '',
          headerHeight: headerRect ? Math.round(headerRect.height) : 0,
          bankLabel: bankBtn?.innerText?.trim() || '',
          bankRight: bankRect ? Math.round(bankRect.right) : 0,
          bankHeight: bankRect ? Math.round(bankRect.height) : 0,
          hasObjectObject: /\[object\s+Object\]/i.test(document.body?.innerText || ''),
        };
      }, vpName);
    };

    const vp1440 = await checkViewportShell('1440x900');
    assert.equal(vp1440.overflowX, false, 'Desktop 1440 không tràn ngang');
    assert.equal(vp1440.savedVisible, true, '.saved phải hiện trên 1440x900');
    assert.equal(vp1440.pageJumpVal, '1', '#page-jump phải hiển thị trang "1"');
    assert(vp1440.headerHeight <= 60, `Header 1440 phải 1 tầng (got ${vp1440.headerHeight}px)`);
    const shot1440 = await shot(teacherPage, 'uv61-desktop-1440x900.png');

    await teacherPage.setViewportSize({width: 1280, height: 720});
    await teacherPage.waitForTimeout(250);
    const vp1280 = await checkViewportShell('1280x720');
    assert.equal(vp1280.overflowX, false, 'Desktop 1280 không tràn ngang');
    assert.equal(vp1280.savedVisible, true, '.saved phải hiện trên 1280x720');
    assert(vp1280.headerHeight <= 60, `Header 1280 phải 1 tầng (got ${vp1280.headerHeight}px)`);
    const shot1280 = await shot(teacherPage, 'uv61-desktop-1280x720.png');

    await teacherPage.setViewportSize({width: 390, height: 844});
    await teacherPage.waitForTimeout(250);
    const vp390 = await checkViewportShell('390x844');
    assert.equal(vp390.overflowX, false, 'Mobile 390 không tràn ngang');
    assert.equal(vp390.savedVisible, true, '.saved phải hiện trên mobile 390');
    assert(vp390.bankRight <= 390 && vp390.bankHeight <= 52, `Mobile Ngân hàng không vỡ/cắt: ${JSON.stringify(vp390)}`);
    const shot390 = await shot(teacherPage, 'uv61-mobile-390x844.png');

    await teacherPage.setViewportSize({width: 1440, height: 900});
    await teacherPage.waitForTimeout(250);

    // Mở Kho đề & chụp ảnh
    await teacherPage.locator('.design-rail [data-action="library"]').click();
    await teacherPage.waitForSelector('#dialog[open] .wb-library-card', {timeout: 8000});
    await teacherPage.locator('#library-filter').fill('Tiếng Anh');
    await teacherPage.waitForTimeout(150);
    assert((await teacherPage.locator('.wb-library-card').count()) >= 1, 'Tìm kiếm Kho đề khớp Tiếng Anh 12');
    await teacherPage.locator('#library-filter').fill('');
    await teacherPage.waitForTimeout(150);
    const libCardsCount = await teacherPage.locator('.wb-library-card').count();
    assert(libCardsCount >= 11, `Kho đề phải hiển thị đủ 10 môn + đề kiểm tra ngược (có ${libCardsCount})`);
    const shotLibrary = await shot(teacherPage, 'uv61-library-modal.png');

    // Lần lượt mở kiểm tra cả 10 môn K-12 thực tế từ Kho đề
    const corpusChecks = [];
    for (const {code, exam} of corpusExams) {
      if (!(await teacherPage.locator('#dialog[open] #library-filter').count())) {
        await teacherPage.locator('.design-rail [data-action="library"]').click();
        await teacherPage.waitForSelector('#dialog[open] .wb-library-card', {timeout: 8000});
      }
      await teacherPage.locator(`#dialog [data-action="open-exam"][data-id="${exam.id}"]`).click();
      await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open, {timeout: 8000});
      await teacherPage.waitForFunction(
        (expectedCount) => document.querySelectorAll('.paper .question').length === expectedCount,
        exam.questions.length,
        {timeout: 12000},
      );
      await teacherPage.waitForTimeout(200);
      const metrics = await teacherPage.evaluate(() => ({
        title: document.querySelector('.paper .title-input')?.value || '',
        questions: document.querySelectorAll('.paper .question').length,
        katex: document.querySelectorAll('.paper .katex').length,
        katexErrors: document.querySelectorAll('.paper .katex-error').length,
        audioPlayers: document.querySelectorAll('.paper audio[data-audio-file-id]').length,
        audioLoaded: [...document.querySelectorAll('.paper audio[data-audio-file-id]')].filter((a) =>
          String(a.src || '').startsWith('data:audio/'),
        ).length,
        quotes: document.querySelectorAll('.paper .quote-box').length,
        dataCharts: document.querySelectorAll('.paper .data-card svg').length,
        codeBlocks: document.querySelectorAll('.paper pre, .paper code').length,
        hasObjectObject: /\[object\s+Object\]/i.test(document.body?.innerText || ''),
      }));
      assert.equal(metrics.hasObjectObject, false, `${code} bị lộ [object Object]`);
      assert.equal(metrics.katexErrors, 0, `${code} có lỗi KaTeX (${metrics.katexErrors})`);
      if (['SC-01', 'SC-02', 'SC-04', 'SC-05', 'SC-07'].includes(code)) {
        assert(metrics.katex > 0, `${code} (${exam.subject}) phải render KaTeX`);
      }
      if (code === 'SC-03') {
        assert(metrics.quotes >= 1, 'SC-03 Ngữ văn phải có khung ngữ liệu .quote-box');
      }
      if (code === 'SC-06') {
        assert(metrics.audioPlayers >= 1 && metrics.audioLoaded >= 1, 'SC-06 Tiếng Anh phải nạp sẵn audio player');
        assert(
          (await teacherPage.locator('.paper .question-audio-card').first().innerText()).includes('Tối đa 2 lượt nghe'),
          'SC-06 hiển thị giới hạn maxPlays = 2',
        );
      }
      if (code === 'SC-08') {
        assert(metrics.dataCharts >= 1, 'SC-08 Sử & Địa phải hiển thị biểu đồ/bảng số liệu');
      }
      if (code === 'SC-09') {
        assert(metrics.codeBlocks >= 1, 'SC-09 Tin học phải hiển thị khối code');
      }
      corpusChecks.push({code, subject: exam.subject, grade: exam.grade, ...metrics});
    }

    // =========================================================================
    // 2. KIỂM TRA 4 MA TRẬN THỰC TẾ KHÓ / LỘN XỘN & CẢNH BÁO MA TRẬN NGƯỢC
    // =========================================================================
    const uploadMatrixViaApi = async (relPath, mime) => {
      const fullPath = path.join(ROOT, relPath);
      const b64 = fs.readFileSync(fullPath).toString('base64');
      const dataUri = `data:${mime};base64,${b64}`;
      const r = await teacherPage.request.post(`${baseUrl}/api/ai/matrix`, {
        headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
        data: {name: path.basename(fullPath), data: dataUri, consent: false},
      });
      return {status: r.status(), body: await r.json()};
    };

    const mMergedDocx = await uploadMatrixViaApi(
      'tests/fixtures/school-corpus/matrix-cv7991-merged-header.docx',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    );
    assert.equal(mMergedDocx.status, 200, JSON.stringify(mMergedDocx));
    assert.equal(mMergedDocx.body.matrix.length, 5, 'Phải đọc đủ 5 dòng của ma trận gộp ô');
    assert(mMergedDocx.body.matrix.some((r) => Boolean(r.choiceGroup)), 'Phải nhận diện được nhánh tự chọn choiceGroup');
    assert(mMergedDocx.body.matrix.some((r) => Math.abs((r.points ?? 0) - 0.4) < 0.001), 'Phải giữ điểm thập phân 0.40đ');

    const mPdf2Pages = await uploadMatrixViaApi(
      'tests/fixtures/school-corpus/matrix-tuyensinh10-2pages.pdf',
      'application/pdf',
    );
    assert.equal(mPdf2Pages.status, 200, JSON.stringify(mPdf2Pages));
    assert.equal(mPdf2Pages.body.count, 13);

    const mFormulaXlsx = await uploadMatrixViaApi(
      'tests/fixtures/school-corpus/matrix-cv7991-merged-formulas.xlsx',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    );
    assert.equal(mFormulaXlsx.status, 409, 'File Excel chứa công thức chưa lưu giá trị phải trả 409 rõ ràng');
    assert.equal(mFormulaXlsx.body.code, 'matrix_formula');

    const mTwoTablesDocx = await uploadMatrixViaApi(
      'tests/fixtures/school-corpus/matrix-messy-edge-cases/two-tables-legend-and-matrix.docx',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    );
    assert.equal(mTwoTablesDocx.status, 200, JSON.stringify(mTwoTablesDocx));
    assert.equal(mTwoTablesDocx.body.count, 20);

    const mSpecOnly = await uploadMatrixViaApi(
      'tests/fixtures/school-corpus/matrix-messy-edge-cases/spec-only-no-counts.docx',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    );
    assert.equal(mSpecOnly.status, 409);
    assert.equal(mSpecOnly.body.code, 'spec_only_matrix');

    // Mở đề kiểm tra lập ma trận ngược trong modal Ma trận để kiểm chứng .matrix-kpi-row & #matrix-reverse-warnings
    await teacherPage.locator('.design-rail [data-action="library"]').click();
    await teacherPage.waitForSelector(`#dialog [data-action="open-exam"][data-id="${reverseWarnExamId}"]`);
    await teacherPage.locator(`#dialog [data-action="open-exam"][data-id="${reverseWarnExamId}"]`).click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // Nạp file ma trận thật qua UI Matrix Chat (.matrix-file-import) trên đề chưa xác nhận ma trận
    await teacherPage.locator('#chat-input').fill('Lập ma trận đề');
    await teacherPage.locator('#chat-form button[type="submit"]').click();
    await teacherPage.waitForSelector('.matrix-chat-plan', {timeout: 8000});
    await teacherPage.locator('.matrix-file-import summary').click();
    await teacherPage
      .locator('input[data-matrix-file]')
      .setInputFiles(path.join(ROOT, 'tests/fixtures/school-corpus/matrix-cv7991-merged-header.docx'));
    await teacherPage.locator('[data-read-matrix-file]').click();
    await teacherPage.waitForFunction(
      () => /Đã đọc \d+ câu/.test(document.querySelector('[data-matrix-file-status]')?.textContent || ''),
      {timeout: 10000},
    );
    await teacherPage.locator('[data-close-plan]').click();
    await teacherPage.waitForFunction(() => !document.querySelector('.matrix-chat-session'), {timeout: 8000});

    await teacherPage.locator('.wf-step[data-action="workflow-matrix"]').click();
    await teacherPage.waitForSelector('#dialog[open] #matrix-form');
    await teacherPage.locator('[data-action="reverse-matrix"]').click();
    await teacherPage.waitForSelector('#matrix-reverse-warnings', {timeout: 10000});

    const matrixUiCheck = await teacherPage.evaluate(() => {
      const kpis = [...document.querySelectorAll('.matrix-kpi-row > *')].map((el) => {
        const r = el.getBoundingClientRect();
        return {text: el.textContent.trim(), left: r.left, right: r.right, top: r.top, bottom: r.bottom};
      });
      let kpiOverlap = false;
      for (let i = 0; i < kpis.length; i++) {
        for (let j = i + 1; j < kpis.length; j++) {
          const a = kpis[i],
            b = kpis[j];
          const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
          const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
          if (ox > 1 && oy > 1) kpiOverlap = true;
        }
      }
      const warn = document.querySelector('#matrix-reverse-warnings');
      const warnRect = warn?.getBoundingClientRect();
      const dlgRect = document.querySelector('#dialog')?.getBoundingClientRect();
      return {
        kpiCount: kpis.length,
        kpiOverlap,
        warnVisible: Boolean(warnRect && warnRect.height > 20),
        warnWithinDialog: Boolean(warnRect && dlgRect && warnRect.right <= dlgRect.right + 2),
        warnText: warn?.innerText?.trim() || '',
      };
    });
    assert(!matrixUiCheck.kpiOverlap, `KPI ma trận bị đè chữ: ${JSON.stringify(matrixUiCheck)}`);
    assert(matrixUiCheck.warnVisible && matrixUiCheck.warnWithinDialog, 'Cảnh báo ma trận ngược phải hiển thị gọn trong modal');
    const shotMatrix = await shot(teacherPage, 'uv61-matrix-warnings.png');
    await teacherPage.locator('#dialog button[data-action="close"]').first().click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // =========================================================================
    // 3. PHÒNG THI ONLINE & 3 HỌC SINH SONG SONG (SC-01 + AUDIO maxPlays=2 + CV 7991 + .XLSX)
    // =========================================================================
    const sc01 = corpusExams[0].exam;
    await teacherPage.locator('.design-rail [data-action="library"]').click();
    await teacherPage.waitForSelector(`#dialog [data-action="open-exam"][data-id="${sc01.id}"]`);
    await teacherPage.locator(`#dialog [data-action="open-exam"][data-id="${sc01.id}"]`).click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // Gắn file .wav thực qua form UI #audio-attach-form (maxPlays = 2)
    await teacherPage.locator('.editor-toolbar [data-action="exam-audio"]').click();
    await teacherPage.waitForSelector('#dialog[open] #audio-attach-form');
    await teacherPage.locator('#audio-attach-form input[name="audioFile"]').setInputFiles(wavFilePath);
    await teacherPage.locator('#audio-attach-form input[name="title"]').fill('Audio hướng dẫn thi Toán 9');
    await teacherPage.locator('#audio-attach-form input[name="maxPlays"]').fill('2');
    await teacherPage.locator('#audio-attach-form button[type="submit"]').click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);
    await teacherPage.locator('.paper .exam-audio-bar').waitFor();
    await waitSaved(teacherPage);

    // Mở tab/modal Phòng thi & tạo phòng bật allowLan: true
    await teacherPage.locator('.design-rail [data-action="exam-rooms"]').click();
    await teacherPage.waitForSelector('#dialog[open] .er-shell', {timeout: 10000});
    await teacherPage.locator('[data-er-action="toggle-create"]').click();
    await teacherPage.waitForSelector('#er-create-form');
    await teacherPage.locator('#er-c-title').fill('Phòng thi thực chiến UV61 · Toán 9');
    await teacherPage.locator('#er-c-class').fill('9A1');
    await teacherPage.locator('#er-c-duration').fill('45');
    await teacherPage.locator('#er-c-tabs').fill('3');
    await teacherPage.locator('#er-c-policy').selectOption('score_and_answers');
    await teacherPage.locator('#er-create-form [name="shuffleQuestions"]').uncheck();
    await teacherPage.locator('#er-create-form [name="shuffleOptions"]').uncheck();
    await teacherPage.locator('#er-create-form [name="allowLan"]').check();

    const [createRoomRes] = await Promise.all([
      teacherPage.waitForResponse((r) => r.url() === `${baseUrl}/api/rooms` && r.request().method() === 'POST'),
      teacherPage.locator('#er-create-form button[type="submit"]').click(),
    ]);
    assert.equal(createRoomRes.status(), 201, await createRoomRes.text());
    const roomCreated = await createRoomRes.json();
    assert.equal(roomCreated.allowLan, true, 'Phòng thi phải bật allowLan: true');
    assert(Array.isArray(roomCreated.lanUrls) && roomCreated.lanUrls.length >= 1, 'Phải sinh URL LAN khi bật allowLan');
    const roomId = roomCreated.id;
    const roomCode = roomCreated.roomCode;
    const joinUrl = `${baseUrl}/phong-thi/${roomCode}`;

    // 3 học sinh mở /phong-thi/{code} trên 3 browser context song song
    const studentsSpec = [
      {
        name: 'Nguyễn Minh An',
        classLabel: '9A1',
        code: 'HS01',
        mcqCorrectCount: 12, // full 3.00đ
        tf1: [true, false, true, false], // 4/4 = 1.00đ
        tf2: [true, true, true, true], // 3/4 = 0.50đ
        shortCorrectCount: 4, // 2.00đ
        essayText: 'Học sinh An trình bày chi tiết đầy đủ các bước chứng minh và kết luận nghiệm.',
        tabSwitches: 1,
        expectedTfPoints: 1.5,
      },
      {
        name: 'Trần Bảo Bình',
        classLabel: '9A1',
        code: 'HS02',
        mcqCorrectCount: 6, // 1.50đ
        tf1: [true, false, false, true], // 2/4 = 0.25đ
        tf2: [true, false, false, true], // 1/4 = 0.10đ
        shortCorrectCount: 2, // 1.00đ
        essayText: 'Học sinh Bình giải được ý chính của bài tự luận.',
        tabSwitches: 1,
        expectedTfPoints: 0.35,
      },
      {
        name: 'Lê Hải Châu',
        classLabel: '9A2',
        code: 'HS03',
        mcqCorrectCount: 0, // 0.00đ
        tf1: [false, true, false, true], // 0/4 = 0.00đ
        tf2: [true, true, true, false], // 4/4 = 1.00đ
        shortCorrectCount: 1, // 0.50đ
        essayText: 'Học sinh Châu mới nêu hướng làm.',
        tabSwitches: 0,
        expectedTfPoints: 1.0,
      },
    ];

    const studentContexts = [];
    for (let i = 0; i < studentsSpec.length; i++) {
      const ctx = await browser.newContext({viewport: {width: 1280, height: 860}});
      const p = await ctx.newPage();
      p.setDefaultTimeout(20000);
      attachTelemetry(p, `student-${i + 1}`, buckets);
      studentContexts.push({ctx, page: p, spec: studentsSpec[i]});
    }

    let shotStudent = '';
    try {
      // Join song song
      const joinInfo = await Promise.all(
        studentContexts.map(async ({page, spec}) => {
          await page.goto(joinUrl, {waitUntil: 'networkidle'});
          await page.waitForSelector('#sr-join-form');
          await page.locator('#sr-name').fill(spec.name);
          await page.locator('#sr-class').fill(spec.classLabel);
          await page.locator('#sr-scode').fill(spec.code);
          const [joinRes] = await Promise.all([
            page.waitForResponse((r) => r.url().endsWith(`/api/rooms/public/${roomCode}/join`) && r.request().method() === 'POST'),
            page.locator('#sr-join-form button[type="submit"]').click(),
          ]);
          assert.equal(joinRes.status(), 201, await joinRes.text());
          const joined = await joinRes.json();
          await page.waitForSelector('#sr-timer');
          await page.waitForSelector('.sr-audio-card');
          return joined;
        }),
      );

      // Học sinh 1: kiểm tra Audio maxPlays = 2 và chụp uv61-student-portal.png với TF CV 7991 + Audio + Timer
      const st1 = studentContexts[0];
      const audioRes1Promise = st1.page.waitForResponse(
        (r) => r.url().includes('/audio/') && r.request().method() === 'GET',
      );
      await st1.page.locator('[data-sr-action="play-audio"]').first().click();
      const audioRes1 = await audioRes1Promise;
      assert.equal(audioRes1.status(), 200, 'Lượt nghe audio 1 phải trả 200');
      assert.equal(audioRes1.headers()['x-audio-plays-remaining'], '1');
      await st1.page.waitForSelector('.sr-audio-el');

      // Chuyển sang câu Đúng/Sai đầu tiên (Câu 13, idx=12) ở chế độ từng câu để chụp ảnh cổng HS rõ Đúng/Sai + Audio + Đồng hồ
      await st1.page.locator('[data-sr-action="jump-q"][data-idx="12"]').first().click();
      await st1.page.locator('[data-sr-action="pick-tf"]').first().waitFor();
      await st1.page.waitForTimeout(200);
      shotStudent = await shot(st1.page, 'uv61-student-portal.png');

      // Nghe lượt 2 -> còn 0 lượt & nút play bị disable; thử request lần 3 trực tiếp trả 403
      const audioRes2Promise = st1.page.waitForResponse(
        (r) => r.url().includes('/audio/') && r.request().method() === 'GET',
      );
      await st1.page.locator('[data-sr-action="play-audio"]').first().click();
      const audioRes2 = await audioRes2Promise;
      assert.equal(audioRes2.status(), 200, 'Lượt nghe audio 2 phải trả 200');
      assert.equal(audioRes2.headers()['x-audio-plays-remaining'], '0');
      await st1.page.waitForFunction(
        () => Boolean(document.querySelector('[data-sr-action="play-audio"]')?.disabled),
        {timeout: 5000},
      );
      const thirdAudioRes = await st1.page.request.get(audioRes2.url(), {
        headers: {'X-Attempt-Token': joinInfo[0].attemptToken},
      });
      assert.equal(thirdAudioRes.status(), 403, 'Lượt nghe thứ 3 vượt maxPlays=2 phải bị chặn HTTP 403');

      // Học sinh 1, 2, 3 cùng làm bài song song & kích hoạt sự kiện chống gian lận
      const mcqQuestions = sc01.questions.filter((q) => q.type === 'mcq');
      const tfQuestions = sc01.questions.filter((q) => q.type === 'truefalse');
      const shortQuestions = sc01.questions.filter((q) => q.type === 'short');
      const essayQuestions = sc01.questions.filter((q) => q.type === 'essay');

      await Promise.all(
        studentContexts.map(async ({page, spec}, idx) => {
          await page.locator('[data-sr-action="view-mode"][data-mode="all"]').click();
          await page.locator('.sr-essay-input').first().waitFor();

          // MCQs
          for (let m = 0; m < mcqQuestions.length; m++) {
            const q = mcqQuestions[m];
            const pickIdx = m < spec.mcqCorrectCount ? q.answer : (q.answer + 1) % 4;
            await page.locator(`[data-sr-action="pick-mcq"][data-qid="${q.id}"][data-idx="${pickIdx}"]`).click();
          }

          // TF CV 7991
          const tfValsList = [spec.tf1, spec.tf2];
          for (let t = 0; t < tfQuestions.length; t++) {
            const q = tfQuestions[t];
            const vals = tfValsList[t];
            for (let r = 0; r < 4; r++) {
              await page
                .locator(`[data-sr-action="pick-tf"][data-qid="${q.id}"][data-row="${r}"][data-val="${vals[r]}"]`)
                .click();
            }
          }

          // Short answers
          for (let s = 0; s < shortQuestions.length; s++) {
            const q = shortQuestions[s];
            const ansVal = s < spec.shortCorrectCount ? String(q.answerText) : '99999';
            const inp = page.locator(`.sr-short-input[data-qid="${q.id}"]`);
            await inp.fill(ansVal);
            await inp.evaluate((el) => el.blur());
          }

          // Essays
          for (let e = 0; e < essayQuestions.length; e++) {
            const q = essayQuestions[e];
            const ta = page.locator(`.sr-essay-input[data-qid="${q.id}"]`);
            await ta.fill(`${spec.essayText} (Ý ${e + 1})`);
            await ta.evaluate((el) => el.blur());
          }

          // Sự kiện tab-switch / blur chống gian lận
          if (spec.tabSwitches > 0) {
            const evPromise = page.waitForResponse(
              (r) => r.url().includes('/events') && r.request().method() === 'POST',
            );
            await page.evaluate(() => {
              Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
              document.dispatchEvent(new Event('visibilitychange'));
              window.dispatchEvent(new Event('blur'));
              Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
              document.dispatchEvent(new Event('visibilitychange'));
            });
            await evPromise;
          }

          // Chờ đồng bộ đáp án xong trước khi nộp
          await page.waitForTimeout(800);
          await page.locator('[data-sr-action="ask-submit"]').first().click();
          const submitResPromise = page.waitForResponse(
            (r) => r.url().endsWith('/submit') && r.request().method() === 'POST',
          );
          await page.locator('[data-sr-action="confirm-submit"]').click();
          const submitRes = await submitResPromise;
          assert.equal(submitRes.status(), 200, `Học sinh ${idx + 1} nộp bài thất bại`);
          await page.waitForSelector('.sr-result-wrap', {timeout: 12000});
        }),
      );

      // Xác minh điểm tự động Đúng/Sai CV 7991 (đủ cả 5 mức 0 / 0.10 / 0.25 / 0.50 / 1.00)
      for (let i = 0; i < studentContexts.length; i++) {
        const {page, spec} = studentContexts[i];
        const attId = joinInfo[i].attemptId;
        const attTok = joinInfo[i].attemptToken;
        const resData = await page.evaluate(
          async ({id, tok}) => {
            const r = await fetch(`/api/rooms/public/attempts/${id}/result`, {
              headers: {'X-Attempt-Token': tok},
            });
            return r.json();
          },
          {id: attId, tok: attTok},
        );
        const tfItems = (resData.questions || []).filter((q) => q.type === 'truefalse');
        const tfSumP100 = tfItems.reduce((acc, q) => acc + Number(q.earnedPointsP100 || 0), 0);
        assert.equal(
          Math.round(tfSumP100),
          Math.round(spec.expectedTfPoints * 100),
          `Học sinh ${spec.name} điểm Đúng/Sai CV 7991 phải là ${spec.expectedTfPoints}, nhận ${tfSumP100 / 100}`,
        );
      }
    } finally {
      for (const {ctx} of studentContexts) {
        await ctx.close();
      }
    }

    // Giáo viên theo dõi, kiểm tra chống gian lận, chấm tự luận theo rubric & xuất .xlsx
    await teacherPage.locator('[data-er-action="switch-tab"][data-tab="monitor"]').click();
    await teacherPage.waitForSelector('[data-er-action="refresh-room"]');
    await teacherPage.locator('[data-er-action="refresh-room"]').click();
    await teacherPage.waitForFunction(
      () =>
        document.body.innerText.includes('Nguyễn Minh An') &&
        document.body.innerText.includes('Trần Bảo Bình') &&
        document.body.innerText.includes('Lê Hải Châu'),
      {timeout: 10000},
    );

    // Kiểm tra tab Chấm tự luận & chấm toàn bộ các bài tự luận của 3 học sinh
    await teacherPage.locator('[data-er-action="switch-tab"][data-tab="grading"]').click();
    await teacherPage.waitForSelector('.er-grade-form', {timeout: 10000});
    const gradeCount = await teacherPage.locator('.er-grade-form').count();
    assert.equal(gradeCount, 12, `Phải có 12 bài tự luận chờ chấm (3 HS x 4 bài), thấy ${gradeCount}`);
    for (let g = 0; g < gradeCount; g++) {
      const form = teacherPage.locator('.er-grade-form').first();
      const attId = await form.getAttribute('data-attempt-id');
      const maxP100 = Number(await form.getAttribute('data-max-p100'));
      const studentNameHint = g < 4 ? 'An' : g < 8 ? 'Bình' : 'Châu';
      const targetScore = ((maxP100 * (g % 3 === 0 ? 1 : g % 3 === 1 ? 0.5 : 0.25)) / 100).toFixed(2);
      await form.locator('[name="earnedPoints"]').fill(targetScore);
      await form.locator('[name="graderNote"]').fill(`Đã chấm rubric bài tự luận (${studentNameHint}) · ${attId.slice(0, 6)}`);
      const gradeResPromise = teacherPage.waitForResponse(
        (r) => r.url().includes('/grades/') && r.request().method() === 'PUT',
      );
      const queueRefreshPromise = teacherPage.waitForResponse(
        (r) => r.url().includes('/grading-queue') && r.request().method() === 'GET',
      );
      await form.locator('button[type="submit"]').click();
      const gradeRes = await gradeResPromise;
      assert.equal(gradeRes.status(), 200, 'Lưu điểm tự luận phải trả 200 OK');
      await queueRefreshPromise;
      await teacherPage.waitForFunction(
        (remaining) => document.querySelectorAll('.er-grade-form').length === remaining,
        gradeCount - g - 1,
        {timeout: 10000},
      );
    }

    // Chuyển tab Thống kê & Xuất bảng điểm (có đủ 3 học sinh + điểm + nút tải .xlsx), chụp ảnh & xuất file
    await teacherPage.locator('[data-er-action="switch-tab"][data-tab="analytics"]').click();
    await teacherPage.waitForSelector('[data-er-action="export-xlsx"]', {timeout: 10000});
    await teacherPage.waitForTimeout(250);
    const analyticsCheck = await teacherPage.evaluate(async (rid) => {
      const res = await fetch(`/api/rooms/${rid}/analytics`);
      const data = await res.json();
      const kpis = [...document.querySelectorAll('.er-kpi')].map((el) => el.innerText.replace(/\s+/g, ' ').trim());
      return {status: res.status, maxScoreP100: data.maxScoreP100, minScoreP100: data.minScoreP100, avgScoreP100: data.avgScoreP100, medianScoreP100: data.medianScoreP100, kpis};
    }, roomId);
    assert.equal(analyticsCheck.status, 200);
    assert.ok(analyticsCheck.maxScoreP100 >= analyticsCheck.minScoreP100, 'maxScoreP100 phải >= minScoreP100');
    const shotTeacherRoom = await shot(teacherPage, 'uv61-exam-room-teacher.png');

    const [xlsxDl] = await Promise.all([
      teacherPage.waitForEvent('download'),
      teacherPage.locator('[data-er-action="export-xlsx"]').click(),
    ]);
    await xlsxDl.saveAs(xlsxOutPath);

    // Xác minh file .xlsx hợp lệ bằng Python zipfile + XML chứa đủ 3 học sinh
    const xlsxAudit = JSON.parse(
      execFileSync(
        PYTHON_EXE,
        [
          '-c',
          [
            'import json, sys, xml.etree.ElementTree as ET, zipfile',
            'p = sys.argv[1]',
            'zf = zipfile.ZipFile(p)',
            'names = zf.namelist()',
            'wb = zf.read("xl/workbook.xml").decode("utf-8")',
            'sheets = [zf.read(n).decode("utf-8") for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]',
            'shared = zf.read("xl/sharedStrings.xml").decode("utf-8") if "xl/sharedStrings.xml" in names else ""',
            'blob = wb + "\\n" + shared + "\\n" + "\\n".join(sheets)',
            'missing = [s for s in ("BangDiem", "ThongKeCauHoi", "Nguyễn Minh An", "Trần Bảo Bình", "Lê Hải Châu") if s not in blob]',
            'ET.fromstring(zf.read("xl/workbook.xml"))',
            'for s in sheets:\n    ET.fromstring(s)',
            'print(json.dumps({"files": len(names), "sheets": len(sheets), "missing": missing, "workbook": wb[:400]}, ensure_ascii=False))',
          ].join('\n'),
          xlsxOutPath,
        ],
        {encoding: 'utf8'},
      ),
    );
    assert.deepEqual(xlsxAudit.missing, [], `File .xlsx thiếu dữ liệu: ${JSON.stringify(xlsxAudit)}`);
    assert(xlsxAudit.sheets >= 2, 'Excel phải có >= 2 sheet BangDiem và ThongKeCauHoi');

    await teacherPage.locator('#dialog button[data-action="close"]').first().click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // =========================================================================
    // 4. TRỢ LÝ AI & KẾT NỐI 2 TẦNG (/api/providers/health + SSE /api/assistant/chat/stream)
    // =========================================================================
    await teacherPage.locator('.assistant-head [data-ux-action="options"]').click();
    await teacherPage.waitForSelector('.ux-chat-options [data-action="connections"]', {state: 'visible'});
    const [healthRes] = await Promise.all([
      teacherPage.waitForResponse(
        (r) => r.url() === `${baseUrl}/api/providers/health` && r.request().method() === 'GET',
      ),
      teacherPage.locator('.ux-chat-options [data-action="connections"]').click(),
    ]);
    await teacherPage.waitForSelector('#dialog[open] #connections-form');
    assert.equal(healthRes.status(), 200);
    const healthJson = await healthRes.json();
    await teacherPage.waitForSelector('#providers-health-strip [data-health-card]', {timeout: 12000});
    // Mở Tầng 2 để xác minh trực quan cả 2 tầng trong modal Kết nối
    await teacherPage.locator('.poc-key-vault > summary').click();
    await teacherPage.waitForTimeout(200);
    const tierCheck = await teacherPage.evaluate(() => ({
      text: document.querySelector('#connections-form')?.innerText || '',
      healthCount: document.querySelectorAll('#providers-health-strip > *').length,
      vaultOpen: Boolean(document.querySelector('.poc-key-vault')?.open),
    }));
    assert(tierCheck.text.includes('Tầng 1') && tierCheck.text.includes('Tầng 2'), 'Modal Kết nối phải hiển thị đủ Tầng 1 và Tầng 2');
    assert(tierCheck.vaultOpen && tierCheck.healthCount >= 4, `Health strip phải có >= 4 kênh AI: ${JSON.stringify(tierCheck)}`);
    const shotConnections = await shot(teacherPage, 'uv61-connections-2tier.png');
    await teacherPage.locator('#dialog button[data-action="close"]').first().click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // Kiểm tra luồng chat SSE /api/assistant/chat/stream (trên router fixture cô lập nếu chưa có key live)
    sseData = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-uv61-sse-'));
    const ssePort = await freePort();
    const sseStarted = await startIsolatedServer(ssePort, sseData, {fixtureCase: 'repair'});
    sseProc = sseStarted.proc;
    const sseCtx = await browser.newContext({viewport: {width: 1280, height: 860}});
    const ssePage = await sseCtx.newPage();
    ssePage.setDefaultTimeout(20000);
    attachTelemetry(ssePage, 'sse-chat', buckets);
    try {
      await ssePage.goto(sseStarted.baseUrl, {waitUntil: 'networkidle'});
      await ssePage.waitForSelector('#chat-input');
      const optionsBtn = ssePage.locator('.assistant-head [data-ux-action="options"]');
      const chatOptions = ssePage.locator('#chat-options');
      if (await optionsBtn.count() && await chatOptions.count() && !(await chatOptions.isVisible())) {
        await optionsBtn.first().click();
        await chatOptions.waitFor({state: 'visible'});
      }
      const consentBox = ssePage.locator('#ai-consent');
      if (await consentBox.count()) await consentBox.check();
      const modeSel = ssePage.locator('#chat-mode');
      if (await modeSel.count()) await modeSel.selectOption('ask');
      if (await optionsBtn.count() && await chatOptions.count() && (await chatOptions.isVisible())) {
        await optionsBtn.first().click();
      }

      const sseRespPromise = ssePage.waitForResponse(
        (r) => r.url().endsWith('/api/assistant/chat/stream') && r.request().method() === 'POST',
      );
      await ssePage.locator('#chat-input').fill('Giải thích ngắn cách kiểm tra phương trình');
      await ssePage.locator('#chat-form button[type="submit"]').click();
      const sseResp = await sseRespPromise;
      assert.equal(sseResp.status(), 200, 'SSE /api/assistant/chat/stream phải trả 200');
      assert.match(sseResp.headers()['content-type'] || '', /text\/event-stream/i);
      await ssePage.waitForFunction(
        () =>
          [...document.querySelectorAll('.assistant-body .assistant-message.role-assistant')].some((el) =>
            el.innerText.includes('Giải thích mẫu để kiểm tra chế độ Chỉ hỏi'),
          ),
        {timeout: 12000},
      );
    } finally {
      await sseCtx.close();
    }

    assert.deepEqual(buckets.consoleErrors, [], `Phát hiện console.error: ${buckets.consoleErrors.join('; ')}`);
    assert.deepEqual(buckets.pageErrors, [], `Phát hiện pageerror: ${buckets.pageErrors.join('; ')}`);
    assert.deepEqual(buckets.http5xx, [], `Phát hiện HTTP 5xx: ${buckets.http5xx.join('; ')}`);

    console.log(
      JSON.stringify(
        {
          ok: true,
          corpusCount: corpusChecks.length,
          matricesChecked: {
            mergedDocxRows: mMergedDocx.body.matrix.length,
            pdf2PagesCount: mPdf2Pages.body.count,
            formulaXlsxCode: mFormulaXlsx.body.code,
            twoTablesCount: mTwoTablesDocx.body.count,
            specOnlyCode: mSpecOnly.body.code,
          },
          matrixUiCheck,
          room: {roomId, roomCode, allowLan: roomCreated.allowLan, lanUrlsCount: roomCreated.lanUrls.length},
          studentsVerified: studentsSpec.map((s) => ({name: s.name, expectedTfPoints: s.expectedTfPoints})),
          gradedEssays: gradeCount,
          analyticsCheck,
          xlsxAudit,
          providersHealth: healthJson,
          sseVerified: true,
          consoleErrors: buckets.consoleErrors,
          pageErrors: buckets.pageErrors,
          http5xx: buckets.http5xx,
          screenshots: {
            desktop1440: shot1440,
            desktop1280: shot1280,
            mobile390: shot390,
            matrixWarnings: shotMatrix,
            examRoomTeacher: shotTeacherRoom,
            studentPortal: shotStudent,
            libraryModal: shotLibrary,
            connections2Tier: shotConnections,
          },
        },
        null,
        2,
      ),
    );
  } catch (err) {
    console.error('REAL_E2E_ERROR:', err);
    console.error('SERVER_LOGS:', getLogs().slice(-2000));
    throw err;
  } finally {
    if (browser) await browser.close();
    await stopServer(sseProc);
    await stopServer(proc);
    fs.rmSync(tmpData, {recursive: true, force: true});
    if (sseData) fs.rmSync(sseData, {recursive: true, force: true});
  }
}

await main();
