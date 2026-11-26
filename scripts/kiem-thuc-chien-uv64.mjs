import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import JSZip from 'jszip';
import {chromium} from 'playwright-core';
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs';

const ROOT = process.cwd();
const PYTHON_EXE = process.env.QA_PYTHON || path.join(ROOT, 'backend', '.venv', 'Scripts', 'python.exe');
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);

const EVIDENCE_DIR = process.env.QA_UV64_SCREENSHOT_DIR
  ? path.resolve(process.env.QA_UV64_SCREENSHOT_DIR)
  : path.join(os.tmpdir(), 'qa-uv64');

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

async function buildMinimalPptxBuffer(slideText = 'Slide 1: Đọc hiểu văn bản PPTX UV64') {
  const zip = new JSZip();
  zip.file(
    '[Content_Types].xml',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
      '<Default Extension="xml" ContentType="application/xml"/>' +
      '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>' +
      '<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' +
      '</Types>',
  );
  zip.file(
    '_rels/.rels',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>' +
      '</Relationships>',
  );
  zip.file(
    'ppt/presentation.xml',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
      '<p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>' +
      '</p:presentation>',
  );
  zip.file(
    'ppt/_rels/presentation.xml.rels',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>' +
      '</Relationships>',
  );
  zip.file(
    'ppt/slides/slide1.xml',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">' +
      '<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>' +
      slideText +
      '</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>' +
      '</p:sld>',
  );
  return await zip.generateAsync({type: 'nodebuffer'});
}

async function pdfText(bytes) {
  const doc = await pdfjsLib.getDocument({data: new Uint8Array(bytes), verbosity: 0}).promise;
  let text = '';
  for (let p = 1; p <= doc.numPages; p++) {
    const page = await doc.getPage(p);
    const tc = await page.getTextContent();
    text += tc.items.map((i) => i.str).join(' ') + '\n';
  }
  return text;
}

