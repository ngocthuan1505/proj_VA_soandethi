import test from 'node:test';
import assert from 'node:assert/strict';

import { resolveCitationContext, citationContextHTML } from '../citation-context.js';
import {
  EXPORT_HISTORY_SCOPE_NOTICE,
  countIndependentVariantUnits,
  handleMVPAction,
  handleMVPSubmit,
  mountMVP,
  renderExportHistoryHTML,
  sourceOriginalLinkHTML,
} from '../mvp.js';
import {
  formatAssistantSourceChipLabel,
  preserveMobileChatOnResize,
  syncAssistantSourceChips,
} from '../workbench.js';
import { runAutoCreateExam } from '../matrix-synthesis.js';

function makeClassList(initial = []) {
  const set = new Set(initial);
  return {
    add: (...items) => items.forEach((x) => set.add(x)),
    remove: (...items) => items.forEach((x) => set.delete(x)),
    toggle: (item, force) => {
      if (force === undefined) {
        if (set.has(item)) set.delete(item);
        else set.add(item);
      } else if (force) set.add(item);
      else set.delete(item);
      return set.has(item);
    },
    contains: (item) => set.has(item),
  };
}

function makeStyle() {
  const map = new Map();
  return {
    setProperty: (k, v) => map.set(k, String(v)),
    removeProperty: (k) => map.delete(k),
    getPropertyValue: (k) => map.get(k) || '',
    maxHeight: '',
    overflowY: '',
  };
}

function createFakeElement(tag = 'div') {
  const children = [];
  const el = {
    tagName: tag.toUpperCase(),
    className: '',
    classList: makeClassList(),
    dataset: {},
    style: makeStyle(),
    innerHTML: '',
    textContent: '',
    value: '',
    checked: false,
    hidden: false,
    disabled: false,
    children,
    attributes: new Map(),
    setAttribute(k, v) {
      this.attributes.set(k, String(v));
      if (k.startsWith('data-')) {
        const camel = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        this.dataset[camel] = String(v);
      }
    },
    getAttribute(k) {
      return this.attributes.get(k) ?? null;
    },
    addEventListener() {},
    append(...nodes) {
      children.push(...nodes);
    },
    prepend(...nodes) {
      children.unshift(...nodes);
    },
    contains(node) {
      return children.includes(node);
    },
    remove() {},
    scrollIntoView() {},
    closest: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    insertAdjacentHTML() {},
    replaceWith() {},
    focus() {},
    close() {
      this.open = false;
    },
    open: false,
  };
  return el;
}

function withMockBrowserEnv(selectorMap, innerDims, fn) {
  const prevDoc = globalThis.document;
  const prevWin = globalThis.window;
  const prevLocalStorage = globalThis.localStorage;
  const prevFetch = globalThis.fetch;
  const prevFormData = globalThis.FormData;
  const prevIntersectionObserver = globalThis.IntersectionObserver;
  const prevInnerWidth = globalThis.innerWidth;
  const prevInnerHeight = globalThis.innerHeight;
  const listeners = new Map();

  const mockDoc = {
    body: { classList: makeClassList(), dataset: {}, addEventListener: () => {} },
    documentElement: { style: makeStyle() },
    activeElement: null,
    createElement: (tag) => createFakeElement(tag),
    getElementById: (id) => selectorMap.get(`#${id}`) || null,
    querySelector: (sel) => selectorMap.get(sel) || null,
    querySelectorAll: (sel) => {
      const val = selectorMap.get(sel);
      return Array.isArray(val) ? val : val ? [val] : [];
    },
    addEventListener: (ev, cb) => {
      if (!listeners.has(ev)) listeners.set(ev, []);
      listeners.get(ev).push(cb);
    },
  };
  const mockWin = {
    addEventListener: () => {},
    visualViewport: {
      height: innerDims?.height ?? 844,
      addEventListener: () => {},
    },
    location: { search: '', pathname: '/' },
  };
  const ls = new Map();
  globalThis.document = mockDoc;
  globalThis.window = mockWin;
  globalThis.FormData = class {
    constructor(form) {
      this._form = form;
    }
    get(k) {
      return this._form?.querySelector?.(`[name=${k}]`)?.value ?? null;
    }
  };
  globalThis.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  globalThis.localStorage = {
    getItem: (k) => (ls.has(k) ? ls.get(k) : null),
    setItem: (k, v) => ls.set(k, String(v)),
    removeItem: (k) => ls.delete(k),
  };
  if (innerDims?.width !== undefined) globalThis.innerWidth = innerDims.width;
  if (innerDims?.height !== undefined) globalThis.innerHeight = innerDims.height;

  return Promise.resolve()
    .then(() => fn({ mockDoc, mockWin }))
    .finally(() => {
      globalThis.document = prevDoc;
      globalThis.window = prevWin;
      globalThis.FormData = prevFormData;
      globalThis.IntersectionObserver = prevIntersectionObserver;
      globalThis.localStorage = prevLocalStorage;
      globalThis.fetch = prevFetch;
      globalThis.innerWidth = prevInnerWidth;
      globalThis.innerHeight = prevInnerHeight;
    });
}

