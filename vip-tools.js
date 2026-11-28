import {LEVELS, QUESTION_TYPES, check, clone, esc, isApproved, uid} from './core.js';
import {richTextHTML} from './math-content.js';

const LEVEL_COLORS = ['#0f4c81', '#1e78c8', '#d97706', '#dc2626'];
const LEVEL_SHORT = ['NB', 'TH', 'VD', 'VDC'];
const ESTIMATED_MINUTES_BY_TYPE = {mcq: 1.5, truefalse: 2.5, short: 2.5, essay: 10};
const SAFE_CELL_IMAGE_RE = /^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/i;

let activeCtx = null;
let bankCache = [];
let bankTotal = 0;
let bankHasMore = false;
let bankFacets = null;
let bankFilters = {q: '', subject: '', grade: '', topic: '', qtype: '', level: ''};
let bankSearchTimer = null;
let bankRequestSeq = 0;
let dragState = {draggedId: null, listenersBound: false, refreshBound: false};

export function stripVietnameseDiacritics(value) {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim();
}

function normalizedTokens(text) {
  const clean = stripVietnameseDiacritics(text)
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((token) => token.length >= 2);
  return new Set(clean);
}

function jaccardSimilarity(tokensA, tokensB) {
  if (!tokensA.size || !tokensB.size) return 0;
  let shared = 0;
  for (const t of tokensA) {
    if (tokensB.has(t)) shared += 1;
  }
  const union = tokensA.size + tokensB.size - shared;
  return union > 0 ? shared / union : 0;
}

function questionPoints(q) {
  if (q && q.points_real != null && q.points_real !== '' && Number.isFinite(Number(q.points_real))) {
    return Number(q.points_real);
  }
  if (q && q.points != null && q.points !== '' && Number.isFinite(Number(q.points))) {
    return Number(q.points);
  }
  if (q && q.pointsQ4 != null && Number.isFinite(Number(q.pointsQ4))) {
    return Number(q.pointsQ4) / 4;
  }
  if (q && q.points_q4 != null && Number.isFinite(Number(q.points_q4))) {
    return Number(q.points_q4) / 4;
  }
  return 0;
}

function round2(n) {
  return Math.round((Number(n) || 0) * 100) / 100;
}

export function filterQuestionBankItems(items, filters = {}) {
  const list = Array.isArray(items) ? items : [];
  const qNeedle = stripVietnameseDiacritics(filters.q || '');
  const subjectNeedle = stripVietnameseDiacritics(filters.subject || '');
  const gradeNeedle = String(filters.grade ?? '').trim();
  const topicNeedle = stripVietnameseDiacritics(filters.topic || '');
  const typeNeedle = String(filters.qtype ?? '').trim();
  const hasLevel = filters.level !== '' && filters.level !== null && filters.level !== undefined;
  const levelNeedle = hasLevel ? Number(filters.level) : null;

  return list.filter((item) => {
    if (!item || typeof item !== 'object') return false;
    const q = item.question && typeof item.question === 'object' ? item.question : {};
    const subject = item.subject || q.subject || '';
    const grade = String(item.grade ?? q.grade ?? '').trim();
    const topic = item.topic || q.topic || '';
    const qtype = item.qtype || q.type || 'mcq';
    const level = item.level != null ? Number(item.level) : Number(q.level ?? 0);

    if (subjectNeedle && stripVietnameseDiacritics(subject) !== subjectNeedle) return false;
    if (gradeNeedle && grade !== gradeNeedle) return false;
    if (topicNeedle && stripVietnameseDiacritics(topic) !== topicNeedle) return false;
    if (typeNeedle && qtype !== typeNeedle) return false;
    if (hasLevel && Number.isFinite(levelNeedle) && level !== levelNeedle) return false;

    if (qNeedle) {
      const haystack = stripVietnameseDiacritics(
        [
          item.topic,
          subject,
          grade,
          q.stem,
          q.topic,
          q.explanation,
          ...(Array.isArray(q.options) ? q.options : []),
          ...(Array.isArray(item.tags) ? item.tags : []),
        ]
          .filter(Boolean)
          .join(' '),
      );
      const parts = qNeedle.split(/\s+/).filter(Boolean);
      if (!parts.every((part) => haystack.includes(part))) return false;
    }
    return true;
  });
}

