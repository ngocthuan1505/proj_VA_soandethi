import assert from 'node:assert/strict';
import test from 'node:test';
import {approveQuestion, commit, undo} from '../core.js';
import {
  computeClientAnalyticsSummary,
  filterQuestionBankItems,
  renderAnalyticsModalHTML,
  renderQuestionBankItemsHTML,
  reorderQuestionsByIds,
  stripVietnameseDiacritics,
} from '../vip-tools.js';

const SAMPLE_BANK_ITEMS = [
  {
    id: 'qb-1',
    subject: 'Toán',
    grade: '9',
    topic: 'Phương trình bậc hai',
    qtype: 'mcq',
    level: 1,
    points_q4: 4,
    tags: ['Toán 9', 'Đại số', 'Định lý Vi-ét'],
    question: {
      id: 'orig-1',
      type: 'mcq',
      stem: 'Tìm nghiệm phương trình $x^2 - 5x + 6 = 0$.',
      options: ['$x=1; x=6$', '$x=2; x=3$', '$x=-2; x=-3$', 'Vô nghiệm'],
      answer: 1,
      explanation: 'Áp dụng định lý Vi-ét.',
      topic: 'Phương trình bậc hai',
      level: 1,
      points: 1,
    },
  },
  {
    id: 'qb-2',
    subject: 'Địa lí',
    grade: '10',
    topic: 'Đô thị hóa',
    qtype: 'truefalse',
    level: 0,
    points_q4: 4,
    tags: ['Địa lí 10', 'Dân cư'],
    question: {
      id: 'orig-2',
      type: 'truefalse',
      stem: 'Xét các nhận định về quá trình đô thị hóa ở Việt Nam.',
      options: ['Tỉ lệ dân thành thị tăng', 'Mạng lưới đô thị mở rộng', 'Không ảnh hưởng kinh tế', 'Giảm dịch vụ'],
      truthValues: [true, true, false, false],
      topic: 'Đô thị hóa',
      level: 0,
      points: 1,
    },
  },
  {
    id: 'qb-3',
    subject: 'Toán',
    grade: '12',
    topic: 'Tích phân',
    qtype: 'essay',
    level: 3,
    points_q4: 8,
    tags: ['Giải tích', 'Vận dụng cao'],
    question: {
      id: 'orig-3',
      type: 'essay',
      stem: 'Tính tích phân $\\int_0^1 x e^x dx$.',
      options: [],
      topic: 'Tích phân',
      level: 3,
      points: 2,
    },
  },
];

test('filterQuestionBankItems: tìm kiếm không dấu tiếng Việt và lọc đa tiêu chí không làm đổi mảng gốc', () => {
  assert.equal(stripVietnameseDiacritics('Đô thị hóa · Phương trình'), 'do thi hoa · phuong trinh');

  const byAccentFree = filterQuestionBankItems(SAMPLE_BANK_ITEMS, {q: 'phuong trinh vi-et'});
  assert.deepEqual(byAccentFree.map((i) => i.id), ['qb-1']);

  const byDoThiHoa = filterQuestionBankItems(SAMPLE_BANK_ITEMS, {q: 'do thi hoa'});
  assert.deepEqual(byDoThiHoa.map((i) => i.id), ['qb-2']);

  const bySubjectGrade = filterQuestionBankItems(SAMPLE_BANK_ITEMS, {subject: 'toan', grade: '12'});
  assert.deepEqual(bySubjectGrade.map((i) => i.id), ['qb-3']);

  const byTypeAndLevel = filterQuestionBankItems(SAMPLE_BANK_ITEMS, {qtype: 'truefalse', level: 0});
  assert.deepEqual(byTypeAndLevel.map((i) => i.id), ['qb-2']);

  const noMatch = filterQuestionBankItems(SAMPLE_BANK_ITEMS, {subject: 'Vật lí'});
  assert.equal(noMatch.length, 0);
  assert.equal(SAMPLE_BANK_ITEMS.length, 3);
});

