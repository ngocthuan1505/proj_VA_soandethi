import {esc} from './core.js';
import {documentPages, sourcePageLabel} from './assistant-sources.js';

export function normalizeCitationText(text) {
 return String(text ?? '').trim().replace(/\s+/g, ' ');
}

function findQuoteRange(content, quote) {
 const text = String(content ?? '');
 const rawQuote = String(quote ?? '');
 const normalizedQuote = normalizeCitationText(rawQuote);
 if (!text || !normalizedQuote) return null;

 const exactStart = rawQuote ? text.indexOf(rawQuote) : -1;
 if (exactStart >= 0) return {start: exactStart, end: exactStart + rawQuote.length};

 const trimmedQuote = rawQuote.trim();
 const trimmedStart = trimmedQuote ? text.indexOf(trimmedQuote) : -1;
 if (trimmedStart >= 0) return {start: trimmedStart, end: trimmedStart + trimmedQuote.length};

 let normalized = '';
 const startMap = [];
 const endMap = [];
 let i = 0;
 while (i < text.length && /\s/.test(text[i])) i++;
 while (i < text.length) {
  if (/\s/.test(text[i])) {
   const wsStart = i;
   while (i < text.length && /\s/.test(text[i])) i++;
   if (i < text.length) {
    normalized += ' ';
    startMap.push(wsStart);
    endMap.push(i);
   }
  } else {
   normalized += text[i];
   startMap.push(i);
   endMap.push(i + 1);
   i++;
  }
 }

 const matchIndex = normalized.indexOf(normalizedQuote);
 if (matchIndex < 0) return null;
 return {
  start: startMap[matchIndex],
  end: endMap[matchIndex + normalizedQuote.length - 1],
 };
}

function highlightContextHTML(content, range) {
 const text = String(content ?? '');
 if (!range) return esc(text);
 return `${esc(text.slice(0, range.start))}<mark>${esc(text.slice(range.start, range.end))}</mark>${esc(text.slice(range.end))}`;
}

function detectStaleNotice(evidence, options, quote, sourceId, kind, index) {
 if (evidence?.stale === true) {
  if (evidence?.staleReason === 'quote_variant_changed') {
   return 'Câu hỏi đã chuyển sang bản ngữ liệu hoặc nguồn mới; trích dẫn của lượt sinh trước được giữ lại để đối chiếu lịch sử.';
  }
  return 'Trích dẫn này đã lỗi thời so với nội dung hoặc nguồn hiện tại của câu hỏi.';
 }
 if (options && 'currentSource' in options) {
  const cur = options.currentSource;
  if (cur === null) {
   return 'Câu hỏi không còn gắn với tài liệu nguồn của trích dẫn này.';
  }
  if (cur && typeof cur === 'object') {
   if (('docId' in cur && cur.docId === null && sourceId) || (cur.docId !== undefined && cur.docId !== sourceId)) {
    return 'Nguồn gắn với câu hỏi hiện tại đã đổi sang tài liệu khác với trích dẫn đã lưu.';
   }
   if (kind === 'page' && cur.page != null && cur.page !== '' && Number(cur.page) !== Number(index)) {
    return 'Trang nguồn gắn với câu hỏi đã thay đổi so với trích dẫn đã lưu.';
   }
  }
 }
 if (evidence?.questionVersion != null && options?.questionVersion != null && Number(evidence.questionVersion) !== Number(options.questionVersion)) {
  return 'Câu hỏi đã được chỉnh sửa sang phiên bản mới; trích dẫn cũ chỉ giữ lại để đối chiếu.';
 }
 if (typeof options?.currentQuoteText === 'string') {
  const curQuote = normalizeCitationText(options.currentQuoteText);
  const evQuote = normalizeCitationText(quote);
  if (!curQuote || (evQuote && !curQuote.includes(evQuote))) {
   return 'Ngữ liệu hiện tại của câu hỏi không còn chứa đoạn trích dẫn đã lưu.';
  }
 }
 return '';
}