export function computeClientAnalyticsSummary(exam) {
  const questions = Array.isArray(exam?.questions) ? exam.questions : [];
  const totalQuestions = questions.length;
  const targetPoints = 10;
  const examMinutes = Number(exam?.minutes) > 0 ? Number(exam.minutes) : 45;

  let totalPointsRaw = 0;
  let commonPointsRaw = 0;
  const trackPoints = new Map();
  let estimatedMinutesRaw = 0;
  let approvedCount = 0;

  const levelCounts = [0, 0, 0, 0];
  const levelPoints = [0, 0, 0, 0];
  const typeBuckets = new Map();
  const answerCounts = {A: 0, B: 0, C: 0, D: 0};
  const mcqAnswers = [];
  const issues = [];
  const tokenSets = [];

  questions.forEach((q, idx) => {
    const qType = q?.type || 'mcq';
    const qPts = questionPoints(q);
    totalPointsRaw += qPts;
    const grp = String(q?.choiceGroup || '').trim();
    if (!grp) {
      commonPointsRaw += qPts;
    } else {
      const grpKey = grp.toLocaleLowerCase('vi-VN');
      trackPoints.set(grpKey, (trackPoints.get(grpKey) || 0) + qPts);
    }
    estimatedMinutesRaw += ESTIMATED_MINUTES_BY_TYPE[qType] ?? 2;
    if (isApproved(q)) approvedCount += 1;

    const lvl = Number.isInteger(q?.level) && q.level >= 0 && q.level <= 3 ? q.level : 0;
    levelCounts[lvl] += 1;
    levelPoints[lvl] += qPts;

    if (!typeBuckets.has(qType)) {
      typeBuckets.set(qType, {type: qType, label: QUESTION_TYPES[qType] || qType, count: 0, points: 0});
    }
    const bucket = typeBuckets.get(qType);
    bucket.count += 1;
    bucket.points = round2(bucket.points + qPts);

    const stemText = String(q?.stem || '').trim();
    tokenSets.push(normalizedTokens(stemText));

    if (!stemText || /^nhập nội dung câu hỏi/i.test(stemText)) {
      issues.push({
        severity: 'error',
        code: 'empty_stem',
        message: `Câu ${idx + 1} chưa có nội dung thân câu hoàn chỉnh.`,
        questionIndex: idx,
      });
    }

    if (qType === 'mcq') {
      const opts = Array.isArray(q?.options) ? q.options : [];
      const filled = opts.map((o) => String(o || '').trim()).filter(Boolean);
      if (filled.length < 4) {
        issues.push({
          severity: 'warning',
          code: 'incomplete_options',
          message: `Câu ${idx + 1} mới có ${filled.length}/4 phương án trả lời.`,
          questionIndex: idx,
        });
      } else {
        const uniqueOpts = new Set(filled.map((o) => stripVietnameseDiacritics(o)));
        if (uniqueOpts.size < filled.length) {
          issues.push({
            severity: 'warning',
            code: 'duplicate_options',
            message: `Câu ${idx + 1} có phương án bị trùng nội dung.`,
            questionIndex: idx,
          });
        }
      }
      if (q?.answerKnown !== false && Number.isInteger(q?.answer) && q.answer >= 0 && q.answer < 4) {
        const selectedOptText = String(opts[q.answer] || '').trim();
        if (!selectedOptText) {
          issues.push({
            severity: 'error',
            code: 'empty_selected_option',
            message: `Câu ${idx + 1} đang chọn đáp án ${'ABCD'[q.answer]} nhưng nội dung phương án đó còn trống.`,
            questionIndex: idx,
          });
        }
        const letter = 'ABCD'[q.answer];
        answerCounts[letter] += 1;
        mcqAnswers.push({letter, index: idx});
      }
    }

    if (q?.answerKnown === false) {
      issues.push({
        severity: 'warning',
        code: 'unconfirmed_answer',
        message: `Câu ${idx + 1} chưa xác nhận đáp án đúng.`,
        questionIndex: idx,
      });
    }

    if (q?.check?.version === q?.v && q.check.status === 'review') {
      issues.push({
        severity: 'warning',
        code: 'needs_review',
        message: `Câu ${idx + 1} đang có cảnh báo cần rà soát lại.`,
        questionIndex: idx,
      });
    }

    if (!String(q?.explanation || '').trim()) {
      issues.push({
        severity: 'info',
        code: 'missing_explanation',
        message: `Câu ${idx + 1} chưa có lời giải hoặc giải thích cho giáo viên.`,
        questionIndex: idx,
      });
    }
  });

  const maxTrackPts = trackPoints.size ? Math.max(...trackPoints.values()) : 0;
  const effectivePoints = trackPoints.size ? commonPointsRaw + maxTrackPts : totalPointsRaw;
  const totalPoints = round2(effectivePoints);
  const pointsDelta = round2(totalPoints - targetPoints);
  const estimatedMinutes = Math.round(estimatedMinutesRaw);

  if (totalQuestions === 0) {
    issues.push({
      severity: 'error',
      code: 'empty_exam',
      message: 'Đề thi chưa có câu hỏi nào.',
      questionIndex: null,
    });
  } else if (totalPoints > 0 && Math.abs(pointsDelta) > 0.01) {
    issues.push({
      severity: 'warning',
      code: 'points_mismatch',
      message: `Tổng điểm hiện tại là ${totalPoints} điểm (lệch ${pointsDelta > 0 ? '+' : ''}${pointsDelta} so với thang ${targetPoints} điểm).`,
      questionIndex: null,
    });
  }

  let maxStreak = 0;
  let curStreak = 0;
  let prevLetter = null;
  let curRun = [];
  let streakQuestions = [];
  for (const entry of mcqAnswers) {
    if (entry.letter === prevLetter) {
      curStreak += 1;
      curRun.push(entry.index);
    } else {
      prevLetter = entry.letter;
      curStreak = 1;
      curRun = [entry.index];
    }
    if (curStreak > maxStreak) {
      maxStreak = curStreak;
      streakQuestions = [...curRun];
    }
  }

  const totalMcq = mcqAnswers.length;
  const maxLetterCount = Math.max(answerCounts.A, answerCounts.B, answerCounts.C, answerCounts.D);
  const imbalanced = totalMcq >= 4 && (maxLetterCount / totalMcq > 0.5 || maxStreak >= 4);

  if (imbalanced) {
    issues.push({
      severity: 'info',
      code: 'answer_imbalance',
      message:
        maxStreak >= 4
          ? `Có chuỗi ${maxStreak} câu trắc nghiệm liên tiếp trùng một đáp án.`
          : 'Phân bố đáp án A/B/C/D đang lệch nhiều về một lựa chọn.',
      questionIndex: streakQuestions[0] ?? null,
    });
  }

  const duplicates = [];
  for (let i = 0; i < totalQuestions; i += 1) {
    if (tokenSets[i].size < 3) continue;
    for (let j = i + 1; j < totalQuestions; j += 1) {
      if (tokenSets[j].size < 3) continue;
      const sim = jaccardSimilarity(tokenSets[i], tokenSets[j]);
      if (sim >= 0.72) {
        const rounded = round2(sim);
        duplicates.push({q1Index: i, q2Index: j, similarity: rounded});
        issues.push({
          severity: 'warning',
          code: 'duplicate_question',
          message: `Câu ${i + 1} và Câu ${j + 1} có nội dung tương đồng cao (${Math.round(rounded * 100)}%).`,
          questionIndex: j,
        });
      }
    }
  }

  const levelDistribution = LEVELS.map((label, level) => ({
    level,
    label,
    count: levelCounts[level],
    points: round2(levelPoints[level]),
    percent: totalQuestions ? Math.round((levelCounts[level] / totalQuestions) * 100) : 0,
  }));

  const typeDistribution = [...typeBuckets.values()];

  let readinessScore = 0;
  if (totalQuestions > 0) {
    const errorCount = issues.filter((it) => it.severity === 'error').length;
    const warnCount = issues.filter((it) => it.severity === 'warning').length;
    const unapprovedRatio = (totalQuestions - approvedCount) / totalQuestions;
    readinessScore = Math.max(
      0,
      Math.min(100, Math.round(100 - errorCount * 16 - warnCount * 6 - unapprovedRatio * 18)),
    );
  }

  return {
    readinessScore,
    totalQuestions,
    totalPoints,
    targetPoints,
    pointsDelta,
    estimatedMinutes,
    examMinutes,
    approvedCount,
    levelDistribution,
    typeDistribution,
    answerDistribution: {
      ...answerCounts,
      totalMcq,
      maxStreak,
      imbalanced,
      streakQuestions,
    },
    duplicates,
    issues,
  };
}

