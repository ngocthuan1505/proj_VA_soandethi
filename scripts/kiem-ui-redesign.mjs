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
const PYTHON_EXE = path.join(ROOT, 'backend', '.venv', 'Scripts', 'python.exe');
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);
const SCREENSHOT_DIR = process.env.QA_SCREENSHOT_DIR
  ? path.resolve(process.env.QA_SCREENSHOT_DIR)
  : fs.mkdtempSync(path.join(os.tmpdir(), 'kiem-ui-redesign-shots-'));

const SAMPLE_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAI0lEQVR4nGM8YWTEQApgIkk1w6gG4gATkergYFQDMYDkUAIAyTsBTI2XZDAAAAAASUVORK5CYII=';
const SAMPLE_PNG_DATA_URI = `data:image/png;base64,${SAMPLE_PNG_BASE64}`;

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

async function startIsolatedServer(port, dataDir) {
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
        NO_PROXY: '127.0.0.1,localhost',
        PYTHONIOENCODING: 'utf-8',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
  let logs = '';
  proc.stdout?.on('data', (chunk) => {
    logs += chunk.toString();
  });
  proc.stderr?.on('data', (chunk) => {
    logs += chunk.toString();
  });

  const baseUrl = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 25000;
  while (Date.now() < deadline) {
    if (proc.exitCode !== null) {
      throw new Error(`Uvicorn thoát sớm (${proc.exitCode}):\n${logs}`);
    }
    try {
      const res = await fetch(`${baseUrl}/api/status`);
      if (res.ok) {
        const status = await res.json();
        if (status?.matrixPython) return {proc, baseUrl, getLogs: () => logs};
      }
    } catch {
      // retry until healthy
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  try {
    proc.kill('SIGKILL');
  } catch {
    // ignore
  }
  throw new Error(`Timeout chờ /api/status trên ${baseUrl}:\n${logs}`);
}

async function stopServer(proc) {
  if (!proc || proc.exitCode !== null) return;
  proc.kill();
  await new Promise((resolve) => {
    const timer = setTimeout(() => {
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
      clearTimeout(timer);
      resolve();
    });
  });
}

async function inspectViewportGeometry(page, label) {
  return await page.evaluate((vpLabel) => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const scrollW = document.documentElement.scrollWidth;
    const overflowX = scrollW > vw + 1;
    const bodyText = document.body?.innerText || '';
    const hasObjectObject = /\[object\s+Object\]/i.test(bodyText);

    const visibleRect = (el) => {
      if (!el) return null;
      const st = getComputedStyle(el);
      if (st.display === 'none' || st.visibility === 'hidden' || Number(st.opacity) === 0) return null;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return null;
      return r;
    };

    const rectsOverlap = (a, b, tol = 2) => {
      const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      return ox > tol && oy > tol;
    };

    const containers = [
      {name: 'workflow-strip', sel: '.workflow-strip button, .workflow-strip .wf-step, .workflow-strip .wf-mode-pill'},
      {name: 'editor-toolbar', sel: '.editor-toolbar button, .editor-toolbar select'},
      {name: 'design-rail', sel: '.design-rail button, .design-rail [data-action]'},
      {name: 'chat-compose', sel: '.chat-compose button, .chat-compose textarea, .chat-compose .source-chip, .chat-compose .source-detach'},
    ];

    const overlaps = [];
    const clipped = [];
    const obscured = [];
    const visualDefects = [];

    // Check assistant-body top clipping (e.g. flex justify-content:center pushing content above scrollTop=0)
    const assistantBody = document.querySelector('.assistant-body');
    const welcomeHead = document.querySelector('.assistant-body .assistant-welcome h2, .assistant-body .assistant-context-head');
    if (assistantBody && visibleRect(assistantBody) && welcomeHead && visibleRect(welcomeHead)) {
      const abRect = assistantBody.getBoundingClientRect();
      const whRect = welcomeHead.getBoundingClientRect();
      if (whRect.top < abRect.top - 2) {
        visualDefects.push({
          viewport: vpLabel,
          area: 'assistant-body-top-clip',
          detail: `Tiêu đề trợ lý bị cắt mất phần trên (${Math.round(whRect.top)} < ${Math.round(abRect.top)})`,
          bodyJustify: getComputedStyle(assistantBody).justifyContent,
        });
      }
    }

    // Check suggestion-card <b> and <small> colliding on the same line without spacing
    for (const card of document.querySelectorAll('.suggestion-card')) {
      if (!visibleRect(card)) continue;
      const bEl = card.querySelector('b');
      const smallEl = card.querySelector('small');
      if (bEl && smallEl) {
        const bStyle = getComputedStyle(bEl);
        const sStyle = getComputedStyle(smallEl);
        const bRect = bEl.getBoundingClientRect();
        const sRect = smallEl.getBoundingClientRect();
        const sameBand = Math.min(bRect.bottom, sRect.bottom) - Math.max(bRect.top, sRect.top) > 2;
        if (sameBand && sStyle.display === 'inline') {
          visualDefects.push({
            viewport: vpLabel,
            area: 'suggestion-card-inline-small',
            detail: `<small> nằm inline dính sát vào <b>: "${(bEl.textContent + smallEl.textContent).slice(0, 70)}"`,
            bDisplay: bStyle.display,
            smallDisplay: sStyle.display,
          });
        }
      }
    }

    for (const group of containers) {
      const nodes = [...document.querySelectorAll(group.sel)]
        .map((el) => ({el, rect: visibleRect(el)}))
        .filter((item) => item.rect);

      for (let i = 0; i < nodes.length; i++) {
        const {el, rect} = nodes[i];
        const parentScroll = el.closest('.editor-toolbar, .workflow-strip, .source-chips');
        const pRect = parentScroll ? visibleRect(parentScroll) : null;
        const clipBound = pRect || {left: 0, right: vw, top: 0, bottom: vh};
        const fullyVisibleInParent =
          rect.left >= clipBound.left - 2 &&
          rect.right <= clipBound.right + 2 &&
          rect.top >= 0 &&
          rect.bottom <= vh + 2;

        if (!pRect && (rect.left < -2 || rect.right > vw + 2)) {
          clipped.push({
            viewport: vpLabel,
            group: group.name,
            text: (el.innerText || el.getAttribute('aria-label') || el.className || '').trim().slice(0, 60),
            rect: {left: Math.round(rect.left), right: Math.round(rect.right), top: Math.round(rect.top), bottom: Math.round(rect.bottom)},
            vw,
          });
        }

        if (fullyVisibleInParent && rect.bottom <= vh && rect.top >= 0 && rect.left >= 0 && rect.right <= vw) {
          const cx = Math.min(vw - 1, Math.max(1, (rect.left + rect.right) / 2));
          const cy = Math.min(vh - 1, Math.max(1, (rect.top + rect.bottom) / 2));
          const hit = document.elementFromPoint(cx, cy);
          const sameComponent = hit && (el === hit || el.contains(hit) || hit.contains(el));
          if (!sameComponent) {
            obscured.push({
              viewport: vpLabel,
              group: group.name,
              target: (el.innerText || el.getAttribute('aria-label') || el.className || '').trim().slice(0, 50),
              hitBy: hit ? `${hit.tagName.toLowerCase()}.${String(hit.className || '').split(/\s+/).slice(0, 3).join('.')}` : null,
            });
          }
        }

        for (let j = i + 1; j < nodes.length; j++) {
          const other = nodes[j];
          if (el.contains(other.el) || other.el.contains(el)) continue;
          if (rectsOverlap(rect, other.rect, 2)) {
            overlaps.push({
              viewport: vpLabel,
              group: group.name,
              a: (el.innerText || el.getAttribute('aria-label') || el.className || '').trim().slice(0, 40),
              b: (other.el.innerText || other.el.getAttribute('aria-label') || other.el.className || '').trim().slice(0, 40),
            });
          }
        }
      }
    }

    return {
      viewport: vpLabel,
      vw,
      vh,
      scrollW,
      overflowX,
      hasObjectObject,
      overlaps,
      clipped,
      obscured,
      visualDefects,
    };
  }, label);
}

async function pdfInspect(bytes) {
  const doc = await pdfjsLib.getDocument({data: new Uint8Array(bytes), verbosity: 0}).promise;
  let text = '';
  let imagePaintCount = 0;
  for (let p = 1; p <= doc.numPages; p++) {
    const page = await doc.getPage(p);
    const tc = await page.getTextContent();
    text += tc.items.map((i) => i.str).join(' ') + '\n';
    const opList = await page.getOperatorList();
    for (const fn of opList.fnArray) {
      if (
        fn === pdfjsLib.OPS.paintImageXObject ||
        fn === pdfjsLib.OPS.paintInlineImageXObject ||
        fn === pdfjsLib.OPS.paintImageMaskXObject
      ) {
        imagePaintCount += 1;
      }
    }
  }
  const raw = Buffer.from(bytes).toString('latin1');
  const rawXObjectImageCount = (raw.match(/\/Subtype\s*\/Image\b/g) || []).length;
  return {
    pages: doc.numPages,
    text,
    imagePaintCount,
    rawXObjectImageCount,
    hasRawBase64: /data:image\/|base64,/i.test(text),
  };
}

async function main() {
  fs.mkdirSync(SCREENSHOT_DIR, {recursive: true});
  const tmpDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'kiem-ui-redesign-data-'));
  const port = await freePort();
  const chromePath = findChrome();
  const server = await startIsolatedServer(port, tmpDataDir);
  const {baseUrl} = server;

  const summary = {
    baseUrl,
    screenshotDir: SCREENSHOT_DIR,
    screenshots: {},
    pillars: {},
    bugs: [],
    failures: [],
    consoleErrors: [],
    pageErrors: [],
    unexpectedHttpErrors: [],
  };

  let allowExpectedHttp = false;
  let browser;

  const recordBug = (owner, area, title, details) => {
    summary.bugs.push({owner, area, title, details});
  };
  const recordFail = (area, error) => {
    summary.failures.push({area, error: error instanceof Error ? error.message : String(error)});
  };

  try {
    browser = await chromium.launch({
      executablePath: chromePath,
      headless: true,
      args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    });
    const context = await browser.newContext({viewport: {width: 1440, height: 900}, acceptDownloads: true});
    const page = await context.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        if (!allowExpectedHttp) summary.consoleErrors.push(msg.text());
      }
    });
    page.on('pageerror', (err) => {
      summary.pageErrors.push(err.message);
    });
    page.on('response', (res) => {
      if (res.status() >= 400 && !allowExpectedHttp) {
        summary.unexpectedHttpErrors.push({status: res.status(), url: res.url()});
      }
    });

    const waitReady = async () => {
      await page.waitForSelector('.paper .question, .paper-empty, .workflow-strip', {timeout: 15000});
      await page.waitForTimeout(300);
    };

    const shot = async (key, filename) => {
      const target = path.join(SCREENSHOT_DIR, filename);
      await page.screenshot({path: target, fullPage: false});
      summary.screenshots[key] = target;
      return target;
    };

    await page.goto(baseUrl, {waitUntil: 'networkidle'});
    await waitReady();

    // =========================================================================
    // PILLAR 1: Aesthetics, geometry across 3 viewports + KaTeX in stem & table
    // =========================================================================
    try {
      const viewports = [
        {name: '1440x900', width: 1440, height: 900, shotKey: 'desktop1440', shotFile: 'redesign-desktop-1440x900.png'},
        {name: '1280x720', width: 1280, height: 720, shotKey: 'desktop1280', shotFile: 'redesign-desktop-1280x720.png'},
        {name: '390x844', width: 390, height: 844, shotKey: 'mobile390', shotFile: 'redesign-mobile-390x844.png'},
      ];
      const vpReports = [];
      for (const vp of viewports) {
        await page.setViewportSize({width: vp.width, height: vp.height});
        await page.waitForTimeout(250);
        const geo = await inspectViewportGeometry(page, vp.name);
        vpReports.push(geo);
        await shot(vp.shotKey, vp.shotFile);

        if (vp.name === '390x844') {
          const assistantTab = page.locator('.ux-view-tabs button', {hasText: /Trợ lý/i}).first();
          if (await assistantTab.count()) {
            await assistantTab.click();
            await page.waitForTimeout(200);
            const mobileAssistantGeo = await inspectViewportGeometry(page, '390x844-assistant');
            vpReports.push(mobileAssistantGeo);
            const editorTab = page.locator('.ux-view-tabs button', {hasText: /Bàn soạn/i}).first();
            if (await editorTab.count()) await editorTab.click();
            await page.waitForTimeout(150);
          }
        }
      }

      // Restore 1440x900 and test KaTeX in stem AND table cells (both richDoc table & q.tables)
      await page.setViewportSize({width: 1440, height: 900});
      await page.waitForTimeout(200);

      // Seed rich question containing formula in stem AND a richDoc table with $x^2+y^2=1$ AND legacy q.tables with image + $a^2+b^2=c^2$
      const kvBefore = await page.evaluate(async (pngUri) => {
        const {documentPlain} = await import('/rich-document.js');
        const res = await fetch('/api/kv?key=state');
        const kv = await res.json();
        const st = structuredClone(kv.value);
        const curExam = st.exams.find((e) => e.id === st.current) || st.exams[0];
        if (!curExam || !curExam.questions?.length) return {ok: false};
        const q0 = curExam.questions[0];
        q0.type = 'mcq';
        q0.options = ['2', '3', '4', '5'];
        q0.answer = 0;
        q0.answerKnown = true;
        q0.explanation = 'GIAI_THICH_BI_MAT_GV_991: Với $x=9$ thì $P=2$.';
        q0.richDoc = {
          type: 'doc',
          content: [
            {
              type: 'paragraph',
              attrs: {id: 'p-qa-stem-1'},
              content: [
                {type: 'text', text: 'Tính giá trị biểu thức '},
                {type: 'mathInline', attrs: {id: 'm-qa-1', latex: 'P = \\frac{\\sqrt{x}+1}{2}', display: false}},
                {type: 'text', text: ' tại '},
                {type: 'mathInline', attrs: {id: 'm-qa-2', latex: 'x=9', display: false}},
                {type: 'text', text: '.'},
              ],
            },
            {
              type: 'table',
              attrs: {id: 'tbl-qa-1'},
              content: [
                {
                  type: 'tableRow',
                  content: [
                    {
                      type: 'tableHeader',
                      content: [{type: 'paragraph', attrs: {id: 'p-th-1'}, content: [{type: 'text', text: 'Biến số'}]}],
                    },
                    {
                      type: 'tableHeader',
                      content: [{type: 'paragraph', attrs: {id: 'p-th-2'}, content: [{type: 'text', text: 'Giá trị'}]}],
                    },
                  ],
                },
                {
                  type: 'tableRow',
                  content: [
                    {
                      type: 'tableCell',
                      content: [
                        {
                          type: 'paragraph',
                          attrs: {id: 'p-td-1'},
                          content: [{type: 'mathInline', attrs: {id: 'm-td-1', latex: 'x^2+y^2=1', display: false}}],
                        },
                      ],
                    },
                    {
                      type: 'tableCell',
                      content: [{type: 'paragraph', attrs: {id: 'p-td-2'}, content: [{type: 'text', text: '9'}]}],
                    },
                  ],
                },
              ],
            },
          ],
        };
        q0.stem = documentPlain(q0.richDoc);
        q0.tables = [
          {
            id: 'legacy-tbl-1',
            rows: [[{data: pngUri, caption: 'Hình trong ô bảng'}, '$a^2+b^2=c^2$']],
          },
        ];
        q0.rubric = [{text: 'BAREM_BI_MAT_GV_882', points: 1}];
        const put = await fetch('/api/kv', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json', 'If-Match': String(kv.revision)},
          body: JSON.stringify({key: 'state', value: st}),
        });
        return {ok: put.status === 200, status: put.status, plainStem: q0.stem};
      }, SAMPLE_PNG_DATA_URI);
      assert(kvBefore.ok, 'Lưu state test ban đầu phải 200');
      await page.reload({waitUntil: 'networkidle'});
      await waitReady();

      const katexAudit = await page.evaluate(() => {
        const stemKatex = document.querySelectorAll('.question .stem-editor .katex').length;
        const katexErrors = document.querySelectorAll('.katex-error').length;
        const richTableKatex = document.querySelectorAll('.question .stem-editor table .katex').length;
        const legacyTable = document.querySelector('.question .inserted-table');
        const legacyTableText = legacyTable ? legacyTable.textContent || '' : '';
        const legacyTableKatex = legacyTable ? legacyTable.querySelectorAll('.katex').length : 0;
        const legacyTableLiteralDollar = /\$a\^2\+b\^2=c\^2\$/.test(legacyTableText);
        const legacyTableImageRendered = legacyTable ? legacyTable.querySelectorAll('img').length : 0;
        return {
          stemKatex,
          katexErrors,
          richTableKatex,
          legacyTableText,
          legacyTableKatex,
          legacyTableLiteralDollar,
          legacyTableImageRendered,
        };
      });

      if (katexAudit.katexErrors > 0) {
        recordBug('ui-architect', 'katex', 'Phát hiện .katex-error khi render công thức', katexAudit);
      }
      if (katexAudit.richTableKatex < 1) {
        recordBug('ui-architect', 'katex-in-rich-table', 'KaTeX không render trong ô bảng richDoc của TipTap', katexAudit);
      }
      if (katexAudit.legacyTableLiteralDollar && katexAudit.legacyTableKatex === 0) {
        recordBug(
          'ux-interactions',
          'katex-in-q-table',
          'Ô bảng q.tables (.inserted-table) chứa $...$ chưa render KaTeX trên canvas (reference.js:481 dùng esc() thay vì richTextHTML())',
          katexAudit,
        );
      }
      for (const rep of vpReports) {
        if (rep.overflowX) recordBug('ui-architect', 'overflowX', `Tràn ngang tại ${rep.viewport}`, rep);
        if (rep.hasObjectObject) recordBug('ui-architect', 'render', `Xuất hiện [object Object] tại ${rep.viewport}`, rep);
        if (rep.overlaps.length) recordBug('ui-architect', 'overlap', `Phần tử đè lên nhau tại ${rep.viewport}`, rep.overlaps);
        if (rep.clipped.length) recordBug('ui-architect', 'clipped', `Phần tử bị cắt ngoài viewport tại ${rep.viewport}`, rep.clipped);
        if (rep.obscured.length) recordBug('ui-architect', 'obscured', `Phần tử bị che khuất elementFromPoint tại ${rep.viewport}`, rep.obscured);
        for (const defect of rep.visualDefects || []) {
          recordBug('ui-architect', defect.area, `${defect.detail} (${rep.viewport})`, defect);
        }
      }

      summary.pillars.p1 = {vpReports, katexAudit};
    } catch (err) {
      recordFail('Pillar 1 (Thẩm mỹ, hình học & KaTeX)', err);
    }

    // =========================================================================
    // PILLAR 2: Multi-subject catalog, accent search, 4 channels, 4 citation states & focus return
    // =========================================================================
    try {
      await page.setViewportSize({width: 1440, height: 900});
      const catalogData = await page.evaluate(async () => {
        const res = await fetch('/api/lesson-catalog');
        return await res.json();
      });
      const collections = catalogData.collections || [];
      const hasCombo = (subRegex, grade) =>
        collections.some((c) => subRegex.test(String(c.subject || '')) && Number(c.grade) === grade && (c.lessons || []).length > 0);
      const subjectCoverage = {
        toan9: hasCombo(/^Toán$/i, 9),
        toan10: hasCombo(/^Toán$/i, 10),
        toan12: hasCombo(/^Toán$/i, 12),
        van9: hasCombo(/Ngữ văn/i, 9),
        van11: hasCombo(/Ngữ văn/i, 11),
        anh9: hasCombo(/Tiếng Anh/i, 9),
        anh11: hasCombo(/Tiếng Anh/i, 11),
        khtn_or_ly_hoa_sinh: collections.some(
          (c) => /(Khoa học tự nhiên|KHTN|Vật lí|Vật lý|Hóa học|Hoá học|Sinh học)/i.test(String(c.subject || '')) && (c.lessons || []).length > 0,
        ),
        scienceSubjectsFound: [...new Set(collections.map((c) => `${c.subject} ${c.grade}`))],
      };
      for (const [k, ok] of Object.entries(subjectCoverage)) {
        if (typeof ok === 'boolean' && !ok) {
          recordBug('content-and-core', 'lesson-catalog', `Thiếu học liệu mẫu cho ${k}`, subjectCoverage);
        }
      }

      // Open Nguồn cho trợ lý (4 kênh) via visible trigger (.compose-attachments paperclip or workflow step 1), check 4 channels, then navigate into SGK / Bài học picker
      const visibleSourceBtn = page.locator('[data-action="assistant-sources"]:visible');
      if (await visibleSourceBtn.count()) {
        await visibleSourceBtn.first().click();
      } else {
        await page.locator('[data-action="workflow-sources"]:visible').first().click();
      }
      await page.waitForSelector('#dialog[open] #assistant-source-form', {timeout: 8000});
      const channelsCheck = await page.evaluate(() => {
        const dialog = document.querySelector('#dialog');
        const badges = [...dialog.querySelectorAll('.source-legend .source-channel-badge')].map((n) => n.textContent.trim());
        const tabLabels = [...dialog.querySelectorAll('.source-tabs button')].map((n) => n.textContent.trim());
        return {badges, tabLabels};
      });

      // Switch to SGK / Bài học picker
      await page.locator('#dialog [data-action="lesson-sources"]').first().click();
      await page.waitForSelector('#dialog[open] #lesson-picker', {timeout: 8000});

      // Clear grade/subject filters so multi-subject catalog shows across subjects & grades
      const gradeSelect = page.locator('#lesson-picker select[name="grade"]');
      const subjectSelect = page.locator('#lesson-picker select[name="subject"]');
      await subjectSelect.selectOption({value: ''});
      await gradeSelect.selectOption({value: ''});
      await page.waitForTimeout(150);

      // Capture screenshot showing multi-subject lesson picker
      await shot('lessonCatalog', 'redesign-lesson-catalog.png');

      // Test accent-insensitive search using a real accented lesson title without accents
      const sampleLesson = collections.find((c) => c.lessons?.length)?.lessons[0];
      const stripAccents = (s) =>
        String(s || '')
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/đ/g, 'd')
          .replace(/Đ/g, 'D')
          .toLowerCase();
      const firstTwoWords = stripAccents(sampleLesson.title).split(/\s+/).filter(Boolean).slice(0, 3).join(' ');
      await page.locator('#lesson-picker input[name="query"]').fill(firstTwoWords);
      await page.waitForTimeout(200);
      const searchMatches = await page.locator('#lesson-picker [data-lesson-list] input[name="lesson"]').count();
      assert(searchMatches >= 1, `Tìm kiếm không dấu "${firstTwoWords}" phải khớp bài "${sampleLesson.title}"`);

      // Select first visible lesson & submit
      await page.locator('#lesson-picker [data-lesson-list] input[name="lesson"]').first().check();
      await page.locator('#lesson-picker button[type="submit"]').click();
      await page.waitForFunction(() => !document.querySelector('#dialog')?.open, {timeout: 8000});
      await page.waitForTimeout(200);

      // Test detach-source focus return!
      const chipsBeforeDetach = await page.locator('.source-chips .source-chip').count();
      assert(chipsBeforeDetach >= 1, 'Phải có ít nhất 1 chip nguồn sau khi gắn bài học');
      const detachBtn = page.locator('.source-chips .source-detach').first();
      await detachBtn.focus();
      await detachBtn.click();
      await page.waitForTimeout(250);
      const chipsAfterDetach = await page.locator('.source-chips .source-chip').count();
      assert.equal(chipsAfterDetach, chipsBeforeDetach - 1, 'Gỡ nguồn phải xóa đúng 1 chip nguồn');

      const activeAfterDetach = await page.evaluate(() => {
        const ae = document.activeElement;
        return {
          tag: ae?.tagName || null,
          className: ae?.className || '',
          action: ae?.dataset?.action || null,
          isBody: ae === document.body,
        };
      });
      if (activeAfterDetach.isBody) {
        recordBug(
          'ux-interactions',
          'detach-source-focus',
          'Bấm nút gỡ nguồn (.source-detach) mất focus về document.body (reference.js:445 gọi c.change re-render toàn bộ DOM mà không khôi phục focus)',
          activeAfterDetach,
        );
      }

      // Test 4 citation states inside real Question Check UI modal
      // Re-attach lesson source via picker or state so doc exists as version 2 for version_changed test
      const citationPrep = await page.evaluate(async () => {
        const r = await fetch('/api/kv?key=state');
        const kv = await r.json();
        const st = structuredClone(kv.value);
        const ex = st.exams.find((e) => e.id === st.current);
        const matchedDocId = 'doc-cite-matched';
        const changedDocId = 'doc-cite-changed';
        ex.docs = [
          {
            id: matchedDocId,
            name: 'Tài liệu đối chiếu chuẩn',
            kind: 'text',
            version: 1,
            pages: [{number: 1, text: 'Phương trình bậc hai có biệt thức Delta = b^2 - 4ac dùng để xét nghiệm.'}],
          },
          {
            id: changedDocId,
            name: 'Tài liệu đã sửa phiên bản',
            kind: 'text',
            version: 2,
            pages: [{number: 1, text: 'Nội dung bản mới đã thay đổi công thức.'}],
          },
        ];
        ex.assistantSources = [matchedDocId, changedDocId];
        const q = ex.questions[0];
        q.source = {docId: matchedDocId, page: 1};
        const put = await fetch('/api/kv', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json', 'If-Match': String(kv.revision)},
          body: JSON.stringify({key: 'state', value: st}),
        });
        return {status: put.status, qid: q.id, matchedDocId, changedDocId};
      });
      assert.equal(citationPrep.status, 200);
      await page.reload({waitUntil: 'networkidle'});
      await waitReady();

      await page.route('**/api/exams/*/questions/*/check', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            method: 'ai_mock_check',
            comparison: 'agrees',
            uncertain: false,
            answer: 0,
            explanation: 'Kết quả đối chiếu 4 trạng thái trích dẫn.',
            evidence: [
              {
                sourceId: citationPrep.matchedDocId,
                sourceVersion: 1,
                locator: {kind: 'page', index: 1},
                quote: 'Phương trình bậc hai có biệt thức Delta = b^2 - 4ac',
              },
              {
                sourceId: citationPrep.changedDocId,
                sourceVersion: 1,
                locator: {kind: 'page', index: 1},
                quote: 'Đoạn trích bản v1 trước khi sửa',
              },
              {
                sourceId: 'doc-cite-deleted-999',
                sourceVersion: 1,
                locator: {kind: 'page', index: 1},
                quote: 'Đoạn trích từ tài liệu đã bị gỡ khỏi đề',
              },
              {
                sourceId: citationPrep.matchedDocId,
                sourceVersion: 1,
                locator: {kind: 'page', index: 1},
                quote: 'Đoạn trích không tồn tại trong trang tài liệu này',
              },
            ],
          }),
        });
      });

      await page.locator(`.question[data-q="${citationPrep.qid}"] .stem-editor`).first().click();
      await page.locator(`.question[data-q="${citationPrep.qid}"]`).hover();
      await page.locator(`.question[data-q="${citationPrep.qid}"] [data-action="select"]`).click({force: true});
      await page.locator('[data-action="ai-check"]').first().click();
      await page.waitForSelector('#dialog[open] #question-check-form', {timeout: 8000});
      await page.locator('#question-check-consent').check();
      await page.locator('#question-check-form button[type="submit"]').click();
      await page.waitForSelector('#dialog[open] .question-check-citation', {timeout: 8000});

      const citationStates = await page.evaluate(() => {
        const cards = [...document.querySelectorAll('#dialog .question-check-citation')];
        return cards.map((card) => {
          const statusEl = card.querySelector('[data-citation-status]');
          const status = statusEl?.dataset?.citationStatus || (card.querySelector('details, .matched-quote, .citation-matched, .citation-quote') ? 'matched' : 'unknown');
          return {
            status,
            hasDetails: !!card.querySelector('details'),
            hasMatchedText: card.textContent.includes('Delta = b^2 - 4ac'),
            text: card.textContent.trim(),
          };
        });
      });
      // Expand any citation <details> inside modal to verify interactive open
      const firstCitationSummary = page.locator('#dialog .question-check-citation details summary').first();
      if (await firstCitationSummary.count()) {
        await firstCitationSummary.click();
        await page.waitForTimeout(100);
      }
      await page.unroute('**/api/exams/*/questions/*/check');
      await page.locator('#dialog button[data-action="close"]').first().click();
      await page.waitForFunction(() => !document.querySelector('#dialog')?.open, {timeout: 5000});

      const expectedCitationStatuses = ['matched', 'version_changed', 'source_missing', 'quote_mismatch'];
      const gotStatuses = citationStates.map((s) => s.status);
      for (const st of expectedCitationStatuses) {
        if (!gotStatuses.includes(st)) {
          recordBug('content-and-core', 'citation-context', `Thiếu trạng thái ngữ cảnh trích dẫn "${st}"`, citationStates);
        }
      }

      summary.pillars.p2 = {
        subjectCoverage,
        searchMatches,
        channelsCheck,
        chipsBeforeDetach,
        chipsAfterDetach,
        activeAfterDetach,
        citationStates,
      };
    } catch (err) {
      recordFail('Pillar 2 (Kho học liệu, tìm không dấu, 4 kênh, trích dẫn & focus)', err);
    }

    // =========================================================================
    // PILLAR 3: Drag-and-drop valid .txt/.md and invalid extension onto Assistant
    // =========================================================================
    try {
      const assistantBefore = await page.locator('.source-chips .source-chip').count();

      // Simulate dragenter / dragover with DataTransfer containing a .txt file on .assistant
      const dropStates = await page.evaluate(async () => {
        const target = document.querySelector('#prompt') || document.querySelector('#chat-input') || document.querySelector('.assistant');
        const assistant = document.querySelector('.assistant');
        const dt = new DataTransfer();
        dt.items.add(new File(['Ngữ liệu bài học Vật lý lớp 10: Định luật II Newton F = ma.'], 'vat-ly-10-drop.txt', {type: 'text/plain'}));

        target.dispatchEvent(new DragEvent('dragenter', {bubbles: true, cancelable: true, dataTransfer: dt}));
        const activeOnEnter = assistant?.classList.contains('is-drop-active') || false;
        target.dispatchEvent(new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: dt}));
        const activeOnOver = assistant?.classList.contains('is-drop-active') || false;
        const overlay = document.querySelector('.assistant-drop-overlay');
        const overlayVisible = overlay ? !overlay.hidden && getComputedStyle(overlay).display !== 'none' : false;

        target.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
        return {activeOnEnter, activeOnOver, overlayVisible};
      });

      await page.waitForFunction(
        (prev) => document.querySelectorAll('.source-chips .source-chip').length > prev,
        assistantBefore,
        {timeout: 10000},
      );
      await page.waitForTimeout(250);

      const chipTextAfterDrop = await page.evaluate(() =>
        [...document.querySelectorAll('.source-chips .source-chip')].map((n) => n.textContent.trim()),
      );
      const dropActiveCleared = await page.evaluate(
        () => !document.querySelector('.assistant')?.classList.contains('is-drop-active'),
      );

      // Also drop .md onto #prompt / #chat-input
      const chipsAfterTxt = chipTextAfterDrop.length;
      await page.evaluate(() => {
        const target = document.querySelector('#chat-input') || document.querySelector('.assistant');
        const dt = new DataTransfer();
        dt.items.add(new File(['# Đọc hiểu Ngữ văn 11\n\nVăn bản nghị luận về trách nhiệm.'], 'ngu-van-11.md', {type: 'text/markdown'}));
        target.dispatchEvent(new DragEvent('dragenter', {bubbles: true, cancelable: true, dataTransfer: dt}));
        target.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
      });
      await page.waitForFunction(
        (prev) => document.querySelectorAll('.source-chips .source-chip').length > prev,
        chipsAfterTxt,
        {timeout: 10000},
      );

      // Close source modal opened by importFile after drop before testing invalid drop & Pillar 4
      if (await page.locator('#dialog[open]').count()) {
        await page.locator('#dialog button[data-action="close"]').first().click().catch(async () => {
          await page.evaluate(() => document.querySelector('#dialog')?.close());
        });
        await page.waitForFunction(() => !document.querySelector('#dialog')?.open, {timeout: 5000});
      }

      // Invalid extension drop test (.exe) and capture #toast notification text immediately
      const chipsBeforeInvalid = await page.locator('.source-chips .source-chip').count();
      const toastTextInvalid = await page.evaluate(async () => {
        const seen = [];
        const toastEl = document.querySelector('#toast');
        const obs = toastEl
          ? new MutationObserver(() => {
              const txt = toastEl.textContent?.trim();
              if (txt) seen.push(txt);
            })
          : null;
        if (obs && toastEl) obs.observe(toastEl, {childList: true, characterData: true, subtree: true});
        const target = document.querySelector('.assistant');
        const dt = new DataTransfer();
        dt.items.add(new File(['MZ\x90\x00binary'], 'blocked.exe', {type: 'application/octet-stream'}));
        target.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
        await new Promise((r) => setTimeout(r, 350));
        obs?.disconnect();
        return seen.join(' | ') || toastEl?.textContent?.trim() || '';
      });
      const chipsAfterInvalid = await page.locator('.source-chips .source-chip').count();

      assert(dropStates.activeOnEnter && dropStates.activeOnOver, 'Kéo tệp vào .assistant phải bật .is-drop-active');
      assert(dropStates.overlayVisible, 'Kéo tệp vào .assistant phải hiện .assistant-drop-overlay');
      assert(dropActiveCleared, 'Sau khi thả phải tắt .is-drop-active');
      assert.equal(chipsAfterInvalid, chipsBeforeInvalid, 'Thả tệp .exe sai định dạng không được thêm chip nguồn');

      if (await page.locator('#dialog[open]').count()) {
        await page.evaluate(() => document.querySelector('#dialog')?.close());
      }

      summary.pillars.p3 = {
        dropStates,
        dropActiveCleared,
        chipTextAfterDrop,
        chipsAfterInvalid,
        toastTextInvalid,
      };
    } catch (err) {
      recordFail('Pillar 3 (Kéo–thả tệp vào Trợ lý AI)', err);
    }

    // =========================================================================
    // PILLAR 4: Quick Actions, Inline Math Panel, Context Bar, Diff 2 Columns & 409
    // =========================================================================
    try {
      // Ensure at least 2 questions exist for move up/down & duplicate checks
      const firstQId = await page.locator('.paper .question').first().getAttribute('data-q');
      assert(firstQId, 'Phải có câu hỏi đầu tiên');

      // Check .q-actions bounding geometry on Desktop 1440x900 AND Mobile 390x844
      const checkQActionsAtViewport = async (w, h, vpName) => {
        await page.setViewportSize({width: w, height: h});
        await page.waitForTimeout(200);
        const card = page.locator(`.question[data-q="${firstQId}"]`);
        await card.locator('.stem-editor').first().click();
        await card.hover();
        await page.waitForTimeout(200);
        return await page.evaluate(({qid, vp}) => {
          const vw = window.innerWidth;
          const cardEl = document.querySelector(`.question[data-q="${qid}"]`);
          const qa = cardEl?.querySelector('.q-actions');
          const statusEl = cardEl?.querySelector('.q-status');
          if (!qa) return {vp, missing: true};
          const qaStyle = getComputedStyle(qa);
          const qaRect = qa.getBoundingClientRect();
          const stRect = statusEl?.getBoundingClientRect();
          const btns = [...qa.querySelectorAll('.q-quick-btn')];
          const hiddenOrZero = btns.filter((b) => {
            const r = b.getBoundingClientRect();
            return r.width < 2 || r.height < 2;
          }).length;
          const clippedRight = qaRect.right > vw + 2 || btns.some((b) => b.getBoundingClientRect().right > vw + 2);
          const clippedLeft = qaRect.left < -2 || btns.some((b) => b.getBoundingClientRect().left < -2);
          const overlapsStatus =
            stRect &&
            Math.min(qaRect.right, stRect.right) - Math.max(qaRect.left, stRect.left) > 2 &&
            Math.min(qaRect.bottom, stRect.bottom) - Math.max(qaRect.top, stRect.top) > 2;
          return {
            vp,
            display: qaStyle.display,
            btnCount: btns.length,
            hiddenOrZero,
            qaRect: {
              left: Math.round(qaRect.left),
              right: Math.round(qaRect.right),
              top: Math.round(qaRect.top),
              bottom: Math.round(qaRect.bottom),
            },
            vw,
            clippedRight,
            clippedLeft,
            overlapsStatus: !!overlapsStatus,
          };
        }, {qid: firstQId, vp: vpName});
      };

      const qActionsMobile = await checkQActionsAtViewport(390, 844, '390x844');
      const qActionsDesktop1280 = await checkQActionsAtViewport(1280, 720, '1280x720');
      const qActionsDesktop1440 = await checkQActionsAtViewport(1440, 900, '1440x900');

      for (const qaInfo of [qActionsDesktop1440, qActionsDesktop1280, qActionsMobile]) {
        if (qaInfo.missing || qaInfo.display === 'none') {
          recordBug('ui-architect', 'q-actions-visibility', `.q-actions không hiển thị khi focus/hover tại ${qaInfo.vp}`, qaInfo);
        }
        if (qaInfo.clippedRight || qaInfo.clippedLeft) {
          recordBug('ui-architect', 'q-actions-clipping', `Thanh .q-actions bị tràn khung nhìn tại ${qaInfo.vp}`, qaInfo);
        }
        if (qaInfo.overlapsStatus) {
          recordBug('ui-architect', 'q-actions-overlap', `Thanh .q-actions đè lên .q-status tại ${qaInfo.vp}`, qaInfo);
        }
      }

      // Context bar verification across states (selected-question -> toggle-approve -> needs-review)
      await page.locator(`.question[data-q="${firstQId}"] [data-action="select"]`).click({force: true});
      await page.waitForTimeout(200);
      const ctxSelectedBadge = (await page.locator('.assistant-context-badge').textContent())?.trim() || '';
      assert(/Đang chọn Câu 1/i.test(ctxSelectedBadge), `Expected selected-question context badge, got "${ctxSelectedBadge}"`);

      // Toggle approve -> unapprove -> approve
      const approveBtn = page.locator(`.question[data-q="${firstQId}"] [data-action="toggle-approve-question"]`);
      const wasApproved = (await approveBtn.getAttribute('aria-pressed')) === 'true';
      await approveBtn.click({force: true});
      await page.waitForTimeout(200);
      const afterToggle1 = await approveBtn.getAttribute('aria-pressed');
      assert.equal(afterToggle1, String(!wasApproved), 'Nút duyệt nhanh phải đảo aria-pressed');
      await approveBtn.click({force: true});
      await page.waitForTimeout(200);
      const afterToggle2 = await approveBtn.getAttribute('aria-pressed');
      assert.equal(afterToggle2, String(wasApproved), 'Bấm lần 2 phải khôi phục aria-pressed');

      // Quick formula button keeps .inline-math-panel open!
      await page.locator(`.question[data-q="${firstQId}"] [data-action="quick-formula"]`).click({force: true});
      await page.waitForSelector('.inline-math-panel', {timeout: 8000});
      await page.waitForTimeout(350);
      const mathPanelPersists = await page.locator('.inline-math-panel').isVisible();
      assert(mathPanelPersists, '.inline-math-panel phải giữ mở sau khi bấm quick-formula');
      await page.locator('.inline-math-panel [data-action="floating-close"]').first().click();
      await page.waitForTimeout(200);

      const qActionsAfterClose = await page.evaluate((qid) => {
        const card = document.querySelector(`.question[data-q="${qid}"]`);
        const qa = card?.querySelector('.q-actions');
        return {
          isSelected: card?.classList.contains('selected') || false,
          hasFocusWithin: card?.matches(':focus-within') || false,
          qaDisplay: qa ? getComputedStyle(qa).display : null,
          activeTag: document.activeElement?.tagName || null,
          activeClass: document.activeElement?.className || '',
        };
      }, firstQId);
      if (qActionsAfterClose.isSelected && qActionsAfterClose.qaDisplay === 'none') {
        recordBug(
          'ui-architect',
          'selected-q-actions-hidden',
          'Câu hỏi đang .selected bị ẩn thanh .q-actions (reference.css:2 ghi đè style.css:632 bỏ rule .question.selected .q-actions)',
          qActionsAfterClose,
        );
      }

      // Duplicate question assigns a brand-new UUID (should work directly on .question.selected without re-hovering)
      const idsBeforeDup = await page.evaluate(() =>
        [...document.querySelectorAll('.paper .question')].map((el) => el.dataset.q),
      );
      await page.locator(`.question[data-q="${firstQId}"] [data-action="duplicate-question"]`).click();
      await page.waitForTimeout(250);
      const idsAfterDup = await page.evaluate(() =>
        [...document.querySelectorAll('.paper .question')].map((el) => el.dataset.q),
      );
      assert.equal(idsAfterDup.length, idsBeforeDup.length + 1, 'Nhân bản phải tăng thêm 1 câu');
      const dupId = idsAfterDup[1];
      assert(dupId && !idsBeforeDup.includes(dupId), 'Câu nhân bản phải có UUID mới không trùng');

      // After duplicate-question, the duplicated copy (dupId) becomes .selected — move it up to index 0 and back down to index 1 directly!
      const qCountBeforeMove = idsAfterDup.length;
      assert(qCountBeforeMove >= 2);
      await page.locator(`.question[data-q="${dupId}"] [data-action="quick-move-up"]`).click();
      await page.waitForTimeout(200);
      const idsAfterMoveUp = await page.evaluate(() =>
        [...document.querySelectorAll('.paper .question')].map((el) => el.dataset.q),
      );
      assert.equal(idsAfterMoveUp[0], dupId, 'quick-move-up phải đưa câu nhân bản lên vị trí đầu');
      await page.locator(`.question[data-q="${dupId}"] [data-action="quick-move-down"]`).click();
      await page.waitForTimeout(200);
      const idsAfterMoveDown = await page.evaluate(() =>
        [...document.querySelectorAll('.paper .question')].map((el) => el.dataset.q),
      );
      assert.equal(idsAfterMoveDown[1], dupId, 'quick-move-down phải đưa câu nhân bản về vị trí 2');
      assert.equal(idsAfterMoveDown[0], firstQId, 'Câu gốc phải trở lại vị trí đầu');

      // Ensure contextual assistant bar switches away from selected-question on clear or exam state change
      const ctxModes = await page.evaluate(async () => {
        const mod = await import('/reference.js');
        const emptyRes = mod.buildContextualAssistantSuggestions({subject: 'Toán', grade: '9', questions: [], docs: [], assistantSources: []});
        const srcRes = mod.buildContextualAssistantSuggestions({
          subject: 'Toán',
          grade: '9',
          questions: [],
          docs: [{id: 'd1', name: 'Src', pages: [{number: 1, text: 'abc'}]}],
          assistantSources: ['d1'],
        });
        const q1 = {id: 'q1', v: 1, type: 'mcq', stem: 'x', options: ['a', 'b', 'c', 'd'], answer: 0, answerKnown: true, check: {version: 1, status: 'review'}};
        const reviewRes = mod.buildContextualAssistantSuggestions({subject: 'Toán', grade: '9', questions: [q1], docs: []});
        const q2 = {...q1, check: {version: 1, status: 'approved'}, approval: {at: Date.now()}};
        const readyRes = mod.buildContextualAssistantSuggestions({subject: 'Toán', grade: '9', questions: [q2], docs: []});
        return {empty: emptyRes.mode, hasSources: srcRes.mode, needsReview: reviewRes.mode, ready: readyRes.mode};
      });
      assert.deepEqual(ctxModes, {
        empty: 'empty',
        hasSources: 'has-sources',
        needsReview: 'needs-review',
        ready: 'ready',
      });

      // Diff 2 columns (workbench apply-block-patch / discard-block-patch / undo-from-diff)
      await page.evaluate(async () => {
        const r = await fetch('/api/kv?key=state');
        const kv = await r.json();
        const st = structuredClone(kv.value);
        const ex = st.exams.find((e) => e.id === st.current);
        ex.aiConsent = true;
        await fetch('/api/kv', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json', 'If-Match': String(kv.revision)},
          body: JSON.stringify({key: 'state', value: st}),
        });
      });
      await page.reload({waitUntil: 'networkidle'});
      await waitReady();

      await page.locator(`.question[data-q="${firstQId}"] .stem-editor`).first().click();
      await page.locator(`.question[data-q="${firstQId}"]`).hover();
      await page.locator(`.question[data-q="${firstQId}"] [data-action="select"]`).click({force: true});
      await page.waitForTimeout(150);

      // Route /api/assistant/patch to test 2-column Diff accept, discard, and undo
      const originalStemAndBlocks = await page.evaluate(async (qid) => {
        const r = await fetch('/api/kv?key=state');
        const kv = await r.json();
        const ex = kv.value.exams.find((e) => e.id === kv.value.current);
        const q = ex.questions.find((item) => item.id === qid);
        return {q, examId: ex.id};
      }, firstQId);

      await page.route('**/api/assistant/patch', async (route) => {
        const reqBody = JSON.parse(route.request().postData() || '{}');
        const targetQ = (reqBody.exam?.questions || []).find((q) => q.id === firstQId) || originalStemAndBlocks.q;
        const blockIds = targetQ.blockIds || {};
        const nextStem = String(targetQ.stem || '').includes('Hãy tính')
          ? targetQ.stem.replace('Hãy tính', 'Hãy tính (bước 2)')
          : String(targetQ.stem || '').replace('Tính giá trị biểu thức', 'Hãy tính giá trị biểu thức');
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            message: 'Đề xuất làm rõ đề bài Câu 1.',
            edits: [
              {
                blockId: blockIds.stem,
                op: 'replace',
                content: nextStem,
              },
              {
                blockId: blockIds.options,
                op: 'replace',
                content: targetQ.options,
              },
              {
                blockId: blockIds.answer,
                op: 'replace',
                content: targetQ.answer,
              },
              {
                blockId: blockIds.explanation,
                op: 'replace',
                content: targetQ.explanation,
              },
            ],
          }),
        });
      });

      const sendPatchPrompt = async (promptText) => {
        await page.locator('#chat-input').fill(promptText);
        await page.locator('#chat-form button[type="submit"]').click();
        await page.waitForFunction(
          () =>
            !!document.querySelector('#dialog[open] .diff-side-by-side') ||
            !!document.querySelector('.proposal-card [data-action="show-block-diff"]'),
          null,
          {timeout: 8000},
        ).catch(async () => {
          const assistantState = await page.evaluate(() => document.querySelector('.assistant-body')?.textContent?.trim() || '');
          throw new Error(`Không thấy Diff 2 cột hay .proposal-card sau prompt "${promptText}". assistant-body: ${assistantState.slice(0, 300)}`);
        });
        if (!(await page.locator('#dialog[open] .diff-side-by-side').count())) {
          await page.locator('.proposal-card [data-action="show-block-diff"]').first().click();
          await page.waitForSelector('#dialog[open] .diff-side-by-side', {timeout: 8000});
        }
      };

      // 1) Test discard
      await sendPatchPrompt('Viết lại câu 1 rõ hơn.');
      const diffColsCount = await page.locator('#dialog .diff-side-by-side .diff-col').count();
      assert.equal(diffColsCount, 2, 'Diff 2 cột phải có đúng 2 .diff-col');
      await page.locator('#dialog [data-action="discard-block-patch"]').click();
      await page.waitForFunction(() => !document.querySelector('#dialog')?.open, {timeout: 5000});

      // 2) Test accept + undo from diff!
      await sendPatchPrompt('Viết lại câu 1 ngắn gọn hơn.');
      await page.locator('#dialog [data-action="apply-block-patch"]').click();
      await page.waitForFunction(() => !document.querySelector('#dialog')?.open, {timeout: 5000});
      await page.waitForTimeout(250);
      const stemAfterApply = await page.locator(`.question[data-q="${firstQId}"] .stem-editor`).textContent();
      assert(/Hãy tính giá trị biểu thức/i.test(stemAfterApply || ''), 'Chấp nhận diff phải cập nhật thân câu');

      // Re-open diff and trigger undo-from-diff (or test undo-ai button on chat)
      await sendPatchPrompt('Viết lại câu 1 thêm một bước.');
      await page.locator('#dialog [data-action="undo-from-diff"]').click();
      await page.waitForFunction(() => !document.querySelector('#dialog')?.open, {timeout: 5000});
      await page.waitForTimeout(250);
      const stemAfterUndo = await page.locator(`.question[data-q="${firstQId}"] .stem-editor`).textContent();
      assert(!/Hãy tính giá trị biểu thức/i.test(stemAfterUndo || ''), 'Hoàn tác từ Diff phải khôi phục thân câu gốc');
      await page.unroute('**/api/assistant/patch');

      // Test REAL 409 conflicts on backend endpoints!
      allowExpectedHttp = true;
      const conflictResults = await page.evaluate(async (eid) => {
        const kv = await (await fetch('/api/kv?key=state')).json();
        const staleKv = await fetch('/api/kv', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json', 'If-Match': '0'},
          body: JSON.stringify({key: 'state', value: kv.value}),
        });
        const staleConfigPatch = await fetch('/api/assistant/patch', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-PoC-Config': 'stale-fingerprint'},
          body: JSON.stringify({}),
        });
        const staleReverse = await fetch(`/api/exams/${eid}/reverse-matrix`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({baseRevision: 0}),
        });
        return {
          kv409: staleKv.status,
          patch409: staleConfigPatch.status,
          reverse409: staleReverse.status,
        };
      }, originalStemAndBlocks.examId);
      allowExpectedHttp = false;

      assert.equal(conflictResults.kv409, 409, 'PUT /api/kv stale If-Match phải trả 409');
      assert.equal(conflictResults.patch409, 409, 'POST /api/assistant/patch stale X-PoC-Config phải trả 409');
      assert.equal(conflictResults.reverse409, 409, 'POST reverse-matrix stale baseRevision phải trả 409');

      summary.pillars.p4 = {
        qActionsDesktop1440,
        qActionsDesktop1280,
        qActionsMobile,
        ctxSelectedBadge,
        ctxModes,
        diffColsCount,
        conflictResults,
      };
    } catch (err) {
      allowExpectedHttp = false;
      recordFail('Pillar 4 (Thao tác nhanh, Composer, Context, Diff 2 cột & 409)', err);
    }

    // =========================================================================
    // PILLAR 5: Decimal matrix (0,40 + 9,60), + Nhánh (Tự chọn A/B) & P2 reverse_matrix warnings
    // =========================================================================
    try {
      // Seed clean 4-question [1, 2, 3, 4]đ exam inside same topic+type to trigger reverse_matrix pointConflict + warnings!
      const p5Prep = await page.evaluate(async (pngUri) => {
        const kv = await (await fetch('/api/kv?key=state')).json();
        const st = structuredClone(kv.value);
        const ex = st.exams.find((e) => e.id === st.current);
        ex.title = 'Đề kiểm tra học kỳ · Ma trận & Xuất';
        ex.questions = [1, 2, 3, 4].map((pts, idx) => ({
          id: `00000000-0000-4000-8000-00000000010${idx + 1}`,
          v: 1,
          type: 'mcq',
          topic: 'Hàm số và đồ thị',
          level: 0,
          points: pts,
          stem:
            idx === 0
              ? 'Câu $1$: Tính giá trị $f(2)=x^2+\\frac{1}{2}$ khi $x=2$.'
              : `Câu ${idx + 1}: Chọn phương án đúng (${pts} điểm).`,
          options: ['Phương án A', 'Phương án B', 'Phương án C', 'Phương án D'],
          answer: idx % 4,
          answerKnown: true,
          explanation: `GIAI_THICH_BI_MAT_GV_991 câu ${idx + 1}`,
          rubric: idx === 0 ? [{text: 'BAREM_BI_MAT_GV_882', points: pts}] : [],
          ...(idx === 0
            ? {
                tables: [
                  {
                    id: 'tbl-export-1',
                    rows: [[{data: pngUri, caption: 'Hình minh họa bảng'}]],
                  },
                ],
              }
            : {}),
        }));
        ex.matrix = [
          {topic: 'Hàm số và đồ thị', type: 'mcq', points: 0.4, targets: [1, 0, 0]},
          {topic: 'Hình học phẳng', type: 'essay', points: 9.6, targets: [0, 1, 0]},
        ];
        ex.matrixConfirmed = false;
        const put = await fetch('/api/kv', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json', 'If-Match': String(kv.revision)},
          body: JSON.stringify({key: 'state', value: st}),
        });
        return {status: put.status};
      }, SAMPLE_PNG_DATA_URI);
      assert.equal(p5Prep.status, 200);
      await page.reload({waitUntil: 'networkidle'});
      await waitReady();

      await page.locator('[data-action="workflow-matrix"]:visible, [data-action="matrix"]:visible').first().click();
      await page.waitForSelector('#dialog[open] #matrix-form', {timeout: 8000});

      // Verify 0.40 + 9.60 live total and cycle + Nhánh (Tự chọn A / Tự chọn B)
      const ptInputs = page.locator('#matrix-rows tr[data-matrix-row] [name="matrix-points"]');
      assert((await ptInputs.count()) >= 2, 'Ma trận phải có tối thiểu 2 dòng để nhập 0,40 + 9,60');
      await ptInputs.nth(0).fill('0.40');
      await ptInputs.nth(1).fill('9.60');
      await ptInputs.nth(1).dispatchEvent('change');

      // Click + Nhánh on row 0 (Tự chọn A) and twice on row 1 (Tự chọn A -> Tự chọn B)
      const branchBtns = page.locator('#matrix-rows tr[data-matrix-row] [data-action="matrix-cycle-group"]');
      await branchBtns.nth(0).click();
      await branchBtns.nth(1).click();
      await branchBtns.nth(1).click();
      await page.waitForTimeout(150);

      const branchGroups = await page.evaluate(() =>
        [...document.querySelectorAll('#matrix-rows tr[data-matrix-row]')].map((tr) => tr.dataset.choiceGroup || ''),
      );
      assert.equal(branchGroups[0], 'Tự chọn A', 'Dòng 1 sau 1 lần bấm + Nhánh phải là Tự chọn A');
      assert.equal(branchGroups[1], 'Tự chọn B', 'Dòng 2 sau 2 lần bấm + Nhánh phải là Tự chọn B');

      const summaryDecimalText = ((await page.locator('#matrix-live-summary').textContent()) || '').trim();
      assert(/10(?:[.,]00?)?\s*đ/i.test(summaryDecimalText) || /10/.test(summaryDecimalText), `Tổng điểm ma trận phải hiển thị 10đ, thực tế: ${summaryDecimalText}`);

      // Trigger reverse-matrix on the [1, 2, 3, 4]đ exam!
      await page.locator('#matrix-form [data-action="reverse-matrix"]').click();
      await page.waitForSelector('#dialog[open] #matrix-reverse-warnings', {timeout: 10000});
      await page.waitForTimeout(200);

      const reverseReportUI = await page.evaluate(() => {
        const dialogBody = document.querySelector('#dialog .modal-body') || document.querySelector('#dialog');
        const warnBanner = document.querySelector('#matrix-reverse-warnings');
        const dlgRect = dialogBody?.getBoundingClientRect();
        const warnRect = warnBanner?.getBoundingClientRect();
        const flags = [...document.querySelectorAll('#matrix-rows .matrix-row-flag')].map((n) => ({
          flagType: n.dataset.rowFlag,
          text: n.textContent.trim(),
        }));
        return {
          bannerText: warnBanner?.textContent?.trim() || '',
          bannerVisibleTop:
            dlgRect && warnRect ? warnRect.top >= dlgRect.top - 2 && warnRect.bottom <= window.innerHeight : false,
          warnTop: warnRect ? Math.round(warnRect.top) : null,
          dlgTop: dlgRect ? Math.round(dlgRect.top) : null,
          flags,
        };
      });
      await shot('matrixWarnings', 'redesign-matrix-warnings.png');

      if (!reverseReportUI.bannerVisibleTop) {
        recordBug(
          'ui-architect',
          'matrix-reverse-warnings-clip',
          'Cảnh báo #matrix-reverse-warnings vẫn bị cuộn/cắt mép trên trong modal Ma trận',
          reverseReportUI,
        );
      }

      assert(
        /Lệch điểm|cảnh báo|kiểm lại/i.test(reverseReportUI.bannerText),
        `Banner #matrix-reverse-warnings phải cảnh báo giáo viên: ${reverseReportUI.bannerText}`,
      );
      assert(
        reverseReportUI.flags.some((f) => /Lệch điểm/i.test(f.text)),
        `Phải có .matrix-row-flag ghi "Lệch điểm": ${JSON.stringify(reverseReportUI.flags)}`,
      );

      await page.locator('#dialog button[data-action="close"]').first().click();
      await page.waitForFunction(() => !document.querySelector('#dialog')?.open, {timeout: 5000});

      summary.pillars.p5 = {
        branchGroups,
        summaryDecimalText,
        reverseReportUI,
      };
    } catch (err) {
      recordFail('Pillar 5 (Ma trận thập phân, 2 nhánh & cảnh báo reverse_matrix)', err);
    }

    // =========================================================================
    // PILLAR 6: Student & Teacher Word / PDF exports, Landscape A4 Matrix/Spec, QR Pack KEY|V1|
    // =========================================================================
    try {
      await page.setViewportSize({width: 1440, height: 900});
      await page.locator('[data-action="export"]:visible').first().click();
      await page.waitForSelector('#dialog[open] .export-cards-grid', {timeout: 8000});
      await page.waitForTimeout(500);
      await shot('exportModal', 'redesign-export-modal.png');

      // Intercept /api/save-export & /api/exports/matrix-specification & /api/exports/tnmaker-pack URLs so we fetch exact generated artifacts
      const ensureExportModal = async () => {
        if (!(await page.locator('#dialog[open] .export-cards-grid').count())) {
          const backBtn = page.locator('#dialog[open] [data-action="export"]');
          if (await backBtn.count()) {
            await backBtn.first().click();
          } else {
            if (await page.locator('#dialog[open]').count()) {
              await page.evaluate(() => document.querySelector('#dialog')?.close());
            }
            await page.locator('[data-action="export"]:visible').first().click();
          }
          await page.waitForSelector('#dialog[open] .export-cards-grid', {timeout: 8000});
        }
      };

      const exportCapture = async (clickFn, {isDirectDownload = false} = {}) => {
        await ensureExportModal();
        const dlPromise = isDirectDownload ? page.waitForEvent('download', {timeout: 30000}) : null;
        if (dlPromise) dlPromise.catch(() => {});
        const respPromise = page.waitForResponse(
          (r) =>
            r.url().includes('/api/save-export') ||
            r.url().includes('/api/exports/matrix-specification') ||
            r.url().includes('/api/exports/tnmaker-pack'),
          {timeout: 30000},
        );
        respPromise.catch(() => {});
        await clickFn();
        const resp = await respPromise;
        if (resp.status() !== 200) {
          const errText = await resp.text().catch(() => '');
          throw new Error(`Export API ${resp.url()} trả ${resp.status()}: ${errText}`);
        }
        if (isDirectDownload) {
          const dl = await dlPromise;
          const dlPath = await dl.path();
          const buf = fs.readFileSync(dlPath);
          return {json: {url: resp.url(), suggestedFilename: dl.suggestedFilename()}, buf};
        }
        const json = await resp.json();
        const fileRes = await fetch(`${baseUrl}${json.url}`);
        assert.equal(fileRes.status, 200, `Tải tệp ${json.url} phải 200`);
        const buf = Buffer.from(await fileRes.arrayBuffer());
        return {json, buf};
      };

      // 1) Student Word (.docx)
      const studentDocx = await exportCapture(() =>
        page.locator('#dialog [data-action="export-file"][data-teacher="false"][data-format="docx"]').click(),
      );
      const docxZip = await JSZip.loadAsync(studentDocx.buf);
      const docxXml = await docxZip.file('word/document.xml').async('string');
      const docxMedia = Object.keys(docxZip.files).filter((k) => k.startsWith('word/media/'));
      const docxHasDrawing = /<w:drawing\b/.test(docxXml);
      const docxHasOMath = /<m:oMath\b/.test(docxXml);
      const docxHasLeak =
        /GIAI_THICH_BI_MAT_GV_991|BAREM_BI_MAT_GV_882|HƯỚNG DẪN CHẤM/i.test(docxXml);
      assert(docxHasDrawing && docxMedia.length >= 1, 'Word HS phải giữ ảnh trong ô bảng (w:drawing + word/media)');
      assert(docxHasOMath, 'Word HS phải giữ công thức m:oMath');
      assert(!docxHasLeak, 'Word HS KHÔNG được rò đáp án/lời giải giáo viên');

      // 2) Student PDF (.pdf)
      const studentPdf = await exportCapture(() =>
        page.locator('#dialog [data-action="export-file"][data-teacher="false"][data-format="pdf"]').click(),
      );
      const studentPdfInfo = await pdfInspect(studentPdf.buf);
      const studentPdfLeak =
        /GIAI_THICH_BI_MAT_GV_991|BAREM_BI_MAT_GV_882|HƯỚNG DẪN CHẤM/i.test(studentPdfInfo.text);
      assert(!studentPdfLeak, 'PDF HS KHÔNG được rò đáp án/lời giải');
      assert(!studentPdfInfo.hasRawBase64, 'PDF HS KHÔNG được lộ chuỗi data:image/base64');
      assert(
        studentPdfInfo.imagePaintCount >= 1 || studentPdfInfo.rawXObjectImageCount >= 1,
        'PDF HS phải chứa ảnh nhúng thật từ ô bảng',
      );

      // 3) Teacher PDF (.pdf)
      const teacherPdf = await exportCapture(() =>
        page.locator('#dialog [data-action="export-file"][data-teacher="true"][data-format="pdf"]').click(),
      );
      const teacherPdfInfo = await pdfInspect(teacherPdf.buf);
      assert(
        /GIAI_THICH_BI_MAT_GV_991/.test(teacherPdfInfo.text),
        'PDF GV phải chứa lời giải/đáp án giáo viên',
      );

      // 4) A4 Landscape Matrix & Specification (HTML + DOCX)
      await ensureExportModal();
      await page.locator('#export-extended-a4 summary').click();
      await page.locator('#export-matrix-landscape').check();
      const matrixSpecHtml = await exportCapture(
        () => page.locator('#dialog [data-action="export-extended"][data-kind="matrix-specification"][data-format="html"]').click(),
        {isDirectDownload: true},
      );
      const matrixHtmlText = matrixSpecHtml.buf.toString('utf8');
      assert(
        /size:\s*A4\s+landscape/i.test(matrixHtmlText),
        `Ma trận & Đặc tả HTML A4 ngang phải có @page A4 landscape (len=${matrixHtmlText.length}, head=${matrixHtmlText.slice(0, 400)})`,
      );

      await ensureExportModal();
      await page.locator('#export-extended-a4').evaluate((el) => {
        el.open = true;
      });
      await page.locator('#export-matrix-landscape').check();
      const matrixSpecDocx = await exportCapture(
        () => page.locator('#dialog [data-action="export-extended"][data-kind="matrix-specification"][data-format="docx"]').click(),
        {isDirectDownload: true},
      );
      const matrixZip = await JSZip.loadAsync(matrixSpecDocx.buf);
      const matrixXml = await matrixZip.file('word/document.xml').async('string');
      assert(/w:orient="landscape"/i.test(matrixXml), 'Ma trận & Đặc tả Word phải có w:orient="landscape"');

      // 5) QR Key Pack (.zip) KEY|V1|
      await ensureExportModal();
      await page.locator('#export-extended-a4').evaluate((el) => {
        el.open = true;
      });
      const qrPack = await exportCapture(() =>
        page.locator('#dialog #export-extended-a4 [data-action="export-tnmaker"]').first().click(),
      );
      assert(String(qrPack.json.qrPayload || '').startsWith('KEY|V1|'), `QR payload phải bắt đầu bằng KEY|V1|, nhận: ${qrPack.json.qrPayload}`);
      const qrZip = await JSZip.loadAsync(qrPack.buf);
      const xlsxBytes = await qrZip.file('DapAn.xlsx')?.async('nodebuffer');
      const qrPngBytes = await qrZip.file('QR_DapAn.png')?.async('nodebuffer');
      assert(xlsxBytes && qrPngBytes, 'Gói khóa QR .zip phải có DapAn.xlsx và QR_DapAn.png');
      assert.equal(qrPngBytes.subarray(0, 4).toString('hex'), '89504e47', 'QR_DapAn.png phải đúng chữ ký PNG');
      const xlsxZip = await JSZip.loadAsync(xlsxBytes);
      const sheet1Xml = await xlsxZip.file('xl/worksheets/sheet1.xml').async('string');
      assert(/MaDe/.test(sheet1Xml) && /DapAn/.test(sheet1Xml), 'DapAn.xlsx phải có cột MaDe và DapAn');

      summary.pillars.p6 = {
        studentDocx: {docxHasDrawing, docxHasOMath, docxMediaCount: docxMedia.length, docxHasLeak},
        studentPdf: {
          pages: studentPdfInfo.pages,
          imagePaintCount: studentPdfInfo.imagePaintCount,
          rawXObjectImageCount: studentPdfInfo.rawXObjectImageCount,
          studentPdfLeak,
        },
        teacherPdf: {
          pages: teacherPdfInfo.pages,
          hasTeacherAnswer: /GIAI_THICH_BI_MAT_GV_991/.test(teacherPdfInfo.text),
        },
        matrixSpecLandscape: {
          htmlLandscape: /size:\s*A4\s+landscape/i.test(matrixHtmlText),
          docxLandscape: /w:orient="landscape"/i.test(matrixXml),
        },
        qrPack: {
          qrPayload: qrPack.json.qrPayload,
          files: Object.keys(qrZip.files),
        },
      };
    } catch (err) {
      recordFail('Pillar 6 (Xuất Word/PDF HS & GV, A4 ngang & Gói khóa QR)', err);
    }

    await context.close();
  } finally {
    if (browser) await browser.close();
    await stopServer(server.proc);
    fs.rmSync(tmpDataDir, {recursive: true, force: true});
  }

  const ok =
    summary.bugs.length === 0 &&
    summary.failures.length === 0 &&
    summary.consoleErrors.length === 0 &&
    summary.pageErrors.length === 0 &&
    summary.unexpectedHttpErrors.length === 0;

  console.log(JSON.stringify({ok, ...summary}, null, 2));
  process.exit(ok ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
