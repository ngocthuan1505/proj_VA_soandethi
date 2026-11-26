import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { documentPlain, renderRichDocument, richPositionMap, richSelection } from '../rich-document.js';
import {
  captureEditorCursor,
  insertInlineMath,
  insertRichContent,
  richPlain,
  textToRich,
} from '../editor.js';
import { citationContextHTML } from '../citation-context.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const readText = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

test('UV64 codeBlock (Ctrl+Alt+C): documentPlain, renderRichDocument và richPositionMap bảo toàn đủ 3 dòng', () => {
  const codeDoc = {
    type: 'doc',
    content: [
      { type: 'paragraph', content: [{ type: 'text', text: 'Đoạn mở đầu' }] },
      {
        type: 'codeBlock',
        attrs: { language: 'python' },
        content: [{ type: 'text', text: 'dong 1\ndong 2\ndong 3' }],
      },
      { type: 'paragraph', content: [{ type: 'text', text: 'Đoạn kết' }] },
    ],
  };

  assert.equal(documentPlain(codeDoc), 'Đoạn mở đầu\ndong 1\ndong 2\ndong 3\nĐoạn kết');

  const html = renderRichDocument(codeDoc);
  assert.ok(html.includes('<pre><code class="language-python">dong 1\ndong 2\ndong 3</code></pre>'));

  const xssCode = {
    type: 'doc',
    content: [
      {
        type: 'codeBlock',
        content: [{ type: 'text', text: 'x = $a$\n<script>alert(1)</script>\ndong 3' }],
      },
    ],
  };
  const xssHtml = renderRichDocument(xssCode);
  assert.ok(xssHtml.includes('<pre><code>x = $a$\n&lt;script&gt;alert(1)&lt;/script&gt;\ndong 3</code></pre>'));
  assert.ok(!xssHtml.includes('<script>'));
  assert.ok(!xssHtml.includes('class="katex"'));

  const map = richPositionMap(codeDoc);
  assert.equal(map.text, documentPlain(codeDoc));
  const l3Start = map.text.indexOf('dong 3');
  const unit = map.units.find((u) => u.type === 'text' && l3Start >= u.start && l3Start + 6 <= u.end);
  assert.ok(unit);
  const from = unit.from + (l3Start - unit.start);
  const sel = richSelection(codeDoc, from, from + 6);
  assert.deepEqual(sel, { start: l3Start, end: l3Start + 6, text: 'dong 3' });

  const fenced = textToRich('Mở đầu\n```js\na = 1;\nb = 2;\nc = 3;\n```\nKết');
  assert.equal(fenced.content[1].type, 'codeBlock');
  assert.equal(fenced.content[1].attrs.language, 'js');
  assert.equal(richPlain(fenced), 'Mở đầu\na = 1;\nb = 2;\nc = 3;\nKết');
});

test('UV64 Editor cursor & smart math spacing: lưu {key, from, to}, khôi phục và chèn khoảng trắng hợp lý', () => {
  assert.equal(typeof captureEditorCursor, 'function');
  assert.equal(typeof insertInlineMath, 'function');
  assert.equal(typeof insertRichContent, 'function');

  const editorJs = readText('editor.js');
  const referenceJs = readText('reference.js');
  const studioJs = readText('studio.js');

  assert.match(editorJs, /const snap=\{key,from,to\};lastCursors\.set\(key,snap\)/);
  assert.match(editorJs, /smartInlineMathPayload/);
  assert.match(editorJs, /setTextSelection\(range\)\.insertContent\(payload\)/);
  assert.match(referenceJs, /const savedCursor=captureEditorCursor\(/);
  assert.match(referenceJs, /insertInlineMath\(q\.id,latex,display,savedFormula\.editorKey,savedFormula\.cursor\)/);
  assert.match(referenceJs, /insertRichContent\(target\.id,content,targetKey,targetCursor\)/);
  assert.match(studioJs, /function showQuestion\(anchor\)[\s\S]*document-menu studio-question-menu/);
  assert.match(referenceJs, /\.paper-scroll'\)\.addEventListener\('scroll',\(\)=>\{if\(!document\.querySelector\('\.inline-math-panel,\.document-menu,\.studio-question-menu'\)\)/);
});

test('UV64 SGK KNTT Modal & Citations & Ma trận 2 nhánh choiceGroup', () => {
  const lessonPickerJs = readText('lesson-picker.js');
  const appJs = readText('app.js');

  assert.match(lessonPickerJs, /import \{richTextHTML\} from '\.\/math-content\.js'/);
  assert.match(lessonPickerJs, /richTextHTML\(summaryText\)/);
  assert.match(lessonPickerJs, /richTextHTML\(rawText\)/);
  assert.match(lessonPickerJs, /richTextHTML\(o\)/);
  assert.match(lessonPickerJs, /NXB Giáo dục Việt Nam/);
  assert.match(lessonPickerJs, /GDPT 2018/);
  assert.match(lessonPickerJs, /Tóm tắt & YCCĐ/);
  assert.match(lessonPickerJs, /sgk-empty-state/);

  assert.match(appJs, /\[name=matrix-level-points\]/);
  assert.match(appJs, /computeMatrixRowActuals/);
  assert.match(appJs, /rowUnitPointsForLevel/);
  assert.match(appJs, /effectiveExamTotals/);
  assert.match(appJs, /Phần chung \+ max\/hướng/);
  assert.match(appJs, /const parsedSrcVer=Number\(q\.source\.version\);[\s\S]*?const srcVer=Number\.isFinite\(parsedSrcVer\)&&parsedSrcVer>=1\?parsedSrcVer:1;/);

  const html = citationContextHTML(
    {
      sourceId: 'doc-v2',
      sourceVersion: 1,
      locator: { kind: 'page', index: 1 },
      quote: 'Trích đoạn v1',
    },
    [{ id: 'doc-v2', name: 'SGK mới', version: 2, text: 'Nội dung mới v2' }],
  );
  assert.ok(html.includes('data-citation-status="version_changed"'));
});

test('UV64 Responsive Mobile 390x844, bàn phím ảo 390x560 và ngưỡng !important < 30', () => {
  const tokensCss = readText('assets/tokens.css');
  const layoutCss = readText('assets/layout.css');
  const paperCss = readText('assets/paper.css');

  const importantCount = [tokensCss, layoutCss, paperCss]
    .map((css) => (css.match(/!important/g) || []).length)
    .reduce((a, b) => a + b, 0);
  assert.ok(importantCount < 30, `Số lượng !important vượt ngưỡng 30: ${importantCount}`);

  assert.match(layoutCss, /\.matrix-table-scroll\s*\{[^}]*max-width:\s*100%;[^}]*overflow-x:\s*auto;[^}]*-webkit-overflow-scrolling:\s*touch;/);
  assert.match(layoutCss, /\.editor-toolbar\s+\[data-action="menu"\]\s*\{[^}]*position:\s*sticky;[^}]*right:\s*0;/);
  assert.match(layoutCss, /\.document-bar\s+\.ruler\s*\{\s*display:\s*none;\s*\}/);
  assert.match(layoutCss, /\.sgk-tree-pane\s*\{\s*min-height:\s*96px;/);
  assert.match(
    layoutCss,
    /@media \(max-width:\s*760px\) and \(max-height:\s*680px\)[\s\S]*height:\s*100dvh;[\s\S]*max-height:\s*100dvh;[\s\S]*\.assistant-body\s*\{[^}]*min-height:\s*120px;/,
  );
});
