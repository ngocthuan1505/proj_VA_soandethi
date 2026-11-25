import {test} from 'node:test';
import assert from 'node:assert/strict';
import {citationContextHTML, normalizeCitationText, resolveCitationContext} from '../citation-context.js';
import {checkEvidenceHTML} from '../question-check.js';

const DOC_ID = '11111111-2222-4333-8444-555555555555';
const OTHER_DOC_ID = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const PASSAGE_ID = '99999999-8888-4777-8666-555555555555';

test('Khớp đúng UUID, đúng phiên bản và đúng trang: mở ngữ cảnh với <mark> và đúng cấu trúc details', () => {
 const source = 'Mai mở cửa thư viện. Nam xếp sách lên kệ. Cô giáo ghi nhận việc giúp đỡ của hai bạn.';
 const docs = [{
  id: DOC_ID,
  name: 'Nguồn fixture tự viết',
  kind: 'text',
  version: 3,
  text: source,
  pages: [
   {number: 1, text: 'Trang ngoài phạm vi này không được gửi.'},
   {number: 2, text: source},
  ],
 }];
 const evidence = {
  sourceId: DOC_ID,
  sourceVersion: 3,
  locator: {kind: 'page', index: 2},
  quote: 'Nam xếp sách lên kệ.',
 };

 const resolved = resolveCitationContext(evidence, docs);
 assert.equal(resolved.status, 'matched');
 assert.equal(resolved.canOpen, true);
 assert.equal(resolved.hasSourceDoc, true);
 assert.equal(resolved.currentVersion, 3);
 assert.equal(resolved.label, 'Nguồn fixture tự viết · Trang 2');
 assert.equal(
  resolved.contextHtml,
  'Mai mở cửa thư viện. <mark>Nam xếp sách lên kệ.</mark> Cô giáo ghi nhận việc giúp đỡ của hai bạn.',
 );
 assert.equal(resolved.notice, '');

 const html = citationContextHTML(evidence, docs);
 assert(html.includes(`<blockquote>“Nam xếp sách lên kệ.”<br><small title="${DOC_ID}">Nguồn fixture tự viết · Trang 2 · Bản 3</small></blockquote>`));
 assert(html.includes('<details class="matrix-evidence-source"><summary>Mở ngữ cảnh · Nguồn fixture tự viết · Trang 2</summary><blockquote>Mai mở cửa thư viện. <mark>Nam xếp sách lên kệ.</mark> Cô giáo ghi nhận việc giúp đỡ của hai bạn.</blockquote></details>'));
 assert(!html.includes('ngoài phạm vi'));
});

test('Chuẩn hóa khoảng trắng khớp nguyên văn qua nhiều khoảng trắng/xuống dòng và từ chối trích dẫn rỗng', () => {
 assert.equal(normalizeCitationText('  Mai   mở\n\tcửa  thư viện.  '), 'Mai mở cửa thư viện.');

 const pageText = 'Đoạn mở đầu.\nMai   mở\tcửa\nthư viện.\nĐoạn kết thúc.';
 const docs = [{
  id: DOC_ID,
  name: 'Tài liệu đọc hiểu',
  version: 1,
  pages: [{number: 1, text: pageText}],
 }];
 const evidence = {
  sourceId: DOC_ID,
  sourceVersion: 1,
  locator: {kind: 'page', index: 1},
  quote: '  Mai mở cửa thư viện.  ',
 };

 const resolved = resolveCitationContext(evidence, docs);
 assert.equal(resolved.status, 'matched');
 assert.equal(resolved.canOpen, true);
 assert.equal(
  resolved.contextHtml,
  'Đoạn mở đầu.\n<mark>Mai   mở\tcửa\nthư viện.</mark>\nĐoạn kết thúc.',
 );

 const emptyQuote = resolveCitationContext({...evidence, quote: '   \n\t  '}, docs);
 assert.equal(emptyQuote.status, 'quote_mismatch');
 assert.equal(emptyQuote.canOpen, false);
});

