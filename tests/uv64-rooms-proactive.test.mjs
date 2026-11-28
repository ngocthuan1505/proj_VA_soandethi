import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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
import { buildGradingTabHTML } from '../exam-rooms.js';
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