test('computeClientAnalyticsSummary: tính chính xác điểm sẵn sàng, phân bố 4 mức độ và đáp án cân bằng', () => {
  const mkQ = (id, stem, answer, level, points) => {
    const q = {
      id,
      v: 1,
      type: 'mcq',
      stem,
      options: ['PA 1', 'PA 2', 'PA 3', 'PA 4'],
      answer,
      answerKnown: true,
      explanation: 'Lời giải rõ ràng.',
      topic: 'Chủ đề ' + id,
      level,
      points,
      check: {version: 1, status: 'consistent', problems: []},
    };
    approveQuestion(q);
    return q;
  };
  const exam = {
    minutes: 45,
    questions: [
      mkQ('q1', 'Câu hỏi nhận biết về hàm số bậc nhất trong hệ tọa độ.', 0, 0, 2.5),
      mkQ('q2', 'Câu hỏi thông hiểu về phương trình bậc hai một ẩn thực.', 1, 1, 2.5),
      mkQ('q3', 'Câu hỏi vận dụng giải hệ hai phương trình tuyến tính.', 2, 2, 2.5),
      mkQ('q4', 'Câu hỏi vận dụng cao chứng minh bất đẳng thức Cauchy.', 3, 3, 2.5),
    ],
  };

  const report = computeClientAnalyticsSummary(exam);
  assert.equal(report.totalQuestions, 4);
  assert.equal(report.totalPoints, 10);
  assert.equal(report.pointsDelta, 0);
  assert.equal(report.approvedCount, 4);
  assert.equal(report.readinessScore, 100);
  assert.equal(report.duplicates.length, 0);
  assert.equal(report.issues.length, 0);
  assert.deepEqual(report.levelDistribution.map((l) => l.percent), [25, 25, 25, 25]);
  assert.equal(report.answerDistribution.A, 1);
  assert.equal(report.answerDistribution.B, 1);
  assert.equal(report.answerDistribution.C, 1);
  assert.equal(report.answerDistribution.D, 1);
  assert.equal(report.answerDistribution.maxStreak, 1);
  assert.equal(report.answerDistribution.imbalanced, false);
});

test('computeClientAnalyticsSummary: phát hiện câu rỗng, trùng lặp, chuỗi đáp án dài và lệch điểm', () => {
  const exam = {
    minutes: 15,
    questions: [
      {
        id: 'q1',
        v: 1,
        type: 'mcq',
        stem: 'Quá trình đô thị hóa làm gia tăng tỉ lệ dân số thành thị tại khu vực nào?',
        options: ['Khu vực A', 'Khu vực B', 'Khu vực C', 'Khu vực D'],
        answer: 0,
        answerKnown: true,
        explanation: 'Giải thích 1',
        level: 0,
        points: 2,
      },
      {
        id: 'q2',
        v: 1,
        type: 'mcq',
        stem: 'Quá trình đô thị hóa làm gia tăng tỉ lệ dân số thành thị ở khu vực nào?',
        options: ['A1', 'A1', 'A3', 'A4'],
        answer: 0,
        answerKnown: true,
        explanation: '',
        level: 0,
        points: 2,
      },
      {
        id: 'q3',
        v: 1,
        type: 'mcq',
        stem: 'Tính diện tích hình tròn có bán kính bằng năm đơn vị đo.',
        options: ['1', '2', '', ''],
        answer: 0,
        answerKnown: true,
        explanation: 'Giải thích 3',
        level: 1,
        points: 2,
      },
      {
        id: 'q4',
        v: 1,
        type: 'mcq',
        stem: 'Xác định cực trị của hàm số bậc ba đơn giản trên đoạn cho trước.',
        options: ['1', '2', '3', '4'],
        answer: 0,
        answerKnown: true,
        explanation: 'Giải thích 4',
        level: 2,
        points: 1,
      },
      {
        id: 'q5',
        v: 1,
        type: 'mcq',
        stem: '',
        options: ['1', '2', '3', '4'],
        answer: 0,
        answerKnown: false,
        explanation: '',
        level: 2,
        points: 1,
        check: {version: 1, status: 'review', problems: ['Lệch đáp án']},
      },
    ],
  };

  const report = computeClientAnalyticsSummary(exam);
  assert.equal(report.totalPoints, 8);
  assert.equal(report.pointsDelta, -2);
  assert.equal(report.duplicates.length, 1);
  assert.equal(report.duplicates[0].q1Index, 0);
  assert.equal(report.duplicates[0].q2Index, 1);
  assert.ok(report.duplicates[0].similarity >= 0.72);
  assert.equal(report.answerDistribution.maxStreak, 4);
  assert.equal(report.answerDistribution.imbalanced, true);

  const codes = new Set(report.issues.map((it) => it.code));
  assert.ok(codes.has('empty_stem'));
  assert.ok(codes.has('incomplete_options'));
  assert.ok(codes.has('duplicate_options'));
  assert.ok(codes.has('unconfirmed_answer'));
  assert.ok(codes.has('needs_review'));
  assert.ok(codes.has('duplicate_question'));
  assert.ok(codes.has('points_mismatch'));
  assert.ok(report.readinessScore < 60);

  const emptyReport = computeClientAnalyticsSummary({questions: []});
  assert.equal(emptyReport.readinessScore, 0);
  assert.equal(emptyReport.issues[0].code, 'empty_exam');
});