test('Đổi phiên bản nguồn (version_changed): giữ nguyên trích dẫn & nhãn, không mở ngữ cảnh sai phiên bản', () => {
 const docs = [{
  id: DOC_ID,
  name: 'SGK Ngữ văn 8',
  kind: 'text',
  version: 4,
  pages: [{number: 2, text: 'Mai mở cửa thư viện. Bản đã cập nhật.'}],
 }];
 const evidence = {
  sourceId: DOC_ID,
  sourceVersion: 3,
  locator: {kind: 'page', index: 2},
  quote: 'Mai mở cửa thư viện.',
 };

 const resolved = resolveCitationContext(evidence, docs);
 assert.equal(resolved.status, 'version_changed');
 assert.equal(resolved.canOpen, false);
 assert.equal(resolved.hasSourceDoc, true);
 assert.equal(resolved.currentVersion, 4);
 assert.equal(resolved.quote, 'Mai mở cửa thư viện.');
 assert.equal(resolved.label, 'SGK Ngữ văn 8 · Trang 2');
 assert.equal(resolved.contextHtml, '');
 assert.match(resolved.notice, /v3.*v4/);

 const html = citationContextHTML(evidence, docs);
 assert(html.includes(`<blockquote>“Mai mở cửa thư viện.”<br><small title="${DOC_ID}">SGK Ngữ văn 8 · Trang 2 · Bản 3</small></blockquote>`));
 assert(html.includes('<p class="hint" data-citation-status="version_changed">'));
 assert(!html.includes('matrix-evidence-source'));

 const defaultVersionMismatch = resolveCitationContext(
  {...evidence, sourceVersion: 2},
  [{id: DOC_ID, name: 'Nguồn mặc định v1', text: 'Mai mở cửa thư viện.'}],
 );
 assert.equal(defaultVersionMismatch.status, 'version_changed');
 assert.equal(defaultVersionMismatch.currentVersion, 1);
});

test('Gỡ hoặc thay thế nguồn bằng UUID khác (source_missing): không mở nhầm và vẫn giữ trích dẫn truy vết', () => {
 const evidence = {
  sourceId: DOC_ID,
  sourceVersion: 2,
  locator: {kind: 'page', index: 1},
  quote: 'Đô thị hóa làm gia tăng tỉ lệ dân thành thị.',
 };

 const removed = resolveCitationContext(evidence, []);
 assert.equal(removed.status, 'source_missing');
 assert.equal(removed.canOpen, false);
 assert.equal(removed.hasSourceDoc, false);
 assert.equal(removed.quote, evidence.quote);
 assert.match(removed.notice, /không còn trong đề/);

 const replacedWithDifferentUuid = resolveCitationContext(evidence, [{
  id: OTHER_DOC_ID,
  name: 'Tài liệu thay thế',
  version: 2,
  text: 'Đô thị hóa làm gia tăng tỉ lệ dân thành thị.',
 }]);
 assert.equal(replacedWithDifferentUuid.status, 'source_missing');
 assert.equal(replacedWithDifferentUuid.canOpen, false);

 const html = citationContextHTML(evidence, []);
 assert(html.includes('<blockquote>“Đô thị hóa làm gia tăng tỉ lệ dân thành thị.”'));
 assert(html.includes('<p class="hint" data-citation-status="source_missing">'));
 assert(!html.includes('matrix-evidence-source'));
});

test('Đúng UUID và phiên bản nhưng lệch đoạn trích hoặc mất trang (quote_mismatch)', () => {
 const docs = [{
  id: DOC_ID,
  name: 'Tài liệu Địa lí 10',
  version: 2,
  pages: [{number: 1, text: 'Nội dung trang 1 đã thay đổi hoàn toàn.'}],
 }];

 const textChanged = resolveCitationContext({
  sourceId: DOC_ID,
  sourceVersion: 2,
  locator: {kind: 'page', index: 1},
  quote: 'Câu trích gốc không còn tồn tại.',
 }, docs);
 assert.equal(textChanged.status, 'quote_mismatch');
 assert.equal(textChanged.canOpen, false);
 assert.equal(textChanged.label, 'Tài liệu Địa lí 10 · Trang 1');
 assert.match(textChanged.notice, /Không khớp nguyên văn/);

 const missingPage = resolveCitationContext({
  sourceId: DOC_ID,
  sourceVersion: 2,
  locator: {kind: 'page', index: 5},
  quote: 'Nội dung trang 5 đã bị xóa.',
 }, docs);
 assert.equal(missingPage.status, 'quote_mismatch');
 assert.equal(missingPage.canOpen, false);
 assert.equal(missingPage.label, 'Tài liệu Địa lí 10 · Trang 5');

 const html = citationContextHTML({
  sourceId: DOC_ID,
  sourceVersion: 2,
  locator: {kind: 'page', index: 1},
  quote: 'Câu trích gốc không còn tồn tại.',
 }, docs);
 assert(html.includes('<blockquote>“Câu trích gốc không còn tồn tại.”'));
 assert(html.includes('<p class="hint" data-citation-status="quote_mismatch">'));
 assert(!html.includes('matrix-evidence-source'));
});