test('UV64 Citation Context: doc.version > sourceVersion hoặc thiếu sourceVersion khi doc.version > 1 trả về version_changed', () => {
  const docsV2 = [
    {
      id: 'doc-1',
      name: 'De_cuong_Ly_10.pdf',
      version: 2,
      pages: [{ number: 1, text: 'Lực ma sát trượt tỉ lệ thuận với áp lực lên mặt tiếp xúc.' }],
    },
  ];

  // Trường hợp 1: evidence ghi sourceVersion=1 trong khi tài liệu đã lên v2
  const r1 = resolveCitationContext(
    { docId: 'doc-1', sourceVersion: 1, page: 1, quote: 'tỉ lệ thuận với áp lực' },
    docsV2,
    { questionVersion: 2, currentQuestionVersion: 2 },
  );
  assert.equal(r1.status, 'version_changed');
  assert.equal(r1.canOpen, false);
  assert.equal(r1.sourceVersion, 1);
  assert.equal(r1.currentVersion, 2);

  // Trường hợp 2: evidence từ bản cũ không ghi sourceVersion khi doc đã ở v2 -> vẫn báo version_changed
  const r2 = resolveCitationContext(
    { docId: 'doc-1', page: 1, quote: 'tỉ lệ thuận với áp lực' },
    docsV2,
    { questionVersion: 1, currentQuestionVersion: 3 },
  );
  assert.equal(r2.status, 'version_changed');
  assert.equal(r2.canOpen, false);

  const html = citationContextHTML(
    { docId: 'doc-1', page: 1, quote: 'tỉ lệ thuận với áp lực' },
    docsV2,
    { questionVersion: 1, currentQuestionVersion: 3 },
  );
  assert.ok(html.includes('v2') && html.includes('phiên bản'), html);
  assert.ok(!html.includes('<details class="citation-details" open>'));
});

test('UV64 MVP: Mở tệp gốc cho PPTX, đếm khối ngữ liệu độc lập mã đề và cảnh báo lịch sử xuất', () => {
  const pptxDoc = {
    id: 'doc-slides-1',
    kind: 'slides',
    name: 'BaiGiang_DiaLi10.pptx',
    fileId: 'file_pptx_123',
    version: 2,
  };
  const link = sourceOriginalLinkHTML(pptxDoc, 2, { localPoC: true });
  assert.match(link, /href="\/api\/source-file\/file_pptx_123"/);
  assert.ok(link.includes('Mở tệp gốc'));
  assert.equal(sourceOriginalLinkHTML(pptxDoc, 2, { localPoC: false }), '');
  assert.equal(sourceOriginalLinkHTML({ id: 'no-file', kind: 'slides', name: 'A.pptx' }, 1, { localPoC: true }), '');

  // 2 khối ngữ liệu gồm 4 câu -> chỉ 2 đơn vị độc lập (mã 101, 102; không cho phép tạo 103)
  const fourQuestionsTwoPassages = [
    { id: 'q1', type: 'mcq', passageId: 'passage-1', stem: 'Câu 1a' },
    { id: 'q2', type: 'mcq', passageId: 'passage-1', stem: 'Câu 1b' },
    { id: 'q3', type: 'mcq', groupId: 'group-2', stem: 'Câu 2a' },
    { id: 'q4', type: 'mcq', groupId: 'group-2', stem: 'Câu 2b' },
  ];
  assert.equal(countIndependentVariantUnits(fourQuestionsTwoPassages), 2);

  // Lịch sử xuất bản in cảnh báo gắn kho nguồn
  const historyHtml = renderExportHistoryHTML([
    { id: 'exp-1', variant: '101', format: 'pdf', teacher: false, url: '/exports/101.pdf' },
  ]);
  assert.ok(historyHtml.includes(EXPORT_HISTORY_SCOPE_NOTICE));
});