export function reorderQuestionsByIds(questions, draggedId, targetId, position = 'before') {
  if (!Array.isArray(questions)) return [];
  const next = [...questions];
  if (!draggedId || !targetId || draggedId === targetId) return next;
  const fromIdx = next.findIndex((q) => q && q.id === draggedId);
  const targetIdx = next.findIndex((q) => q && q.id === targetId);
  if (fromIdx < 0 || targetIdx < 0) return next;
  const [moved] = next.splice(fromIdx, 1);
  const adjustedTarget = next.findIndex((q) => q && q.id === targetId);
  const insertAt = position === 'after' ? adjustedTarget + 1 : adjustedTarget;
  next.splice(insertAt, 0, moved);
  return next;
}

export function renderQuestionBankItemsHTML(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) {
    return '<div class="qbank-empty">Chưa có câu hỏi nào khớp bộ lọc. Bấm biểu tượng <b>★</b> trên câu hỏi hoặc <b>★ Lưu cả đề vào kho</b> để tái sử dụng nhanh.</div>';
  }
  return list
    .map((item) => {
      const q = item.question && typeof item.question === 'object' ? item.question : {};
      const qType = item.qtype || q.type || 'mcq';
      const typeLabel = QUESTION_TYPES[qType] || qType;
      const lvl = Number.isInteger(item.level) ? item.level : Number(q.level ?? 0);
      const levelLabel = LEVELS[lvl] || LEVELS[0];
      const exactPts =
        item.points_real ??
        (item.points != null && item.points !== '' ? item.points : null) ??
        (q.points != null && q.points !== '' ? q.points : null);
      const pts =
        exactPts != null && Number.isFinite(Number(exactPts))
          ? Number(exactPts)
          : questionPoints(item) || questionPoints(q);
      const subject = item.subject || q.subject || 'Chưa rõ môn';
      const grade = item.grade || q.grade ? `Lớp ${item.grade || q.grade}` : '';
      const topic = item.topic || q.topic || '';
      const tags = Array.isArray(item.tags) ? item.tags.filter(Boolean).slice(0, 5) : [];
      const opts = Array.isArray(q.options) ? q.options.filter((o) => String(o || '').trim()) : [];
      const thumbImg = Array.isArray(q.images)
        ? q.images.find((im) => typeof im?.data === 'string' && SAFE_CELL_IMAGE_RE.test(im.data))
        : null;
      return `<article class="qbank-card" data-bank-id="${esc(item.id)}">
        <div class="qbank-card-head">
          <div class="qbank-meta">
            <span class="qbank-badge qbank-badge-subject">${esc(subject)}${grade ? ' · ' + esc(grade) : ''}</span>
            <span class="qbank-badge qbank-badge-type">${esc(typeLabel)}</span>
            <span class="qbank-badge qbank-badge-level" data-level="${lvl}">${esc(levelLabel)}</span>
            ${pts ? `<span class="qbank-badge">${esc(String(pts))} điểm</span>` : ''}
          </div>
          <div class="qbank-card-actions">
            <button type="button" class="primary qbank-insert-btn" data-action="insert-from-bank" data-id="${esc(item.id)}">＋ Chèn vào đề</button>
            <button type="button" class="danger tiny-btn" data-action="delete-bank-item" data-id="${esc(item.id)}" aria-label="Xóa câu khỏi ngân hàng">Xóa</button>
          </div>
        </div>
        ${topic ? `<div class="qbank-topic">Chủ đề: <b>${esc(topic)}</b></div>` : ''}
        <div class="qbank-stem read-formula">${richTextHTML(q.stem || '(Chưa có nội dung)')}</div>
        ${thumbImg ? `<div class="qbank-thumb-wrap"><img class="qbank-thumb" src="${esc(thumbImg.data)}" alt="${esc(thumbImg.caption || 'Hình câu hỏi')}"></div>` : ''}
        ${opts.length ? `<div class="qbank-options">${opts.map((opt, idx) => `<div class="qbank-opt"><b>${String.fromCharCode(65 + idx)}.</b> ${richTextHTML(opt)}</div>`).join('')}</div>` : ''}
        ${tags.length ? `<div class="qbank-tags">${tags.map((t) => `<span class="qbank-tag">#${esc(t)}</span>`).join('')}</div>` : ''}
      </article>`;
    })
    .join('');
}