test('Hỗ trợ nguồn dán locator.kind === "passage" qua pastedText/pastedName/pastedRefs đủ 4 trạng thái', () => {
 const pastedText = 'Buổi sáng nắng khẽ chạm ô cửa thư viện.\nMai mở cuốn sách cũ nghe tiếng giấy xào xạc.';
 const pastedRefs = [{
  sourceId: PASSAGE_ID,
  sourceVersion: 1,
  locator: {kind: 'passage', index: 1},
 }];
 const evidence = {
  sourceId: PASSAGE_ID,
  sourceVersion: 1,
  locator: {kind: 'passage', index: 1},
  quote: 'Mai mở cuốn sách cũ',
 };

 const matched = resolveCitationContext(evidence, [], {
  pastedText,
  pastedName: 'Ngữ liệu tự dán',
  pastedRefs,
 });
 assert.equal(matched.status, 'matched');
 assert.equal(matched.canOpen, true);
 assert.equal(matched.label, 'Ngữ liệu tự dán · Đoạn 1');
 assert(matched.contextHtml.includes('<mark>Mai mở cuốn sách cũ</mark>'));

 const html = citationContextHTML(evidence, [], {
  pastedText,
  pastedName: '   ',
  pastedRefs,
 });
 assert(html.includes('<details class="matrix-evidence-source"><summary>Mở ngữ cảnh · Ngữ liệu đã dán · Đoạn 1</summary>'));

 const versionChanged = resolveCitationContext(evidence, [], {
  pastedText,
  pastedName: 'Ngữ liệu tự dán',
  pastedRefs: [{sourceId: PASSAGE_ID, sourceVersion: 2, locator: {kind: 'passage', index: 1}}],
 });
 assert.equal(versionChanged.status, 'version_changed');
 assert.equal(versionChanged.canOpen, false);
 assert.equal(versionChanged.currentVersion, 2);

 const missing = resolveCitationContext(evidence, [], {
  pastedText,
  pastedName: 'Ngữ liệu tự dán',
  pastedRefs: [],
 });
 assert.equal(missing.status, 'source_missing');
 assert.equal(missing.canOpen, false);

 const mismatch = resolveCitationContext(evidence, [], {
  pastedText: 'Đoạn văn đã thay nội dung khác.',
  pastedName: 'Ngữ liệu tự dán',
  pastedRefs,
 });
 assert.equal(mismatch.status, 'quote_mismatch');
 assert.equal(mismatch.canOpen, false);
});

test('Giữ đúng vị trí gốc sourceLocator ("Slide 3") cho bài giảng cá nhân và slide trình chiếu', () => {
 const personalDoc = {
  id: DOC_ID,
  name: 'Bài giảng Sinh học 10',
  personalLesson: true,
  sourceLocator: 'Slide 3',
  version: 2,
  text: 'Tế bào nhân thực có màng nhân bao bọc vật chất di truyền.',
 };
 const evidence = {
  sourceId: DOC_ID,
  sourceVersion: 2,
  locator: {kind: 'page', index: 1},
  quote: 'màng nhân bao bọc vật chất di truyền',
 };

 const matched = resolveCitationContext(evidence, [personalDoc]);
 assert.equal(matched.status, 'matched');
 assert.equal(matched.label, 'Bài giảng Sinh học 10 · Slide 3');
 const html = citationContextHTML(evidence, [personalDoc]);
 assert(html.includes('<summary>Mở ngữ cảnh · Bài giảng Sinh học 10 · Slide 3</summary>'));

 const changed = resolveCitationContext(evidence, [{...personalDoc, version: 3}]);
 assert.equal(changed.status, 'version_changed');
 assert.equal(changed.label, 'Bài giảng Sinh học 10 · Slide 3');

 const pptxDoc = {
  id: OTHER_DOC_ID,
  name: 'Trình chiếu Địa lí',
  kind: 'slides',
  version: 1,
  pages: [
   {number: 1, text: 'Slide mở đầu.'},
   {number: 3, text: 'Slide 3 trình bày cơ cấu dân số.'},
  ],
 };
 const slideMatched = resolveCitationContext({
  sourceId: OTHER_DOC_ID,
  sourceVersion: 1,
  locator: {kind: 'page', index: 3},
  quote: 'cơ cấu dân số',
 }, [pptxDoc]);
 assert.equal(slideMatched.status, 'matched');
 assert.equal(slideMatched.label, 'Trình chiếu Địa lí · Slide 3');
});