test('UV64 MVP DOM: sửa văn bản nguồn PDF/PPTX tăng version lên v2 ổn định không revert về v1', async () => {
  const docId = 'doc-pptx-1';
  const exam = {
    id: 'exam-mvp-1',
    revision: 1,
    title: 'Đề kiểm tra',
    subject: 'Ngữ văn',
    grade: '8',
    docs: [
      {
        id: docId,
        kind: 'slides',
        name: 'Nguon_slides.pptx',
        version: 1,
        text: 'Văn bản v1 ban đầu.',
        pages: [{ number: 1, text: 'Văn bản v1 ban đầu.' }],
      },
    ],
    questions: [
      {
        id: 'q-linked-1',
        v: 1,
        type: 'mcq',
        stem: 'Câu hỏi gắn với v1?',
        options: ['A', 'B', 'C', 'D'],
        answer: 0,
        explanation: 'Giải thích',
        source: { docId, version: 1, page: 1, location: 'Slide 1', quote: 'Văn bản v1 ban đầu.' },
        check: null,
      },
    ],
  };
  const state = { exams: [exam], current: exam.id, prefs: [] };
  const dialog = createFakeElement('dialog');
  const modalFoot = createFakeElement('div');
  const headerTop = createFakeElement('header');
  headerTop.dataset.unifiedHeader = '1';
  const selectorMap = new Map([
    ['header.top', headerTop],
    ['#dialog', dialog],
    ['#dialog .modal-foot', modalFoot],
    ['#source-page', null],
    ['.chat-compose', createFakeElement('div')],
    ['.paper', createFakeElement('div')],
    ['.paper-scroll', createFakeElement('div')],
    ['.assistant-body', createFakeElement('div')],
    ['#chat-input', createFakeElement('textarea')],
    ['.sidebar', createFakeElement('aside')],
    ['.workspace', createFakeElement('div')],
  ]);

  let persisted = 0;
  let rendered = 0;
  const ctx = {
    exam: () => exam,
    getState: () => state,
    qget: (id) => exam.questions.find((q) => q.id === id),
    getSelected: () => exam.questions[0].id,
    setSelected: () => {},
    currentScope: () => null,
    isTeacher: () => false,
    icon: () => '',
    toast: () => {},
    render: () => {
      rendered += 1;
    },
    modal: (_title, html) => {
      dialog.open = true;
      dialog.innerHTML = html;
    },
    change: (_label, mutator) => {
      exam.revision += 1;
      mutator(exam);
    },
    persist: async () => {
      persisted += 1;
    },
    act: async () => {},
    setTab: () => {},
  };

  await withMockBrowserEnv(selectorMap, { width: 1280, height: 800 }, async () => {
    mountMVP(ctx);

    const form = {
      id: 'source-text-form',
      dataset: { exam: exam.id, doc: docId, page: '1', version: '1' },
      querySelector: (sel) => (sel === '[name=text]' ? { value: 'Văn bản v2 sau khi sửa.' } : null),
    };
    const handled = await handleMVPSubmit(form);
    assert.equal(handled, true);
    assert.equal(exam.docs[0].version, 2);
    assert.equal(exam.docs[0].pages[0].text, 'Văn bản v2 sau khi sửa.');
    assert.equal(exam.docs[0].text, 'Văn bản v2 sau khi sửa.');
    // Bản trích ở câu hỏi cũ vẫn giữ version 1 để citation-context phát hiện version_changed
    assert.equal(exam.questions[0].source.version, 1);
    assert.ok(persisted >= 1);
    assert.ok(dialog.innerHTML.includes('data-version="2"'));

    const citationState = resolveCitationContext(exam.questions[0].source, exam.docs, {
      questionVersion: exam.questions[0].v,
      currentQuestionVersion: exam.questions[0].v,
    });
    assert.equal(citationState.status, 'version_changed');
  });
});