export function renderAnalyticsModalHTML(report, exam = null, {clientFallback = false} = {}) {
  const r = report || computeClientAnalyticsSummary(exam || {});
  const score = Math.max(0, Math.min(100, Math.round(Number(r.readinessScore) || 0)));
  const scoreTone = score >= 80 ? 'is-good' : score >= 55 ? 'is-warn' : 'is-bad';
  const totalPts = round2(r.totalPoints ?? 0);
  const targetPts = round2(r.targetPoints ?? 10);
  const delta = round2(r.pointsDelta ?? totalPts - targetPts);
  const ptsOk = Math.abs(delta) <= 0.01 && totalPts > 0;
  const estMin = Math.round(Number(r.estimatedMinutes) || 0);
  const examMin = Math.round(Number(r.examMinutes ?? exam?.minutes) || 45);
  const approved = Number(r.approvedCount) || 0;
  const totalQ = Number(r.totalQuestions) || 0;

  const levels = Array.isArray(r.levelDistribution) && r.levelDistribution.length
    ? r.levelDistribution
    : LEVELS.map((label, level) => ({level, label, count: 0, points: 0, percent: 0}));
  const types = Array.isArray(r.typeDistribution) ? r.typeDistribution : [];
  const ans = r.answerDistribution || {A: 0, B: 0, C: 0, D: 0, totalMcq: 0, maxStreak: 0, imbalanced: false};
  const duplicates = Array.isArray(r.duplicates) ? r.duplicates : [];
  const issues = Array.isArray(r.issues) ? r.issues : [];

  const levelBarSegments = levels
    .map((item, idx) => {
      const pct = Math.max(0, Math.min(100, Number(item.percent) || 0));
      if (!pct) return '';
      const color = LEVEL_COLORS[item.level ?? idx] || LEVEL_COLORS[0];
      return `<span class="analytics-bar-seg" style="width:${pct}%;background:${color}" title="${esc(item.label)}: ${item.count} câu (${pct}%)"></span>`;
    })
    .join('');

  const ansTotal = Math.max(1, Number(ans.totalMcq) || 0);
  const answerBars = ['A', 'B', 'C', 'D']
    .map((letter) => {
      const count = Number(ans[letter]) || 0;
      const pct = ans.totalMcq ? Math.round((count / ansTotal) * 100) : 0;
      return `<div class="analytics-ans-row">
        <b>${letter}</b>
        <div class="analytics-ans-track"><span style="width:${pct}%"></span></div>
        <small>${count} (${pct}%)</small>
      </div>`;
    })
    .join('');

  const issueItems = issues.length
    ? issues
        .map((issue) => {
          const sev =
            issue.severity === 'error'
              ? 'error'
              : issue.severity === 'warning' || issue.severity === 'warn'
                ? 'warning'
                : 'info';
          const sevLabel = sev === 'error' ? 'Lỗi' : sev === 'warning' ? 'Cảnh báo' : 'Gợi ý';
          const hasIdx = Number.isInteger(issue.questionIndex) && issue.questionIndex >= 0;
          const qObj = hasIdx && Array.isArray(exam?.questions) ? exam.questions[issue.questionIndex] : null;
          const attrs = hasIdx
            ? `data-action="jump-issue-question" data-q-index="${issue.questionIndex}"${qObj?.id ? ` data-q-id="${esc(qObj.id)}"` : ''}`
            : '';
          if (hasIdx) {
            return `<button type="button" class="analytics-issue is-${sev}" ${attrs}>
              <span class="analytics-sev">${sevLabel}</span>
              <span class="analytics-issue-msg">${esc(issue.message)}</span>
              <span class="analytics-jump">Đến Câu ${issue.questionIndex + 1} →</span>
            </button>`;
          }
          return `<div class="analytics-issue is-${sev} is-static">
            <span class="analytics-sev">${sevLabel}</span>
            <span class="analytics-issue-msg">${esc(issue.message)}</span>
          </div>`;
        })
        .join('')
    : '<p class="analytics-all-good">✓ Chưa phát hiện vấn đề cấu trúc đáng kể. Đề sẵn sàng để giáo viên rà soát cuối và xuất bản.</p>';

  const dupHTML = duplicates.length
    ? `<section class="analytics-section">
        <h3>Cặp câu có nguy cơ trùng lặp (${duplicates.length})</h3>
        <div class="analytics-dup-list">${duplicates
          .map((d) => {
            const q1 = Number(d.q1Index);
            const q2 = Number(d.q2Index);
            const pct = Math.round((Number(d.similarity) || 0) * 100);
            const q2Obj = Array.isArray(exam?.questions) ? exam.questions[q2] : null;
            return `<button type="button" class="analytics-issue is-warning" data-action="jump-issue-question" data-q-index="${q2}"${q2Obj?.id ? ` data-q-id="${esc(q2Obj.id)}"` : ''}>
              <span class="analytics-sev">${pct}%</span>
              <span class="analytics-issue-msg">Câu ${q1 + 1} và Câu ${q2 + 1} có nội dung tương đồng cao</span>
              <span class="analytics-jump">Xem Câu ${q2 + 1} →</span>
            </button>`;
          })
          .join('')}</div>
      </section>`
    : '';

  return `<div class="analytics-modal">
    ${clientFallback ? '<p class="hint">Đang hiển thị phân tích tính trực tiếp trên trình duyệt (máy chủ phân tích chưa phản hồi).</p>' : ''}
    <div class="analytics-kpi-grid">
      <div class="analytics-kpi ${scoreTone}">
        <small>Điểm sẵn sàng</small>
        <strong>${score}<span>/100</span></strong>
      </div>
      <div class="analytics-kpi ${ptsOk ? 'is-good' : 'is-warn'}">
        <small>Tổng điểm</small>
        <strong>${esc(String(totalPts))}<span>/${esc(String(targetPts))}đ</span></strong>
      </div>
      <div class="analytics-kpi ${estMin <= examMin ? 'is-good' : 'is-warn'}">
        <small>Thời lượng ước tính</small>
        <strong>${estMin}<span>/${examMin}p</span></strong>
      </div>
      <div class="analytics-kpi ${totalQ > 0 && approved === totalQ ? 'is-good' : ''}">
        <small>Câu đã duyệt</small>
        <strong>${approved}<span>/${totalQ}</span></strong>
      </div>
    </div>

    <section class="analytics-section">
      <h3>Phân bố 4 mức độ nhận thức</h3>
      <div class="analytics-level-bar" role="img" aria-label="Biểu đồ 4 mức độ nhận thức">${levelBarSegments || '<span class="analytics-bar-empty"></span>'}</div>
      <div class="analytics-level-legend">
        ${levels
          .map((item, idx) => {
            const color = LEVEL_COLORS[item.level ?? idx] || LEVEL_COLORS[0];
            const code = LEVEL_SHORT[item.level ?? idx] || '';
            return `<span class="analytics-legend-chip"><i style="background:${color}"></i><b>${esc(code)}</b> ${esc(item.label)}: ${item.count} câu (${item.percent}%)</span>`;
          })
          .join('')}
      </div>
      ${types.length ? `<div class="analytics-type-chips">${types.map((t) => `<span class="pill">${esc(t.label)}: <b>${t.count}</b> câu${t.points ? ` · ${esc(String(round2(t.points)))}đ` : ''}</span>`).join('')}</div>` : ''}
    </section>

    <section class="analytics-section">
      <div class="analytics-sec-head">
        <h3>Phân bố đáp án trắc nghiệm (A / B / C / D)</h3>
        <span class="hint">${ans.totalMcq ? `${ans.totalMcq} câu trắc nghiệm · Chuỗi dài nhất: ${ans.maxStreak || 0}` : 'Chưa có câu trắc nghiệm đã xác nhận đáp án'}</span>
      </div>
      <div class="analytics-ans-grid">${answerBars}</div>
      ${ans.imbalanced ? '<div class="alert analytics-mini-alert">Phân bố đáp án chưa đều hoặc có chuỗi trùng đáp án dài. Cân nhắc trộn phương án khi tạo mã đề.</div>' : ''}
    </section>

    ${dupHTML}

    <section class="analytics-section">
      <h3>Cảnh báo &amp; Gợi ý (${issues.length})</h3>
      <div class="analytics-issue-list">${issueItems}</div>
    </section>
  </div>`;
}

