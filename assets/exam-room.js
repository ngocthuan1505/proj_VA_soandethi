const ROOT_ID = 'student-room-app';
const TYPE_LABELS = {
  mcq: 'Trắc nghiệm nhiều lựa chọn',
  truefalse: 'Trắc nghiệm Đúng / Sai',
  short: 'Trả lời ngắn',
  essay: 'Tự luận',
};
const STATUS_LABELS = {
  draft: 'Phòng chưa mở',
  open: 'Đang mở',
  closed: 'Đã đóng',
  archived: 'Đã lưu trữ',
};
const GRADING_STATUS_LABELS = {
  auto_graded: 'Đã chấm tự động',
  needs_manual: 'Đang chờ giáo viên chấm tự luận',
  graded: 'Đã chấm hoàn tất',
};

const appState = {
  screen: 'loading', // 'lookup' | 'join' | 'exam' | 'result'
  roomCode: '',
  roomMeta: null,
  attempt: null,
  attemptToken: '',
  exam: null,
  answers: {},
  flagged: new Set(),
  currentIndex: 0,
  viewMode: 'single', // 'single' | 'all'
  mobileNavOpen: false,
  confirmSubmitOpen: false,
  serverOffsetMs: 0,
  saveState: 'idle', // 'idle' | 'saving' | 'saved' | 'error'
  saveLabel: 'Đã đồng bộ',
  hadNetworkError: false,
  localAnsweredCount: null,
  error: '',
  warningBanner: '',
  submitting: false,
  result: null,
  audioState: {}, // { [fileId]: { blobUrl, playsUsed, playsRemaining, maxPlays, loading, activePlayback, error } }
  resumeOffer: null, // { attemptId, attemptToken, studentName }
};

let timerInterval = null;
let autoSaveTimer = null;
let periodicBackupTimer = null;
let lastVisibilityBlurAt = 0;
let lastCopyEventAt = 0;
let listenersBound = false;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => {
    switch (ch) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      case "'":
        return '&#39;';
      default:
        return ch;
    }
  });
}

function formatPointsVi(p100) {
  if (p100 === null || p100 === undefined || !Number.isFinite(Number(p100))) return '—';
  const num = Number(p100) / 100;
  return num.toFixed(2).replace(/\.?0+$/, '').replace('.', ',');
}

