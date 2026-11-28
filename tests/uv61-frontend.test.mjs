import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  parseSseRecords,
  streamAssistantChat,
  buildSuggestedActionPreview,
  confirmSuggestedActionModalHTML,
  examLibrarySearchText,
  filterAndSortLibraryExams,
  moveExamsToTrash,
  restoreExamsFromTrash,
  isTeacherOwnedDoc,
  buildFlexibleChatContext,
  stabilizeStreamingMarkdown,
} from '../workbench.js';
import {
  renderProvidersHealthHTML,
  formatProviderTestResultHTML,
  connectionSettings,
  translateProviderErrorMessage,
} from '../connections.js';
import {isRoomLaunchBlocked, roomPreflightBannerHTML} from '../exam-rooms.js';
import {stripTrueFalseOptionPrefix, renderResultReviewSectionHTML} from '../assets/exam-room.js';
import {
  PEDAGOGICAL_PROMPT_LIBRARY,
  promptLibraryHTML,
  computeAttachmentState,
  setQuestionMcqAnswer,
  buildAudioAttachmentMeta,
  audioAttachmentCardHTML,
  emptyCanvasHTML,
} from '../reference.js';
import {
  renderExportHistoryHTML,
  exportConfirmationNote,
  buildVisualTableEditorHTML,
  readVisualTableRows,
} from '../mvp.js';
import { pendingRichPreviewHTML } from '../editor.js';
import { createSketchHistory } from '../sketch-board.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const readText = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

test('UV61 CSS architecture: 3 tệp CSS sạch có tổng < 30 !important và index.html không nạp 9 CSS cũ', () => {
  const tokens = readText('assets/tokens.css');
  const layout = readText('assets/layout.css');
  const paper = readText('assets/paper.css');
  const countImp = (css) => (css.match(/!\s*important\b/gi) || []).length;
  const totalImportant = countImp(tokens) + countImp(layout) + countImp(paper);
  assert.ok(totalImportant < 30, `Tổng !important=${totalImportant}, yêu cầu < 30`);

  const html = readText('index.html');
  for (const href of ['assets/tokens.css', 'assets/katex/katex.min.css', 'assets/layout.css', 'assets/paper.css']) {
    assert.ok(html.includes(href), `index.html thiếu ${href}`);
  }
  for (const legacy of ['styles.css', 'mvp.css', 'workbench.css', 'studio.css', 'design.css', 'theme-system.css', 'usability.css', 'ui2-tokens.css', 'ui2-shell.css']) {
    assert.ok(!html.includes(`"${legacy}"`) && !html.includes(`'${legacy}'`), `index.html vẫn nạp CSS cũ ${legacy}`);
  }
  assert.ok(html.includes('id="dialog"') && html.includes('id="dialog-layer2"'));
});

