import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

import {
  appState,
  bindGlobalListeners,
  renderJoinScreenHTML,
  renderExamScreenHTML,
  renderResultScreenHTML,
  renderAudioCardHTML,
  handleAudioPlay,
  acknowledgeAudioPlay,
  flushAnswers,
  submitAttempt,
  formatChoiceGroupLabel,
} from '../assets/exam-room.js';
import {
  buildGradingTabHTML,
  buildShellHTML,
  openExamRooms,
  handleExamRoomAction,
} from '../exam-rooms.js';
import {
  renderProactiveCardsHTML,
  openNewReminderModal,
  handleHomeAction,
} from '../home.js';

function resetExamRoomState() {
  appState.screen = 'exam';
  appState.roomCode = 'K7M9P2';
  appState.roomMeta = {
    roomCode: 'K7M9P2',
    title: 'Đề Tin học 12',
    status: 'open',
    mode: 'exam',
    durationMinutes: 45,
    questionCount: 4,
    totalPointsP100: 1000,
    choiceGroups: ['A', 'B'],
  };
  appState.attempt = {
    attemptId: 'att-1',
    variantCode: '101',
    studentName: 'Nguyễn An',
    status: 'in_progress',
    expiresAt: Date.now() + 600_000,
  };
  appState.attemptToken = 'tok-1';
  appState.exam = {
    title: 'Đề Tin học 12',
    questions: [
      { id: 'q1', type: 'mcq', stem: 'Chung 1', options: ['A', 'B', 'C', 'D'], points: 5 },
      { id: 'q2', type: 'mcq', choiceGroup: 'A', stem: 'Nhánh A', options: ['A', 'B', 'C', 'D'], points: 5 },
      { id: 'q3', type: 'mcq', choiceGroup: 'B', stem: 'Nhánh B', options: ['A', 'B', 'C', 'D'], points: 5 },
    ],
  };
  appState.answers = {};
  appState.flagged = new Set();
  appState.currentIndex = 0;
  appState.viewMode = 'all';
  appState.confirmSubmitOpen = false;
  appState.saveState = 'saved';
  appState.saveLabel = 'Đã đồng bộ';
  appState.hadNetworkError = false;
  appState.localAnsweredCount = null;
  appState.error = '';
  appState.warningBanner = '';
  appState.submitting = false;
  appState.result = null;
  appState.audioState = {};
}

test('UV64 Phòng thi: hiển thị nhãn Phần chung / Tự chọn A / Tự chọn B và hướng dẫn làm 1 nhánh', () => {
  resetExamRoomState();
  assert.equal(formatChoiceGroupLabel(''), 'Phần chung');
  assert.equal(formatChoiceGroupLabel('A'), 'Tự chọn A');
  assert.equal(formatChoiceGroupLabel('Tự chọn B'), 'Tự chọn B');

  const joinHtml = renderJoinScreenHTML();
  assert.ok(joinHtml.includes('Thang 10 điểm'));
  assert.ok(joinHtml.includes('Phần chung + 1 trong các hướng tự chọn'));

  const examHtml = renderExamScreenHTML();
  assert.ok(examHtml.includes('data-choice-guide="1"'));
  assert.ok(examHtml.includes('Phần chung'));
  assert.ok(examHtml.includes('Tự chọn A'));
  assert.ok(examHtml.includes('Tự chọn B'));
  assert.ok(examHtml.includes('Chỉ cần làm <strong>Phần chung</strong> + <strong>1 trong các hướng tự chọn</strong>'));
});

test('UV64 Phòng thi: không báo giả Mất mạng khi bỏ trống câu hoặc làm 1 nhánh; Failed to fetch chuyển ngay sang error', async () => {
  resetExamRoomState();
  appState.answers = { q1: 0, q2: 1 }; // chỉ làm 2/3 câu (1 nhánh)
  appState.localAnsweredCount = 2;
  appState.result = {
    studentName: 'Nguyễn An',
    gradingStatus: 'auto_graded',
    resultsAvailable: true,
    totalScoreP100: 1000,
    totalPointsP100: 1000,
    autoScoreP100: 1000,
    manualScoreP100: 0,
    chosenTrack: 'A',
    trackScores: {
      A: { scoreP100: 500, maxPointsP100: 500, answeredCount: 1, questionCount: 1 },
      B: { scoreP100: 0, maxPointsP100: 500, answeredCount: 0, questionCount: 1 },
    },
    syncedAnswerCount: 2,
    totalQuestions: 3,
    questions: [],
  };

  const okHtml = renderResultScreenHTML();
  assert.ok(okHtml.includes('data-sync-status="ok"'));
  assert.ok(okHtml.includes('Đã đồng bộ đầy đủ 2 câu đã trả lời'));
  assert.ok(!okHtml.includes('do mất mạng'));
  assert.ok(okHtml.includes('Hướng tự chọn được tính điểm: Tự chọn A'));

  // Khi thực sự mất câu (synced < localAnsweredCount) -> hiện cảnh báo
  appState.result.syncedAnswerCount = 1;
  const lossHtml = renderResultScreenHTML();
  assert.ok(lossHtml.includes('data-sync-status="loss"'));
  assert.ok(lossHtml.includes('do mất mạng hoặc gián đoạn kết nối'));

  // Khi server báo networkInterrupted -> hiện cảnh báo
  appState.result.syncedAnswerCount = 2;
  appState.result.networkInterrupted = true;
  assert.ok(renderResultScreenHTML().includes('data-sync-status="loss"'));

  // Kiểm tra Failed to fetch ở auto-save & submit chuyển ngay saveState -> 'error'
  const origFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch');
  };
  try {
    resetExamRoomState();
    appState.answers = { q1: 0 };
    await flushAnswers();
    assert.equal(appState.saveState, 'error');
    assert.equal(appState.hadNetworkError, true);
    assert.ok(appState.saveLabel.includes('Mất mạng'));

    appState.saveState = 'saved';
    appState.saveLabel = 'Đã đồng bộ';
    appState.hadNetworkError = false;
    await submitAttempt({ autoSubmit: false });
    assert.equal(appState.saveState, 'error');
    assert.equal(appState.hadNetworkError, true);
    assert.equal(appState.localAnsweredCount, 1);
    assert.ok(appState.saveLabel.includes('Mất mạng'));
  } finally {
    globalThis.fetch = origFetch;
  }
});

test('UV64 Điểm tạm & Hướng dẫn chấm chung: hiện ĐIỂM TẠM khi còn tự luận và khung quy tắc chấm', () => {
  resetExamRoomState();
  appState.localAnsweredCount = 3;
  appState.result = {
    studentName: 'Nguyễn An',
    gradingStatus: 'needs_manual',
    ungradedEssayCount: 2,
    isProvisionalScore: true,
    resultsAvailable: true,
    autoScoreP100: 400,
    manualScoreP100: 0,
    totalScoreP100: 400,
    totalPointsP100: 1000,
    syncedAnswerCount: 3,
    totalQuestions: 3,
    questions: [],
  };
  const provHtml = renderResultScreenHTML();
  assert.ok(provHtml.includes('ĐIỂM TẠM (CHỜ CHẤM TỰ LUẬN)'));
  assert.ok(provHtml.includes('Còn 2 câu tự luận chưa chấm'));

  const gradingHtml = buildGradingTabHTML(
    {
      markingGuidance: 'Trừ 0,25 điểm nếu thiếu đơn vị ở kết quả cuối.',
      pendingCount: 1,
      gradedCount: 0,
      items: [],
    },
    null,
    true,
  );
  assert.ok(gradingHtml.includes('Hướng dẫn chấm chung của đề'));
  assert.ok(gradingHtml.includes('Trừ 0,25 điểm nếu thiếu đơn vị'));

  const erSrc = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../exam-rooms.js'),
    'utf8',
  );
  assert.ok(erSrc.includes('.er-shell .er-tab.is-active:hover:not(:disabled)'));
  assert.ok(erSrc.includes('background: var(--er-teal, #0f4c81);'));
});

