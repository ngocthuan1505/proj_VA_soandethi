/**
 * Trang chủ Cá Voi Xanh + Trợ lý Chủ động (Chiến dịch nhiều đề, nhắc rà soát hôm sau, hạn nộp).
 */

import {esc} from './core.js';
import {mountVoiceButton} from './voice-input.js';

const WHALE_BADGE_SVG = `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M3 13c0-4.2 3.8-7 8.8-7 3.6 0 6.2 1.8 6.8 4.4l2.9-1.7c.3-.2.7.1.6.4-.5 2-1.4 3.4-2.8 4.2-.8 2.4-3.7 3.7-7.7 3.7C6.6 17 3 15.6 3 13z" fill="currentColor" fill-opacity="0.22" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="7.5" cy="11.8" r="1" fill="currentColor"/><path d="M4 19.2c2.2 1.1 4.4 1.1 6.6 0s4.4-1.1 6.6 0c1.1.5 2 .7 2.8.6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`;

const EXAMPLE_PROMPTS = [
  'Đề Toán 11 CK1 chuẩn GDPT 2018',
  'Đề Ngữ văn 10 đọc hiểu',
  'Đề Tiếng Anh 12 THPT',
  'Bộ 10 đề ôn tập Toán 9',
];

const WF_LABELS = {
  draft: 'Dự thảo',
  reviewed: 'Đã rà soát',
  approved: 'Bản duyệt',
  printed: 'Bản đã in',
};

let cachedDigest = null;

function emptyDigest() {
  return {
    badgeCount: 0,
    greeting: 'Chào thầy cô',
    activeCampaigns: [],
    nextDayReviewNudges: [],
    urgentDeadlines: [],
    pendingRoomGrading: {count: 0, rooms: []},
  };
}

export function getCachedProactiveDigest() {
  return cachedDigest || emptyDigest();
}

export async function fetchProactiveDigest(headers = {}) {
  try {
    const res = await fetch('/api/proactive/digest', {headers});
    if (!res.ok) {
      cachedDigest = emptyDigest();
      return cachedDigest;
    }
    const data = await res.json();
    cachedDigest = {
      ...emptyDigest(),
      ...(data && typeof data === 'object' ? data : {}),
    };
    return cachedDigest;
  } catch {
    cachedDigest = emptyDigest();
    return cachedDigest;
  }
}

export function parsePromptIntent(rawPrompt) {
  const text = String(rawPrompt || '').trim();
  const subjectRules = [
    [/\bto[aá]n\b/i, 'Toán'],
    [/\bng[uữ]\s*v[aă]n\b|\bv[aă]n\s*h[oọ]c\b|\bđ[oọ]c\s*hi[eể]u\b/i, 'Ngữ văn'],
    [/\bti[eế]ng\s*anh\b|\benglish\b/i, 'Tiếng Anh'],
    [/\bv[aậ]t\s*l[iíý]\b/i, 'Vật lí'],
    [/\bh[oó]a\s*h[oọ]c\b|\bh[oó]a\b/i, 'Hoá học'],
    [/\bsinh\s*h[oọ]c\b/i, 'Sinh học'],
    [/\bl[iị]ch\s*s[uử]\b/i, 'Lịch sử'],
    [/\bđ[iị]a\s*l[iíý]\b/i, 'Địa lí'],
    [/\btin\s*h[oọ]c\b/i, 'Tin học'],
    [/\bgdcd\b|\bgi[aá]o\s*d[uụ]c\s*c[oô]ng\s*d[aâ]n\b/i, 'GDCD'],
  ];
  let subject = 'Toán';
  for (const [re, name] of subjectRules) {
    if (re.test(text)) {
      subject = name;
      break;
    }
  }
  const gradeMatch = text.match(/(?:l[oớ]p|kh[oố]i|to[aá]n|v[aă]n|anh|l[iíý]|h[oó]a|sinh|s[uử]|đ[iị]a|tin)\s*(\d{1,2})\b/i);
  const grade = gradeMatch ? gradeMatch[1] : '10';
  const multiMatch = text.match(/(?:b[oộ]|chi[eế]n\s*d[iị]ch|chu[oỗ]i|lo[aạ]t|t[aạ]o|so[aạ]n)\s+(\d{1,2})\s+đ[eề]/i);
  const parsedCount = multiMatch ? Number(multiMatch[1]) : 0;
  const campaignTarget = parsedCount >= 2 ? Math.min(50, parsedCount) : 0;
  const title = text.length > 90 ? text.slice(0, 87).trim() + '…' : text || `Đề ${subject} lớp ${grade}`;
  return {subject, grade, title, campaignTarget};
}