test('reorderQuestionsByIds: kéo-thả before/after chính xác, bất biến và tương thích hoàn tác Undo', () => {
  const exam = {
    questions: [{id: 'a', stem: 'A'}, {id: 'b', stem: 'B'}, {id: 'c', stem: 'C'}, {id: 'd', stem: 'D'}],
    undo: [],
    redo: [],
    history: [],
    revision: 1,
  };

  const movedAfter = reorderQuestionsByIds(exam.questions, 'a', 'c', 'after');
  assert.deepEqual(movedAfter.map((q) => q.id), ['b', 'c', 'a', 'd']);
  assert.deepEqual(exam.questions.map((q) => q.id), ['a', 'b', 'c', 'd']);

  const movedBefore = reorderQuestionsByIds(exam.questions, 'd', 'b', 'before');
  assert.deepEqual(movedBefore.map((q) => q.id), ['a', 'd', 'b', 'c']);

  const noop = reorderQuestionsByIds(exam.questions, 'missing', 'b', 'before');
  assert.deepEqual(noop.map((q) => q.id), ['a', 'b', 'c', 'd']);

  commit(exam, 'Sắp xếp lại thứ tự câu hỏi', (draft) => {
    draft.questions = reorderQuestionsByIds(draft.questions, 'c', 'a', 'before');
  });
  assert.deepEqual(exam.questions.map((q) => q.id), ['c', 'a', 'b', 'd']);
  assert.equal(undo(exam), true);
  assert.deepEqual(exam.questions.map((q) => q.id), ['a', 'b', 'c', 'd']);
});

test('renderQuestionBankItemsHTML và renderAnalyticsModalHTML: render KaTeX và chống XSS toàn diện', () => {
  const maliciousItems = [
    {
      id: 'id" onmouseover="alert(1)',
      subject: '<script>alert(1)</script>Toán',
      grade: '9<img src=x onerror=alert(2)>',
      topic: '<b>Chủ đề</b>',
      qtype: 'mcq',
      level: 2,
      tags: ['<svg onload=alert(3)>'],
      question: {
        stem: 'Giải $x^2-4=0$ và <img src=x onerror=alert(4)>',
        options: ['<script>x()</script>$x=2$', 'PA B'],
      },
    },
  ];

  const bankHtml = renderQuestionBankItemsHTML(maliciousItems);
  assert.match(bankHtml, /class="katex"/);
  assert.match(bankHtml, /data-action="insert-from-bank"/);
  assert.match(bankHtml, /data-action="delete-bank-item"/);
  assert.ok(!bankHtml.includes('<script>'));
  assert.ok(!bankHtml.includes('<img '));
  assert.ok(!bankHtml.includes('<svg '));
  assert.ok(!bankHtml.includes('" onmouseover="alert(1)'));
  assert.ok(bankHtml.includes('&lt;script&gt;'));
  assert.ok(bankHtml.includes('&lt;img '));

  const emptyBankHtml = renderQuestionBankItemsHTML([]);
  assert.match(emptyBankHtml, /qbank-empty/);

  const xssExam = {
    minutes: 45,
    questions: [
      {id: 'q"bad', v: 1, type: 'mcq', stem: '', options: [], answer: 0, answerKnown: false, level: 0, points: 1},
    ],
  };
  const report = computeClientAnalyticsSummary(xssExam);
  report.issues.push({
    severity: 'warning',
    code: 'xss_test',
    message: '<img src=x onerror=alert(9)> Cảnh báo mẫu',
    questionIndex: 0,
  });
  const analyticsHtml = renderAnalyticsModalHTML(report, xssExam, {clientFallback: true});
  assert.match(analyticsHtml, /data-action="jump-issue-question"/);
  assert.match(analyticsHtml, /data-q-index="0"/);
  assert.ok(!analyticsHtml.includes('<img src=x'));
  assert.ok(analyticsHtml.includes('&lt;img src=x onerror=alert(9)&gt;'));
  assert.ok(!analyticsHtml.includes('data-q-id="q"bad"'));
});

