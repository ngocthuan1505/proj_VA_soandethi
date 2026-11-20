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

 if (kind === 'passage') {
  const pastedRefs = Array.isArray(options?.pastedRefs) ? options.pastedRefs.filter(Boolean) : [];
  const sameIdRefs = pastedRefs.filter(ref => ref.sourceId === sourceId && ref.locator?.kind === 'passage');
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
    label: `Nguồn của lượt sinh · Đoạn ${index}`,
    contextHtml: '',
    notice: `Nguồn gốc không còn trong đề hoặc phiên soạn (đã bị gỡ hoặc thay thế); trích dẫn đã lưu ở bản v${sourceVersion} vẫn được giữ để truy vết.`,
   };
  }

  const sameVersionRefs = sameIdRefs.filter(ref => (ref.sourceVersion ?? 1) === sourceVersion);
  const refForLabel = sameVersionRefs[0] || sameIdRefs[0];
  const pastedName = String(refForLabel.name ?? options?.pastedName ?? '').trim() || 'Ngữ liệu đã dán';
  const label = `${pastedName} · Đoạn ${index}`;

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
 if (!doc) {
  const unit = kind === 'region' ? 'Vùng ' : 'Trang ';
  return {
   status: 'source_missing',
   canOpen: false,
   hasSourceDoc: false,
   sourceId,
   sourceVersion,
   currentVersion: null,
   locator,
   quote,
   label: `Nguồn của lượt sinh · ${unit}${index}`,
   contextHtml: '',
   notice: `Nguồn gốc không còn trong đề (đã bị gỡ hoặc thay thế); trích dẫn đã lưu ở bản v${sourceVersion} vẫn được giữ để truy vết.`,
  };
 }

 const docName = String(doc.name ?? '').trim() || 'Tài liệu nguồn';
 const locationLabel = kind === 'page' ? sourcePageLabel(doc, index) : `Vùng ${index}`;
 const label = `${docName} · ${locationLabel}`;
 const currentVersion = doc.version || 1;

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