function ensureHomeStyles() {
  if (typeof document === 'undefined' || document.getElementById('mach-home-style')) return;
  const style = document.createElement('style');
  style.id = 'mach-home-style';
  style.textContent = `
    .home-view {
      flex: 1 1 auto;
      overflow-y: auto;
      background:
        radial-gradient(circle at 12% 8%, rgba(30, 120, 200, 0.09), transparent 42%),
        radial-gradient(circle at 88% 14%, rgba(15, 76, 129, 0.08), transparent 38%),
        var(--bg-canvas, #f3f7fb);
      padding: 24px 20px 44px;
    }
    .home-shell {
      max-width: 1180px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .home-hero {
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
      gap: 24px;
      align-items: stretch;
    }
    .home-hero-left {
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 14px;
      padding: 8px 4px;
    }
    .home-whale-badge {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      align-self: flex-start;
      padding: 5px 12px;
      border-radius: var(--radius-pill, 999px);
      background: var(--brand-soft, #e8f2fc);
      border: 1px solid var(--brand-border, #b6d4f0);
      color: var(--brand, #0f4c81);
      font-size: 12px;
      font-weight: 700;
    }
    .home-hero-left h1 {
      margin: 0;
      font-size: clamp(26px, 3vw, 36px);
      line-height: 1.2;
      color: var(--ink-strong, #0f1e2e);
      letter-spacing: -0.02em;
    }
    .home-hero-lead {
      margin: 0;
      font-size: 14.5px;
      line-height: 1.6;
      color: var(--ink-muted, #4b6075);
      max-width: 54ch;
    }
    .home-cta-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 4px;
    }
    .home-cta-row button {
      height: 40px;
      padding: 0 16px;
      border-radius: 10px;
      font-size: 13.5px;
      font-weight: 600;
    }
    .home-tools-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 6px;
    }
    .home-tools-strip button {
      height: 32px;
      padding: 0 11px;
      font-size: 12.5px;
      border-radius: var(--radius-pill, 999px);
      background: var(--bg-surface, #fff);
      border: 1px solid var(--line, #dbe6f2);
      color: var(--ink, #1a2b3c);
    }
    .home-tools-strip button:hover {
      border-color: var(--brand-border, #b6d4f0);
      background: var(--brand-soft, #e8f2fc);
      color: var(--brand, #0f4c81);
    }
    .home-prompt-card {
      background: var(--bg-surface, #fff);
      border: 1px solid var(--line, #dbe6f2);
      border-radius: var(--radius-xl, 18px);
      box-shadow: var(--shadow-md, 0 10px 28px rgba(15, 30, 46, 0.12));
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .home-a4-preview {
      display: grid;
      grid-template-columns: 76px minmax(0, 1fr);
      gap: 12px;
      align-items: center;
      padding: 10px 12px;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--bg-subtle, #edf3fa), var(--brand-soft, #e8f2fc));
      border: 1px solid var(--line, #dbe6f2);
    }
    .home-a4-sheet {
      width: 72px;
      height: 92px;
      background: #fff;
      border: 1px solid var(--line-strong, #c2d4e8);
      border-radius: 5px;
      box-shadow: 0 3px 10px rgba(15, 30, 46, 0.08);
      padding: 7px 6px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .home-a4-sheet i {
      display: block;
      height: 4px;
      border-radius: 2px;
      background: var(--line, #dbe6f2);
    }
    .home-a4-sheet i.h { height: 5px; width: 70%; margin: 0 auto 2px; background: var(--brand, #0f4c81); opacity: 0.75; }
    .home-a4-sheet i.s { width: 82%; }
    .home-a4-sheet i.m { width: 64%; }
    .home-a4-meta b { display: block; font-size: 13px; color: var(--ink-strong, #0f1e2e); }
    .home-a4-meta small { display: block; font-size: 12px; color: var(--ink-muted, #4b6075); margin-top: 2px; line-height: 1.45; }
    #home-prompt-form {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    #home-prompt-input {
      width: 100%;
      min-height: 86px;
      resize: vertical;
      border-radius: 12px;
      border: 1px solid var(--line-strong, #c2d4e8);
      padding: 10px 12px;
      font-size: 14px;
      line-height: 1.5;
    }
    #home-prompt-input:focus {
      border-color: var(--brand, #0f4c81);
      box-shadow: 0 0 0 3px rgba(15, 76, 129, 0.12);
      outline: none;
    }
    .home-prompt-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
    }
    .home-prompt-left-actions, .home-prompt-right-actions {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .home-prompt-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .home-prompt-chip {
      font-size: 12px;
      padding: 4px 10px;
      border-radius: var(--radius-pill, 999px);
      background: var(--bg-elevated, #fafcff);
      border: 1px solid var(--line, #dbe6f2);
      color: var(--ink-muted, #4b6075);
    }
    .home-prompt-chip:hover {
      background: var(--brand-soft, #e8f2fc);
      border-color: var(--brand-border, #b6d4f0);
      color: var(--brand, #0f4c81);
    }
    .home-section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .home-section-head h2 {
      margin: 0;
      font-size: 16.5px;
      color: var(--ink-strong, #0f1e2e);
    }
    .home-section-head p {
      margin: 2px 0 0;
      font-size: 12.5px;
      color: var(--ink-muted, #4b6075);
    }
    .home-proactive-strip {
      background: var(--bg-surface, #fff);
      border: 1px solid var(--line, #dbe6f2);
      border-radius: var(--radius-lg, 14px);
      padding: 16px;
      box-shadow: var(--shadow-xs, 0 1px 2px rgba(15, 30, 46, 0.05));
    }
    .home-proactive-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
    }
    .proactive-card {
      border: 1px solid var(--line, #dbe6f2);
      border-radius: 12px;
      padding: 12px;
      background: var(--bg-elevated, #fafcff);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .proactive-card.is-warn {
      border-color: var(--warn-border, #f59e0b);
      background: var(--warn-bg, #fffbeb);
    }
    .proactive-card-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
    }
    .proactive-card-title {
      font-size: 13.5px;
      font-weight: 700;
      color: var(--ink-strong, #0f1e2e);
      margin: 0;
    }
    .proactive-card-msg {
      font-size: 12.5px;
      color: var(--ink-muted, #4b6075);
      margin: 0;
      line-height: 1.45;
    }
    .proactive-progress {
      height: 7px;
      border-radius: 999px;
      background: var(--line, #dbe6f2);
      overflow: hidden;
    }
    .proactive-progress > span {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--brand, #0f4c81), var(--accent, #1e78c8));
      border-radius: 999px;
    }
    .home-recent-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .home-recent-card {
      background: var(--bg-surface, #fff);
      border: 1px solid var(--line, #dbe6f2);
      border-radius: 12px;
      padding: 14px;
      text-align: left;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
      width: 100%;
    }
    .home-recent-card:hover {
      border-color: var(--brand-border, #b6d4f0);
      box-shadow: var(--shadow-sm, 0 2px 8px rgba(15, 30, 46, 0.07));
      transform: translateY(-1px);
    }
    .home-recent-card b {
      font-size: 14px;
      color: var(--ink-strong, #0f1e2e);
      line-height: 1.35;
    }
    .home-recent-meta {
      font-size: 12px;
      color: var(--ink-muted, #4b6075);
    }
    .proactive-bell-btn {
      position: relative;
      padding: 4px 8px !important;
      min-width: 34px;
    }
    .proactive-bell-badge {
      position: absolute;
      top: -3px;
      right: -3px;
      min-width: 17px;
      height: 17px;
      padding: 0 4px;
      border-radius: 999px;
      background: var(--danger, #b91c1c);
      color: #fff;
      font-size: 10.5px;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
    }
    @media (max-width: 960px) {
      .home-hero { grid-template-columns: 1fr; }
      .home-recent-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 640px) {
      .home-view { padding: 14px 12px 32px; }
      .home-recent-grid { grid-template-columns: 1fr; }
    }
  `;
  document.head.appendChild(style);
}