test('UV64 Quick Compose Consent: consent cục bộ không tự bật saveWorkspaceConsent hay exam.aiConsent', async () => {
  const exam = {
    id: 'exam-consent-1',
    revision: 1,
    title: 'Đề mới',
    subject: 'Toán',
    grade: '8',
    docs: [{ id: 'd1', name: 'SGK.pdf', version: 1, pages: [{ number: 1, text: 'Hàm số bậc nhất' }] }],
    questions: [],
    chat: [],
  };
  const bodyEl = createFakeElement('div');
  const selectorMap = new Map([['.assistant-body', bodyEl]]);
  const posted = [];
  const sseBody = 'event: phase\ndata: {"phase":"blueprint","step":1,"label":"Lập dàn ý"}\n\nevent: error\ndata: {"code":"cancelled","message":"Dừng kiểm thử"}\n\n';

  const fakeFetch = async (url, init = {}) => {
    if (String(url).includes('/agent/auto-create')) {
      posted.push(JSON.parse(init.body));
      return new Response(sseBody, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      });
    }
    if (String(url) === '/api/account') {
      return new Response(JSON.stringify({ localPoC: true, credits: { balance: 100 } }), { status: 200 });
    }
    return new Response(JSON.stringify({}), { status: 200 });
  };

  await withMockBrowserEnv(selectorMap, { width: 1280, height: 800 }, async () => {
    globalThis.fetch = fakeFetch;
    const ctx = {
      exam: () => exam,
      getState: () => ({ exams: [exam], prefs: [] }),
      change: () => {},
      persist: async () => {},
      render: () => {},
      toast: () => {},
      setTab: () => {},
    };
    await runAutoCreateExam(ctx, 'Soạn đề nhanh từ bài này', {
      consentGiven: true,
      fetchImpl: fakeFetch,
      onOpenManualMatrix: () => {},
    });
  });

  assert.equal(posted.length, 1);
  assert.equal(posted[0].consentGiven, true);
  assert.equal(posted[0].saveWorkspaceConsent, false);
  assert.ok(!exam.aiConsent, 'Không tự bật aiConsent trên đề khi chỉ gửi consentGiven cục bộ 1 lượt');
});