function formatDateTimeVi(ms) {
  if (!ms) return '';
  try {
    return new Date(Number(ms)).toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

function storageSessionKey(code) {
  return `mach_room_session_${String(code || '').toUpperCase()}`;
}

function storageDraftKey(attemptId) {
  return `mach_room_draft_${attemptId}`;
}

function loadSavedSession(code) {
  try {
    const raw = localStorage.getItem(storageSessionKey(code));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(code, data) {
  try {
    localStorage.setItem(storageSessionKey(code), JSON.stringify(data));
  } catch {
    // Ignore storage quota errors
  }
}

function clearSavedSession(code) {
  try {
    localStorage.removeItem(storageSessionKey(code));
  } catch {
    // Ignore errors
  }
}

function loadSavedDraft(attemptId) {
  try {
    const raw = localStorage.getItem(storageDraftKey(attemptId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveDraft(attemptId, answers, flaggedSet) {
  try {
    localStorage.setItem(
      storageDraftKey(attemptId),
      JSON.stringify({
        answers,
        flagged: Array.from(flaggedSet || []),
        updatedAt: Date.now(),
      }),
    );
  } catch {
    // Ignore quota errors
  }
}

function extractRoomCodeFromPath() {
  const parts = String(location.pathname || '')
    .split('/')
    .filter(Boolean);
  if (parts[0] === 'phong-thi' && parts[1]) {
    return decodeURIComponent(parts[1]).trim().toUpperCase();
  }
  const urlCode = new URLSearchParams(location.search).get('code');
  return urlCode ? urlCode.trim().toUpperCase() : '';
}

async function apiFetch(path, { method = 'GET', body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers['X-Attempt-Token'] = token;
  const response = await fetch(path, {
    method,
    headers,
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
      `Lỗi kết nối (${response.status}).`;
    const err = new Error(msg);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  if (data && Number.isFinite(Number(data.serverNow))) {
    appState.serverOffsetMs = Number(data.serverNow) - Date.now();
  }
  return data;
}

function renderRunHTML(node) {
  if (!node || typeof node !== 'object') return '';
  if (node.type === 'hardBreak') return '<br>';
  if (node.type === 'math' || node.type === 'inlineMath') {
    const latex = node.attrs?.latex || node.text || '';
    return `$${esc(latex)}$`;
  }
  if (node.type === 'text') {
    let out = esc(node.text || '');
    const marks = Array.isArray(node.marks) ? node.marks : [];
    for (const m of marks) {
      const mType = typeof m === 'string' ? m : m?.type;
      if (mType === 'bold' || mType === 'strong') out = `<strong>${out}</strong>`;
      else if (mType === 'italic' || mType === 'em') out = `<em>${out}</em>`;
      else if (mType === 'underline') out = `<u>${out}</u>`;
      else if (mType === 'superscript') out = `<sup>${out}</sup>`;
      else if (mType === 'subscript') out = `<sub>${out}</sub>`;
    }
    return out;
  }
  const inner = Array.isArray(node.content) ? node.content.map(renderRunHTML).join('') : '';
  if (node.type === 'paragraph') return `<p style="margin:0 0 6px;">${inner}</p>`;
  if (node.type === 'bulletList') return `<ul style="margin:4px 0 8px 18px;">${inner}</ul>`;
  if (node.type === 'orderedList') return `<ol style="margin:4px 0 8px 18px;">${inner}</ol>`;
  if (node.type === 'listItem') return `<li>${inner}</li>`;
  return inner;
}

const TF_OPT_PREFIX_RE = /^\s*[a-d]\)\s*/i;

function stripRichDocLeadingPrefix(node) {
  if (!node || typeof node !== 'object') return { node, stripped: false };
  if (node.type === 'text' && typeof node.text === 'string') {
    const nextText = node.text.replace(TF_OPT_PREFIX_RE, '');
    return {
      node: nextText === node.text ? node : { ...node, text: nextText },
      stripped: true,
    };
  }
  if (Array.isArray(node.runs) && node.runs.length) {
    const runs = [...node.runs];
    for (let i = 0; i < runs.length; i++) {
      const r = runs[i];
      if (r && typeof r.text === 'string' && r.text.length) {
        runs[i] = { ...r, text: r.text.replace(TF_OPT_PREFIX_RE, '') };
        return { node: { ...node, runs }, stripped: true };
      }
      if (r && r.latex) return { node, stripped: true };
    }
  }
  const arrKey = Array.isArray(node.content) ? 'content' : Array.isArray(node.blocks) ? 'blocks' : '';
  if (arrKey) {
    const list = [...node[arrKey]];
    for (let i = 0; i < list.length; i++) {
      const res = stripRichDocLeadingPrefix(list[i]);
      if (res.stripped) {
        list[i] = res.node;
        return { node: { ...node, [arrKey]: list }, stripped: true };
      }
    }
  }
  return { node, stripped: false };
}

export function stripTrueFalseOptionPrefix(stmt, richDoc = null) {
  const cleanText = String(stmt ?? '').replace(TF_OPT_PREFIX_RE, '');
  const cleanRichDoc = richDoc && typeof richDoc === 'object' ? stripRichDocLeadingPrefix(richDoc).node : richDoc;
  return { text: cleanText, richDoc: cleanRichDoc };
}

function renderRichContent(text, richDoc) {
  if (richDoc && typeof richDoc === 'object') {
    if (Array.isArray(richDoc.content)) {
      return renderRunHTML(richDoc);
    }
    if (Array.isArray(richDoc.blocks)) {
      return richDoc.blocks
        .map((blk) => {
          if (Array.isArray(blk.runs)) {
            return `<p style="margin:0 0 6px;">${blk.runs
              .map((r) => {
                if (r.latex) return `$${esc(r.latex)}$`;
                let out = esc(r.text || '');
                if (r.bold) out = `<strong>${out}</strong>`;
                if (r.italic) out = `<em>${out}</em>`;
                if (r.underline) out = `<u>${out}</u>`;
                return out;
              })
              .join('')}</p>`;
          }
          return renderRunHTML(blk);
        })
        .join('');
    }
  }
  return esc(text || '').replace(/\n/g, '<br>');
}

function renderDataChartSVG(data) {
  if (!Array.isArray(data) || !data.length) return '';
  const max = Math.max(...data.map((d) => Number(d?.value || 0)), 1);
  const w = Math.max(300, data.length * 76 + 32);
  const bars = data
    .map((d, i) => {
      const val = Number(d?.value || 0);
      const h = Math.round((val / max) * 124);
      const x = i * 76 + 24;
      const lbl = String(d?.label || '');
      return `
        <g>
          <rect x="${x}" y="${158 - h}" width="38" height="${h}" rx="4" fill="#0f4c81"/>
          <text x="${x + 19}" y="${150 - h}" text-anchor="middle" font-size="11.5" font-weight="700" fill="#0b3a63">${esc(val)}</text>
          <text x="${x + 19}" y="178" text-anchor="middle" font-size="11" fill="#334155">${esc(lbl.length > 10 ? `${lbl.slice(0, 9)}…` : lbl)}</text>
        </g>
      `;
    })
    .join('');
  return `<svg viewBox="0 0 ${w} 195" width="${w}" height="195" role="img" aria-label="Biểu đồ dữ liệu">${bars}<line x1="12" y1="158" x2="${w - 12}" y2="158" stroke="#94a3b8" stroke-width="1"/></svg>`;
}

function getPassagesMap() {
  const raw = appState.exam?.passages;
  const map = new Map();
  if (Array.isArray(raw)) {
    for (const p of raw) {
      if (p && p.id) map.set(String(p.id), p);
    }
  } else if (raw && typeof raw === 'object') {
    for (const [k, p] of Object.entries(raw)) {
      if (p && typeof p === 'object') map.set(String(p.id || k), p);
    }
  }
  return map;
}

function revokeAllAudioBlobs() {
  for (const entry of Object.values(appState.audioState)) {
    if (entry?.blobUrl) {
      try {
        URL.revokeObjectURL(entry.blobUrl);
      } catch {
        // Ignore cleanup errors
      }
    }
  }
  appState.audioState = {};
}

function initAudioEntries() {
  revokeAllAudioBlobs();
  const seed = (aud) => {
    if (!aud || !aud.fileId) return;
    const fid = String(aud.fileId);
    const maxP = Number(aud.maxPlays || 2);
    const used = Number(aud.playsUsed || 0);
    const rem = Number.isFinite(Number(aud.playsRemaining))
      ? Number(aud.playsRemaining)
      : Math.max(0, maxP - used);
    appState.audioState[fid] = {
      fileId: fid,
      filename: String(aud.filename || 'Đoạn âm thanh'),
      url: String(aud.url || ''),
      blobUrl: '',
      playsUsed: used,
      playsRemaining: rem,
      maxPlays: maxP,
      loading: false,
      activePlayback: false,
      error: '',
    };
  };
  seed(appState.exam?.audio);
  for (const q of appState.exam?.questions || []) {
    seed(q?.audio);
  }
  for (const p of getPassagesMap().values()) {
    seed(p?.audio);
  }
}

function lockExhaustedAudio(audioEl, st) {
  if (st) st.activePlayback = false;
  if (!audioEl) return;
  audioEl.pause();
  audioEl.currentTime = 0;
  audioEl.removeAttribute('controls');
  audioEl.src = '';
  audioEl.removeAttribute('src');
  if (st && st.blobUrl) {
    try {
      URL.revokeObjectURL(st.blobUrl);
    } catch {
      // Ignore
    }
    st.blobUrl = '';
  }
}

export function renderAudioCardHTML(aud) {
  if (!aud || !aud.fileId) return '';
  const st = appState.audioState[String(aud.fileId)] || {
    fileId: String(aud.fileId),
    filename: String(aud.filename || 'Tệp nghe'),
    url: String(aud.url || ''),
    blobUrl: '',
    playsUsed: Number(aud.playsUsed || 0),
    playsRemaining: Number(aud.playsRemaining ?? aud.maxPlays ?? 2),
    maxPlays: Number(aud.maxPlays || 2),
    loading: false,
    activePlayback: false,
    error: '',
  };
  const exhausted = st.playsRemaining <= 0;
  const keepAudioTag = Boolean(st.blobUrl && (st.activePlayback || !exhausted));
  const btnText = st.loading
    ? 'Đang tải audio…'
    : st.activePlayback
      ? 'Đang phát lượt hiện tại…'
      : st.blobUrl
        ? 'Tải & phát lượt tiếp theo'
        : 'Nghe đoạn audio';
  return `
    <div class="sr-audio-card" data-audio-box="${esc(st.fileId)}">
      <div class="sr-audio-top">
        <div>
          <strong>Nghe audio:</strong> ${esc(st.filename)}
        </div>
        <span class="sr-q-pts" style="background:${exhausted && !st.activePlayback ? '#fee2e2' : '#d1fae5'};color:${exhausted && !st.activePlayback ? '#991b1b' : '#065f46'};">
          Còn ${esc(st.playsRemaining)} / ${esc(st.maxPlays)} lượt tải phát
        </span>
      </div>
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;">
        <button type="button" class="sr-btn sr-btn-soft sr-btn-sm" data-sr-action="play-audio" data-file-id="${esc(st.fileId)}" ${exhausted || st.loading ? 'disabled' : ''}>
          ${btnText}
        </button>
        ${st.error ? `<span style="font-size:12.5px;color:#991b1b;">${esc(st.error)}</span>` : ''}
      </div>
      ${keepAudioTag ? `<audio class="sr-audio-el" controls autoplay src="${esc(st.blobUrl)}"></audio>` : ''}
    </div>
  `;
}

function getQuestionChoiceGroup(q) {
  return String(q?.choiceGroup || q?.track || '').trim();
}

export function formatChoiceGroupLabel(grp) {
  const clean = String(grp || '').trim();
  if (!clean) return 'Phần chung';
  if (/^(?:tự\s*chọn|nhánh|hướng|phần)\b/i.test(clean)) return clean;
  return `Tự chọn ${clean}`;
}

function getExamChoiceGroups(questions) {
  const groups = [];
  const seen = new Set();
  for (const q of questions || []) {
    const grp = getQuestionChoiceGroup(q);
    if (grp && !seen.has(grp)) {
      seen.add(grp);
      groups.push(grp);
    }
  }
  return groups;
}

function isAnswerValueNonEmpty(val, qtype = '') {
  if (val === null || val === undefined) return false;
  if (qtype === 'mcq' || typeof val === 'number') return Number.isInteger(val);
  if (qtype === 'truefalse' || Array.isArray(val)) {
    return Array.isArray(val) && val.some((x) => x === true || x === false);
  }
  if (typeof val === 'string') return val.trim().length > 0;
  return true;
}

function isQuestionAnswered(q) {
  return isAnswerValueNonEmpty(appState.answers[q.id], q.type);
}

function countLocalAnswered() {
  const qs = appState.exam?.questions;
  if (Array.isArray(qs) && qs.length) {
    return qs.filter(isQuestionAnswered).length;
  }
  return Object.values(appState.answers || {}).filter((v) => isAnswerValueNonEmpty(v)).length;
}

function renderQuestionMediaHTML(q, passageMap) {
  const parts = [];
  if (q.passageId && passageMap.has(String(q.passageId))) {
    const p = passageMap.get(String(q.passageId));
    parts.push(`
      <div class="sr-passage-box">
        ${p.title ? `<div style="font-weight:700;color:var(--sr-brand-dark, var(--sr-teal-dark, #0b3a63));margin-bottom:4px;">${esc(p.title)}</div>` : ''}
        <div>${renderRichContent(p.text || p.passageText || '', p.richDoc)}</div>
        ${p.audio ? `<div style="margin-top:10px;">${renderAudioCardHTML(p.audio)}</div>` : ''}
      </div>
    `);
  } else if (q.passageText) {
    parts.push(`
      <div class="sr-passage-box">
        ${q.passageTitle ? `<div style="font-weight:700;color:var(--sr-brand-dark, var(--sr-teal-dark, #0b3a63));margin-bottom:4px;">${esc(q.passageTitle)}</div>` : ''}
        <div>${esc(q.passageText).replace(/\n/g, '<br>')}</div>
      </div>
    `);
  }

  if (q.audio) {
    parts.push(renderAudioCardHTML(q.audio));
  }

  if (q.dataLinked && Array.isArray(appState.exam?.data) && appState.exam.data.length) {
    const dRows = appState.exam.data;
    parts.push(`
      <div class="sr-passage-box">
        <div style="font-weight:700;margin-bottom:6px;color:var(--sr-brand-dark, var(--sr-teal-dark, #0b3a63));">Bảng số liệu & Biểu đồ minh họa</div>
        <div class="sr-scroll-box">
          <table class="sr-table">
            <thead><tr>${dRows.map((d) => `<th>${esc(d.label)}</th>`).join('')}</tr></thead>
            <tbody><tr>${dRows.map((d) => `<td>${esc(d.value)}</td>`).join('')}</tr></tbody>
          </table>
        </div>
        <div class="sr-scroll-box sr-svg-wrap" style="margin-top:8px;">
          ${renderDataChartSVG(dRows)}
        </div>
      </div>
    `);
  }

  if (Array.isArray(q.formulas) && q.formulas.length) {
    parts.push(
      q.formulas
        .map((f) => {
          const latex = typeof f === 'string' ? f : f?.latex || '';
          return latex ? `<div class="sr-formula-block">$$${esc(latex)}$$</div>` : '';
        })
        .join(''),
    );
  }

  if (Array.isArray(q.tables) && q.tables.length) {
    parts.push(
      q.tables
        .map((t) => {
          const rows = Array.isArray(t?.rows) ? t.rows : [];
          if (!rows.length) return '';
          return `
            <div class="sr-scroll-box">
              <table class="sr-table">
                ${rows
                  .map((r, rIdx) => {
                    const cells = Array.isArray(r) ? r : [];
                    const tag = rIdx === 0 ? 'th' : 'td';
                    return `<tr>${cells.map((c) => `<${tag}>${esc(c)}</${tag}>`).join('')}</tr>`;
                  })
                  .join('')}
              </table>
            </div>
          `;
        })
        .join(''),
    );
  }

  if (Array.isArray(q.images) && q.images.length) {
    parts.push(
      q.images
        .map((img) => {
          const src = String(img?.data || img?.src || '');
          if (!src.startsWith('data:image/') && !src.startsWith('/assets/')) return '';
          return `
            <figure class="sr-img-wrap" style="margin:4px 0;">
              <img src="${esc(src)}" alt="${esc(img?.caption || 'Hình minh họa câu hỏi')}">
              ${img?.caption ? `<figcaption class="sr-muted" style="margin-top:4px;">${esc(img.caption)}</figcaption>` : ''}
            </figure>
          `;
        })
        .join(''),
    );
  }

  return parts.join('');
}

function renderQuestionInputHTML(q) {
  const ans = appState.answers[q.id];

  if (q.type === 'mcq') {
    const opts = Array.isArray(q.options) ? q.options : [];
    const docs = Array.isArray(q.optionDocs) ? q.optionDocs : [];
    return `
      <div class="sr-options" role="radiogroup" aria-label="Chọn đáp án">
        ${opts
          .map((opt, idx) => {
            const selected = ans === idx;
            const letter = String.fromCharCode(65 + idx);
            return `
              <button type="button" class="sr-opt-card ${selected ? 'is-selected' : ''}" data-sr-action="pick-mcq" data-qid="${esc(q.id)}" data-idx="${idx}" aria-pressed="${selected}">
                <span class="sr-opt-key">${esc(letter)}</span>
                <span class="sr-opt-text">${renderRichContent(opt, docs[idx])}</span>
              </button>
            `;
          })
          .join('')}
      </div>
    `;
  }

  if (q.type === 'truefalse') {
    const opts = Array.isArray(q.options) ? q.options : ['', '', '', ''];
    const docs = Array.isArray(q.optionDocs) ? q.optionDocs : [];
    const cur = Array.isArray(ans) ? ans : [null, null, null, null];
    return `
      <div class="sr-tf-list">
        ${[0, 1, 2, 3]
          .map((rowIdx) => {
            const val = cur[rowIdx];
            const clean = stripTrueFalseOptionPrefix(opts[rowIdx] ?? '', docs[rowIdx]);
            const labelLetter = String.fromCharCode(97 + rowIdx);
            return `
              <div class="sr-tf-row">
                <div class="sr-tf-stmt"><strong>${esc(labelLetter)})</strong> ${renderRichContent(clean.text, clean.richDoc)}</div>
                <div class="sr-tf-toggle">
                  <button type="button" class="sr-tf-btn ${val === true ? 'is-true' : ''}" data-sr-action="pick-tf" data-qid="${esc(q.id)}" data-row="${rowIdx}" data-val="true" aria-pressed="${val === true}">Đúng</button>
                  <button type="button" class="sr-tf-btn ${val === false ? 'is-false' : ''}" data-sr-action="pick-tf" data-qid="${esc(q.id)}" data-row="${rowIdx}" data-val="false" aria-pressed="${val === false}">Sai</button>
                </div>
              </div>
            `;
          })
          .join('')}
      </div>
    `;
  }

  if (q.type === 'short') {
    const curStr = typeof ans === 'string' ? ans : '';
    return `
      <div class="sr-field">
        <label for="sr-short-${esc(q.id)}">Đáp án ngắn của bạn</label>
        <input id="sr-short-${esc(q.id)}" class="sr-input sr-short-input" data-qid="${esc(q.id)}" type="text" value="${esc(curStr)}" placeholder="Nhập số hoặc từ ngắn (ví dụ: 1,5 hoặc -3)…" autocomplete="off">
      </div>
    `;
  }

  const curEssay = typeof ans === 'string' ? ans : '';
  const wordCount = curEssay.trim() ? curEssay.trim().split(/\s+/).length : 0;
  return `
    <div class="sr-field">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <label for="sr-essay-${esc(q.id)}">Bài làm tự luận</label>
        <span class="sr-muted" data-word-count="${esc(q.id)}">${wordCount} từ</span>
      </div>
      <textarea id="sr-essay-${esc(q.id)}" class="sr-textarea sr-essay-input" data-qid="${esc(q.id)}" rows="7" placeholder="Trình bày đầy đủ các bước lập luận tại đây…">${esc(curEssay)}</textarea>
    </div>
  `;
}

function renderQuestionCardHTML(q, index, total, passageMap, hasChoiceGroups = false) {
  const isFlagged = appState.flagged.has(q.id);
  const ptsTxt = q.points ? `${String(q.points).replace('.', ',')} điểm` : '';
  const grp = getQuestionChoiceGroup(q);
  const trackBadgeHTML = hasChoiceGroups
    ? `<span class="sr-q-pts" data-track-badge="${esc(grp || 'common')}" style="background:${grp ? '#fef3c7' : '#e8f2fc'};color:${grp ? '#92400e' : '#0b3a63'};font-weight:700;">${esc(formatChoiceGroupLabel(grp))}</span>`
    : '';
  return `
    <article class="sr-q-card" data-q-card="${esc(q.id)}">
      <div class="sr-q-head">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          <span class="sr-q-badge">Câu ${index + 1} / ${total}</span>
          ${trackBadgeHTML}
          <span class="sr-q-pts">${esc(TYPE_LABELS[q.type] || q.type)}${ptsTxt ? ` · ${esc(ptsTxt)}` : ''}</span>
        </div>
        <button type="button" class="sr-flag-btn ${isFlagged ? 'is-flagged' : ''}" data-sr-action="toggle-flag" data-qid="${esc(q.id)}" aria-pressed="${isFlagged}">
          ${isFlagged ? 'Đã đánh dấu xem lại' : 'Đánh dấu xem lại'}
        </button>
      </div>
      ${renderQuestionMediaHTML(q, passageMap)}
      <div class="sr-stem">${renderRichContent(q.stem, q.richDoc)}</div>
      ${renderQuestionInputHTML(q)}
    </article>
  `;
}

function renderLookupScreenHTML() {
  return `
    <div class="sr-center-wrap">
      <div class="sr-card">
        <div class="sr-brand-row" style="margin-bottom:10px;">
          <img src="/assets/exam-icon.svg" alt="" width="28" height="28">
          <strong>Vào phòng thi trực tuyến</strong>
        </div>
        <p class="sr-muted" style="margin-top:0;">Nhập mã phòng gồm 6 ký tự do giáo viên cung cấp hoặc quét mã QR bằng điện thoại.</p>
        ${appState.error ? `<div class="sr-alert sr-alert-danger">${esc(appState.error)}</div>` : ''}
        <form id="sr-lookup-form" class="sr-form">
          <div class="sr-field">
            <label for="sr-code-input">Mã phòng thi</label>
            <input id="sr-code-input" class="sr-input" name="roomCode" placeholder="Ví dụ: K7M9P2" maxlength="12" value="${esc(appState.roomCode)}" style="text-transform:uppercase;letter-spacing:0.14em;font-weight:700;" required autofocus>
          </div>
          <button type="submit" class="sr-btn sr-btn-primary">Kiểm tra phòng thi</button>
        </form>
      </div>
    </div>
  `;
}

export function renderJoinScreenHTML() {
  const m = appState.roomMeta;
  const openToJoin = m?.status === 'open';
  const modeText = m?.mode === 'homework' ? 'Bài tập về nhà' : 'Kiểm tra trực tuyến';
  const durText = m?.durationMinutes > 0 ? `${m.durationMinutes} phút` : 'Không giới hạn phiên';
  const choiceGroups = Array.isArray(m?.choiceGroups) ? m.choiceGroups : [];

  return `
    <div class="sr-center-wrap">
      <div class="sr-join-hero">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
          <span class="sr-room-code-pill">${esc(m.roomCode)}</span>
          <span class="sr-q-pts">${esc(STATUS_LABELS[m.status] || m.status)}</span>
        </div>
        <h1 class="sr-title">${esc(m.title)}</h1>
        <div class="sr-meta-list">
          <span>${esc(modeText)}</span>
          ${m.classLabel ? `<span>· Lớp ${esc(m.classLabel)}</span>` : ''}
          <span>· ${esc(m.questionCount)} câu</span>
          <span>· Thang ${esc(formatPointsVi(m.totalPointsP100))} điểm</span>
          <span>· Thời gian: ${esc(durText)}</span>
          ${m.opensAt ? `<span>· Mở từ: ${esc(formatDateTimeVi(m.opensAt))}</span>` : ''}
      ${m.deadlineAt ? `<span>· Hạn đóng: ${esc(formatDateTimeVi(m.deadlineAt))}</span>` : ''}
        </div>
        ${
          choiceGroups.length
            ? `<div class="sr-alert sr-alert-info" style="margin:10px 0 0;">
                 Đề có ${esc(choiceGroups.length)} hướng tự chọn (${choiceGroups.map((g) => esc(formatChoiceGroupLabel(g))).join(' / ')}): chỉ cần làm <strong>Phần chung + 1 trong các hướng tự chọn</strong>.
               </div>`
            : ''
        }
      </div>

      ${appState.error ? `<div class="sr-alert sr-alert-danger">${esc(appState.error)}</div>` : ''}

      ${
        appState.resumeOffer
          ? `<div class="sr-card" style="margin-bottom:14px;border-color:#1e78c8;background:#e8f2fc;">
               <strong>Tìm thấy bài làm đã lưu trên thiết bị</strong>
               <p class="sr-muted" style="margin:6px 0 12px;">Thí sinh <strong>${esc(appState.resumeOffer.studentName)}</strong> có một lượt thi chưa hoàn tất hoặc đã nộp trên trình duyệt này.</p>
               <div style="display:flex;flex-wrap:wrap;gap:8px;">
                 <button type="button" class="sr-btn sr-btn-primary" data-sr-action="resume-saved">Khôi phục phiên làm bài</button>
                 <button type="button" class="sr-btn" data-sr-action="discard-saved">Làm với thông tin mới</button>
               </div>
             </div>`
          : ''
      }

      ${
        !openToJoin
          ? `<div class="sr-alert sr-alert-warn">Phòng này hiện ở trạng thái <strong>${esc(STATUS_LABELS[m.status] || m.status)}</strong> nên chưa thể bắt đầu lượt làm mới.</div>`
          : ''
      }

      <div class="sr-card">
        <form id="sr-join-form" class="sr-form">
          <div class="sr-field">
            <label for="sr-name">Họ và tên học sinh *</label>
            <input id="sr-name" class="sr-input" name="studentName" placeholder="Nhập đầy đủ họ và tên" maxlength="120" required ${!openToJoin ? 'disabled' : ''}>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <div class="sr-field">
              <label for="sr-class">Lớp</label>
              <input id="sr-class" class="sr-input" name="studentClass" placeholder="Ví dụ: 9A1" maxlength="60" ${!openToJoin ? 'disabled' : ''}>
            </div>
            <div class="sr-field">
              <label for="sr-scode">Số báo danh / Mã HS</label>
              <input id="sr-scode" class="sr-input" name="studentCode" placeholder="Tùy chọn" maxlength="60" ${!openToJoin ? 'disabled' : ''}>
            </div>
          </div>
          ${
            m.requiresPin
              ? `<div class="sr-field">
                   <label for="sr-pin">Mã PIN vào phòng *</label>
                   <input id="sr-pin" class="sr-input" name="pin" type="password" placeholder="Nhập mã PIN giáo viên cung cấp" maxlength="32" required ${!openToJoin ? 'disabled' : ''}>
                 </div>`
              : ''
          }
          ${
            m.requireFullscreen || m.maxTabSwitches > 0
              ? `<div class="sr-alert sr-alert-info" style="margin:2px 0 0;">
                   ${m.requireFullscreen ? 'Phòng thi yêu cầu bật chế độ toàn màn hình. ' : ''}
                   ${m.maxTabSwitches > 0 ? `Hệ thống sẽ tự động thu bài nếu rời màn hình quá ${esc(m.maxTabSwitches)} lần.` : ''}
                 </div>`
              : ''
          }
          <button type="submit" class="sr-btn sr-btn-primary" ${!openToJoin ? 'disabled' : ''}>Bắt đầu làm bài</button>
          <button type="button" class="sr-btn sr-btn-sm" data-sr-action="switch-code">Nhập mã phòng khác</button>
        </form>
      </div>
    </div>
  `;
}

function formatCountdown(msRemaining) {
  if (msRemaining === null || msRemaining === undefined) return 'Không giới hạn';
  const totalSec = Math.max(0, Math.floor(msRemaining / 1000));
  const hrs = Math.floor(totalSec / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  const pad = (n) => String(n).padStart(2, '0');
  return hrs > 0 ? `${pad(hrs)}:${pad(mins)}:${pad(secs)}` : `${pad(mins)}:${pad(secs)}`;
}

function renderNavGridHTML(questions) {
  const groups = getExamChoiceGroups(questions);
  if (!groups.length) {
    return `
      <div class="sr-nav-grid">
        ${questions
          .map((q, idx) => {
            const answered = isQuestionAnswered(q);
            const flagged = appState.flagged.has(q.id);
            const current = appState.viewMode === 'single' && appState.currentIndex === idx;
            return `
              <button type="button" class="sr-qnum-btn ${answered ? 'is-answered' : ''} ${flagged ? 'is-flagged' : ''} ${current ? 'is-current' : ''}" data-sr-action="jump-q" data-idx="${idx}" aria-label="Câu ${idx + 1}">
                ${idx + 1}
              </button>
            `;
          })
          .join('')}
      </div>
    `;
  }
  const buckets = new Map();
  questions.forEach((q, idx) => {
    const key = getQuestionChoiceGroup(q);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push({ q, idx });
  });
  return Array.from(buckets.entries())
    .map(
      ([grp, items]) => `
        <div style="margin-top:6px;">
          <div style="font-size:11.5px;font-weight:700;color:var(--sr-muted);margin-bottom:4px;">${esc(formatChoiceGroupLabel(grp))}</div>
          <div class="sr-nav-grid">
            ${items
              .map(({ q, idx }) => {
                const answered = isQuestionAnswered(q);
                const flagged = appState.flagged.has(q.id);
                const current = appState.viewMode === 'single' && appState.currentIndex === idx;
                return `
                  <button type="button" class="sr-qnum-btn ${answered ? 'is-answered' : ''} ${flagged ? 'is-flagged' : ''} ${current ? 'is-current' : ''}" data-sr-action="jump-q" data-idx="${idx}" aria-label="Câu ${idx + 1}">
                    ${idx + 1}
                  </button>
                `;
              })
              .join('')}
          </div>
        </div>
      `,
    )
    .join('');
}

export function renderExamScreenHTML() {
  const questions = appState.exam?.questions || [];
  const total = questions.length;
  const answeredCount = questions.filter(isQuestionAnswered).length;
  const passageMap = getPassagesMap();
  const room = appState.roomMeta || {};
  const att = appState.attempt || {};
  const choiceGroups = getExamChoiceGroups(questions);
  const hasChoiceGroups = choiceGroups.length > 0;

  const remMs = att.expiresAt
    ? Math.max(0, Number(att.expiresAt) - (Date.now() + appState.serverOffsetMs))
    : null;
  const timerCls =
    remMs === null ? '' : remMs <= 60000 ? 'is-urgent' : remMs <= 300000 ? 'is-warn' : '';
  const saveCls =
    appState.saveState === 'error'
      ? 'is-err is-offline'
      : appState.saveState === 'saved'
        ? 'is-ok'
        : '';

  const quoteText = appState.exam?.quote?.chosen || appState.exam?.subject === 'Ngữ văn'
    ? appState.exam?.quote?.text
    : '';

  let shownQuestions;
  if (appState.viewMode === 'all') {
    let lastGroup = null;
    shownQuestions = questions
      .map((q, idx) => {
        const curGroup = getQuestionChoiceGroup(q);
        const sectionHeading =
          hasChoiceGroups && curGroup !== lastGroup
            ? `<div class="sr-passage-box" data-track-section="${esc(curGroup || 'common')}" style="margin-top:8px;margin-bottom:4px;font-weight:700;color:var(--sr-brand-dark, #0b3a63);">${esc(formatChoiceGroupLabel(curGroup))}${curGroup ? ' (Nhánh tự chọn)' : ' (Bắt buộc)'}</div>`
            : '';
        lastGroup = curGroup;
        return sectionHeading + renderQuestionCardHTML(q, idx, total, passageMap, hasChoiceGroups);
      })
      .join('');
  } else {
    shownQuestions = questions[appState.currentIndex]
      ? renderQuestionCardHTML(
          questions[appState.currentIndex],
          appState.currentIndex,
          total,
          passageMap,
          hasChoiceGroups,
        )
      : '<div class="sr-card">Đề thi chưa có câu hỏi.</div>';
  }

  return `
    <header class="sr-exam-header">
      <div class="sr-header-inner">
        <div class="sr-header-title-wrap">
          <div class="sr-header-title">${esc(room.title || appState.exam?.title || 'Phòng thi')}</div>
          <div class="sr-header-sub">
            ${esc(att.studentName || '')}
            ${att.variantCode ? ` · Mã đề ${esc(att.variantCode)}` : ''}
            · Đã làm ${answeredCount}/${total} câu
          </div>
        </div>
        <div class="sr-header-controls">
          <span id="sr-save-pill" class="sr-save-pill ${saveCls}">${esc(appState.saveLabel)}</span>
          <div id="sr-timer" class="sr-timer ${timerCls}">${esc(formatCountdown(remMs))}</div>
          ${
            room.requireFullscreen && (typeof document === 'undefined' || !document.fullscreenElement)
              ? `<button type="button" class="sr-btn sr-btn-soft sr-btn-sm" data-sr-action="enter-fullscreen">Toàn màn hình</button>`
              : ''
          }
          <button type="button" class="sr-btn sr-btn-primary sr-btn-sm" data-sr-action="ask-submit" ${appState.submitting ? 'disabled' : ''}>
            ${appState.submitting ? 'Đang nộp…' : 'Nộp bài'}
          </button>
        </div>
      </div>
    </header>

    <div class="sr-workspace">
      <main class="sr-main-col">
        ${appState.warningBanner ? `<div class="sr-alert sr-alert-warn">${esc(appState.warningBanner)}</div>` : ''}
        ${appState.error ? `<div class="sr-alert sr-alert-danger">${esc(appState.error)}</div>` : ''}
        ${
          hasChoiceGroups
            ? `<div class="sr-alert sr-alert-info" data-choice-guide="1">
                 <strong>Hướng dẫn làm bài có phần tự chọn:</strong>
                 Chỉ cần làm <strong>Phần chung</strong> + <strong>1 trong các hướng tự chọn</strong> (${choiceGroups.map((g) => `<strong>${esc(formatChoiceGroupLabel(g))}</strong>`).join(', ')}). Nếu làm nhiều hơn 1 hướng, hệ thống tự động tính điểm theo hướng có điểm cao hơn.
               </div>`
            : ''
        }
        ${
          appState.confirmSubmitOpen
            ? `<div class="sr-card" style="border-color:var(--sr-brand, #0f4c81);background:#e8f2fc;">
                 <strong>Xác nhận nộp bài?</strong>
                 <p class="sr-muted" style="margin:6px 0 12px;">
                   Bạn đã trả lời <strong>${answeredCount}/${total}</strong> câu${hasChoiceGroups ? ' (đề có phần tự chọn: chỉ cần làm Phần chung + 1 hướng)' : ''}${appState.flagged.size ? ` · Có ${appState.flagged.size} câu đánh dấu xem lại` : ''}. Sau khi nộp, bài làm sẽ được ghi nhận ngay.
                 </p>
                 <div style="display:flex;gap:8px;flex-wrap:wrap;">
                   <button type="button" class="sr-btn sr-btn-primary" data-sr-action="confirm-submit" ${appState.submitting ? 'disabled' : ''}>Xác nhận nộp bài</button>
                    ${answeredCount < total ? `<button type="button" class="sr-btn sr-btn-soft" data-sr-action="jump-first-unanswered">Chuyển tới câu chưa làm</button>` : ''}
                   <button type="button" class="sr-btn" data-sr-action="cancel-submit">Tiếp tục làm bài</button>
                 </div>
               </div>`
            : ''
        }

        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
          <div style="display:flex;gap:6px;">
            <button type="button" class="sr-btn sr-btn-sm ${appState.viewMode === 'single' ? 'sr-btn-soft' : ''}" data-sr-action="view-mode" data-mode="single">Từng câu</button>
            <button type="button" class="sr-btn sr-btn-sm ${appState.viewMode === 'all' ? 'sr-btn-soft' : ''}" data-sr-action="view-mode" data-mode="all">Tất cả (${total})</button>
          </div>
          ${
            appState.viewMode === 'single' && total > 1
              ? `<div style="display:flex;gap:6px;">
                   <button type="button" class="sr-btn sr-btn-sm" data-sr-action="prev-q" ${appState.currentIndex <= 0 ? 'disabled' : ''}>Câu trước</button>
                   <button type="button" class="sr-btn sr-btn-sm sr-btn-soft" data-sr-action="next-q" ${appState.currentIndex >= total - 1 ? 'disabled' : ''}>Câu tiếp theo</button>
                 </div>`
              : ''
          }
        </div>

        ${
          quoteText
            ? `<div class="sr-passage-box"><strong>Ngữ liệu tham khảo</strong><div style="margin-top:4px;">${esc(quoteText).replace(/\n/g, '<br>')}</div></div>`
            : ''
        }
        ${(() => {
          const examAud = appState.exam?.audio || passageMap.get('exam-listening')?.audio;
          if (!examAud || !examAud.fileId) return '';
          return `<div class="sr-passage-box"><strong>Phần nghe chung của đề thi</strong><div style="margin-top:8px;">${renderAudioCardHTML(examAud)}</div></div>`;
        })()}

        ${shownQuestions}
      </main>

      <aside class="sr-nav-sidebar">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <strong>Danh sách câu hỏi</strong>
          <span class="sr-muted">${answeredCount}/${total}</span>
        </div>
        ${renderNavGridHTML(questions)}
        <div class="sr-muted" style="font-size:12px;">
          Màu xanh: đã trả lời · Chấm cam: đánh dấu xem lại
        </div>
        ${answeredCount < total ? `<button type="button" class="sr-btn sr-btn-soft sr-btn-sm" data-sr-action="jump-first-unanswered" style="width:100%;margin-bottom:8px;">Chuyển tới câu chưa làm</button>` : ''}
        <button type="button" class="sr-btn sr-btn-primary" data-sr-action="ask-submit" ${appState.submitting ? 'disabled' : ''}>
          Nộp bài ngay
        </button>
      </aside>
    </div>

    <div class="sr-mobile-bottom">
      <button type="button" class="sr-btn sr-btn-sm" data-sr-action="prev-q" ${appState.currentIndex <= 0 || appState.viewMode === 'all' ? 'disabled' : ''}>Trước</button>
      <button type="button" class="sr-btn sr-btn-soft sr-btn-sm" data-sr-action="open-mobile-nav">Câu (${answeredCount}/${total})</button>
      <button type="button" class="sr-btn sr-btn-sm" data-sr-action="next-q" ${appState.currentIndex >= total - 1 || appState.viewMode === 'all' ? 'disabled' : ''}>Tiếp</button>
    </div>

    ${
      appState.mobileNavOpen
        ? `<div class="sr-drawer-backdrop" data-sr-action="close-mobile-nav">
             <div class="sr-drawer-panel">
               <div style="display:flex;justify-content:space-between;align-items:center;">
                 <strong>Chọn nhanh câu hỏi</strong>
                 <button type="button" class="sr-btn sr-btn-sm" data-sr-action="close-mobile-nav-btn">Đóng</button>
               </div>
               ${renderNavGridHTML(questions)}
               ${answeredCount < total ? `<button type="button" class="sr-btn sr-btn-soft sr-btn-sm" data-sr-action="jump-first-unanswered" style="width:100%;margin-bottom:8px;">Chuyển tới câu chưa làm</button>` : ''}
               <button type="button" class="sr-btn sr-btn-primary" data-sr-action="ask-submit">Nộp bài (${answeredCount}/${total})</button>
             </div>
           </div>`
        : ''
    }
  `;
}

function formatStudentAnsReview(q) {
  const resp = q.studentResponse;
  if (resp === null || resp === undefined || resp === '') return 'Chưa trả lời';
  if (q.type === 'mcq') {
    const idx = Number(resp);
    if (!Number.isInteger(idx)) return 'Chưa trả lời';
    const letter = String.fromCharCode(65 + idx);
    const optTxt = Array.isArray(q.options) && q.options[idx] !== undefined ? ` — ${q.options[idx]}` : '';
    return `${letter}${optTxt}`;
  }
  if (q.type === 'truefalse') {
    if (!Array.isArray(resp)) return 'Chưa trả lời';
    return resp
      .map((v, i) => `${String.fromCharCode(97 + i)}) ${v === true ? 'Đúng' : v === false ? 'Sai' : '—'}`)
      .join(' · ');
  }
  return String(resp);
}

function formatCorrectAnsReview(q) {
  const corr = q.correctAnswer;
  if (corr === null || corr === undefined || corr === '') return 'Chấm theo biểu điểm tự luận';
  if (q.type === 'mcq') {
    const idx = Number(corr);
    if (!Number.isInteger(idx)) return String(corr);
    const letter = String.fromCharCode(65 + idx);
    const optTxt = Array.isArray(q.options) && q.options[idx] !== undefined ? ` — ${q.options[idx]}` : '';
    return `${letter}${optTxt}`;
  }
  if (q.type === 'truefalse' && Array.isArray(corr)) {
    return corr
      .map((v, i) => `${String.fromCharCode(97 + i)}) ${v ? 'Đúng' : 'Sai'}`)
      .join(' · ');
  }
  return String(corr);
}

export function renderResultReviewSectionHTML(r) {
  if (!r || !r.resultsAvailable) {
    return `<div class="sr-card">
      <p style="margin-top:0;">${esc(r?.message || 'Bài làm của bạn đã được lưu. Điểm và đáp án sẽ hiển thị theo cấu hình của giáo viên.')}</p>
      <button type="button" class="sr-btn sr-btn-soft" data-sr-action="refresh-result">Kiểm tra lại kết quả</button>
    </div>`;
  }
  if (r.resultPolicy === 'score_only') {
    return `<div class="sr-card">
      <p style="margin:0;">Giáo viên chỉ cho phép xem tổng điểm cho phòng thi này.</p>
    </div>`;
  }
  if (!Array.isArray(r.questions) || !r.questions.length) {
    return '';
  }
  return r.questions
    .map((q) => {
      const maxP = Number(q.maxPointsP100 || 0);
      const earned = q.earnedPointsP100;
      const stateCls =
        earned === null || earned === undefined
          ? ''
          : earned >= maxP && maxP > 0
            ? 'is-correct'
            : earned > 0
              ? 'is-partial'
              : 'is-wrong';
      return `
        <div class="sr-rev-item ${stateCls}">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
            <strong>Câu ${esc(q.order)} (${esc(TYPE_LABELS[q.type] || q.type)})${q.choiceGroup ? ` · ${esc(formatChoiceGroupLabel(q.choiceGroup))}` : ''}</strong>
            <span class="sr-q-pts">
              ${earned === null || earned === undefined ? 'Chờ chấm tay' : `${formatPointsVi(earned)} / ${formatPointsVi(maxP)} điểm`}
            </span>
          </div>
          ${q.stem ? `<div style="font-size:14.5px;">${renderRichContent(q.stem, q.richDoc)}</div>` : ''}
          <div style="font-size:13.5px;">
            <strong>Bài làm của bạn:</strong> ${esc(formatStudentAnsReview(q))}
          </div>
          ${
            q.correctAnswer !== undefined && q.correctAnswer !== null
              ? `<div style="font-size:13.5px;color:#065f46;">
                   <strong>Đáp án đúng:</strong> ${esc(formatCorrectAnsReview(q))}
                 </div>`
              : ''
          }
          ${
            q.explanation
              ? `<div class="sr-passage-box" style="margin-top:4px;font-size:13.5px;">
                   <strong>Lời giải / Hướng dẫn:</strong> ${renderRichContent(q.explanation, null)}
                 </div>`
              : ''
          }
          ${
            q.graderNote
              ? `<div style="font-size:13px;color:var(--sr-brand-dark, var(--sr-teal-dark, #0b3a63));"><strong>Nhận xét của giáo viên:</strong> ${esc(q.graderNote)}</div>`
              : ''
          }
        </div>
      `;
    })
    .join('');
}

export function renderResultScreenHTML() {
  const r = appState.result;
  if (!r) return '';

  const synced = Number.isInteger(r.syncedAnswerCount)
    ? r.syncedAnswerCount
    : countLocalAnswered();
  const total = Number.isInteger(r.totalQuestions)
    ? r.totalQuestions
    : (appState.exam?.questions || []).length;
  const localAnswered = Number.isInteger(appState.localAnsweredCount)
    ? appState.localAnsweredCount
    : countLocalAnswered();
  const isLoss = Boolean(r.networkInterrupted) || synced < localAnswered;

  const ungradedEssays = Number.isInteger(r.ungradedEssayCount)
    ? r.ungradedEssayCount
    : Array.isArray(r.questions)
      ? r.questions.filter(
          (q) => q.type === 'essay' && (q.earnedPointsP100 === null || q.earnedPointsP100 === undefined),
        ).length
      : 0;
  const isProvisional = Boolean(
    r.isProvisionalScore || r.gradingStatus === 'needs_manual' || ungradedEssays > 0,
  );
  const scoreHeading = isProvisional ? 'ĐIỂM TẠM (CHỜ CHẤM TỰ LUẬN)' : 'TỔNG ĐIỂM';

  const trackEntries = r.trackScores && typeof r.trackScores === 'object' ? Object.entries(r.trackScores) : [];
  const trackSummaryHTML =
    r.resultsAvailable && (r.chosenTrack || trackEntries.length)
      ? `<div class="sr-card" data-track-summary="1" style="margin:12px 0;padding:12px 16px;background:#f8fbff;border:1px solid #bfdbfe;border-radius:8px;">
           <div style="font-size:13.5px;font-weight:700;color:#0b3a63;">
             ${r.chosenTrack ? `Hướng tự chọn được tính điểm: ${esc(formatChoiceGroupLabel(r.chosenTrack))}` : 'Điểm các hướng tự chọn'}
           </div>
           ${
             trackEntries.length
               ? `<div class="sr-muted" style="margin-top:4px;font-size:13px;">
                    ${trackEntries
                      .map(([grp, info]) => {
                        const sP100 = typeof info === 'object' && info !== null ? info.scoreP100 : info;
                        const maxP100 = typeof info === 'object' && info !== null ? info.maxPointsP100 : null;
                        const scoreStr = maxP100 != null ? `${formatPointsVi(sP100)} / ${formatPointsVi(maxP100)}` : formatPointsVi(sP100);
                        return `${esc(formatChoiceGroupLabel(grp))}: <strong>${esc(scoreStr)} điểm</strong>`;
                      })
                      .join(' · ')}
                  </div>`
               : ''
           }
         </div>`
      : '';

  const syncSummaryText = isLoss
    ? `Đã đồng bộ ${synced}/${localAnswered || total} câu lên máy chủ`
    : synced < total
      ? `Đã đồng bộ đầy đủ ${synced} câu đã trả lời (trên tổng ${total} câu trong đề) lên máy chủ`
      : `Đã đồng bộ đầy đủ ${synced}/${total} câu lên máy chủ`;

  return `
    <div class="sr-result-wrap">
      <div class="sr-score-banner">
        <div>
          <div style="font-size:13px;opacity:0.9;">
            ${esc(appState.roomMeta?.title || 'Kết quả bài làm')}
            ${r.variantCode ? ` · Mã đề ${esc(r.variantCode)}` : ''}
          </div>
          <h1 style="margin:4px 0 6px;font-size:22px;">${esc(r.studentName || appState.attempt?.studentName || 'Thí sinh')}</h1>
          <div style="font-size:13px;opacity:0.9;">
            ${esc(GRADING_STATUS_LABELS[r.gradingStatus] || 'Đã ghi nhận bài làm')}
            ${r.submittedAt ? ` · Nộp lúc ${esc(formatDateTimeVi(r.submittedAt))}` : ''}
          </div>
        </div>
        ${
          r.resultsAvailable
            ? `<div style="text-align:right;">
                 <div style="font-size:12.5px;opacity:0.9;font-weight:700;">${esc(scoreHeading)}</div>
                 <div class="sr-score-big">${esc(formatPointsVi(r.totalScoreP100))} / ${esc(formatPointsVi(r.totalPointsP100))}</div>
                 ${r.manualScoreP100 > 0 || isProvisional ? `<div style="font-size:12px;opacity:0.9;">Trắc nghiệm: ${esc(formatPointsVi(r.autoScoreP100))} · Tự luận: ${esc(formatPointsVi(r.manualScoreP100))}</div>` : ''}
                 ${isProvisional ? `<div style="font-size:12px;opacity:0.95;margin-top:2px;">Còn ${esc(ungradedEssays > 0 ? ungradedEssays : 1)} câu tự luận chưa chấm</div>` : ''}
               </div>`
            : `<span class="sr-room-code-pill" style="color:#0b3a63;">Đã nộp bài an toàn</span>`
        }
      </div>

      ${trackSummaryHTML}

      <div class="sr-card" data-sync-status="${isLoss ? 'loss' : 'ok'}" style="margin:12px 0;padding:12px 16px;background:${isLoss ? '#fffbeb' : '#f0fdf4'};border:1px solid ${isLoss ? '#fde68a' : '#bbf7d0'};border-radius:8px;">
        <div style="font-size:14px;font-weight:600;color:${isLoss ? '#92400e' : '#166534'};">
          ${esc(syncSummaryText)}
        </div>
        ${isLoss ? `<div class="sr-alert sr-alert-warn" style="margin-top:8px;">Cảnh báo: Chỉ có ${esc(synced)}/${esc(localAnswered || total)} câu được ghi nhận trên máy chủ do mất mạng hoặc gián đoạn kết nối trước khi nộp bài.</div>` : ''}
      </div>

      ${appState.warningBanner ? `<div class="sr-alert sr-alert-warn">${esc(appState.warningBanner)}</div>` : ''}

      ${renderResultReviewSectionHTML(r)}

      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button type="button" class="sr-btn" data-sr-action="refresh-result">Làm mới kết quả</button>
        <button type="button" class="sr-btn sr-btn-soft" data-sr-action="back-to-room">Quay lại trang vào phòng</button>
      </div>
    </div>
  `;
}

function renderKaTeX(root) {
  if (!root || typeof window.renderMathInElement !== 'function') return;
  try {
    window.renderMathInElement(root, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\[', right: '\\]', display: true },
        { left: '\\(', right: '\\)', display: false },
      ],
      throwOnError: false,
    });
  } catch {
    // Ignore KaTeX edge parse errors
  }
}

function renderApp() {
  const root = typeof document !== 'undefined' ? document.getElementById(ROOT_ID) : null;
  if (!root) return;
  if (appState.screen === 'lookup') root.innerHTML = renderLookupScreenHTML();
  else if (appState.screen === 'join') root.innerHTML = renderJoinScreenHTML();
  else if (appState.screen === 'exam') root.innerHTML = renderExamScreenHTML();
  else if (appState.screen === 'result') root.innerHTML = renderResultScreenHTML();
  else {
    root.innerHTML = `<div class="sr-center-wrap"><div class="sr-card sr-loading-card">Đang tải phòng thi…</div></div>`;
  }
  renderKaTeX(root);
}

function stopExamTimers() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer);
    autoSaveTimer = null;
  }
  if (periodicBackupTimer) {
    clearInterval(periodicBackupTimer);
    periodicBackupTimer = null;
  }
}

function updateSaveBadge(state, label) {
  appState.saveState = state;
  appState.saveLabel = label;
  const pill = typeof document !== 'undefined' ? document.getElementById('sr-save-pill') : null;
  if (!pill) return;
  pill.className = `sr-save-pill ${state === 'error' ? 'is-err is-offline' : state === 'saved' ? 'is-ok' : ''}`;
  pill.textContent = label;
}

export async function flushAnswers() {
  if (appState.screen !== 'exam' || !appState.attempt?.attemptId || !appState.attemptToken) return;
  updateSaveBadge('saving', 'Đang lưu…');
  try {
    await apiFetch(
      `/api/rooms/public/attempts/${encodeURIComponent(appState.attempt.attemptId)}/answers`,
      {
        method: 'PUT',
        token: appState.attemptToken,
        body: { answers: appState.answers },
      },
    );
    appState.hadNetworkError = false;
    updateSaveBadge('saved', 'Đã đồng bộ');
  } catch (err) {
    if (err.status === 409) {
      await handleLockedOrSubmitted('Bài làm đã được khóa hoặc kết thúc trên máy chủ.');
      return;
    }
    appState.hadNetworkError = true;
    updateSaveBadge('error', 'Mất mạng · đang lưu tạm trên máy');
  }
}

function scheduleAnswerSave() {
  if (appState.attempt?.attemptId) {
    saveDraft(appState.attempt.attemptId, appState.answers, appState.flagged);
  }
  updateSaveBadge('saving', 'Chưa đồng bộ…');
  clearTimeout(autoSaveTimer);
  autoSaveTimer = setTimeout(() => {
    flushAnswers();
  }, 750);
}

async function handleLockedOrSubmitted(bannerMsg = '') {
  stopExamTimers();
  if (!Number.isInteger(appState.localAnsweredCount)) {
    appState.localAnsweredCount = countLocalAnswered();
  }
  if (bannerMsg) appState.warningBanner = bannerMsg;
  await loadResultScreen();
}

async function reportSecurityEvent(eventType, detail = {}) {
  if (appState.screen !== 'exam' || !appState.attempt?.attemptId || !appState.attemptToken) return;
  try {
    const res = await apiFetch(
      `/api/rooms/public/attempts/${encodeURIComponent(appState.attempt.attemptId)}/events`,
      {
        method: 'POST',
        token: appState.attemptToken,
        body: { eventType, detail },
      },
    );
    if (res?.autoLocked) {
      await handleLockedOrSubmitted(
        'Hệ thống đã tự động khóa và thu bài vì vượt quá số lần rời màn hình cho phép.',
      );
    } else if (res?.maxTabSwitches > 0 && (eventType === 'tab_hidden' || eventType === 'window_blur')) {
      appState.warningBanner = `Cảnh báo rời màn hình (${res.tabSwitchCount}/${res.maxTabSwitches}). Quá giới hạn hệ thống sẽ tự thu bài.`;
      const warnEl = document.querySelector('.sr-alert-warn');
      if (warnEl) warnEl.textContent = appState.warningBanner;
      else renderApp();
    }
  } catch (err) {
    if (err.status === 409) {
      await handleLockedOrSubmitted('Phiên làm bài đã kết thúc.');
    }
  }
}

function startExamTimers() {
  stopExamTimers();
  timerInterval = setInterval(() => {
    if (appState.screen !== 'exam' || !appState.attempt) return;
    const expiresAt = appState.attempt.expiresAt;
    if (!expiresAt) return;
    const remMs = Number(expiresAt) - (Date.now() + appState.serverOffsetMs);
    const el = document.getElementById('sr-timer');
    if (el) {
      el.textContent = formatCountdown(remMs);
      el.className = `sr-timer ${remMs <= 60000 ? 'is-urgent' : remMs <= 300000 ? 'is-warn' : ''}`;
    }
    if (remMs <= 0 && !appState.submitting) {
      submitAttempt({ autoSubmit: true });
    }
  }, 1000);

  periodicBackupTimer = setInterval(() => {
    if (appState.screen === 'exam') {
      flushAnswers();
    }
  }, 25000);
}

export async function submitAttempt({ autoSubmit = false } = {}) {
  if (appState.submitting || !appState.attempt?.attemptId) return;
  appState.submitting = true;
  appState.confirmSubmitOpen = false;
  appState.localAnsweredCount = countLocalAnswered();
  clearTimeout(autoSaveTimer);
  renderApp();
  try {
    await apiFetch(
      `/api/rooms/public/attempts/${encodeURIComponent(appState.attempt.attemptId)}/submit`,
      {
        method: 'POST',
        token: appState.attemptToken,
        body: { answers: appState.answers, autoSubmit },
      },
    );
    appState.hadNetworkError = false;
    updateSaveBadge('saved', 'Đã đồng bộ');
    stopExamTimers();
    if (typeof document !== 'undefined' && document.fullscreenElement && document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    }
    await loadResultScreen();
  } catch (err) {
    appState.error = err.message || 'Không thể nộp bài. Vui lòng thử lại ngay.';
    if (err.status === 409) {
      await loadResultScreen();
      return;
    }
    appState.hadNetworkError = true;
    updateSaveBadge('error', 'Mất mạng · đang lưu tạm trên máy');
    appState.submitting = false;
    renderApp();
  }
}

async function loadResultScreen() {
  stopExamTimers();
  appState.submitting = false;
  appState.screen = 'result';
  appState.error = '';
  try {
    appState.result = await apiFetch(
      `/api/rooms/public/attempts/${encodeURIComponent(appState.attempt.attemptId)}/result`,
      { token: appState.attemptToken },
    );
  } catch (err) {
    appState.error = err.message || 'Không tải được kết quả bài làm.';
  }
  renderApp();
}

async function resumeAttemptByToken(attemptId, attemptToken) {
  const data = await apiFetch(`/api/rooms/public/attempts/${encodeURIComponent(attemptId)}`, {
    token: attemptToken,
  });
  appState.attemptToken = attemptToken;
  appState.roomMeta = data.room;
  appState.roomCode = data.room?.roomCode || appState.roomCode;
  appState.attempt = {
    attemptId: data.attemptId,
    attemptNo: data.attemptNo,
    variantCode: data.variantCode,
    status: data.status,
    startedAt: data.startedAt,
    expiresAt: data.expiresAt,
    submittedAt: data.submittedAt,
    studentName: data.studentName,
    studentCode: data.studentCode,
    studentClass: data.studentClass,
  };
  appState.exam = data.exam;
  const serverAns = data.answers && typeof data.answers === 'object' ? { ...data.answers } : {};
  const draft = loadSavedDraft(data.attemptId);
  if (draft?.answers && data.status === 'in_progress') {
    appState.answers = { ...serverAns, ...draft.answers };
    appState.flagged = new Set(Array.isArray(draft.flagged) ? draft.flagged : []);
  } else {
    appState.answers = serverAns;
    appState.flagged = new Set();
  }
  initAudioEntries();

  if (data.status !== 'in_progress') {
    await loadResultScreen();
    return;
  }
  appState.screen = 'exam';
  appState.currentIndex = 0;
  appState.hadNetworkError = false;
  appState.localAnsweredCount = null;
  appState.error = '';
  appState.warningBanner = '';
  updateSaveBadge('saved', 'Đã đồng bộ');
  renderApp();
  startExamTimers();
  reportSecurityEvent('reconnect', { source: 'resume' });
}

async function openRoomByCode(code) {
  const cleanCode = String(code || '').trim().toUpperCase();
  if (!cleanCode) {
    appState.screen = 'lookup';
    renderApp();
    return;
  }
  appState.roomCode = cleanCode;
  appState.error = '';
  appState.warningBanner = '';
  appState.resumeOffer = null;
  try {
    appState.roomMeta = await apiFetch(`/api/rooms/public/${encodeURIComponent(cleanCode)}`);
    const saved = loadSavedSession(cleanCode);
    if (saved?.attemptId && saved?.attemptToken) {
      try {
        await resumeAttemptByToken(saved.attemptId, saved.attemptToken);
        return;
      } catch {
        clearSavedSession(cleanCode);
      }
    }
    appState.screen = 'join';
  } catch (err) {
    appState.roomMeta = null;
    appState.screen = 'lookup';
    appState.error = err.message || 'Không tìm thấy phòng thi với mã vừa nhập.';
  }
  renderApp();
}

export async function handleAudioPlay(fileId) {
  const st = appState.audioState[fileId];
  if (!st || st.loading || st.playsRemaining <= 0 || !appState.attempt?.attemptId) return;
  st.loading = true;
  st.error = '';
  renderApp();
  try {
    const res = await fetch(
      st.url || `/api/rooms/public/attempts/${encodeURIComponent(appState.attempt.attemptId)}/audio/${encodeURIComponent(fileId)}`,
      {
        method: 'GET',
        headers: { 'X-Attempt-Token': appState.attemptToken },
      },
    );
    if (!res.ok) {
      let msg = 'Không thể tải tệp âm thanh.';
      try {
        const j = await res.json();
        msg = j?.detail || msg;
      } catch {
        // Ignore parse failure
      }
      if (res.status === 403) st.playsRemaining = 0;
      throw new Error(msg);
    }
    const usedH = res.headers.get('X-Audio-Plays-Used');
    const remH = res.headers.get('X-Audio-Plays-Remaining');
    const maxH = res.headers.get('X-Audio-Max-Plays');
    if (usedH !== null) st.playsUsed = Number(usedH);
    if (remH !== null) st.playsRemaining = Number(remH);
    if (maxH !== null) st.maxPlays = Number(maxH);
    const blob = await res.blob();
    if (st.blobUrl) {
      try {
        URL.revokeObjectURL(st.blobUrl);
      } catch {
        // Ignore
      }
    }
    st.blobUrl = URL.createObjectURL(blob);
    st.activePlayback = true;
  } catch (err) {
    st.activePlayback = false;
    st.error = err.message || 'Không tải được âm thanh.';
  } finally {
    st.loading = false;
    renderApp();
  }
}

function syncExamProgressUI(qid) {
  const questions = appState.exam?.questions || [];
  const total = questions.length;
  const answeredCount = questions.filter(isQuestionAnswered).length;
  const subEl = document.querySelector('.sr-header-sub');
  if (subEl && appState.attempt) {
    subEl.textContent = `${appState.attempt.studentName || ''}${appState.attempt.variantCode ? ` · Mã đề ${appState.attempt.variantCode}` : ''} · Đã làm ${answeredCount}/${total} câu`;
  }
  const mobBtn = document.querySelector('[data-sr-action="open-mobile-nav"]');
  if (mobBtn) mobBtn.textContent = `Câu (${answeredCount}/${total})`;
  const sideCnt = document.querySelector('.sr-nav-sidebar .sr-muted');
  if (sideCnt) sideCnt.textContent = `${answeredCount}/${total}`;

  const qIdx = questions.findIndex((item) => item.id === qid);
  if (qIdx >= 0) {
    const q = questions[qIdx];
    const answered = isQuestionAnswered(q);
    const flagged = appState.flagged.has(q.id);
    document.querySelectorAll(`[data-sr-action="jump-q"][data-idx="${qIdx}"]`).forEach((el) => {
      el.classList.toggle('is-answered', answered);
      el.classList.toggle('is-flagged', flagged);
    });
  }
}

function bindGlobalListeners() {
  if (listenersBound) return;
  listenersBound = true;
  const root = document.getElementById(ROOT_ID);
  if (!root) return;

  root.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('[data-sr-action]');
    if (!btn) return;
    const action = btn.dataset.srAction;

    if (action === 'switch-code') {
      appState.roomMeta = null;
      appState.error = '';
      appState.screen = 'lookup';
      history.replaceState({}, '', '/phong-thi');
      renderApp();
      return;
    }

    if (action === 'resume-saved' && appState.resumeOffer) {
      await resumeAttemptByToken(appState.resumeOffer.attemptId, appState.resumeOffer.attemptToken);
      return;
    }

    if (action === 'discard-saved') {
      clearSavedSession(appState.roomCode);
      appState.resumeOffer = null;
      renderApp();
      return;
    }

    if (action === 'pick-mcq') {
      const qid = btn.dataset.qid;
      const idx = Number(btn.dataset.idx);
      if (!qid || !Number.isInteger(idx)) return;
      appState.answers[qid] = idx;
      scheduleAnswerSave();
      const card = btn.closest('[data-q-card]');
      if (card) {
        card.querySelectorAll('[data-sr-action="pick-mcq"]').forEach((optBtn) => {
          const sel = Number(optBtn.dataset.idx) === idx;
          optBtn.classList.toggle('is-selected', sel);
          optBtn.setAttribute('aria-pressed', String(sel));
        });
        syncExamProgressUI(qid);
      } else {
        renderApp();
      }
      return;
    }

    if (action === 'pick-tf') {
      const qid = btn.dataset.qid;
      const row = Number(btn.dataset.row);
      const val = btn.dataset.val === 'true';
      if (!qid || !Number.isInteger(row) || row < 0 || row > 3) return;
      const prev = Array.isArray(appState.answers[qid])
        ? [...appState.answers[qid]]
        : [null, null, null, null];
      while (prev.length < 4) prev.push(null);
      prev[row] = prev[row] === val ? null : val;
      appState.answers[qid] = prev;
      scheduleAnswerSave();
      const tfRow = btn.closest('.sr-tf-row');
      if (tfRow) {
        tfRow.querySelectorAll('[data-sr-action="pick-tf"]').forEach((b) => {
          const bVal = b.dataset.val === 'true';
          b.classList.toggle('is-true', bVal && prev[row] === true);
          b.classList.toggle('is-false', !bVal && prev[row] === false);
          b.setAttribute('aria-pressed', String(prev[row] === bVal));
        });
        syncExamProgressUI(qid);
      } else {
        renderApp();
      }
      return;
    }

    if (action === 'toggle-flag') {
      const qid = btn.dataset.qid;
      if (!qid) return;
      if (appState.flagged.has(qid)) appState.flagged.delete(qid);
      else appState.flagged.add(qid);
      if (appState.attempt?.attemptId) {
        saveDraft(appState.attempt.attemptId, appState.answers, appState.flagged);
      }
      const isFlagged = appState.flagged.has(qid);
      btn.classList.toggle('is-flagged', isFlagged);
      btn.setAttribute('aria-pressed', String(isFlagged));
      btn.textContent = isFlagged ? 'Đã đánh dấu xem lại' : 'Đánh dấu xem lại';
      syncExamProgressUI(qid);
      return;
    }

    if (action === 'jump-q') {
      const idx = Number(btn.dataset.idx);
      const total = (appState.exam?.questions || []).length;
      if (!Number.isInteger(idx) || idx < 0 || idx >= total) return;
      appState.currentIndex = idx;
      appState.mobileNavOpen = false;
      renderApp();
      if (appState.viewMode === 'all') {
        const q = appState.exam.questions[idx];
        document.querySelector(`[data-q-card="${q.id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      return;
    }

    if (action === 'prev-q') {
      if (appState.currentIndex > 0) {
        appState.currentIndex -= 1;
        renderApp();
      }
      return;
    }

    if (action === 'next-q') {
      const total = (appState.exam?.questions || []).length;
      if (appState.currentIndex < total - 1) {
        appState.currentIndex += 1;
        renderApp();
      }
      return;
    }

    if (action === 'view-mode') {
      appState.viewMode = btn.dataset.mode === 'all' ? 'all' : 'single';
      renderApp();
      return;
    }

    if (action === 'open-mobile-nav') {
      appState.mobileNavOpen = true;
      renderApp();
      return;
    }

    if (action === 'close-mobile-nav') {
      if (ev.target.closest('.sr-drawer-panel')) return;
      appState.mobileNavOpen = false;
      renderApp();
      return;
    }

    if (action === 'close-mobile-nav-btn') {
      appState.mobileNavOpen = false;
      renderApp();
      return;
    }

    if (action === 'enter-fullscreen') {
      if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(() => {});
      }
      return;
    }

    if (action === 'ask-submit') {
      appState.mobileNavOpen = false;
      appState.confirmSubmitOpen = true;
      renderApp();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    if (action === 'cancel-submit') {
      appState.confirmSubmitOpen = false;
      renderApp();
      return;
    }

    if (action === 'jump-first-unanswered') {
      const questions = appState.exam?.questions || [];
      const idx = questions.findIndex((q) => !isQuestionAnswered(q));
      if (idx >= 0) {
        appState.currentIndex = idx;
        appState.confirmSubmitOpen = false;
        appState.mobileNavOpen = false;
        renderApp();
        if (appState.viewMode === 'all') {
          const card = document.querySelector(`[data-q-card="${esc(questions[idx].id)}"]`);
          if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
      return;
    }

    if (action === 'confirm-submit') {
      await submitAttempt({ autoSubmit: false });
      return;
    }

    if (action === 'play-audio') {
      await handleAudioPlay(btn.dataset.fileId || '');
      return;
    }

    if (action === 'refresh-result') {
      await loadResultScreen();
      return;
    }

    if (action === 'back-to-room') {
      clearSavedSession(appState.roomCode);
      revokeAllAudioBlobs();
      appState.attempt = null;
      appState.attemptToken = '';
      appState.result = null;
      appState.hadNetworkError = false;
      appState.localAnsweredCount = null;
      await openRoomByCode(appState.roomCode);
    }
  });

  root.addEventListener('input', (ev) => {
    const t = ev.target;
    if (t.classList.contains('sr-short-input') || t.classList.contains('sr-essay-input')) {
      const qid = t.dataset.qid;
      if (!qid) return;
      appState.answers[qid] = t.value;
      const wc = root.querySelector(`[data-word-count="${qid}"]`);
      if (wc) {
        const cnt = t.value.trim() ? t.value.trim().split(/\s+/).length : 0;
        wc.textContent = `${cnt} từ`;
      }
      scheduleAnswerSave();
    }
  });

  root.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    if (form.id === 'sr-lookup-form') {
      const fd = new FormData(form);
      const code = String(fd.get('roomCode') || '').trim().toUpperCase();
      if (!code) return;
      history.replaceState({}, '', `/phong-thi/${encodeURIComponent(code)}`);
      await openRoomByCode(code);
      return;
    }

    if (form.id === 'sr-join-form') {
      appState.error = '';
      const fd = new FormData(form);
      const payload = {
        studentName: String(fd.get('studentName') || '').trim(),
        studentClass: String(fd.get('studentClass') || '').trim(),
        studentCode: String(fd.get('studentCode') || '').trim(),
        pin: String(fd.get('pin') || '').trim(),
      };
      try {
        const joined = await apiFetch(
          `/api/rooms/public/${encodeURIComponent(appState.roomCode)}/join`,
          { method: 'POST', body: payload },
        );
        appState.attemptToken = joined.attemptToken;
        appState.roomMeta = joined.room;
        appState.attempt = {
          attemptId: joined.attemptId,
          attemptNo: joined.attemptNo,
          variantCode: joined.variantCode,
          status: joined.status,
          startedAt: joined.startedAt,
          expiresAt: joined.expiresAt,
          studentName: joined.studentName,
          studentCode: joined.studentCode,
          studentClass: joined.studentClass,
        };
        appState.exam = joined.exam;
        appState.answers = joined.answers && typeof joined.answers === 'object' ? { ...joined.answers } : {};
        appState.flagged = new Set();
        appState.currentIndex = 0;
        appState.confirmSubmitOpen = false;
        appState.hadNetworkError = false;
        appState.localAnsweredCount = null;
        initAudioEntries();
        updateSaveBadge('saved', 'Đã đồng bộ');
        saveSession(appState.roomCode, {
          attemptId: joined.attemptId,
          attemptToken: joined.attemptToken,
          studentName: joined.studentName,
        });
        if (joined.room?.requireFullscreen && document.documentElement.requestFullscreen) {
          document.documentElement.requestFullscreen().catch(() => {});
        }
        appState.screen = 'exam';
        renderApp();
        startExamTimers();
      } catch (err) {
        appState.error = err.message || 'Không thể vào phòng thi.';
        renderApp();
      }
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (appState.screen !== 'exam' || appState.attempt?.status !== 'in_progress') return;
    if (document.visibilityState === 'hidden') {
      lastVisibilityBlurAt = Date.now();
      reportSecurityEvent('tab_hidden', { at: Date.now() });
    }
  });

  window.addEventListener('blur', () => {
    if (appState.screen !== 'exam' || appState.attempt?.status !== 'in_progress') return;
    const now = Date.now();
    if (now - lastVisibilityBlurAt < 1200) return;
    lastVisibilityBlurAt = now;
    reportSecurityEvent('window_blur', { at: now });
  });

  document.addEventListener('fullscreenchange', () => {
    if (appState.screen !== 'exam' || appState.attempt?.status !== 'in_progress') return;
    if (appState.roomMeta?.requireFullscreen && !document.fullscreenElement) {
      reportSecurityEvent('fullscreen_exit', { at: Date.now() });
      renderApp();
    }
  });

  document.addEventListener('copy', () => {
    if (appState.screen !== 'exam' || appState.attempt?.status !== 'in_progress') return;
    const now = Date.now();
    if (now - lastCopyEventAt < 4000) return;
    lastCopyEventAt = now;
    reportSecurityEvent('copy_attempt', { at: now });
  });

  document.addEventListener(
    'play',
    (e) => {
      const audio = e.target;
      if (audio && (audio.matches?.('audio, .sr-audio-el') || audio.tagName === 'AUDIO')) {
        const card = audio.closest?.('[data-audio-box]');
        const fid = card?.dataset?.audioBox;
        const st = fid ? appState.audioState[fid] : null;
        if (st && st.playsRemaining <= 0 && !st.activePlayback) {
          e.preventDefault();
          e.stopPropagation();
          audio.pause();
          audio.currentTime = 0;
          lockExhaustedAudio(audio, st);
        }
      }
    },
    true,
  );

  document.addEventListener(
    'keydown',
    (e) => {
      if (e.key === ' ' || e.code === 'Space' || e.key === 'Enter') {
        const target = e.target;
        const audioCard = target?.closest?.('[data-audio-box]');
        if (audioCard) {
          const fid = audioCard.dataset?.audioBox;
          const st = fid ? appState.audioState[fid] : null;
          if (st && st.playsRemaining <= 0 && !st.activePlayback) {
            e.preventDefault();
            e.stopPropagation();
            const aud = audioCard.querySelector('audio');
            if (aud) {
              aud.pause();
              aud.currentTime = 0;
              lockExhaustedAudio(aud, st);
            }
          }
        }
      }
    },
    true,
  );

  document.addEventListener(
    'ended',
    (e) => {
      const audio = e.target;
      if (audio && (audio.matches?.('audio, .sr-audio-el') || audio.tagName === 'AUDIO')) {
        const card = audio.closest?.('[data-audio-box]');
        const fid = card?.dataset?.audioBox;
        const st = fid ? appState.audioState[fid] : null;
        if (st) {
          st.activePlayback = false;
          audio.pause();
          audio.currentTime = 0;
          lockExhaustedAudio(audio, st);
          renderApp();
        }
      }
    },
    true,
  );

  window.addEventListener('offline', () => {
    if (appState.screen === 'exam') {
      appState.hadNetworkError = true;
      updateSaveBadge('error', 'Mất mạng · đang lưu tạm trên máy');
    }
  });

  window.addEventListener('online', () => {
    if (appState.screen === 'exam') {
      flushAnswers();
    }
  });

  window.addEventListener('load', () => {
    const rootEl = document.getElementById(ROOT_ID);
    if (rootEl) renderKaTeX(rootEl);
  });
}

async function bootstrap() {
  bindGlobalListeners();
  const code = extractRoomCodeFromPath();
  if (code) {
    await openRoomByCode(code);
  } else {
    appState.screen = 'lookup';
    renderApp();
  }
}

export { appState, bindGlobalListeners, lockExhaustedAudio, updateSaveBadge };

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  bootstrap();
}