function formatDateShort(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
    });
  } catch {
    return '';
  }
}

export function renderProactiveCardsHTML(digest, state = null) {
  const cards = [];

  for (const camp of digest.activeCampaigns || []) {
    const pct = Math.min(100, Math.round((camp.completedCount / Math.max(1, camp.targetCount)) * 100));
    cards.push(`
      <article class="proactive-card" data-campaign-id="${esc(camp.id)}">
        <div class="proactive-card-head">
          <h3 class="proactive-card-title">${esc(camp.title)}</h3>
          <span class="pill">${camp.completedCount}/${camp.targetCount} đề</span>
        </div>
        <div class="proactive-progress" aria-label="Tiến độ ${pct}%"><span style="width:${pct}%"></span></div>
        <p class="proactive-card-msg">${esc(camp.message || `Đã xong ${camp.completedCount}/${camp.targetCount} đề — Bấm soạn tiếp đề ${camp.nextOrdinal}`)}</p>
        <div class="buttons">
          <button type="button" class="primary tiny-btn" data-action="home-continue-campaign" data-id="${esc(camp.id)}" data-title="${esc(camp.title)}" data-subject="${esc(camp.subject || '')}" data-grade="${esc(camp.grade || '')}" data-ordinal="${camp.nextOrdinal}">Soạn tiếp đề ${camp.nextOrdinal}</button>
        </div>
      </article>
    `);
  }

  for (const nudge of digest.nextDayReviewNudges || []) {
    cards.push(`
      <article class="proactive-card is-warn" data-review-exam="${esc(nudge.examId)}">
        <div class="proactive-card-head">
          <h3 class="proactive-card-title">Rà soát: ${esc(nudge.title)}</h3>
          <span class="pill warn">${nudge.draftQuestionCount} câu chưa duyệt</span>
        </div>
        <p class="proactive-card-msg">${esc(nudge.message)}</p>
        <div class="buttons">
          <button type="button" class="tiny-btn" data-action="home-open-exam" data-id="${esc(nudge.examId)}">Mở rà soát ngay</button>
        </div>
      </article>
    `);
  }

  for (const dl of digest.urgentDeadlines || []) {
    const isRem = dl.source === 'reminder';
    const attachedExamId =
      isRem && (dl.targetType === 'exam' || (!dl.targetType && dl.targetId))
        ? String(dl.targetId || '').trim()
        : '';
    const localExam =
      attachedExamId && Array.isArray(state?.exams)
        ? state.exams.find((ex) => ex && ex.id === attachedExamId)
        : null;
    const attachedExamTitle = String(dl.targetTitle || dl.examTitle || localExam?.title || '').trim();
    cards.push(`
      <article class="proactive-card ${dl.overdue ? 'is-warn' : ''}" data-deadline-id="${esc(dl.id)}">
        <div class="proactive-card-head">
          <h3 class="proactive-card-title">${esc(dl.title)}</h3>
          <span class="pill ${dl.overdue ? 'warn' : ''}">${dl.overdue ? 'Quá hạn' : 'Sắp đến hạn'}</span>
        </div>
        <p class="proactive-card-msg">${esc(dl.message)}${dl.dueAt ? ` · ${esc(formatDateShort(dl.dueAt))}` : ''}</p>
        ${
          isRem && attachedExamId
            ? `<p class="proactive-card-msg" data-reminder-exam="${esc(attachedExamId)}"><strong>Đề gắn kèm:</strong> ${esc(attachedExamTitle || attachedExamId)}</p>`
            : ''
        }
        <div class="buttons">
          ${
            isRem
              ? `${attachedExamId ? `<button type="button" class="tiny-btn primary" data-action="home-open-exam" data-id="${esc(attachedExamId)}">Mở đề</button>` : ''}
                 <button type="button" class="tiny-btn" data-action="proactive-done-reminder" data-id="${esc(dl.id)}">Đã xong</button>
                 <button type="button" class="tiny-btn ghost" data-action="proactive-snooze-reminder" data-id="${esc(dl.id)}" data-hours="4">Hoãn 4 giờ</button>`
              : `<button type="button" class="tiny-btn" data-action="home-continue-campaign" data-id="${esc(dl.id)}" data-title="${esc(dl.title)}">Mở chiến dịch</button>`
          }
        </div>
      </article>
    `);
  }

  if (digest.pendingRoomGrading?.count > 0) {
    cards.push(`
      <article class="proactive-card is-warn">
        <div class="proactive-card-head">
          <h3 class="proactive-card-title">Chấm bài tự luận phòng thi</h3>
          <span class="pill warn">${digest.pendingRoomGrading.count} bài chờ chấm</span>
        </div>
        <p class="proactive-card-msg">Có ${digest.pendingRoomGrading.count} bài làm học sinh cần chấm tay trong ${digest.pendingRoomGrading.rooms?.length || 1} phòng thi.</p>
        <div class="buttons">
          <button type="button" class="tiny-btn" data-action="exam-rooms">Mở Phòng thi</button>
        </div>
      </article>
    `);
  }

  if (!cards.length) {
    return `<p class="hint" style="margin:0">Chưa có chiến dịch dở dang hay nhắc rà soát nào. Thầy cô có thể tạo <b>Chiến dịch nhiều đề</b> (ví dụ bộ 10 đề ôn tập) hoặc đặt <b>Nhắc lịch</b> để Trợ lý Cá Voi theo dõi tiến độ giúp.</p>`;
  }
  return `<div class="home-proactive-grid">${cards.join('')}</div>`;
}