test('UV64 Audio 1 lượt: khi playsRemaining về 0 sau tải vẫn giữ <audio controls> cho lượt hiện tại nhờ activePlayback', async () => {
  resetExamRoomState();
  const aud = { fileId: 'aud-1', filename: 'nghe1.mp3', maxPlays: 1, playsUsed: 0, playsRemaining: 1 };
  appState.audioState['aud-1'] = {
    fileId: 'aud-1',
    filename: 'nghe1.mp3',
    url: '/api/rooms/public/attempts/att-1/audio/aud-1',
    blobUrl: '',
    playsUsed: 0,
    playsRemaining: 1,
    maxPlays: 1,
    loading: false,
    activePlayback: false,
    error: '',
  };

  const origFetch = globalThis.fetch;
  const origCreate = URL.createObjectURL;
  const origRevoke = URL.revokeObjectURL;
  URL.createObjectURL = () => 'blob:mock-audio-1';
  URL.revokeObjectURL = () => {};
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    headers: new Headers({
      'X-Audio-Plays-Used': '1',
      'X-Audio-Plays-Remaining': '0',
      'X-Audio-Max-Plays': '1',
    }),
    blob: async () => new Blob(['FAKE_MP3'], { type: 'audio/mpeg' }),
  });

  try {
    await handleAudioPlay('aud-1');
    const st = appState.audioState['aud-1'];
    assert.equal(st.playsRemaining, 0);
    assert.equal(st.activePlayback, true);
    assert.equal(st.blobUrl, 'blob:mock-audio-1');

    const playingHtml = renderAudioCardHTML(aud);
    assert.ok(playingHtml.includes('<audio class="sr-audio-el" controls autoplay src="blob:mock-audio-1"></audio>'));
    assert.ok(playingHtml.includes('disabled'));

    // Kiểm tra listener play & ended qua fake DOM
    const docListeners = {};
    const winListeners = {};
    const fakeRoot = {
      id: 'student-room-app',
      innerHTML: '',
      addEventListener: () => {},
      querySelector: () => null,
      querySelectorAll: () => [],
    };
    const origDocument = globalThis.document;
    const origWindow = globalThis.window;
    globalThis.document = {
      getElementById: (id) => (id === 'student-room-app' ? fakeRoot : null),
      addEventListener: (ev, fn) => {
        docListeners[ev] = fn;
      },
      querySelector: () => null,
      querySelectorAll: () => [],
    };
    globalThis.window = {
      addEventListener: (ev, fn) => {
        winListeners[ev] = fn;
      },
    };
    try {
      bindGlobalListeners();
      let pausedCalled = false;
      let removedControls = false;
      const fakeCard = { dataset: { audioBox: 'aud-1' } };
      const fakeAudio = {
        tagName: 'AUDIO',
        matches: (sel) => sel.includes('audio'),
        closest: (sel) => (sel === '[data-audio-box]' ? fakeCard : null),
        pause: () => {
          pausedCalled = true;
        },
        currentTime: 5,
        src: 'blob:mock-audio-1',
        removeAttribute: (attr) => {
          if (attr === 'controls') removedControls = true;
        },
      };

      // Trong khi activePlayback === true, sự kiện play KHÔNG được chặn hoặc pause
      let prevented = false;
      docListeners.play({
        target: fakeAudio,
        preventDefault: () => {
          prevented = true;
        },
        stopPropagation: () => {},
      });
      assert.equal(prevented, false);
      assert.equal(pausedCalled, false);

      // Khi kết thúc lượt (ended), tắt activePlayback = false, khóa audio & render lại
      docListeners.ended({ target: fakeAudio });
      assert.equal(st.activePlayback, false);
      assert.equal(removedControls, true);
      assert.equal(st.blobUrl, '');

      // Sau khi ended, cố bấm play lần nữa PHẢI bị chặn
      docListeners.play({
        target: fakeAudio,
        preventDefault: () => {
          prevented = true;
        },
        stopPropagation: () => {},
      });
      assert.equal(prevented, true);
      assert.equal(pausedCalled, true);
    } finally {
      globalThis.document = origDocument;
      globalThis.window = origWindow;
    }

    const endedHtml = renderAudioCardHTML(aud);
    assert.ok(!endedHtml.includes('<audio'));
  } finally {
    globalThis.fetch = origFetch;
    URL.createObjectURL = origCreate;
    URL.revokeObjectURL = origRevoke;
  }
});

test('Gói 1 Phòng thi: Đứt mạng body WAV rỗng, pendingLeaseId sau tải lại và retry /ack', async () => {
  resetExamRoomState();
  const aud = {
    fileId: 'aud-empty',
    filename: 'nghe_empty.wav',
    maxPlays: 1,
    playsUsed: 0,
    playsRemaining: 1,
    pendingLeaseId: 'lease-pending-1',
  };
  const pendingHtml = renderAudioCardHTML(aud);
  assert.ok(pendingHtml.includes('Tải lại lượt nghe (chưa trừ lượt)'));

  appState.audioState['aud-empty'] = {
    fileId: 'aud-empty',
    filename: 'nghe_empty.wav',
    url: '/api/rooms/public/attempts/att-2/audio/aud-empty',
    blobUrl: '',
    playsUsed: 0,
    playsRemaining: 1,
    maxPlays: 1,
    activeLeaseId: 'lease-pending-1',
    leaseAcked: false,
    loading: false,
    activePlayback: false,
    error: '',
  };

  const origFetch = globalThis.fetch;
  const origCreate = URL.createObjectURL;
  const origRevoke = URL.revokeObjectURL;
  URL.createObjectURL = () => 'blob:mock-empty-ok';
  URL.revokeObjectURL = () => {};

  let step = 0;
  globalThis.fetch = async (url) => {
    step += 1;
    if (step === 1) {
      assert.ok(String(url).includes('leaseId=lease-pending-1'));
      return {
        ok: true,
        status: 200,
        headers: new Headers({
          'X-Audio-Plays-Used': '1',
          'X-Audio-Plays-Remaining': '0',
          'X-Audio-Max-Plays': '1',
          'X-Audio-Lease-Id': 'lease-pending-1',
        }),
        blob: async () => new Blob([], { type: 'audio/wav' }),
      };
    }
    if (step === 2) {
      return {
        ok: true,
        status: 200,
        headers: new Headers({
          'X-Audio-Plays-Used': '1',
          'X-Audio-Plays-Remaining': '0',
          'X-Audio-Max-Plays': '1',
          'X-Audio-Lease-Id': 'lease-pending-1',
        }),
        blob: async () => new Blob(['RIFFWAV'], { type: 'audio/wav' }),
      };
    }
    if (step === 3) {
      throw new TypeError('Failed to fetch');
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ playsUsed: 1, playsRemaining: 0, maxPlays: 1, acknowledged: true }),
    };
  };

  try {
    // Lần 1: body rỗng do rớt mạng -> giữ nguyên playsRemaining = 1
    await handleAudioPlay('aud-empty');
    const st = appState.audioState['aud-empty'];
    assert.equal(st.playsRemaining, 1);
    assert.equal(st.activePlayback, false);
    assert.ok(st.error.includes('Lượt nghe chưa bị trừ'));

    // Lần 2: tải lại thành công
    await handleAudioPlay('aud-empty');
    assert.equal(st.blobUrl, 'blob:mock-empty-ok');
    assert.equal(st.activePlayback, true);

    // Lần 3: /ack rớt mạng -> reset leaseAcked = false để thử lại được
    await acknowledgeAudioPlay('aud-empty');
    assert.equal(st.leaseAcked, false);

    // Lần 4: /ack thành công -> xóa activeLeaseId và cập nhật 0 lượt còn lại
    await acknowledgeAudioPlay('aud-empty');
    assert.equal(st.leaseAcked, true);
    assert.equal(st.activeLeaseId, '');
    assert.equal(st.playsUsed, 1);
    assert.equal(st.playsRemaining, 0);
  } finally {
    globalThis.fetch = origFetch;
    URL.createObjectURL = origCreate;
    URL.revokeObjectURL = origRevoke;
  }
});

test('UV64 Nhắc lịch PATCH 503 báo lỗi trung thực, chọn đề và nút Mở đề trên thẻ nhắc lịch', async () => {
  const cardsHtml = renderProactiveCardsHTML(
    {
      activeCampaigns: [],
      nextDayReviewNudges: [],
      urgentDeadlines: [
        {
          id: 'rem-1',
          source: 'reminder',
          title: 'Kiểm tra đáp án trước khi in',
          kind: 'review',
          targetType: 'exam',
          targetId: 'ex-9',
          targetTitle: 'Đề Toán 9 Ôn Tập',
          dueAt: Date.now() + 3_600_000,
          overdue: false,
          message: 'Sắp đến hạn: Kiểm tra đáp án trước khi in',
        },
      ],
      pendingRoomGrading: { count: 0, rooms: [] },
    },
    { exams: [{ id: 'ex-9', title: 'Đề Toán 9 Ôn Tập' }] },
  );
  assert.ok(cardsHtml.includes('Đề gắn kèm:</strong> Đề Toán 9 Ôn Tập'));
  assert.ok(cardsHtml.includes('data-action="home-open-exam" data-id="ex-9">Mở đề</button>'));

  // Kiểm tra modal tạo nhắc lịch có select chọn đề
  let modalBody = '';
  const modalCtx = {
    exam: () => ({ id: 'ex-9', title: 'Đề Toán 9 Ôn Tập' }),
    getState: () => ({
      exams: [
        { id: 'ex-9', title: 'Đề Toán 9 Ôn Tập' },
        { id: 'ex-10', title: 'Đề Ngữ văn 10' },
      ],
    }),
    modal: (_title, body) => {
      modalBody = body;
    },
  };
  openNewReminderModal(modalCtx);
  assert.ok(modalBody.includes('<select name="targetId">'));
  assert.ok(modalBody.includes('value="ex-9" selected'));
  assert.ok(modalBody.includes('Đề Ngữ văn 10'));

  // Kiểm tra PATCH 503 và network error không toast thành công và không xóa thẻ
  const origFetch = globalThis.fetch;
  const toasts = [];
  let openedExamId = '';
  const ctx = {
    workspaceHeaders: () => ({}),
    toast: (msg) => toasts.push(msg),
    getState: () => ({ exams: [{ id: 'ex-9', title: 'Đề Toán 9 Ôn Tập' }] }),
    openExamInWorkspace: (id) => {
      openedExamId = id;
    },
  };
  const fakeNode = { dataset: { id: 'rem-1', hours: '4' } };

  try {
    // 503 Service Unavailable trên done
    globalThis.fetch = async () => ({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Máy chủ tạm bận' }),
    });
    await handleHomeAction('proactive-done-reminder', fakeNode, ctx);
    assert.equal(toasts.length, 1);
    assert.ok(toasts[0].includes('503') && !toasts[0].includes('Đã đánh dấu hoàn thành'));

    // Lỗi mạng trên snooze
    toasts.length = 0;
    globalThis.fetch = async () => {
      throw new TypeError('Failed to fetch');
    };
    await handleHomeAction('proactive-snooze-reminder', fakeNode, ctx);
    assert.equal(toasts.length, 1);
    assert.ok(toasts[0].includes('Không thể kết nối') && !toasts[0].includes('Đã hoãn nhắc lịch'));

    // Mở đề gắn kèm
    await handleHomeAction('home-open-exam', { dataset: { id: 'ex-9' } }, ctx);
    assert.equal(openedExamId, 'ex-9');
  } finally {
    globalThis.fetch = origFetch;
  }
});