test('Chống XSS: thoát hoàn toàn <script>, <img onerror> và thuộc tính nguy hiểm ở mọi trường', () => {
 const payload = '<script>alert(1)</script><img src=x onerror=alert(2)>';
 const evilId = 'id-" onmouseover="alert(3)';
 const docs = [{
  id: evilId,
  name: `Tên ${payload}`,
  personalLesson: true,
  sourceLocator: `Slide 3 ${payload}`,
  version: 1,
  text: `Mở đầu ${payload} kết thúc.`,
 }];
 const evidence = {
  sourceId: evilId,
  sourceVersion: 1,
  locator: {kind: 'page', index: 1},
  quote: payload,
 };

 const resolved = resolveCitationContext(evidence, docs);
 assert.equal(resolved.status, 'matched');
 assert(!resolved.contextHtml.includes('<script'));
 assert(!resolved.contextHtml.includes('<img'));
 assert(resolved.contextHtml.includes('<mark>&lt;script&gt;alert(1)&lt;/script&gt;&lt;img src=x onerror=alert(2)&gt;</mark>'));

 const html = citationContextHTML(evidence, docs);
 assert(!html.includes('<script'));
 assert(!html.includes('<img'));
 assert(!html.includes('" onmouseover="'));
 assert(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
 assert(html.includes('&lt;img src=x onerror=alert(2)&gt;'));

 const changedHtml = citationContextHTML(evidence, [{...docs[0], version: 2}]);
 assert(!changedHtml.includes('<script'));
 assert(!changedHtml.includes('<img'));
 assert(changedHtml.includes('data-citation-status="version_changed"'));
});

test('question-check checkEvidenceHTML mở ngữ cảnh trực tiếp và xử lý nút Mở nguồn khi còn/mất tài liệu', () => {
 const docs = [{
  id: DOC_ID,
  name: 'Tư liệu Lịch sử',
  version: 2,
  pages: [{number: 2, text: 'Phong trào diễn ra rộng khắp vào mùa thu năm 1945.'}],
 }];
 const evidence = [{
  sourceId: DOC_ID,
  sourceVersion: 2,
  locator: {kind: 'page', index: 2},
  quote: 'mùa thu năm 1945',
 }];

 const matchedHtml = checkEvidenceHTML(evidence, docs);
 assert(matchedHtml.includes('<details class="matrix-evidence-source"><summary>Mở ngữ cảnh · Tư liệu Lịch sử · Trang 2</summary>'));
 assert(matchedHtml.includes('<mark>mùa thu năm 1945</mark>'));
 assert(matchedHtml.includes(`data-action="source" data-doc="${DOC_ID}" data-page="2"`));
 assert(matchedHtml.includes('Mở nguồn để đối chiếu'));

 const versionChangedHtml = checkEvidenceHTML(evidence, [{...docs[0], version: 3}]);
 assert(versionChangedHtml.includes('data-citation-status="version_changed"'));
 assert(!versionChangedHtml.includes('matrix-evidence-source'));
 assert(versionChangedHtml.includes(`data-action="source" data-doc="${DOC_ID}" data-page="2"`));

 const missingHtml = checkEvidenceHTML(evidence, []);
 assert(missingHtml.includes('data-citation-status="source_missing"'));
 assert(missingHtml.includes('mùa thu năm 1945'));
 assert(!missingHtml.includes('data-action="source"'));
 assert(!missingHtml.includes('Mở nguồn để đối chiếu'));
});

test('UC9 stale citations: đánh dấu stale cho đủ 4 điều kiện và không mở details cũ', () => {
 const docs = [{
  id: DOC_ID,
  name: 'Ngữ liệu Văn 9',
  version: 1,
  pages: [{number: 1, text: 'Sông Hồng chảy qua vùng đồng bằng Bắc Bộ.'}],
 }];
 const baseEv = {
  sourceId: DOC_ID,
  sourceVersion: 1,
  locator: {kind: 'page', index: 1},
  quote: 'Sông Hồng chảy qua vùng đồng bằng',
  questionVersion: 1,
 };

 const flagStale = resolveCitationContext({...baseEv, stale: true, staleReason: 'quote_variant_changed'}, docs);
 assert.equal(flagStale.status, 'stale');
 assert.equal(flagStale.canOpen, false);
 assert.equal(flagStale.quote, baseEv.quote);
 assert.ok(flagStale.label.includes('Ngữ liệu Văn 9'));

 const sourceMismatchNull = resolveCitationContext(baseEv, docs, {currentSource: {docId: null, location: 'Bản nhập tay'}});
 assert.equal(sourceMismatchNull.status, 'stale');
 assert.equal(sourceMismatchNull.canOpen, false);

 const pageMismatch = resolveCitationContext(baseEv, docs, {currentSource: {docId: DOC_ID, page: 2}});
 assert.equal(pageMismatch.status, 'stale');

 const versionMismatch = resolveCitationContext(baseEv, docs, {questionVersion: 2});
 assert.equal(versionMismatch.status, 'stale');

 const quoteChanged = resolveCitationContext(baseEv, docs, {currentQuoteText: 'Đoạn ngữ liệu hoàn toàn mới không có đoạn cũ.'});
 assert.equal(quoteChanged.status, 'stale');

 const staleHtml = citationContextHTML(baseEv, docs, {questionVersion: 2});
 assert.ok(staleHtml.includes('data-citation-status="stale"'));
 assert.ok(staleHtml.includes(baseEv.quote));
 assert.ok(!staleHtml.includes('matrix-evidence-source'));
});