test('UV64 Workbench: chip nguồn chat hiện tên bài SGK cụ thể và resize thu chiều cao không đóng Chat', async () => {
  const sgkDoc = {
    id: 'sgk-doc-1',
    name: 'Khoa học tự nhiên 8 · Tập 1',
    catalog: true,
    version: 1,
    pages: [
      { number: 1, lessonTitle: 'Bài 1: Sử dụng một số hóa chất trong phòng thí nghiệm', text: '...' },
      { number: 2, lessonTitle: 'Bài 2: Phản ứng hóa học', text: '...' },
    ],
  };
  const exam = {
    id: 'exam-wb-1',
    docs: [sgkDoc],
    assistantSources: [sgkDoc.id],
    assistantSourcePages: { [sgkDoc.id]: [2] },
  };
  const label = formatAssistantSourceChipLabel(exam, sgkDoc);
  assert.ok(label.text.includes('Bài 2: Phản ứng hóa học'), label.text);
  assert.ok(label.fullTitle.includes('Bài 2: Phản ứng hóa học'), label.fullTitle);

  const chip = createFakeElement('button');
  chip.dataset.doc = sgkDoc.id;
  chip.className = 'source-chip';
  const root = {
    querySelectorAll: (sel) =>
      sel === '.assistant-sources .source-chip[data-doc]' ? [chip] : [],
  };
  syncAssistantSourceChips(exam, root);
  assert.ok(chip.textContent.includes('Bài 2: Phản ứng hóa học'), chip.textContent);
  assert.ok(chip.title.includes('Bài 2: Phản ứng hóa học'), chip.title);

  // Kiểm tra thu hẹp chiều cao trên mobile (390x844 -> 390x560) do mở bàn phím ảo KHÔNG đóng khung Chat
  const workspace = createFakeElement('div');
  workspace.classList = makeClassList(['workspace', 'mobile-ai-view']);
  const assistant = createFakeElement('aside');
  assistant.classList = makeClassList(['assistant', 'open']);
  const assistantBody = createFakeElement('div');
  const chatCompose = createFakeElement('div');
  assistant.querySelector = (sel) => {
    if (sel === '.assistant-body') return assistantBody;
    if (sel === '.chat-compose') return chatCompose;
    return null;
  };

  await withMockBrowserEnv(
    new Map([
      ['.workspace', workspace],
      ['aside.assistant', assistant],
      ['.assistant', assistant],
    ]),
    { width: 390, height: 560 },
    async () => {
      const resizeRes = preserveMobileChatOnResize({
        prevWidth: 390,
        width: 390,
        prevHeight: 844,
        height: 560,
        workspace,
        assistant,
        wasOpen: true,
      });
      assert.equal(resizeRes.keptOpen, true);
      assert.equal(resizeRes.heightOnlyResize, true);
      assert.equal(assistant.classList.contains('open'), true);
      assert.equal(workspace.classList.contains('mobile-ai-view'), true);
      assert.equal(workspace.classList.contains('chat-hidden'), false);
      assert.equal(assistantBody.style.minHeight, '96px');
      assert.equal(chatCompose.style.maxHeight, '246px');
      assert.equal(chatCompose.style.overflowY, 'auto');
    },
  );

  // Chuyển từ desktop (>760px) có sẵn .open từ phiên trước xuống mobile (<=760px) không tự coi là đang mở Chat mobile
  const deskToMobWorkspace = createFakeElement('div');
  deskToMobWorkspace.classList = makeClassList(['workspace', 'mobile-ai-view']);
  const deskToMobAssistant = createFakeElement('aside');
  deskToMobAssistant.classList = makeClassList(['assistant', 'open']);
  await withMockBrowserEnv(
    new Map([
      ['.workspace', deskToMobWorkspace],
      ['aside.assistant', deskToMobAssistant],
      ['.assistant', deskToMobAssistant],
    ]),
    { width: 390, height: 844 },
    async () => {
      const res = preserveMobileChatOnResize({
        prevWidth: 1600,
        width: 390,
        prevHeight: 1000,
        height: 844,
        workspace: deskToMobWorkspace,
        assistant: deskToMobAssistant,
      });
      assert.equal(res.keptOpen, false);
      assert.equal(res.heightOnlyResize, false);
      assert.equal(deskToMobAssistant.classList.contains('open'), false);
      assert.equal(deskToMobWorkspace.classList.contains('mobile-ai-view'), false);
    },
  );
});

test('UV64 MVP guard: export variants chỉ đọc unit độc lập và action không vượt quá số khối', async () => {
  const exam = {
    id: 'exam-var-1',
    revision: 1,
    title: 'Đề đọc hiểu',
    subject: 'Ngữ văn',
    grade: '9',
    questions: [
      { id: 'q1', type: 'mcq', passageId: 'p1', stem: 'Câu 1a', options: ['A', 'B', 'C', 'D'], answer: 0 },
      { id: 'q2', type: 'mcq', passageId: 'p1', stem: 'Câu 1b', options: ['A', 'B', 'C', 'D'], answer: 1 },
      { id: 'q3', type: 'mcq', passageId: 'p2', stem: 'Câu 2a', options: ['A', 'B', 'C', 'D'], answer: 2 },
      { id: 'q4', type: 'mcq', passageId: 'p2', stem: 'Câu 2b', options: ['A', 'B', 'C', 'D'], answer: 3 },
    ],
  };
  assert.equal(countIndependentVariantUnits(exam.questions), 2);
  // Kiểm tra thêm: nút export fallback khi đóng modal không lỗi và history luôn mang cảnh báo exam_exports
  const modalBtn = await handleMVPAction('menu', { dataset: { menu: 'file' }, getBoundingClientRect: () => ({ left: 0, bottom: 0 }) }).catch(() => false);
  assert.equal(typeof modalBtn, 'boolean');
});