test('Gói 1 Phòng thi: Audio lease retry khi đứt mạng giữa đường, điều chỉnh tổng bài và UI nộp bài/kết quả', async () => {
  resetExamRoomState();
  const aud = { fileId: 'aud-drop', filename: 'nghe_drop.wav', maxPlays: 1, playsUsed: 0, playsRemaining: 1 };
  appState.audioState['aud-drop'] = {
    fileId: 'aud-drop',
    filename: 'nghe_drop.wav',
    url: '/api/rooms/public/attempts/att-1/audio/aud-drop',
    blobUrl: '',
    playsUsed: 0,
    playsRemaining: 1,
    maxPlays: 1,
    activeLeaseId: '',
    leaseAcked: false,
    loading: false,
    activePlayback: false,
    error: '',
  };

  const origFetch = globalThis.fetch;
  const origCreate = URL.createObjectURL;
  const origRevoke = URL.revokeObjectURL;
  URL.createObjectURL = () => 'blob:mock-drop-ok';
  URL.revokeObjectURL = () => {};

  let callNo = 0;
  globalThis.fetch = async (url) => {
    callNo += 1;
    if (callNo === 1) {
      assert.ok(String(url).includes('lease=1'));
      return {
        ok: true,
        status: 200,
        headers: new Headers({
          'X-Audio-Plays-Used': '1',
          'X-Audio-Plays-Remaining': '0',
          'X-Audio-Max-Plays': '1',
          'X-Audio-Lease-Id': 'lease-xyz',
        }),
        blob: async () => {
          throw new TypeError('Failed to fetch');
        },
      };
    }
    return {
      ok: true,
      status: 200,
      headers: new Headers({
        'X-Audio-Plays-Used': '1',
        'X-Audio-Plays-Remaining': '0',
        'X-Audio-Max-Plays': '1',
        'X-Audio-Lease-Id': 'lease-xyz',
      }),
      blob: async () => new Blob(['WAV'], { type: 'audio/wav' }),
    };
  };

  try {
    // Lần 1: đứt mạng khi đọc body -> playsRemaining vẫn là 1, không hiện Failed to fetch thô
    await handleAudioPlay('aud-drop');
    const st = appState.audioState['aud-drop'];
    assert.equal(st.playsRemaining, 1);
    assert.equal(st.playsUsed, 0);
    assert.equal(st.activePlayback, false);
    assert.ok(!st.error.includes('Failed to fetch'));
    assert.ok(st.error.includes('Lượt nghe chưa bị trừ'));

    // Lần 2: tải lại thành công và giữ được audio tag
    await handleAudioPlay('aud-drop');
    assert.equal(st.blobUrl, 'blob:mock-drop-ok');
    assert.equal(st.activeLeaseId, 'lease-xyz');
    assert.equal(st.activePlayback, true);

    // Hiển thị điều chỉnh tổng bài trên màn kết quả HS (5 + 5 - 0,25 = 9,75)
    appState.result = {
      studentName: 'Lê Minh',
      gradingStatus: 'graded',
      resultsAvailable: true,
      autoScoreP100: 0,
      manualScoreP100: 1000,
      scoreAdjustmentP100: -25,
      adjustmentNote: 'Thiếu đơn vị toàn bài',
      totalScoreP100: 975,
      totalPointsP100: 1000,
      syncedAnswerCount: 2,
      totalQuestions: 2,
      questions: [],
    };
    const resHtml = renderResultScreenHTML();
    assert.ok(resHtml.includes('9,75 / 10'));
    assert.ok(resHtml.includes('Điều chỉnh toàn bài: -0,25 điểm'));
    assert.ok(resHtml.includes('Thiếu đơn vị toàn bài'));

    // Pill nhảy tới câu bỏ trống trong xác nhận nộp bài
    appState.confirmSubmitOpen = true;
    appState.answers = {};
    const confirmHtml = renderExamScreenHTML();
    assert.ok(confirmHtml.includes('data-unanswered-pills="1"'));
    assert.ok(confirmHtml.includes('Em còn 3 câu chưa làm'));

    // Form điều chỉnh tổng điểm trong tab Chấm tự luận GV
    const gradingHtml = buildGradingTabHTML(
      {
        markingGuidance: '',
        pendingCount: 0,
        gradedCount: 2,
        attempts: [
          {
            attemptId: 'att-1',
            studentName: 'Lê Minh',
            studentClass: '11A1',
            scoreAdjustmentP100: -25,
            adjustmentNote: 'Thiếu đơn vị',
            totalScoreP100: 975,
            totalPointsP100: 1000,
            isProvisionalScore: false,
          },
        ],
        items: [],
      },
      null,
      true,
    );
    assert.ok(gradingHtml.includes('class="er-adjust-form"'));
    assert.ok(gradingHtml.includes('9,75 / 10'));
  } finally {
    globalThis.fetch = origFetch;
    URL.createObjectURL = origCreate;
    URL.revokeObjectURL = origRevoke;
  }
});

test('t5 Mở chiến dịch sắp đến hạn hiển thị đúng chi tiết và giữ nguyên kho đề', async (t) => {
  const campaign = {
    id: 'anh-8',
    title: 'Bộ đề Tiếng Anh 8',
    subject: 'Tiếng Anh',
    grade: '8',
    completedCount: 2,
    targetCount: 4,
    nextOrdinal: 3,
    dueAt: Date.now() + 3_600_000,
  };
  const digest = {
    activeCampaigns: [{...campaign, id: 'toan-10', title: 'Bộ đề Toán 10', subject: 'Toán', grade: '10'}, campaign],
    urgentDeadlines: [{id: campaign.id, source: 'campaign', title: campaign.title, dueAt: campaign.dueAt}],
  };
  const html = renderProactiveCardsHTML(digest);
  const [, action, id] = html.match(/data-action="([^"]+)" data-id="([^"]+)"[^>]*>Mở chiến dịch<\/button>/);
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => ({ok: true, json: async () => digest}));
  const ctx = {
    modal: t.mock.fn(),
    createBlankExamForHome: t.mock.fn(() => ({id: 'unexpected-draft'})),
    onAutoCreateExam: t.mock.fn(),
  };

  assert.equal(await handleHomeAction(action, {dataset: {id, title: campaign.title}}, ctx), true);
  assert.equal(ctx.createBlankExamForHome.mock.callCount(), 0);
  assert.equal(ctx.onAutoCreateExam.mock.callCount(), 0);
  assert.deepEqual(fetchMock.mock.calls.map(({arguments: [url, init]}) => [url, init?.method ?? 'GET']), [
    ['/api/proactive/digest', 'GET'],
  ]);
  assert.equal(ctx.modal.mock.callCount(), 1);
  const body = ctx.modal.mock.calls[0].arguments[1];
  assert.match(body, /Bộ đề Tiếng Anh 8/);
  assert.match(body, /Tiếng Anh · Lớp 8/);
  assert.match(body, /2\/4 đề/);
  assert.match(body, /Hạn:/);
  assert.match(body, /Soạn tiếp đề 3/);
  assert.doesNotMatch(body, /Bộ đề Toán 10/);
});

test('t5 Trang chủ & Trợ lý Chủ động: hoàn thành/lưu trữ chiến dịch gọi PATCH /api/campaigns/{id} và không dùng !important trong home.js', async () => {
  const homeSrc = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../home.js'),
    'utf8',
  );
  assert.ok(!homeSrc.includes('!important'), 'home.js không được chứa !important');

  const campHtml = renderProactiveCardsHTML({
    activeCampaigns: [
      {
        id: 'camp-1',
        title: 'Bộ 5 đề Toán 10',
        subject: 'Toán',
        grade: '10',
        completedCount: 5,
        targetCount: 5,
        nextOrdinal: 6,
      },
    ],
    nextDayReviewNudges: [],
    urgentDeadlines: [],
    pendingRoomGrading: {count: 0, rooms: []},
  });
  assert.ok(campHtml.includes('data-action="proactive-complete-campaign"'));
  assert.ok(campHtml.includes('data-action="proactive-archive-campaign"'));
  assert.ok(campHtml.includes('Toán · Lớp 10'));

  const origFetch = globalThis.fetch;
  const calls = [];
  const toasts = [];
  const ctx = {
    workspaceHeaders: () => ({}),
    toast: (msg) => toasts.push(msg),
    getState: () => ({exams: []}),
  };
  try {
    globalThis.fetch = async (url, init) => {
      calls.push({url: String(url), method: init?.method, body: init?.body});
      return {ok: true, status: 200, json: async () => ({badgeCount: 0, activeCampaigns: [], nextDayReviewNudges: [], urgentDeadlines: [], pendingRoomGrading: {count: 0, rooms: []}})};
    };
    await handleHomeAction('proactive-complete-campaign', {dataset: {id: 'camp-1'}}, ctx);
    assert.equal(calls[0].url, '/api/campaigns/camp-1');
    assert.equal(calls[0].method, 'PATCH');
    assert.deepEqual(JSON.parse(calls[0].body), {status: 'completed'});
    assert.ok(toasts.at(-1).includes('hoàn thành'));

    await handleHomeAction('proactive-archive-campaign', {dataset: {id: 'camp-1'}}, ctx);
    assert.deepEqual(JSON.parse(calls[2].body), {status: 'archived'});
    assert.ok(toasts.at(-1).includes('lưu trữ'));
  } finally {
    globalThis.fetch = origFetch;
  }
});

