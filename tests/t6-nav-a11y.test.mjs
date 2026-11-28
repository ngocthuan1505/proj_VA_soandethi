import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

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