async function docxText(bytes) {
  const zip = await JSZip.loadAsync(bytes);
  const xml = await zip.file('word/document.xml').async('string');
  return [...xml.matchAll(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g)].map((m) => m[1]).join('');
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

async function main() {
  fs.mkdirSync(EVIDENCE_DIR, {recursive: true});
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'uv64-real-'));
  const dataDir = path.join(tempRoot, 'local-data');
  fs.mkdirSync(dataDir, {recursive: true});

  const port = await freePort();
  const server = await startLocalServer(port, dataDir);
  const {baseUrl} = server;
  const consoleErrors = [];
  const pageErrors = [];
  const findings = [];
  const checks = {};

  const browser = await chromium.launch({
    executablePath: findChrome(),
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--autoplay-policy=no-user-gesture-required'],
  });

  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 900}, acceptDownloads: true});
    const page = await context.newPage();
    page.setDefaultTimeout(20000);
    let allowExpected503 = false;
    page.on('console', (m) => {
      if (m.type() === 'error') {
        const txt = m.text();
        if (allowExpected503 && txt.includes('status of 503')) return;
        consoleErrors.push(txt);
      }
    });
    page.on('pageerror', (e) => pageErrors.push(e.message));

    const shot = async (name) => {
      const p = path.join(EVIDENCE_DIR, name);
      await page.screenshot({path: p});
      return p;
    };

    // =========================================================================
    // 1. Nguồn thu hồi (pending_review) + gỡ sạch assistantSources:[] + Soạn nhanh consent
    // =========================================================================
    const revokedLessonRes = await fetch(`${baseUrl}/api/lesson-catalog/sources`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({
        grade: 10,
        subject: 'Toán',
        series: 'KNTT',
        volume: 'Tập 1',
        chapter: 'Chương I',
        lesson: 'Bài 1',
        title: 'Nguồn bị thu hồi QA64',
        license_status: 'pending_review',
        locator: 'Trang 1',
        content_excerpt: 'NOI_DUNG_BI_THU_HOI_KHONG_DUOC_LOT',
      }),
    });
    assert.equal(revokedLessonRes.status, 201, 'Phải tạo được bản ghi curriculum_sources pending_review');
    const revokedRec = await revokedLessonRes.json();

    const examRevId = 'uv64-exam-revoked';
    const examEmptySelId = 'uv64-exam-empty-sel';
    const examQuickAId = 'uv64-exam-quick-a';
    const examConsentBId = 'uv64-exam-consent-b';

    const curKv = await (await fetch(`${baseUrl}/api/kv?key=state`)).json();
    const seededState = {
      version: curKv?.value?.version || 1,
      current: examQuickAId,
      prefs: [],
      exams: [
        {
          id: examRevId,
          title: 'Đề chứa bản chụp nguồn đã thu hồi',
          subject: 'Toán',
          grade: '10',
          minutes: 45,
          revision: 1,
          updated: Date.now(),
          aiConsent: true,
          docs: [
            {
              id: revokedRec.id,
              name: 'Nguồn thu hồi (snapshot allowed)',
              kind: 'text',
              version: 1,
              licenseStatus: 'allowed',
              pages: [{number: 1, text: 'NOI_DUNG_BI_THU_HOI_KHONG_DUOC_LOT'}],
              text: 'NOI_DUNG_BI_THU_HOI_KHONG_DUOC_LOT',
            },
          ],
          assistantSources: [revokedRec.id],
          questions: [],
          matrix: [{topic: 'Mệnh đề', targets: [1, 0, 0, 0]}],
          undo: [],
          redo: [],
          history: [],
          appliedPrefs: [],
          chat: [],
          quote: {text: '', versions: [], chosen: ''},
        },
        {
          id: examEmptySelId,
          title: 'Đề đã gỡ hết assistantSources',
          subject: 'Toán',
          grade: '10',
          minutes: 45,
          revision: 1,
          updated: Date.now(),
          aiConsent: true,
          docs: [
            {
              id: 'local-doc-hidden',
              name: 'Tài liệu riêng không được chọn',
              kind: 'text',
              version: 1,
              pages: [{number: 1, text: 'TAI_LIEU_KHONG_DUOC_PHEP_TRUY_XUAT_64'}],
              text: 'TAI_LIEU_KHONG_DUOC_PHEP_TRUY_XUAT_64',
            },
          ],
          assistantSources: [],
          questions: [],
          matrix: [{topic: 'Hàm số', targets: [1, 0, 0, 0]}],
          undo: [],
          redo: [],
          history: [],
          appliedPrefs: [],
          chat: [],
          quote: {text: '', versions: [], chosen: ''},
        },
        {
          id: examQuickAId,
          title: 'Đề A kiểm Soạn nhanh',
          subject: 'Toán',
          grade: '10',
          minutes: 45,
          revision: 1,
          updated: Date.now(),
          aiConsent: false,
          docs: [],
          questions: [],
          matrix: [{topic: 'Mệnh đề', targets: [1, 0, 0, 0]}],
          undo: [],
          redo: [],
          history: [],
          appliedPrefs: [],
          chat: [],
          quote: {text: '', versions: [], chosen: ''},
        },
        {
          id: examConsentBId,
          title: 'Đề B chưa cấp quyền AI',
          subject: 'Toán',
          grade: '10',
          minutes: 45,
          revision: 1,
          updated: Date.now(),
          aiConsent: false,
          docs: [
            {
              id: 'b-private-doc',
              name: 'Tư liệu B',
              kind: 'text',
              version: 1,
              pages: [{number: 1, text: 'Dữ liệu riêng của đề B'}],
              text: 'Dữ liệu riêng của đề B',
            },
          ],
          assistantSources: ['b-private-doc'],
          questions: [],
          matrix: [{topic: 'Tập hợp', targets: [1, 0, 0, 0]}],
          undo: [],
          redo: [],
          history: [],
          appliedPrefs: [],
          chat: [],
          quote: {text: '', versions: [], chosen: ''},
        },
      ],
    };
    const putSeed = await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl, ...(curKv?.revision ? {'If-Match': String(curKv.revision)} : {})},
      body: JSON.stringify({key: 'state', value: seededState}),
    });
    assert.equal(putSeed.status, 200);

    // 1a. Kiểm tra API chặn 403 source_license_restricted cả ở chat và auto-create
    const revChatRes = await fetch(`${baseUrl}/api/assistant/chat`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({examId: examRevId, text: 'Tóm tắt nguồn', consent: true}),
    });
    assert.equal(revChatRes.status, 403);
    const revChatJson = await revChatRes.json();
    assert.equal(revChatJson.code, 'source_license_restricted');

    const revAutoRes = await fetch(`${baseUrl}/api/exams/${examRevId}/agent/auto-create`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({prompt: 'Soạn 1 câu', consentGiven: true}),
    });
    assert.equal(revAutoRes.status, 403);
    assert.equal((await revAutoRes.json()).code, 'source_license_restricted');

    // 1b. Kiểm tra assistantSources: [] không fallback lấy exam.docs (kể cả qua chat endpoint thật khi chưa cấu hình AI: kiểm 0 nguồn gửi tới AI bằng route /api/assistant/chat/stream stub nhẹ không? Trước hết kiểm API thật: local_workspace không fallback)
    // Với Chrome UI: kiểm Soạn đề nhanh từ bài SGK trên Đề A -> Hoàn tác -> Đề B vẫn hỏi consent và workspaceAiConsent=false
    await page.goto(baseUrl, {waitUntil: 'networkidle'});
    await page.locator('.paper').waitFor();

    let capturedAutoCreateReq = null;
    await page.route('**/api/exams/*/agent/auto-create', async (route) => {
      capturedAutoCreateReq = JSON.parse(route.request().postData() || '{}');
      const sseBody = [
        'event: step\ndata: {"phase":"plan","status":"done","title":"Đề A nhanh","subject":"Toán","grade":"10","minutes":45,"totalQuestions":1,"totalBatches":1}\n\n',
        'event: step\ndata: {"phase":"swarm","status":"done","completedCount":1,"totalBatches":1}\n\n',
        'event: verify\ndata: {"totalQuestions":1,"totalPoints":10,"repairRounds":0}\n\n',
        'event: step\ndata: {"phase":"goal","status":"done","repairRounds":0}\n\n',
        `event: complete\ndata: ${JSON.stringify({
          title: 'Đề A nhanh',
          subject: 'Toán',
          grade: '10',
          minutes: 45,
          totalPoints: 10,
          matrix: [{topic: 'Mệnh đề', targets: [1, 0, 0, 0]}],
          questions: [
            {id: 'qa-gen-1', v: 1, type: 'mcq', topic: 'Mệnh đề', level: 0, points: 10, approvalStatus: 'draft', stem: 'Mệnh đề nào đúng?', options: ['A', 'B', 'C', 'D'], answer: 0, answerKnown: true, explanation: 'A đúng'},
          ],
          stats: {modelsUsed: ['gemini-3.8-flash-medium'], repairRounds: 0},
        })}\n\n`,
      ].join('');
      await route.fulfill({status: 200, contentType: 'text/event-stream; charset=utf-8', body: sseBody});
    });

    await page.locator('[data-action="lesson-sources"]:visible').first().click();
    await page.locator('#dialog[open] #lesson-picker').waitFor();
    await page.locator('#lesson-picker .sgk-lesson-row').first().click();
    await page.locator('#lesson-picker [data-sgk-quick-compose]').click();
    await page.locator('.auto-create-card[data-status="complete"]').waitFor();
    assert.ok(capturedAutoCreateReq, 'Soạn nhanh phải gọi /agent/auto-create');
    assert.equal(capturedAutoCreateReq.consentGiven, true);
    assert.equal(capturedAutoCreateReq.saveWorkspaceConsent, false, 'Soạn nhanh KHÔNG được bật saveWorkspaceConsent');
    assert.equal(capturedAutoCreateReq.sources.length, 1, 'Chỉ gửi đúng 1 bài đã chọn, không tự chèn thêm');

    const statusAfterQuick = await (await fetch(`${baseUrl}/api/status`)).json();
    assert.equal(statusAfterQuick.config?.fixedRouter?.workspaceAiConsent, false, 'workspaceAiConsent phải giữ false');

    // Hoàn tác trên Đề A rồi chuyển sang Đề B kiểm tra consent
    await page.locator('[data-action="undo"]:visible').first().click();
    await page.waitForTimeout(200);

    // Kiểm tra Đề A sau Hoàn tác KHÔNG bị tự bật aiConsent=true
    const kvAfterUndo = await (await fetch(`${baseUrl}/api/kv?key=state`)).json();
    const examAAfterUndo = kvAfterUndo.value.exams.find((x) => x.id === examQuickAId);
    const examAAiConsentAfterUndo = Boolean(examAAfterUndo?.aiConsent);
    assert.equal(examAAiConsentAfterUndo, false, 'Sau khi Hoàn tác trên Đề A, aiConsent phải giữ false');

    // Chuyển sang Đề B (aiConsent=false) và gửi chat -> PHẢI hiện thẻ xin phép AI (.chat-consent-card)
    await page.locator('.design-rail [data-action="library"]').click();
    await page.locator('#dialog[open] .wb-library').waitFor();
    await page.locator('.wb-library-card', {hasText: 'Đề B chưa cấp quyền AI'}).locator('[data-action="open-exam"]').click();
    await page.locator('#dialog').waitFor({state: 'hidden'});
    await page.locator('#chat-input').fill('Hãy đặt 1 câu từ tư liệu');
    await page.locator('#chat-send').click();
    await page.locator('.chat-consent-card').waitFor();
    await page.unroute('**/api/exams/*/agent/auto-create');

    // Chuyển sang Đề đã gỡ hết assistantSources: [] -> xác nhận 0 chip và không tự gửi doc trong DOM
    await page.locator('.design-rail [data-action="library"]').click();
    await page.locator('#dialog[open] .wb-library').waitFor();
    await page.locator('.wb-library-card', {hasText: 'Đề đã gỡ hết assistantSources'}).locator('[data-action="open-exam"]').click();
    await page.locator('#dialog').waitFor({state: 'hidden'});
    assert.equal(await page.locator('.assistant-sources .source-chip').count(), 0);
    await shot('uv64-sources-consent-guard.png');
    checks.sourcesAndConsent = {
      revokedChatStatus: revChatRes.status,
      revokedAutoStatus: revAutoRes.status,
      quickComposeSaveWorkspaceConsent: capturedAutoCreateReq.saveWorkspaceConsent,
      workspaceAiConsentAfterQuick: statusAfterQuick.config?.fixedRouter?.workspaceAiConsent,
      examAAiConsentAfterUndo,
      examBPromptedConsent: true,
    };

    // =========================================================================
    // 2. Sao lưu & Khôi phục kho sạch có WAV + đề cộng đồng answer:null -> 200 OK + nghe WAV
    // =========================================================================
    const wavBuf = buildSampleWavBuffer();
    const wavUri = `data:audio/wav;base64,${wavBuf.toString('base64')}`;
    const backupPayload = {
      format: 'tro-ly-soan-de',
      version: 1,
      savedAt: new Date().toISOString(),
      examExportsCount: 2,
      state: {
        version: 1,
        current: 'restored-exam-1',
        prefs: [],
        exams: [
          {
            id: 'restored-exam-1',
            title: 'Đề khôi phục có Audio WAV & ẩn đáp án',
            subject: 'Tiếng Anh',
            grade: '11',
            minutes: 45,
            revision: 1,
            updated: Date.now(),
            audio: {fileId: 'aud-wav-64', filename: 'track64.wav', title: 'Track UV64', maxPlays: 2, mimeType: 'audio/wav'},
            questions: [
              {
                id: 'rq-comm-null',
                v: 1,
                type: 'mcq',
                level: 0,
                stem: 'Câu cộng đồng ẩn khóa đáp án (6 phương án):',
                options: ['O1', 'O2', 'O3', 'O4', 'O5', 'O6'],
                answer: null,
                answerKnown: false,
                points: 5,
                explanation: '',
              },
              {
                id: 'rq-mcq-e',
                v: 1,
                type: 'mcq',
                level: 0,
                stem: 'Câu 5 phương án đáp án E:',
                options: ['PA A', 'PA B', 'PA C', 'PA D', 'PA E'],
                answer: 4,
                answerKnown: true,
                points: 5,
                explanation: 'Đáp án E',
              },
            ],
            docs: [],
            data: [],
            matrix: [{topic: 'Listening', targets: [2, 0, 0, 0]}],
            undo: [],
            redo: [],
            history: [],
            appliedPrefs: [],
            chat: [],
            quote: {text: '', versions: [], chosen: ''},
          },
        ],
      },
      files: {'aud-wav-64': wavUri},
    };
    const backupPath = path.join(tempRoot, 'backup-uv64.json');
    fs.writeFileSync(backupPath, JSON.stringify(backupPayload), 'utf8');

    // Mở Xuất đề kiểm tra cảnh báo exam_exports scope notice trước
    await page.locator('[data-action="export"]:visible').first().click();
    await page.locator('#dialog[open] .export-history-scope-note').waitFor();
    const scopeNoticeText = await page.locator('#dialog .export-history-scope-note').textContent();
    assert.match(scopeNoticeText || '', /exam_exports|không di chuyển sang kho mới/i);
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});

    // Nhập bản sao JSON qua Kho đề -> kiểm tra cảnh báo + khôi phục 200 OK + audio WAV load lại được
    await page.locator('.design-rail [data-action="library"]').click();
    await page.locator('#dialog[open] [data-action="import-backup"]').waitFor();
    const [fc] = await Promise.all([
      page.waitForEvent('filechooser'),
      page.locator('#dialog[open] [data-action="import-backup"]').click(),
    ]);
    await fc.setFiles(backupPath);
    await page.locator('#dialog[open] [data-action="confirm-backup"]').waitFor();
    const previewDlgText = await page.locator('#dialog').textContent();
    assert.match(previewDlgText || '', /Khôi phục bản sao dữ liệu/i);
    const [restoreResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes('/api/workspace/restore') && !r.url().includes('/preview')),
      page.locator('#dialog [data-action="confirm-backup"]').click(),
    ]);
    assert.equal(restoreResp.status(), 200, 'Khôi phục bản sao WAV + answer:null phải trả 200 OK');
    await page.waitForLoadState('networkidle');
    await page.locator('.paper audio[data-audio-file-id="aud-wav-64"]').waitFor();
    await page.waitForFunction(() => {
      const a = document.querySelector('audio[data-audio-file-id="aud-wav-64"]');
      return a && a.dataset.loaded === '1' && String(a.src).startsWith('data:audio/wav');
    });
    await shot('uv64-backup-restore-audio.png');
    checks.backupRestore = {restoreStatus: restoreResp.status(), audioLoaded: true, scopeNotice: scopeNoticeText?.trim()};

    // =========================================================================
    // 3. Trộn mã đề 2 khối ngữ liệu 4 câu (Mã 102: 3-4-1-2) -> DOCX XML, HTML, PDF & max 2 mã
    // =========================================================================
    const passageExam = {
      id: 'uv64-passage-variants',
      title: 'Đề đọc hiểu 2 ngữ liệu UV64',
      subject: 'Ngữ văn',
      grade: '9',
      minutes: 45,
      revision: 1,
      updated: Date.now(),
      passages: [
        {id: 'p1', title: 'Ngữ liệu 1 (câu 1–2): Mùa xuân', text: 'Đoạn văn mùa xuân dùng cho từ câu 1 đến câu 2.'},
        {id: 'p2', title: 'Ngữ liệu 2 (câu 3–4): Biển đảo', text: 'Đoạn văn biển đảo dùng cho câu 3 và câu 4.'},
      ],
      questions: [
        {id: 'pv1', v: 1, type: 'mcq', passageId: 'p1', topic: 'Đọc hiểu', level: 0, points: 2.5, stem: 'Câu 1a mùa xuân?', options: ['A', 'B', 'C', 'D'], answer: 0, answerKnown: true, explanation: 'G1'},
        {id: 'pv2', v: 1, type: 'mcq', passageId: 'p1', topic: 'Đọc hiểu', level: 0, points: 2.5, stem: 'Câu 1b mùa xuân?', options: ['A', 'B', 'C', 'D'], answer: 1, answerKnown: true, explanation: 'G2'},
        {id: 'pv3', v: 1, type: 'mcq', passageId: 'p2', topic: 'Đọc hiểu', level: 1, points: 2.5, stem: 'Câu 2a biển đảo?', options: ['A', 'B', 'C', 'D'], answer: 2, answerKnown: true, explanation: 'G3'},
        {id: 'pv4', v: 1, type: 'mcq', passageId: 'p2', topic: 'Đọc hiểu', level: 1, points: 2.5, stem: 'Câu 2b biển đảo?', options: ['A', 'B', 'C', 'D'], answer: 3, answerKnown: true, explanation: 'G4'},
      ],
      docs: [],
      matrix: [{topic: 'Đọc hiểu', type: 'mcq', targets: [2, 2, 0, 0]}],
      undo: [],
      redo: [],
      history: [],
      appliedPrefs: [],
      chat: [],
      quote: {text: '', versions: [], chosen: ''},
    };
    const kvBeforePass = await (await fetch(`${baseUrl}/api/kv?key=state`)).json();
    await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl, 'If-Match': String(kvBeforePass.revision)},
      body: JSON.stringify({
        key: 'state',
        value: {...kvBeforePass.value, current: passageExam.id, exams: [...kvBeforePass.value.exams, passageExam]},
      }),
    });
    await page.reload({waitUntil: 'networkidle'});
    await page.locator('.paper').waitFor();

    await page.locator('[data-action="export"]:visible').first().click();
    await page.locator('#dialog[open] #export-variants').waitFor();
    await page.locator('#export-variants summary').click();
    const varBoxes = page.locator('#export-variants input[data-kind]');
    for (let i = 0; i < (await varBoxes.count()); i++) await varBoxes.nth(i).check();
    const variantCodeTexts = await page.locator('#export-variant-code option').allTextContents();
    assert.deepEqual(variantCodeTexts, ['Đề gốc', 'Mã đề 101', 'Mã đề 102'], '2 khối 4 câu chỉ được hiện tối đa 2 mã 101, 102');

    await page.locator('#export-variant-code').selectOption('1'); // Mã đề 102
    await page.locator('[data-action="preview-variant"]').click();
    await page.locator('.variant-preview').waitFor();
    const previewHtmlText = await page.locator('.variant-preview').textContent();
    assert.match(previewHtmlText || '', /Biển đảo/);
    assert.match(previewHtmlText || '', /Mùa xuân/);
    assert.match(previewHtmlText || '', /câu 1–2/);
    assert.match(previewHtmlText || '', /câu 3–4/);
    await shot('uv64-variant-passages-preview.png');

    const downloadPack = async (format) => {
      const [resp] = await Promise.all([
        page.waitForResponse((r) => r.url().includes('/api/save-export')),
        page.locator(`#export-variants [data-action="export-pack"][data-format="${format}"]`).click(),
      ]);
      assert.equal(resp.status(), 200);
      const j = await resp.json();
      const zipRes = await fetch(`${baseUrl}${j.url}`);
      assert.equal(zipRes.status, 200);
      const zip = await JSZip.loadAsync(Buffer.from(await zipRes.arrayBuffer()));
      await page.locator('#dialog [data-action="export"]').first().click();
      await page.locator('#dialog #export-variants').waitFor();
      return zip;
    };

    const docxPackZip = await downloadPack('docx');
    const ma102Docx = await docxText(await docxPackZip.file('HOC_SINH/Ma_102.docx').async('nodebuffer'));
    assert.ok(ma102Docx.includes('Biển đảo') && ma102Docx.includes('Mùa xuân'), 'Ma_102.docx thiếu ngữ liệu');
    assert.ok(ma102Docx.includes('câu 1–2') && ma102Docx.includes('từ câu 3 đến câu 4'), `Ma_102.docx chưa đổi lời dẫn: ${ma102Docx}`);
    assert.ok(ma102Docx.indexOf('Biển đảo') < ma102Docx.indexOf('Mùa xuân'), 'Ma_102.docx sai thứ tự ngữ liệu');

    const htmlPackZip = await downloadPack('html');
    const ma102Html = await htmlPackZip.file('HOC_SINH/Ma_102.html').async('string');
    assert.ok(ma102Html.includes('Biển đảo') && ma102Html.includes('Mùa xuân'));
    assert.ok(ma102Html.includes('câu 1–2') && ma102Html.includes('từ câu 3 đến câu 4'));

    const pdfPackZip = await downloadPack('pdf');
    const ma102Pdf = await pdfText(await pdfPackZip.file('HOC_SINH/Ma_102.pdf').async('nodebuffer'));
    assert.ok(ma102Pdf.includes('Biển đảo') && ma102Pdf.includes('Mùa xuân'), 'Ma_102.pdf thiếu ngữ liệu');
    assert.ok(ma102Pdf.includes('câu 1–2') && ma102Pdf.includes('từ câu 3 đến câu 4'), 'Ma_102.pdf chưa đổi lời dẫn');

    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});
    checks.variantPassages = {variantCodeTexts, docxOk: true, htmlOk: true, pdfOk: true};

    // =========================================================================
    // 4. Đề 2 hướng Tin học + Đáp án E + Mẫu ma trận 0.40/9.60 + Rebalance + Ma trận ngược
    // =========================================================================
    const tin2TrackExam = {
      id: '64000000-0000-4000-8000-000000000004',
      title: 'Đề Tin học 12 hai hướng UV64',
      subject: 'Tin học',
      grade: '12',
      minutes: 50,
      revision: 1,
      updated: Date.now(),
      questions: [
        {id: 'tc1', v: 1, type: 'mcq', topic: 'Mạng máy tính', level: 0, points: 0.4, stem: 'Câu chung 1 (0,4đ)?', options: ['A', 'B', 'C', 'D'], answer: 0, answerKnown: true, explanation: 'G'},
        {id: 'tc2', v: 1, type: 'mcq', topic: 'Mạng máy tính', level: 0, points: 9.6, stem: 'Câu chung 2 (9,6đ)?', options: ['A', 'B', 'C', 'D', 'E'], answer: 4, answerKnown: true, explanation: 'Đáp án E'},
        {id: 'ta1', v: 1, type: 'mcq', choiceGroup: 'Tự chọn A', topic: 'KHMT', level: 1, points: 5.0, stem: 'Câu nhánh A?', options: ['A', 'B', 'C', 'D'], answer: 1, answerKnown: true, explanation: 'GA'},
        {id: 'tb1', v: 1, type: 'mcq', choiceGroup: 'Tự chọn B', topic: 'THUD', level: 1, points: 5.0, stem: 'Câu nhánh B?', options: ['A', 'B', 'C', 'D'], answer: 2, answerKnown: true, explanation: 'GB'},
      ],
      docs: [],
      matrix: [
        {topic: 'Mạng máy tính', type: 'mcq', targets: [1, 1, 1, 0], pointsByLevel: [0.2, 0.4, 0.6, null]},
        {topic: 'KHMT', type: 'mcq', choiceGroup: 'Tự chọn A', targets: [0, 1, 0, 0], points: 5.0},
        {topic: 'THUD', type: 'mcq', choiceGroup: 'Tự chọn B', targets: [0, 1, 0, 0], points: 5.0},
      ],
      undo: [],
      redo: [],
      history: [],
      appliedPrefs: [],
      chat: [],
      quote: {text: '', versions: [], chosen: ''},
    };
    const kvBeforeTin = await (await fetch(`${baseUrl}/api/kv?key=state`)).json();
    await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl, 'If-Match': String(kvBeforeTin.revision)},
      body: JSON.stringify({
        key: 'state',
        value: {...kvBeforeTin.value, current: tin2TrackExam.id, exams: [...kvBeforeTin.value.exams, tin2TrackExam]},
      }),
    });
    await page.reload({waitUntil: 'networkidle'});
    await page.locator('.paper').waitFor();

    const wsSummary = await page.locator('.document-summary').textContent();
    assert.match(wsSummary || '', /15,00|Phần chung \+ max\/hướng/, `Bàn soạn phải tính theo hiệu lực Phần chung + max/hướng: ${wsSummary}`);

    // Test API /api/save-export với 2 hướng choiceGroup + 5 phương án đáp án E (KHÔNG cần allowDraft)
    const twoTrackClean = {
      id: 'uv64-tin-clean-10',
      title: 'Đề Tin học 12 hai hướng chuẩn 10đ',
      subject: 'Tin học',
      grade: '12',
      minutes: 45,
      questions: [
        {id: 'c1', type: 'mcq', topic: 'Mạng', level: 0, points: 5.0, stem: 'Câu chung 5 phương án?', options: ['A1', 'B1', 'C1', 'D1', 'E1'], answer: 4, answerKnown: true, explanation: 'Chọn E'},
        {id: 'a1', type: 'mcq', choiceGroup: 'Tự chọn A', topic: 'KHMT', level: 1, points: 5.0, stem: 'Câu KHMT?', options: ['A', 'B', 'C', 'D'], answer: 0, answerKnown: true, explanation: 'A'},
        {id: 'b1', type: 'mcq', choiceGroup: 'Tự chọn B', topic: 'THUD', level: 1, points: 5.0, stem: 'Câu THUD?', options: ['A', 'B', 'C', 'D'], answer: 1, answerKnown: true, explanation: 'B'},
      ],
    };
    for (const fmt of ['docx', 'html', 'pdf']) {
      const expRes = await fetch(`${baseUrl}/api/save-export`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', Origin: baseUrl},
        body: JSON.stringify({type: 'exam', exam: twoTrackClean, teacher: true, format: fmt}),
      });
      assert.equal(expRes.status, 200, `Export ${fmt} 2 hướng + đáp án E không allowDraft phải trả 200`);
      const expJson = await expRes.json();
      const expBytes = Buffer.from(await (await fetch(`${baseUrl}${expJson.url}`)).arrayBuffer());
      const content = fmt === 'docx' ? await docxText(expBytes) : fmt === 'pdf' ? await pdfText(expBytes) : expBytes.toString('utf8');
      assert.ok(content.includes('PHẦN CHUNG') && content.includes('PHẦN RIÊNG'), `${fmt} thiếu PHẦN CHUNG/PHẦN RIÊNG`);
      assert.ok(content.includes('Thí sinh chỉ chọn làm MỘT trong các hướng sau'), `${fmt} thiếu hướng dẫn chọn 1 hướng`);
      assert.ok(content.includes('Hướng 1: Tự chọn A') && content.includes('Hướng 2: Tự chọn B'), `${fmt} thiếu tiêu đề Hướng 1/2`);
      assert.ok(content.includes('E.') && content.includes('E1') && content.includes('Đáp án E'), `${fmt} thiếu phương án/đáp án E`);
    }

    // Kiểm tra Ma trận: Rebalance giữ pointsByLevel + Ma trận ngược đếm Có 1 mỗi dòng + Lưu mẫu 0.40/9.60 trả 201
    await page.locator('.menubar [data-menu="view"]').click();
    await page.locator('.document-menu [data-action="matrix"]').click();
    await page.locator('#dialog[open] #matrix-form').waitFor();
    await page.locator('[data-action="matrix-rebalance"]').click();
    await page.waitForTimeout(150);
    const lvlPtsAfterBal = await page.locator('#matrix-rows tr[data-matrix-row]').first().locator('[name="matrix-level-points"]').evaluateAll((els) =>
      els.map((el) => (el.value === '' ? null : Number(el.value))),
    );
    assert.ok(lvlPtsAfterBal[0] > 0 && lvlPtsAfterBal[1] > lvlPtsAfterBal[0] && lvlPtsAfterBal[2] > lvlPtsAfterBal[1], `Tỷ trọng pointsByLevel bị san phẳng: ${JSON.stringify(lvlPtsAfterBal)}`);

    // Ma trận ngược cho tin2TrackExam (có Mạng máy tính 0,4đ và 9,6đ -> đếm Có 1 mỗi dòng!)
    await page.locator('[data-action="reverse-matrix"]').click();
    await page.waitForFunction(() => document.querySelectorAll('#matrix-rows tr[data-matrix-row]').length >= 4);
    const revRowActuals = await page.locator('#matrix-rows tr[data-matrix-row]').evaluateAll((trs) =>
      trs.map((tr) => ({
        topic: tr.querySelector('.topic')?.value || '',
        group: tr.dataset.choiceGroup || '',
        actuals: [...tr.querySelectorAll('.matrix-cell-actual')].map((n) => n.textContent.trim()),
      })),
    );
    const mangRows = revRowActuals.filter((r) => r.topic.includes('Mạng máy tính'));
    assert.equal(mangRows.length, 2, 'Ma trận ngược phải tách 2 dòng 0,4đ và 9,6đ');
    assert.equal(mangRows[0].actuals[0], 'Có 1', `Dòng 0,4đ phải đếm Có 1, thực tế: ${JSON.stringify(mangRows)}`);
    assert.equal(mangRows[1].actuals[0], 'Có 1', `Dòng 9,6đ phải đếm Có 1, thực tế: ${JSON.stringify(mangRows)}`);

    // Lưu mẫu ma trận điểm lẻ 0,40 / 9,60 trả 201
    const decTplRes = await fetch(`${baseUrl}/api/matrix-templates`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({
        name: 'Mẫu 0.40 + 9.60 UV64',
        subject: 'Toán',
        grade: '12',
        rows: [
          {topic: 'Mạng (0,4đ)', type: 'mcq', targets: [1, 0, 0, 0], points: 0.4},
          {topic: 'Mạng (9,6đ)', type: 'mcq', targets: [0, 1, 0, 0], points: 9.6},
        ],
      }),
    });
    assert.equal(decTplRes.status, 201, 'Lưu mẫu ma trận 0.40/9.60 phải trả 201');
    await shot('uv64-matrix-two-track-reverse.png');
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});
    if (await page.locator('#dialog[open]').count()) {
      const closeBtn = page.locator('#dialog[open] [data-action="close"]').first();
      if (await closeBtn.isVisible()) await closeBtn.click();
      else await page.keyboard.press('Escape');
      await page.locator('#dialog').waitFor({state: 'hidden'});
    }
    checks.exportsMatrix = {lvlPtsAfterBal, mangRows, matrixTemplateStatus: decTplRes.status};

    // =========================================================================
    // 5. Phòng thi / BTVN: 0,75 <-> 3/4 & 6/8, 2 hướng 10/10, không báo giả mất mạng,
    //    Điểm tạm + markingGuidance + XLSX BaiLamChiTiet + Audio 1 lượt trọn vẹn
    // =========================================================================
    const roomAudId = 'uv64-room-aud';
    await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({key: `file:${roomAudId}`, value: wavUri}),
    });
    const roomExam = {
      id: 'uv64-room-exam-full',
      title: 'Phòng thi Tin học & Vật lí UV64',
      subject: 'Tin học',
      grade: '12',
      minutes: 45,
      revision: 1,
      updated: Date.now(),
      markingGuidance: 'Trừ 0,25 điểm nếu thiếu đơn vị ở kết quả cuối.',
      audio: {fileId: roomAudId, filename: 'listen64.wav', title: 'Nghe UV64', maxPlays: 1, mimeType: 'audio/wav'},
      questions: [
        {id: 'rq-short', v: 1, type: 'short', level: 0, options: [], stem: 'Viết 0,75 dưới dạng phân số hoặc thập phân:', answerText: '0,75', answer: '', answerKnown: true, points: 5.0, explanation: '3/4 = 0,75'},
        {id: 'rq-a', v: 1, type: 'mcq', level: 0, choiceGroup: 'Tự chọn A', stem: 'Nhánh A: chọn B', options: ['A', 'B', 'C', 'D'], answer: 1, answerKnown: true, points: 5.0, explanation: 'Chọn B'},
        {id: 'rq-b', v: 1, type: 'essay', level: 0, choiceGroup: 'Tự chọn B', options: [], answer: null, stem: 'Nhánh B: tự luận viết lời giải', rubric: [{text: 'Đủ đơn vị', points: 5.0}], points: 5.0, explanation: 'Lời giải chuẩn'},
      ],
      docs: [],
      data: [],
      matrix: [{topic: 'Tổng hợp', targets: [1, 1, 0, 0]}],
      undo: [],
      redo: [],
      history: [],
      appliedPrefs: [],
      chat: [],
      quote: {text: '', versions: [], chosen: ''},
    };
    const kvBeforeRoom = await (await fetch(`${baseUrl}/api/kv?key=state`)).json();
    await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl, 'If-Match': String(kvBeforeRoom.revision)},
      body: JSON.stringify({
        key: 'state',
        value: {...kvBeforeRoom.value, current: roomExam.id, exams: [...kvBeforeRoom.value.exams, roomExam]},
      }),
    });
    const createdRoomRes = await fetch(`${baseUrl}/api/rooms`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({examId: roomExam.id, title: roomExam.title, mode: 'exam', status: 'open', resultPolicy: 'full_explanation'}),
    });
    assert.equal(createdRoomRes.status, 201);
    const createdRoomJson = await createdRoomRes.json();
    const roomObj = createdRoomJson.room || createdRoomJson;

    // HS1: Audio 1 lượt phát được trọn vẹn trước khi khóa + trả lời 3/4 + Tự chọn A (bỏ trống B) -> 10/10, không báo giả mất mạng
    const sPage1 = await browser.newPage({viewport: {width: 420, height: 844}});
    sPage1.setDefaultTimeout(15000);
    sPage1.on('pageerror', (e) => pageErrors.push(`s1:${e.message}`));
    await sPage1.goto(`${baseUrl}/phong-thi/${roomObj.roomCode}`, {waitUntil: 'networkidle'});
    await sPage1.locator('#sr-join-form input[name="studentName"]').fill('HS Một UV64');
    await sPage1.locator('#sr-join-form input[name="studentCode"]').fill('S01');
    await sPage1.locator('#sr-join-form button[type="submit"]').click();
    await sPage1.locator('[data-choice-guide="1"]').waitFor();
    await sPage1.locator('[data-sr-action="play-audio"]').click();
    await sPage1.waitForFunction(() => {
      const btn = document.querySelector('[data-sr-action="play-audio"]');
      return btn && btn.disabled && document.body.innerText.includes('0 / 1');
    });
    const audioDuringPlay = await sPage1.evaluate(() => {
      const aud = document.querySelector('audio.sr-audio-el');
      return {exists: Boolean(aud), hasControls: Boolean(aud?.hasAttribute('controls')), src: aud?.getAttribute('src') || ''};
    });
    assert.equal(audioDuringPlay.exists, true, 'Lượt nghe 1 khi playsRemaining=0 phải giữ <audio controls> cho lượt hiện tại');
    assert.equal(audioDuringPlay.hasControls, true);
    // Đợi audio 0.25s phát xong (hoặc kiểm tra khóa sau khi ended)
    await sPage1.waitForFunction(() => !document.querySelector('audio.sr-audio-el'), {timeout: 5000});
    const audioAfterEnd = await sPage1.evaluate(() => ({
      exists: Boolean(document.querySelector('audio.sr-audio-el')),
      playBtnDisabled: Boolean(document.querySelector('[data-sr-action="play-audio"]')?.disabled),
    }));
    assert.equal(audioAfterEnd.exists, false, 'Sau khi phát xong ended, <audio> phải bị khóa/gỡ');
    assert.equal(audioAfterEnd.playBtnDisabled, true);

    await sPage1.locator('#sr-short-rq-short').waitFor();
    if (await sPage1.locator('[data-sr-action="view-mode"][data-mode="all"]').isVisible()) {
      await sPage1.locator('[data-sr-action="view-mode"][data-mode="all"]').click();
    }
    await sPage1.locator('#sr-short-rq-short').fill('3/4');
    await sPage1.locator('[data-sr-action="pick-mcq"][data-qid="rq-a"][data-idx="1"]').click();
    await sPage1.waitForTimeout(200);
    await sPage1.locator('[data-sr-action="ask-submit"]').first().click();
    await sPage1.locator('[data-sr-action="confirm-submit"]').click();
    await sPage1.locator('.sr-score-big').waitFor();
    const s1ResultText = await sPage1.locator('#student-room-app').textContent();
    assert.match(s1ResultText || '', /10\s*\/\s*10/, `Phải đạt 10/10 khi nhập 3/4 + Tự chọn A: ${s1ResultText}`);
    assert.equal(await sPage1.locator('[data-sync-status="ok"]').count(), 1, 'Không được báo giả mất mạng khi bỏ trống nhánh B');
    await sPage1.close();

    // HS2: Nhập 6/8 + làm câu tự luận Tự chọn B -> hiện ĐIỂM TẠM (CHỜ CHẤM TỰ LUẬN)
    const sPage2 = await browser.newPage({viewport: {width: 420, height: 844}});
    sPage2.setDefaultTimeout(15000);
    sPage2.on('pageerror', (e) => pageErrors.push(`s2:${e.message}`));
    await sPage2.goto(`${baseUrl}/phong-thi/${roomObj.roomCode}`, {waitUntil: 'networkidle'});
    await sPage2.locator('#sr-join-form input[name="studentName"]').fill('HS Hai Tự Luận');
    await sPage2.locator('#sr-join-form input[name="studentCode"]').fill('S02');
    await sPage2.locator('#sr-join-form button[type="submit"]').click();
    await sPage2.locator('#sr-short-rq-short').waitFor();
    if (await sPage2.locator('[data-sr-action="view-mode"][data-mode="all"]').isVisible()) {
      await sPage2.locator('[data-sr-action="view-mode"][data-mode="all"]').click();
    }
    await sPage2.locator('#sr-short-rq-short').fill('6/8');
    await sPage2.locator('#sr-essay-rq-b').fill('Kết quả bằng 9,8 m/s2');
    await sPage2.waitForTimeout(200);
    await sPage2.locator('[data-sr-action="ask-submit"]').first().click();
    await sPage2.locator('[data-sr-action="confirm-submit"]').click();
    await sPage2.locator('.sr-score-big').waitFor();
    const s2ResultText = await sPage2.locator('#student-room-app').textContent();
    assert.match(s2ResultText || '', /ĐIỂM TẠM \(CHỜ CHẤM TỰ LUẬN\)/, `Thiếu nhãn điểm tạm: ${s2ResultText}`);
    assert.match(s2ResultText || '', /5\s*\/\s*10/, `Short 6/8 khớp 0,75 phải được 5/10 tạm: ${s2ResultText}`);
    await sPage2.screenshot({path: path.join(EVIDENCE_DIR, 'uv64-room-student-audio-provisional.png')});
    await sPage2.close();

    // GV mở Phòng thi -> tab Chấm tự luận -> thấy markingGuidance + tải XLSX có sheet BaiLamChiTiet
    await page.reload({waitUntil: 'networkidle'});
    await page.locator('.paper').waitFor();
    await page.locator('.design-rail [data-action="exam-rooms"]').click();
    await page.locator('#dialog[open] .er-tabs').waitFor();
    await page.locator('#dialog [data-er-action="switch-tab"][data-tab="grading"]').click();
    await page.locator('#dialog [data-marking-guidance="1"]').waitFor();
    const guidanceText = await page.locator('#dialog [data-marking-guidance="1"]').textContent();
    assert.match(guidanceText || '', /Trừ 0,25 điểm nếu thiếu đơn vị/);
    await shot('uv64-room-teacher-grading-guidance.png');
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});

    const xlsxRes = await fetch(`${baseUrl}/api/rooms/${roomObj.id}/export.xlsx`);
    assert.equal(xlsxRes.status, 200);
    const xlsxZip = await JSZip.loadAsync(Buffer.from(await xlsxRes.arrayBuffer()));
    const wbXml = await xlsxZip.file('xl/workbook.xml').async('string');
    const sheet3Xml = await xlsxZip.file('xl/worksheets/sheet3.xml').async('string');
    const sharedStringsXml = xlsxZip.file('xl/sharedStrings.xml') ? await xlsxZip.file('xl/sharedStrings.xml').async('string') : '';
    const detailPoolXml = `${sheet3Xml}\n${sharedStringsXml}`;
    assert.ok(wbXml.includes('BaiLamChiTiet'), 'XLSX thiếu sheet BaiLamChiTiet');
    assert.ok(
      detailPoolXml.includes('3/4') && detailPoolXml.includes('6/8') && detailPoolXml.includes('9,8 m/s2'),
      'BaiLamChiTiet thiếu bài làm gốc',
    );
    checks.examRooms = {audioDuringPlay, audioAfterEnd, hs1Score10: true, hs2Provisional: true, guidanceVisible: true, xlsxDetailSheet: true};

    // =========================================================================
    // 6. Nhắc lịch PATCH 503 giữ nguyên thẻ & báo lỗi + Mở đề gắn kèm
    // =========================================================================
    const remCreated = await (
      await fetch(`${baseUrl}/api/reminders`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', Origin: baseUrl},
        body: JSON.stringify({
          title: 'Kiểm tra lại câu đáp án E UV64',
          kind: 'review',
          targetType: 'exam',
          targetId: roomExam.id,
          remindAt: Date.now() + 3600_000,
        }),
      })
    ).json();
    const remId = remCreated.reminder.id;

    await page.locator('.design-rail [data-action="design-home"]').click();
    await page.locator('#home-view').waitFor();
    await page.locator('.proactive-card [data-action="proactive-done-reminder"]').first().waitFor();

    allowExpected503 = true;
    await page.route(`**/api/reminders/${remId}`, async (route) => {
      await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'Lỗi 503 thử nghiệm'})});
    });
    await page.locator(`.proactive-card [data-action="proactive-done-reminder"][data-id="${remId}"]`).click();
    await page.waitForTimeout(300);
    assert.equal(
      await page.locator(`.proactive-card [data-action="proactive-done-reminder"][data-id="${remId}"]`).count(),
      1,
      'Khi PATCH 503, thẻ nhắc lịch PHẢI được giữ nguyên!',
    );
    const toast503 = await page.locator('#toast').textContent();
    assert.match(toast503 || '', /503|Không thể cập nhật/i);
    await shot('uv64-proactive-reminder-503.png');
    await page.unroute(`**/api/reminders/${remId}`);
    allowExpected503 = false;

    await page.locator(`.proactive-card [data-action="home-open-exam"][data-id="${roomExam.id}"]`).click();
    await page.locator('.paper').waitFor();
    assert.match((await page.locator('.header-title').inputValue()) || '', /Phòng thi Tin học/);
    checks.proactiveReminder503 = {cardKeptOn503: true, toast503: toast503?.trim(), openedAttachedExam: true};

    // =========================================================================
    // 7. SGK KNTT (Toán 9 Ch.VIII, Toán 12 Bayes/vectơ/thống kê/mặt cầu, Toán 5)
    //    + KaTeX .katex + Trích dẫn v1->v2 + PPTX Mở tệp gốc
    // =========================================================================
    await page.locator('[data-action="lesson-sources"]:visible').first().click();
    await page.locator('#dialog[open] #lesson-picker').waitFor();

    // Toán 9 Chương VIII Xác suất
    await page.locator('#lesson-picker select[name="grade"]').selectOption('9');
    await page.locator('#lesson-picker select[name="subject"]').selectOption('Toán');
    await page.locator('#lesson-picker [data-sgk-volume="Tập hai"]').click();
    await page.waitForTimeout(150);
    assert.ok((await page.locator('#lesson-picker [data-lesson-list]').textContent())?.includes('Chương VIII. Xác suất'));

    // Toán 12 Bayes + KaTeX
    await page.locator('#lesson-picker select[name="grade"]').selectOption('12');
    await page.locator('#lesson-picker input[name="query"]').fill('Bayes');
    await page.waitForTimeout(150);
    const bayesRow = page.locator('#lesson-picker .sgk-lesson-row', {hasText: 'Bài 19: Công thức xác suất toàn phần và công thức Bayes'}).first();
    await bayesRow.waitFor();
    await bayesRow.click();
    await page.waitForTimeout(150);
    const kntt12Check = await page.evaluate(() => {
      const detail = document.querySelector('[data-sgk-detail]');
      return {
        katexCount: detail?.querySelectorAll('.katex').length || 0,
        text: detail?.innerText || '',
      };
    });
    assert.ok(kntt12Check.katexCount >= 1, 'Xem trước SGK Toán 12 Bayes phải render .katex thay vì LaTeX thô');
    assert.match(kntt12Check.text, /NXB Giáo dục Việt Nam/);
    assert.match(kntt12Check.text, /GDPT 2018/);
    await shot('uv64-sgk-kntt-katex.png');

    await page.locator('#lesson-picker [data-sgk-volume=""]').click();
    await page.waitForTimeout(100);
    for (const kw of ['vectơ', 'thống kê', 'mặt cầu', 'xác suất có điều kiện']) {
      await page.locator('#lesson-picker input[name="query"]').fill(kw);
      await page.waitForTimeout(80);
      assert.ok((await page.locator('#lesson-picker .sgk-lesson-row').count()) >= 1, `Toán 12 tìm "${kw}" bị rỗng`);
    }

    // Toán 5 Bài 58-60 & diện tích
    await page.locator('#lesson-picker select[name="grade"]').selectOption('5');
    await page.locator('#lesson-picker [data-sgk-volume=""]').click();
    await page.locator('#lesson-picker input[name="query"]').fill('Vận tốc');
    await page.waitForTimeout(100);
    assert.ok((await page.locator('#lesson-picker [data-lesson-list]').textContent())?.includes('Bài 59'));

    // 390px dòng báo rỗng không bị cắt
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('#lesson-picker input[name="query"]').fill('zzzzkhongcobai64');
    await page.waitForTimeout(100);
    const empty390 = await page.evaluate(() => {
      const el = document.querySelector('.sgk-empty-state');
      const r = el?.getBoundingClientRect();
      return {exists: Boolean(el), width: r?.width || 0, overflows: el ? el.scrollWidth > el.clientWidth + 2 : true};
    });
    assert.equal(empty390.exists, true);
    assert.equal(empty390.overflows, false);

    await page.setViewportSize({width: 1440, height: 900});
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});

    // PPTX Mở tệp gốc + v1 -> v2 version_changed
    const pptxBuf = await buildMinimalPptxBuffer('Slide 1: Nội dung gốc v1 để trích dẫn.');
    const pptxUri = `data:application/vnd.openxmlformats-officedocument.presentationml.presentation;base64,${pptxBuf.toString('base64')}`;
    await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl},
      body: JSON.stringify({key: 'file:pptx-uv64-file', value: pptxUri}),
    });
    const pptxExam = {
      id: 'uv64-pptx-cit',
      title: 'Đề PPTX & Trích dẫn v1->v2',
      subject: 'Ngữ văn',
      grade: '8',
      minutes: 45,
      revision: 1,
      updated: Date.now(),
      docs: [
        {
          id: 'pptx-doc-64',
          fileId: 'pptx-uv64-file',
          name: 'BaiGiang_UV64.pptx',
          kind: 'slides',
          version: 1,
          text: 'Slide 1: Nội dung gốc v1 để trích dẫn.',
          pages: [{number: 1, text: 'Slide 1: Nội dung gốc v1 để trích dẫn.'}],
        },
      ],
      questions: [
        {
          id: 'pq-1',
          v: 1,
          type: 'mcq',
          topic: 'Đọc hiểu',
          level: 0,
          points: 10,
          stem: 'Câu trích từ slide v1?',
          options: ['A', 'B', 'C', 'D'],
          answer: 0,
          answerKnown: true,
          source: {docId: 'pptx-doc-64', page: 1, location: 'Slide 1', quote: 'Nội dung gốc v1'},
          explanation: 'G',
        },
      ],
      matrix: [{topic: 'Đọc hiểu', targets: [1, 0, 0, 0]}],
      undo: [],
      redo: [],
      history: [],
      appliedPrefs: [],
      chat: [],
      quote: {text: '', versions: [], chosen: ''},
    };
    const kvBeforePptx = await (await fetch(`${baseUrl}/api/kv?key=state`)).json();
    await fetch(`${baseUrl}/api/kv`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', Origin: baseUrl, 'If-Match': String(kvBeforePptx.revision)},
      body: JSON.stringify({
        key: 'state',
        value: {...kvBeforePptx.value, current: pptxExam.id, exams: [...kvBeforePptx.value.exams, pptxExam]},
      }),
    });
    await page.reload({waitUntil: 'networkidle'});
    await page.locator('.paper').waitFor();

    // Mở nguồn PPTX -> thấy nút "Mở tệp gốc" -> kiểm URL trả 200 -> sửa văn bản -> version=2
    await page.locator('[data-action="source"][data-id="pq-1"]').click();
    await page.locator('#dialog[open] #source-text-form').waitFor();
    const pptxHref = await page.locator('#dialog a', {hasText: 'Mở tệp gốc'}).getAttribute('href');
    assert.ok(pptxHref && pptxHref.includes('/api/source-file/pptx-uv64-file'), `Thiếu link Mở tệp gốc cho PPTX: ${pptxHref}`);
    const pptxFetch = await fetch(`${baseUrl}${pptxHref}`);
    assert.equal(pptxFetch.status, 200);

    await page.locator('#source-text-form textarea[name="text"]').fill('Slide 1: Nội dung đã sửa thành v2.');
    await page.locator('#source-text-form button[type="submit"]').click();
    await page.waitForFunction(() => document.querySelector('#source-text-form')?.dataset.version === '2');
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});

    // Mở Rà soát câu (qua Kiểm tra bằng phép tính -> Xem căn cứ) -> thấy status version_changed
    await page.locator('.menubar [data-menu="tools"]').click();
    await page.locator('.document-menu [data-action="check-all"]').click();
    await page.locator('#dialog[open] [data-action="review"][data-id="pq-1"]').waitFor();
    await page.locator('#dialog[open] [data-action="review"][data-id="pq-1"]').click();
    await page.locator('#dialog[open] [data-citation-status="version_changed"]').waitFor();
    await shot('uv64-pptx-citation-v2.png');
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});
    checks.sgkAndPptx = {katexCount: kntt12Check.katexCount, pptxHref, versionChangedVisible: true};

    // =========================================================================
    // 8. Desktop & Mobile 390x844 / 390x560:
    //    Thêm câu theo dạng ▾, Ctrl+Alt+C 3 dòng, Con trỏ chèn công thức, Ma trận 390px, Chat 390x560
    // =========================================================================
    // 8a. Bấm trực tiếp "Thêm câu theo dạng ▾" (không bị tự đóng!)
    await page.locator('[data-action="studio-question"]').click();
    await page.waitForTimeout(200);
    await page.locator('.studio-question-menu [data-action="studio-add-question"][data-type="short"]').waitFor();
    await page.locator('.studio-question-menu [data-action="studio-add-question"][data-type="short"]').click();
    await page.waitForFunction(() => document.querySelectorAll('.paper .question').length === 2);

    // 8b. Khối mã Ctrl+Alt+C giữ đủ 3 dòng
    const secondStem = page.locator('.paper .question').nth(1).locator('.stem-editor .tiptap');
    await secondStem.click();
    await page.keyboard.press('Control+Alt+c');
    await page.keyboard.type('dong 1');
    await page.keyboard.press('Enter');
    await page.keyboard.type('dong 2');
    await page.keyboard.press('Enter');
    await page.keyboard.type('dong 3');
    await page.locator('.header-title').click(); // trigger blur + flush
    await page.waitForTimeout(700);
    const kvAfterCode = await (await fetch(`${baseUrl}/api/kv?key=state`)).json();
    const curAfterCode = kvAfterCode.value.exams.find((x) => x.id === pptxExam.id);
    const savedStemCode = curAfterCode.questions[1]?.stem || '';
    assert.ok(
      savedStemCode.includes('dong 1') && savedStemCode.includes('dong 2') && savedStemCode.includes('dong 3'),
      `Khối mã Ctrl+Alt+C rơi dòng: ${JSON.stringify(savedStemCode)}`,
    );

    // 8c. Chèn công thức đúng tại vị trí con trỏ giữa câu (không nhảy về đầu câu)
    await page.locator('.outline-item[data-id="pq-1"]').click();
    const firstStem = page.locator('#q-pq-1 .stem-editor .tiptap');
    await firstStem.click();
    await page.keyboard.press('Control+a');
    await page.keyboard.press('Backspace');
    await page.keyboard.type('Cho ham so tren R');
    for (let i = 0; i < ' tren R'.length; i += 1) await page.keyboard.press('ArrowLeft');
    await page.locator('.editor-toolbar [data-action="formula"]').click();
    await page.locator('.composer-shell #inline-math-form').waitFor();
    await page.locator('.composer-shell #catalog-subject').selectOption('math');
    await page.locator('.composer-shell #catalog-items .catalog-item').first().click();
    await page.locator('.composer-shell #formula-display').selectOption('inline');
    await page.locator('.composer-shell .composer-advanced summary').click();
    await page.locator('.composer-shell #inline-math-input').fill('x^{2}');
    await page.locator('.composer-shell #composer-save').click();
    await page.locator('.composer-shell').waitFor({state: 'hidden'});
    await page.locator('.header-title').click();
    await page.waitForTimeout(700);
    const kvAfterFormula = await (await fetch(`${baseUrl}/api/kv?key=state`)).json();
    const savedFormulaStem = kvAfterFormula.value.exams.find((x) => x.id === pptxExam.id)?.questions[0]?.stem || '';
    assert.match(
      savedFormulaStem,
      /Cho ham so\s+\$x\^\{?2\}?\$\s+tren R/,
      `Công thức phải chèn đúng giữa câu và tách khoảng trắng hợp lý, thực tế: ${JSON.stringify(savedFormulaStem)}`,
    );

    // 8d. Mobile 390x844: ma trận cuộn gọn + thước ẩn + nút ⋮
    await page.setViewportSize({width: 390, height: 844});
    await page.waitForTimeout(150);
    const mobileBarCheck = await page.evaluate(() => {
      const rulerDisp = getComputedStyle(document.querySelector('.document-bar .ruler')).display;
      const menuBtn = document.querySelector('.editor-toolbar [data-action="menu"][data-menu="insert"]');
      const zoomEl = document.querySelector('.editor-toolbar #zoom');
      const mRect = menuBtn?.getBoundingClientRect();
      const zRect = zoomEl?.getBoundingClientRect();
      const overlapsZoom =
        mRect && zRect
          ? Math.min(mRect.right, zRect.right) - Math.max(mRect.left, zRect.left) > 2 &&
            Math.min(mRect.bottom, zRect.bottom) - Math.max(mRect.top, zRect.top) > 2
          : false;
      return {
        rulerDisp,
        menuRight: mRect?.right || 0,
        overlapsZoom,
        overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
      };
    });
    assert.equal(mobileBarCheck.rulerDisp, 'none', 'Thước phải ẩn trên 390px');
    assert.ok(mobileBarCheck.menuRight <= 391, 'Nút ⋮ bị cắt ngoài rìa phải 390px');
    assert.equal(mobileBarCheck.overlapsZoom, false, `Nút ⋮ không được đè lên #zoom trên 390x844 (menuRight=${mobileBarCheck.menuRight})`);
    await shot('uv64-mobile-390-toolbar.png');

    await page.locator('.menubar [data-menu="view"]').click();
    await page.locator('.document-menu [data-action="matrix"]').click();
    await page.locator('#dialog[open] .matrix-table-scroll').waitFor();
    await page.waitForTimeout(150);
    const matrixMobileCheck = await page.evaluate(() => {
      const dlg = document.querySelector('#dialog').getBoundingClientRect();
      const scr = document.querySelector('#dialog .matrix-table-scroll').getBoundingClientRect();
      return {
        dlgWidth: Math.round(dlg.width),
        scrWidth: Math.round(scr.width),
        tableScrollable: document.querySelector('#dialog .matrix-table-scroll').scrollWidth >= document.querySelector('#dialog .matrix-table-scroll').clientWidth,
      };
    });
    assert.ok(matrixMobileCheck.dlgWidth <= 390, `Modal ma trận tràn 390px: ${matrixMobileCheck.dlgWidth}`);
    await shot('uv64-mobile-390-matrix.png');
    await page.locator('#dialog [data-action="close"]').first().click();
    await page.locator('#dialog').waitFor({state: 'hidden'});

    // 8d. Chat 390x844 -> 390x560 giữ Chat mở và #chat-send nằm trong viewport
    await page.locator('.ux-view-tabs [data-action="toggle-ai"]').click();
    await page.locator('aside.assistant.open').waitFor();
    await page.setViewportSize({width: 390, height: 560});
    await page.waitForTimeout(200);
    const chat560Check = await page.evaluate(() => {
      const ast = document.querySelector('aside.assistant');
      const body = document.querySelector('aside.assistant .assistant-body');
      const send = document.querySelector('#chat-send');
      const form = document.querySelector('#chat-form');
      return {
        open: ast?.classList.contains('open'),
        bodyH: Math.round(body?.getBoundingClientRect().height || 0),
        sendBottom: Math.round(send?.getBoundingClientRect().bottom || 9999),
        formBottom: Math.round(form?.getBoundingClientRect().bottom || 9999),
      };
    });
    assert.equal(chat560Check.open, true, 'Resize 390x844 -> 390x560 KHÔNG được đóng Chat');
    assert.ok(chat560Check.bodyH >= 96, `Vùng tin nhắn quá bé: ${chat560Check.bodyH}px`);
    assert.ok(chat560Check.sendBottom <= 560, `Nút #chat-send tụt khỏi viewport 560px: ${chat560Check.sendBottom}`);
    await shot('uv64-mobile-390x560-chat.png');

    checks.editorMobile = {
      studioQuestionMenuWorked: true,
      codeBlock3LinesSaved: true,
      cursorFormulaStem: savedFormulaStem,
      mobileBarCheck,
      matrixMobileCheck,
      chat560Check,
    };

    assert.deepEqual(consoleErrors, [], `Console errors: ${consoleErrors.join('; ')}`);
    assert.deepEqual(pageErrors, [], `Page errors: ${pageErrors.join('; ')}`);

    console.log(
      JSON.stringify(
        {
          ok: findings.length === 0,
          baseUrl,
          evidenceDir: EVIDENCE_DIR,
          checks,
          findings,
        },
        null,
        2,
      ),
    );
    if (findings.length > 0) {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
    await stopServer(server.proc);
    fs.rmSync(tempRoot, {recursive: true, force: true});
  }
}

await main();