function createFakeRoomsDom({ includeLayer2 = true } = {}) {
  const docListeners = new Map();
  const fakeDoc = {
    hidden: false,
    visibilityState: 'visible',
    activeElement: null,
    head: { appendChild: () => {} },
    body: { tagName: 'BODY' },
    createElement: (tag) => makeEl(tag, ''),
    addEventListener: (ev, fn) => {
      if (!docListeners.has(ev)) docListeners.set(ev, new Set());
      docListeners.get(ev).add(fn);
    },
    removeEventListener: (ev, fn) => {
      docListeners.get(ev)?.delete(fn);
    },
    dispatchEvent: (ev) => {
      for (const fn of [...(docListeners.get(ev.type) || [])]) {
        fn(ev);
      }
      return true;
    },
    getListenerCount: (ev) => docListeners.get(ev)?.size || 0,
  };
  fakeDoc.activeElement = fakeDoc.body;

  function makeEl(tagName, id = '') {
    const listeners = new Map();
    const attrs = new Map();
    let html = '';
    const el = {
      tagName: tagName.toUpperCase(),
      id,
      dataset: {},
      className: '',
      disabled: false,
      checked: true,
      open: false,
      scrollTop: 0,
      scrollLeft: 0,
      isConnected: true,
      parentElement: null,
      children: [],
      style: {},
      focusCalls: [],
      classList: {
        contains: (cls) => String(el.className || '').split(/\s+/).includes(cls),
      },
      setAttribute: (k, v) => attrs.set(k, String(v)),
      getAttribute: (k) => (attrs.has(k) ? attrs.get(k) : null),
      removeAttribute: (k) => attrs.delete(k),
      addEventListener: (ev, fn) => {
        if (!listeners.has(ev)) listeners.set(ev, new Set());
        listeners.get(ev).add(fn);
      },
      removeEventListener: (ev, fn) => {
        listeners.get(ev)?.delete(fn);
      },
      dispatchEvent: (ev) => {
        const event = {
          preventDefault: () => {
            event.defaultPrevented = true;
          },
          stopPropagation: () => {
            event.propagationStopped = true;
          },
          target: el,
          ...ev,
        };
        for (const fn of [...(listeners.get(event.type) || [])]) {
          fn(event);
        }
        return !event.defaultPrevented;
      },
      focus: (opts) => {
        el.focusCalls.push(opts || null);
        fakeDoc.activeElement = el;
      },
      contains: (node) => {
        let cur = node;
        while (cur) {
          if (cur === el) return true;
          cur = cur.parentElement;
        }
        return false;
      },
      closest: (sel) => {
        let cur = el;
        while (cur) {
          if (matchesSimple(cur, sel)) return cur;
          cur = cur.parentElement;
        }
        return null;
      },
      querySelector: (sel) => el.querySelectorAll(sel)[0] || null,
      querySelectorAll: () => [],
      close: () => {
        el.open = false;
        el.dispatchEvent({ type: 'close' });
      },
      showModal: () => {
        el.open = true;
      },
    };
    Object.defineProperty(el, 'innerHTML', {
      get: () => html,
      set: (val) => {
        html = String(val || '');
        if (el._onHtmlChange) el._onHtmlChange(html);
      },
    });
    return el;
  }

  function matchesSimple(node, selector) {
    return selector
      .split(',')
      .map((s) => s.trim())
      .some((part) => {
        if (part.startsWith('#')) return node.id === part.slice(1);
        if (part.includes('[data-er-action="lock-attempt"]')) {
          return (
            node.dataset?.erAction === 'lock-attempt' &&
            (!part.includes('data-attempt-id') ||
              part.includes(`"${node.dataset.attemptId}"`))
          );
        }
        if (part.includes('[data-er-action="delete-room"]')) {
          return node.dataset?.erAction === 'delete-room';
        }
        if (part.includes('[data-er-action="switch-tab"]')) {
          return (
            node.dataset?.erAction === 'switch-tab' &&
            (!part.includes('data-tab') || part.includes(`"${node.dataset.tab}"`))
          );
        }
        if (part.includes('[data-er-action="select-room"]')) {
          return node.dataset?.erAction === 'select-room' && (!part.includes('.is-active') || node.classList.contains('is-active'));
        }
        if (part.includes('[data-er-action="scope-filter"]')) {
          return (
            node.dataset?.erAction === 'scope-filter' &&
            (!part.includes('data-scope') || part.includes(`"${node.dataset.scope}"`))
          );
        }
        if (part.includes('[data-er-action]')) return Boolean(node.dataset?.erAction);
        if (part === '[role="tab"][aria-selected="true"]') {
          return node.getAttribute('role') === 'tab' && node.getAttribute('aria-selected') === 'true';
        }
        if (part.includes('.er-tabs')) return node.classList.contains('er-tabs');
        return false;
      });
  }

  const dialog = makeEl('dialog', 'dialog');
  const modalBody = makeEl('div', '');
  modalBody.className = 'modal-body';
  modalBody.parentElement = dialog;
  const dialogLayer2 = includeLayer2 ? makeEl('dialog', 'dialog-layer2') : null;

  const elements = new Map([
    ['dialog', dialog],
    ['exam-rooms-shell', null],
    ['er-monitor-badges', null],
    ['er-monitor-results', null],
    ['er-autorefresh-chk', null],
    ['er-cancel-delete-btn', null],
    ['er-confirm-delete-btn', null],
    ['er-cancel-inline-delete-btn', null],
    ['er-confirm-inline-delete-btn', null],
  ]);
  if (dialogLayer2) elements.set('dialog-layer2', dialogLayer2);

  let shellEl = null;
  let tabsEl = null;
  let tabEls = [];
  let monitorBadgesEl = null;
  let monitorResultsEl = null;
  let tableWrapEl = null;
  let autorefreshChk = null;
  let lockAttemptBtns = [];
  let deleteBtn = null;
  let inlineCancelBtn = null;
  let inlineConfirmBtn = null;
  let activePillBtn = null;
  let scopeFilterBtns = [];
  let quickOpenBtn = null;
  let layer2CancelBtn = null;
  let layer2ConfirmBtn = null;
  let layer2ConfirmBox = null;

  function parseHtmlIntoDom(html) {
    if (!html.includes('id="exam-rooms-shell"')) return;
    shellEl = makeEl('div', 'exam-rooms-shell');
    shellEl.className = 'er-shell';
    shellEl.parentElement = modalBody;
    elements.set('exam-rooms-shell', shellEl);

    quickOpenBtn = makeEl('button', 'er-quick-open-btn');
    quickOpenBtn.dataset = { erAction: 'quick-open' };
    quickOpenBtn.parentElement = shellEl;
    elements.set('er-quick-open-btn', quickOpenBtn);

    scopeFilterBtns = [];
    const scopeMatches = [
      ...html.matchAll(/data-er-action="scope-filter"[^>]*data-scope="([^"]+)"/g),
    ];
    for (const m of scopeMatches) {
      const sb = makeEl('button', '');
      sb.dataset = { erAction: 'scope-filter', scope: m[1] };
      sb.parentElement = shellEl;
      scopeFilterBtns.push(sb);
    }

    const activeRoomMatch = html.match(/class="er-room-pill is-active"[^>]*data-room-id="([^"]+)"/);
    if (activeRoomMatch) {
      activePillBtn = makeEl('button', '');
      activePillBtn.className = 'er-room-pill is-active';
      activePillBtn.dataset = { erAction: 'select-room', roomId: activeRoomMatch[1] };
      activePillBtn.parentElement = shellEl;
    } else {
      activePillBtn = null;
    }

    tabsEl = makeEl('div', '');
    tabsEl.className = 'er-tabs';
    tabsEl.parentElement = shellEl;
    tabEls = [];
    const tabMatches = [
      ...html.matchAll(
        /<button[^>]*id="er-tab-([^"]+)"[^>]*aria-selected="(true|false)"[^>]*data-tab="([^"]+)"[^>]*>([^<]*)<\/button>/g,
      ),
    ];
    for (const m of tabMatches) {
      const tb = makeEl('button', `er-tab-${m[1]}`);
      tb.className = m[2] === 'true' ? 'er-tab is-active' : 'er-tab';
      tb.setAttribute('role', 'tab');
      tb.setAttribute('aria-selected', m[2]);
      tb.dataset = { erAction: 'switch-tab', tab: m[3] };
      tb.textContent = m[4];
      tb.parentElement = tabsEl;
      tabEls.push(tb);
      elements.set(tb.id, tb);
    }

    if (html.includes('data-er-action="delete-room"')) {
      deleteBtn = makeEl('button', '');
      deleteBtn.dataset = { erAction: 'delete-room' };
      deleteBtn.parentElement = shellEl;
    } else {
      deleteBtn = null;
    }

    if (html.includes('id="er-cancel-inline-delete-btn"')) {
      inlineCancelBtn = makeEl('button', 'er-cancel-inline-delete-btn');
      inlineCancelBtn.dataset = { erAction: 'cancel-delete-room' };
      inlineCancelBtn.parentElement = shellEl;
      const mId = html.match(/id="er-confirm-inline-delete-btn"[^>]*data-room-id="([^"]+)"/);
      inlineConfirmBtn = makeEl('button', 'er-confirm-inline-delete-btn');
      inlineConfirmBtn.dataset = { erAction: 'confirm-delete-room', roomId: mId?.[1] || '' };
      inlineConfirmBtn.parentElement = shellEl;
      elements.set('er-cancel-inline-delete-btn', inlineCancelBtn);
      elements.set('er-confirm-inline-delete-btn', inlineConfirmBtn);
    } else {
      inlineCancelBtn = null;
      inlineConfirmBtn = null;
      elements.set('er-cancel-inline-delete-btn', null);
      elements.set('er-confirm-inline-delete-btn', null);
    }

    if (html.includes('id="er-monitor-results"')) {
      monitorBadgesEl = makeEl('div', 'er-monitor-badges');
      monitorBadgesEl.parentElement = shellEl;
      autorefreshChk = makeEl('input', 'er-autorefresh-chk');
      autorefreshChk.parentElement = shellEl;
      monitorResultsEl = makeEl('div', 'er-monitor-results');
      monitorResultsEl.parentElement = shellEl;
      elements.set('er-monitor-badges', monitorBadgesEl);
      elements.set('er-monitor-results', monitorResultsEl);
      elements.set('er-autorefresh-chk', autorefreshChk);
      monitorBadgesEl._onHtmlChange = () => {};
      monitorResultsEl._onHtmlChange = (inner) => syncMonitorResults(inner);
      syncMonitorResults(html);
    } else {
      monitorBadgesEl = null;
      monitorResultsEl = null;
      tableWrapEl = null;
      autorefreshChk = null;
      lockAttemptBtns = [];
      elements.set('er-monitor-badges', null);
      elements.set('er-monitor-results', null);
      elements.set('er-autorefresh-chk', null);
    }

    shellEl.querySelector = (sel) => shellEl.querySelectorAll(sel)[0] || null;
    shellEl.querySelectorAll = (sel) => {
      const candidates = [
        ...tabEls,
        ...(activePillBtn ? [activePillBtn] : []),
        ...scopeFilterBtns,
        ...(quickOpenBtn ? [quickOpenBtn] : []),
        ...(deleteBtn ? [deleteBtn] : []),
        ...(autorefreshChk ? [autorefreshChk] : []),
        ...(tableWrapEl ? [tableWrapEl] : []),
        ...lockAttemptBtns,
        ...(inlineCancelBtn ? [inlineCancelBtn] : []),
        ...(inlineConfirmBtn ? [inlineConfirmBtn] : []),
      ];
      if (sel === '.er-table-wrap') return tableWrapEl ? [tableWrapEl] : [];
      if (sel === '.er-tabs [role="tab"][data-er-action="switch-tab"]') return tabEls;
      return candidates.filter((n) => matchesSimple(n, sel));
    };
    modalBody.querySelector = (sel) => shellEl?.querySelector(sel) || null;
    modalBody.querySelectorAll = (sel) => shellEl?.querySelectorAll(sel) || [];
  }

  function syncMonitorResults(inner) {
    if (!monitorResultsEl) return;
    if (inner.includes('class="er-table-wrap"')) {
      tableWrapEl = makeEl('div', '');
      tableWrapEl.className = 'er-table-wrap';
      tableWrapEl.parentElement = monitorResultsEl;
    } else {
      tableWrapEl = null;
    }
    lockAttemptBtns = [];
    const attMatches = [
      ...inner.matchAll(/data-er-action="lock-attempt" data-attempt-id="([^"]+)"/g),
    ];
    for (const m of attMatches) {
      const b = makeEl('button', '');
      b.dataset = { erAction: 'lock-attempt', attemptId: m[1] };
      b.parentElement = tableWrapEl || monitorResultsEl;
      lockAttemptBtns.push(b);
    }
    monitorResultsEl.querySelector = (sel) => monitorResultsEl.querySelectorAll(sel)[0] || null;
    monitorResultsEl.querySelectorAll = (sel) => {
      const list = [...(tableWrapEl ? [tableWrapEl] : []), ...lockAttemptBtns];
      if (sel === '.er-table-wrap') return tableWrapEl ? [tableWrapEl] : [];
      return list.filter((n) => matchesSimple(n, sel));
    };
  }

  modalBody._onHtmlChange = parseHtmlIntoDom;

  if (dialogLayer2) {
    dialogLayer2._onHtmlChange = (inner) => {
      if (inner.includes('id="er-cancel-delete-btn"')) {
        layer2ConfirmBox = makeEl('div', '');
        layer2ConfirmBox.className = 'er-confirm-delete';
        layer2ConfirmBox.parentElement = dialogLayer2;
        layer2CancelBtn = makeEl('button', 'er-cancel-delete-btn');
        layer2CancelBtn.dataset = { action: 'close-top-modal' };
        layer2CancelBtn.parentElement = layer2ConfirmBox;
        const mId = inner.match(/id="er-confirm-delete-btn"[^>]*data-room-id="([^"]+)"/);
        layer2ConfirmBtn = makeEl('button', 'er-confirm-delete-btn');
        layer2ConfirmBtn.dataset = { action: 'er-confirm-delete-room', roomId: mId?.[1] || '' };
        layer2ConfirmBtn.parentElement = layer2ConfirmBox;
        elements.set('er-cancel-delete-btn', layer2CancelBtn);
        elements.set('er-confirm-delete-btn', layer2ConfirmBtn);
        layer2ConfirmBox.querySelectorAll = (sel) => {
          if (sel.includes('button')) return [layer2CancelBtn, layer2ConfirmBtn];
          return [];
        };
        dialogLayer2.querySelector = (sel) =>
          sel === '.er-confirm-delete' ? layer2ConfirmBox : null;
      } else {
        layer2ConfirmBox = null;
        layer2CancelBtn = null;
        layer2ConfirmBtn = null;
        elements.set('er-cancel-delete-btn', null);
        elements.set('er-confirm-delete-btn', null);
      }
    };
  }

  fakeDoc.getElementById = (id) => elements.get(id) || null;
  fakeDoc.querySelector = () => null;
  fakeDoc.querySelectorAll = () => [];

  return {
    fakeDoc,
    dialog,
    dialogLayer2,
    modalBody,
    getShell: () => shellEl,
    getTab: (tab) => tabEls.find((t) => t.dataset.tab === tab) || null,
    getScopeFilterBtn: (scope) => scopeFilterBtns.find((b) => b.dataset.scope === scope) || null,
    getDeleteBtn: () => deleteBtn,
    getAutorefreshChk: () => autorefreshChk,
    getTableWrap: () => tableWrapEl,
    getLockBtn: (attId) => lockAttemptBtns.find((b) => b.dataset.attemptId === attId) || null,
    getLayer2CancelBtn: () => layer2CancelBtn,
    getLayer2ConfirmBtn: () => layer2ConfirmBtn,
    getInlineCancelBtn: () => inlineCancelBtn,
    getInlineConfirmBtn: () => inlineConfirmBtn,
  };
}

