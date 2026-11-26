import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildFlexibleChatContext } from '../workbench.js';
import { parsePromptIntent, renderHomeViewHTML } from '../home.js';
import { isVoiceSupported, mountVoiceButton } from '../voice-input.js';
import {
  AUTO_CREATE_STEPS,
  parseAutoCreateSse,
  renderAutoCreateCardHTML,
  isAutoPilotEnabled,
  setAutoPilotEnabled,
} from '../matrix-synthesis.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const readText = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');

test('UV63 Chat Source Isolation: gỡ hết nguồn (assistantSources: []) không gửi nhầm docs vào chat', () => {
  const ctx = buildFlexibleChatContext(
    {
      id: 'ex-detached',
      subject: 'Toán',
      grade: '11',
      assistantSources: [],
      docs: [
        {
          id: 'doc-1',
          name: 'Tài liệu đã gỡ khỏi chat',
          version: 1,
          pages: [{ number: 1, text: 'Nội dung này không được tự gửi khi đã bỏ chọn hết nguồn.' }],
        },
      ],
      questions: [],
    },
    [],
    [],
  );
  const sources = ctx.filter((x) => x.kind === 'attached-source');
  assert.equal(sources.length, 0);
});

test('UV63 Home & Proactive Intent: parsePromptIntent nhận diện đúng môn, lớp và chiến dịch nhiều đề', () => {
  const multi = parsePromptIntent('Bộ 10 đề ôn tập Toán 9');
  assert.equal(multi.subject, 'Toán');
  assert.equal(multi.grade, '9');
  assert.equal(multi.campaignTarget, 10);

  const single = parsePromptIntent('tạo 1 đề thi cuối kì 1 lớp 11 môn toán theo chuẩn bgd 2018');
  assert.equal(single.subject, 'Toán');
  assert.equal(single.grade, '11');
  assert.equal(single.campaignTarget, 0);

  const html = renderHomeViewHTML(
    {
      exams: [{ id: 'e1', title: 'Đề mẫu Toán 11', subject: 'Toán', grade: '11', questions: [{}], updated: Date.now() }],
    },
    {
      badgeCount: 2,
      greeting: 'Chào thầy cô',
      activeCampaigns: [{ id: 'c1', title: 'Ôn tập HK1', subject: 'Toán', grade: '11', completedCount: 3, targetCount: 10 }],
      nextDayReviewNudges: [],
      urgentDeadlines: [],
      pendingRoomGrading: { count: 0, rooms: [] },
    },
  );
  for (const needle of ['id="home-view"', 'id="home-prompt-form"', 'id="home-prompt-input"', 'id="home-prompt-submit"', '3/10']) {
    assert.ok(html.includes(needle), `renderHomeViewHTML thiếu ${needle}`);
  }
});

test('UV63 Voice Input & Auto-Create UI: xuất module giọng nói, phân tích SSE 4 pha và trạng thái Auto-Pilot', () => {
  assert.equal(typeof isVoiceSupported, 'function');
  assert.equal(typeof mountVoiceButton, 'function');
  assert.equal(AUTO_CREATE_STEPS.length, 4);

  const parsed = parseAutoCreateSse('event: step\ndata: {"phase":"plan","status":"done"}\n\nevent: comple');
  assert.equal(parsed.records.length, 1);
  assert.equal(parsed.records[0].type, 'step');
  assert.equal(parsed.records[0].data.phase, 'plan');

  const cardHtml = renderAutoCreateCardHTML({
    status: 'running',
    running: true,
    statusText: 'Đang sinh song song 3 lô câu hỏi…',
    phases: { plan: 'done', swarm: 'running', goal: 'pending', apply: 'pending' },
    totalBatches: 3,
    completedBatches: 1,
    completedCount: 5,
    totalSlots: 15,
  });
  assert.ok(cardHtml.includes('auto-create-card') && cardHtml.includes('data-action="auto-create-cancel"'));

  const prev = isAutoPilotEnabled(true);
  setAutoPilotEnabled(false);
  assert.equal(isAutoPilotEnabled(true), false);
  setAutoPilotEnabled(prev);
});

test('UV63 Clean Jargon: mọi module mới sạch thuật ngữ kỹ thuật lộ cho giáo viên', () => {
  for (const file of ['home.js', 'voice-input.js', 'matrix-chat.js', 'matrix-synthesis.js', 'lesson-picker.js', 'studio.js']) {
    const src = readText(file);
    assert.ok(!/(?:bản PoC|Điểm MVP|dùng điểm MVP|Guardrail|giải mù chéo|M01–M11|M01-M11)/i.test(src), `${file} chứa thuật ngữ bị cấm`);
  }
});