export function renderHomeViewHTML(state, digest = getCachedProactiveDigest()) {
  const exams = [...(state?.exams || [])]
    .sort((a, b) => Number(b.updated || 0) - Number(a.updated || 0))
    .slice(0, 6);

  const recentCards = exams.length
    ? exams
        .map((ex) => {
          const wf = WF_LABELS[ex.workflowStatus] || 'Dự thảo';
          return `
            <button type="button" class="home-recent-card" data-action="home-open-exam" data-id="${esc(ex.id)}">
              <div class="row space" style="width:100%">
                <span class="pill">${esc(ex.subject || 'Môn học')} · Lớp ${esc(ex.grade || '—')}</span>
                <span class="pill ${ex.workflowStatus === 'approved' || ex.workflowStatus === 'printed' ? 'ok' : ''}">${esc(wf)}</span>
              </div>
              <b>${esc(ex.title || 'Đề chưa đặt tên')}</b>
              <div class="home-recent-meta">${ex.questions?.length || 0} câu hỏi · ${ex.minutes || 45} phút · ${esc(formatDateShort(ex.updated))}</div>
            </button>
          `;
        })
        .join('')
    : '<p class="hint">Chưa có đề nào. Bấm “Bắt đầu soạn đề” để tạo đề đầu tiên.</p>';

  return `
    <section id="home-view" class="home-view" aria-label="Trang chủ Trợ lý Soạn đề Cá Voi Xanh">
      <div class="home-shell">
        <div class="home-hero">
          <div class="home-hero-left">
            <span class="home-whale-badge">${WHALE_BADGE_SVG}<span>Cá Voi Xanh Tri Thức · Trợ lý Soạn đề GDPT 2018</span></span>
            <h1>Mô tả đề bạn cần, Trợ lý Cá Voi soạn bản đầu tiên</h1>
            <p class="home-hero-lead">Soạn nhanh đề kiểm tra, bám sát SGK và ma trận 4 mức độ nhận thức, kiểm tra đáp án tự động và giao phòng thi trực tuyến ngay trên một không gian duy nhất.</p>
            <div class="home-cta-row">
              <button type="button" class="primary" data-action="design-workspace">Bắt đầu soạn đề</button>
              <button type="button" data-action="home-go-extract">Chuyển ảnh, PDF sang đề</button>
            </div>
            <div class="home-tools-strip" aria-label="Lối tắt công cụ">
              <button type="button" data-action="home-go-lessons">SGK Kết nối tri thức</button>
              <button type="button" data-action="exam-rooms">Phòng thi online</button>
              <button type="button" data-action="question-bank">Ngân hàng câu hỏi</button>
              <button type="button" data-action="open-new-campaign">Chiến dịch nhiều đề</button>
            </div>
          </div>

          <div class="home-prompt-card">
            <div class="home-a4-preview">
              <div class="home-a4-sheet" aria-hidden="true">
                <i class="h"></i>
                <i></i>
                <i class="s"></i>
                <i class="m"></i>
                <i></i>
                <i class="s"></i>
                <i class="m"></i>
              </div>
              <div class="home-a4-meta">
                <b>Tạo đề AI nhanh trên tờ A4 chuẩn</b>
                <small>Gõ yêu cầu hoặc bấm Micro nói tiếng Việt. Gõ “Bộ 10 đề…” để tự mở Chiến dịch theo dõi tiến độ.</small>
              </div>
            </div>

            <form id="home-prompt-form">
              <textarea id="home-prompt-input" rows="3" placeholder="Ví dụ: Soạn đề Toán 11 cuối kì 1 chuẩn GDPT 2018 gồm 12 câu trắc nghiệm, 4 đúng-sai, 2 tự luận…" aria-label="Mô tả đề thi cần tạo"></textarea>
              <div class="home-prompt-bar">
                <div class="home-prompt-left-actions">
                  <button type="button" class="tiny-btn" data-action="home-go-sources" title="Đính kèm tài liệu nguồn">Đính kèm nguồn</button>
                  <button type="button" class="tiny-btn" data-action="home-go-lessons" title="Chọn bài học SGK">Bài học SGK</button>
                </div>
                <div class="home-prompt-right-actions" id="home-prompt-voice-slot">
                  <button type="submit" id="home-prompt-submit" class="primary">Tạo đề ngay</button>
                </div>
              </div>
              <div class="home-prompt-chips" aria-label="Ví dụ nhanh">
                ${EXAMPLE_PROMPTS.map((p) => `<button type="button" class="home-prompt-chip" data-action="home-pick-chip" data-prompt="${esc(p)}">${esc(p)}</button>`).join('')}
              </div>
            </form>
          </div>
        </div>

        <section class="home-proactive-strip" aria-label="Trợ lý Chủ động">
          <div class="home-section-head">
            <div>
              <h2>${esc(digest.greeting || 'Chào thầy cô')} · Trợ lý Chủ động</h2>
              <p>Theo dõi chiến dịch nhiều đề, nhắc rà soát đề hôm qua và hạn nộp sắp tới.</p>
            </div>
            <div class="buttons">
              <button type="button" class="tiny-btn" data-action="open-new-campaign">+ Chiến dịch mới</button>
              <button type="button" class="tiny-btn" data-action="open-new-reminder">+ Nhắc lịch</button>
            </div>
          </div>
          <div id="home-proactive-body">${renderProactiveCardsHTML(digest, state)}</div>
        </section>

        <section aria-label="Đề gần đây">
          <div class="home-section-head">
            <div>
              <h2>Đề gần đây</h2>
              <p>Bấm vào đề để mở ngay trên Bàn soạn.</p>
            </div>
            <button type="button" class="tiny-btn" data-action="library">Xem toàn bộ kho đề</button>
          </div>
          <div class="home-recent-grid">${recentCards}</div>
        </section>
      </div>
    </section>
  `;
}