async function getWorkspaceHeaders() {
  if (typeof activeCtx?.workspaceHeaders === 'function') {
    return activeCtx.workspaceHeaders() || {};
  }
  if (typeof indexedDB !== 'undefined') {
    const db = await import('./storage.js');
    return db.workspaceHeaders();
  }
  return {};
}

async function vipApi(path, {method = 'GET', body} = {}) {
  const headers = {...(await getWorkspaceHeaders())};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {
    method,
    headers,
    ...(body !== undefined ? {body: JSON.stringify(body)} : {}),
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const msg = data?.detail?.message || (typeof data?.detail === 'string' ? data.detail : '') || data?.error || `Lỗi máy chủ (${response.status})`;
    const err = new Error(msg);
    err.status = response.status;
    throw err;
  }
  return data;
}

export function buildBankPayload(exam, q) {
  const subject = String(q?.subject || exam?.subject || '').trim();
  const grade = String(q?.grade ?? exam?.grade ?? '').trim();
  const topic = String(q?.topic || '').trim();
  const points = questionPoints(q) || 1;
  const tags = [subject, grade ? `Lớp ${grade}` : '', topic].filter(Boolean);
  const questionCopy = clone(q);
  if (subject && !questionCopy.subject) questionCopy.subject = subject;
  if (grade && !questionCopy.grade) questionCopy.grade = grade;
  questionCopy.points = points;
  return {subject, grade, topic, points, question: questionCopy, tags};
}

export async function saveQuestionToBank(c, questionId) {
  const e = c.exam();
  const targetId = questionId || c.getSelected?.();
  const idx = e.questions.findIndex((q) => q.id === targetId);
  if (idx < 0) {
    c.toast('Chọn một câu hỏi để lưu vào Ngân hàng câu hỏi.');
    return null;
  }
  const q = e.questions[idx];
  const res = await vipApi('/api/question-bank', {method: 'POST', body: buildBankPayload(e, q)});
  if (res?.duplicateOf) {
    c.toast(`Câu ${idx + 1} tương tự câu đã có trong Ngân hàng (trùng lặp).`);
  } else {
    c.toast(`Đã lưu Câu ${idx + 1} vào Ngân hàng câu hỏi`);
  }
  return res?.item || null;
}

export async function saveAllQuestionsToBank(c) {
  const e = c.exam();
  if (!e.questions.length) {
    c.toast('Đề hiện tại chưa có câu hỏi nào để lưu vào Ngân hàng.');
    return 0;
  }
  let saved = 0;
  let dupCount = 0;
  for (const q of e.questions) {
    const res = await vipApi('/api/question-bank', {method: 'POST', body: buildBankPayload(e, q)});
    if (res?.duplicateOf) dupCount += 1;
    else saved += 1;
  }
  c.toast(
    dupCount
      ? `Đã lưu ${saved} câu mới vào Ngân hàng (${dupCount} câu đã có/trùng lặp).`
      : `Đã lưu ${saved}/${e.questions.length} câu vào Ngân hàng câu hỏi`,
  );
  if (document.querySelector('#qbank-list')) {
    await refreshQuestionBankList(c);
  }
  return saved + dupCount;
}

function hasActiveBankFilters() {
  return Boolean(
    bankFilters.q.trim() ||
    bankFilters.subject ||
    bankFilters.grade ||
    bankFilters.topic ||
    bankFilters.qtype ||
    (bankFilters.level !== '' && bankFilters.level != null),
  );
}

function paintQuestionBankList() {
  const listEl = document.querySelector('#qbank-list');
  const countEl = document.querySelector('#qbank-count');
  const resetBtn = document.querySelector('#qbank-reset');
  const loadMoreBtn = document.querySelector('#qbank-load-more');
  if (!listEl) return;
  const total = Math.max(bankTotal || 0, bankCache.length);
  if (countEl) {
    countEl.textContent = `Hiển thị ${bankCache.length} / ${total} câu hỏi trong kho`;
  }
  if (resetBtn) {
    resetBtn.hidden = !hasActiveBankFilters();
  }
  listEl.innerHTML = renderQuestionBankItemsHTML(bankCache);
  if (loadMoreBtn) {
    loadMoreBtn.hidden = !bankHasMore;
    loadMoreBtn.disabled = false;
  }
}