export function resolveCitationContext(evidence, docs = [], options = {}) {
 const docList = Array.isArray(docs) ? docs.filter(Boolean) : [];
 const sourceId = String(evidence?.sourceId ?? '');
 const sourceVersion = evidence?.sourceVersion ?? 1;
 const rawLocator = evidence?.locator && typeof evidence.locator === 'object' ? evidence.locator : {};
 const kind = rawLocator.kind || 'page';
 const index = rawLocator.index ?? 1;
 const locator = {
  kind,
  index,
  ...(rawLocator.regionId !== undefined ? {regionId: rawLocator.regionId} : {}),
 };
 const quote = String(evidence?.quote ?? '');
 const staleNotice = detectStaleNotice(evidence, options, quote, sourceId, kind, index);

 if (kind === 'passage') {
  const pastedRefs = Array.isArray(options?.pastedRefs) ? options.pastedRefs.filter(Boolean) : [];
  const sameIdRefs = pastedRefs.filter(ref => ref.sourceId === sourceId && ref.locator?.kind === 'passage');
  const sameVersionRefs = sameIdRefs.filter(ref => (ref.sourceVersion ?? 1) === sourceVersion);
  const refForLabel = sameVersionRefs[0] || sameIdRefs[0];
  const pastedName = String(refForLabel?.name ?? options?.pastedName ?? '').trim() || 'Ngữ liệu đã dán';
  const label = refForLabel ? `${pastedName} · Đoạn ${index}` : `Nguồn của lượt sinh · Đoạn ${index}`;

  if (staleNotice) {
   return {
    status: 'stale',
    canOpen: false,
    hasSourceDoc: false,
    sourceId,
    sourceVersion,
    currentVersion: refForLabel ? (refForLabel.sourceVersion ?? 1) : null,
    locator,
    quote,
    label,
    contextHtml: '',
    notice: staleNotice,
   };
  }

  if (!sameIdRefs.length) {
   return {
    status: 'source_missing',
    canOpen: false,
    hasSourceDoc: false,
    sourceId,
    sourceVersion,
    currentVersion: null,
    locator,
    quote,
    label,
    contextHtml: '',
    notice: `Nguồn gốc không còn trong đề hoặc phiên soạn (đã bị gỡ hoặc thay thế); trích dẫn đã lưu ở bản v${sourceVersion} vẫn được giữ để truy vết.`,
   };
  }

  if (!sameVersionRefs.length) {
   const currentVersion = refForLabel.sourceVersion ?? 1;
   return {
    status: 'version_changed',
    canOpen: false,
    hasSourceDoc: false,
    sourceId,
    sourceVersion,
    currentVersion,
    locator,
    quote,
    label,
    contextHtml: '',
    notice: `Nguồn đã cập nhật từ bản v${sourceVersion} sang bản v${currentVersion}; không tự mở sai phiên bản. Trích dẫn đã lưu vẫn được giữ để đối chiếu.`,
   };
  }

  const matchedRef = sameVersionRefs.find(ref => ref.locator?.index === index) || null;
  const content = matchedRef
   ? (typeof matchedRef.text === 'string' ? matchedRef.text : String(options?.pastedText ?? ''))
   : '';
  const range = matchedRef ? findQuoteRange(content, quote) : null;
  if (!range) {
   return {
    status: 'quote_mismatch',
    canOpen: false,
    hasSourceDoc: false,
    sourceId,
    sourceVersion,
    currentVersion: sourceVersion,
    locator,
    quote,
    label,
    contextHtml: '',
    notice: matchedRef
     ? `Không khớp nguyên văn đoạn trích trong ${label} ở bản v${sourceVersion}.`
     : `Vị trí Đoạn ${index} không còn hoặc không khớp nguyên văn đoạn trích ở bản v${sourceVersion}.`,
   };
  }

  return {
   status: 'matched',
   canOpen: true,
   hasSourceDoc: false,
   sourceId,
   sourceVersion,
   currentVersion: sourceVersion,
   locator,
   quote,
   label,
   contextHtml: highlightContextHTML(content, range),
   notice: '',
  };
 }

 const doc = docList.find(item => item.id === sourceId) || null;
 const unit = kind === 'region' ? 'Vùng ' : 'Trang ';
 const docName = doc ? (String(doc.name ?? '').trim() || 'Tài liệu nguồn') : '';
 const locationLabel = doc ? (kind === 'page' ? sourcePageLabel(doc, index) : `Vùng ${index}`) : `${unit}${index}`;
 const label = doc ? `${docName} · ${locationLabel}` : `Nguồn của lượt sinh · ${unit}${index}`;
 const currentVersion = doc ? (doc.version || 1) : null;

 if (staleNotice) {
  return {
   status: 'stale',
   canOpen: false,
   hasSourceDoc: Boolean(doc),
   sourceId,
   sourceVersion,
   currentVersion,
   locator,
   quote,
   label,
   contextHtml: '',
   notice: staleNotice,
  };
 }

 if (!doc) {
  return {
   status: 'source_missing',
   canOpen: false,
   hasSourceDoc: false,
   sourceId,
   sourceVersion,
   currentVersion: null,
   locator,
   quote,
   label,
   contextHtml: '',
   notice: `Nguồn gốc không còn trong đề (đã bị gỡ hoặc thay thế); trích dẫn đã lưu ở bản v${sourceVersion} vẫn được giữ để truy vết.`,
  };
 }

 if (currentVersion !== sourceVersion) {
  return {
   status: 'version_changed',
   canOpen: false,
   hasSourceDoc: true,
   sourceId,
   sourceVersion,
   currentVersion,
   locator,
   quote,
   label,
   contextHtml: '',
   notice: `Nguồn đã cập nhật từ bản v${sourceVersion} sang bản v${currentVersion}; không tự mở sai phiên bản. Trích dẫn đã lưu vẫn được giữ để đối chiếu.`,
  };
 }

 if (kind !== 'page') {
  return {
   status: 'quote_mismatch',
   canOpen: false,
   hasSourceDoc: true,
   sourceId,
   sourceVersion,
   currentVersion,
   locator,
   quote,
   label,
   contextHtml: '',
   notice: `Không khớp nguyên văn đoạn trích tại ${locationLabel} ở bản v${sourceVersion}.`,
  };
 }

 const page = documentPages(doc).find(item => item && item.number === index) || null;
 const content = typeof page?.text === 'string' ? page.text : '';
 const range = page ? findQuoteRange(content, quote) : null;
 if (!range) {
  return {
   status: 'quote_mismatch',
   canOpen: false,
   hasSourceDoc: true,
   sourceId,
   sourceVersion,
   currentVersion,
   locator,
   quote,
   label,
   contextHtml: '',
   notice: page
    ? `Không khớp nguyên văn đoạn trích trong ${locationLabel} ở bản v${sourceVersion}.`
    : `Không tìm thấy ${locationLabel} hoặc trang đã thay đổi nên không khớp nguyên văn đoạn trích ở bản v${sourceVersion}.`,
  };
 }

 return {
  status: 'matched',
  canOpen: true,
  hasSourceDoc: true,
  sourceId,
  sourceVersion,
  currentVersion,
  locator,
  quote,
  label,
  contextHtml: highlightContextHTML(content, range),
  notice: '',
 };
}

export function citationContextHTML(evidence, docs = [], options = {}) {
 const resolved = resolveCitationContext(evidence, docs, options);
 const quoteBlock = `<blockquote>“${esc(resolved.quote)}”<br><small title="${esc(resolved.sourceId)}">${esc(resolved.label)} · Bản ${esc(resolved.sourceVersion)}</small></blockquote>`;
 if (resolved.status === 'matched') {
  return `${quoteBlock}<details class="matrix-evidence-source"><summary>Mở ngữ cảnh · ${esc(resolved.label)}</summary><blockquote>${resolved.contextHtml}</blockquote></details>`;
 }
 return `${quoteBlock}<p class="hint" data-citation-status="${esc(resolved.status)}">${esc(resolved.notice)}</p>`;
}