export function mountHomeView(ctx) {
  ensureHomeStyles();
  const slot = document.getElementById('home-prompt-voice-slot');
  const submitBtn = document.getElementById('home-prompt-submit');
  const input = document.getElementById('home-prompt-input');
  if (slot && input) {
    mountVoiceButton(slot, {
      targetInput: input,
      insertBefore: submitBtn,
      lang: 'vi-VN',
      onNotify: (msg) => ctx.toast?.(msg),
    });
  }
  void refreshProactiveUI(ctx);
}

export async function refreshProactiveUI(ctx) {
  const digest = await fetchProactiveDigest(ctx?.workspaceHeaders?.() || {});
  const body = document.getElementById('home-proactive-body');
  if (body) body.innerHTML = renderProactiveCardsHTML(digest, ctx?.getState?.());
  const bell = document.querySelector('[data-action="open-proactive-center"]');
  if (bell) {
    let badge = bell.querySelector('.proactive-bell-badge');
    if (digest.badgeCount > 0) {
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'proactive-bell-badge';
        bell.appendChild(badge);
      }
      badge.textContent = digest.badgeCount > 99 ? '99+' : String(digest.badgeCount);
      badge.hidden = false;
    } else if (badge) {
      badge.hidden = true;
    }
  }
  return digest;
}