function populateQuestionBankFilterOptions(e) {
  const subjectSel = document.querySelector('#qbank-subject');
  const gradeSel = document.querySelector('#qbank-grade');
  const topicSel = document.querySelector('#qbank-topic');
  const facetSubjects = Array.isArray(bankFacets?.subjects) ? bankFacets.subjects : [];
  const facetGrades = Array.isArray(bankFacets?.grades) ? bankFacets.grades : [];
  const facetTopics = Array.isArray(bankFacets?.topics) ? bankFacets.topics : [];
  if (subjectSel) {
    const subjects = [
      ...new Set([
        ...(facetSubjects.length ? facetSubjects : []),
        ...(bankFilters.subject ? [bankFilters.subject] : []),
        ...(!facetSubjects.length && e?.subject ? [e.subject] : []),
        ...(!facetSubjects.length ? bankCache.map((it) => it.subject || it.question?.subject) : []),
      ].filter(Boolean)),
    ].sort((a, b) => a.localeCompare(b, 'vi-VN'));
    subjectSel.innerHTML = `<option value="">Tất cả môn</option>${subjects.map((s) => `<option value="${esc(s)}" ${bankFilters.subject === s ? 'selected' : ''}>${esc(s)}</option>`).join('')}`;
  }
  if (gradeSel) {
    const grades = [
      ...new Set([
        ...(facetGrades.length ? facetGrades : []),
        ...(bankFilters.grade ? [bankFilters.grade] : []),
        ...(!facetGrades.length && e?.grade ? [String(e.grade)] : []),
        ...(!facetGrades.length ? bankCache.map((it) => String(it.grade ?? it.question?.grade ?? '').trim()) : []),
      ].filter(Boolean)),
    ].sort((a, b) => Number(a) - Number(b));
    gradeSel.innerHTML = `<option value="">Tất cả lớp</option>${grades.map((g) => `<option value="${esc(g)}" ${bankFilters.grade === g ? 'selected' : ''}>Lớp ${esc(g)}</option>`).join('')}`;
  }
  if (topicSel) {
    const topics = [
      ...new Set([
        ...(facetTopics.length ? facetTopics : []),
        ...(bankFilters.topic ? [bankFilters.topic] : []),
        ...(!facetTopics.length ? bankCache.map((it) => it.topic || it.question?.topic) : []),
      ].filter(Boolean)),
    ].sort((a, b) => a.localeCompare(b, 'vi-VN'));
    topicSel.innerHTML = `<option value="">Tất cả chủ đề</option>${topics.map((t) => `<option value="${esc(t)}" ${bankFilters.topic === t ? 'selected' : ''}>${esc(t)}</option>`).join('')}`;
  }
}

async function refreshQuestionBankList(c, {append = false} = {}) {
  const listEl = document.querySelector('#qbank-list');
  const loadMoreBtn = document.querySelector('#qbank-load-more');
  const seq = ++bankRequestSeq;
  if (!append && listEl) {
    listEl.innerHTML = '<div class="busy"><span class="spinner"></span>Đang tải Ngân hàng câu hỏi…</div>';
  }
  if (append && loadMoreBtn) {
    loadMoreBtn.disabled = true;
  }
  try {
    const params = new URLSearchParams();
    if (bankFilters.q.trim()) params.set('q', bankFilters.q.trim());
    if (bankFilters.subject) params.set('subject', bankFilters.subject);
    if (bankFilters.grade) params.set('grade', bankFilters.grade);
    if (bankFilters.topic) params.set('topic', bankFilters.topic);
    if (bankFilters.qtype) params.set('qtype', bankFilters.qtype);
    if (bankFilters.level !== '' && bankFilters.level != null) params.set('level', String(bankFilters.level));
    params.set('limit', '50');
    params.set('offset', String(append ? bankCache.length : 0));

    const data = await vipApi(`/api/question-bank?${params.toString()}`);
    if (seq !== bankRequestSeq) return;
    const incoming = Array.isArray(data?.items) ? data.items : [];
    if (append) {
      const seen = new Set(bankCache.map((it) => it.id));
      bankCache = [...bankCache, ...incoming.filter((it) => !seen.has(it.id))];
    } else {
      bankCache = incoming;
    }
    bankTotal = Number.isFinite(Number(data?.total)) ? Number(data.total) : bankCache.length;
    bankHasMore = typeof data?.hasMore === 'boolean' ? data.hasMore : bankCache.length < bankTotal;
    if (data?.facets && typeof data.facets === 'object') {
      bankFacets = data.facets;
    }
    populateQuestionBankFilterOptions(c.exam());
    paintQuestionBankList();
  } catch (err) {
    if (seq !== bankRequestSeq) return;
    if (loadMoreBtn) loadMoreBtn.disabled = false;
    if (!append && listEl) {
      listEl.innerHTML = `<div class="alert">Chưa tải được Ngân hàng câu hỏi: ${esc(err.message)}</div>`;
    } else {
      c.toast(`Chưa tải thêm được câu hỏi: ${err.message}`);
    }
  }
}

