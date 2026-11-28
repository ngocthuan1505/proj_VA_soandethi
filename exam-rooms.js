import { esc, QUESTION_TYPES } from './core.js';
import { richTextHTML } from './math-content.js';
import { workspaceHeaders as fallbackWorkspaceHeaders } from './storage.js';

const STYLE_ID = 'exam-rooms-styles';
const ROOM_STATUS_LABELS = {
  draft: 'Bản nháp',
  open: 'Đang mở',
  closed: 'Đã đóng',
  archived: 'Lưu trữ',
};
const ATTEMPT_STATUS_LABELS = {
  in_progress: 'Đang làm bài',
  submitted: 'Đã nộp',
  auto_submitted: 'Tự động thu bài',
  locked: 'Đã khóa',
};
const GRADING_STATUS_LABELS = {
  auto_graded: 'Tự động',
  needs_manual: 'Chờ chấm tự luận',
  graded: 'Đã chấm đủ',
};
const RESULT_POLICY_LABELS = {
  hidden: 'Ẩn điểm và đáp án',
  score_only: 'Chỉ hiện tổng điểm',
  score_and_answers: 'Hiện điểm và đáp án đúng',
  full_explanation: 'Hiện điểm, đáp án và lời giải',
};

let activeCtx = null;
let pollTimer = null;
let pollRequest = null;
let tabLoadEpoch = 0;
let detailLoadEpoch = 0;
let deleteInFlight = false;
let visibilityHandler = null;
let qrObjectUrl = '';
let state = {
  rooms: [],
  selectedRoomId: '',
  roomDetail: null,
  gradingQueue: null,
  analytics: null,
  preflight: null,
  activeTab: 'share',
  scopeFilter: 'exam',
  onlyPendingGrading: true,
  createPanelOpen: false,
  autoRefresh: true,
  loading: false,
  loadingTab: '',
  pendingDeleteRoomId: '',
  confirmDeleteRoomId: '',
  error: '',
  qrBaseOrigin: '',
};