export async function openProactiveCenterModal(ctx) {
  ensureHomeStyles();
  const digest = await refreshProactiveUI(ctx);
  ctx.modal(
    'Trợ lý Chủ động · Lịch & Tiến độ',
    `<div style="display:flex;flex-direction:column;gap:12px">
      <div class="row space">
        <p class="hint" style="margin:0">${esc(digest.greeting)} · ${digest.badgeCount} mục cần chú ý</p>
        <div class="buttons">
          <button type="button" class="tiny-btn" data-action="open-new-campaign">+ Chiến dịch mới</button>
          <button type="button" class="tiny-btn" data-action="open-new-reminder">+ Nhắc lịch</button>
        </div>
      </div>
      ${renderProactiveCardsHTML(digest, ctx?.getState?.())}
    </div>`,
    'Chiến dịch nhiều đề, nhắc rà soát đề hôm sau và hạn nộp sắp tới',
  );
}

function openNewCampaignModal(ctx) {
  const cur = ctx.exam?.() || {};
  ctx.modal(
    'Tạo chiến dịch soạn nhiều đề',
    `<form id="new-campaign-form" style="display:flex;flex-direction:column;gap:10px">
      <label>Tên chiến dịch<input name="title" required maxlength="200" placeholder="Ví dụ: Bộ 10 đề ôn tập Toán 9"></label>
      <div class="grid3">
        <label>Môn học<input name="subject" maxlength="80" value="${esc(cur.subject || 'Toán')}"></label>
        <label>Lớp<input name="grade" maxlength="40" value="${esc(cur.grade || '9')}"></label>
        <label>Số đề mục tiêu<input name="targetCount" type="number" min="1" max="200" value="10" required></label>
      </div>
      <label>Hạn hoàn thành (tùy chọn)<input name="dueAtLocal" type="datetime-local"></label>
      <label>Ghi chú (tùy chọn)<textarea name="note" rows="2" maxlength="1000" placeholder="Ví dụ: Bám sát cấu trúc đề Sở GD&ĐT"></textarea></label>
      <div class="modal-foot"><button type="button" data-action="close">Hủy</button><button type="submit" class="primary">Tạo chiến dịch</button></div>
    </form>`,
  );
}