test('UV61 Shell & Jargon purge: Header 1 tầng 5 không gian, giữ selector IT, bỏ tab ma docs/matrix và sạch thuật ngữ kỹ thuật', () => {
  const appSrc = readText('app.js');
  const mvpSrc = readText('mvp.js');
  assert.ok(appSrc.includes('data-unified-header="1"'));
  assert.ok(mvpSrc.includes("header?.dataset.unifiedHeader==='1'"));
  for (const req of ['design-workspace', "'Mở kho đề'", 'question-bank', 'exam-rooms', 'exam-analytics', "button('new'", 'Xuất đề']) {
    assert.ok(appSrc.includes(req), `app.js thiếu ${req}`);
  }
  assert.ok(appSrc.includes('aria-label="${esc(aria)}"'), 'app.js gắn aria-label cho nút không gian');
  assert.ok(!/data-tab="docs"|data-tab="matrix"/.test(appSrc), 'Không còn tab ma docs/matrix');
  assert.ok(!/button\(['"]export['"],[^)]*Mã đề/.test(appSrc), 'Header không gắn nhãn sai Mã đề cho nút Xuất đề');

  const files = ['app.js', 'mvp.js', 'workbench.js', 'connections.js', 'reference.js', 'design.js', 'exam-rooms.js'];
  for (const file of files) {
    const src = readText(file);
    assert.ok(!/(?:bản PoC|Điểm MVP|dùng điểm MVP|Guardrail|giải mù chéo|M01–M11|M01-M11)/i.test(src), `${file} còn chứa thuật ngữ kỹ thuật lộ cho giáo viên`);
  }
});

test('UV61 SSE Stream & Fallback: parseSseRecords, streaming delta/meta/done và fallback /api/assistant/chat khi 404/503', async () => {
  const first = parseSseRecords('event: meta\ndata: {"provider":"gemini","model":"gemini-flash"}\n\nevent: del');
  assert.equal(first.records.length, 1);
  assert.equal(first.records[0].type, 'meta');
  const second = parseSseRecords(first.rest + 'ta\ndata: {"text":"Xin chào "}\n\nevent: done\ndata: {"message":"Xin chào thầy cô","latencyMs":120}\n\n');
  assert.equal(second.records.length, 2);
  assert.equal(second.records[0].type, 'delta');
  assert.equal(second.records[1].data.message, 'Xin chào thầy cô');

  const chunks = [
    'event: meta\ndata: {"provider":"deepseek","model":"ds-v4"}\n\n',
    'event: delta\ndata: {"text":"Đáp án "}\n\n',
    'event: delta\ndata: {"text":"là B."}\n\n',
    'event: done\ndata: {"message":"Đáp án là B.","providerUsed":"deepseek","latencyMs":210}\n\n',
  ];
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    start(ctrl) {
      for (const ch of chunks) ctrl.enqueue(enc.encode(ch));
      ctrl.close();
    },
  });
  const metas = [];
  const deltas = [];
  const res = await streamAssistantChat(
    { text: 'Giải thích câu 1' },
    {
      fetchImpl: async () => new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }),
      onMeta: (m) => metas.push(m),
      onDelta: (d) => deltas.push(d),
    },
  );
  assert.equal(metas[0].provider, 'deepseek');
  assert.equal(deltas.join(''), 'Đáp án là B.');
  assert.equal(res.message, 'Đáp án là B.');

  const calls = [];
  const fallbackRes = await streamAssistantChat(
    { text: 'Fallback test' },
    {
      fetchImpl: async (url) => {
        calls.push(url);
        if (url === '/api/assistant/chat/stream') {
          return new Response(JSON.stringify({ code: 'not_migrated' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
        }
        return new Response(JSON.stringify({ message: 'Fallback thành công', providerUsed: 'ollama' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      },
    },
  );
  assert.deepEqual(calls, ['/api/assistant/chat/stream', '/api/assistant/chat']);
  assert.equal(fallbackRes.message, 'Fallback thành công');
});

test('UV61 Listening Audio: kiểm tra .mp3/.wav, giới hạn maxPlays [1..20], render trình phát và lưu vào /api/kv', () => {
  assert.throws(() => buildAudioAttachmentMeta({ filename: 'evil.exe', mimeType: 'application/x-msdownload' }), /mp3|wav/i);
  assert.throws(() => buildAudioAttachmentMeta({ filename: 'big.mp3', sizeBytes: 25 * 1024 * 1024 }), /20 MB/);
  const meta = buildAudioAttachmentMeta({ filename: 'track1.mp3', mimeType: 'audio/mpeg', sizeBytes: 102400, maxPlays: 99, title: 'Part 1 Listening' });
  assert.equal(meta.maxPlays, 20);
  assert.equal(meta.mimeType, 'audio/mpeg');
  const html = audioAttachmentCardHTML(meta, { scope: 'question', targetId: 'q1', label: 'Audio câu 1' });
  assert.ok(html.includes('<audio controls') && html.includes('Tối đa 20 lượt nghe') && html.includes('data-audio-file-id='));
  assert.ok(readText('app.js').includes("db.put('file:'+fid,dataUri)"));
});

test('UV61 Providers Health & 2-tier Connections: hiển thị 4 kênh AI và format kết quả thử kênh', () => {
  const html = renderProvidersHealthHTML({
    providers: {
      agy: { ok: true, available: true, model: 'agy-default' },
      gemini: { ok: true, keyCount: 3 },
      deepseek: { ok: false, configured: false },
      ollama: { ok: true, models: ['qwen3:8b', 'gemma3:4b'] },
    },
  });
  for (const id of ['agy', 'gemini', 'deepseek', 'ollama']) {
    assert.ok(html.includes(`data-health-card="${id}"`), `Thiếu card ${id}`);
    assert.ok(html.includes(`data-provider="${id}"`), `Thiếu nút thử kênh ${id}`);
  }
  const formatted = formatProviderTestResultHTML('ollama', { ok: true, message: 'Sẵn sàng', models: [{ name: 'qwen3:8b' }] });
  assert.equal(formatted.ok, true);
  assert.deepEqual(formatted.models, ['qwen3:8b']);
  const cfgHtml = connectionSettings({ localPoC: true, fixedRouter: {}, gemini: {}, deepseek: {}, ollama: {} });
  assert.ok(cfgHtml.includes('poc-key-vault') && cfgHtml.includes('Tầng 1') && cfgHtml.includes('Tầng 2'));
});

test('UV61 Chat Prompt Library & Safe Confirm Modals: không tự sửa đề nếu chưa bấm xác nhận', () => {
  const flatPrompts = PEDAGOGICAL_PROMPT_LIBRARY.flatMap((g) => g.items || []);
  assert.ok(flatPrompts.length >= 6);
  const plHtml = promptLibraryHTML({ subject: 'Toán', grade: '9' });
  assert.ok(plHtml.includes('prompt-library-drawer') && plHtml.includes('pick-prompt-template'));

  const exam = { id: 'e1', questions: [{ id: 'q1', stem: 'Câu gốc', options: ['A', 'B', 'C', 'D'], answer: 0 }], matrix: [{ topic: 'Hàm số', targets: [1, 0, 0, 0] }] };
  const preview = buildSuggestedActionPreview({ kind: 'propose_questions', questions: [{ stem: 'Câu mới', options: ['1', '2', '3', '4'], answer: 1 }] }, exam);
  assert.equal(preview.count, 1);
  assert.equal(exam.questions.length, 1);
  const confirmHtml = confirmSuggestedActionModalHTML({ kind: 'propose_patch', questionNumber: 1, patch: { stem: 'Câu đã sửa' } }, exam);
  assert.ok(confirmHtml.includes('data-action="confirm-chat-action"') && confirmHtml.includes('Câu gốc') && confirmHtml.includes('Câu đã sửa'));
  assert.equal(exam.questions[0].stem, 'Câu gốc');
});

test('UV61 Authoring UX: 1-click MCQ, Visual Table Editor, Empty Canvas, Export History url/isDraft/PDF', () => {
  const exam = {
    subject: 'Toán',
    grade: '9',
    questions: [
      { id: 'q1', v: 1, type: 'mcq', stem: '1+1=?', options: ['1', '2', '3', '4'], answer: 0, answerKnown: false },
      { id: 'q2', v: 1, type: 'essay', stem: 'Giải pt', options: [], answer: 0 },
    ],
  };
  const updated = setQuestionMcqAnswer(exam, 'q1', 1);
  assert.equal(updated.answer, 1);
  assert.equal(updated.answerKnown, true);
  assert.equal(updated.v, 2);
  assert.equal(setQuestionMcqAnswer(exam, 'q2', 1), null);

  const tokens = new Map();
  const tblHtml = buildVisualTableEditorHTML([[{ data: 'data:image/png;base64,AAA', caption: 'Hình' }, '10']], tokens);
  assert.ok(tblHtml.includes('id="visual-table-grid"') && tblHtml.includes('table-row-add'));
  const mockForm = {
    dataset: { tableMode: 'grid' },
    querySelector: () => ({
      querySelectorAll: () => [
        { querySelectorAll: () => [{ value: '[Ảnh #1: Hình]' }, { value: '20' }] },
      ],
    }),
  };
  const parsedRows = readVisualTableRows(mockForm, tokens);
  assert.equal(parsedRows[0][0].data, 'data:image/png;base64,AAA');
  assert.equal(parsedRows[0][1], '20');

  assert.ok(emptyCanvasHTML(exam).includes('empty-paper-canvas'));

  const histHtml = renderExportHistoryHTML([
    { revision: 4, audience: 'teacher', format: 'pdf', downloadUrl: '/dl/1.pdf', isDraft: true, classLabel: '9A' },
  ]);
  assert.ok(histHtml.includes('/dl/1.pdf') && histHtml.includes('Giáo viên') && histHtml.includes('Nháp') && histHtml.includes('9A'));
  assert.equal(exportConfirmationNote('pdf'), '');
  assert.equal(exportConfirmationNote('html'), '');
  assert.ok(exportConfirmationNote('docx').includes('Word'));
});

test('UV61 P2 Bugs: tìm explanation trong Kho đề, Trash khôi phục hàng loạt, Editor rich-pending, Sketch Redo & Escape, Modal 2 tầng & Đang/Sắp gắn', () => {
  const exams = [
    { id: 'a', title: 'Đề số 1', subject: 'Toán', grade: '9', questions: [{ stem: 'Tìm x', explanation: 'Sử dụng định lý Vi-ét để tìm nghiệm', rubric: [] }] },
    { id: 'b', title: 'Đề số 2', subject: 'Vật lí', grade: '9', questions: [{ stem: 'Tính I', explanation: 'Định luật Ôm', rubric: [] }] },
  ];
  assert.ok(examLibrarySearchText(exams[0]).includes('vi-et'));
  assert.deepEqual(filterAndSortLibraryExams(exams, { q: 'dinh ly vi-et' }).map((e) => e.id), ['a']);

  const state = { current: 'a', exams: [...exams], trash: [] };
  assert.equal(moveExamsToTrash(state, ['a']), 1);
  assert.equal(state.exams.length, 1);
  assert.equal(state.current, 'b');
  assert.equal(state.trash.length, 1);
  assert.equal(restoreExamsFromTrash(state, ['a']), 1);
  assert.equal(state.exams.length, 2);
  assert.equal(state.trash.length, 0);

  const richHtml = pendingRichPreviewHTML({ stem: 'Đậm', runs: [{ text: 'Đậm', bold: true }] }, 'stem', 0, 'Đậm');
  assert.ok(richHtml.includes('font-weight:700') && richHtml.includes('Đậm'));
  const docHtml = pendingRichPreviewHTML(
    { explanationDoc: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Lời giải nhấn', marks: [{ type: 'bold' }] }] }] } },
    'explanation',
    0,
    'Lời giải nhấn',
  );
  assert.ok(docHtml.includes('<strong>Lời giải nhấn</strong>'));

  const sketchHist = createSketchHistory();
  sketchHist.push({ color: '#000', points: [{ x: 1, y: 1 }] });
  sketchHist.push({ color: '#f00', points: [{ x: 2, y: 2 }] });
  assert.equal(sketchHist.canUndo, true);
  assert.equal(sketchHist.canRedo, false);
  const undone = sketchHist.undo();
  assert.equal(undone.color, '#f00');
  assert.equal(sketchHist.strokes.length, 1);
  assert.equal(sketchHist.canRedo, true);
  const redone = sketchHist.redo();
  assert.equal(redone.color, '#f00');
  assert.equal(sketchHist.strokes.length, 2);
  sketchHist.undo();
  sketchHist.push({ color: '#176853', points: [{ x: 3, y: 3 }] });
  assert.equal(sketchHist.canRedo, false);
  assert.ok(readText('sketch-board.js').includes('data-sketch-confirm-close'));

  assert.equal(computeAttachmentState(true, true).label, 'Đang gắn');
  assert.equal(computeAttachmentState(false, true).label, 'Sắp gắn (chưa lưu)');
  assert.equal(computeAttachmentState(true, false).label, 'Sẽ gỡ khi lưu');
  assert.ok(readText('lesson-picker.js').includes('dialog-layer2') && readText('sharing.js').includes('dialog-layer2'));
});

test('Whale UX: strictTeacherOnly, in-place SSE, room preflight, exam-room a) prefix + score_only, Ollama error VN', () => {
  assert.equal(isTeacherOwnedDoc({id: '1', name: 'File GV.pdf', sample: false}), true);
  assert.equal(isTeacherOwnedDoc({id: '2', name: 'Bài giảng riêng', personalLesson: true, sourceOrigin: 'personal_lesson'}), true);
  assert.equal(isTeacherOwnedDoc({id: '3', name: 'SGK mẫu', catalog: true}), false);
  assert.equal(isTeacherOwnedDoc({id: '4', name: 'Mẫu hệ thống', sample: true}), false);
  assert.equal(isTeacherOwnedDoc({id: '5', name: 'Cộng đồng', communityToken: 'tok'}), false);
  assert.equal(isTeacherOwnedDoc({id: '6', name: 'Catalog origin', sourceOrigin: 'lesson_catalog'}), false);

  const strictCtx = buildFlexibleChatContext({
    id: 'ex-1',
    subject: 'Toán',
    grade: '9',
    strictTeacherOnly: true,
    assistantSources: ['gv-doc', 'cat-doc'],
    assistantSourcePages: {'gv-doc': [2]},
    docs: [
      {id: 'gv-doc', name: 'Đề cương GV', version: 3, pages: [{number: 1, text: 'Trang 1 bỏ qua'}, {number: 2, text: 'Trang 2 được chọn'}]},
      {id: 'cat-doc', name: 'Học liệu mẫu', catalog: true, sourceOrigin: 'lesson_catalog', pages: [{number: 1, text: 'Không được gửi'}]},
    ],
    questions: [],
  }, [], []);
  const srcItems = strictCtx.filter((x) => x.kind === 'attached-source');
  assert.equal(srcItems.length, 1);
  assert.equal(srcItems[0].id, 'gv-doc');
  assert.equal(srcItems[0].pageNumber, 2);
  assert.equal(srcItems[0].version, 3);
  assert.ok(srcItems[0].excerpt.includes('Trang 2 được chọn'));

  assert.equal(stabilizeStreamingMarkdown('```js\nconst x = 1;'), '```js\nconst x = 1;\n```');
  assert.equal(stabilizeStreamingMarkdown('$$x^2 + 1'), '$$x^2 + 1\n$$');

  const wbSrc = readText('workbench.js');
  assert.ok(wbSrc.includes('paintStreamingReplyInPlace(examId)'));
  assert.ok(wbSrc.includes('examId:e.id,text,effort:'));
  assert.ok(wbSrc.includes('modelUsed:result.modelUsed||streamedModel'));
  assert.ok(wbSrc.includes('retryPrompt:text'));

  assert.equal(isRoomLaunchBlocked({ready: false, blockingIssues: [{message: 'Thiếu đáp án Câu 1'}]}), true);
  assert.equal(isRoomLaunchBlocked({ready: true, blockingIssues: []}), false);
  const banner = roomPreflightBannerHTML({ready: false, blockingIssues: [{message: 'Thiếu đáp án Câu 1'}]});
  assert.ok(banner.includes('Thiếu đáp án Câu 1'));

  const cleanTf = stripTrueFalseOptionPrefix('a) Hàm số đồng biến trên R', {
    type: 'doc',
    content: [{type: 'paragraph', content: [{type: 'text', text: 'a) Hàm số đồng biến trên R'}]}],
  });
  assert.equal(cleanTf.text, 'Hàm số đồng biến trên R');
  assert.equal(cleanTf.richDoc.content[0].content[0].text, 'Hàm số đồng biến trên R');

  const scoreOnlyHtml = renderResultReviewSectionHTML({
    resultsAvailable: true,
    resultPolicy: 'score_only',
    questions: [{order: 1, type: 'mcq', stem: 'Câu mật'}],
  });
  assert.ok(scoreOnlyHtml.includes('Giáo viên chỉ cho phép xem tổng điểm cho phòng thi này.'));
  assert.ok(!scoreOnlyHtml.includes('sr-rev-item'));

  assert.equal(
    translateProviderErrorMessage('ollama', 'All connection attempts failed'),
    'Chưa bật dịch vụ Ollama tại máy (127.0.0.1:11434)',
  );
  assert.ok(formatProviderTestResultHTML('ollama', {ok: false, error: 'All connection attempts failed'}).text.includes('127.0.0.1:11434'));
});

test('UV63 CSS restoration & 3 new features: đủ selector khôi phục, Trang chủ, Proactive/Voice, Modal SGK và tổng !important < 30', () => {
  const tokens = readText('assets/tokens.css');
  const layout = readText('assets/layout.css');
  const paper = readText('assets/paper.css');
  const allCss = `${tokens}\n${layout}\n${paper}`;

  const countImp = (css) => (css.match(/!\s*important\b/gi) || []).length;
  const totalImportant = countImp(tokens) + countImp(layout) + countImp(paper);
  assert.ok(totalImportant < 30, `Tổng !important=${totalImportant}, yêu cầu < 30`);

  const requiredSelectors = [
    // Form modal & matrix scroll
    '[data-dialog-feedback]',
    '.matrix-table-scroll',
    // Composer
    '.composer-close',
    '.composer-search',
    '.catalog-card-meta',
    '.catalog-item.selected',
    '.catalog-load-more',
    '.builder-fields',
    '.composer-direct',
    '.composer-keyboard',
    '#catalog-items',
    '#composer-feedback',
    '#inline-math-input',
    '#inline-math-preview',
    // Matrix & Auto-Create
    '.quick-exam-plan',
    '.quick-plan-fields',
    '.matrix-preview-active > .paper',
    '.matrix-live-steps',
    '.matrix-step',
    '.matrix-rubric',
    '#matrix-confirm-save',
    '#matrix-composer-stop',
    '.auto-create-card',
    '.auto-step-list',
    '.auto-step.is-done',
    '.auto-step.is-active',
    '.auto-step.is-error',
    '.auto-batch-pills',
    '.auto-batch-pill',
    // P1
    '.export-omr-panel',
    '.export-preflight-panel',
    '.export-choice-card',
    '#export-variants',
    '.version-text',
    '.block-diffs',
    '.question-check-comparison',
    '.source-group-card.is-attached',
    '.effort-panel',
    '.studio-menu-icon',
    '.find-hit.active',
    '.visual-figure-form',
    '#figure-preview',
    '.formula-block',
    '.inline-formula',
    '.rubric-label',
    '.continuation-label',
    '.wb-library-card.is-current',
    '.wb-current-pill',
    '.online-member [data-action="connections"]',
    '.chat-list-ordered::before',
    '.dot.consistent',
    '.data-value',
    // UV63 Home
    '.home-view',
    '.home-hero',
    '.home-hero-grid',
    '.home-prompt-card',
    '.home-paper-mock',
    '.home-prompt-box',
    '.home-quick-tools',
    '.home-recent-grid',
    '.home-proactive-strip',
    // UV63 Proactive & Voice
    '.proactive-bell',
    '.proactive-badge',
    '.proactive-popover',
    '.proactive-banner',
    '.campaign-card',
    '.campaign-progress',
    '.campaign-bar',
    '.reminder-pill',
    '.voice-mic-btn',
    '.voice-mic-btn.is-listening',
    // UV63 SGK Modal
    '.sgk-modal',
    '.sgk-tabs',
    '.sgk-tab.is-active',
    '.sgk-filter-bar',
    '.sgk-volume-pills',
    '.sgk-pill.is-active',
    '.sgk-split',
    '.sgk-tree-pane',
    '.sgk-tree-all',
    '.sgk-chapter-row',
    '.sgk-lesson-row',
    '.sgk-lesson-row.is-selected',
    '.sgk-page-tag',
    '.sgk-detail-pane',
    '.sgk-badge',
    '.sgk-meta-line',
    '.sgk-outcomes-list',
    '.sgk-footer',
    '#dialog:has(.sgk-modal)',
    '#dialog-layer2:has(.sgk-modal)',
  ];

  for (const sel of requiredSelectors) {
    assert.ok(allCss.includes(sel), `Thiếu selector UV63: ${sel}`);
  }
});