test('UV60: renderQuestionBankItemsHTML giữ điểm thập phân 0.4, ảnh an toàn; renderAnalyticsModalHTML chuẩn hóa severity warn và empty_selected_option', () => {
  const png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
  const html = renderQuestionBankItemsHTML([
    {
      id: 'qb-dec',
      subject: 'Toán',
      grade: '9',
      topic: 'Hàm số',
      qtype: 'mcq',
      level: 1,
      points_q4: 2,
      points: 0.4,
      question: {
        stem: 'Câu có ảnh và 0.4 điểm',
        points: 0.4,
        options: ['1', '2', '3', '4'],
        images: [{data: png, caption: 'Hình minh họa'}],
      },
    },
  ]);
  assert.ok(html.includes('0.4 điểm'));
  assert.ok(!html.includes('0.5 điểm'));
  assert.ok(html.includes('<img class="qbank-thumb" src="' + png + '"'));

  const badMcqExam = {
    minutes: 45,
    questions: [
      {
        id: 'q-empty-sel',
        v: 1,
        type: 'mcq',
        stem: 'Chọn đáp án đúng?',
        options: ['PA A', '', 'PA C', 'PA D'],
        answer: 1,
        answerKnown: true,
        level: 0,
        points: 1,
      },
    ],
  };
  const summary = computeClientAnalyticsSummary(badMcqExam);
  const emptySel = summary.issues.find((x) => x.code === 'empty_selected_option');
  assert.ok(emptySel);
  assert.equal(emptySel.severity, 'error');

  const warnHtml = renderAnalyticsModalHTML(
    {
      readinessScore: 80,
      issues: [{severity: 'warn', code: 'x', message: 'Cảnh báo từ backend'}],
    },
    badMcqExam,
  );
  assert.ok(warnHtml.includes('analytics-issue is-warning'));
  assert.ok(warnHtml.includes('>Cảnh báo<'));
});

test('t5: computeClientAnalyticsSummary tính đúng tổng điểm hiệu lực cho đề 2 hướng choiceGroup', () => {
  const twoTrackExam = {
    minutes: 45,
    questions: [
      {id: 'c1', v: 1, type: 'mcq', stem: 'Câu chung phần đại số', options: ['A', 'B', 'C', 'D'], answer: 0, answerKnown: true, explanation: 'G', level: 0, points: 5},
      {id: 'a1', v: 1, type: 'mcq', choiceGroup: 'Tự chọn A', stem: 'Câu nhánh A khoa học máy tính', options: ['A', 'B', 'C', 'D'], answer: 1, answerKnown: true, explanation: 'G', level: 1, points: 5},
      {id: 'b1', v: 1, type: 'mcq', choiceGroup: 'Tự chọn B', stem: 'Câu nhánh B tin học ứng dụng', options: ['A', 'B', 'C', 'D'], answer: 2, answerKnown: true, explanation: 'G', level: 1, points: 5},
    ],
  };
  const report = computeClientAnalyticsSummary(twoTrackExam);
  assert.equal(report.totalPoints, 10);
  assert.equal(report.pointsDelta, 0);
  assert.equal(report.issues.some((it) => it.code === 'points_mismatch'), false);
});