export function openNewReminderModal(ctx) {
  const cur = ctx.exam?.() || {};
  const stateExams = Array.isArray(ctx?.getState?.()?.exams) ? ctx.getState().exams : [];
  const examsList = stateExams.length ? stateExams : cur?.id ? [cur] : [];
  const examOptions = examsList
    .filter((ex) => ex && ex.id)
    .map(
      (ex) =>
        `<option value="${esc(ex.id)}" ${ex.id === cur.id ? 'selected' : ''}>${esc(ex.title || 'Đề chưa đặt tên')}</option>`,
    )
    .join('');
  ctx.modal(
    'Tạo nhắc lịch giáo viên',
    `<form id="new-reminder-form" style="display:flex;flex-direction:column;gap:10px">
      <label>Nội dung nhắc<input name="title" required maxlength="240" placeholder="Ví dụ: Rà lại đáp án đề Toán 11 trước khi in"></label>
      <div class="grid2">
        <label>Loại nhắc<select name="kind"><option value="review">Rà soát đề</option><option value="deadline">Hạn nộp / in đề</option><option value="grading">Chấm bài</option><option value="general">Khác</option></select></label>
        <label>Thời điểm nhắc<input name="remindAtLocal" type="datetime-local"></label>
      </div>
      <label>Gắn với đề thi (tùy chọn)<select name="targetId"><option value="">— Không gắn đề cụ thể —</option>${examOptions}</select></label>
      <input type="hidden" name="targetType" value="exam">
      <div class="modal-foot"><button type="button" data-action="close">Hủy</button><button type="submit" class="primary">Lưu nhắc lịch</button></div>
    </form>`,
  );
}