function injectStyles() {
  if (typeof document === 'undefined' || document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    dialog:has(.er-shell) {
      width: min(1060px, 95vw);
      max-width: min(1060px, 100vw);
      padding: 0;
      box-sizing: border-box;
    }
    dialog:has(.er-shell) .modal-body {
      padding: 16px 20px 22px;
      background: var(--surface-subtle, #f6f9fd);
      overflow-x: hidden;
    }
    .er-shell {
      --er-teal: var(--brand, #0f4c81);
      --er-teal-dark: var(--brand-hover, #0b3a63);
      --er-teal-soft: var(--brand-soft, #e8f2fc);
      --er-accent: var(--accent, #1e78c8);
      --er-border: var(--line, #d5e2ef);
      --er-ink: var(--ink, #17283a);
      --er-muted: var(--ink-muted, #4b6178);
      --er-warn: #92400e;
      --er-warn-bg: #fef3c7;
      --er-danger: #991b1b;
      --er-danger-bg: #fee2e2;
      --er-ok: #065f46;
      --er-ok-bg: #d1fae5;
      color: var(--er-ink);
      display: flex;
      flex-direction: column;
      gap: 14px;
      font-size: 14px;
      min-width: 0;
      max-width: 100%;
      box-sizing: border-box;
    }
    .er-card {
      background: #ffffff;
      border: 1px solid var(--er-border);
      border-radius: 10px;
      padding: 14px 16px;
      min-width: 0;
      max-width: 100%;
      box-sizing: border-box;
    }
    .er-topbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: linear-gradient(135deg, var(--er-teal-soft) 0%, #ffffff 72%);
      border: 1px solid var(--er-border);
      border-radius: 10px;
      padding: 14px 16px;
      min-width: 0;
      box-sizing: border-box;
    }
    .er-exam-title {
      font-weight: 700;
      font-size: 15px;
      color: var(--er-teal-dark);
      margin-bottom: 3px;
    }
    .er-exam-meta {
      font-size: 12.5px;
      color: var(--er-muted);
    }
    .er-btn-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }
    .er-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 8px;
      border: 1px solid var(--er-border);
      background: #ffffff;
      color: var(--er-ink);
      font-weight: 600;
      font-size: 13px;
      line-height: 1.25;
      cursor: pointer;
      box-sizing: border-box;
      text-decoration: none;
      transition: background 0.15s ease, border-color 0.15s ease;
    }
    .er-shell .er-btn:hover:not(:disabled) {
      background: var(--er-teal-soft);
      border-color: var(--er-accent);
      color: var(--er-ink);
    }
    .er-btn:disabled { opacity: 0.55; cursor: not-allowed; }
    .er-shell .er-btn-primary {
      background: var(--er-teal, #0f4c81);
      border-color: var(--er-teal, #0f4c81);
      color: #ffffff;
    }
    .er-shell .er-btn-primary:hover:not(:disabled) {
      background: var(--er-teal-dark, #0b3a63);
      border-color: var(--er-teal-dark, #0b3a63);
      color: #ffffff;
    }
    .er-shell .er-btn-soft {
      background: var(--er-teal-soft);
      border-color: #bfd7ef;
      color: var(--er-teal-dark);
    }
    .er-shell .er-btn-soft:hover:not(:disabled) {
      background: #dbeafa;
      border-color: #9ec4e6;
      color: var(--er-teal-dark);
    }
    .er-shell .er-btn-danger {
      background: #fff5f5;
      border-color: #f3c2c2;
      color: var(--er-danger);
    }
    .er-shell .er-btn-danger:hover:not(:disabled) {
      background: var(--er-danger-bg);
      border-color: #f3c2c2;
      color: var(--er-danger);
    }
    .er-btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 6px; }
    .er-grid-2 {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .er-grid-3 {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .er-field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;
    }
    .er-field label {
      font-size: 12.5px;
      font-weight: 600;
      color: var(--er-muted);
    }
    .er-field input, .er-field select, .er-field textarea {
      width: 100%;
      box-sizing: border-box;
      padding: 7px 10px;
      border: 1px solid #c4d7ea;
      border-radius: 7px;
      font-size: 13.5px;
      font-family: inherit;
      background: #ffffff;
      color: var(--er-ink);
    }
    .er-field input:focus, .er-field select:focus, .er-field textarea:focus {
      outline: 2px solid rgba(15, 76, 129, 0.22);
      border-color: var(--er-teal);
    }
    .er-checks {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      margin-top: 4px;
    }
    .er-check {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 13px;
      cursor: pointer;
    }
    .er-hint-box {
      background: var(--er-teal-soft);
      border-left: 3px solid var(--er-teal);
      border-radius: 6px;
      padding: 9px 12px;
      font-size: 12.5px;
      color: var(--er-teal-dark);
      line-height: 1.45;
    }
    .er-preflight-banner {
      background: #fff7ed;
      border: 1px solid #fdba74;
      border-left: 4px solid #c2410c;
      border-radius: 10px;
      padding: 12px 14px;
      color: #9a3412;
      font-size: 13px;
      line-height: 1.45;
    }
    .er-preflight-banner ul {
      margin: 6px 0 0 18px;
      padding: 0;
    }
    .er-room-strip {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .er-room-strip-head {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }
    .er-room-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .er-room-pill {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 3px;
      min-width: 190px;
      max-width: 260px;
      padding: 9px 12px;
      border: 1px solid var(--er-border);
      border-radius: 9px;
      background: #ffffff;
      cursor: pointer;
      text-align: left;
    }
    .er-room-pill:hover { border-color: var(--er-teal); }
    .er-room-pill.is-active {
      background: var(--er-teal-soft);
      border-color: var(--er-teal);
      box-shadow: inset 0 0 0 1px var(--er-teal);
    }
    .er-pill-top {
      display: flex;
      width: 100%;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }
    .er-code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: var(--er-teal-dark);
    }
    .er-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11.5px;
      font-weight: 600;
      white-space: nowrap;
    }
    .er-badge-open { background: var(--er-ok-bg); color: var(--er-ok); }
    .er-badge-closed { background: #e5e7eb; color: #374151; }
    .er-badge-draft { background: var(--er-warn-bg); color: var(--er-warn); }
    .er-badge-archived { background: #f3f4f6; color: #4b5563; }
    .er-badge-warn { background: var(--er-warn-bg); color: var(--er-warn); }
    .er-badge-danger { background: var(--er-danger-bg); color: var(--er-danger); }
    .er-badge-teal { background: var(--er-teal-soft); color: var(--er-teal-dark); }
    .er-check input[type="checkbox"],
    .er-rubric-step-chk {
      width: 18px;
      height: 18px;
      flex-shrink: 0;
      accent-color: var(--er-teal, #0f4c81);
    }
    .er-tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      border-bottom: 1px solid var(--er-border);
      padding-bottom: 10px;
    }
    .er-shell .er-tab {
      padding: 7px 14px;
      border-radius: 8px;
      border: 1px solid transparent;
      background: transparent;
      font-weight: 600;
      font-size: 13px;
      color: var(--er-muted);
      cursor: pointer;
    }
    .er-shell .er-tab:hover:not(:disabled) {
      background: var(--er-teal-soft);
      border-color: transparent;
      color: var(--er-ink);
    }
    .er-shell .er-tab.is-active,
    .er-shell .er-tab.is-active:hover:not(:disabled) {
      background: var(--er-teal, #0f4c81);
      border-color: var(--er-teal, #0f4c81);
      color: #ffffff;
    }
    .er-shell .er-tab:focus-visible,
    .er-shell .er-btn:focus-visible,
    .er-shell .er-room-pill:focus-visible {
      outline: 2px solid var(--er-accent, #1e78c8);
      outline-offset: 2px;
    }
    .er-tabpanel {
      min-width: 0;
    }
    .er-confirm-inline {
      border-color: #f3c2c2;
      background: #fff5f5;
      color: var(--er-ink);
    }
    .er-confirm-delete p {
      margin: 0 0 8px;
      line-height: 1.5;
    }
    .er-share-layout {
      display: grid;
      grid-template-columns: 230px minmax(0, 1fr);
      gap: 16px;
      align-items: start;
      min-width: 0;
    }
    .er-qr-card {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 12px;
      background: #ffffff;
      border: 1px solid var(--er-border);
      border-radius: 10px;
      min-width: 0;
      box-sizing: border-box;
    }
    .er-qr-box {
      width: 184px;
      height: 184px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #ffffff;
      border: 1px solid #e5eef7;
      border-radius: 8px;
      padding: 6px;
    }
    .er-qr-box img { width: 100%; height: 100%; object-fit: contain; }
    .er-big-code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 26px;
      font-weight: 800;
      letter-spacing: 0.16em;
      color: var(--er-teal-dark);
      background: var(--er-teal-soft);
      padding: 6px 14px;
      border-radius: 8px;
      border: 1px dashed #8fb8e2;
    }
    .er-link-box {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      background: #f4f8fc;
      border: 1px solid var(--er-border);
      border-radius: 8px;
      padding: 7px 10px;
      min-width: 0;
      max-width: 100%;
      box-sizing: border-box;
    }
    .er-link-box code {
      flex: 1 1 180px;
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
      white-space: normal;
      font-size: 12.5px;
      color: var(--er-ink);
    }
    .er-table-wrap {
      overflow-x: auto;
      border: 1px solid var(--er-border);
      border-radius: 9px;
      background: #ffffff;
    }
    .er-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    .er-table th {
      background: #eef5fc;
      color: var(--er-teal-dark);
      font-weight: 700;
      text-align: left;
      padding: 9px 10px;
      border-bottom: 1px solid var(--er-border);
      white-space: nowrap;
    }
    .er-table td {
      padding: 9px 10px;
      border-bottom: 1px solid #e5eef7;
      vertical-align: middle;
    }
    .er-table tr:last-child td { border-bottom: none; }
    .er-grade-item {
      border: 1px solid var(--er-border);
      border-radius: 10px;
      background: #ffffff;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .er-grade-head {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      border-bottom: 1px solid #e5eef7;
      padding-bottom: 8px;
    }
    .er-grade-split {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
      gap: 14px;
    }
    .er-student-answer {
      background: #f8fbfe;
      border: 1px solid #d4e2f0;
      border-radius: 8px;
      padding: 10px 12px;
      white-space: pre-wrap;
      line-height: 1.55;
      min-height: 76px;
    }
    .er-rubric-box {
      background: #f4f9fe;
      border: 1px solid #c9ddf1;
      border-radius: 8px;
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .er-rubric-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
      font-size: 12.8px;
      padding: 5px 7px;
      background: #ffffff;
      border: 1px solid #ddeaf6;
      border-radius: 6px;
      cursor: pointer;
    }
    .er-kpis {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
      gap: 10px;
    }
    .er-kpi {
      background: #ffffff;
      border: 1px solid var(--er-border);
      border-radius: 9px;
      padding: 10px 12px;
    }
    .er-kpi-label { font-size: 12px; color: var(--er-muted); }
    .er-kpi-value { font-size: 20px; font-weight: 800; color: var(--er-teal-dark); margin-top: 2px; }
    .er-hist {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 8px;
      align-items: end;
      height: 165px;
      padding: 14px 10px 6px;
      background: #ffffff;
      border: 1px solid var(--er-border);
      border-radius: 9px;
    }
    .er-hist-col {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-end;
      height: 100%;
      gap: 4px;
    }
    .er-hist-bar {
      width: 100%;
      max-width: 44px;
      background: linear-gradient(180deg, var(--er-accent) 0%, var(--er-teal) 100%);
      border-radius: 6px 6px 2px 2px;
      min-height: 4px;
      transition: height 0.2s ease;
    }
    .er-hist-cnt { font-size: 11.5px; font-weight: 700; color: var(--er-teal-dark); }
    .er-hist-lbl { font-size: 11px; color: var(--er-muted); text-align: center; }
    .er-empty {
      padding: 24px;
      text-align: center;
      color: var(--er-muted);
      background: #ffffff;
      border: 1px dashed var(--er-border);
      border-radius: 10px;
    }
    .er-error {
      padding: 10px 12px;
      background: var(--er-danger-bg);
      color: var(--er-danger);
      border: 1px solid #fecaca;
      border-radius: 8px;
      font-size: 13px;
    }
    @media (max-width: 780px) {
      dialog:has(.er-shell) {
        width: calc(100vw - 16px);
        max-width: 100vw;
      }
      dialog:has(.er-shell) .modal-body {
        padding: 12px;
      }
      .er-grid-2, .er-grid-3, .er-share-layout, .er-grade-split {
        grid-template-columns: minmax(0, 1fr);
      }
      .er-room-pill {
        min-width: 0;
        max-width: none;
        width: 100%;
      }
      .er-btn, a.er-btn, .er-btn-sm, a.er-btn-sm, .er-shell .er-tab {
        min-height: 44px;
        display: inline-flex;
        align-items: center;
      }
      .er-check {
        min-height: 44px;
      }
      .er-check input[type="checkbox"],
      .er-rubric-step-chk {
        width: 20px;
        height: 20px;
      }
      .er-hist { gap: 4px; }
    }
  `;
  document.head.appendChild(style);
}

export function isRoomLaunchBlocked(preflight) {
  return Boolean(preflight && preflight.ready === false);
}

export function roomPreflightBannerHTML(preflight) {
  if (!isRoomLaunchBlocked(preflight)) return '';
  const blocking = Array.isArray(preflight?.blockingIssues) ? preflight.blockingIssues : [];
  const listHTML = blocking.length
    ? `<ul>${blocking.slice(0, 8).map((item) => `<li>${esc(item?.message || String(item || ''))}</li>`).join('')}</ul>`
    : '<ul><li>Đề hiện tại còn lỗi chặn cần rà soát trước khi phát hành cho học sinh.</li></ul>';
  return `<div class="er-preflight-banner" role="alert"><strong>Đề thi chưa đủ điều kiện mở phòng công khai (${blocking.length || 1} lỗi chặn):</strong>${listHTML}<div style="margin-top:6px;font-size:12px;">Vui lòng hoàn thiện khóa đáp án hoặc sửa lỗi chặn trên đề trước khi bấm mở phòng.</div></div>`;
}

export function formatPointsVi(p100) {
  if (p100 === null || p100 === undefined || !Number.isFinite(Number(p100))) return '—';
  const num = Number(p100) / 100;
  const fixed = num.toFixed(2).replace(/\.?0+$/, '');
  return fixed.replace('.', ',');
}

function formatDateTimeVi(ms) {
  if (!ms) return 'Không giới hạn';
  try {
    return new Date(Number(ms)).toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

function toDateTimeLocalInput(ms) {
  if (!ms) return '';
  const d = new Date(Number(ms));
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDateTimeLocalInput(val) {
  const clean = String(val || '').trim();
  if (!clean) return null;
  const ms = Date.parse(clean);
  return Number.isFinite(ms) ? ms : null;
}

async function getHeaders(c) {
  if (typeof c?.workspaceHeaders === 'function') {
    return c.workspaceHeaders();
  }
  return fallbackWorkspaceHeaders();
}

async function roomApi(c, path, { method = 'GET', body, signal } = {}) {
  const headers = { ...(await getHeaders(c)) };
  signal?.throwIfAborted();
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {
    method,
    headers,
    signal,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const msg =
      data?.detail?.message ||
      (typeof data?.detail === 'string' ? data.detail : '') ||
      data?.error ||
      `Không thể xử lý yêu cầu (${response.status}).`;
    const err = new Error(msg);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

async function fetchAuthBlob(c, path) {
  const headers = { ...(await getHeaders(c)) };
  const response = await fetch(path, { method: 'GET', headers });
  if (!response.ok) {
    throw new Error(`Không tải được tệp (${response.status}).`);
  }
  return response.blob();
}

function stopPolling() {
  pollRequest?.abort();
  pollRequest = null;
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function revokeQrUrl() {
  if (qrObjectUrl) {
    try {
      URL.revokeObjectURL(qrObjectUrl);
    } catch {
      // Ignore cleanup errors
    }
    qrObjectUrl = '';
  }
}

function notify(c, msg) {
  if (typeof c?.toast === 'function') {
    c.toast(msg);
  }
}

async function copyText(c, text, label = 'liên kết') {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      notify(c, `Đã sao chép ${label}.`);
      return;
    }
  } catch {
    // Fallback below
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    notify(c, `Đã sao chép ${label}.`);
  } catch {
    notify(c, 'Không thể sao chép tự động; thầy cô vui lòng bôi đen để sao chép.');
  } finally {
    ta.remove();
  }
}

function renderRichField(text, richDoc) {
  if (typeof richTextHTML === 'function') {
    return richTextHTML(text || '', richDoc);
  }
  return esc(text || '').replace(/\n/g, '<br>');
}

function roomStatusBadge(status) {
  const cls =
    status === 'open'
      ? 'er-badge-open'
      : status === 'draft'
        ? 'er-badge-draft'
        : status === 'archived'
          ? 'er-badge-archived'
          : 'er-badge-closed';
  return `<span class="er-badge ${cls}">${esc(ROOM_STATUS_LABELS[status] || status)}</span>`;
}

function attemptStatusBadge(status) {
  const cls =
    status === 'in_progress'
      ? 'er-badge-teal'
      : status === 'locked'
        ? 'er-badge-danger'
        : status === 'auto_submitted'
          ? 'er-badge-warn'
          : 'er-badge-open';
  return `<span class="er-badge ${cls}">${esc(ATTEMPT_STATUS_LABELS[status] || status)}</span>`;
}

function selectedRoom() {
  return state.rooms.find((r) => r.id === state.selectedRoomId) || null;
}

function resolveExamMinutes(cur, fallback = 45) {
  const raw = cur?.minutes;
  if (raw === undefined || raw === null || raw === '') return fallback;
  const num = Number(raw);
  return Number.isFinite(num) && num >= 0 ? num : fallback;
}

function buildCreateFormHTML(cur) {
  const defaultTitle = cur?.title ? `${cur.title}` : 'Phòng thi trực tuyến';
  const defaultMin = resolveExamMinutes(cur, 45);
  return `
    <form id="er-create-form" class="er-card" style="display:flex;flex-direction:column;gap:12px;">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <strong>Thiết lập phòng mới cho đề hiện tại</strong>
        <button type="button" class="er-btn er-btn-sm" data-er-action="toggle-create">Thu gọn</button>
      </div>
      <div class="er-grid-3">
        <div class="er-field">
          <label for="er-c-title">Tên phòng thi / bài tập</label>
          <input id="er-c-title" name="title" value="${esc(defaultTitle)}" maxlength="240" required>
        </div>
        <div class="er-field">
          <label for="er-c-class">Lớp / Nhóm học sinh</label>
          <input id="er-c-class" name="classLabel" placeholder="Ví dụ: 9A1, Tổ tự nhiên" maxlength="120">
        </div>
        <div class="er-field">
          <label for="er-c-mode">Hình thức tổ chức</label>
          <select id="er-c-mode" name="mode">
            <option value="exam">Kiểm tra trực tuyến</option>
            <option value="homework">Bài tập về nhà</option>
          </select>
        </div>
      </div>
      <div class="er-grid-3">
        <div class="er-field">
          <label for="er-c-duration">Thời lượng làm bài (phút, 0 = không giới hạn phiên)</label>
          <input id="er-c-duration" name="durationMinutes" type="number" min="0" max="600" value="${esc(defaultMin)}">
        </div>
        <div class="er-field">
          <label for="er-c-deadline">Hạn chót mở phòng (tùy chọn)</label>
          <input id="er-c-deadline" name="deadlineAt" type="datetime-local">
        </div>
        <div class="er-field">
          <label for="er-c-attempts">Số lượt làm tối đa / học sinh</label>
          <input id="er-c-attempts" name="maxAttempts" type="number" min="1" max="50" value="1">
        </div>
      </div>
      <div class="er-grid-3">
        <div class="er-field">
          <label for="er-c-pin">Mã PIN vào phòng (bỏ trống nếu vào tự do)</label>
          <input id="er-c-pin" name="pin" placeholder="Ví dụ: 2025" maxlength="32" autocomplete="off">
        </div>
        <div class="er-field">
          <label for="er-c-policy">Hiển thị kết quả cho học sinh</label>
          <select id="er-c-policy" name="resultPolicy">
            <option value="score_only">Chỉ hiện tổng điểm</option>
            <option value="score_and_answers">Hiện điểm và đáp án đúng</option>
            <option value="full_explanation">Hiện điểm, đáp án và lời giải</option>
            <option value="hidden">Ẩn hoàn toàn sau khi nộp</option>
          </select>
        </div>
        <div class="er-field">
          <label for="er-c-tabs">Giới hạn chuyển tab (0 = chỉ ghi nhận)</label>
          <input id="er-c-tabs" name="maxTabSwitches" type="number" min="0" max="100" value="3">
        </div>
      </div>
      <div class="er-checks">
        <label class="er-check"><input type="checkbox" name="shuffleQuestions" checked> Trộn thứ tự câu hỏi</label>
        <label class="er-check"><input type="checkbox" name="shuffleOptions" checked> Trộn đáp án A/B/C/D</label>
        <label class="er-check"><input type="checkbox" name="releaseResultsAfterClose"> Chỉ công bố kết quả sau khi đóng phòng</label>
        <label class="er-check"><input type="checkbox" name="requireFullscreen"> Yêu cầu toàn màn hình</label>
        <label class="er-check"><input type="checkbox" name="allowLan"> Mở qua mạng nội bộ (LAN) tại phòng máy / Wi-Fi lớp</label>
      </div>
      <div class="er-hint-box">
        <strong>Lưu ý chế độ mạng nội bộ (LAN):</strong> Khi bật <em>Mở qua mạng nội bộ (LAN)</em>, hệ thống sẽ gợi ý địa chỉ IP nội bộ và mã QR tương ứng để học sinh trong cùng Wi-Fi lớp truy cập ngay trên điện thoại hoặc máy tính phòng tin mà không cần Internet ngoài. Máy chủ cần được khởi chạy với quyền lắng nghe trong mạng lớp.
      </div>
      <div class="er-btn-row" style="justify-content:flex-end;">
        <button type="submit" class="er-btn er-btn-primary" ${isRoomLaunchBlocked(state.preflight) ? 'disabled' : ''}>Tạo &amp; mở phòng ngay</button>
      </div>
    </form>
  `;
}

function buildShareTabHTML(room) {
  const origin = state.qrBaseOrigin || (typeof location !== 'undefined' ? location.origin : '');
  const primaryJoinUrl = (origin || '') + room.joinPath;
  const lanUrls = Array.isArray(room.lanUrls) ? room.lanUrls : [];
  const nextStatus = room.status === 'open' ? 'closed' : 'open';
  const nextStatusLabel = room.status === 'open' ? 'Đóng phòng ngay' : 'Mở lại phòng';

  return `
    <div class="er-share-layout">
      <div class="er-qr-card">
        <span style="font-size:12px;font-weight:700;color:var(--er-muted);">MÃ VÀO PHÒNG</span>
        <div class="er-big-code">${esc(room.roomCode)}</div>
        <div class="er-qr-box" id="er-qr-box">
          ${qrObjectUrl ? `<img src="${esc(qrObjectUrl)}" alt="Mã QR phòng ${esc(room.roomCode)}">` : '<span style="font-size:12px;color:var(--er-muted);">Đang tạo mã QR…</span>'}
        </div>
        <div class="er-btn-row" style="justify-content:center;">
          <button type="button" class="er-btn er-btn-soft er-btn-sm" data-er-action="download-qr">Tải mã QR (.svg)</button>
        </div>
        ${
          lanUrls.length
            ? `<div style="width:100%;display:flex;flex-direction:column;gap:4px;">
                 <span style="font-size:11.5px;color:var(--er-muted);text-align:center;">Đích mã QR hiện tại:</span>
                 <button type="button" class="er-btn er-btn-sm" data-er-action="use-qr-origin" data-origin="${esc(typeof location !== 'undefined' ? location.origin : '')}">Địa chỉ hiện tại</button>
                 ${lanUrls
                   .map((u) => {
                     let uOrigin = '';
                     try {
                       uOrigin = new URL(u).origin;
                     } catch {
                       uOrigin = '';
                     }
                     return uOrigin
                       ? `<button type="button" class="er-btn er-btn-sm" data-er-action="use-qr-origin" data-origin="${esc(uOrigin)}">QR LAN: ${esc(uOrigin.replace(/^https?:\/\//, ''))}</button>`
                       : '';
                   })
                   .join('')}
               </div>`
            : ''
        }
      </div>

      <div style="min-width:0;display:flex;flex-direction:column;gap:12px;">
        <div class="er-card" style="display:flex;flex-direction:column;gap:10px;">
          <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;">
            <div>
              <div style="font-weight:700;font-size:15px;">${esc(room.title)}</div>
              <div style="font-size:12.5px;color:var(--er-muted);">
                ${room.mode === 'homework' ? 'Bài tập về nhà' : 'Kiểm tra trực tuyến'}
                ${room.classLabel ? ` · Lớp ${esc(room.classLabel)}` : ''}
                · ${esc(room.questionCount)} câu · Thang ${esc(formatPointsVi(room.totalPointsP100))} điểm
                ${room.requiresPin ? ' · Có mã PIN' : ' · Không cần PIN'}
              </div>
            </div>
            <div class="er-btn-row">
              ${roomStatusBadge(room.status)}
              <button type="button" class="er-btn er-btn-sm ${room.status === 'open' ? 'er-btn-danger' : 'er-btn-primary'}" data-er-action="toggle-room-status" data-next-status="${esc(nextStatus)}">${esc(nextStatusLabel)}</button>
            </div>
          </div>

          <div class="er-field">
            <label>Đường dẫn cho học sinh</label>
            <div class="er-link-box">
              <code>${esc(primaryJoinUrl)}</code>
              <button type="button" class="er-btn er-btn-soft er-btn-sm" data-er-action="copy-text" data-copy="${esc(primaryJoinUrl)}" data-label="đường dẫn phòng thi">Sao chép link</button>
              <button type="button" class="er-btn er-btn-sm" data-er-action="copy-text" data-copy="${esc(room.roomCode)}" data-label="mã phòng">Chép mã</button>
              <a class="er-btn er-btn-sm" href="${esc(room.joinPath)}" target="_blank" rel="noopener" style="text-decoration:none;">Mở thử</a>
            </div>
          </div>

          ${
            room.allowLan
              ? `<div class="er-hint-box">
                   <strong>Chế độ mạng nội bộ (LAN) đang bật:</strong>
                   ${
                     lanUrls.length
                       ? `<div style="margin-top:6px;display:flex;flex-direction:column;gap:6px;">
                            ${lanUrls
                              .map(
                                (u) => `<div class="er-link-box"><code>${esc(u)}</code><button type="button" class="er-btn er-btn-sm" data-er-action="copy-text" data-copy="${esc(u)}" data-label="địa chỉ LAN">Sao chép LAN</button></div>`,
                              )
                              .join('')}
                          </div>`
                       : `<div style="margin-top:4px;">Chưa phát hiện địa chỉ IP mạng nội bộ khả dụng từ máy hiện tại. Nếu dạy qua phòng máy/Wi-Fi lớp, hãy chạy máy chủ mở cho mạng LAN và gửi link dạng <code>http://&lt;IP-máy-giáo-viên&gt;:&lt;cổng&gt;${esc(room.joinPath)}</code>.</div>`
                   }
                 </div>`
              : ''
          }
        </div>

        <form id="er-update-form" class="er-card" style="display:flex;flex-direction:column;gap:10px;">
          <strong>Cập nhật cấu hình phòng</strong>
          <div class="er-grid-3">
            <div class="er-field">
              <label for="er-u-title">Tên phòng</label>
              <input id="er-u-title" name="title" value="${esc(room.title)}" maxlength="240" required>
            </div>
            <div class="er-field">
              <label for="er-u-class">Lớp / Nhóm</label>
              <input id="er-u-class" name="classLabel" value="${esc(room.classLabel || '')}" maxlength="120">
            </div>
            <div class="er-field">
              <label for="er-u-status">Trạng thái phòng</label>
              <select id="er-u-status" name="status">
                <option value="open" ${room.status === 'open' ? 'selected' : ''}>Đang mở</option>
                <option value="closed" ${room.status === 'closed' ? 'selected' : ''}>Đã đóng</option>
                <option value="draft" ${room.status === 'draft' ? 'selected' : ''}>Bản nháp</option>
                <option value="archived" ${room.status === 'archived' ? 'selected' : ''}>Lưu trữ</option>
              </select>
            </div>
          </div>
          <div class="er-grid-3">
            <div class="er-field">
              <label for="er-u-duration">Thời lượng (phút)</label>
              <input id="er-u-duration" name="durationMinutes" type="number" min="0" max="600" value="${esc(room.durationMinutes ?? 0)}">
            </div>
            <div class="er-field">
              <label for="er-u-deadline">Hạn đóng phòng</label>
              <input id="er-u-deadline" name="deadlineAt" type="datetime-local" value="${esc(toDateTimeLocalInput(room.deadlineAt))}">
            </div>
            <div class="er-field">
              <label for="er-u-tabs">Giới hạn chuyển tab</label>
              <input id="er-u-tabs" name="maxTabSwitches" type="number" min="0" max="100" value="${esc(room.maxTabSwitches ?? 0)}">
            </div>
          </div>
          <div class="er-grid-2">
            <div class="er-field">
              <label for="er-u-policy">Hiển thị kết quả</label>
              <select id="er-u-policy" name="resultPolicy">
                ${Object.entries(RESULT_POLICY_LABELS)
                  .map(
                    ([k, lbl]) =>
                      `<option value="${esc(k)}" ${room.resultPolicy === k ? 'selected' : ''}>${esc(lbl)}</option>`,
                  )
                  .join('')}
              </select>
            </div>
            <div class="er-field">
              <label for="er-u-pin">Đặt lại mã PIN (bỏ trống để giữ nguyên)</label>
              <input id="er-u-pin" name="pin" placeholder="Nhập PIN mới hoặc để trống" maxlength="32" autocomplete="off">
            </div>
          </div>
          <div class="er-checks">
            <label class="er-check"><input type="checkbox" name="releaseResultsAfterClose" ${room.releaseResultsAfterClose ? 'checked' : ''}> Chỉ công bố kết quả sau khi đóng phòng</label>
            <label class="er-check"><input type="checkbox" name="requireFullscreen" ${room.requireFullscreen ? 'checked' : ''}> Yêu cầu toàn màn hình</label>
            <label class="er-check"><input type="checkbox" name="allowLan" ${room.allowLan ? 'checked' : ''}> Mở qua mạng nội bộ (LAN)</label>
          </div>
          <div class="er-btn-row" style="justify-content:space-between;">
            <button type="button" class="er-btn er-btn-danger er-btn-sm" data-er-action="delete-room">Xóa phòng này</button>
            <button type="submit" class="er-btn er-btn-primary">Lưu thay đổi phòng</button>
          </div>
        </form>
        ${
          state.confirmDeleteRoomId === room.id
            ? `<div class="er-card er-confirm-inline" role="alertdialog" aria-modal="false" aria-labelledby="er-inline-del-title" aria-describedby="er-inline-del-desc" style="display:flex;flex-direction:column;gap:8px;">
                 <strong id="er-inline-del-title">Xóa phòng ${esc(room.roomCode)}?</strong>
                 <p id="er-inline-del-desc" style="margin:0;line-height:1.5;">Xóa phòng <strong>${esc(room.roomCode)}</strong> (${esc(room.title)}) và toàn bộ bài làm trong phòng này? Hành động này không thể hoàn tác.</p>
                 <div class="er-btn-row" style="justify-content:flex-end;">
                   <button type="button" id="er-cancel-inline-delete-btn" class="er-btn er-btn-sm" data-er-action="cancel-delete-room">Hủy</button>
                   <button type="button" id="er-confirm-inline-delete-btn" class="er-btn er-btn-danger er-btn-sm" data-er-action="confirm-delete-room" data-room-id="${esc(room.id)}">Xóa phòng</button>
                 </div>
               </div>`
            : ''
        }
      </div>
    </div>
  `;
}

function buildMonitorSummaryBadgesHTML(room) {
  const attempts = state.roomDetail?.attempts || [];
  const inProg = attempts.filter((a) => a.status === 'in_progress').length;
  const submitted = attempts.filter((a) => a.status !== 'in_progress').length;
  const warned = attempts.filter((a) => (a.tabSwitchCount || 0) > 0 || (a.fullscreenExitCount || 0) > 0).length;
  return `
    <span class="er-badge er-badge-teal">Tổng lượt: ${attempts.length}</span>
    <span class="er-badge er-badge-open">Đã nộp/Khóa: ${submitted}</span>
    <span class="er-badge er-badge-draft">Đang làm: ${inProg}</span>
    ${warned ? `<span class="er-badge er-badge-warn">Cảnh báo rời màn hình: ${warned}</span>` : ''}
  `;
}

function buildMonitorResultsHTML(room) {
  if (state.loadingTab === 'monitor' && !state.roomDetail) {
    return `<div class="er-empty">Đang tải dữ liệu giám sát…</div>`;
  }
  const attempts = state.roomDetail?.attempts || [];
  if (!attempts.length) {
    return `<div class="er-empty">Chưa có học sinh nào tham gia phòng <strong>${esc(room.roomCode)}</strong>. Hãy chia sẻ mã hoặc mã QR ở tab Chia sẻ.</div>`;
  }
  return `
    <div class="er-table-wrap">
      <table class="er-table">
        <thead>
          <tr>
            <th>Học sinh</th>
            <th>Lớp / SBD</th>
            <th>Mã đề</th>
            <th>Trạng thái</th>
            <th>Chuyển tab / Toàn màn hình</th>
            <th>Điểm số</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          ${attempts
            .map((a) => {
              const tabCnt = Number(a.tabSwitchCount || 0);
              const fsCnt = Number(a.fullscreenExitCount || 0);
              const limit = Number(room.maxTabSwitches || 0);
              const tabCls =
                limit > 0 && tabCnt > limit
                  ? 'er-badge-danger'
                  : tabCnt > 0
                    ? 'er-badge-warn'
                    : 'er-badge-open';
              const scoreTxt =
                a.status === 'in_progress'
                  ? 'Đang làm'
                  : `${formatPointsVi(a.totalScoreP100)} / ${formatPointsVi(a.totalPointsP100)}`;
              const adjP100 = Number(a.scoreAdjustmentP100 || 0);
              const adjTxt =
                adjP100 !== 0
                  ? `Điều chỉnh: ${adjP100 > 0 ? '+' : ''}${formatPointsVi(adjP100)} đ${a.adjustmentNote ? ` (${a.adjustmentNote})` : ''}`
                  : '';
              return `
                <tr>
                  <td>
                    <strong>${esc(a.studentName)}</strong>
                    <div style="font-size:11.5px;color:var(--er-muted);">Lượt ${esc(a.attemptNo)} · Bắt đầu ${esc(formatDateTimeVi(a.startedAt))}</div>
                  </td>
                  <td>${esc(a.studentClass || '—')}${a.studentCode ? ` · ${esc(a.studentCode)}` : ''}</td>
                  <td><span class="er-code">${esc(a.variantCode || 'Gốc')}</span></td>
                  <td>${attemptStatusBadge(a.status)}</td>
                  <td>
                    <span class="er-badge ${tabCls}">${tabCnt} tab</span>
                    ${fsCnt ? `<span class="er-badge er-badge-warn">${fsCnt} lần thoát toàn màn hình</span>` : ''}
                  </td>
                  <td>
                    <strong>${esc(scoreTxt)}</strong>
                    ${a.status !== 'in_progress' && a.gradingStatus === 'needs_manual' ? ' <span class="er-badge er-badge-warn">Điểm tạm</span>' : ''}
                    <div style="font-size:11.5px;color:var(--er-muted);">${esc(GRADING_STATUS_LABELS[a.gradingStatus] || a.gradingStatus)}</div>
                    ${adjTxt ? `<div style="font-size:11.5px;color:var(--er-warn);">${esc(adjTxt)}</div>` : ''}
                  </td>
                  <td>
                    ${
                      a.status === 'in_progress'
                        ? `<button type="button" class="er-btn er-btn-danger er-btn-sm" data-er-action="lock-attempt" data-attempt-id="${esc(a.id)}">Khóa & thu bài</button>`
                        : `<span style="font-size:12px;color:var(--er-muted);">${esc(formatDateTimeVi(a.submittedAt))}</span>`
                    }
                  </td>
                </tr>
              `;
            })
            .join('')}
        </tbody>
      </table>
    </div>
  `;
}

function buildMonitorTabHTML(room) {
  return `
    <div id="er-monitor-panel" style="display:flex;flex-direction:column;gap:12px;">
      <div class="er-card" style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;">
        <div id="er-monitor-badges" class="er-btn-row">
          ${buildMonitorSummaryBadgesHTML(room)}
        </div>
        <div class="er-btn-row">
          <label class="er-check" style="font-size:12.5px;">
            <input type="checkbox" id="er-autorefresh-chk" ${state.autoRefresh ? 'checked' : ''}>
            Tự động làm mới (5 giây)
          </label>
          <button type="button" class="er-btn er-btn-sm" data-er-action="refresh-room">Làm mới ngay</button>
        </div>
      </div>

      <div id="er-monitor-results">
        ${buildMonitorResultsHTML(room)}
      </div>
    </div>
  `;
}

function formatEssayStudentResponse(resp) {
  if (resp === null || resp === undefined || resp === '') {
    return '(Học sinh bỏ trống câu này)';
  }
  if (typeof resp === 'object') {
    return String(resp.text || resp.answerText || resp.answer || JSON.stringify(resp));
  }
  return String(resp);
}

export function buildGradingTabHTML(
  queue = state.gradingQueue,
  room = selectedRoom(),
  onlyPending = state.onlyPendingGrading,
) {
  if (!queue) {
    return `<div class="er-empty">Đang tải danh sách chấm tự luận…</div>`;
  }
  const allItems = queue.items || [];
  const items = onlyPending
    ? allItems.filter((it) => it.earnedPointsP100 === null || it.earnedPointsP100 === undefined)
    : allItems;
  const markingGuidance = String(queue.markingGuidance || room?.markingGuidance || '').trim();
  const attemptSummaries = Array.isArray(queue.attempts) ? queue.attempts : [];

  return `
    <div style="display:flex;flex-direction:column;gap:12px;">
      <div class="er-card" style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;">
        <div class="er-btn-row">
          <span class="er-badge ${queue.pendingCount > 0 ? 'er-badge-warn' : 'er-badge-open'}">Chờ chấm: ${queue.pendingCount}</span>
          <span class="er-badge er-badge-teal">Đã chấm: ${queue.gradedCount}</span>
        </div>
        <div class="er-btn-row">
          <label class="er-check" style="font-size:12.5px;">
            <input type="checkbox" id="er-pending-only-chk" ${onlyPending ? 'checked' : ''}>
            Chỉ hiển thị bài chưa chấm
          </label>
          <button type="button" class="er-btn er-btn-sm" data-er-action="refresh-grading">Làm mới</button>
        </div>
      </div>

      ${
        markingGuidance
          ? `<div class="er-hint-box" data-marking-guidance="1">
               <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.03em;margin-bottom:4px;">Hướng dẫn chấm chung của đề</div>
               <div>${renderRichField(markingGuidance, null)}</div>
             </div>`
          : ''
      }

      ${
        attemptSummaries.length
          ? `<div class="er-card" data-attempt-adjustments="1" style="display:flex;flex-direction:column;gap:10px;">
               <div>
                 <strong>Điều chỉnh điểm toàn bài (giữ nguyên điểm từng câu)</strong>
                 <div style="font-size:12px;color:var(--er-muted);">Áp dụng trừ/cộng ở cấp cả bài làm (ví dụ -0,25 đ lỗi đơn vị toàn bài) mà không làm lệch thống kê từng câu.</div>
               </div>
               <div style="display:flex;flex-direction:column;gap:8px;">
                 ${attemptSummaries
                   .map((att) => {
                     const adjVal = (Number(att.scoreAdjustmentP100 || 0) / 100)
                       .toFixed(2)
                       .replace(/\.?0+$/, '');
                     return `
                       <form class="er-adjust-form" data-attempt-id="${esc(att.attemptId)}" style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;border:1px solid var(--er-border);border-radius:8px;background:#fafcff;">
                         <div style="min-width:190px;flex:1 1 200px;">
                           <strong>${esc(att.studentName)}</strong>
                           ${att.studentClass ? `<span style="color:var(--er-muted);"> (${esc(att.studentClass)})</span>` : ''}
                           <div style="font-size:12px;color:var(--er-muted);">
                             Tổng hiện tại: <strong>${esc(formatPointsVi(att.totalScoreP100))} / ${esc(formatPointsVi(att.totalPointsP100))}</strong>
                             ${att.isProvisionalScore ? '<span class="er-badge er-badge-warn" style="margin-left:4px;">Điểm tạm</span>' : ''}
                           </div>
                         </div>
                         <div class="er-btn-row" style="flex-wrap:wrap;">
                           <button type="button" class="er-btn er-btn-sm" data-er-action="quick-adjust" data-adjust="-0.25">-0,25 đ</button>
                           <button type="button" class="er-btn er-btn-sm" data-er-action="quick-adjust" data-adjust="-0.5">-0,5 đ</button>
                           <button type="button" class="er-btn er-btn-sm" data-er-action="quick-adjust" data-adjust="0">0 đ</button>
                           <input class="er-adjust-input" name="adjustmentPoints" type="number" step="0.01" min="-100" max="100" value="${esc(adjVal)}" style="width:92px;padding:5px 8px;border:1px solid var(--er-border);border-radius:6px;" aria-label="Điểm điều chỉnh toàn bài">
                           <input name="adjustmentNote" type="text" maxlength="500" value="${esc(att.adjustmentNote || '')}" placeholder="Lý do điều chỉnh toàn bài…" style="width:190px;padding:5px 8px;border:1px solid var(--er-border);border-radius:6px;">
                           <button type="submit" class="er-btn er-btn-soft er-btn-sm">Lưu điều chỉnh</button>
                         </div>
                       </form>
                     `;
                   })
                   .join('')}
               </div>
             </div>`
          : ''
      }

      ${
        items.length
          ? items
              .map((it) => {
                const maxPtsNum = (Number(it.maxPointsP100 || 0) / 100).toFixed(2).replace(/\.?0+$/, '');
                const curVal =
                  it.earnedPointsP100 !== null && it.earnedPointsP100 !== undefined
                    ? (Number(it.earnedPointsP100) / 100).toFixed(2).replace(/\.?0+$/, '')
                    : '';
                const rubric = Array.isArray(it.rubric) ? it.rubric : [];
                const formKey = `${it.attemptId}__${it.questionId}`;
                return `
                  <div class="er-grade-item" data-grade-card="${esc(formKey)}">
                    <div class="er-grade-head">
                      <div>
                        <strong>Câu ${esc(it.questionNumber)}</strong> ·
                        <strong>${esc(it.studentName)}</strong>
                        ${it.studentClass ? `<span style="color:var(--er-muted);">(${esc(it.studentClass)})</span>` : ''}
                        ${it.studentCode ? `<span style="color:var(--er-muted);">· SBD ${esc(it.studentCode)}</span>` : ''}
                      </div>
                      <div class="er-btn-row">
                        <span class="er-badge ${it.earnedPointsP100 == null ? 'er-badge-warn' : 'er-badge-open'}">
                          ${it.earnedPointsP100 == null ? 'Chưa chấm' : `${formatPointsVi(it.earnedPointsP100)} / ${formatPointsVi(it.maxPointsP100)} đ`}
                        </span>
                      </div>
                    </div>

                    <div class="er-grade-split">
                      <div style="display:flex;flex-direction:column;gap:8px;">
                        <div style="font-size:13px;line-height:1.5;">${renderRichField(it.stem, it.richDoc)}</div>
                        <div>
                          <div style="font-size:12px;font-weight:700;color:var(--er-muted);margin-bottom:4px;">BÀI LÀM CỦA HỌC SINH</div>
                          <div class="er-student-answer">${esc(formatEssayStudentResponse(it.response))}</div>
                        </div>
                      </div>

                      <div style="display:flex;flex-direction:column;gap:10px;">
                        <div class="er-rubric-box">
                          <div style="font-size:12px;font-weight:700;color:var(--er-teal-dark);">BIỂU ĐIỂM & HƯỚNG DẪN CHẤM (TỐI ĐA ${esc(formatPointsVi(it.maxPointsP100))} ĐIỂM)</div>
                          ${
                            rubric.length
                              ? rubric
                                  .map((step, sIdx) => {
                                    const stepPts =
                                      step.pointsQ4 !== undefined
                                        ? Number(step.pointsQ4) / 4
                                        : Number(step.points || 0);
                                    return `
                                      <label class="er-rubric-row">
                                        <span style="display:flex;gap:6px;align-items:flex-start;">
                                          <input type="checkbox" class="er-rubric-step-chk" data-step-pts="${esc(stepPts)}">
                                          <span><strong>Ý ${sIdx + 1}:</strong> ${renderRichField(step.text, step.richDoc)}</span>
                                        </span>
                                        <strong style="color:var(--er-teal-dark);white-space:nowrap;">+${esc(formatPointsVi(Math.round(stepPts * 100)))} đ</strong>
                                      </label>
                                    `;
                                  })
                                  .join('')
                              : `<div style="font-size:12.5px;color:var(--er-muted);">Không có từng ý biểu điểm rời. ${it.explanation ? '' : 'Thầy cô nhập điểm trực tiếp bên dưới.'}</div>`
                          }
                          ${
                            it.explanation
                              ? `<div style="font-size:12.5px;border-top:1px dashed var(--er-border);padding-top:6px;"><strong>Lời giải tham khảo:</strong> ${renderRichField(it.explanation, null)}</div>`
                              : ''
                          }
                        </div>

                        <form class="er-grade-form" data-attempt-id="${esc(it.attemptId)}" data-question-id="${esc(it.questionId)}" data-max-p100="${esc(it.maxPointsP100)}" style="display:flex;flex-direction:column;gap:8px;">
                          <div class="er-grid-2">
                            <div class="er-field">
                              <label>Điểm chấm (0 – ${esc(maxPtsNum)})</label>
                              <input class="er-score-input" name="earnedPoints" type="number" min="0" max="${esc(maxPtsNum)}" step="0.01" value="${esc(curVal)}" required>
                            </div>
                            <div class="er-field">
                              <label>Chấm nhanh</label>
                              <div class="er-btn-row">
                                <button type="button" class="er-btn er-btn-sm" data-er-action="quick-score" data-score="0">0 đ</button>
                                <button type="button" class="er-btn er-btn-sm" data-er-action="quick-score" data-score="${esc((Number(it.maxPointsP100) / 200).toFixed(2).replace(/\.?0+$/, ''))}">50%</button>
                                <button type="button" class="er-btn er-btn-sm er-btn-soft" data-er-action="quick-score" data-score="${esc(maxPtsNum)}">Tối đa</button>
                              </div>
                            </div>
                          </div>
                          <div class="er-field">
                            <label>Nhận xét cho học sinh (tùy chọn)</label>
                            <textarea name="graderNote" rows="2" placeholder="Ghi nhận điểm mạnh hoặc lỗi cần lưu ý…">${esc(it.graderNote || '')}</textarea>
                          </div>
                          <div class="er-btn-row" style="justify-content:flex-end;">
                            <button type="submit" class="er-btn er-btn-primary er-btn-sm">Lưu điểm câu này</button>
                          </div>
                        </form>
                      </div>
                    </div>
                  </div>
                `;
              })
              .join('')
          : `<div class="er-empty">${allItems.length ? 'Tất cả bài tự luận đã được chấm đủ!' : 'Đề thi trong phòng này không có câu tự luận cần chấm tay.'}</div>`
      }
    </div>
  `;
}

function buildAnalyticsTabHTML(room) {
  const an = state.analytics;
  if (!an) {
    return `<div class="er-empty">Đang tổng hợp thống kê…</div>`;
  }
  const hist = Array.isArray(an.histogram) ? an.histogram : [];
  const maxHist = Math.max(1, ...hist.map((b) => Number(b.count || 0)));
  const totalPts = Number(an.totalPointsP100 || room.totalPointsP100 || 0);
  const qStats = Array.isArray(an.questionStats) ? an.questionStats : [];
  const gradedCnt = Number(an.gradedCount ?? an.submittedCount ?? 0);
  const provCnt = Number(an.provisionalCount ?? an.needsManualCount ?? 0);

  return `
    <div style="display:flex;flex-direction:column;gap:14px;">
      <div class="er-card" style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;">
        <div>
          <strong>Báo cáo kết quả & Phổ điểm</strong>
          <div style="font-size:12.5px;color:var(--er-muted);">Tính trên ${esc(gradedCnt)} bài đã chấm đủ (trên tổng ${esc(an.submittedCount)} bài đã nộp/khóa${provCnt > 0 ? ` · ${esc(provCnt)} bài chờ chấm tự luận chưa vào phổ điểm` : ''}; thang ${esc(formatPointsVi(totalPts))} điểm).</div>
        </div>
        <div class="er-btn-row">
          <button type="button" class="er-btn er-btn-sm" data-er-action="refresh-analytics">Cập nhật số liệu</button>
          <button type="button" class="er-btn er-btn-primary" data-er-action="export-xlsx">Tải bảng điểm Excel (.xlsx)</button>
        </div>
      </div>

      <div class="er-kpis">
        <div class="er-kpi"><div class="er-kpi-label">Đã chấm đủ / Đã nộp</div><div class="er-kpi-value">${esc(gradedCnt)} / ${esc(an.submittedCount)}</div></div>
        <div class="er-kpi"><div class="er-kpi-label">Điểm trung bình</div><div class="er-kpi-value">${gradedCnt > 0 ? esc(formatPointsVi(an.avgScoreP100)) : '—'}</div></div>
        <div class="er-kpi"><div class="er-kpi-label">Điểm trung vị</div><div class="er-kpi-value">${gradedCnt > 0 ? esc(formatPointsVi(an.medianScoreP100)) : '—'}</div></div>
        <div class="er-kpi"><div class="er-kpi-label">Cao nhất / Thấp nhất</div><div class="er-kpi-value">${gradedCnt > 0 ? `${esc(formatPointsVi(an.maxScoreP100))} / ${esc(formatPointsVi(an.minScoreP100))}` : '—'}</div></div>
        <div class="er-kpi"><div class="er-kpi-label">Đạt từ 50% trở lên</div><div class="er-kpi-value">${gradedCnt > 0 ? `${esc(an.passRate)}%` : '—'}</div></div>
      </div>

      <div class="er-card">
        <div style="font-weight:700;margin-bottom:8px;">Phổ điểm (quy đổi thang 10)</div>
        <div class="er-hist">
          ${hist
            .map((b) => {
              const cnt = Number(b.count || 0);
              const pctHeight = cnt > 0 ? Math.max(10, Math.round((cnt / maxHist) * 100)) : 4;
              return `
                <div class="er-hist-col">
                  <div class="er-hist-cnt">${cnt}</div>
                  <div class="er-hist-bar" style="height:${pctHeight}%;" title="${esc(b.label)}: ${cnt} bài"></div>
                  <div class="er-hist-lbl">${esc(b.label)}</div>
                </div>
              `;
            })
            .join('')}
        </div>
      </div>

      <div class="er-table-wrap">
        <table class="er-table">
          <thead>
            <tr>
              <th>Câu</th>
              <th>Dạng</th>
              <th>Nội dung</th>
              <th>Điểm tối đa</th>
              <th>Tỷ lệ đúng hoàn toàn</th>
              <th>Đúng / Một phần / Sai</th>
              <th>Điểm TB</th>
            </tr>
          </thead>
          <tbody>
            ${
              qStats.length
                ? qStats
                    .map(
                      (q) => `
                      <tr>
                        <td><strong>Câu ${esc(q.order)}</strong></td>
                        <td>${esc(QUESTION_TYPES[q.type] || q.type)}</td>
                        <td style="max-width:300px;">${q.stem ? richTextHTML(q.stem) : '—'}</td>
                        <td>${esc(formatPointsVi(q.maxPointsP100))}</td>
                        <td><strong>${esc(q.correctRate)}%</strong></td>
                        <td>${esc(q.correctCount)} / ${esc(q.partialCount)} / ${esc(q.wrongCount)}</td>
                        <td>${esc(formatPointsVi(q.avgEarnedP100))}</td>
                      </tr>
                    `,
                    )
                    .join('')
                : '<tr><td colspan="7" style="text-align:center;color:var(--er-muted);">Chưa có dữ liệu trả lời câu hỏi.</td></tr>'
            }
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function buildAnswerKeysTabHTML(room) {
  const keys = Array.isArray(state.roomDetail?.answerKeys) ? state.roomDetail.answerKeys : [];
  if (!state.roomDetail) {
    return `<div class="er-empty">Đang tải khóa đáp án phòng thi…</div>`;
  }
  if (!keys.length) {
    return `<div class="er-empty">Phòng thi chưa có câu hỏi để cập nhật khóa đáp án.</div>`;
  }
  return `
    <form id="er-regrade-form" style="display:flex;flex-direction:column;gap:12px;">
      <div class="er-card" style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px;">
        <div>
          <strong>Sửa khóa đáp án &amp; Chấm lại bài đã nộp (${esc(room.roomCode)})</strong>
          <div style="font-size:12.5px;color:var(--er-muted);">Chỉnh đáp án hoặc điểm từng câu trong phòng đã phát và tự động chấm lại toàn bộ bài đã nộp (vẫn giữ điểm tự luận và điều chỉnh toàn bài).</div>
        </div>
        <button type="submit" class="er-btn er-btn-primary">Lưu khóa &amp; Chấm lại toàn phòng</button>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        ${keys
          .map((k) => {
            let inputHTML = '';
            if (k.type === 'mcq') {
              const opts = Array.isArray(k.options) ? k.options : [];
              inputHTML = `
                <select name="key_mcq_${esc(k.questionId)}" data-regrade-qid="${esc(k.questionId)}" data-regrade-type="mcq" aria-label="Đáp án đúng Câu ${esc(k.order)}" style="padding:6px 10px;border:1px solid var(--er-border);border-radius:6px;">
                  ${opts
                    .map((opt, idx) => {
                      const letter = String.fromCharCode(65 + idx);
                      const cleanOpt = String(opt || '').slice(0, 60);
                      return `<option value="${idx}" ${Number(k.answer) === idx ? 'selected' : ''}>${esc(letter)}${cleanOpt ? ` — ${esc(cleanOpt)}` : ''}</option>`;
                    })
                    .join('')}
                </select>
              `;
            } else if (k.type === 'truefalse') {
              const tv = Array.isArray(k.truthValues) ? k.truthValues : [false, false, false, false];
              inputHTML = `
                <div style="display:flex;flex-wrap:wrap;gap:10px;" data-regrade-qid="${esc(k.questionId)}" data-regrade-type="truefalse">
                  ${[0, 1, 2, 3]
                    .map(
                      (i) => `
                        <label class="er-check" style="font-size:12.5px;">
                          <input type="checkbox" name="key_tf_${esc(k.questionId)}_${i}" ${tv[i] ? 'checked' : ''}>
                          Ý ${String.fromCharCode(97 + i)} đúng
                        </label>
                      `,
                    )
                    .join('')}
                </div>
              `;
            } else if (k.type === 'short') {
              inputHTML = `
                <input type="text" name="key_short_${esc(k.questionId)}" data-regrade-qid="${esc(k.questionId)}" data-regrade-type="short" aria-label="Đáp án đúng Câu ${esc(k.order)}" value="${esc(k.answerText || '')}" style="width:100%;max-width:260px;padding:6px 10px;border:1px solid var(--er-border);border-radius:6px;" placeholder="Nhập đáp án đúng…">
              `;
            } else {
              inputHTML = `<span style="font-size:12.5px;color:var(--er-muted);">Câu tự luận (chấm ở tab Chấm tự luận)</span>`;
            }
            return `
              <div class="er-card" style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;padding:10px 14px;">
                <div style="flex:1 1 260px;min-width:0;">
                  <div style="font-size:12.5px;font-weight:700;color:var(--er-teal-dark);">Câu ${esc(k.order)} · ${esc(QUESTION_TYPES[k.type] || k.type)}</div>
                  <div style="font-size:13px;color:var(--er-ink);margin-top:2px;">${k.stem ? renderRichField(k.stem, null) : '—'}</div>
                </div>
                <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;">
                  <div>${inputHTML}</div>
                  <label style="font-size:12px;color:var(--er-muted);display:flex;align-items:center;gap:4px;">
                    Điểm:
                    <input type="number" step="0.01" min="0" max="100" name="key_pts_${esc(k.questionId)}" value="${esc(k.points)}" style="width:74px;padding:5px 8px;border:1px solid var(--er-border);border-radius:6px;">
                  </label>
                </div>
              </div>
            `;
          })
          .join('')}
      </div>
    </form>
  `;
}

function buildShellHTML(c) {
  const cur = c?.exam?.();
  const visibleRooms =
    state.scopeFilter === 'exam' && cur?.id
      ? state.rooms.filter((r) => r.examId === cur.id)
      : state.rooms;
  const active = selectedRoom();
  const preflightBlocked = isRoomLaunchBlocked(state.preflight);

  return `
    <div id="exam-rooms-shell" class="er-shell">
      <div class="er-topbar">
        <div>
          <div class="er-exam-title">${esc(cur?.title || 'Chưa chọn đề thi')}</div>
          <div class="er-exam-meta">
            ${cur ? `${esc(cur.subject || '')} · Lớp ${esc(cur.grade || '')} · ${esc(cur.questions?.length || 0)} câu · ${esc(cur.minutes || 45)} phút` : 'Mở một đề thi để tạo phòng thi trực tuyến hoặc giao bài tập về nhà.'}
          </div>
        </div>
        <div class="er-btn-row">
          <button type="button" class="er-btn er-btn-primary" id="er-quick-open-btn" data-er-action="quick-open" ${!cur || preflightBlocked ? 'disabled' : ''}>
            Mở phòng ngay (1 chạm)
          </button>
          <button type="button" class="er-btn er-btn-soft" data-er-action="toggle-create" ${!cur ? 'disabled' : ''}>
            ${state.createPanelOpen ? 'Đóng cấu hình' : 'Cấu hình phòng mới…'}
          </button>
        </div>
      </div>

      ${roomPreflightBannerHTML(state.preflight)}
      ${state.error ? `<div class="er-error">${esc(state.error)}</div>` : ''}
      ${state.createPanelOpen && cur ? buildCreateFormHTML(cur) : ''}

      <div class="er-room-strip">
        <div class="er-room-strip-head">
          <strong>Phòng thi & Bài tập (${visibleRooms.length})</strong>
          <div class="er-btn-row">
            <button type="button" class="er-btn er-btn-sm ${state.scopeFilter === 'exam' ? 'er-btn-soft' : ''}" data-er-action="scope-filter" data-scope="exam">Phòng của đề đang mở</button>
            <button type="button" class="er-btn er-btn-sm ${state.scopeFilter === 'all' ? 'er-btn-soft' : ''}" data-er-action="scope-filter" data-scope="all">Tất cả phòng của tôi (${state.rooms.length})</button>
          </div>
        </div>
      ${
        visibleRooms.length
          ? `<div class="er-room-pills">
               ${visibleRooms
                 .map(
                   (r) => `
                   <button type="button" class="er-room-pill ${r.id === state.selectedRoomId ? 'is-active' : ''}" data-er-action="select-room" data-room-id="${esc(r.id)}">
                     <div class="er-pill-top">
                       <span class="er-code">${esc(r.roomCode)}</span>
                       ${roomStatusBadge(r.status)}
                     </div>
                     <div style="font-weight:600;font-size:13px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(r.title)}</div>
                     <div data-er-pill-meta="${esc(r.id)}" style="font-size:11.5px;color:var(--er-muted);">
                       ${r.mode === 'homework' ? 'Bài tập' : 'Thi'} · ${esc(r.attemptCount || 0)} lượt
                       ${r.needsManualCount > 0 ? ` · <span style="color:var(--er-warn);font-weight:700;">${r.needsManualCount} chờ chấm</span>` : ''}
                     </div>
                   </button>
                 `,
                 )
                 .join('')}
             </div>`
          : `<div class="er-empty">Chưa có phòng nào${state.scopeFilter === 'exam' ? ' cho đề thi đang mở' : ''}. Nhấn <strong>Mở phòng ngay (1 chạm)</strong> ở trên để phát hành cho học sinh.</div>`
      }
      </div>

      ${
        active
          ? (() => {
              const tabs = [
                { id: 'share', label: 'Chia sẻ & Cấu hình' },
                {
                  id: 'monitor',
                  label: `Giám sát trực tiếp (${active.attemptCount ?? state.roomDetail?.attempts?.length ?? 0})`,
                },
                {
                  id: 'grading',
                  label:
                    active.needsManualCount > 0
                      ? `Chấm tự luận (${active.needsManualCount})`
                      : 'Chấm tự luận',
                },
                { id: 'analytics', label: 'Thống kê & Excel' },
                { id: 'keys', label: 'Đáp án & Chấm lại' },
              ];
              const activeTabId = VALID_TABS.includes(state.activeTab) ? state.activeTab : 'share';
              const loading = state.loadingTab === activeTabId;
              const panelHTML = loading
                ? '<div class="er-empty" role="status">Đang tải dữ liệu phòng thi…</div>'
                : activeTabId === 'share'
                  ? buildShareTabHTML(active)
                  : activeTabId === 'monitor'
                    ? buildMonitorTabHTML(active)
                    : activeTabId === 'grading'
                      ? buildGradingTabHTML()
                      : activeTabId === 'keys'
                        ? buildAnswerKeysTabHTML(active)
                        : buildAnalyticsTabHTML(active);
              return `<div class="er-card" style="display:flex;flex-direction:column;gap:14px;">
                <div class="er-tabs" role="tablist" aria-label="Quản lý phòng thi">
                  ${tabs
                    .map((t) => {
                      const isActive = activeTabId === t.id;
                      return `<button type="button" id="er-tab-${t.id}" class="er-tab ${isActive ? 'is-active' : ''}" role="tab" aria-selected="${isActive ? 'true' : 'false'}" aria-controls="er-tabpanel-${t.id}" tabindex="${isActive ? '0' : '-1'}" data-er-action="switch-tab" data-tab="${t.id}">${esc(t.label)}</button>`;
                    })
                    .join('')}
                </div>
                <div id="er-tabpanel-${activeTabId}" class="er-tabpanel" role="tabpanel" aria-labelledby="er-tab-${activeTabId}"${loading ? ' aria-busy="true"' : ''}>
                  ${panelHTML}
                </div>
              </div>`;
            })()
          : ''
      }
    </div>
  `;
}

const VALID_TABS = ['share', 'monitor', 'grading', 'analytics', 'keys'];

function escapeAttrValue(val) {
  const s = String(val ?? '');
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(s);
  }
  return s.replace(/["\\]/g, '\\$&');
}

function captureScrollState(wrapper) {
  if (!wrapper) return null;
  const tables = [];
  if (typeof wrapper.querySelectorAll === 'function') {
    wrapper.querySelectorAll('.er-table-wrap').forEach((el, idx) => {
      tables.push({ idx, top: el.scrollTop || 0, left: el.scrollLeft || 0 });
    });
  }
  return {
    wrapperTop: wrapper.scrollTop || 0,
    wrapperLeft: wrapper.scrollLeft || 0,
    tables,
  };
}

function restoreScrollState(wrapper, snap) {
  if (!snap || !wrapper) return;
  wrapper.scrollTop = snap.wrapperTop;
  wrapper.scrollLeft = snap.wrapperLeft;
  if (typeof wrapper.querySelectorAll === 'function') {
    const tables = wrapper.querySelectorAll('.er-table-wrap');
    for (const entry of snap.tables || []) {
      const tbl = tables[entry.idx];
      if (tbl) {
        tbl.scrollTop = entry.top;
        tbl.scrollLeft = entry.left;
      }
    }
  }
}

function captureFocusState(wrapper) {
  if (!wrapper || typeof document === 'undefined') return null;
  const active = document.activeElement;
  if (!active || active === document.body) return null;
  if (typeof wrapper.contains === 'function' && !wrapper.contains(active)) return null;

  let selectionStart = null;
  let selectionEnd = null;
  try {
    if (typeof active.selectionStart === 'number' && typeof active.selectionEnd === 'number') {
      selectionStart = active.selectionStart;
      selectionEnd = active.selectionEnd;
    }
  } catch {
    // Ignore selection read errors on number/date inputs
  }

  let selector = '';
  let fallbackSelector = '';
  if (active.id) {
    selector = `#${escapeAttrValue(active.id)}`;
  } else if (active.dataset?.erAction) {
    const action = active.dataset.erAction;
    const parts = [`[data-er-action="${escapeAttrValue(action)}"]`];
    if (active.dataset.tab) parts.push(`[data-tab="${escapeAttrValue(active.dataset.tab)}"]`);
    if (active.dataset.roomId) parts.push(`[data-room-id="${escapeAttrValue(active.dataset.roomId)}"]`);
    if (active.dataset.scope) parts.push(`[data-scope="${escapeAttrValue(active.dataset.scope)}"]`);
    if (active.dataset.attemptId) parts.push(`[data-attempt-id="${escapeAttrValue(active.dataset.attemptId)}"]`);
    if (active.dataset.origin) parts.push(`[data-origin="${escapeAttrValue(active.dataset.origin)}"]`);
    if (active.dataset.score !== undefined) parts.push(`[data-score="${escapeAttrValue(active.dataset.score)}"]`);
    if (active.dataset.adjust !== undefined) parts.push(`[data-adjust="${escapeAttrValue(active.dataset.adjust)}"]`);
    if (active.dataset.copy) parts.push(`[data-copy="${escapeAttrValue(active.dataset.copy)}"]`);
    const parentForm = active.closest?.('form[data-attempt-id]');
    if (parentForm) {
      const pAtt = parentForm.dataset.attemptId;
      const pQid = parentForm.dataset.questionId;
      if (pAtt && pQid) {
        selector = `form[data-attempt-id="${escapeAttrValue(pAtt)}"][data-question-id="${escapeAttrValue(pQid)}"] ${parts.join('')}`;
      } else if (pAtt) {
        selector = `form[data-attempt-id="${escapeAttrValue(pAtt)}"] ${parts.join('')}`;
      }
    }
    if (!selector) selector = parts.join('');
    if (action === 'lock-attempt') {
      fallbackSelector = '#er-autorefresh-chk, [data-er-action="refresh-room"], [role="tab"][aria-selected="true"]';
    }
  } else if (active.name) {
    const form = active.closest?.('form');
    if (form?.id) {
      selector = `#${escapeAttrValue(form.id)} [name="${escapeAttrValue(active.name)}"]`;
    } else if (form?.dataset?.attemptId && form?.dataset?.questionId) {
      selector = `form[data-attempt-id="${escapeAttrValue(form.dataset.attemptId)}"][data-question-id="${escapeAttrValue(form.dataset.questionId)}"] [name="${escapeAttrValue(active.name)}"]`;
      fallbackSelector = '#er-pending-only-chk, [role="tab"][aria-selected="true"]';
    } else if (form?.dataset?.attemptId) {
      selector = `form[data-attempt-id="${escapeAttrValue(form.dataset.attemptId)}"] [name="${escapeAttrValue(active.name)}"]`;
    } else {
      selector = `[name="${escapeAttrValue(active.name)}"]`;
    }
  } else if (active.classList?.contains('er-rubric-step-chk')) {
    const card = active.closest?.('[data-grade-card]');
    if (card?.dataset?.gradeCard) {
      selector = `[data-grade-card="${escapeAttrValue(card.dataset.gradeCard)}"] .er-rubric-step-chk`;
      fallbackSelector = '#er-pending-only-chk, [role="tab"][aria-selected="true"]';
    }
  } else if (active.getAttribute?.('type') === 'submit') {
    const form = active.closest?.('form');
    if (form?.id) {
      selector = `#${escapeAttrValue(form.id)} button[type="submit"]`;
    } else if (form?.dataset?.attemptId && form?.dataset?.questionId) {
      selector = `form[data-attempt-id="${escapeAttrValue(form.dataset.attemptId)}"][data-question-id="${escapeAttrValue(form.dataset.questionId)}"] button[type="submit"]`;
      fallbackSelector = '.er-grade-form .er-score-input, #er-pending-only-chk, [role="tab"][aria-selected="true"]';
    } else if (form?.dataset?.attemptId) {
      selector = `form[data-attempt-id="${escapeAttrValue(form.dataset.attemptId)}"] button[type="submit"]`;
    }
  }

  if (!selector) return null;
  let index = 0;
  if (typeof wrapper.querySelectorAll === 'function') {
    const matches = Array.from(wrapper.querySelectorAll(selector));
    const idx = matches.indexOf(active);
    if (idx >= 0) index = idx;
  }
  return { selector, index, fallbackSelector, selectionStart, selectionEnd };
}

function restoreFocusState(wrapper, snap) {
  if (!snap || !wrapper || typeof wrapper.querySelectorAll !== 'function') return false;
  const matches = Array.from(wrapper.querySelectorAll(snap.selector));
  let target = matches[snap.index] || matches[0] || null;
  if (target?.disabled) target = null;
  if (!target && snap.fallbackSelector) {
    const fallback = wrapper.querySelector(snap.fallbackSelector);
    if (fallback && !fallback.disabled) target = fallback;
  }
  if (!target || typeof target.focus !== 'function') return false;
  try {
    target.focus({ preventScroll: true });
  } catch {
    target.focus();
  }
  if (
    snap.selectionStart !== null &&
    snap.selectionEnd !== null &&
    typeof target.setSelectionRange === 'function'
  ) {
    try {
      target.setSelectionRange(snap.selectionStart, snap.selectionEnd);
    } catch {
      // Ignore setSelectionRange errors on unsupported input types
    }
  }
  return true;
}

function renderShell(c, options = {}) {
  const host = document.getElementById('exam-rooms-shell');
  if (!host) return;
  const wrapper = host.parentElement;
  if (!wrapper) return;
  const scrollSnap = options.resetScroll ? null : captureScrollState(wrapper);
  const focusSnap = options.focusTargetSelector
    ? {
        selector: options.focusTargetSelector,
        index: 0,
        fallbackSelector: options.fallbackSelector || '',
        selectionStart: null,
        selectionEnd: null,
      }
    : captureFocusState(wrapper);

  wrapper.innerHTML = buildShellHTML(c);
  if (typeof window !== 'undefined' && typeof window.renderMathInElement === 'function') {
    try {
      window.renderMathInElement(wrapper, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false },
        ],
        throwOnError: false,
      });
    } catch {
      // Ignore math render failure in modal preview
    }
  }
  bindShellEvents(c);
  restoreFocusState(wrapper, focusSnap);
  if (scrollSnap) restoreScrollState(wrapper, scrollSnap);
}

async function refreshQrImage(c) {
  const room = selectedRoom();
  if (!room) return;
  const baseUrl = state.qrBaseOrigin || (typeof location !== 'undefined' ? location.origin : '');
  try {
    const blob = await fetchAuthBlob(
      c,
      `/api/rooms/${encodeURIComponent(room.id)}/qr.svg?baseUrl=${encodeURIComponent(baseUrl)}`,
    );
    revokeQrUrl();
    qrObjectUrl = URL.createObjectURL(blob);
    const box = document.getElementById('er-qr-box');
    if (box) {
      box.innerHTML = `<img src="${esc(qrObjectUrl)}" alt="Mã QR phòng ${esc(room.roomCode)}">`;
    }
  } catch {
    // Keep non-fatal if SVG preview fails transiently
  }
}

async function loadRooms(c, { preferredRoomId = '' } = {}) {
  const res = await roomApi(c, '/api/rooms');
  state.rooms = Array.isArray(res?.rooms) ? res.rooms : [];
  const curId = c?.exam?.()?.id;
  if (preferredRoomId && state.rooms.some((r) => r.id === preferredRoomId)) {
    state.selectedRoomId = preferredRoomId;
  } else if (!state.rooms.some((r) => r.id === state.selectedRoomId)) {
    const matchCur = curId ? state.rooms.find((r) => r.examId === curId) : null;
    state.selectedRoomId = matchCur?.id || state.rooms[0]?.id || '';
  }
}

async function loadActiveTabData(c) {
  const tab = state.activeTab;
  const room = selectedRoom();
  if (!room) return;
  if (state.activeTab === 'share') {
    await refreshQrImage(c);
  } else if (tab === 'monitor' || tab === 'keys') {
    await loadRoomDetail(c, room.id, tab);
  } else if (state.activeTab === 'grading') {
    const session = state;
    const queue = await roomApi(
      c,
      `/api/rooms/${encodeURIComponent(room.id)}/grading-queue?includeGraded=true`,
    );
    if (state !== session || state.activeTab !== tab || state.selectedRoomId !== room.id) return;
    state.gradingQueue = queue;
    const idx = state.rooms.findIndex((r) => r.id === room.id);
    if (idx >= 0 && state.gradingQueue) {
      if (state.gradingQueue.pendingCount != null) {
        state.rooms[idx].needsManualCount = Number(state.gradingQueue.pendingCount);
      }
      const nextAttempts = state.gradingQueue.totalAttempts ?? state.gradingQueue.attemptCount;
      if (nextAttempts != null) {
        state.rooms[idx].attemptCount = Number(nextAttempts);
      }
    }
  } else if (state.activeTab === 'analytics') {
    const session = state;
    const analytics = await roomApi(c, `/api/rooms/${encodeURIComponent(room.id)}/analytics`);
    if (state !== session || state.activeTab !== tab || state.selectedRoomId !== room.id) return;
    state.analytics = analytics;
    const idx = state.rooms.findIndex((r) => r.id === room.id);
    if (idx >= 0 && state.analytics) {
      const nextAttempts =
        state.analytics.totalAttempts ??
        state.analytics.attemptCount ??
        (Array.isArray(state.analytics.attempts) ? state.analytics.attempts.length : state.analytics.submittedCount);
      if (nextAttempts != null) {
        state.rooms[idx].attemptCount = Number(nextAttempts);
      }
      if (state.analytics.needsManualCount != null) {
        state.rooms[idx].needsManualCount = Number(state.analytics.needsManualCount);
      }
    }
  }
}

async function loadRoomDetail(c, roomId, tab, signal) {
  const epoch = ++detailLoadEpoch;
  const session = state;
  const detail = await roomApi(c, `/api/rooms/${encodeURIComponent(roomId)}`, { signal });
  if (
    signal?.aborted ||
    epoch !== detailLoadEpoch ||
    state !== session ||
    state.activeTab !== tab ||
    state.selectedRoomId !== roomId ||
    (signal && !shouldPollMonitor())
  ) {
    return false;
  }
  state.roomDetail = detail;
  const idx = state.rooms.findIndex((room) => room.id === roomId);
  if (idx >= 0 && detail?.room) state.rooms[idx] = detail.room;
  return true;
}

function isDocumentHidden() {
  if (typeof document === 'undefined') return false;
  return document.hidden === true || document.visibilityState === 'hidden';
}

function shouldPollMonitor() {
  if (typeof document === 'undefined') return false;
  const dialog = document.getElementById('dialog');
  return Boolean(
    dialog?.open &&
      document.getElementById('exam-rooms-shell') &&
      state.activeTab === 'monitor' &&
      !state.loading &&
      !state.loadingTab &&
      state.autoRefresh &&
      selectedRoom() &&
      !isDocumentHidden(),
  );
}

function updateMonitorInPlace(c) {
  if (typeof document === 'undefined') return;
  const shell = document.getElementById('exam-rooms-shell');
  const room = selectedRoom();
  const badgesEl = document.getElementById('er-monitor-badges');
  const resultsEl = document.getElementById('er-monitor-results');
  if (!shell || !room || !badgesEl || !resultsEl || state.error) {
    renderShell(c);
    return;
  }
  const wrapper = shell.parentElement;
  const scrollSnap = captureScrollState(wrapper);
  const activeEl = document.activeElement;
  const focusInResults = Boolean(
    activeEl && typeof resultsEl.contains === 'function' && resultsEl.contains(activeEl),
  );
  const focusSnap = focusInResults ? captureFocusState(resultsEl) : null;

  badgesEl.innerHTML = buildMonitorSummaryBadgesHTML(room);
  resultsEl.innerHTML = buildMonitorResultsHTML(room);

  const monitorTabEl = shell.querySelector('[data-er-action="switch-tab"][data-tab="monitor"]');
  if (monitorTabEl) {
    const cnt = room.attemptCount ?? state.roomDetail?.attempts?.length ?? 0;
    monitorTabEl.textContent = `Giám sát trực tiếp (${cnt})`;
  }
  const gradingTabEl = shell.querySelector('[data-er-action="switch-tab"][data-tab="grading"]');
  if (gradingTabEl) {
    gradingTabEl.textContent =
      room.needsManualCount > 0 ? `Chấm tự luận (${room.needsManualCount})` : 'Chấm tự luận';
  }
  const pillMeta = shell.querySelector(`[data-er-pill-meta="${escapeAttrValue(room.id)}"]`);
  if (pillMeta) {
    pillMeta.innerHTML = `${room.mode === 'homework' ? 'Bài tập' : 'Thi'} · ${esc(room.attemptCount || 0)} lượt${
      room.needsManualCount > 0
        ? ` · <span style="color:var(--er-warn);font-weight:700;">${rCountText(room.needsManualCount)}</span>`
        : ''
    }`;
  }

  if (focusSnap) {
    const restored = restoreFocusState(resultsEl, focusSnap);
    if (!restored && focusSnap.fallbackSelector) {
      const fb = shell.querySelector(focusSnap.fallbackSelector);
      if (fb && typeof fb.focus === 'function') {
        try {
          fb.focus({ preventScroll: true });
        } catch {
          fb.focus();
        }
      }
    }
  }
  restoreScrollState(wrapper, scrollSnap);
}

function rCountText(count) {
  return `${count} chờ chấm`;
}

async function runMonitorRefresh(c) {
  if (!shouldPollMonitor()) {
    stopPolling();
    return;
  }
  if (pollRequest) return;
  const request = new AbortController();
  pollRequest = request;
  try {
    if (await loadRoomDetail(c, state.selectedRoomId, 'monitor', request.signal)) {
      if (!request.signal.aborted && shouldPollMonitor()) updateMonitorInPlace(c);
    }
  } catch {
    // Ignore transient poll error
  } finally {
    if (pollRequest === request) pollRequest = null;
  }
}

function detachVisibilityListener() {
  if (typeof document !== 'undefined' && visibilityHandler) {
    document.removeEventListener('visibilitychange', visibilityHandler);
  }
  visibilityHandler = null;
}

function ensureVisibilityListener(c) {
  if (typeof document === 'undefined') return;
  if (visibilityHandler) return;
  visibilityHandler = () => {
    const ctx = activeCtx || c;
    const dialog = document.getElementById('dialog');
    if (!dialog?.open || !document.getElementById('exam-rooms-shell')) {
      stopPolling();
      detachVisibilityListener();
      return;
    }
    syncPolling(ctx);
    if (shouldPollMonitor()) void runMonitorRefresh(ctx);
  };
  document.addEventListener('visibilitychange', visibilityHandler);
}

function syncPolling(c = activeCtx) {
  if (c) activeCtx = c;
  stopPolling();
  if (typeof document === 'undefined') return;
  const dialog = document.getElementById('dialog');
  if (
    dialog?.open &&
    state.activeTab === 'monitor' &&
    state.autoRefresh &&
    selectedRoom()
  ) {
    ensureVisibilityListener(c);
    if (shouldPollMonitor()) {
      pollTimer = setInterval(() => runMonitorRefresh(activeCtx || c), 5000);
    }
  } else if (!dialog?.open) {
    detachVisibilityListener();
  }
}

async function persistBeforeCreate(c) {
  if (typeof c?.persist === 'function') {
    try {
      await c.persist();
    } catch {
      // Allow server lookup even if local persist was a no-op
    }
  }
}

async function loadRoomPreflight(c, examSnapshot) {
  if (!examSnapshot?.id) {
    state.preflight = null;
    return null;
  }
  try {
    const report = await roomApi(c, '/api/exports/preflight', {
      method: 'POST',
      body: { exam: examSnapshot },
    });
    state.preflight = report && typeof report === 'object' ? report : null;
  } catch {
    state.preflight = null;
  }
  return state.preflight;
}

async function createRoomFromPayload(c, payload) {
  const cur = c?.exam?.();
  if (!cur?.id) {
    throw new Error('Cần mở một đề thi trước khi tạo phòng.');
  }
  await persistBeforeCreate(c);
  let created;
  try {
    created = await roomApi(c, '/api/rooms', {
      method: 'POST',
      body: {
        examId: cur.id,
        ...payload,
      },
    });
  } catch (err) {
    const detail = err?.data?.detail;
    const blockingIssues =
      detail?.blockingIssues ||
      err?.data?.blockingIssues ||
      detail?.preflight?.blockingIssues ||
      err?.data?.preflight?.blockingIssues;
    if (detail?.preflight || err?.data?.preflight || Array.isArray(blockingIssues)) {
      state.preflight =
        detail?.preflight ||
        err?.data?.preflight || {
          ready: false,
          blockingIssues: Array.isArray(blockingIssues) ? blockingIssues : [],
        };
    }
    throw err;
  }
  state.createPanelOpen = false;
  state.error = '';
  state.qrBaseOrigin = typeof location !== 'undefined' ? location.origin : '';
  await loadRooms(c, { preferredRoomId: created.id });
  state.activeTab = 'share';
  await loadActiveTabData(c);
  renderShell(c);
  syncPolling(c);
  notify(c, `Đã mở phòng ${created.roomCode}.`);
}

async function switchTab(c, nextTab, { focusTab = false } = {}) {
  const targetTab = VALID_TABS.includes(nextTab) ? nextTab : 'share';
  const epoch = ++tabLoadEpoch;
  state.error = '';
  state.confirmDeleteRoomId = '';
  state.activeTab = targetTab;
  state.loadingTab = targetTab;
  renderShell(c, {
    focusTargetSelector: focusTab ? `#er-tab-${escapeAttrValue(targetTab)}` : '',
  });
  syncPolling(c);
  try {
    await loadActiveTabData(c);
  } catch (err) {
    if (epoch !== tabLoadEpoch) return;
    state.error = err.message || 'Không tải được dữ liệu tab.';
  } finally {
    if (epoch === tabLoadEpoch) {
      state.loadingTab = '';
      const stillInTabs =
        typeof document !== 'undefined' &&
        document.activeElement?.closest?.('.er-tabs');
      renderShell(
        c,
        focusTab && stillInTabs
          ? { focusTargetSelector: `#er-tab-${escapeAttrValue(targetTab)}` }
          : {},
      );
      syncPolling(c);
    }
  }
}

function openDeleteRoomConfirmDialog(c, room, triggerBtn) {
  if (!room) return;
  if (
    triggerBtn &&
    typeof triggerBtn.focus === 'function' &&
    typeof document !== 'undefined' &&
    document.activeElement !== triggerBtn
  ) {
    try {
      triggerBtn.focus({ preventScroll: true });
    } catch {
      triggerBtn.focus();
    }
  }
  const dlg2 = typeof document !== 'undefined' ? document.getElementById('dialog-layer2') : null;
  if (dlg2 && typeof c?.modal === 'function') {
    state.pendingDeleteRoomId = room.id;
    state.confirmDeleteRoomId = '';
    c.modal(
      `Xóa phòng ${esc(room.roomCode)}?`,
      `<div class="er-confirm-delete" data-er-confirm-dialog="delete-room">
         <p id="er-delete-confirm-desc">Xóa phòng <strong>${esc(room.roomCode)}</strong> (${esc(room.title)}) và toàn bộ bài làm trong phòng này?</p>
         <p class="hint">Hành động này không thể hoàn tác. Danh sách lượt làm bài, điểm chấm tự luận và thống kê của phòng sẽ bị xóa vĩnh viễn.</p>
         <div class="modal-foot">
           <button type="button" id="er-cancel-delete-btn" data-action="close-top-modal" autofocus>Hủy</button>
           <button type="button" id="er-confirm-delete-btn" class="danger" data-action="er-confirm-delete-room" data-room-id="${esc(room.id)}">Xóa phòng</button>
         </div>
       </div>`,
      'Xác nhận trước khi xóa phòng thi.',
      { layer: 2 },
    );
    dlg2.setAttribute?.('aria-describedby', 'er-delete-confirm-desc');
    const confirmBox = dlg2.querySelector?.('.er-confirm-delete');
    if (confirmBox) {
      confirmBox.addEventListener('keydown', (ev) => {
        if (ev.key === 'ArrowLeft' || ev.key === 'ArrowRight') {
          const btns = Array.from(confirmBox.querySelectorAll('.modal-foot button:not([disabled])'));
          const idx = btns.indexOf(document.activeElement);
          if (idx >= 0 && btns.length > 1) {
            ev.preventDefault();
            const next =
              ev.key === 'ArrowRight'
                ? (idx + 1) % btns.length
                : (idx - 1 + btns.length) % btns.length;
            btns[next]?.focus?.();
          }
        }
      });
    }
    const onLayer2Close = () => {
      state.pendingDeleteRoomId = '';
      dlg2.removeAttribute?.('aria-describedby');
      dlg2.removeEventListener?.('close', onLayer2Close);
    };
    dlg2.addEventListener?.('close', onLayer2Close);
    document.getElementById('er-cancel-delete-btn')?.focus?.();
    return;
  }

  state.confirmDeleteRoomId = room.id;
  renderShell(c, { focusTargetSelector: '#er-cancel-inline-delete-btn' });
}

async function executeDeleteRoom(c, roomId, triggerBtn) {
  if (deleteInFlight) return;
  const room = state.rooms.find((r) => r.id === roomId);
  if (!room) return;
  const session = state;
  let deleted = false;
  deleteInFlight = true;
  if (triggerBtn) {
    triggerBtn.disabled = true;
    triggerBtn.textContent = 'Đang xóa…';
  }
  const dlg2 = typeof document !== 'undefined' ? document.getElementById('dialog-layer2') : null;
  try {
    await roomApi(c, `/api/rooms/${encodeURIComponent(room.id)}`, { method: 'DELETE' });
    deleted = true;
    notify(c, `Đã xóa phòng ${room.roomCode}.`);
    if (state !== session) return;
    state.pendingDeleteRoomId = '';
    state.confirmDeleteRoomId = '';
    state.rooms = state.rooms.filter((r) => r.id !== room.id);
    state.selectedRoomId = state.rooms.find((r) => r.examId === c?.exam?.()?.id)?.id || state.rooms[0]?.id || '';
    state.roomDetail = null;
    state.gradingQueue = null;
    state.analytics = null;
    await loadRooms(c);
    await loadActiveTabData(c);
    if (state !== session) return;
    if (dlg2?.open && dlg2.querySelector?.('.er-confirm-delete')) dlg2.close();
    renderShell(c, {
      focusTargetSelector: selectedRoom()
        ? '[data-er-action="select-room"].is-active'
        : '#er-quick-open-btn',
      fallbackSelector: '#er-quick-open-btn',
      resetScroll: true,
    });
    syncPolling(c);
  } catch (err) {
    if (state !== session) return;
    state.pendingDeleteRoomId = '';
    state.confirmDeleteRoomId = '';
    if (dlg2?.open && dlg2.querySelector?.('.er-confirm-delete')) dlg2.close();
    state.error = deleted
      ? 'Đã xóa phòng nhưng chưa tải lại được danh sách.'
      : err.message || 'Không thể xóa phòng thi.';
    renderShell(c, {
      focusTargetSelector: '[data-er-action="delete-room"]',
      fallbackSelector: '#er-quick-open-btn',
    });
  } finally {
    deleteInFlight = false;
    if (triggerBtn?.isConnected) {
      triggerBtn.disabled = false;
      triggerBtn.textContent = 'Xóa phòng';
    }
  }
}

function bindShellEvents(c) {
  const shell = document.getElementById('exam-rooms-shell');
  if (!shell) return;

  shell.addEventListener('keydown', (ev) => {
    const tabBtn = ev.target?.closest?.('.er-tabs [role="tab"][data-er-action="switch-tab"]');
    if (
      tabBtn &&
      !ev.altKey &&
      !ev.ctrlKey &&
      !ev.metaKey &&
      (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft' || ev.key === 'Home' || ev.key === 'End')
    ) {
      const tabs = Array.from(shell.querySelectorAll('.er-tabs [role="tab"][data-er-action="switch-tab"]'));
      const idx = tabs.indexOf(tabBtn);
      if (idx >= 0 && tabs.length) {
        ev.preventDefault();
        let nextIdx = idx;
        if (ev.key === 'ArrowRight') nextIdx = (idx + 1) % tabs.length;
        else if (ev.key === 'ArrowLeft') nextIdx = (idx - 1 + tabs.length) % tabs.length;
        else if (ev.key === 'Home') nextIdx = 0;
        else if (ev.key === 'End') nextIdx = tabs.length - 1;
        const nextTab = tabs[nextIdx]?.dataset?.tab;
        if (nextTab) {
          void switchTab(c, nextTab, { focusTab: true });
        }
      }
      return;
    }

    if (ev.key === 'Escape' && state.confirmDeleteRoomId) {
      ev.preventDefault();
      ev.stopPropagation();
      state.confirmDeleteRoomId = '';
      renderShell(c, { focusTargetSelector: '[data-er-action="delete-room"]' });
    }
  });

  shell.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('[data-er-action]');
    if (!btn) return;
    ev.preventDefault();
    const action = btn.dataset.erAction;
    state.error = '';

    try {
      if (action === 'toggle-create') {
        state.createPanelOpen = !state.createPanelOpen;
        renderShell(c);
        return;
      }
      if (action === 'quick-open') {
        const cur = c?.exam?.();
        await createRoomFromPayload(c, {
          mode: 'exam',
          title: cur?.title || 'Phòng thi trực tuyến',
          durationMinutes: resolveExamMinutes(cur, 45),
          status: 'open',
          maxAttempts: 1,
          shuffleQuestions: true,
          shuffleOptions: true,
          resultPolicy: 'score_only',
        });
        return;
      }
      if (action === 'scope-filter') {
        state.scopeFilter = btn.dataset.scope === 'all' ? 'all' : 'exam';
        state.confirmDeleteRoomId = '';
        const visible =
          state.scopeFilter === 'exam' && c?.exam?.()?.id
            ? state.rooms.filter((r) => r.examId === c.exam().id)
            : state.rooms;
        if (visible.length && !visible.some((r) => r.id === state.selectedRoomId)) {
          state.selectedRoomId = visible[0].id;
          state.roomDetail = null;
          state.gradingQueue = null;
          state.analytics = null;
          await loadActiveTabData(c);
        }
        renderShell(c);
        syncPolling(c);
        return;
      }
      if (action === 'select-room') {
        stopPolling();
        state.selectedRoomId = btn.dataset.roomId || '';
        state.confirmDeleteRoomId = '';
        state.roomDetail = null;
        state.gradingQueue = null;
        state.analytics = null;
        state.qrBaseOrigin = typeof location !== 'undefined' ? location.origin : '';
        await loadActiveTabData(c);
        renderShell(c, { resetScroll: true });
        syncPolling(c);
        return;
      }
      if (action === 'switch-tab') {
        await switchTab(c, btn.dataset.tab || 'share', { focusTab: false });
        return;
      }
      if (action === 'copy-text') {
        await copyText(c, btn.dataset.copy || '', btn.dataset.label || 'nội dung');
        return;
      }
      if (action === 'use-qr-origin') {
        state.qrBaseOrigin = btn.dataset.origin || '';
        await refreshQrImage(c);
        notify(c, 'Đã cập nhật địa chỉ trong mã QR.');
        return;
      }
      if (action === 'download-qr') {
        const room = selectedRoom();
        if (!room) return;
        const baseUrl = state.qrBaseOrigin || (typeof location !== 'undefined' ? location.origin : '');
        const blob = await fetchAuthBlob(
          c,
          `/api/rooms/${encodeURIComponent(room.id)}/qr.svg?baseUrl=${encodeURIComponent(baseUrl)}`,
        );
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `MaQR_${room.roomCode}.svg`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        return;
      }
      if (action === 'toggle-room-status') {
        const room = selectedRoom();
        if (!room) return;
        const nextStatus = btn.dataset.nextStatus || 'closed';
        const res = await roomApi(c, `/api/rooms/${encodeURIComponent(room.id)}`, {
          method: 'PATCH',
          body: { status: nextStatus },
        });
        if (res?.room) {
          const idx = state.rooms.findIndex((r) => r.id === room.id);
          if (idx >= 0) state.rooms[idx] = res.room;
        }
        renderShell(c);
        notify(c, nextStatus === 'closed' ? 'Đã đóng phòng thi.' : 'Đã mở lại phòng thi.');
        return;
      }
      if (action === 'delete-room') {
        const room = selectedRoom();
        if (!room) return;
        openDeleteRoomConfirmDialog(c, room, btn);
        return;
      }
      if (action === 'cancel-delete-room') {
        state.confirmDeleteRoomId = '';
        renderShell(c, { focusTargetSelector: '[data-er-action="delete-room"]' });
        return;
      }
      if (action === 'confirm-delete-room') {
        if (state.confirmDeleteRoomId && btn.dataset.roomId === state.confirmDeleteRoomId) {
          await executeDeleteRoom(c, state.confirmDeleteRoomId, btn);
        }
        return;
      }
      if (action === 'refresh-room' || action === 'refresh-grading' || action === 'refresh-analytics') {
        await loadRooms(c, { preferredRoomId: selectedRoom()?.id || '' });
        await loadActiveTabData(c);
        renderShell(c);
        return;
      }
      if (action === 'lock-attempt') {
        const room = selectedRoom();
        const attemptId = btn.dataset.attemptId;
        if (!room || !attemptId) return;
        await roomApi(
          c,
          `/api/rooms/${encodeURIComponent(room.id)}/attempts/${encodeURIComponent(attemptId)}/lock`,
          { method: 'POST', body: { reason: 'teacher_lock' } },
        );
        await loadActiveTabData(c);
        renderShell(c);
        notify(c, 'Đã khóa phiên và thu bài học sinh.');
        return;
      }
      if (action === 'quick-score') {
        const form = btn.closest('form');
        const input = form?.querySelector('.er-score-input');
        if (input) input.value = btn.dataset.score || '0';
        return;
      }
      if (action === 'quick-adjust') {
        const form = btn.closest('form');
        const input = form?.querySelector('.er-adjust-input');
        const noteInput = form?.querySelector('input[name="adjustmentNote"]');
        if (input) input.value = btn.dataset.adjust || '0';
        if (noteInput && !noteInput.value.trim() && Number(btn.dataset.adjust || 0) < 0) {
          noteInput.value = 'Trừ lỗi toàn bài';
        }
        return;
      }
      if (action === 'export-xlsx') {
        const room = selectedRoom();
        if (!room) return;
        const blob = await fetchAuthBlob(c, `/api/rooms/${encodeURIComponent(room.id)}/export.xlsx`);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `BangDiem_${room.roomCode}.xlsx`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        notify(c, 'Đã tải bảng điểm Excel (.xlsx).');
        return;
      }
    } catch (err) {
      state.error = err.message || 'Thao tác chưa thành công.';
      renderShell(c);
    }
  });

  shell.addEventListener('change', async (ev) => {
    const t = ev.target;
    if (t.id === 'er-autorefresh-chk') {
      state.autoRefresh = t.checked;
      syncPolling(c);
      return;
    }
    if (t.id === 'er-pending-only-chk') {
      state.onlyPendingGrading = t.checked;
      renderShell(c);
      return;
    }
    if (t.classList.contains('er-rubric-step-chk')) {
      const card = t.closest('.er-grade-item');
      if (!card) return;
      const checked = Array.from(card.querySelectorAll('.er-rubric-step-chk:checked'));
      const total = checked.reduce((acc, el) => acc + Number(el.dataset.stepPts || 0), 0);
      const input = card.querySelector('.er-score-input');
      if (input) {
        const maxVal = Number(input.max || total);
        const clamped = Math.min(maxVal, Math.max(0, Math.round(total * 100) / 100));
        input.value = String(clamped);
      }
    }
  });

  shell.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    state.error = '';
    try {
      if (form.id === 'er-create-form') {
        const fd = new FormData(form);
        await createRoomFromPayload(c, {
          title: String(fd.get('title') || '').trim(),
          classLabel: String(fd.get('classLabel') || '').trim(),
          mode: fd.get('mode') === 'homework' ? 'homework' : 'exam',
          status: 'open',
          durationMinutes: Number(fd.get('durationMinutes') || 0),
          deadlineAt: fromDateTimeLocalInput(fd.get('deadlineAt')),
          maxAttempts: Math.max(1, Number(fd.get('maxAttempts') || 1)),
          pin: String(fd.get('pin') || '').trim(),
          resultPolicy: String(fd.get('resultPolicy') || 'score_only'),
          maxTabSwitches: Math.max(0, Number(fd.get('maxTabSwitches') || 0)),
          shuffleQuestions: form.querySelector('[name="shuffleQuestions"]')?.checked || false,
          shuffleOptions: form.querySelector('[name="shuffleOptions"]')?.checked || false,
          releaseResultsAfterClose:
            form.querySelector('[name="releaseResultsAfterClose"]')?.checked || false,
          requireFullscreen: form.querySelector('[name="requireFullscreen"]')?.checked || false,
          allowLan: form.querySelector('[name="allowLan"]')?.checked || false,
        });
        return;
      }

      if (form.id === 'er-update-form') {
        const room = selectedRoom();
        if (!room) return;
        const fd = new FormData(form);
        const body = {
          title: String(fd.get('title') || '').trim(),
          classLabel: String(fd.get('classLabel') || '').trim(),
          status: String(fd.get('status') || room.status),
          durationMinutes: Number(fd.get('durationMinutes') || 0),
          deadlineAt: fromDateTimeLocalInput(fd.get('deadlineAt')),
          maxTabSwitches: Math.max(0, Number(fd.get('maxTabSwitches') || 0)),
          resultPolicy: String(fd.get('resultPolicy') || room.resultPolicy),
          releaseResultsAfterClose:
            form.querySelector('[name="releaseResultsAfterClose"]')?.checked || false,
          requireFullscreen: form.querySelector('[name="requireFullscreen"]')?.checked || false,
          allowLan: form.querySelector('[name="allowLan"]')?.checked || false,
        };
        const newPin = String(fd.get('pin') || '').trim();
        if (newPin) body.pin = newPin;
        const res = await roomApi(c, `/api/rooms/${encodeURIComponent(room.id)}`, {
          method: 'PATCH',
          body,
        });
        if (res?.room) {
          const idx = state.rooms.findIndex((r) => r.id === room.id);
          if (idx >= 0) state.rooms[idx] = res.room;
        }
        await refreshQrImage(c);
        renderShell(c);
        notify(c, 'Đã cập nhật cấu hình phòng.');
        return;
      }

      if (form.classList.contains('er-grade-form')) {
        const room = selectedRoom();
        if (!room) return;
        const attemptId = form.dataset.attemptId;
        const questionId = form.dataset.questionId;
        const maxP100 = Number(form.dataset.maxP100 || 0);
        const fd = new FormData(form);
        const rawNum = Number(String(fd.get('earnedPoints') || '0').replace(',', '.'));
        if (!Number.isFinite(rawNum) || rawNum < 0) {
          throw new Error('Điểm chấm không hợp lệ.');
        }
        const earnedPointsP100 = Math.round(rawNum * 100);
        if (earnedPointsP100 > maxP100) {
          throw new Error(`Điểm chấm vượt quá mức tối đa (${formatPointsVi(maxP100)} điểm).`);
        }
        const graderNote = String(fd.get('graderNote') || '').trim();
        await roomApi(
          c,
          `/api/rooms/${encodeURIComponent(room.id)}/attempts/${encodeURIComponent(attemptId)}/grades/${encodeURIComponent(questionId)}`,
          {
            method: 'PUT',
            body: { earnedPointsP100, graderNote },
          },
        );
        await loadRooms(c, { preferredRoomId: room.id });
        await loadActiveTabData(c);
        renderShell(c);
        notify(c, 'Đã lưu điểm câu tự luận.');
        return;
      }

      if (form.classList.contains('er-adjust-form')) {
        const room = selectedRoom();
        if (!room) return;
        const attemptId = form.dataset.attemptId;
        const fd = new FormData(form);
        const rawNum = Number(String(fd.get('adjustmentPoints') || '0').replace(',', '.'));
        if (!Number.isFinite(rawNum) || rawNum < -100 || rawNum > 100) {
          throw new Error('Giá trị điều chỉnh toàn bài không hợp lệ.');
        }
        const adjustmentPointsP100 = Math.round(rawNum * 100);
        const adjustmentNote = String(fd.get('adjustmentNote') || '').trim();
        await roomApi(
          c,
          `/api/rooms/${encodeURIComponent(room.id)}/attempts/${encodeURIComponent(attemptId)}/adjustment`,
          {
            method: 'PUT',
            body: { adjustmentPointsP100, adjustmentNote },
          },
        );
        await loadRooms(c, { preferredRoomId: room.id });
        await loadActiveTabData(c);
        renderShell(c);
        notify(c, 'Đã lưu điều chỉnh tổng điểm toàn bài.');
        return;
      }

      if (form.id === 'er-regrade-form') {
        const room = selectedRoom();
        if (!room) return;
        const keys = Array.isArray(state.roomDetail?.answerKeys) ? state.roomDetail.answerKeys : [];
        const updates = [];
        for (const k of keys) {
          const ptsInput = form.querySelector(`[name="key_pts_${CSS?.escape ? CSS.escape(k.questionId) : k.questionId}"]`);
          const ptsNum = ptsInput ? Number(String(ptsInput.value || '').replace(',', '.')) : k.points;
          if (!Number.isFinite(ptsNum) || ptsNum < 0) {
            throw new Error(`Điểm câu ${k.order} không hợp lệ.`);
          }
          const item = { questionId: k.questionId, points: ptsNum };
          if (k.type === 'mcq') {
            const sel = form.querySelector(`[name="key_mcq_${CSS?.escape ? CSS.escape(k.questionId) : k.questionId}"]`);
            if (sel) item.answer = Number(sel.value);
          } else if (k.type === 'truefalse') {
            const tv = [0, 1, 2, 3].map((i) => {
              const chk = form.querySelector(`[name="key_tf_${CSS?.escape ? CSS.escape(k.questionId) : k.questionId}_${i}"]`);
              return Boolean(chk?.checked);
            });
            item.truthValues = tv;
          } else if (k.type === 'short') {
            const inp = form.querySelector(`[name="key_short_${CSS?.escape ? CSS.escape(k.questionId) : k.questionId}"]`);
            if (inp) item.answerText = String(inp.value || '').trim();
          }
          updates.push(item);
        }
        const res = await roomApi(c, `/api/rooms/${encodeURIComponent(room.id)}/regrade`, {
          method: 'POST',
          body: { questions: updates },
        });
        await loadRooms(c, { preferredRoomId: room.id });
        await loadActiveTabData(c);
        renderShell(c);
        notify(c, `Đã cập nhật khóa đáp án và chấm lại ${res?.regradedCount ?? 0} bài.`);
      }
    } catch (err) {
      state.error = err.message || 'Không thể lưu thay đổi.';
      renderShell(c);
    }
  });
}

let dialogCloseHandler = null;

export async function openExamRooms(c = activeCtx, { tab = 'share', openCreate = false } = {}) {
  if (c) activeCtx = c;
  injectStyles();
  tabLoadEpoch += 1;
  stopPolling();
  detachVisibilityListener();
  revokeQrUrl();

  state = {
    rooms: [],
    selectedRoomId: '',
    roomDetail: null,
    gradingQueue: null,
    analytics: null,
    preflight: null,
    activeTab: VALID_TABS.includes(tab) ? tab : 'share',
    scopeFilter: c?.exam?.() ? 'exam' : 'all',
    onlyPendingGrading: true,
    createPanelOpen: !!openCreate,
    autoRefresh: true,
    loading: true,
    loadingTab: '',
    pendingDeleteRoomId: '',
    confirmDeleteRoomId: '',
    error: '',
    qrBaseOrigin: typeof location !== 'undefined' ? location.origin : '',
  };

  c.modal(
    'Phòng thi trực tuyến & Bài tập về nhà',
    '<div id="exam-rooms-shell" class="er-shell"><div class="er-empty">Đang tải danh sách phòng thi…</div></div>',
    'Tạo mã phòng hoặc mã QR cho học sinh làm bài, giám sát thời gian thực, chấm tự luận và xuất bảng điểm Excel.',
  );

  const dialog = document.getElementById('dialog');
  if (dialog) {
    if (dialogCloseHandler) {
      dialog.removeEventListener('close', dialogCloseHandler);
    }
    dialogCloseHandler = () => {
      tabLoadEpoch += 1;
      stopPolling();
      detachVisibilityListener();
      revokeQrUrl();
      dialog.removeEventListener('close', dialogCloseHandler);
      dialogCloseHandler = null;
    };
    dialog.addEventListener('close', dialogCloseHandler);
  }

  try {
    await Promise.all([loadRooms(c), loadRoomPreflight(c, c?.exam?.())]);
    if (selectedRoom()) {
      await loadActiveTabData(c);
    }
  } catch (err) {
    state.error = err.message || 'Không tải được danh sách phòng thi.';
  } finally {
    state.loading = false;
  }

  renderShell(c, { resetScroll: true });
  syncPolling(c);
}

export function mountExamRooms(c) {
  activeCtx = c;
  injectStyles();
}

export async function handleExamRoomAction(action, node, c = activeCtx) {
  if (c) activeCtx = c;
  switch (action) {
    case 'exam-rooms':
    case 'open-exam-rooms':
    case 'room-center':
      await openExamRooms(c);
      return true;
    case 'create-exam-room':
    case 'open-exam-room-create':
      await openExamRooms(c, { openCreate: true });
      return true;
    case 'exam-room-grading':
      await openExamRooms(c, { tab: 'grading' });
      return true;
    case 'er-confirm-delete-room':
      if (
        document.getElementById('dialog-layer2')?.open &&
        state.pendingDeleteRoomId &&
        node?.dataset?.roomId === state.pendingDeleteRoomId
      ) {
        await executeDeleteRoom(c, state.pendingDeleteRoomId, node);
      }
      return true;
    default:
      return false;
  }
}

export async function handleExamRoomSubmit() {
  return false;
}

export { buildShellHTML, renderShell, syncPolling };
