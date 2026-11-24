import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  blank,
  duplicateExam,
  filterPrefsForExam,
  prefMatchesExamScope,
  rebalanceMatrixRowsToTen,
  separateMarking,
  validateMatrixRows,
} from '../core.js';
import {buildBankPayload, filterQuestionBankItems} from '../vip-tools.js';
import {shouldDeferPageLayout} from '../pages.js';
import {shouldConfirmStudentExport} from '../mvp.js';
import {examLibrarySearchText, filterAndSortLibraryExams} from '../workbench.js';
import {lessonSubjectMatches} from '../lesson-picker.js';
import {CHAT_TIME_PRESETS} from '../reference.js';

const readText = (relPath) => readFileSync(new URL(`../${relPath}`, import.meta.url), 'utf8');

test('UV60 BUG-P0-01: app.js gọi allQuestionBank() khi backup và hiển thị preview.questionBank khi import-backup', () => {
  const appSrc = readText('app.js');
  assert.ok(appSrc.includes('db.allQuestionBank()'));
  assert.ok(appSrc.includes('...(questionBank?{questionBank}:{})'));
  assert.ok(appSrc.includes('preview.questionBank'));
});

test('UV60 BUG-P1-01 & BUG-P1-02: buildBankPayload gửi top-level subject/grade/topic/points và UI dùng step="0.05"', () => {
  const payload = buildBankPayload(
    {subject: 'Toán', grade: '9'},
    {id: 'q1', type: 'mcq', stem: 'Câu 0.4đ', topic: 'Hàm số', points: 0.4, options: ['A', 'B', 'C', 'D'], answer: 0},
  );
  assert.equal(payload.subject, 'Toán');
  assert.equal(payload.grade, '9');
  assert.equal(payload.topic, 'Hàm số');
  assert.equal(payload.points, 0.4);
  assert.equal(payload.question.points, 0.4);

  const items = [
    {id: '1', subject: 'Toán', grade: '9', topic: 'Hàm số', qtype: 'mcq', level: 0, question: {stem: 'A'}},
    {id: '2', subject: 'Toán', grade: '9', topic: 'Phương trình', qtype: 'mcq', level: 0, question: {stem: 'B'}},
  ];
  assert.deepEqual(filterQuestionBankItems(items, {topic: 'ham so'}).map((x) => x.id), ['1']);

  assert.ok(readText('app.js').includes('min="0.05" max="10" step="0.05"'));
  assert.ok(readText('reference.js').includes('min="0.05" max="10" step="0.05"'));
  const studioSrc = readText('studio.js');
  assert.ok(studioSrc.includes('min="0.05" max="10" step="0.05"'));
  assert.ok(studioSrc.includes('Math.abs(value*20-Math.round(value*20))>0.001'));
});

