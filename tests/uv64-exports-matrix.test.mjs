import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  isApproved,
  matrix,
  rebalanceMatrixRowsToTen,
  validateMatrixRows,
} from '../core.js';
import { buildMatrixPlanOverviewHTML } from '../matrix-chat.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

test('UV64 core.js: isApproved không crash và trả false khi thiếu q.v hoặc null', () => {
  assert.equal(isApproved(null), false);
  assert.equal(isApproved(undefined), false);
  assert.equal(isApproved({}), false);
  assert.equal(isApproved({ check: { status: 'approved' } }), false);
  assert.equal(isApproved({ approval: { status: 'approved' } }), false);
  assert.equal(isApproved({ v: 2, check: { version: 1, status: 'approved' } }), false);
  assert.equal(isApproved({ v: 2, check: { version: 2, status: 'approved' } }), true);
  assert.equal(isApproved({ v: 0, approval: { version: 0, status: 'approved' } }), true);
});

test('UV64 core.js: rebalanceMatrixRowsToTen giữ nguyên pointsByLevel và tỷ trọng ô về 10,00đ', () => {
  const rows = [
    {
      topic: 'Mạng máy tính',
      type: 'mcq',
      targets: [8, 8, 4, 0],
      pointsByLevel: [0.2, 0.25, 0.4, null],
      pointsByLevelQ4: [0.8, 1, 1.6, null],
    },
    {
      topic: 'Lập trình Python',
      type: 'essay',
      targets: [0, 0, 2, 1],
      pointsByLevel: [null, null, 1.0, 2.0],
      pointsByLevelQ4: [null, null, 4, 8],
    },
  ];
  const balanced = rebalanceMatrixRowsToTen(rows);
  assert.equal(balanced.length, 2);

  // Bảo toàn mảng pointsByLevel khác nhau thay vì san phẳng thành một mức đồng đều
  assert.ok(Array.isArray(balanced[0].pointsByLevel));
  assert.equal(balanced[0].points, undefined);
  assert.ok(Array.isArray(balanced[1].pointsByLevel));

  const [nb, th, vd] = balanced[0].pointsByLevel;
  assert.ok(nb > 0 && th > nb && vd > th, `Thứ tự tỷ trọng bị mất: ${nb}, ${th}, ${vd}`);

  // Mỗi mức đều là bội số của 0,05 và tổng toàn ma trận đúng 10,00đ
  const sumUnits = balanced.reduce(
    (sum, r) =>
      sum +
      r.targets.reduce(
        (rowSum, cnt, i) =>
          rowSum + Math.round((Number(cnt) || 0) * Math.round((r.pointsByLevel[i] || 0) * 100)),
        0,
      ),
    0,
  );
  assert.equal(sumUnits, 1000);
  assert.doesNotThrow(() => validateMatrixRows(balanced));

  // Kiểm tra đề Tin học 2 nhánh choiceGroup có pointsByLevel cân đủ 10,00đ cho cả hai nhánh
  const twoTrack = rebalanceMatrixRowsToTen([
    {
      topic: 'Phần chung',
      type: 'mcq',
      targets: [10, 10, 4, 0],
      pointsByLevel: [0.2, 0.25, 0.4, null],
    },
    {
      topic: 'Định hướng KHMT',
      type: 'mcq',
      choiceGroup: 'Tự chọn A',
      targets: [2, 1, 1, 0],
      pointsByLevel: [0.5, 0.75, 1.0, null],
    },
    {
      topic: 'Định hướng THUD',
      type: 'mcq',
      choiceGroup: 'Tự chọn B',
      targets: [2, 1, 1, 0],
      pointsByLevel: [0.5, 0.75, 1.0, null],
    },
  ]);
  assert.doesNotThrow(() => validateMatrixRows(twoTrack));
});