async function patchReminderAction(rid, payload, successMessage, ctx) {
  if (!rid) return;
  let res;
  try {
    res = await fetch(`/api/reminders/${encodeURIComponent(rid)}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json', ...(ctx?.workspaceHeaders?.() || {})},
      body: JSON.stringify(payload),
    });
  } catch {
    ctx?.toast?.('Không thể kết nối máy chủ để cập nhật nhắc lịch. Thầy cô vui lòng thử lại.');
    return;
  }
  if (!res || !res.ok) {
    let detailMsg = '';
    try {
      const errData = await res.json();
      detailMsg = errData?.detail || errData?.error || '';
    } catch {}
    ctx?.toast?.(
      detailMsg
        ? `Không thể cập nhật nhắc lịch (${res.status}): ${detailMsg}`
        : `Không thể cập nhật nhắc lịch (lỗi ${res?.status || 'mạng'}). Vui lòng thử lại.`,
    );
    return;
  }
  await refreshProactiveUI(ctx);
  if (typeof document !== 'undefined' && document.getElementById('dialog')?.open) {
    await openProactiveCenterModal(ctx);
  }
  ctx?.toast?.(successMessage);
}

export async function handleHomeAction(action, node, ctx) {
  if (action === 'open-proactive-center') {
    await openProactiveCenterModal(ctx);
    return true;
  }
  if (action === 'open-new-campaign') {
    openNewCampaignModal(ctx);
    return true;
  }
  if (action === 'open-new-reminder') {
    openNewReminderModal(ctx);
    return true;
  }
  if (action === 'home-pick-chip') {
    const input = document.getElementById('home-prompt-input');
    if (input) {
      input.value = node.dataset.prompt || '';
      input.dispatchEvent(new Event('input', {bubbles: true}));
      input.focus();
    }
    return true;
  }
  if (action === 'home-open-exam') {
    const examId = node.dataset.id;
    if (examId && ctx.openExamInWorkspace) {
      const exams = ctx.getState?.()?.exams;
      if (Array.isArray(exams) && !exams.some((x) => x && x.id === examId)) {
        ctx.toast?.('Đề gắn kèm không còn trong kho đề hiện tại.');
        return true;
      }
      ctx.openExamInWorkspace(examId);
    }
    return true;
  }
  if (action === 'home-go-extract') {
    ctx.setViewMode?.('workspace');
    await ctx.act('extract');
    return true;
  }
  if (action === 'home-go-sources') {
    ctx.setViewMode?.('workspace');
    await ctx.act('assistant-sources');
    return true;
  }
  if (action === 'home-go-lessons') {
    ctx.setViewMode?.('workspace');
    await ctx.act('lesson-sources');
    return true;
  }
  if (action === 'home-continue-campaign') {
    const cid = node.dataset.id;
    const cTitle = node.dataset.title || 'Chiến dịch ôn tập';
    const subject = node.dataset.subject || 'Toán';
    const grade = node.dataset.grade || '10';
    const ordinal = Number(node.dataset.ordinal || 1);
    const examTitle = `${cTitle} · Đề số ${ordinal}`;
    const createdExam = ctx.createBlankExamForHome?.({subject, grade, title: examTitle});
    if (createdExam && cid) {
      try {
        await fetch(`/api/campaigns/${encodeURIComponent(cid)}/link-exam`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', ...(ctx.workspaceHeaders?.() || {})},
          body: JSON.stringify({examId: createdExam.id}),
        });
      } catch {}
    }
    const prompt = `Soạn đề số ${ordinal} cho chiến dịch "${cTitle}" môn ${subject} lớp ${grade}, bám sát chuẩn GDPT 2018.`;
    const detail = {prompt, examId: createdExam?.id || null, campaignId: cid || null, subject, grade, consentGiven: true};
    ctx.onAutoCreateExam?.(detail);
    void refreshProactiveUI(ctx);
    return true;
  }
  if (action === 'proactive-done-reminder') {
    await patchReminderAction(
      node.dataset.id,
      {done: true},
      'Đã đánh dấu hoàn thành nhắc lịch.',
      ctx,
    );
    return true;
  }
  if (action === 'proactive-snooze-reminder') {
    const hours = Number(node.dataset.hours || 4);
    await patchReminderAction(
      node.dataset.id,
      {snoozeHours: hours},
      `Đã hoãn nhắc lịch thêm ${hours} giờ.`,
      ctx,
    );
    return true;
  }
  return false;
}

export async function handleHomeSubmit(form, ctx) {
  if (form.id === 'home-prompt-form') {
    const input = form.querySelector('#home-prompt-input');
    const prompt = String(input?.value || '').trim();
    if (!prompt) {
      ctx.toast?.('Hãy nhập mô tả đề thi hoặc chọn một gợi ý nhanh.');
      input?.focus();
      return true;
    }
    const intent = parsePromptIntent(prompt);
    const createdExam = ctx.createBlankExamForHome?.({
      subject: intent.subject,
      grade: intent.grade,
      title: intent.campaignTarget > 0 ? `${intent.title} · Đề số 1` : intent.title,
    });
    let campaignId = null;
    if (intent.campaignTarget >= 2) {
      try {
        const res = await fetch('/api/campaigns', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', ...(ctx.workspaceHeaders?.() || {})},
          body: JSON.stringify({
            title: intent.title,
            subject: intent.subject,
            grade: intent.grade,
            targetCount: intent.campaignTarget,
            examIds: createdExam ? [createdExam.id] : [],
          }),
        });
        if (res.ok) {
          const data = await res.json();
          campaignId = data?.campaign?.id || null;
        }
      } catch {}
    }
    const detail = {prompt, examId: createdExam?.id || null, campaignId, subject: intent.subject, grade: intent.grade, consentGiven: true};
    ctx.onAutoCreateExam?.(detail);
    void refreshProactiveUI(ctx);
    return true;
  }

  if (form.id === 'new-campaign-form') {
    const fd = new FormData(form);
    const title = String(fd.get('title') || '').trim();
    if (!title) throw Error('Nhập tên chiến dịch.');
    const dueStr = String(fd.get('dueAtLocal') || '').trim();
    const dueAt = dueStr ? new Date(dueStr).getTime() : null;
    const res = await fetch('/api/campaigns', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', ...(ctx.workspaceHeaders?.() || {})},
      body: JSON.stringify({
        title,
        subject: String(fd.get('subject') || '').trim(),
        grade: String(fd.get('grade') || '').trim(),
        targetCount: Math.max(1, Number(fd.get('targetCount') || 5)),
        dueAt: Number.isFinite(dueAt) ? dueAt : null,
        note: String(fd.get('note') || '').trim(),
      }),
    });
    if (!res.ok) throw Error('Chưa tạo được chiến dịch mới.');
    document.getElementById('dialog')?.close();
    await refreshProactiveUI(ctx);
    ctx.toast?.('Đã tạo chiến dịch soạn đề mới.');
    return true;
  }

  if (form.id === 'new-reminder-form') {
    const fd = new FormData(form);
    const title = String(fd.get('title') || '').trim();
    if (!title) throw Error('Nhập nội dung nhắc lịch.');
    const remindStr = String(fd.get('remindAtLocal') || '').trim();
    const remindAt = remindStr ? new Date(remindStr).getTime() : Date.now() + 24 * 3600 * 1000;
    const targetId = String(fd.get('targetId') || '').trim();
    const targetType = targetId ? String(fd.get('targetType') || 'exam').trim() || 'exam' : '';
    const res = await fetch('/api/reminders', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', ...(ctx.workspaceHeaders?.() || {})},
      body: JSON.stringify({
        title,
        kind: String(fd.get('kind') || 'general'),
        targetType,
        targetId,
        remindAt: Number.isFinite(remindAt) ? remindAt : null,
      }),
    });
    if (!res.ok) throw Error('Chưa lưu được nhắc lịch.');
    document.getElementById('dialog')?.close();
    await refreshProactiveUI(ctx);
    ctx.toast?.('Đã lưu nhắc lịch giáo viên.');
    return true;
  }

  return false;
}