test('UV60 BUG-P1-05: Nhãn preset AGY đồng nhất và CSS matrix-live-steps tắt đánh số mặc định <ol>', () => {
  const expected = new Map([
    ['fast', 'Thời gian: Nhanh (2p · API nhanh)'],
    ['standard', 'Thời gian: Chuẩn (5p · AGY)'],
    ['deep', 'Thời gian: Kỹ sâu (20p · AGY)'],
    ['extended', 'Thời gian: Sâu (60p · AGY)'],
  ]);
  for (const [id, label] of CHAT_TIME_PRESETS) {
    assert.equal(label, expected.get(id));
  }
  const usabilityJs = readText('assets/usability.js');
  for (const label of expected.values()) {
    assert.ok(usabilityJs.includes(label), label);
  }
  const workbenchSrc = readText('workbench.js');
  assert.ok(workbenchSrc.includes('teacherFilesOnly:Boolean(e.strictTeacherOnly)'));
  assert.ok(workbenchSrc.includes('fallbackFrom:result.fallbackFrom'));

  const css = readText('assets/usability.css');
  assert.match(css, /#matrix-live-steps[^}]*list-style:\s*none\s*!important/);
});

test('UV60 BUG-P1-06: shouldDeferPageLayout hoãn layout khi đang gõ trong editor chưa tràn +80px và app.js có beforeunload', () => {
  const paperEl = {};
  const oldGetComputed = globalThis.getComputedStyle;
  globalThis.getComputedStyle = () => ({getPropertyValue: () => '1000px'});
  try {
    const insideEditor = (scrollHeight) => ({
      closest: (sel) =>
        sel.includes('#paper') || sel.includes('.ProseMirror')
          ? {closest: () => ({scrollHeight})}
          : null,
    });
    assert.equal(shouldDeferPageLayout(insideEditor(900), paperEl), true);
    assert.equal(shouldDeferPageLayout(insideEditor(1080), paperEl), true);
    assert.equal(shouldDeferPageLayout(insideEditor(1081), paperEl), false);
    assert.equal(shouldDeferPageLayout({closest: () => null}, paperEl), false);
  } finally {
    globalThis.getComputedStyle = oldGetComputed;
  }

  const appSrc = readText('app.js');
  assert.ok(appSrc.includes("window.addEventListener('beforeunload'"));
  assert.ok(appSrc.includes('persistRunning||db.hasPendingWrites()||hasPendingEditorChanges()'));
});

test('UV60 BUG-P2-01: shouldConfirmStudentExport bảo vệ khi xuất Bản học sinh có lớp/đã duyệt mà chưa duyệt hết câu, không chặn đề nháp E2E', () => {
  assert.equal(
    shouldConfirmStudentExport({batch: false, teacher: false, confirmed: false, classLabel: '', workflowStatus: 'draft', unapprovedCount: 3, preflightFailed: false}),
    false,
  );
  assert.equal(
    shouldConfirmStudentExport({batch: false, teacher: false, confirmed: false, classLabel: 'Lớp 9A', workflowStatus: 'draft', unapprovedCount: 2, preflightFailed: false}),
    true,
  );
  assert.equal(
    shouldConfirmStudentExport({batch: false, teacher: false, confirmed: false, classLabel: '', workflowStatus: 'approved', unapprovedCount: 1, preflightFailed: false}),
    true,
  );
  assert.equal(
    shouldConfirmStudentExport({batch: false, teacher: false, confirmed: true, classLabel: 'Lớp 9A', workflowStatus: 'draft', unapprovedCount: 2, preflightFailed: false}),
    false,
  );
  assert.equal(
    shouldConfirmStudentExport({batch: false, teacher: true, confirmed: false, classLabel: 'Lớp 9A', workflowStatus: 'draft', unapprovedCount: 2, preflightFailed: false}),
    false,
  );
});

test('UV60 BUG-P2-02 & P2-04 CSS: save-warning nổi trên footer, responsive mobile giữ .wf-mode-pill & menubar, hiện .q-status cần rà', () => {
  const css = readText('assets/usability.css');
  assert.match(css, /\[data-save-warning\]:not\(\[hidden\]\)[^}]*position:\s*absolute\s*!important/);
  assert.match(css, /\.mach\s+\.main-footer\s+\.wf-mode-pill\{display:\s*inline-flex\s*!important/);
  assert.match(css, /\.mach\s+\.menubar\s*\{display:\s*flex\s*!important;[^}]*overflow-x:\s*auto\s*!important/);
  assert.match(css, /\.mach\s+\.q-status\.review[^}]*display:\s*inline-flex\s*!important/);
  assert.ok(!readText('studio.css').includes('.studio .menubar button:nth-child(n+5){display:none}'));
});

test('UV60 BUG-P2-05: Quy tắc phạm vi Toán 9 không rò sang Ngữ văn 7C và blank() kế thừa teacherProfile', () => {
  const prefs = [
    {id: 'all', text: 'Chung mọi môn', scopeType: 'all', confirmedAt: 1},
    {id: 'math9', text: 'Chuẩn Toán 9', scopeType: 'subject_grade', subject: 'Toán', grade: '9', confirmedAt: 2},
    {id: 'van', text: 'Ngữ văn chuẩn', scopeType: 'subject', subject: 'Ngữ văn', confirmedAt: 3},
    {id: 'draft', text: 'Chưa xác nhận', scopeType: 'all'},
  ];
  assert.equal(prefMatchesExamScope(prefs[1], 'Toán', '9'), true);
  assert.equal(prefMatchesExamScope(prefs[1], 'Ngữ văn', '7C'), false);
  assert.equal(prefMatchesExamScope(prefs[1], 'Toán', '10'), false);
  assert.equal(prefMatchesExamScope(prefs[2], 'Tiếng Việt', '5'), true);

  assert.deepEqual(filterPrefsForExam(prefs, 'Toán', '9').map((p) => p.id), ['all', 'math9']);
  assert.deepEqual(filterPrefsForExam(prefs, 'Ngữ văn', '7C').map((p) => p.id), ['all', 'van']);

  const e = blank('Ngữ văn', prefs, {
    school: 'THCS LÊ QUÝ ĐÔN',
    department: 'PHÒNG GD&ĐT QUẬN 1',
    grade: '7C',
    layout: {font: 'Arial', fontSize: 13},
  });
  assert.equal(e.school, 'THCS LÊ QUÝ ĐÔN');
  assert.equal(e.department, 'PHÒNG GD&ĐT QUẬN 1');
  assert.equal(e.grade, '7C');
  assert.equal(e.layout.font, 'Arial');
  assert.deepEqual(e.appliedPrefs.map((p) => p.id), ['all', 'van']);
  assert.equal(e.workflowStatus, 'draft');

  e.workflowStatus = 'printed';
  const copied = duplicateExam(e);
  assert.equal(copied.workflowStatus, 'draft');
});

