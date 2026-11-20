import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { ensureBlocks } from '../blocks.js';
import { commit, exportHTML, redo, undo } from '../core.js';
import { closePDFBrowser, makeDocx, makePDF } from '../exports.mjs';
import { documentPlain, richPositionMap, richSelection } from '../rich-document.js';
import { dependency } from '../runtime.mjs';

const fixturePath = new URL('./fixtures/ui2-editor-golden.json', import.meta.url);

test('T01: golden fixture đủ 3 môn, blockIds chuẩn và undo/redo giữ nguyên richDoc', async () => {
  const { multiSubjectExam, longPaginatedExam } = JSON.parse(await readFile(fixturePath, 'utf8'));
  assert.equal(multiSubjectExam.questions.length, 3);
  assert.ok(longPaginatedExam.questions.length >= 8);
  for (const exam of [multiSubjectExam, longPaginatedExam]) {
    ensureBlocks(exam);
    assert.deepEqual(Object.keys(exam.blockIds).sort(), ['general', 'heading', 'marking']);
    for (const q of exam.questions) {
      assert.equal(Object.keys(q.blockIds).length, 8);
      assert.equal(documentPlain(q.richDoc), q.stem);
      if (q.explanationDoc) assert.equal(documentPlain(q.explanationDoc), q.explanation);
    }
  }
  const snapshotBefore = structuredClone(multiSubjectExam.questions[0].richDoc);
  commit(multiSubjectExam, 'Sửa thử câu 1', (draft) => {
    draft.questions[0].stem = 'Đã thay tạm.';
  });
  assert.equal(undo(multiSubjectExam), true);
  assert.deepEqual(multiSubjectExam.questions[0].richDoc, snapshotBefore);
  assert.equal(redo(multiSubjectExam), true);
  assert.equal(multiSubjectExam.questions[0].stem, 'Đã thay tạm.');
  assert.equal(undo(multiSubjectExam), true);
});

test('T01: xuất Word OMML & PDF giữ công thức và tách rạch bản học sinh vs giáo viên', async () => {
  const { multiSubjectExam } = JSON.parse(await readFile(fixturePath, 'utf8'));
  const studentHTML = exportHTML(multiSubjectExam, false);
  const teacherHTML = exportHTML(multiSubjectExam, true);
  assert.ok(!studentHTML.includes(multiSubjectExam.questions[0].explanation));
  assert.ok(teacherHTML.includes(multiSubjectExam.questions[0].explanation));

  const studentDocx = await makeDocx(multiSubjectExam, false);
  const teacherDocx = await makeDocx(multiSubjectExam, true);
  const JSZip = dependency('jszip');
  const studentXml = await (await JSZip.loadAsync(studentDocx)).file('word/document.xml').async('string');
  const teacherXml = await (await JSZip.loadAsync(teacherDocx)).file('word/document.xml').async('string');
  assert.ok(studentXml.includes('<m:m>') || studentXml.includes('<m:m '));
  assert.ok(!studentXml.includes(multiSubjectExam.questions[0].explanation));
  assert.ok(teacherXml.includes(multiSubjectExam.questions[0].explanation));

  const pdfBytes = await makePDF(multiSubjectExam, true, 'http://127.0.0.1:4173');
  await closePDFBrowser();
  assert.ok(Buffer.from(pdfBytes).subarray(0, 5).toString('utf8') === '%PDF-');
});

test('T03: richPositionMap và richSelection khớp chính xác công thức $x+1$ thứ hai giữa tiếng Việt có dấu', async () => {
  const { edgeCases } = JSON.parse(await readFile(fixturePath, 'utf8'));
  const doc = edgeCases.duplicateFormulaDoc;
  const plain = documentPlain(doc);
  const map = richPositionMap(doc);
  assert.equal(map.text, plain);
  const mathUnits = map.units.filter((u) => u.type === 'mathInline');
  assert.equal(mathUnits.length, 2);
  const second = mathUnits[1];
  const sel = richSelection(doc, second.from, second.to);
  assert.equal(sel.start, plain.lastIndexOf('$x+1$'));
  assert.equal(sel.text, '$x+1$');
});