export async function openQuestionBank(c) {
  clearTimeout(bankSearchTimer);
  bankFilters = {q: '', subject: '', grade: '', topic: '', qtype: '', level: ''};
  bankCache = [];
  bankTotal = 0;
  bankHasMore = false;
  bankFacets = null;
  c.modal(
    'Ngân hàng câu hỏi thông minh',
    `<div class="qbank-modal">
      <div class="qbank-toolbar">
        <input id="qbank-search" type="search" placeholder="Tìm nội dung, chủ đề, thẻ (hỗ trợ không dấu)…" aria-label="Tìm trong ngân hàng câu hỏi">
        <button type="button" class="qbank-save-all-btn" data-action="save-all-to-bank">★ Lưu cả đề vào kho</button>
      </div>
      <div class="qbank-filters">
        <select id="qbank-subject" aria-label="Lọc theo môn"><option value="">Tất cả môn</option></select>
        <select id="qbank-grade" aria-label="Lọc theo lớp"><option value="">Tất cả lớp</option></select>
        <select id="qbank-topic" aria-label="Lọc theo chủ đề"><option value="">Tất cả chủ đề</option></select>
        <select id="qbank-qtype" aria-label="Lọc theo dạng câu">
          <option value="">Tất cả dạng</option>
          ${Object.entries(QUESTION_TYPES).map(([k, label]) => `<option value="${esc(k)}">${esc(label)}</option>`).join('')}
        </select>
        <select id="qbank-level" aria-label="Lọc theo mức độ">
          <option value="">Tất cả mức độ</option>
          ${LEVELS.map((label, idx) => `<option value="${idx}">${esc(label)}</option>`).join('')}
        </select>
      </div>
      <div class="qbank-count-row">
        <div id="qbank-count" class="qbank-count">Đang tải…</div>
        <button type="button" id="qbank-reset" class="tiny-btn ghost" data-action="reset-bank-filters" hidden>Xóa bộ lọc</button>
      </div>
      <div id="qbank-list" class="qbank-list"></div>
      <div class="qbank-more-wrap"><button type="button" id="qbank-load-more" data-action="load-more-bank" hidden>Tải thêm</button></div>
    </div>`,
    'Lưu câu hỏi hay từ mọi đề thi, tìm không dấu tiếng Việt và chèn lại kèm hoàn tác Ctrl+Z.',
  );

  const modalRoot = document.querySelector('.qbank-modal');
  if (modalRoot) {
    modalRoot.addEventListener('input', (ev) => {
      if (ev.target.id === 'qbank-search') {
        bankFilters.q = ev.target.value;
        clearTimeout(bankSearchTimer);
        bankSearchTimer = setTimeout(() => {
          refreshQuestionBankList(c);
        }, 200);
      }
    });
    modalRoot.addEventListener('change', (ev) => {
      const id = ev.target.id;
      if (id === 'qbank-subject') bankFilters.subject = ev.target.value;
      else if (id === 'qbank-grade') bankFilters.grade = ev.target.value;
      else if (id === 'qbank-topic') bankFilters.topic = ev.target.value;
      else if (id === 'qbank-qtype') bankFilters.qtype = ev.target.value;
      else if (id === 'qbank-level') bankFilters.level = ev.target.value;
      else return;
      refreshQuestionBankList(c);
    });
  }

  await refreshQuestionBankList(c);
}

async function insertFromBank(c, itemId) {
  if (!itemId) return;
  const res = await vipApi(`/api/question-bank/${encodeURIComponent(itemId)}/clone`, {method: 'POST'});
  const cloned = res?.question ? clone(res.question) : null;
  if (!cloned) throw new Error('Không lấy được bản sao câu hỏi từ Ngân hàng.');
  if (!cloned.id) cloned.id = uid();
  cloned.v = 1;
  cloned.check = null;
  if (!Array.isArray(cloned.options)) {
    cloned.options = ['mcq', 'truefalse'].includes(cloned.type || 'mcq') ? ['', '', '', ''] : [];
  }
  c.change('Chèn câu từ Ngân hàng câu hỏi', (e) => {
    e.questions.push(cloned);
    check(e, cloned);
  });
  if (c.getViewMode?.() === 'home') {
    c.setViewMode?.('workspace');
  }
  c.setSelected?.(cloned.id);
  c.toast('Đã chèn câu hỏi từ Ngân hàng vào đề (Ctrl+Z để hoàn tác).');
}

async function deleteBankItem(c, itemId) {
  if (!itemId) return;
  await vipApi(`/api/question-bank/${encodeURIComponent(itemId)}`, {method: 'DELETE'});
  bankCache = bankCache.filter((it) => it.id !== itemId);
  bankTotal = Math.max(bankCache.length, bankTotal - 1);
  paintQuestionBankList();
  c.toast('Đã xóa câu hỏi khỏi Ngân hàng.');
}

export async function openExamAnalytics(c) {
  const e = clone(c.exam());
  c.modal(
    'Phân tích chất lượng & Ma trận đề',
    '<div class="busy"><span class="spinner"></span>Đang phân tích cấu trúc, mức độ nhận thức và đáp án của đề…</div>',
    `${esc(e.title)} · ${e.questions.length} câu`,
  );
  let report = null;
  let clientFallback = false;
  try {
    report = await vipApi('/api/exams/analyze', {method: 'POST', body: {exam: e}});
  } catch {
    report = computeClientAnalyticsSummary(e);
    clientFallback = true;
  }
  const dialog = document.querySelector('#dialog');
  if (!dialog?.open) return;
  const body = dialog.querySelector('.modal-body');
  if (body) {
    body.innerHTML = renderAnalyticsModalHTML(report, e, {clientFallback});
  }
}

function jumpToIssueQuestion(c, node) {
  const e = c.exam();
  const qIdAttr = node?.dataset?.qId;
  const qIdx = Number(node?.dataset?.qIndex);
  const target =
    (qIdAttr ? e.questions.find((q) => q.id === qIdAttr) : null) ||
    (Number.isInteger(qIdx) && qIdx >= 0 ? e.questions[qIdx] : null);
  if (!target) {
    c.toast('Không tìm thấy câu hỏi tương ứng trên trang đề.');
    return;
  }
  const dialog = document.querySelector('#dialog');
  if (dialog?.open) dialog.close();
  if (c.getViewMode?.() === 'home') {
    c.setViewMode?.('workspace');
  }
  c.setSelected?.(target.id);
  const el = document.getElementById('q-' + target.id);
  if (el) {
    el.scrollIntoView({block: 'center', behavior: 'smooth'});
    el.classList.add('is-jump-highlight');
    setTimeout(() => el.classList.remove('is-jump-highlight'), 1400);
  }
}

export async function exportOmrSheet(c, {teacher = false, format = 'html'} = {}) {
  const e = clone(c.exam());
  const codeSelect = document.querySelector('#export-variant-code');
  const rawCode = codeSelect?.value;
  const variantCode = rawCode !== undefined && rawCode !== '' ? String(101 + Number(rawCode)) : '101';

  const result = await vipApi('/api/exports/omr-sheet', {
    method: 'POST',
    body: {exam: e, teacher: Boolean(teacher), variantCode, format},
  });

  if (format === 'pdf') {
    if (!result?.downloadUrl) throw new Error('Máy chủ chưa trả đường dẫn tải phiếu OMR PDF.');
    const link = document.createElement('a');
    link.href = result.downloadUrl;
    link.download = result.name || `Phieu-OMR-${variantCode}.pdf`;
    document.body.append(link);
    link.click();
    link.remove();
    c.toast(`Đã tải phiếu tô OMR PDF (${result.name || 'Bộ GD&ĐT 2025'}).`);
    return result;
  }

  if (result?.html) {
    const win = window.open('about:blank', '_blank');
    if (win) {
      win.document.write(result.html);
      win.document.close();
      c.toast(teacher ? 'Đã mở Phiếu OMR đáp án giáo viên (Bộ GD&ĐT 2025).' : 'Đã mở Phiếu tô OMR học sinh A4 (Bộ GD&ĐT 2025).');
      return result;
    }
  }
  if (result?.downloadUrl) {
    window.open(result.downloadUrl, '_blank', 'noopener');
    c.toast('Đã xuất Phiếu tô OMR (Bộ GD&ĐT 2025).');
    return result;
  }
  throw new Error('Không thể mở bản xem in phiếu OMR.');
}

