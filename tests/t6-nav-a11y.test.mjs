import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {expandLessonSearchVariants, lessonMatchesSearch, normalizeLessonSearch} from '../lesson-picker.js';

const ROOT = process.cwd();
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

test('t6 · Trang chủ có lối tắt Rút trích PDF/OCR, hỗ trợ Ctrl+Enter và giữ focus khi làm mới Trợ lý Chủ động', () => {
  const src = read('home.js');
  assert.match(src, /data-action="home-go-extract"/);
  assert.match(src, /ctrlEnterBound/);
  assert.match(src, /focusedAction/);
  assert.match(src, /Thông báo Trợ lý Chủ động/);
  assert.match(src, /home-open-campaign/);
});

test('t6 · Kho SGK Kết nối tri thức hỗ trợ phím mũi tên tablist, roving tabindex, role=tabpanel và phản hồi tiếng Việt', () => {
  const src = read('lesson-picker.js');
  assert.match(src, /ArrowRight/);
  assert.match(src, /ArrowLeft/);
  assert.match(src, /Home/);
  assert.match(src, /End/);
  assert.match(src, /role="tabpanel"/);
  assert.match(src, /tabindex/);
  assert.match(src, /data-sgk-reset-filters/);
  assert.match(src, /data-sgk-clear-query/);
  assert.match(src, /Vui lòng chọn ít nhất một bài học SGK trước khi soạn đề nhanh\./);
});

test('t6 · Neo điều hướng ngoài Soạn đề trong app.js và phản hồi tiếng Việt trong mvp.js', () => {
  const appSrc = read('app.js');
  const mvpSrc = read('mvp.js');
  assert.match(appSrc, /import \{mountDesign,setActiveWorkspaceNav\} from '\.\/design\.js';/);
  assert.match(appSrc, /function syncHomeUrl\(mode\)/);
  assert.match(mvpSrc, /role="alert"/);
  assert.match(mvpSrc, /Không thể kết nối máy chủ để xuất bản tổng hợp/);
  assert.match(mvpSrc, /Đã lưu bản đối chiếu trang/);
});

test('t6 · CSS bảo đảm tương phản >= 4.5:1 cho SGK/Ngân hàng/Phân tích và vùng chạm >= 40px trên 390px', () => {
  const css = read('assets/layout.css');
  assert.match(css, /\.sgk-tab\.is-active/);
  assert.match(css, /\.qbank-badge-subject\s*\{[^}]*color:\s*#0f4c81/);
  assert.match(css, /\.qbank-badge-type\s*\{[^}]*color:\s*#0f4c81/);
  assert.match(css, /\.analytics-jump\s*\{[^}]*color:\s*#0f4c81/);
  assert.match(css, /\.mach-logo\s*\{\s*width:\s*40px;\s*height:\s*40px;\s*\}/);
});

test('t6 · Kho SGK cho phép thu gọn kết quả khi tìm kiếm, trả focus về nút tập và tìm không dấu đúng', () => {
  const src = read('lesson-picker.js');
  assert.match(src, /searchCollapsedChapters/);
  assert.match(src, /hasSearch\?searchCollapsedChapters\.has\(chKey\):collapsedChapters\.has\(chKey\)/);
  assert.match(src, /aria-pressed="\$\{selectedVolume===v\?'true':'false'\}"/);
  assert.match(src, /volumePillsHost\?\.querySelector\(`\[data-sgk-volume="\$\{CSS\.escape\(volValue\)\}"\]`\)/);
  assert.equal(normalizeLessonSearch('Phương pháp thế — Hệ phương trình!'), 'phuong phap the he phuong trinh');
  assert.equal(
    lessonMatchesSearch(
      {name: 'Toán 9 Tập 1', subject: 'Toán', volume: 'Tập 1'},
      {chapter: 'Chương I', title: 'Giải hệ phương trình bằng phương pháp thế', text: ''},
      'phep the',
    ),
    true,
  );
});

test('t6 · Mở Kho SGK từ Trang chủ rồi nhấn Hủy quay về Trang chủ và không mở assistant-sources', () => {
  const homeSrc = read('home.js');
  const pickerSrc = read('lesson-picker.js');
  assert.match(homeSrc, /if \(action === 'home-go-lessons'\)\s*\{\s*if \(node instanceof HTMLElement && node\.isConnected\) node\.focus\?\.\(\);\s*const \{openLessonPicker\} = await import\('\.\/lesson-picker\.js'\);\s*await openLessonPicker\(ctx\);\s*return true;\s*\}/);
  assert.match(pickerSrc, /data-action="\$\{useLayer2\?'close-top-modal':\(origin\?'assistant-sources':'close'\)\}">Hủy<\/button>/);
});

test('t6 · Tìm giải hệ phương trình giữ từ khóa phương pháp, loại Bài 11 Tỉ số lượng giác lớp 9 khi tìm Gauss', () => {
  const query = 'giải hệ phương trình bằng phương pháp Gauss';
  const variants = expandLessonSearchVariants(query);
  assert.ok(variants.includes('giai he phuong trinh bang phuong phap gauss'));
  assert.ok(variants.includes('giai he bang phuong phap gauss'));
  assert.ok(!variants.includes('giai he'));
  assert.ok(variants.every((v) => v.includes('gauss')));

  const kntt9 = {
    name: 'Toán 9 - Tập 1 (Kết nối tri thức)',
    subject: 'Toán',
    series: 'Kết nối tri thức với cuộc sống',
    volume: 'Tập 1',
  };
  const bai11 = {
    chapter: 'Chương IV: Hệ thức lượng trong tam giác vuông',
    title: 'Bài 11: Tỉ số lượng giác của góc nhọn',
    summary: 'Tỉ số lượng giác của góc nhọn trong tam giác vuông.',
    learningOutcomes: [
      'Tính được tỉ số lượng giác và hệ thức cạnh - góc trong tam giác vuông.',
      'Ứng dụng giải bài toán đo chiều cao, khoảng cách thực tế.',
    ],
  };
  const bai2 = {
    chapter: 'Chương I: Phương trình và hệ hai phương trình bậc nhất hai ẩn',
    title: 'Bài 2: Giải hệ hai phương trình bậc nhất hai ẩn',
    summary: 'Giải hệ hai phương trình bậc nhất hai ẩn bằng phương pháp thế, cộng đại số và giải bài toán thực tế.',
  };
  const gauss10 = {
    chapter: 'Chuyên đề 1: Hệ phương trình bậc nhất ba ẩn',
    title: 'Bài 1: Hệ phương trình bậc nhất ba ẩn',
    summary: 'Giải hệ phương trình bậc nhất ba ẩn bằng phương pháp Gauss và vận dụng giải bài toán vật lí, hóa học, kinh tế.',
  };

  assert.equal(lessonMatchesSearch(kntt9, bai11, query), false);
  assert.equal(lessonMatchesSearch(kntt9, bai2, query), false);
  assert.equal(lessonMatchesSearch({name: 'Chuyên đề Toán 10', subject: 'Toán'}, gauss10, query), true);
  assert.equal(
    lessonMatchesSearch(
      kntt9,
      {chapter: 'Phương trình và hệ phương trình', title: 'Giải hệ bằng phép thế', text: ''},
      'giải hệ phương trình bằng phương pháp thế',
    ),
    true,
  );
});
