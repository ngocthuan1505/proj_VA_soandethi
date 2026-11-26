import test from 'node:test';
import assert from 'node:assert/strict';

import { chatMetaDisplay, lastAssistantChatIndex } from '../workbench.js';
import { describeActiveEngine, renderAutoCreateCardHTML } from '../matrix-synthesis.js';

test('chatMetaDisplay bỏ lặp agy-cli nhưng giữ tên model thật và fallbackReason', () => {
  assert.equal(
    chatMetaDisplay({ providerUsed: 'agy', modelUsed: 'agy-cli', latencyMs: 21600 }),
    'AGY CLI · 21,6s',
  );
  assert.equal(
    chatMetaDisplay({
      providerUsed: 'agy',
      modelUsed: 'gemini-3.8-flash-medium',
      latencyMs: 3200,
    }),
    'AGY CLI · gemini-3.8-flash-medium · 3,2s',
  );
  assert.equal(
    chatMetaDisplay({
      providerUsed: 'deepseek_chat',
      fallbackFrom: 'agy',
      modelUsed: 'deepseek-chat',
      latencyMs: 1800,
    }),
    'DeepSeek (dự phòng từ AGY CLI) · deepseek-chat · 1,8s',
  );
});

test('lastAssistantChatIndex chỉ trỏ vào tin nhắn trợ lý bình thường cuối cùng', () => {
  const msgs = [
    { role: 'user', text: 'Chào bạn' },
    { role: 'assistant', text: 'Xin chào!', followUps: ['Gợi ý 1'] },
    { role: 'user', text: 'Tạo 5 câu Toán 9' },
    { role: 'assistant', text: 'Đây là 5 câu.', followUps: ['Gợi ý 2'] },
    { role: 'assistant', text: 'Cho phép AI', needsAIConsent: true },
  ];
  assert.equal(lastAssistantChatIndex(msgs), 3);
  assert.equal(lastAssistantChatIndex([{ role: 'user', text: 'Hi' }]), -1);
});

test('describeActiveEngine ánh xạ đúng AGY CLI, DeepSeek API, Gemini API và Ollama', () => {
  assert.deepEqual(
    describeActiveEngine({
      fixture: false,
      aiProvider: 'ollama',
      model: 'qwen3:4b',
      config: {
        fixedRouter: {
          enabled: true,
          agyAvailable: true,
          agyModel: 'gemini-pro-orchestrator-neon',
          agyFastModel: 'gemini-3.8-flash-medium',
        },
        deepseek: { hasKey: false },
        gemini: { hasKey: false, freeTierConfirmed: false },
      },
    }),
    {
      destination: 'AGY CLI',
      genModel: 'gemini-pro-orchestrator-neon',
      revModel: 'gemini-3.8-flash-medium',
    },
  );

  assert.equal(
    describeActiveEngine({
      fixture: false,
      aiProvider: 'ollama',
      model: 'qwen3:4b',
      config: {
        fixedRouter: { enabled: true, agyAvailable: false },
        deepseek: { hasKey: true, model: 'deepseek-chat', reasonerModel: 'deepseek-reasoner' },
        gemini: { hasKey: false },
      },
    }).destination,
    'DeepSeek API',
  );

  assert.equal(
    describeActiveEngine({
      fixture: true,
      aiProvider: 'ollama',
      model: 'qwen3:4b',
      reviewer: { provider: 'gemini', model: 'gemini-2.5-flash' },
    }).destination,
    'Ollama trên máy và Gemini API của Google',
  );
});

test('renderAutoCreateCardHTML có nút đóng khi hoàn tất/lỗi và không lặp đoạn tóm tắt dài', () => {
  const runningHtml = renderAutoCreateCardHTML({
    status: 'running',
    running: true,
    statusText: 'Đang sinh…',
    phases: { plan: 'done', swarm: 'running', goal: 'pending', apply: 'pending' },
  });
  assert.ok(!runningHtml.includes('data-action="auto-create-dismiss"'));
  assert.ok(runningHtml.includes('data-action="auto-create-cancel"'));

  const longNote = 'ĐOẠN TÓM TẮT DÀI ĐÃ ĐẨY VÀO BONG BÓNG CHAT';
  const doneHtml = renderAutoCreateCardHTML({
    status: 'complete',
    running: false,
    statusText: 'Hoàn tất',
    phases: { plan: 'done', swarm: 'done', goal: 'done', apply: 'done' },
    complete: {
      message: longNote,
      totalQuestions: 5,
      totalPoints: 10,
      questions: [{}, {}, {}, {}, {}],
    },
  });
  assert.ok(doneHtml.includes('data-status="complete"'));
  assert.ok(doneHtml.includes('data-action="auto-create-dismiss"'));
  assert.ok(doneHtml.includes('Đã áp 5 câu (10 điểm) lên trang A4.'));
  assert.ok(!doneHtml.includes(longNote));
});