function clearOutlineDragClasses() {
  document
    .querySelectorAll('.outline-item.is-dragging, .outline-item.is-drop-before, .outline-item.is-drop-after')
    .forEach((node) => node.classList.remove('is-dragging', 'is-drop-before', 'is-drop-after'));
}

function markOutlineItemsDraggable() {
  document.querySelectorAll('.side-content .outline-item[data-id], .outline .outline-item[data-id]').forEach((item) => {
    item.setAttribute('draggable', 'true');
  });
}

export function bindOutlineDragReorder(c) {
  activeCtx = c;
  markOutlineItemsDraggable();

  if (!dragState.refreshBound) {
    dragState.refreshBound = true;
    document.addEventListener('studio-refreshed', markOutlineItemsDraggable);
  }

  if (dragState.listenersBound) return;
  dragState.listenersBound = true;

  const findOutlineItem = (target) => target?.closest?.('.side-content .outline-item[data-id], .outline .outline-item[data-id]') || null;

  document.addEventListener('dragstart', (event) => {
    const item = findOutlineItem(event.target);
    if (!item) return;
    const id = item.dataset.id;
    if (!id) return;
    dragState.draggedId = id;
    item.classList.add('is-dragging');
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', id);
    }
  });

  document.addEventListener('dragover', (event) => {
    if (!dragState.draggedId) return;
    const item = findOutlineItem(event.target);
    if (!item || item.dataset.id === dragState.draggedId) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    const rect = item.getBoundingClientRect();
    const after = event.clientY > rect.top + rect.height / 2;
    document
      .querySelectorAll('.outline-item.is-drop-before, .outline-item.is-drop-after')
      .forEach((n) => {
        if (n !== item) n.classList.remove('is-drop-before', 'is-drop-after');
      });
    item.classList.toggle('is-drop-before', !after);
    item.classList.toggle('is-drop-after', after);
  });

  document.addEventListener('dragleave', (event) => {
    if (!dragState.draggedId) return;
    const item = findOutlineItem(event.target);
    if (!item) return;
    if (event.relatedTarget && item.contains(event.relatedTarget)) return;
    item.classList.remove('is-drop-before', 'is-drop-after');
  });

  document.addEventListener('drop', (event) => {
    const draggedId = dragState.draggedId;
    if (!draggedId) return;
    const item = findOutlineItem(event.target);
    if (!item) {
      dragState.draggedId = null;
      clearOutlineDragClasses();
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    const targetId = item.dataset.id;
    const position = item.classList.contains('is-drop-after') ? 'after' : 'before';
    dragState.draggedId = null;
    clearOutlineDragClasses();

    if (!activeCtx || !targetId || draggedId === targetId) return;
    const e = activeCtx.exam();
    const beforeIds = e.questions.map((q) => q.id);
    const reordered = reorderQuestionsByIds(e.questions, draggedId, targetId, position);
    const afterIds = reordered.map((q) => q.id);
    if (beforeIds.every((id, i) => id === afterIds[i])) return;

    activeCtx.change('Sắp xếp lại thứ tự câu hỏi', (draft) => {
      draft.questions = reorderQuestionsByIds(draft.questions, draggedId, targetId, position);
    });
    activeCtx.setSelected?.(draggedId);
    activeCtx.toast('Đã đổi thứ tự câu hỏi (Ctrl+Z để hoàn tác).');
  });

  document.addEventListener('dragend', () => {
    if (!dragState.draggedId) return;
    dragState.draggedId = null;
    clearOutlineDragClasses();
  });
}

export function mountVipTools(c) {
  activeCtx = c;
  bindOutlineDragReorder(c);
}

export async function handleVipAction(action, node, c) {
  activeCtx = c;
  switch (action) {
    case 'save-to-bank':
      await saveQuestionToBank(c, node?.dataset?.id);
      return true;
    case 'save-all-to-bank':
      await saveAllQuestionsToBank(c);
      return true;
    case 'question-bank':
      await openQuestionBank(c);
      return true;
    case 'insert-from-bank':
      await insertFromBank(c, node?.dataset?.id);
      return true;
    case 'delete-bank-item':
      await deleteBankItem(c, node?.dataset?.id);
      return true;
    case 'load-more-bank':
      await refreshQuestionBankList(c, {append: true});
      return true;
    case 'reset-bank-filters':
      clearTimeout(bankSearchTimer);
      bankFilters = {q: '', subject: '', grade: '', topic: '', qtype: '', level: ''};
      for (const [sel, val] of [
        ['#qbank-search', ''],
        ['#qbank-subject', ''],
        ['#qbank-grade', ''],
        ['#qbank-topic', ''],
        ['#qbank-qtype', ''],
        ['#qbank-level', ''],
      ]) {
        const el = document.querySelector(sel);
        if (el) el.value = val;
      }
      await refreshQuestionBankList(c);
      return true;
    case 'exam-analytics':
      await openExamAnalytics(c);
      return true;
    case 'jump-issue-question':
      jumpToIssueQuestion(c, node);
      return true;
    case 'export-omr-student':
      await exportOmrSheet(c, {teacher: false, format: 'html'});
      return true;
    case 'export-omr-teacher':
      await exportOmrSheet(c, {teacher: true, format: 'html'});
      return true;
    case 'export-omr-pdf':
      await exportOmrSheet(c, {teacher: false, format: 'pdf'});
      return true;
    default:
      return false;
  }
}
