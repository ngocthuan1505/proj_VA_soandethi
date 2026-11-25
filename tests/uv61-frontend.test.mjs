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
} from '../workbench.js';
import {
  renderProvidersHealthHTML,
  formatProviderTestResultHTML,
  connectionSettings,
} from '../connections.js';
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