test('UV60 BUG-P2-07: Tìm kiếm không dấu trên Kho đề qua thân câu và barem, lọc & sắp xếp chuẩn xác', () => {
  const exams = [
    {
      id: 'e1',
      title: 'Đề ôn giữa kì',
      subject: 'Toán',
      grade: '9A',
      workflowStatus: 'approved',
      updated: 200,
      questions: [
        {stem: 'Giải bất phương trình bậc nhất', rubric: [{text: 'Biến đổi tương đương', points: 1}]},
      ],
    },
    {
      id: 'e2',
      title: 'Đề đọc hiểu',
      subject: 'Ngữ văn',
      grade: '7C',
      workflowStatus: 'draft',
      updated: 300,
      questions: [
        {stem: 'Phân tích biện pháp nhân hóa', rubric: [{text: 'Nêu được tác dụng gợi hình', points: 1}]},
      ],
    },
  ];
  assert.ok(examLibrarySearchText(exams[1]).includes('tac dung goi hinh'));
  assert.deepEqual(filterAndSortLibraryExams(exams, {q: 'bien doi tuong duong'}).map((e) => e.id), ['e1']);
  assert.deepEqual(filterAndSortLibraryExams(exams, {q: 'goi hinh', status: 'draft'}).map((e) => e.id), ['e2']);
  assert.deepEqual(filterAndSortLibraryExams(exams, {sort: 'title'}).map((e) => e.id), ['e2', 'e1']);
});

test('UV60 VIP M05-01 & UX-02/03/04 & P3: rebalanceMatrixRowsToTen cân về 10,00đ và lessonSubjectMatches Tiếng Việt <-> Ngữ văn', () => {
  const rows = [
    {topic: 'Đại số', type: 'mcq', targets: [4, 4, 0, 0], points: 1},
    {topic: 'Hình học', type: 'essay', targets: [0, 1, 1, 0], points: 1},
  ];
  const balanced = rebalanceMatrixRowsToTen(rows);
  assert.doesNotThrow(() => validateMatrixRows(balanced));

  const branched = [
    {topic: 'Chung', type: 'mcq', targets: [10, 0, 0, 0], points: 0.5},
    {topic: 'Riêng A', type: 'essay', choiceGroup: 'Tự chọn A', targets: [0, 2, 0, 0], points: 1},
    {topic: 'Riêng B', type: 'essay', choiceGroup: 'Tự chọn B', targets: [0, 2, 0, 0], points: 3},
  ];
  const balancedBranched = rebalanceMatrixRowsToTen(branched);
  assert.doesNotThrow(() => validateMatrixRows(balancedBranched));

  assert.equal(lessonSubjectMatches('Tiếng Việt', 'Ngữ văn'), true);
  assert.equal(lessonSubjectMatches('Ngữ văn', 'Tiếng Việt'), true);
  assert.equal(lessonSubjectMatches('Toán', 'Ngữ văn'), false);

  assert.equal(separateMarking({fullExam: true, questions: []}), false);
  assert.equal(separateMarking({fullExam: true, questions: [{type: 'essay'}]}), true);
  assert.ok(readText('mvp.js').includes("'studio-replace','Tìm và thay thế (Ctrl+H)'"));
  assert.ok(readText('design.js').includes("'studio-replace','Tìm và thay thế'"));
  assert.ok(readText('reference.js').includes('captureAssistantSourceDraft'));
  assert.ok(readText('reference.js').includes('strictTeacherOnly'));
});

test('UV60 M02-03/UX-05: studio.js tích hợp reconcileEditorRich để bảo toàn richDoc khi Tìm & Thay thế', () => {
  const studioSrc = readText('studio.js');
  assert.ok(studioSrc.includes('reconcileEditorRich'));
  assert.ok(studioSrc.includes('preserveRich'));
  assert.ok(studioSrc.includes('replaceStringPreservingRich'));
});