test('t4 Phòng thi · tablist ARIA, bỏ window.confirm và hộp thoại xác nhận xóa bàn phím', async () => {
  const erSrc = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../exam-rooms.js'),
    'utf8',
  );
  assert.ok(!erSrc.includes('window.confirm'), 'exam-rooms.js không được dùng window.confirm');
  assert.ok(erSrc.includes('role="tablist"') && erSrc.includes('role="tab"'));
  assert.ok(erSrc.includes('aria-selected') && erSrc.includes('role="tabpanel"'));
  assert.ok(erSrc.includes('document.hidden') && erSrc.includes('visibilitychange'));

  const origDocument = globalThis.document;
  const origWindow = globalThis.window;
  const origFetch = globalThis.fetch;
  const origCreateObj = URL.createObjectURL;
  const origRevokeObj = URL.revokeObjectURL;

  const dom = createFakeRoomsDom({ includeLayer2: true });
  let confirmCalled = false;
  let rooms = [
    {
      id: 'room-1',
      examId: 'ex-1',
      roomCode: 'ABC123',
      title: 'Phòng thi Toán 9',
      status: 'open',
      mode: 'exam',
      attemptCount: 2,
      needsManualCount: 0,
      questionCount: 2,
      totalPointsP100: 1000,
    },
  ];
  const deleteCalls = [];
  const modalCalls = [];
  const toasts = [];

  globalThis.document = dom.fakeDoc;
  globalThis.window = {
    confirm: () => {
      confirmCalled = true;
      return true;
    },
  };
  URL.createObjectURL = () => 'blob:qr-mock';
  URL.revokeObjectURL = () => {};
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    const method = (init.method || 'GET').toUpperCase();
    if (u === '/api/rooms' && method === 'GET') {
      return { ok: true, status: 200, json: async () => ({ rooms }) };
    }
    if (u === '/api/exports/preflight') {
      return { ok: true, status: 200, json: async () => ({ ready: true, blockingIssues: [] }) };
    }
    if (u.includes('/qr.svg')) {
      return { ok: true, status: 200, blob: async () => new Blob(['<svg></svg>'], { type: 'image/svg+xml' }) };
    }
    if (u === '/api/rooms/room-1' && method === 'DELETE') {
      deleteCalls.push(u);
      rooms = [];
      return { ok: true, status: 200, json: async () => ({ ok: true, deleted: 'room-1' }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const ctx = {
    exam: () => ({ id: 'ex-1', title: 'Đề Toán 9', subject: 'Toán', grade: '9', minutes: 45, questions: [{}] }),
    workspaceHeaders: () => ({}),
    toast: (m) => toasts.push(m),
    modal: (title, body, subtitle, opts) => {
      modalCalls.push({ title, body, subtitle, opts });
      if (opts?.layer === 2) {
        dom.dialogLayer2.innerHTML = `<div class="modal-head"><h2>${title}</h2></div><div class="modal-body">${body}</div>`;
        dom.dialogLayer2.showModal();
      } else {
        dom.modalBody.innerHTML = body;
        dom.dialog.showModal();
      }
    },
  };

  try {
    await openExamRooms(ctx, { tab: 'share' });
    const shellHtml = buildShellHTML(ctx);
    assert.ok(shellHtml.includes('role="tablist"'));
    assert.ok(shellHtml.includes('id="er-tab-share" class="er-tab is-active" role="tab" aria-selected="true" aria-controls="er-tabpanel-share" tabindex="0"'));
    assert.ok(shellHtml.includes('id="er-tab-monitor" class="er-tab " role="tab" aria-selected="false" aria-controls="er-tabpanel-monitor" tabindex="-1"'));
    assert.ok(shellHtml.includes('id="er-tabpanel-share" class="er-tabpanel" role="tabpanel" aria-labelledby="er-tab-share"'));

    // Bấm Xóa phòng này -> mở dialog layer 2, focus vào nút Hủy, không gọi window.confirm hay DELETE
    dom.getShell().dispatchEvent({ type: 'click', target: dom.getDeleteBtn() });
    assert.equal(confirmCalled, false);
    assert.equal(deleteCalls.length, 0);
    assert.equal(dom.dialogLayer2.open, true);
    assert.equal(modalCalls.at(-1).opts?.layer, 2);
    assert.equal(dom.fakeDoc.activeElement.id, 'er-cancel-delete-btn');

    // Hủy bằng đóng layer 2 -> KHÔNG gọi DELETE
    dom.dialogLayer2.close();
    assert.equal(dom.dialogLayer2.open, false);
    await handleExamRoomAction('er-confirm-delete-room', dom.getLayer2ConfirmBtn(), ctx);
    assert.equal(deleteCalls.length, 0);

    // Mở lại xác nhận và bấm Xóa phòng -> gọi DELETE, đóng layer 2, thông báo đã xóa
    dom.getShell().dispatchEvent({ type: 'click', target: dom.getDeleteBtn() });
    assert.equal(dom.dialogLayer2.open, true);
    await handleExamRoomAction('er-confirm-delete-room', dom.getLayer2ConfirmBtn(), ctx);
    assert.deepEqual(deleteCalls, ['/api/rooms/room-1']);
    assert.equal(dom.dialogLayer2.open, false);
    assert.ok(toasts.at(-1).includes('ABC123'));

    // Kiểm tra fallback inline role="alertdialog" khi môi trường không có #dialog-layer2
    rooms = [
      {
        id: 'room-2',
        examId: 'ex-1',
        roomCode: 'XYZ789',
        title: 'Phòng dự phòng',
        status: 'open',
        mode: 'exam',
        attemptCount: 0,
        needsManualCount: 0,
      },
    ];
    const domNoL2 = createFakeRoomsDom({ includeLayer2: false });
    globalThis.document = domNoL2.fakeDoc;
    const ctxNoL2 = {
      ...ctx,
      modal: (_t, body) => {
        domNoL2.modalBody.innerHTML = body;
        domNoL2.dialog.showModal();
      },
    };
    await openExamRooms(ctxNoL2, { tab: 'share' });
    domNoL2.getShell().dispatchEvent({ type: 'click', target: domNoL2.getDeleteBtn() });
    assert.ok(domNoL2.getInlineCancelBtn(), 'Phải dựng hộp xác nhận inline khi thiếu #dialog-layer2');
    assert.equal(domNoL2.fakeDoc.activeElement.id, 'er-cancel-inline-delete-btn');
    domNoL2.getShell().dispatchEvent({ type: 'keydown', key: 'Escape' });
    assert.equal(domNoL2.getInlineCancelBtn(), null, 'Nhấn Escape phải đóng hộp xác nhận inline');
    assert.deepEqual(deleteCalls, ['/api/rooms/room-1']);

    domNoL2.dialog.close();
  } finally {
    globalThis.document = origDocument;
    globalThis.window = origWindow;
    globalThis.fetch = origFetch;
    URL.createObjectURL = origCreateObj;
    URL.revokeObjectURL = origRevokeObj;
  }
});

test('t4 Phòng thi · điều hướng tab bằng phím mũi tên, dừng polling khi tab ẩn, làm mới khi quay lại và giữ focus/cuộn', async () => {
  const origDocument = globalThis.document;
  const origWindow = globalThis.window;
  const origFetch = globalThis.fetch;
  const origSetInterval = globalThis.setInterval;
  const origClearInterval = globalThis.clearInterval;
  const origCreateObj = URL.createObjectURL;
  const origRevokeObj = URL.revokeObjectURL;

  const dom = createFakeRoomsDom({ includeLayer2: true });
  const intervals = new Map();
  let nextTimerId = 1;
  let roomGetCount = 0;
  let delayNextPoll = false;
  let delayedPoll;

  const roomObj = {
    id: 'room-poll',
    examId: 'ex-1',
    roomCode: 'MON123',
    title: 'Phòng thi Giám sát',
    status: 'open',
    mode: 'exam',
    attemptCount: 2,
    needsManualCount: 0,
    maxTabSwitches: 3,
    questionCount: 2,
    totalPointsP100: 1000,
  };
  let attemptsData = [
    {
      id: 'att-1',
      studentName: 'Nguyễn An',
      studentClass: '9A1',
      studentCode: '01',
      attemptNo: 1,
      variantCode: '101',
      status: 'in_progress',
      gradingStatus: 'auto_graded',
      tabSwitchCount: 0,
      fullscreenExitCount: 0,
      startedAt: Date.now() - 60_000,
    },
  ];

  globalThis.document = dom.fakeDoc;
  globalThis.window = {};
  URL.createObjectURL = () => 'blob:qr-poll';
  URL.revokeObjectURL = () => {};
  globalThis.setInterval = (fn, ms) => {
    const id = nextTimerId++;
    intervals.set(id, { fn, ms });
    return id;
  };
  globalThis.clearInterval = (id) => {
    intervals.delete(id);
  };
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    if (u === '/api/rooms') {
      return { ok: true, status: 200, json: async () => ({ rooms: [roomObj] }) };
    }
    if (u === '/api/exports/preflight') {
      return { ok: true, status: 200, json: async () => ({ ready: true, blockingIssues: [] }) };
    }
    if (u.includes('/qr.svg')) {
      return { ok: true, status: 200, blob: async () => new Blob(['<svg></svg>'], { type: 'image/svg+xml' }) };
    }
    if (u === '/api/rooms/room-poll') {
      roomGetCount += 1;
      if (delayNextPoll && init.signal) {
        delayNextPoll = false;
        await new Promise((resolve) => {
          delayedPoll = { signal: init.signal, resolve };
        });
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({
          room: { ...roomObj, attemptCount: attemptsData.length },
          attempts: attemptsData,
          answerKeys: [],
        }),
      };
    }
    if (u.includes('/grading-queue')) {
      return { ok: true, status: 200, json: async () => ({ pendingCount: 0, gradedCount: 0, items: [] }) };
    }
    if (u.includes('/analytics')) {
      return { ok: true, status: 200, json: async () => ({ submittedCount: 0, histogram: [], questionStats: [] }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const ctx = {
    exam: () => ({ id: 'ex-1', title: 'Đề Toán 9', subject: 'Toán', grade: '9', minutes: 45, questions: [{}] }),
    workspaceHeaders: () => ({}),
    toast: () => {},
    modal: (_t, body) => {
      dom.modalBody.innerHTML = body;
      dom.dialog.showModal();
    },
  };

  try {
    await openExamRooms(ctx, { tab: 'share' });
    // Điều hướng phím mũi tên trên .er-tabs
    dom.getTab('share').focus();
    dom.getShell().dispatchEvent({ type: 'keydown', key: 'ArrowRight', target: dom.getTab('share') });
    await new Promise((r) => setTimeout(r, 15));
    assert.equal(dom.getTab('monitor').getAttribute('aria-selected'), 'true');
    assert.equal(dom.fakeDoc.activeElement.id, 'er-tab-monitor');

    dom.getShell().dispatchEvent({ type: 'keydown', key: 'End', target: dom.getTab('monitor') });
    assert.match(dom.modalBody.innerHTML, /role="tabpanel"[^>]*aria-busy="true"/);
    await new Promise((r) => setTimeout(r, 15));
    assert.equal(dom.getTab('keys').getAttribute('aria-selected'), 'true');
    assert.equal(dom.fakeDoc.activeElement.id, 'er-tab-keys');
    assert.doesNotMatch(dom.modalBody.innerHTML, /aria-busy="true"/);

    dom.getShell().dispatchEvent({ type: 'keydown', key: 'Home', target: dom.getTab('keys') });
    await new Promise((r) => setTimeout(r, 15));
    assert.equal(dom.getTab('share').getAttribute('aria-selected'), 'true');
    assert.equal(dom.fakeDoc.activeElement.id, 'er-tab-share');

    dom.getShell().dispatchEvent({ type: 'keydown', key: 'ArrowRight', target: dom.getTab('share') });
    await new Promise((r) => setTimeout(r, 15));
    assert.equal(dom.getTab('monitor').getAttribute('aria-selected'), 'true');

    // Focus vào #er-autorefresh-chk và cuộn modal + bảng ngang
    assert.equal(intervals.size, 1, 'Phải bật polling 5s khi tab đang hiển thị');
    assert.equal([...intervals.values()][0].ms, 5000);
    const chk = dom.getAutorefreshChk();
    chk.focus();
    dom.modalBody.scrollTop = 240;
    dom.getTableWrap().scrollLeft = 95;
    const countBeforePoll = roomGetCount;

    // Kích hoạt 1 nhịp poll khi đang hiển thị -> giữ nguyên focus ở #er-autorefresh-chk và vị trí cuộn
    attemptsData = [
      ...attemptsData,
      {
        id: 'att-2',
        studentName: 'Trần Bình',
        studentClass: '9A1',
        studentCode: '02',
        attemptNo: 1,
        variantCode: '102',
        status: 'in_progress',
        gradingStatus: 'auto_graded',
        tabSwitchCount: 1,
        fullscreenExitCount: 0,
        startedAt: Date.now() - 30_000,
      },
    ];
    await [...intervals.values()][0].fn();
    await new Promise((r) => setTimeout(r, 15));
    assert.equal(roomGetCount, countBeforePoll + 1);
    assert.equal(dom.fakeDoc.activeElement, chk, 'Focus phải giữ nguyên ở #er-autorefresh-chk sau poll');
    assert.equal(dom.modalBody.scrollTop, 240);
    assert.equal(dom.getTableWrap().scrollLeft, 95);

    // Focus vào nút Khóa & thu bài trong kết quả poll -> sau poll phải khôi phục focus bằng preventScroll: true
    const lockBtnBefore = dom.getLockBtn('att-1');
    lockBtnBefore.focus();
    await [...intervals.values()][0].fn();
    await new Promise((r) => setTimeout(r, 15));
    const lockBtnAfter = dom.getLockBtn('att-1');
    assert.equal(dom.fakeDoc.activeElement, lockBtnAfter, 'Focus phải khôi phục đúng nút lock-attempt');
    assert.deepEqual(lockBtnAfter.focusCalls.at(-1), { preventScroll: true });
    assert.equal(dom.modalBody.scrollTop, 240);
    assert.equal(dom.getTableWrap().scrollLeft, 95);

    // Ẩn tab (document.hidden = true) -> dừng polling, không gửi GET khi ẩn
    delayNextPoll = true;
    const stale = [...intervals.values()][0].fn();
    await Promise.resolve();
    assert.ok(delayedPoll);
    dom.fakeDoc.hidden = true;
    dom.fakeDoc.visibilityState = 'hidden';
    dom.fakeDoc.dispatchEvent({ type: 'visibilitychange' });
    assert.equal(intervals.size, 0, 'Phải dừng toàn bộ timer polling khi tab bị ẩn');
    assert.equal(delayedPoll.signal.aborted, true);
    const countWhenHidden = roomGetCount;

    // Quay lại tab (document.hidden = false) -> làm mới ngay và bật lại polling 5s, giữ focus & cuộn
    dom.fakeDoc.hidden = false;
    dom.fakeDoc.visibilityState = 'visible';
    dom.fakeDoc.dispatchEvent({ type: 'visibilitychange' });
    await new Promise((r) => setTimeout(r, 20));
    assert.equal(roomGetCount, countWhenHidden + 1, 'Phải làm mới ngay khi quay lại tab');
    assert.equal(intervals.size, 1, 'Phải khởi động lại polling 5s khi quay lại tab');
    assert.equal(dom.fakeDoc.activeElement.dataset?.attemptId, 'att-1');
    assert.equal(dom.modalBody.scrollTop, 240);
    assert.equal(dom.getTableWrap().scrollLeft, 95);
    const restoredLock = dom.getLockBtn('att-1');
    delayedPoll.resolve();
    await stale;
    assert.equal(dom.getLockBtn('att-1'), restoredLock, 'Kết quả đã hủy không được thay DOM mới');

    // Đóng modal -> dọn dẹp timer và visibilitychange listener
    dom.dialog.close();
    assert.equal(intervals.size, 0);
    assert.equal(dom.fakeDoc.getListenerCount('visibilitychange'), 0);
  } finally {
    globalThis.document = origDocument;
    globalThis.window = origWindow;
    globalThis.fetch = origFetch;
    globalThis.setInterval = origSetInterval;
    globalThis.clearInterval = origClearInterval;
    URL.createObjectURL = origCreateObj;
    URL.revokeObjectURL = origRevokeObj;
  }
});

test('t4 Phòng thi · hai đề: xóa phòng cuối của đề A không chọn nhầm phòng đề B và trả focus về nút lọc', async () => {
  const origDocument = globalThis.document;
  const origWindow = globalThis.window;
  const origFetch = globalThis.fetch;
  const origCreateObj = URL.createObjectURL;
  const origRevokeObj = URL.revokeObjectURL;

  const dom = createFakeRoomsDom({ includeLayer2: true });
  let rooms = [
    {
      id: 'room-a',
      examId: 'ex-a',
      roomCode: 'AAA111',
      title: 'Phòng đề A',
      status: 'open',
      mode: 'exam',
      attemptCount: 0,
      needsManualCount: 0,
      questionCount: 1,
      totalPointsP100: 1000,
    },
    {
      id: 'room-b',
      examId: 'ex-b',
      roomCode: 'BBB222',
      title: 'Phòng đề B',
      status: 'open',
      mode: 'exam',
      attemptCount: 0,
      needsManualCount: 0,
      questionCount: 1,
      totalPointsP100: 1000,
    },
  ];
  const deleteCalls = [];

  globalThis.document = dom.fakeDoc;
  globalThis.window = {};
  URL.createObjectURL = () => 'blob:qr-two-exams';
  URL.revokeObjectURL = () => {};
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    const method = (init.method || 'GET').toUpperCase();
    if (u === '/api/rooms' && method === 'GET') {
      return { ok: true, status: 200, json: async () => ({ rooms }) };
    }
    if (u === '/api/exports/preflight') {
      return { ok: true, status: 200, json: async () => ({ ready: true, blockingIssues: [] }) };
    }
    if (u.includes('/qr.svg')) {
      return { ok: true, status: 200, blob: async () => new Blob(['<svg></svg>'], { type: 'image/svg+xml' }) };
    }
    if (u === '/api/rooms/room-a' && method === 'DELETE') {
      deleteCalls.push(u);
      rooms = rooms.filter((r) => r.id !== 'room-a');
      return { ok: true, status: 200, json: async () => ({ ok: true, deleted: 'room-a' }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const ctx = {
    exam: () => ({ id: 'ex-a', title: 'Đề A', subject: 'Toán', grade: '9', minutes: 45, questions: [{}] }),
    workspaceHeaders: () => ({}),
    toast: () => {},
    modal: (title, body, _subtitle, opts) => {
      if (opts?.layer === 2) {
        dom.dialogLayer2.innerHTML = `<div class="modal-head"><h2>${title}</h2></div><div class="modal-body">${body}</div>`;
        dom.dialogLayer2.showModal();
      } else {
        dom.modalBody.innerHTML = body;
        dom.dialog.showModal();
      }
    },
  };

  try {
    await openExamRooms(ctx, { tab: 'share' });
    assert.ok(dom.modalBody.innerHTML.includes('Phòng thi & Bài tập (1)'));
    assert.ok(dom.modalBody.innerHTML.includes('AAA111'));
    assert.ok(!dom.modalBody.innerHTML.includes('BBB222'));

    // Xóa phòng cuối của đề A
    dom.getShell().dispatchEvent({ type: 'click', target: dom.getDeleteBtn() });
    assert.equal(dom.dialogLayer2.open, true);
    await handleExamRoomAction('er-confirm-delete-room', dom.getLayer2ConfirmBtn(), ctx);

    assert.deepEqual(deleteCalls, ['/api/rooms/room-a']);
    assert.ok(dom.modalBody.innerHTML.includes('Phòng thi & Bài tập (0)'));
    assert.equal(dom.getDeleteBtn(), null, 'Không được hiện nút xóa phòng của đề B khi danh sách đề A còn 0 phòng');
    assert.ok(!dom.modalBody.innerHTML.includes('BBB222'), 'Không được hiện chi tiết phòng đề B trong bộ lọc đề A');
    assert.equal(
      dom.fakeDoc.activeElement,
      dom.getScopeFilterBtn('all'),
      'Hết phòng trong bộ lọc đề A phải trả focus về nút lọc Tất cả phòng',
    );

    // Chuyển sang "Tất cả phòng của tôi" -> hiện phòng đề B; chuyển lại "Phòng của đề đang mở" -> xóa lựa chọn
    dom.getShell().dispatchEvent({ type: 'click', target: dom.getScopeFilterBtn('all') });
    await new Promise((r) => setTimeout(r, 15));
    assert.ok(dom.modalBody.innerHTML.includes('BBB222'));
    assert.ok(dom.getDeleteBtn());

    dom.getShell().dispatchEvent({ type: 'click', target: dom.getScopeFilterBtn('exam') });
    await new Promise((r) => setTimeout(r, 15));
    assert.ok(dom.modalBody.innerHTML.includes('Phòng thi & Bài tập (0)'));
    assert.equal(dom.getDeleteBtn(), null);
    assert.ok(!dom.modalBody.innerHTML.includes('BBB222'));

    // Mở lại từ đầu khi chỉ còn phòng đề B -> loadRooms không chọn nhầm phòng đề B
    dom.dialog.close();
    await openExamRooms(ctx, { tab: 'share' });
    assert.ok(dom.modalBody.innerHTML.includes('Phòng thi & Bài tập (0)'));
    assert.equal(dom.getDeleteBtn(), null);
    assert.ok(!dom.modalBody.innerHTML.includes('BBB222'));

    dom.dialog.close();
  } finally {
    globalThis.document = origDocument;
    globalThis.window = origWindow;
    globalThis.fetch = origFetch;
    URL.createObjectURL = origCreateObj;
    URL.revokeObjectURL = origRevokeObj;
  }
});

function findChromeExecutable() {
  const candidates = [
    process.env.BROWSER_PATH,
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return '';
}

async function launchChromeForTest() {
  const args = ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'];
  const envPath = process.env.BROWSER_PATH || process.env.CHROME_PATH || '';
  if (envPath && fs.existsSync(envPath)) {
    try {
      return await chromium.launch({ headless: true, executablePath: envPath, args });
    } catch {
      // Fall through to channel launch on Windows Chrome 136+
    }
  }
  try {
    return await chromium.launch({ headless: true, channel: 'chrome', args });
  } catch {
    const chromePath = findChromeExecutable();
    if (!chromePath) return null;
    return chromium.launch({ headless: true, executablePath: chromePath, args });
  }
}

test('t4 Phòng thi · Chrome: vô hiệu hóa nút Xóa phòng này trong lúc chuyển phòng QR chậm và mở đúng xác nhận sau khi tải xong', async (t) => {
  let browser = await launchChromeForTest();
  if (!browser) {
    t.skip('Không tìm thấy Chrome/Chromium trên máy kiểm thử');
    return;
  }

  const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const rooms = [
    {
      id: 'room-a',
      examId: 'ex-1',
      roomCode: 'AAA111',
      title: 'Phòng A',
      status: 'open',
      mode: 'exam',
      joinPath: '/exam-room.html?code=AAA111',
      attemptCount: 0,
      needsManualCount: 0,
      questionCount: 1,
      totalPointsP100: 1000,
    },
    {
      id: 'room-b',
      examId: 'ex-1',
      roomCode: 'BBB222',
      title: 'Phòng B',
      status: 'open',
      mode: 'exam',
      joinPath: '/exam-room.html?code=BBB222',
      attemptCount: 0,
      needsManualCount: 0,
      questionCount: 1,
      totalPointsP100: 1000,
    },
  ];

  let releaseRoomBQr = null;
  let roomBQrStartedResolve = null;
  const roomBQrStarted = new Promise((resolve) => {
    roomBQrStartedResolve = resolve;
  });

  const harnessHtml = `<!doctype html>
<html lang="vi">
<head><meta charset="utf-8"><title>t4 switch room test</title></head>
<body>
  <dialog id="dialog"><div class="modal-head"><h2></h2></div><div class="modal-body"></div></dialog>
  <dialog id="dialog-layer2"><div class="modal-head"><h2></h2></div><div class="modal-body"></div></dialog>
  <script type="module">
    import { openExamRooms, handleExamRoomAction } from '/exam-rooms.js';
    const ctx = {
      exam: () => ({ id: 'ex-1', title: 'Đề Toán 9', subject: 'Toán', grade: '9', minutes: 45, questions: [{}] }),
      workspaceHeaders: () => ({}),
      toast: () => {},
      modal: (title, body, _subtitle, opts) => {
        const dlg = document.getElementById(opts?.layer === 2 ? 'dialog-layer2' : 'dialog');
        dlg.querySelector('h2').textContent = title;
        dlg.querySelector('.modal-body').innerHTML = body;
        if (!dlg.open) dlg.showModal();
      },
    };
    document.addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-action]');
      if (!btn) return;
      if (btn.dataset.action === 'close-top-modal') {
        document.getElementById('dialog-layer2')?.close();
        return;
      }
      void handleExamRoomAction(btn.dataset.action, btn, ctx);
    });
    window.__roomsReady = openExamRooms(ctx, { tab: 'share' });
  </script>
</body>
</html>`;

  const server = http.createServer((req, res) => {
    const reqUrl = new URL(req.url || '/', 'http://127.0.0.1');
    const pathname = reqUrl.pathname;

    if (pathname === '/__t4-harness.html') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(harnessHtml);
      return;
    }
    if (pathname === '/api/rooms') {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ rooms }));
      return;
    }
    if (pathname === '/api/exports/preflight') {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ready: true, blockingIssues: [] }));
      return;
    }
    if (pathname === '/api/rooms/room-a/qr.svg') {
      res.writeHead(200, { 'Content-Type': 'image/svg+xml' });
      res.end('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>');
      return;
    }
    if (pathname === '/api/rooms/room-b/qr.svg') {
      roomBQrStartedResolve();
      new Promise((resolve) => {
        releaseRoomBQr = resolve;
      }).then(() => {
        if (!res.writableEnded) {
          res.writeHead(200, { 'Content-Type': 'image/svg+xml' });
          res.end('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>');
        }
      });
      return;
    }

    const rel = pathname.replace(/^\/+/, '');
    const fullPath = path.resolve(repoRoot, rel);
    if (
      rel &&
      fullPath.startsWith(repoRoot) &&
      fs.existsSync(fullPath) &&
      fs.statSync(fullPath).isFile()
    ) {
      const ext = path.extname(fullPath).toLowerCase();
      const contentType =
        ext === '.js' || ext === '.mjs'
          ? 'application/javascript; charset=utf-8'
          : ext === '.css'
            ? 'text/css; charset=utf-8'
            : 'application/octet-stream';
      res.writeHead(200, { 'Content-Type': contentType });
      fs.createReadStream(fullPath).pipe(res);
      return;
    }

    res.writeHead(404);
    res.end('Not found');
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const addr = server.address();
  const baseUrl = `http://127.0.0.1:${addr.port}`;

  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(err.message));

    await page.goto(`${baseUrl}/__t4-harness.html`, { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => window.__roomsReady);

    const deleteBtn = page.locator('[data-er-action="delete-room"]');
    await deleteBtn.waitFor({ state: 'visible' });
    assert.equal(await deleteBtn.isDisabled(), false);
    assert.equal(await deleteBtn.getAttribute('data-room-id'), 'room-a');

    // Chuyển từ phòng A sang phòng B khi QR của phòng B trả chậm
    await page.locator('[data-er-action="select-room"][data-room-id="room-b"]').click();
    await roomBQrStarted;

    // Trong lúc chờ QR phòng B: giao diện vẫn đang ở phòng A nhưng nút Xóa phải bị vô hiệu hóa
    assert.equal(await deleteBtn.isDisabled(), true, 'Nút Xóa phòng này phải bị vô hiệu hóa trong lúc chuyển phòng');
    assert.equal(await deleteBtn.getAttribute('aria-disabled'), 'true');
    assert.equal(await page.locator('#er-u-title').inputValue(), 'Phòng A');

    // Kể cả khi kích hoạt click cưỡng bức lúc đang chuyển phòng, không được mở xác nhận xóa phòng B
    await deleteBtn.click({ force: true });
    assert.equal(
      await page.evaluate(() => document.getElementById('dialog-layer2').open),
      false,
      'Không được mở hộp thoại xác nhận xóa phòng B khi giao diện vẫn đang hiển thị phòng A',
    );

    // Cho phép QR phòng B hoàn tất -> giao diện chuyển sang phòng B và bật lại nút Xóa cho đúng phòng B
    releaseRoomBQr();
    await page.waitForFunction(
      () => document.querySelector('#er-u-title')?.value === 'Phòng B',
    );
    assert.equal(await deleteBtn.isDisabled(), false);
    assert.equal(await deleteBtn.getAttribute('data-room-id'), 'room-b');

    await deleteBtn.click();
    await page.waitForFunction(() => document.getElementById('dialog-layer2')?.open === true);
    const confirmText = await page.locator('#er-delete-confirm-desc').textContent();
    assert.ok(confirmText.includes('BBB222'), 'Sau khi chuyển xong phải mở đúng xác nhận xóa phòng B');
    assert.equal(
      await page.evaluate(() => document.activeElement?.id),
      'er-cancel-delete-btn',
    );
    assert.deepEqual(pageErrors, []);
  } finally {
    if (releaseRoomBQr) releaseRoomBQr();
    if (browser) await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});
