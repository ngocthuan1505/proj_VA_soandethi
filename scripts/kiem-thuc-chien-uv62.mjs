import assert from 'node:assert/strict';
import {execFileSync, spawn} from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import JSZip from 'jszip';
import {chromium} from 'playwright-core';

const ROOT = process.cwd();
const PYTHON_EXE = process.env.QA_PYTHON || path.join(ROOT, 'backend', '.venv', 'Scripts', 'python.exe');
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);

const EVIDENCE_DIR = process.env.QA_UV62_SCREENSHOT_DIR
  ? path.resolve(process.env.QA_UV62_SCREENSHOT_DIR)
  : 'C:\\Users\\nguye\\.gemini\\antigravity\\brain\\f3eea969-4834-47f8-8318-93e7d029e582\\qa-uv62-evidence';

function findChrome() {
  for (const candidate of CHROME_CANDIDATES) {
    if (fs.existsSync(candidate)) return candidate;
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

function buildSampleWavBuffer(seconds = 0.25, sampleRate = 8000) {
  const numSamples = Math.floor(seconds * sampleRate);
  const dataSize = numSamples * 2;
  const buf = Buffer.alloc(44 + dataSize);
  buf.write('RIFF', 0);
  buf.writeUInt32LE(36 + dataSize, 4);
  buf.write('WAVE', 8);
  buf.write('fmt ', 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate * 2, 28);
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write('data', 36);
  buf.writeUInt32LE(dataSize, 40);
  for (let i = 0; i < numSamples; i++) {
    const sample = Math.round(Math.sin((2 * Math.PI * 440 * i) / sampleRate) * 6000);
    buf.writeInt16LE(sample, 44 + i * 2);
  }
  return buf;
}

async function startLocalServer(port, dataDir) {
  const proc = spawn(
    PYTHON_EXE,
    [
      '-m',
      'uvicorn',
      'mach_backend.local_workspace:app',
      '--app-dir',
      path.join(ROOT, 'backend', 'src'),
      '--host',
      '127.0.0.1',
      '--port',
      String(port),
    ],
    {
      cwd: ROOT,
      env: {
        ...process.env,
        MACH_DATA_DIR: dataDir,
        PYTHONPATH: path.join(ROOT, 'backend', 'src'),
        NO_PROXY: '127.0.0.1,localhost',
        PYTHONIOENCODING: 'utf-8',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
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
      throw new Error(`Uvicorn local thoát sớm (${proc.exitCode}):\n${logs}`);
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

async function startSseStrictServer(port, dataDir, captureLogPath) {
  const pyScript = `
import json, pathlib, sys, uvicorn
from mach_backend.local_workspace import create_app

data_dir = pathlib.Path(sys.argv[1])
capture_file = pathlib.Path(sys.argv[2])

async def _uv62_agent(purpose, body):
    captured = {"purpose": purpose, "body": body}
    capture_file.write_text(json.dumps(captured, ensure_ascii=False), encoding="utf-8")
    raw = json.dumps(body, ensure_ascii=False)
    has_p2 = "DINH_LY_TRANG_2_DOC_QUYEN" in raw
    has_p1 = "BI_MAT_TRANG_1_KHONG_CHON" in raw
    msg = f"Đã đọc đúng ngữ liệu giáo viên chọn (p2={has_p2}, p1={has_p1})."
    return {
        "role": "assistant",
        "content": json.dumps({"message": msg, "followUps": ["Tóm tắt trang 2"]}, ensure_ascii=False),
        "provider": "agy",
        "providerFamily": "agy",
        "model": "gemini-3-flash",
    }

app = create_app(data_dir, agent_call=_uv62_agent)
uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[3]), log_level="warning")
`;
  const proc = spawn(
    PYTHON_EXE,
    ['-c', pyScript, dataDir, captureLogPath, String(port)],
    {
      cwd: ROOT,
      env: {
        ...process.env,
        PYTHONPATH: path.join(ROOT, 'backend', 'src'),
        NO_PROXY: '127.0.0.1,localhost',
        PYTHONIOENCODING: 'utf-8',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
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
      throw new Error(`Uvicorn SSE thoát sớm (${proc.exitCode}):\n${logs}`);
    }
    try {
      const res = await fetch(`${baseUrl}/api/status`);
      if (res.ok) return {proc, baseUrl, getLogs: () => logs};
    } catch {
      // retry
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  await stopServer(proc);
  throw new Error(`Timeout chờ SSE server trên ${baseUrl}:\n${logs}`);
}

async function startTeamServer(port, teamDataDir) {
  const proc = spawn(
    PYTHON_EXE,
    [
      '-m',
      'uvicorn',
      'mach_backend.team_workspace:app',
      '--app-dir',
      path.join(ROOT, 'backend', 'src'),
      '--host',
      '127.0.0.1',
      '--port',
      String(port),
    ],
    {
      cwd: ROOT,
      env: {
        ...process.env,
        MACH_TEAM_DATA_DIR: teamDataDir,
        PYTHONPATH: path.join(ROOT, 'backend', 'src'),
        NO_PROXY: '127.0.0.1,localhost',
        PYTHONIOENCODING: 'utf-8',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
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
      throw new Error(`Uvicorn team thoát sớm (${proc.exitCode}):\n${logs}`);
    }
    try {
      const res = await fetch(`${baseUrl}/api/team/health`);
      if (res.ok) return {proc, baseUrl, getLogs: () => logs};
    } catch {
      // retry
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  await stopServer(proc);
  throw new Error(`Timeout chờ team server trên ${baseUrl}:\n${logs}`);
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
      const text = msg.text();
      if (!/status of (400|403|409|422)\b/.test(text)) {
        buckets.consoleErrors.push(`[${label}] ${text}`);
      }
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

async function shot(page, filename) {
  fs.mkdirSync(EVIDENCE_DIR, {recursive: true});
  const dest = path.join(EVIDENCE_DIR, filename);
  await page.screenshot({path: dest});
  return dest;
}

async function waitSaved(page) {
  await page.waitForFunction(
    () => (document.querySelector('.saved')?.textContent || '').includes('Đã lưu'),
    {timeout: 12000},
  );
}

async function run() {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-uv62-main-'));
  const sseDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-uv62-sse-'));
  const teamDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-uv62-team-'));
  const sseCaptureFile = path.join(sseDataDir, 'captured-chat.json');
  const wavFilePath = path.join(dataDir, 'uv62-listening.wav');
  const xlsxOutPath = path.join(dataDir, 'bang-diem-uv62.xlsx');
  fs.writeFileSync(wavFilePath, buildSampleWavBuffer());

  let mainProc = null;
  let sseProc = null;
  let teamProc = null;
  let browser = null;
  const buckets = {consoleErrors: [], pageErrors: [], http5xx: []};

  try {
    const port = await freePort();
    const started = await startLocalServer(port, dataDir);
    mainProc = started.proc;
    const baseUrl = started.baseUrl;

    browser = await chromium.launch({
      executablePath: findChrome(),
      headless: true,
      args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    });

    const sc01 = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests/fixtures/school-corpus/SC-01.json'), 'utf8'));
    const sc02 = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests/fixtures/school-corpus/SC-02.json'), 'utf8'));
    const sc06 = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests/fixtures/school-corpus/SC-06.json'), 'utf8'));

    // Prepare UC9 test exam (quote variants + evidence) and preflight-invalid exam
    const uc9Exam = {
      ...structuredClone(sc01),
      id: 'uv62-uc9-quote-exam',
      title: 'Kiểm tra Ngữ văn UC9 · Stale Evidence',
      subject: 'Ngữ văn',
      grade: '11',
      minutes: 45,
      school: 'TRƯỜNG THPT CÁ VOI XANH',
      department: 'TỔ NGỮ VĂN',
      workflowStatus: 'draft',
      sample: false,
      matrixConfirmed: false,
      appliedPrefs: [],
      undo: [],
      redo: [],
      revision: 1,
      updated: Date.now(),
      docs: [
        {
          id: 'doc-uc9',
          name: 'Ngữ liệu văn học gốc',
          kind: 'text',
          version: 1,
          pages: [{number: 1, text: 'Bản văn gốc thứ nhất dùng để trích dẫn kiểm chứng.'}],
          text: 'Bản văn gốc thứ nhất dùng để trích dẫn kiểm chứng.',
        },
      ],
      quote: {
        text: 'Bản văn gốc thứ nhất dùng để trích dẫn kiểm chứng.',
        chosen: 'qv1',
        versions: [
          {
            id: 'qv1',
            docId: 'doc-uc9',
            page: 1,
            location: 'Trang 1 · Bản gốc',
            text: 'Bản văn gốc thứ nhất dùng để trích dẫn kiểm chứng.',
          },
          {
            id: 'qv2',
            docId: 'doc-uc9',
            page: 1,
            location: 'Trang 1 · Bản đối chiếu mới',
            text: 'Bản văn đã hiệu đính thứ hai dùng để đối chiếu lại.',
          },
        ],
      },
      questions: [
        {
          id: 'uc9-q1',
          v: 1,
          type: 'mcq',
          stem: 'Đoạn trích trên mang nội dung chính nào sau đây?',
          options: ['Phương án 1', 'Phương án 2', 'Phương án 3', 'Phương án 4'],
          answer: 0,
          answerKnown: true,
          explanation: 'Theo bản gốc trang 1.',
          rubric: [],
          points: 2.0,
          topic: 'Đọc hiểu',
          level: 1,
          quote: true,
          check: null,
          evidence: [
            {
              id: 'ev-uc9-1',
              quote: 'Bản văn gốc thứ nhất dùng để trích dẫn kiểm chứng.',
              snippet: 'Bản văn gốc thứ nhất dùng để trích dẫn kiểm chứng.',
              docId: 'doc-uc9',
              page: 1,
            },
          ],
          source: {docId: 'doc-uc9', page: 1, location: 'Trang 1 · Bản gốc'},
        },
      ],
      matrix: [],
      chat: [],
      history: [],
    };

    const brokenRoomExam = {
      ...structuredClone(sc01),
      id: 'uv62-broken-preflight-exam',
      title: 'Đề chưa hoàn chỉnh (Chặn mở phòng 422)',
      subject: 'Toán',
      grade: '9',
      minutes: 45,
      school: 'TRƯỜNG THCS CÁ VOI XANH',
      department: 'TỔ TOÁN',
      workflowStatus: 'draft',
      sample: false,
      matrixConfirmed: false,
      appliedPrefs: [],
      undo: [],
      redo: [],
      quote: {text: '', chosen: '', versions: []},
      revision: 1,
      updated: Date.now(),
      docs: [],
      questions: [
        {
          id: 'brk-q1',
          v: 1,
          type: 'mcq',
          stem: 'Câu hỏi chưa khóa đáp án để kiểm tra cổng preflight 422: $\\sqrt{x+2} = 3$?',
          options: ['x = 7', 'x = 5', 'x = 9', 'x = 1'],
          answer: 0,
          answerKnown: false,
          explanation: '',
          rubric: [],
          points: 1.0,
          topic: 'Phương trình căn thức',
          level: 1,
          source: null,
          check: null,
        },
      ],
      matrix: [],
      chat: [],
      history: [],
    };

    const outlineUnicodeExam = {
      ...structuredClone(sc01),
      id: 'uv62-unicode-outline-exam',
      title: 'Đề kiểm tra ký hiệu Outline $\\sqrt{x+1}$ & $\\triangle ABC$',
      subject: 'Toán',
      grade: '9',
      minutes: 45,
      school: 'TRƯỜNG THCS CÁ VOI XANH',
      department: 'TỔ TOÁN',
      workflowStatus: 'reviewed',
      sample: false,
      appliedPrefs: [],
      undo: [],
      redo: [],
      quote: {text: '', chosen: '', versions: []},
      revision: 1,
      updated: Date.now(),
      docs: [],
      questions: [
        {
          id: 'uni-q1',
          v: 1,
          type: 'mcq',
          stem: 'Điều kiện xác định của biểu thức $\\sqrt{x+1}$ trong $\\triangle ABC$ là gì?',
          options: ['$x \\ge -1$', '$x > -1$', '$x \\le -1$', '$x < -1$'],
          answer: 0,
          answerKnown: true,
          explanation: 'Biểu thức dưới dấu căn không âm: $x + 1 \\ge 0$.',
          rubric: [],
          points: 1.0,
          topic: 'Căn bậc hai',
          level: 0,
          source: null,
          check: null,
        },
        ...structuredClone(sc01.questions.slice(1, 5)),
      ],
      matrix: [],
      chat: [],
      history: [],
    };

    // Normalize SC-01 workflowStatus='reviewed' in seed so SC-01 starts as "Đã rà soát"
    const sc01Reviewed = {...sc01, workflowStatus: 'reviewed'};

    const teacherCtx = await browser.newContext({viewport: {width: 1440, height: 900}});
    const teacherPage = await teacherCtx.newPage();
    teacherPage.setDefaultTimeout(20000);
    attachTelemetry(teacherPage, 'teacher', buckets);

    const wavBytes = buildSampleWavBuffer();
    const putAudio = await teacherPage.request.put(`${baseUrl}/api/kv`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {key: 'file:48d8617b-539b-553a-8b5f-edd7048e5327', value: `data:audio/wav;base64,${wavBytes.toString('base64')}`},
    });
    assert(putAudio.ok());

    const seedState = {
      version: 1,
      current: sc01Reviewed.id,
      exams: [sc01Reviewed, sc02, sc06, outlineUnicodeExam, brokenRoomExam, uc9Exam],
      prefs: [],
    };
    const putState = await teacherPage.request.put(`${baseUrl}/api/kv`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {key: 'state', value: seedState},
    });
    assert(putState.ok());

    await teacherPage.goto(baseUrl, {waitUntil: 'networkidle'});
    await teacherPage.locator('.paper .question').first().waitFor();
    await teacherPage.evaluate(() => document.fonts?.ready);
    await teacherPage.waitForTimeout(350);

    // =========================================================================
    // 1. BLUE WHALE THEME, VIEWPORTS (1440, 1280, 390), WORKFLOW & UNICODE OUTLINE
    // =========================================================================
    const checkViewport1440 = await teacherPage.evaluate(() => {
      const rootStyle = getComputedStyle(document.documentElement);
      const brand = rootStyle.getPropertyValue('--brand').trim().toLowerCase();
      const paper = document.querySelector('.document-page') || document.querySelector('.paper');
      const paperBg = paper ? getComputedStyle(paper).backgroundColor : '';
      const wfSelect = document.querySelector('#workflow-status-select');
      const wfLabel = wfSelect?.selectedOptions?.[0]?.textContent?.trim() || '';
      const wfValue = wfSelect?.value || '';
      const wfStrip = document.querySelector('.workflow-strip') || document.querySelector('.wf-steps');
      const stripRect = wfStrip?.getBoundingClientRect();
      const wfButtons = [...document.querySelectorAll('.wf-steps button:not(.wf-step-vip)')].map((b) => {
        const r = b.getBoundingClientRect();
        return {
          text: b.innerText.replace(/\s+/g, ' ').trim(),
          clipped: Boolean(stripRect && r.right > stripRect.right + 1),
          width: Math.round(r.width),
        };
      });
      const bc = document.querySelector('.breadcrumb');
      const bcRect = bc?.getBoundingClientRect();
      const faviconHref = document.querySelector('link[rel="icon"]')?.getAttribute('href') || '';
      const overflowX = document.documentElement.scrollWidth > window.innerWidth + 1;
      return {brand, paperBg, wfValue, wfLabel, wfButtons, bcHeight: bcRect ? Math.round(bcRect.height) : 0, faviconHref, overflowX};
    });
    assert.equal(checkViewport1440.brand, '#0f4c81', `Token --brand phải là #0f4c81, nhận: ${checkViewport1440.brand}`);
    assert.equal(checkViewport1440.paperBg, 'rgb(255, 255, 255)', `Giấy .paper phải trắng #ffffff, nhận: ${checkViewport1440.paperBg}`);
    assert.equal(checkViewport1440.wfValue, 'reviewed');
    assert.equal(checkViewport1440.wfLabel, 'Đã rà soát', `Dropdown trạng thái phải hiển thị "Đã rà soát", nhận: "${checkViewport1440.wfLabel}"`);
    assert(checkViewport1440.wfButtons.length >= 4, `Phải có >= 4 nút .wf-steps, thấy ${checkViewport1440.wfButtons.length}`);
    assert(checkViewport1440.wfButtons.every((b) => !b.clipped && b.width > 40), `Có nút .wf-steps bị cắt ở 1440px: ${JSON.stringify(checkViewport1440.wfButtons)}`);
    assert(checkViewport1440.bcHeight <= 42, `Breadcrumb phải 1 dòng (got ${checkViewport1440.bcHeight}px)`);
    assert.equal(checkViewport1440.overflowX, false);
    await shot(teacherPage, 'uv62-desktop-1440x900.png');

    await teacherPage.setViewportSize({width: 1280, height: 720});
    await teacherPage.waitForTimeout(250);
    const checkViewport1280 = await teacherPage.evaluate(() => {
      const wfStrip = document.querySelector('.workflow-strip') || document.querySelector('.wf-steps');
      const stripRect = wfStrip?.getBoundingClientRect();
      const wfButtons = [...document.querySelectorAll('.wf-steps button:not(.wf-step-vip)')].map((b) => {
        const r = b.getBoundingClientRect();
        return {text: b.innerText.replace(/\s+/g, ' ').trim(), clipped: Boolean(stripRect && r.right > stripRect.right + 1)};
      });
      return {
        overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
        wfButtons,
      };
    });
    assert.equal(checkViewport1280.overflowX, false);
    assert(checkViewport1280.wfButtons.every((b) => !b.clipped), `Có nút .wf-steps bị cắt ở 1280px: ${JSON.stringify(checkViewport1280.wfButtons)}`);
    await shot(teacherPage, 'uv62-desktop-1280x720.png');

    await teacherPage.setViewportSize({width: 390, height: 844});
    await teacherPage.waitForTimeout(250);
    assert.equal(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true, 'Mobile 390 không tràn ngang');
    await shot(teacherPage, 'uv62-mobile-390x844.png');

    await teacherPage.setViewportSize({width: 1440, height: 900});
    await teacherPage.waitForTimeout(200);

    // Kiểm tra Outline Unicode (√, △, không mangled \sqrt/\triangle) trên outlineUnicodeExam
    await teacherPage.locator('.design-rail [data-action="library"]').click();
    await teacherPage.waitForSelector(`#dialog [data-action="open-exam"][data-id="${outlineUnicodeExam.id}"]`);
    await teacherPage.locator(`#dialog [data-action="open-exam"][data-id="${outlineUnicodeExam.id}"]`).click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);
    await teacherPage.locator('#q-uni-q1').waitFor({timeout: 8000});
    await teacherPage.waitForFunction(
      () => (document.querySelector('.outline-item .outline-title')?.textContent || '').includes('△'),
      {timeout: 5000},
    );
    const firstOutlineTitle = await teacherPage.locator('.outline-item .outline-title').first().innerText();
    assert(firstOutlineTitle.includes('√') && firstOutlineTitle.includes('△'), `Outline phải đổi LaTeX sang Unicode √/△, nhận: "${firstOutlineTitle}"`);
    assert(!/\\sqrt|\\triangle/.test(firstOutlineTitle), `Outline còn sót LaTeX thô: "${firstOutlineTitle}"`);

    // =========================================================================
    // 2. EMPTY CANVAS WHALE, ANALYTICS MODAL & QUESTION BANK MODAL
    // =========================================================================
    await teacherPage.locator('[data-action="new"]').first().click();
    await teacherPage.waitForSelector('#dialog[open] [data-action="create-blank"]');
    await teacherPage.locator('#dialog [data-action="create-blank"]').click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);
    await teacherPage.waitForSelector('.empty-paper-canvas .empty-whale-art svg');
    await shot(teacherPage, 'uv62-empty-canvas-whale.png');

    // Quay về SC-01 để kiểm tra Analytics & QBank
    await teacherPage.locator('.design-rail [data-action="library"]').click();
    await teacherPage.waitForSelector(`#dialog [data-action="open-exam"][data-id="${sc01Reviewed.id}"]`);
    await teacherPage.locator(`#dialog [data-action="open-exam"][data-id="${sc01Reviewed.id}"]`).click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);
    await teacherPage.locator('.paper .question').first().waitFor();

    await teacherPage.locator('.design-rail [data-action="exam-analytics"]').click();
    await teacherPage.waitForSelector('#dialog[open] .analytics-kpi-grid');
    await teacherPage.waitForTimeout(200);
    const analyticsStyle = await teacherPage.evaluate(() => {
      const grid = document.querySelector('.analytics-kpi-grid');
      const cs = grid ? getComputedStyle(grid) : null;
      return {display: cs?.display || '', cardCount: document.querySelectorAll('.analytics-kpi-grid .analytics-kpi').length};
    });
    assert.equal(analyticsStyle.display, 'grid', '.analytics-kpi-grid phải dùng CSS grid');
    assert.equal(analyticsStyle.cardCount, 4);
    await shot(teacherPage, 'uv62-analytics-modal.png');
    await teacherPage.locator('#dialog button[data-action="close"]').first().click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    await teacherPage.locator('.design-rail [data-action="question-bank"]').click();
    await teacherPage.waitForSelector('#dialog[open]');
    if ((await teacherPage.locator('#dialog .qbank-card').count()) === 0) {
      await teacherPage.locator('#dialog [data-action="save-all-to-bank"]').click();
      await teacherPage.waitForSelector('#dialog .qbank-card', {timeout: 8000});
    }
    const qbankCheck = await teacherPage.evaluate(() => ({
      cards: document.querySelectorAll('#dialog .qbank-card').length,
      badges: document.querySelectorAll('#dialog .qbank-badge').length,
      insertBtns: document.querySelectorAll('#dialog [data-action="insert-from-bank"]').length,
    }));
    assert(qbankCheck.cards >= 1 && qbankCheck.badges >= 1 && qbankCheck.insertBtns >= 1, `QBank thiếu thẻ/nhãn: ${JSON.stringify(qbankCheck)}`);
    await shot(teacherPage, 'uv62-qbank-modal.png');
    await teacherPage.locator('#dialog button[data-action="close"]').first().click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // =========================================================================
    // 3. TEAM LOGIN /login BLUE WHALE CHECK
    // =========================================================================
    const teamPort = await freePort();
    const teamStarted = await startTeamServer(teamPort, teamDataDir);
    teamProc = teamStarted.proc;
    const teamCtx = await browser.newContext({viewport: {width: 1280, height: 800}});
    const teamPage = await teamCtx.newPage();
    attachTelemetry(teamPage, 'team-login', buckets);
    await teamPage.goto(`${teamStarted.baseUrl}/login`, {waitUntil: 'networkidle'});
    await teamPage.evaluate(() => document.fonts?.ready);
    await teamPage.waitForTimeout(250);
    const loginAudit = await teamPage.evaluate(() => {
      const iconImg = document.querySelector('img[src*="exam-icon.svg"]');
      const hasInlineSvg = Boolean(document.querySelector('svg'));
      const overflowX = document.documentElement.scrollWidth > window.innerWidth + 1;
      const bodyBg = getComputedStyle(document.body).backgroundColor;
      return {
        imgComplete: Boolean(iconImg && iconImg.complete && iconImg.naturalWidth > 0),
        hasSvg: Boolean(iconImg || hasInlineSvg),
        overflowX,
        bodyBg,
        hasForm: Boolean(document.querySelector('form')),
      };
    });
    assert(loginAudit.hasSvg && loginAudit.hasForm && !loginAudit.overflowX, `Team /login lỗi: ${JSON.stringify(loginAudit)}`);
    await shot(teamPage, 'uv62-team-login-whale.png');
    await teamCtx.close();
    await stopServer(teamProc);
    teamProc = null;

    // =========================================================================
    // 4. PHÒNG THI: CỔNG 422 PREFLIGHT, SCORE_ONLY, 3 HS SONG SONG, KATEX ANALYTICS & MOBILE 390
    // =========================================================================
    // 4a) 422 Preflight Gate (API + UI)
    const badRoomRes = await teacherPage.request.post(`${baseUrl}/api/rooms`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {
        examId: brokenRoomExam.id,
        title: 'Phòng không hợp lệ',
        mode: 'exam',
        durationMinutes: 30,
        resultPolicy: 'score_only',
      },
    });
    assert.equal(badRoomRes.status(), 422, 'Phòng từ đề chưa khóa đáp án phải bị chặn 422');
    const badRoomJson = await badRoomRes.json();
    assert.equal(badRoomJson.detail?.code, 'room_preflight_failed', JSON.stringify(badRoomJson));

    // Kiểm tra UI .er-preflight-banner & nút quick-open bị disable trên brokenRoomExam
    await teacherPage.locator('.design-rail [data-action="library"]').click();
    await teacherPage.waitForSelector(`#dialog [data-action="open-exam"][data-id="${brokenRoomExam.id}"]`);
    await teacherPage.locator(`#dialog [data-action="open-exam"][data-id="${brokenRoomExam.id}"]`).click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);
    await teacherPage.locator('.design-rail [data-action="exam-rooms"]').click();
    await teacherPage.waitForSelector('#dialog[open] .er-preflight-banner', {timeout: 10000});
    const uiPreflightBlocked = await teacherPage.evaluate(() => ({
      bannerText: document.querySelector('.er-preflight-banner')?.innerText?.trim() || '',
      quickOpenDisabled: Boolean(document.querySelector('#er-quick-open-btn')?.disabled),
    }));
    assert(uiPreflightBlocked.bannerText.includes('chưa đủ điều kiện') && uiPreflightBlocked.quickOpenDisabled, `UI preflight phải chặn mở phòng: ${JSON.stringify(uiPreflightBlocked)}`);
    await teacherPage.locator('#dialog button[data-action="close"]').first().click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // Chuyển lại SC-01 để test score_only + 3 HS thực chiến
    await teacherPage.locator('.design-rail [data-action="library"]').click();
    await teacherPage.waitForSelector(`#dialog [data-action="open-exam"][data-id="${sc01Reviewed.id}"]`);
    await teacherPage.locator(`#dialog [data-action="open-exam"][data-id="${sc01Reviewed.id}"]`).click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // 4b) Kiểm chứng chính sách score_only ẩn câu hỏi & điểm từng câu
    const scoreOnlyCreate = await teacherPage.request.post(`${baseUrl}/api/rooms`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {
        examId: sc01Reviewed.id,
        title: 'Phòng kiểm tra score_only UV62',
        classLabel: '9S',
        mode: 'exam',
        durationMinutes: 30,
        resultPolicy: 'score_only',
        shuffleQuestions: false,
        shuffleOptions: false,
      },
    });
    assert.equal(scoreOnlyCreate.status(), 201, await scoreOnlyCreate.text());
    const scoreOnlyRoom = await scoreOnlyCreate.json();

    const sOnlyCtx = await browser.newContext({viewport: {width: 1280, height: 840}});
    const sOnlyPage = await sOnlyCtx.newPage();
    attachTelemetry(sOnlyPage, 'student-score-only', buckets);
    await sOnlyPage.goto(`${baseUrl}/assets/exam-room.html?code=${scoreOnlyRoom.roomCode}`, {waitUntil: 'networkidle'});
    await sOnlyPage.locator('#sr-name').fill('Phạm Minh Đức');
    await sOnlyPage.locator('#sr-class').fill('9S');
    const sOnlyJoinPromise = sOnlyPage.waitForResponse((r) => r.url().includes('/join') && r.request().method() === 'POST');
    await sOnlyPage.locator('#sr-join-form button[type="submit"]').click();
    const sOnlyJoin = await (await sOnlyJoinPromise).json();
    await sOnlyPage.waitForSelector('[data-sr-action="ask-submit"]');
    const firstMcq = sc01Reviewed.questions.find((q) => q.type === 'mcq');
    await sOnlyPage.locator(`[data-sr-action="pick-mcq"][data-qid="${firstMcq.id}"][data-idx="${firstMcq.answer}"]`).click();
    await sOnlyPage.waitForTimeout(300);
    await sOnlyPage.locator('[data-sr-action="ask-submit"]').first().click();
    await sOnlyPage.locator('[data-sr-action="confirm-submit"]').click();
    await sOnlyPage.waitForSelector('.sr-result-wrap', {timeout: 10000});

    const sOnlyResultData = await sOnlyPage.evaluate(
      async ({id, tok}) => {
        const r = await fetch(`/api/rooms/public/attempts/${id}/result`, {headers: {'X-Attempt-Token': tok}});
        return r.json();
      },
      {id: sOnlyJoin.attemptId, tok: sOnlyJoin.attemptToken},
    );
    assert.equal(sOnlyResultData.resultPolicy, 'score_only');
    assert.deepEqual(sOnlyResultData.questions || [], [], 'score_only KHÔNG được trả về mảng questions chi tiết');
    const sOnlyRevCount = await sOnlyPage.locator('.sr-rev-item').count();
    assert.equal(sOnlyRevCount, 0, 'score_only KHÔNG được render .sr-rev-item từng câu');
    await shot(sOnlyPage, 'uv62-student-score-only.png');
    await sOnlyCtx.close();

    // Đóng & xóa phòng score_only tạm
    await teacherPage.request.delete(`${baseUrl}/api/rooms/${scoreOnlyRoom.id}`, {headers: {Origin: baseUrl}});

    // 4c) Phòng thi 3 học sinh + WAV maxPlays=2 + CV 7991 + rubric 0.01 + PATCH attemptCount + KaTeX analytics + mobile 390
    await teacherPage.locator('.editor-toolbar [data-action="exam-audio"]').click();
    await teacherPage.waitForSelector('#dialog[open] #audio-attach-form');
    await teacherPage.locator('#audio-attach-form input[name="audioFile"]').setInputFiles(wavFilePath);
    await teacherPage.locator('#audio-attach-form input[name="title"]').fill('Audio hướng dẫn thi UV62');
    await teacherPage.locator('#audio-attach-form input[name="maxPlays"]').fill('2');
    await teacherPage.locator('#audio-attach-form button[type="submit"]').click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);
    await teacherPage.locator('.paper .exam-audio-bar').waitFor();
    await waitSaved(teacherPage);

    await teacherPage.locator('.design-rail [data-action="exam-rooms"]').click();
    await teacherPage.waitForSelector('#dialog[open] .er-shell');
    await teacherPage.locator('[data-er-action="toggle-create"]').click();
    await teacherPage.waitForSelector('#er-create-form');
    await teacherPage.locator('#er-c-title').fill('Phòng thi thực chiến UV62 · Toán 9');
    await teacherPage.locator('#er-c-class').fill('9A1');
    await teacherPage.locator('#er-c-duration').fill('45');
    await teacherPage.locator('#er-c-tabs').fill('3');
    await teacherPage.locator('#er-c-policy').selectOption('score_and_answers');
    await teacherPage.locator('#er-create-form [name="shuffleQuestions"]').uncheck();
    await teacherPage.locator('#er-create-form [name="shuffleOptions"]').uncheck();
    await teacherPage.locator('#er-create-form [name="allowLan"]').check();

    const createRoomPromise = teacherPage.waitForResponse((r) => r.url().endsWith('/api/rooms') && r.request().method() === 'POST');
    await teacherPage.locator('#er-create-form button[type="submit"]').click();
    const createRoomRes = await createRoomPromise;
    assert.equal(createRoomRes.status(), 201, await createRoomRes.text());
    const roomCreated = await createRoomRes.json();
    const roomId = roomCreated.id;
    const roomCode = roomCreated.roomCode;

    const tfQ0 = sc01Reviewed.questions.filter((q) => q.type === 'truefalse');
    const makeTf = (tv, matches) => tv.map((v, i) => (i < matches ? Boolean(v) : !v));
    const studentSpecs = [
      {
        name: 'Nguyễn Minh An',
        classLabel: '9A1',
        mcqCorrect: 4,
        tf1: makeTf(tfQ0[0].truthValues, 4), // 1.00
        tf2: makeTf(tfQ0[1].truthValues, 4), // 1.00
        expectedTf: 2.0,
        shortOk: 2,
        tabs: 1,
      },
      {
        name: 'Trần Bảo Bình',
        classLabel: '9A1',
        mcqCorrect: 2,
        tf1: makeTf(tfQ0[0].truthValues, 3), // 0.50
        tf2: makeTf(tfQ0[1].truthValues, 2), // 0.25
        expectedTf: 0.75,
        shortOk: 1,
        tabs: 0,
      },
      {
        name: 'Lê Hải Châu',
        classLabel: '9A1',
        mcqCorrect: 0,
        tf1: makeTf(tfQ0[0].truthValues, 1), // 0.10
        tf2: makeTf(tfQ0[1].truthValues, 0), // 0.00
        expectedTf: 0.1,
        shortOk: 0,
        tabs: 0,
      },
    ];
    const studentContexts = [];
    const joinInfo = [];

    try {
      for (let i = 0; i < studentSpecs.length; i++) {
        const spec = studentSpecs[i];
        const ctx = await browser.newContext({viewport: {width: 1280, height: 840}});
        const page = await ctx.newPage();
        page.setDefaultTimeout(20000);
        attachTelemetry(page, `student-${i + 1}`, buckets);
        await page.goto(`${baseUrl}/assets/exam-room.html?code=${roomCode}`, {waitUntil: 'networkidle'});
        await page.locator('#sr-name').fill(spec.name);
        await page.locator('#sr-class').fill(spec.classLabel);
        const jp = page.waitForResponse((r) => r.url().includes('/join') && r.request().method() === 'POST');
        await page.locator('#sr-join-form button[type="submit"]').click();
        const jr = await jp;
        assert.equal(jr.status(), 201);
        joinInfo.push(await jr.json());
        await page.waitForSelector('.sr-workspace');
        studentContexts.push({ctx, page, spec});
      }

      // Kiểm tra Student Portal không lặp nhãn a) a) & chụp ảnh + kiểm tra audio maxPlays=2
      const st1 = studentContexts[0];
      await st1.page.locator('[data-sr-action="view-mode"][data-mode="all"]').click();
      await st1.page.locator('.sr-tf-row').first().waitFor();
      const dupPrefixCheck = await st1.page.evaluate(() => {
        const rows = [...document.querySelectorAll('.sr-tf-row')].map((r) => r.innerText.replace(/\s+/g, ' ').trim());
        const duplicated = rows.filter((t) => /^[a-d]\)\s*[a-d][\).]/i.test(t));
        return {count: rows.length, duplicated};
      });
      assert.equal(dupPrefixCheck.duplicated.length, 0, `Cổng học sinh bị lặp nhãn a) a): ${JSON.stringify(dupPrefixCheck.duplicated)}`);
      await shot(st1.page, 'uv62-student-portal.png');

      // Audio maxPlays=2 check
      const a1p = st1.page.waitForResponse((r) => r.url().includes('/audio/') && r.request().method() === 'GET');
      await st1.page.locator('[data-sr-action="play-audio"]').first().click();
      const a1 = await a1p;
      assert.equal(a1.status(), 200);
      assert.equal(a1.headers()['x-audio-plays-remaining'], '1');

      const a2p = st1.page.waitForResponse((r) => r.url().includes('/audio/') && r.request().method() === 'GET');
      await st1.page.locator('[data-sr-action="play-audio"]').first().click();
      const a2 = await a2p;
      assert.equal(a2.status(), 200);
      assert.equal(a2.headers()['x-audio-plays-remaining'], '0');

      const a3 = await st1.page.request.get(a2.url(), {headers: {'X-Attempt-Token': joinInfo[0].attemptToken}});
      assert.equal(a3.status(), 403, 'Lượt nghe thứ 3 vượt maxPlays=2 phải trả 403');

      const mcqQ = sc01Reviewed.questions.filter((q) => q.type === 'mcq');
      const tfQ = sc01Reviewed.questions.filter((q) => q.type === 'truefalse');
      const shortQ = sc01Reviewed.questions.filter((q) => q.type === 'short');
      const essayQ = sc01Reviewed.questions.filter((q) => q.type === 'essay');

      await Promise.all(
        studentContexts.map(async ({page, spec}) => {
          if (await page.locator('[data-sr-action="view-mode"][data-mode="all"]').count()) {
            await page.locator('[data-sr-action="view-mode"][data-mode="all"]').click().catch(() => {});
          }
          await page.locator('.sr-essay-input').first().waitFor();
          for (let m = 0; m < mcqQ.length; m++) {
            const q = mcqQ[m];
            const idxPick = m < spec.mcqCorrect ? q.answer : (q.answer + 1) % 4;
            await page.locator(`[data-sr-action="pick-mcq"][data-qid="${q.id}"][data-idx="${idxPick}"]`).click();
          }
          const tfVals = [spec.tf1, spec.tf2];
          for (let t = 0; t < tfQ.length; t++) {
            const q = tfQ[t];
            for (let r = 0; r < 4; r++) {
              await page.locator(`[data-sr-action="pick-tf"][data-qid="${q.id}"][data-row="${r}"][data-val="${tfVals[t][r]}"]`).click();
            }
          }
          for (let s = 0; s < shortQ.length; s++) {
            const q = shortQ[s];
            const inp = page.locator(`.sr-short-input[data-qid="${q.id}"]`);
            await inp.fill(s < spec.shortOk ? String(q.answerText) : '99999');
            await inp.evaluate((el) => el.blur());
          }
          for (let eIdx = 0; eIdx < essayQ.length; eIdx++) {
            const q = essayQ[eIdx];
            const ta = page.locator(`.sr-essay-input[data-qid="${q.id}"]`);
            await ta.fill(`Bài giải chi tiết của ${spec.name} · Ý ${eIdx + 1}`);
            await ta.evaluate((el) => el.blur());
          }
          await page.waitForTimeout(700);
          await page.locator('[data-sr-action="ask-submit"]').first().click();
          const sp = page.waitForResponse((r) => r.url().endsWith('/submit') && r.request().method() === 'POST');
          await page.locator('[data-sr-action="confirm-submit"]').click();
          assert.equal((await sp).status(), 200);
          await page.waitForSelector('.sr-result-wrap', {timeout: 12000});
        }),
      );

      for (let i = 0; i < studentContexts.length; i++) {
        const {page, spec} = studentContexts[i];
        const resData = await page.evaluate(
          async ({id, tok}) => (await fetch(`/api/rooms/public/attempts/${id}/result`, {headers: {'X-Attempt-Token': tok}})).json(),
          {id: joinInfo[i].attemptId, tok: joinInfo[i].attemptToken},
        );
        const tfSumP100 = (resData.questions || []).filter((q) => q.type === 'truefalse').reduce((acc, q) => acc + Number(q.earnedPointsP100 || 0), 0);
        assert.equal(Math.round(tfSumP100), Math.round(spec.expectedTf * 100));
      }
    } catch (err) {
    console.error('TELEMETRY ON FAILURE:', JSON.stringify(buckets, null, 2));
    throw err;
  } finally {
      for (const {ctx} of studentContexts) await ctx.close();
    }

    // Chấm tự luận bước 0.01 (0.51 cho bài đầu tiên)
    await teacherPage.locator('[data-er-action="switch-tab"][data-tab="grading"]').click();
    await teacherPage.waitForSelector('.er-grade-form', {timeout: 10000});
    const gradeTotal = await teacherPage.locator('.er-grade-form').count();
    assert.equal(gradeTotal, 12);
    for (let g = 0; g < gradeTotal; g++) {
      const form = teacherPage.locator('.er-grade-form').first();
      const maxP100 = Number(await form.getAttribute('data-max-p100'));
      const fineVal = g === 0 && maxP100 >= 51 ? '0.51' : ((maxP100 * 0.5) / 100).toFixed(2);
      await form.locator('[name="earnedPoints"]').fill(fineVal);
      await form.locator('[name="graderNote"]').fill(`Rubric UV62 bước 0.01 (#${g + 1})`);
      const gp = teacherPage.waitForResponse((r) => r.url().includes('/grades/') && r.request().method() === 'PUT');
      await form.locator('button[type="submit"]').click();
      assert.equal((await gp).status(), 200, `Chấm điểm ${fineVal} phải trả 200`);
      await teacherPage.waitForFunction((rem) => document.querySelectorAll('.er-grade-form').length === rem, gradeTotal - g - 1, {timeout: 10000});
    }

    // Tab Thống kê & KaTeX trong bảng + Xuất .xlsx
    await teacherPage.locator('[data-er-action="switch-tab"][data-tab="analytics"]').click();
    await teacherPage.waitForSelector('[data-er-action="export-xlsx"]', {timeout: 10000});
    await teacherPage.waitForTimeout(300);
    const analyticsCheck = await teacherPage.evaluate(() => ({
      katexCount: document.querySelectorAll('#dialog .er-table td .katex').length,
      katexErrors: document.querySelectorAll('#dialog .er-table td .katex-error').length,
      hasStudentRows: document.querySelector('#dialog')?.innerText?.includes('Nguyễn Minh An'),
    }));
    assert(analyticsCheck.katexCount >= 1 && analyticsCheck.katexErrors === 0, `Bảng thống kê phòng thi phải render KaTeX sạch: ${JSON.stringify(analyticsCheck)}`);
    await shot(teacherPage, 'uv62-exam-room-teacher.png');

    const [xlsxDl] = await Promise.all([
      teacherPage.waitForEvent('download'),
      teacherPage.locator('[data-er-action="export-xlsx"]').click(),
    ]);
    await xlsxDl.saveAs(xlsxOutPath);
    const xlsxCheck = JSON.parse(
      execFileSync(
        PYTHON_EXE,
        [
          '-c',
          'import json,sys,zipfile;zf=zipfile.ZipFile(sys.argv[1]);names=zf.namelist();sheets=[zf.read(n).decode("utf-8") for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")];blob=zf.read("xl/workbook.xml").decode("utf-8")+(zf.read("xl/sharedStrings.xml").decode("utf-8") if "xl/sharedStrings.xml" in names else "")+"\\n".join(sheets);print(json.dumps({"sheets":len(sheets),"ok":all(s in blob for s in ("BangDiem","ThongKeCauHoi","Nguyễn Minh An","Trần Bảo Bình","Lê Hải Châu"))},ensure_ascii=False))',
          xlsxOutPath,
        ],
        {encoding: 'utf8'},
      ),
    );
    assert(xlsxCheck.ok && xlsxCheck.sheets >= 2, `File .xlsx thiếu sheet/dữ liệu: ${JSON.stringify(xlsxCheck)}`);

    // Kiểm tra PATCH đóng phòng giữ nguyên attemptCount === 3
    const patchCloseRes = await teacherPage.request.patch(`${baseUrl}/api/rooms/${roomId}`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {status: 'closed'},
    });
    assert.equal(patchCloseRes.status(), 200, await patchCloseRes.text());
    const closedBody = await patchCloseRes.json();
    const closedRoom = closedBody.room || closedBody;
    assert.equal(closedRoom.attemptCount, 3, `PATCH đóng phòng phải giữ attemptCount=3, nhận: ${closedRoom.attemptCount}`);
    const listRoomsRes = await (await teacherPage.request.get(`${baseUrl}/api/rooms`)).json();
    const closedListed = (listRoomsRes.rooms || listRoomsRes || []).find((r) => r.id === roomId);
    assert.equal(closedListed?.attemptCount, 3, `Danh sách phòng sau reload phải giữ attemptCount=3, nhận: ${closedListed?.attemptCount}`);

    // Kiểm tra Phòng thi trên mobile 390x844 không tràn ngang
    await teacherPage.setViewportSize({width: 390, height: 844});
    await teacherPage.waitForTimeout(300);
    const mobileRoomCheck = await teacherPage.evaluate(() => {
      const dlg = document.querySelector('#dialog');
      return {
        pageOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        dlgScrollW: dlg ? dlg.scrollWidth : 0,
        dlgClientW: dlg ? dlg.clientWidth : 0,
      };
    });
    assert(!mobileRoomCheck.pageOverflow && mobileRoomCheck.dlgScrollW <= mobileRoomCheck.dlgClientW + 2, `Phòng thi mobile 390 bị tràn ngang: ${JSON.stringify(mobileRoomCheck)}`);
    await shot(teacherPage, 'uv62-exam-room-mobile-390.png');
    await teacherPage.setViewportSize({width: 1440, height: 900});
    await teacherPage.locator('#dialog button[data-action="close"]').first().click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);

    // =========================================================================
    // 5. LESSON PICKER: "ty so", CHIPS ẨN NGOÀI BỘ LỌC, TÁCH MẪU / CÁ NHÂN
    // =========================================================================
    await teacherPage.locator('.assistant-source-bar [data-action="lesson-sources"]').click();
    await teacherPage.waitForSelector('#dialog[open] #lesson-picker', {timeout: 10000});

    // Thêm 1 học liệu cá nhân để kiểm tra tách bạch HỌC LIỆU MẪU vs TÀI LIỆU CÁ NHÂN
    await teacherPage.locator('[data-personal-editor] summary').click();
    await teacherPage.locator('#personal-lesson-form [name="title"]').fill('Bài giảng cá nhân Hệ thức lượng UV62');
    await teacherPage.locator('#personal-lesson-form [name="lesson"]').fill('Chuyên đề cá nhân');
    await teacherPage.locator('#personal-lesson-form [name="content_excerpt"]').fill('Nội dung học liệu cá nhân riêng về tỉ số lượng giác và ứng dụng thực tế.');
    await teacherPage.locator('#personal-lesson-form [name="usage"]').check();
    await teacherPage.locator('#personal-lesson-form button[type="submit"]').click();
    await teacherPage.waitForSelector('.source-channel-badge[data-channel="personal"]', {timeout: 8000});
    const lpForm = teacherPage.locator('#lesson-picker');
    assert.equal(await lpForm.locator('[name="library"]').inputValue(), 'personal', 'Sau khi lưu học liệu cá nhân phải lọc Kho = personal');
    await lpForm.locator('[name="library"]').selectOption('');
    await teacherPage.waitForTimeout(150);

    const channelCheck = await teacherPage.evaluate(() => ({
      hasSampleBadge: Boolean(document.querySelector('.source-channel-badge[data-channel="sample"]')),
      hasPersonalBadge: Boolean(document.querySelector('.source-channel-badge[data-channel="personal"]')),
    }));
    assert(channelCheck.hasSampleBadge && channelCheck.hasPersonalBadge, `Phải tách badge Học liệu mẫu & Tài liệu cá nhân: ${JSON.stringify(channelCheck)}`);

    await lpForm.locator('[name="query"]').fill('ty so');
    await teacherPage.waitForTimeout(200);
    const tySoMatched = await teacherPage.evaluate(() => document.querySelector('#lesson-picker')?.innerText?.includes('Tỉ số lượng giác'));
    assert(tySoMatched, 'Tìm "ty so" phải khớp bài "Tỉ số lượng giác và bài toán đo chiều cao"');
    await shot(teacherPage, 'uv62-lesson-picker-tyso.png');

    // Chọn 1 bài rồi đổi bộ lọc để kiểm tra chip "(đang ẩn ngoài bộ lọc)"
    await lpForm.locator('[name="lesson"]').first().check();
    await lpForm.locator('[name="query"]').fill('phương trình bậc hai một ẩn xyz không trùng');
    await teacherPage.waitForTimeout(200);
    const hiddenChipText = await teacherPage.locator('[data-lesson-selected-chips] .lesson-selected-chip.is-hidden-filter').first().innerText();
    assert(hiddenChipText.includes('đang ẩn ngoài bộ lọc'), `Phải hiện chip báo bài chọn đang ẩn: "${hiddenChipText}"`);

    // Đóng mọi modal đang mở
    await teacherPage.evaluate(() => {
      document.querySelector('#dialog-layer2')?.close?.();
      document.querySelector('#dialog')?.close?.();
    });

    // =========================================================================
    // 6. UC8 (409 PREFLIGHT -> allowDraft -> isDraft -> BẢN NHÁP), UC9 (stale), M07-04 (rubric)
    // =========================================================================
    // UC8: 409 -> allowDraft -> HTML & DOCX BẢN NHÁP
    const uc8Blocked = await teacherPage.request.post(`${baseUrl}/api/save-export`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {type: 'exam', exam: brokenRoomExam, format: 'html', teacher: true},
    });
    assert.equal(uc8Blocked.status(), 409, 'UC8 xuất đề có lỗi blocking phải trả 409 trước khi xác nhận');
    const uc8BlockedJson = await uc8Blocked.json();
    assert.equal(uc8BlockedJson.code, 'export_preflight_blocked');

    const uc8HtmlDraft = await teacherPage.request.post(`${baseUrl}/api/save-export`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {type: 'exam', exam: brokenRoomExam, format: 'html', teacher: true, allowDraft: true},
    });
    assert.equal(uc8HtmlDraft.status(), 200);
    const uc8HtmlJson = await uc8HtmlDraft.json();
    assert.equal(uc8HtmlJson.isDraft, true, 'UC8 allowDraft phải gắn cờ isDraft: true');
    const htmlDraftRes = await teacherPage.request.get(`${baseUrl}${uc8HtmlJson.url}`);
    const htmlDraftText = await htmlDraftRes.text();
    assert(htmlDraftText.includes('BẢN NHÁP'), 'HTML giáo viên xuất nháp phải có banner BẢN NHÁP');

    const uc8DocxDraft = await teacherPage.request.post(`${baseUrl}/api/save-export`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {type: 'exam', exam: brokenRoomExam, format: 'docx', teacher: true, allowDraft: true},
    });
    assert.equal(uc8DocxDraft.status(), 200);
    const uc8DocxJson = await uc8DocxDraft.json();
    const docxDraftBuf = Buffer.from(await (await teacherPage.request.get(`${baseUrl}${uc8DocxJson.url}`)).body());
    const docxZip = await JSZip.loadAsync(docxDraftBuf);
    const docxXml = await docxZip.file('word/document.xml').async('string');
    assert(docxXml.includes('BẢN NHÁP'), 'DOCX giáo viên xuất nháp phải có đoạn BẢN NHÁP');

    // UC9: Đổi dị bản ngữ liệu -> evidence giữ lại + stale: true + staleReason
    await teacherPage.locator('.design-rail [data-action="library"]').click();
    await teacherPage.waitForSelector(`#dialog [data-action="open-exam"][data-id="${uc9Exam.id}"]`);
    await teacherPage.locator(`#dialog [data-action="open-exam"][data-id="${uc9Exam.id}"]`).click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);
    await teacherPage.locator('[data-action="menu"][data-menu="tools"]').click();
    await teacherPage.locator('.document-menu [data-action="quotes"]').click();
    await teacherPage.waitForSelector('#dialog[open] [data-action="choose-variant"][data-id="qv2"]');
    await teacherPage.locator('#dialog [data-action="choose-variant"][data-id="qv2"]').click();
    await teacherPage.waitForSelector('#dialog[open] [data-action="apply-quote"]');
    await teacherPage.locator('#dialog [data-action="apply-quote"]').click();
    await teacherPage.waitForSelector('#dialog [data-action="close"]');
    await teacherPage.locator('#dialog button[data-action="close"]').first().click();
    await teacherPage.waitForFunction(() => !document.querySelector('#dialog')?.open);
    await waitSaved(teacherPage);

    const uc9SavedState = await (await teacherPage.request.get(`${baseUrl}/api/kv?key=state`)).json();
    const uc9UpdatedExam = (uc9SavedState.value?.exams || []).find((ex) => ex.id === uc9Exam.id);
    const uc9Ev = uc9UpdatedExam?.questions?.[0]?.evidence?.[0];
    assert.equal(uc9Ev?.stale, true, `UC9 evidence phải có stale: true: ${JSON.stringify(uc9Ev)}`);
    assert.equal(uc9Ev?.staleReason, 'quote_variant_changed');
    const hasStaleUi = await teacherPage.locator('.paper .is-stale-source').count();
    assert(hasStaleUi >= 1, 'UC9 phải hiển thị cảnh báo .is-stale-source trên câu đọc hiểu');

    // M07-04: Quét rubric chặn trộn vỡ cặp nhưng cho phép trộn hợp lệ
    const m07BadExam = {
      id: 'm07-rubric-test',
      title: 'Test M07-04',
      subject: 'Toán',
      grade: '9',
      questions: [
        {id: 'm1', type: 'mcq', stem: 'Câu 1 độc lập?', options: ['A', 'B', 'C', 'D'], answer: 0, answerKnown: true, points: 1},
        {
          id: 'm2',
          type: 'mcq',
          stem: 'Câu 2 giải kết quả?',
          options: ['1', '2', '3', '4'],
          answer: 0,
          answerKnown: true,
          rubric: [{text: 'Dựa vào câu trước để suy ra bước tiếp.', points: 1}],
          points: 1,
        },
        {id: 'm3', type: 'mcq', stem: 'Phép tính độc lập thứ ba là gì?', options: ['A', 'B', 'C', 'D'], answer: 1, answerKnown: true, points: 1},
      ],
    };
    const m07BlockedRes = await teacherPage.request.post(`${baseUrl}/api/preview-variant`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {exam: m07BadExam, variant: {offset: 1, questionIds: ['m1', 'm2', 'm3']}},
    });
    assert.equal(m07BlockedRes.status(), 400, 'M07-04 rubric chứa "câu trước" khi trộn tách m1-m2 phải bị chặn 400');

    const m07AllowedRes = await teacherPage.request.post(`${baseUrl}/api/preview-variant`, {
      headers: {Origin: baseUrl, 'Content-Type': 'application/json'},
      data: {
        exam: {
          ...m07BadExam,
          questions: [
            {...m07BadExam.questions[0], groupId: 'g-1'},
            {...m07BadExam.questions[1], groupId: 'g-1'},
            m07BadExam.questions[2],
            {id: 'm4', type: 'mcq', stem: 'Phép tính độc lập thứ tư là gì?', options: ['A', 'B', 'C', 'D'], answer: 2, answerKnown: true, points: 1},
          ],
        },
        variant: {offset: 1, questionIds: ['m3', 'm4']},
      },
    });
    assert.equal(m07AllowedRes.status(), 200, `M07-04 trộn các câu độc lập xa khối liên kết phải được phép 200: ${await m07AllowedRes.text()}`);

    await teacherCtx.close();

    // =========================================================================
    // 7. SSE STRICT TEACHER ONLY (CHỈ TRANG 2 + 0-HIT CẮT SẠCH) & MODEL USED PERSISTED
    // =========================================================================
    const ssePort = await freePort();
    const sseStarted = await startSseStrictServer(ssePort, sseDataDir, sseCaptureFile);
    sseProc = sseStarted.proc;
    const sseCtx = await browser.newContext({viewport: {width: 1280, height: 860}});
    const ssePage = await sseCtx.newPage();
    attachTelemetry(ssePage, 'sse-strict', buckets);

    const strictExam = {
      ...sc01Reviewed,
      id: 'uv62-sse-strict-exam',
      workflowStatus: 'draft',
      aiConsent: true,
      aiTimePreset: 'standard',
      strictTeacherOnly: true,
      assistantSources: ['doc-strict-pages'],
      assistantSourcePages: {'doc-strict-pages': [2]},
      docs: [
        {
          id: 'doc-strict-pages',
          name: 'Tài liệu giáo viên nhiều trang',
          kind: 'text',
          version: 1,
          pages: [
            {number: 1, text: 'Trang 1 có từ khóa bí mật BI_MAT_TRANG_1_KHONG_CHON không được chọn.'},
            {number: 2, text: 'Trang 2 nêu định lý trọng tâm DINH_LY_TRANG_2_DOC_QUYEN dùng để tạo đề.'},
          ],
          text: 'Trang 1 BI_MAT_TRANG_1_KHONG_CHON\nTrang 2 DINH_LY_TRANG_2_DOC_QUYEN',
        },
      ],
      chat: [],
    };
    await ssePage.request.put(`${sseStarted.baseUrl}/api/kv`, {
      headers: {Origin: sseStarted.baseUrl, 'Content-Type': 'application/json'},
      data: {key: 'state', value: {version: 1, current: strictExam.id, exams: [strictExam], prefs: []}},
    });
    await ssePage.goto(sseStarted.baseUrl, {waitUntil: 'networkidle'});
    await ssePage.waitForSelector('#chat-input');

    // Gửi câu hỏi khớp Trang 2 -> SSE trả modelUsed & provider AGY, prompt không rò Trang 1
    const sseOkPromise = ssePage.waitForResponse((r) => r.url().endsWith('/api/assistant/chat/stream') && r.request().method() === 'POST');
    await ssePage.locator('#chat-input').fill('Hãy giải thích DINH_LY_TRANG_2_DOC_QUYEN');
    await ssePage.locator('#chat-form button[type="submit"]').click();
    const sseOkRes = await sseOkPromise;
    assert.equal(sseOkRes.status(), 200);
    await ssePage.waitForFunction(
      () => document.querySelectorAll('.assistant-message.role-assistant:not(.is-streaming) .chat-provider-meta').length >= 1,
      {timeout: 12000},
    );
    const metaText = await ssePage.locator('.assistant-message.role-assistant .chat-provider-meta').last().innerText();
    assert(metaText.includes('gemini-3-flash') || metaText.includes('AGY'), `Phải hiển thị modelUsed/AGY trên bong bóng chat: "${metaText}"`);
    assert((await ssePage.locator('.assistant-message.role-assistant .chat-retry-btn').count()) >= 1, 'Phải có nút Thử lại');

    const capturedPayloadText = fs.readFileSync(sseCaptureFile, 'utf8');
    assert(capturedPayloadText.includes('DINH_LY_TRANG_2_DOC_QUYEN'), 'Ngữ cảnh gửi AI phải có trang 2 đã chọn');
    assert(!capturedPayloadText.includes('BI_MAT_TRANG_1_KHONG_CHON'), 'Ngữ cảnh strictTeacherOnly chỉ chọn trang 2 KHÔNG được lọt trang 1');

    // Kiểm tra 0-hit trên 1 nguồn bị strictTeacherOnly cắt sạch (noMatchingSourceFragments: true)
    const zeroHitRes = await ssePage.request.post(`${sseStarted.baseUrl}/api/assistant/chat/stream`, {
      headers: {Origin: sseStarted.baseUrl, 'Content-Type': 'application/json'},
      data: {
        examId: strictExam.id,
        revision: 1,
        text: 'Từ khóa không hề tồn tại ZZZ_KHONG_CO_999',
        teacherFilesOnly: true,
        strictTeacherOnly: true,
        assistantSources: ['doc-strict-pages'],
        assistantSourcePages: {'doc-strict-pages': [2]},
        exam: strictExam,
        consent: true,
        context: [],
      },
    });
    assert.equal(zeroHitRes.status(), 200);
    const zeroHitSseText = await zeroHitRes.text();
    assert(zeroHitSseText.includes('"noMatchingSourceFragments":true') || zeroHitSseText.includes('"noMatchingSourceFragments": true'), `0-hit strictTeacherOnly trên 1 nguồn phải bật noMatchingSourceFragments: ${zeroHitSseText.slice(0, 400)}`);

    await sseCtx.close();

    assert.deepEqual(buckets.consoleErrors, [], `Phát hiện console.error: ${buckets.consoleErrors.join('; ')}`);
    assert.deepEqual(buckets.pageErrors, [], `Phát hiện pageerror: ${buckets.pageErrors.join('; ')}`);
    assert.deepEqual(buckets.http5xx, [], `Phát hiện HTTP 5xx: ${buckets.http5xx.join('; ')}`);

    console.log(
      JSON.stringify(
        {
          ok: true,
          evidenceDir: EVIDENCE_DIR,
          screenshots: [
            'uv62-desktop-1440x900.png',
            'uv62-desktop-1280x720.png',
            'uv62-mobile-390x844.png',
            'uv62-empty-canvas-whale.png',
            'uv62-analytics-modal.png',
            'uv62-qbank-modal.png',
            'uv62-exam-room-teacher.png',
            'uv62-exam-room-mobile-390.png',
            'uv62-student-portal.png',
            'uv62-student-score-only.png',
            'uv62-lesson-picker-tyso.png',
            'uv62-team-login-whale.png',
          ],
          checks: {
            brand: checkViewport1440.brand,
            paperBg: checkViewport1440.paperBg,
            wfLabel: checkViewport1440.wfLabel,
            analyticsKatex: analyticsCheck.katexCount,
            roomAttemptCountAfterClose: closedListed?.attemptCount,
            uc8Draft: uc8HtmlJson.isDraft,
            uc9Stale: uc9Ev?.stale,
            strictMeta: metaText,
          },
        },
        null,
        2,
      ),
    );
  } catch (err) {
    console.error('TELEMETRY ON FAILURE:', JSON.stringify(buckets, null, 2));
    throw err;
  } finally {
    if (browser) await browser.close().catch(() => {});
    await stopServer(mainProc);
    await stopServer(sseProc);
    await stopServer(teamProc);
    for (const dir of [dataDir, sseDataDir, teamDataDir]) {
      fs.rmSync(dir, {recursive: true, force: true});
    }
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
