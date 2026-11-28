import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
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

const EVIDENCE_DIR = process.env.QA_UV63_SCREENSHOT_DIR
  ? path.resolve(process.env.QA_UV63_SCREENSHOT_DIR)
  : 'C:\\Users\\nguye\\.gemini\\antigravity\\brain\\f3eea969-4834-47f8-8318-93e7d029e582\\qa-uv63-evidence';

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

function buildSampleWavBuffer(seconds = 0.2, sampleRate = 8000) {
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
  // Khởi chạy server chuẩn local (fixture === false) để kiểm chứng đúng luồng thực tế Auto-Pilot
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
        if (body?.matrixPython && body?.fixture === false) {
          return {proc, baseUrl, statusBody: body, getLogs: () => logs};
        }
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
        proc.kill('SIGKILL');
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

async function main() {
  fs.mkdirSync(EVIDENCE_DIR, {recursive: true});
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'uv63-real-'));
  const dataDir = path.join(tempRoot, 'local-data');
  fs.mkdirSync(dataDir, {recursive: true});

  const port = await freePort();
  const server = await startLocalServer(port, dataDir);
  const {baseUrl, statusBody} = server;
  const consoleErrors = [];
  const pageErrors = [];
  const httpErrors = [];

  const browser = await chromium.launch({
    executablePath: findChrome(),
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    // 1. Seed Chiến dịch 3/10 đề + Đề nháp cũ (> 20h) + Nhắc lịch sắp tới
    const curStateRes = await fetch(`${baseUrl}/api/kv?key=state`);
    assert.equal(curStateRes.status, 200);
    const kvState = await curStateRes.json();
    const exams = kvState?.value?.exams ? [...kvState.value.exams] : [];
    const oldDraftId = 'uv63-old-draft-exam';
    const doneIds = ['uv63-done-1', 'uv63-done-2', 'uv63-done-3'];
    for (let i = 0; i < doneIds.length; i++) {
      exams.push({
        id: doneIds[i],
        title: `Đề ôn tập Toán 11 · Đề ${i + 1}`,
        subject: 'Toán',
        grade: '11',
        minutes: 90,
        revision: 2,
        updated: Date.now() - (i + 1) * 3600 * 1000,
        workflowStatus: 'approved',
        approvalStatus: 'approved',
        questions: [
          {
            id: `${doneIds[i]}-q1`,
            v: 1,
            type: 'mcq',
            stem: `Tính $\\lim_{n\\to\\infty}\\frac{2n+1}{n+3}$ (Đề ${i + 1})?`,
            options: ['1', '2', '3', '0'],
            answer: 1,
            answerKnown: true,
            points: 10,
            approvalStatus: 'approved',
          },
        ],
        docs: [],
        matrix: [{topic: 'Giới hạn', targets: [1, 0, 0, 0]}],
        undo: [],
        redo: [],
        history: [],
        appliedPrefs: [],
        chat: [],
        quote: {text: '', versions: [], chosen: ''},
      });
    }
    exams.push({
      id: oldDraftId,
      title: 'Đề nháp AI Toán 11 (chờ rà soát hôm sau)',
      subject: 'Toán',
      grade: '11',
      minutes: 90,
      revision: 1,
      updated: Date.now() - 22 * 3600 * 1000,
      workflowStatus: 'draft',
      approvalStatus: 'draft',
      questions: [
        {
          id: 'old-draft-q1',
          v: 1,
          type: 'mcq',
          stem: 'Cho cấp số cộng $(u_n)$ có $u_1 = 2, d = 3$. Giá trị $u_5$ bằng?',
          options: ['11', '14', '17', '20'],
          answer: 1,
          answerKnown: true,
          points: 10,
          approvalStatus: 'draft',
        },
      ],
      docs: [],
      matrix: [{topic: 'Cấp số cộng', targets: [1, 0, 0, 0]}],
      undo: [],
      redo: [],
      history: [],
      appliedPrefs: [],
      chat: [],
      quote: {text: '', versions: [], chosen: ''},
    });
    const nextState = {
      version: kvState?.value?.version || 1,
      current: oldDraftId,
      exams,
      prefs: kvState?.value?.prefs || [],
    };
    const putKvRes = await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({key: 'state', value: nextState}),
    });
    assert.equal(putKvRes.status, 200);

    const campRes = await fetch(`${baseUrl}/api/campaigns`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({
        title: 'Bộ 10 đề ôn tập HK1 Toán 11',
        subject: 'Toán',
        grade: '11',
        targetCount: 10,
        examIds: doneIds,
        dueAt: Date.now() + 18 * 3600 * 1000,
      }),
    });
    assert.equal(campRes.status, 201);
    const campJson = await campRes.json();
    assert.equal(campJson.campaign.completedCount, 3);
    assert.equal(campJson.campaign.targetCount, 10);

    const remRes = await fetch(`${baseUrl}/api/reminders`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({
        title: 'Rà soát đáp án Đề HK1 Toán 11 trước khi phát lớp 11A1',
        kind: 'deadline',
        remindAt: Date.now() + 2 * 3600 * 1000,
      }),
    });
    assert.equal(remRes.status, 201);

    const digestRes = await fetch(`${baseUrl}/api/proactive/digest`);
    assert.equal(digestRes.status, 200);
    const digestJson = await digestRes.json();
    assert.ok(digestJson.badgeCount >= 2, 'Digest phải báo chiến dịch + nhắc rà soát/hạn');
    assert.ok(digestJson.activeCampaigns.some((c) => c.completedCount === 3 && c.targetCount === 10));
    assert.ok(digestJson.nextDayReviewNudges.some((n) => n.examId === oldDraftId));

    // Verify AGY config defaults
    assert.equal(statusBody.config?.fixedRouter?.agyModel, 'gemini-pro-orchestrator-neon');
    assert.equal(statusBody.config?.fixedRouter?.agyFastModel, 'gemini-3.8-flash-medium');
    assert.equal(statusBody.config?.fixedRouter?.autoPilot, true);

    const context = await browser.newContext({viewport: {width: 1440, height: 900}});
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on('console', (m) => {
      if (m.type() === 'error') consoleErrors.push(m.text());
    });
    page.on('pageerror', (e) => pageErrors.push(e.message));
    page.on('response', (res) => {
      const s = res.status();
      if (s >= 400 && !res.url().includes('/agent/auto-create')) {
        httpErrors.push(`${s} ${res.url()}`);
      }
    });

    // 2. Trang chủ (?view=home) ở 1440x900, 1280x720, 390x844
    await page.goto(`${baseUrl}/?view=home`, {waitUntil: 'networkidle'});
    await page.locator('#home-view').waitFor();
    await page.locator('#home-prompt-form').waitFor();
    await page.waitForSelector('.proactive-card[data-campaign-id]');
    const homeStats1440 = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      hasVoiceBtn: Boolean(document.querySelector('#home-prompt-form .voice-mic-btn')),
      hasCampaign: document.body.innerText.includes('3/10'),
      hasBellBadge: Boolean(document.querySelector('.proactive-bell-btn')),
    }));
    assert.equal(homeStats1440.overflow, false, 'Trang chủ 1440 bị tràn ngang');
    assert.equal(homeStats1440.hasVoiceBtn, true, 'Trang chủ thiếu nút micro giọng nói');
    assert.equal(homeStats1440.hasCampaign, true, 'Trang chủ không hiện tiến độ chiến dịch 3/10');
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-home-1440.png')});

    await page.setViewportSize({width: 1280, height: 720});
    await page.waitForTimeout(150);
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1),
      false,
      'Trang chủ 1280 bị tràn ngang',
    );
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-home-1280.png')});

    await page.setViewportSize({width: 390, height: 844});
    await page.waitForTimeout(150);
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1),
      false,
      'Trang chủ 390 bị tràn ngang',
    );
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-home-390.png')});

    // 3. Proactive Notification Bell Modal
    await page.setViewportSize({width: 1440, height: 900});
    await page.locator('.proactive-bell-btn').click();
    await page.locator('#dialog[open]').waitFor();
    await page.waitForTimeout(120);
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-proactive-campaigns.png')});
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});

    // 4. Bàn soạn 1440 & 1280: Kiểm design-rail 6 nút, Micro & chiều cao composer
    await page.locator('.design-rail [data-action="design-workspace"]').click();
    await page.locator('.paper').waitFor();
    const ws1440 = await page.evaluate(() => {
      const compose = document.querySelector('.chat-compose')?.getBoundingClientRect();
      const railBtns = [...document.querySelectorAll('.design-rail button')];
      const clipped = railBtns.some((b) => b.getBoundingClientRect().right > document.querySelector('.design-rail').getBoundingClientRect().right + 2);
      return {
        overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        composeH: compose ? compose.height : 0,
        railCount: railBtns.length,
        railClipped: clipped,
        hasVoice: Boolean(document.querySelector('.compose-bottom .voice-mic-btn')),
      };
    });
    assert.equal(ws1440.overflow, false);
    assert.ok(ws1440.composeH > 0 && ws1440.composeH < 190, `chat-compose height=${ws1440.composeH} >= 190`);
    assert.ok(ws1440.railCount >= 6, 'design-rail thiếu nút Trang chủ');
    assert.equal(ws1440.hasVoice, true, 'Thiếu nút Micro trong .compose-bottom');
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-workspace-1440.png')});

    await page.setViewportSize({width: 1280, height: 720});
    await page.waitForTimeout(150);
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1),
      false,
      'Workspace 1280 bị tràn ngang',
    );
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-workspace-1280.png')});
    await page.setViewportSize({width: 1440, height: 900});

    // 5. Modal Chèn nội dung theo môn (đối chiếu Ảnh 4)
    await page.locator('[data-action="subject-library"]:visible').first().click();
    await page.locator('.composer-shell').waitFor();
    await page.waitForTimeout(150);
    const composerCheck = await page.evaluate(() => {
      const firstCard = document.querySelector('#catalog-items .catalog-item');
      const metas = [...(firstCard?.querySelectorAll('.catalog-card-meta > *, .catalog-card-meta span') || [])];
      let overlaps = false;
      for (let i = 1; i < metas.length; i++) {
        const prev = metas[i - 1].getBoundingClientRect();
        const cur = metas[i].getBoundingClientRect();
        if (Math.abs(prev.top - cur.top) < 6 && prev.right > cur.left + 1) overlaps = true;
      }
      const shell = document.querySelector('.composer-shell');
      const shRect = shell?.getBoundingClientRect();
      return {
        hasItems: document.querySelectorAll('#catalog-items .catalog-item').length > 0,
        overlaps,
        width: shRect?.width || 0,
        height: shRect?.height || 0,
      };
    });
    assert.equal(composerCheck.hasItems, true, 'Catalog items trống');
    assert.equal(composerCheck.overlaps, false, 'Badge catalog bị đè dính vào nhau');
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-composer-modal.png')});
    await page.locator('.composer-shell .composer-close').click();
    await page.locator('.composer-shell').waitFor({state: 'detached'});

    // 6. Modal SGK KNTT 5 tab + 2 cột (đối chiếu Ảnh 3)
    await page.locator('.ux-attach-toggle, [data-ux-action="attach"]').first().click();
    await page.locator('.ux-attach-menu [data-action="assistant-sources"]').click();
    await page.locator('#dialog[open] #assistant-source-form').waitFor();
    await page.getByRole('button', {name: 'SGK / Bài học', exact: true}).click();
    const layer2 = page.locator('#dialog-layer2');
    const picker = layer2.locator('#lesson-picker');
    await picker.waitFor();
    await picker.locator('[name="grade"]').selectOption('10');
    await picker.locator('[name="subject"]').selectOption('Toán');
    const knttBai2 = layer2.locator('.sgk-lesson-row', {hasText: 'Tập hợp và các phép toán trên tập hợp'}).first();
    await knttBai2.waitFor();
    await knttBai2.click();
    await page.waitForTimeout(150);
    const sgkCheck = await page.evaluate(() => {
      const tabs = [...document.querySelectorAll('.sgk-tabs button')].map((b) => b.textContent.trim());
      const detail = document.querySelector('[data-sgk-detail]')?.innerText || '';
      const hasSplit = Boolean(document.querySelector('.sgk-split') && document.querySelector('.sgk-detail-pane'));
      return {
        tabsCount: tabs.length,
        hasSplit,
        hasSgkBadge: detail.includes('SGK'),
        hasPages: /tr\.\s*12-19/i.test(detail),
        hasPeriods: /4\s*tiết/i.test(detail),
        hasOutcomes: detail.includes('YÊU CẦU CẦN ĐẠT'),
      };
    });
    assert.equal(sgkCheck.tabsCount, 5, 'Modal SGK phải có đúng 5 tab');
    assert.equal(sgkCheck.hasSplit, true);
    assert.equal(sgkCheck.hasSgkBadge, true);
    assert.equal(sgkCheck.hasPages, true);
    assert.equal(sgkCheck.hasPeriods, true);
    assert.equal(sgkCheck.hasOutcomes, true);
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-sgk-kntt-2pane.png')});
    await layer2.locator('[data-action="close-top-modal"]').first().click();
    await layer2.waitFor({state: 'hidden'});
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});

    // 7. Modal Cài đặt AI (AGY Orchestrator Neon & Auto-Pilot)
    await page.locator('[data-ux-action="options"]').click();
    await page.locator('#chat-options [data-action="connections"]').click();
    await page.locator('#dialog[open]').waitFor();
    await page.waitForTimeout(200);
    const settingsCheck = await page.evaluate(() => {
      const text = document.querySelector('#dialog .modal-body')?.innerText || '';
      const selects = [...document.querySelectorAll('#dialog select option')].map((o) => o.value);
      return {
        hasOrchestrator: text.includes('gemini-pro-orchestrator-neon') || selects.includes('gemini-pro-orchestrator-neon'),
        hasFast: text.includes('gemini-3.8-flash-medium') || selects.includes('gemini-3.8-flash-medium'),
        hasArgon: selects.some((v) => v.toLowerCase().includes('argon')),
      };
    });
    assert.equal(settingsCheck.hasOrchestrator, true, 'Cài đặt thiếu gemini-pro-orchestrator-neon');
    assert.equal(settingsCheck.hasFast, true, 'Cài đặt thiếu gemini-3.8-flash-medium');
    assert.equal(settingsCheck.hasArgon, false, 'Không được xuất hiện argon trong danh sách model');
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-agy-settings.png')});
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});

    // 8. Luồng Auto-Create 1 chạm (đối chiếu Ảnh 5 — KHÔNG rơi vào quick-exam-plan 4 form!)
    // Dùng API thật POST /api/exams/{id}/agent/auto-create trả SSE hoàn chỉnh (qua route stub nhẹ để không đốt quota live API trong test UI)
    await page.route('**/api/exams/*/agent/auto-create', async (route) => {
      const sseBody = [
        'event: step\ndata: {"phase":"plan","status":"done","title":"Đề kiểm tra Cuối kì 1 · Toán 11 (GDPT 2018)","subject":"Toán","grade":"11","minutes":90,"totalQuestions":4,"totalBatches":2}\n\n',
        'event: batch\ndata: {"batchIndex":1,"totalBatches":2,"completedCount":2,"totalSlots":4,"model":"gemini-3.8-flash-medium"}\n\n',
        'event: batch\ndata: {"batchIndex":2,"totalBatches":2,"completedCount":4,"totalSlots":4,"model":"gemini-pro-orchestrator-neon"}\n\n',
        'event: step\ndata: {"phase":"swarm","status":"done","completedCount":4,"totalBatches":2}\n\n',
        'event: verify\ndata: {"totalQuestions":4,"totalPoints":10,"repairRounds":0}\n\n',
        'event: step\ndata: {"phase":"goal","status":"done","repairRounds":0}\n\n',
        `event: complete\ndata: ${JSON.stringify({
          title: 'Đề kiểm tra Cuối kì 1 · Toán 11 (GDPT 2018)',
          subject: 'Toán',
          grade: '11',
          minutes: 90,
          totalPoints: 10,
          message: 'Đã tự động soạn xong 4 câu Toán 11 chuẩn GDPT 2018 (Orchestrator Neon + Flash Medium, 0 lỗi).',
          matrix: [{topic: 'Lượng giác & Giới hạn', targets: [1, 1, 1, 1]}],
          questions: [
            {id: 'ac-1', v: 1, type: 'mcq', topic: 'Lượng giác', level: 0, points: 2.5, approvalStatus: 'draft', stem: 'Tập xác định của hàm số $y = \\tan x$ là?', options: ['$\\mathbb{R}$', '$\\mathbb{R} \\setminus \\{\\frac{\\pi}{2}+k\\pi\\}$', '$\\mathbb{R} \\setminus \\{k\\pi\\}$', '$(0;+\\infty)$'], answer: 1, answerKnown: true, explanation: 'Điều kiện $\\cos x \\neq 0$.'},
            {id: 'ac-2', v: 1, type: 'mcq', topic: 'Dãy số', level: 1, points: 2.5, approvalStatus: 'draft', stem: 'Giới hạn $\\lim_{n\\to\\infty}\\frac{3n-1}{n+2}$ bằng?', options: ['1', '2', '3', '-1/2'], answer: 2, answerKnown: true, explanation: 'Chia tử mẫu cho $n$.'},
            {id: 'ac-3', v: 1, type: 'mcq', topic: 'Không gian', level: 2, points: 2.5, approvalStatus: 'draft', stem: 'Trong không gian, hai đường thẳng chéo nhau có bao nhiêu điểm chung?', options: ['0', '1', '2', 'Vô số'], answer: 0, answerKnown: true, explanation: 'Hai đường thẳng chéo nhau không đồng phẳng và không cắt nhau.'},
            {id: 'ac-4', v: 1, type: 'essay', topic: 'Giới hạn hàm số', level: 3, points: 2.5, approvalStatus: 'draft', stem: 'Tính giới hạn $I = \\lim_{x\\to 1}\\frac{x^2-1}{x-1}$.', options: [], answer: 0, answerKnown: true, explanation: 'Phân tích tử thức thành $(x-1)(x+1)$, suy ra $I = 2$.', rubric: [{text: 'Rút gọn $(x-1)(x+1)$ đúng', points: 1.5}, {text: 'Tính đúng kết quả $I=2$', points: 1}]},
          ],
          stats: {modelsUsed: ['gemini-pro-orchestrator-neon', 'gemini-3.8-flash-medium'], repairRounds: 0},
        })}\n\n`,
      ].join('');
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream; charset=utf-8',
        body: sseBody,
      });
    });

    // Bật consent 1 lần (bên trong menu ⋯) rồi gõ trực tiếp prompt mà user chụp trong Ảnh 5
    await page.locator('[data-ux-action="options"]').click();
    await page.locator('#ai-consent').check();
    await page.locator('[data-ux-action="options"]').click();
    await page.locator('#chat-input').fill('tạo 1 đề thi cuối kì 1 lớp 11 môn toán theo chuẩn bgd 2018 đu');
    await page.locator('#chat-form button[type="submit"]').click();
    await page.locator('.auto-create-card[data-status="complete"]').waitFor();
    await page.waitForFunction(() => document.querySelectorAll('.paper .question').length === 4);
    assert.equal(await page.locator('.quick-exam-plan').count(), 0, 'Vẫn rơi vào quick-exam-plan thay vì tự động 1 chạm!');
    await page.waitForTimeout(150);
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-auto-create-live.png')});

    // 9. Mobile 390px: mở menu Chỉnh sửa rồi kích hoạt Tìm & Thay (menu phải tự đóng, không che ô input)
    await page.setViewportSize({width: 390, height: 844});
    await page.waitForTimeout(150);
    if (await page.locator('.assistant.open').count()) {
      await page.locator('.assistant [data-action="toggle-chat"]').first().click().catch(() => {});
    }
    await page.locator('.menubar [data-menu="edit"]').click();
    await page.locator('.floating-panel.document-menu [data-action="studio-replace"]').click();
    await page.locator('.studio-find').waitFor();
    await page.waitForTimeout(120);
    const mobileFindOk = await page.evaluate(() => {
      const inp = document.querySelector('#find-query');
      const menu = document.querySelector('.floating-panel.document-menu');
      const inpRect = inp?.getBoundingClientRect();
      return {
        menuOpen: Boolean(menu && getComputedStyle(menu).display !== 'none'),
        findVisible: Boolean(inpRect && inpRect.width > 80 && inpRect.height > 20),
      };
    });
    assert.equal(mobileFindOk.menuOpen, false, 'Menu Chỉnh sửa vẫn mở đè lên thanh Tìm/Thay');
    assert.equal(mobileFindOk.findVisible, true, 'Ô Tìm kiếm không hiển thị rõ trên mobile 390px');
    await page.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-mobile-390-find.png')});

    // 10. Phòng thi học sinh: khóa Audio ở 0 lượt & nút nhảy câu chưa làm
    const wavBuf = buildSampleWavBuffer();
    const wavB64 = `data:audio/wav;base64,${wavBuf.toString('base64')}`;
    const audioFileId = 'uv63-aud-1';
    const kvFileRes = await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({key: `file:${audioFileId}`, value: wavB64}),
    });
    assert.equal(kvFileRes.status, 200);

    const roomExam = {
      id: 'uv63-room-exam',
      title: 'Kiểm tra Nghe Tiếng Anh 11',
      subject: 'Tiếng Anh',
      grade: '11',
      minutes: 15,
      revision: 1,
      updated: Date.now(),
      workflowStatus: 'approved',
      approvalStatus: 'approved',
      audio: {fileId: audioFileId, filename: 'listen.wav', title: 'Listening Track 1', maxPlays: 1, mimeType: 'audio/wav'},
      questions: [
        {id: 'rq-1', v: 1, type: 'mcq', stem: 'Câu nghe 1: What time does the library open?', options: ['7:00', '8:00', '9:00', '10:00'], answer: 1, answerKnown: true, points: 5, approvalStatus: 'approved'},
        {id: 'rq-2', v: 1, type: 'mcq', stem: 'Câu 2: Chọn đáp án đúng?', options: ['A', 'B', 'C', 'D'], answer: 0, answerKnown: true, points: 5, approvalStatus: 'approved'},
      ],
      docs: [],
      matrix: [{topic: 'Listening', targets: [2, 0, 0, 0]}],
      undo: [],
      redo: [],
      history: [],
      appliedPrefs: [],
      chat: [],
      quote: {text: '', versions: [], chosen: ''},
    };
    const kvCurRes = await fetch(`${baseUrl}/api/kv?key=state`);
    assert.equal(kvCurRes.status, 200);
    const kvCur = await kvCurRes.json();
    const kvPutRoomExamRes = await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Origin: baseUrl,
        ...(kvCur.revision ? {'If-Match': String(kvCur.revision)} : {}),
      },
      body: JSON.stringify({
        key: 'state',
        value: {
          ...(kvCur.value || {version: 1, prefs: []}),
          current: kvCur.value?.current || roomExam.id,
          exams: [...(kvCur.value?.exams || []).filter((x) => x.id !== roomExam.id), roomExam],
        },
      }),
    });
    assert.equal(kvPutRoomExamRes.status, 200);

    const roomRes = await fetch(`${baseUrl}/api/rooms`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({examId: roomExam.id, title: roomExam.title, mode: 'exam', status: 'open'}),
    });
    assert.equal(roomRes.status, 201);
    const roomCreated = await roomRes.json();
    const roomCode = roomCreated.room?.roomCode || roomCreated.roomCode;
    assert.ok(roomCode, 'Thiếu roomCode trả về từ POST /api/rooms');

    const studentPage = await browser.newPage({viewport: {width: 420, height: 844}});
    studentPage.setDefaultTimeout(15000);
    studentPage.on('pageerror', (e) => pageErrors.push(`student:${e.message}`));
    await studentPage.goto(`${baseUrl}/phong-thi/${roomCode}`, {waitUntil: 'networkidle'});
    await studentPage.locator('#sr-join-form input[name="studentName"]').fill('Nguyễn Học Sinh');
    await studentPage.locator('#sr-join-form input[name="studentClass"]').fill('11A1');
    await studentPage.locator('#sr-join-form input[name="studentCode"]').fill('11A1-01');
    await studentPage.locator('#sr-join-form button[type="submit"]').click();
    await studentPage.locator('[data-sr-action="play-audio"]').waitFor();
    await studentPage.locator('[data-sr-action="play-audio"]').click();
    await studentPage.waitForFunction(() => {
      const btn = document.querySelector('[data-sr-action="play-audio"]');
      return btn && btn.disabled && document.body.innerText.includes('0 / 1');
    });
    // Theo đặc tả UV64, <audio controls> được giữ hết lượt phát hiện tại rồi tự khóa sau khi ended
    await studentPage.waitForFunction(() => !document.querySelector('audio.sr-audio-el'), {timeout: 5000});
    await studentPage.locator('[data-sr-action="ask-submit"]').first().click();
    await studentPage.locator('[data-sr-action="jump-first-unanswered"]').first().waitFor();
    await studentPage.waitForTimeout(150);
    const audioLockCheck = await studentPage.evaluate(() => {
      const aud = document.querySelector('audio');
      const playBtn = document.querySelector('[data-sr-action="play-audio"]');
      const badge = document.body.innerText.includes('Hết lượt') || document.body.innerText.includes('0 / 1');
      const jumpBtn = Boolean(document.querySelector('[data-sr-action="jump-first-unanswered"]'));
      return {
        hasControls: aud ? aud.hasAttribute('controls') : false,
        playBtnDisabled: Boolean(playBtn?.disabled),
        badge,
        jumpBtn,
      };
    });
    assert.equal(audioLockCheck.hasControls, false, 'Audio còn 0 lượt vẫn còn controls!');
    assert.equal(audioLockCheck.playBtnDisabled, true, 'Nút nghe Audio ở 0 lượt phải bị vô hiệu hóa!');
    assert.equal(audioLockCheck.badge, true, 'Thiếu huy hiệu Hết lượt / 0 / 1');
    assert.equal(audioLockCheck.jumpBtn, true, 'Thiếu nút Chuyển tới câu chưa làm');
    await studentPage.screenshot({path: path.join(EVIDENCE_DIR, 'uv63-room-audio-locked.png')});
    await studentPage.close();

    assert.deepEqual(consoleErrors, [], `Console errors: ${consoleErrors.join('; ')}`);
    assert.deepEqual(pageErrors, [], `Page errors: ${pageErrors.join('; ')}`);
    assert.deepEqual(httpErrors, [], `HTTP errors: ${httpErrors.join('; ')}`);

    const summary = {
      ok: true,
      baseUrl,
      screenshots: [
        'uv63-home-1440.png',
        'uv63-home-1280.png',
        'uv63-home-390.png',
        'uv63-proactive-campaigns.png',
        'uv63-workspace-1440.png',
        'uv63-workspace-1280.png',
        'uv63-composer-modal.png',
        'uv63-sgk-kntt-2pane.png',
        'uv63-agy-settings.png',
        'uv63-auto-create-live.png',
        'uv63-mobile-390-find.png',
        'uv63-room-audio-locked.png',
      ],
      composerCheck,
      sgkCheck,
      settingsCheck,
      ws1440,
      mobileFindOk,
      audioLockCheck,
    };
    console.log(JSON.stringify(summary, null, 2));
  } finally {
    await browser.close();
    await stopServer(server.proc);
    fs.rmSync(tempRoot, {recursive: true, force: true});
  }
}

await main();