test('UV64 core.js: matrix(e) tách choiceGroup và không đếm đôi các dòng cùng chủ đề nhưng khác điểm', () => {
  const exam = {
    matrix: [
      { topic: 'Hàm số (0,4đ)', type: 'mcq', targets: [1, 0, 0, 0], points: 0.4 },
      { topic: 'Hàm số (9,6đ)', type: 'mcq', targets: [1, 0, 0, 0], points: 9.6 },
      { topic: 'Hàm số', type: 'mcq', targets: [1, 0, 0, 0], points: 0.4 },
      { topic: 'Hàm số', type: 'mcq', targets: [1, 0, 0, 0], points: 9.6 },
      {
        topic: 'Đồ thị thuật toán',
        type: 'mcq',
        choiceGroup: 'Tự chọn A',
        targets: [1, 0, 0, 0],
        points: 1.0,
      },
      {
        topic: 'CSDL SQL',
        type: 'mcq',
        choiceGroup: 'Tự chọn B',
        targets: [1, 0, 0, 0],
        points: 1.0,
      },
    ],
    questions: [
      { id: 'q1', topic: 'Hàm số', type: 'mcq', level: 0, points: 0.4 },
      { id: 'q2', topic: 'Hàm số', type: 'mcq', level: 0, points: 9.6 },
      { id: 'q3', topic: 'Đồ thị thuật toán', type: 'mcq', level: 0, choiceGroup: 'Tự chọn A', points: 1.0 },
    ],
  };

  const rows = matrix(exam);
  assert.equal(rows[0].cells[0].actual, 1, 'Dòng tách Hàm số (0,4đ) chỉ đếm đúng 1 câu');
  assert.equal(rows[1].cells[0].actual, 1, 'Dòng tách Hàm số (9,6đ) chỉ đếm đúng 1 câu');
  assert.equal(rows[2].cells[0].actual, 1, 'Dòng trùng tên Hàm số 0,4đ không đếm đôi thành 2');
  assert.equal(rows[3].cells[0].actual, 1, 'Dòng trùng tên Hàm số 9,6đ không đếm đôi thành 2');
  assert.equal(rows[4].cells[0].actual, 1, 'Dòng Tự chọn A đếm đúng 1 câu');
  assert.equal(rows[5].cells[0].actual, 0, 'Dòng Tự chọn B chưa có câu nào không được đếm nhầm');
});

test('UV64 matrix-chat.js: bảng xem trước không lặp điểm hai định dạng và tính đúng số câu hiệu lực 2 nhánh', () => {
  const html = buildMatrixPlanOverviewHTML({
    rows: [
      { topic: 'Hàm số (0,4đ)', type: 'mcq', targets: [1, 0, 0, 0], points: 0.4 },
      {
        topic: 'Mạng máy tính',
        type: 'mcq',
        targets: [10, 10, 3, 0],
        pointsByLevel: [0.2, 0.25, 0.4, null],
      },
      {
        topic: 'KHMT (1,5đ)',
        type: 'mcq',
        choiceGroup: 'Tự chọn A',
        targets: [2, 2, 0, 0],
        points: 1.5,
      },
      {
        topic: 'THUD (1,5đ)',
        type: 'mcq',
        choiceGroup: 'Tự chọn B',
        targets: [2, 2, 0, 0],
        points: 1.5,
      },
    ],
    notes: 'Xem trước ma trận điểm lẻ',
  });

  // Số câu hiệu lực = 1 + 23 + max(4, 4) = 28 câu/ý (không cộng đôi 32)
  assert.match(html, /Cơ cấu đề xuất · 28 câu\/ý · 10 điểm/);
  // Đã gỡ thẻ (0,4đ) / (1,5đ) ở tên chủ đề khi cột mức đã hiển thị 0,40đ / 1,50đ
  assert.doesNotMatch(html, /Hàm số \(0,4đ\)/);
  assert.doesNotMatch(html, /KHMT \(1,5đ\)/);
  // Tách số câu và điểm bằng thẻ block <small style="display:block">, không dính thành 10,4đ
  assert.match(html, /<td>1<small style="display:block">0,40đ<\/small><\/td>/);
  assert.match(html, /<td>2<small style="display:block">1,50đ<\/small><\/td>/);
  assert.doesNotMatch(html, /10,4đ/);

  // Bảo đảm không chứa thuật ngữ kỹ thuật lộ cho giáo viên
  for (const rel of ['core.js', 'matrix-chat.js']) {
    const content = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    assert.doesNotMatch(content, /bản PoC|Điểm MVP|Guardrail|giải mù chéo/i, `${rel} sạch jargon`);
  }
});
