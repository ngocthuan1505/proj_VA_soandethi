/**
 * Nhập giọng nói tiếng Việt qua Web Speech API (SpeechRecognition / webkitSpeechRecognition).
 */

const MIC_ICON_SVG = `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v3 M8 22h8"/></svg>`;
const STOP_ICON_SVG = `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/></svg>`;

let activeSession = null;

function getSpeechRecognitionCtor() {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function isVoiceSupported() {
  return Boolean(getSpeechRecognitionCtor());
}

function defaultNotify(message) {
  const toastEl = typeof document !== 'undefined' ? document.querySelector('#toast') : null;
  if (toastEl) {
    toastEl.textContent = message;
    toastEl.classList.add('show');
    clearTimeout(toastEl._voiceToastTimer);
    toastEl._voiceToastTimer = setTimeout(() => toastEl.classList.remove('show'), 3500);
  }
}

function joinTranscript(baseText, addition) {
  const cleanAdd = String(addition || '').trim();
  if (!cleanAdd) return String(baseText || '');
  const base = String(baseText || '');
  if (!base.trim()) return cleanAdd;
  const sep = /[\s\n]$/.test(base) ? '' : ' ';
  return base + sep + cleanAdd;
}

function translateVoiceError(code) {
  switch (String(code || '')) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Trình duyệt chưa cấp quyền micro. Hãy cho phép micro trong thanh địa chỉ rồi thử lại.';
    case 'audio-capture':
      return 'Không tìm thấy micro đang hoạt động trên thiết bị.';
    case 'no-speech':
      return 'Chưa nghe thấy giọng nói. Hãy bấm micro và nói lại gần thiết bị hơn.';
    case 'network':
      return 'Không kết nối được dịch vụ nhận dạng giọng nói. Kiểm tra mạng rồi thử lại.';
    case 'aborted':
      return '';
    default:
      return 'Chưa nhận dạng được giọng nói lúc này. Thầy cô có thể thử lại hoặc nhập trực tiếp.';
  }
}

function ensureVoiceStyle() {
  if (typeof document === 'undefined' || document.getElementById('mach-voice-style')) return;
  const style = document.createElement('style');
  style.id = 'mach-voice-style';
  style.textContent = `
    .voice-mic-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      height: 28px;
      min-height: 28px;
      min-width: 28px;
      padding: 0 7px;
      border-radius: 7px;
      border: 1px solid var(--line-strong, #c2d4e8);
      background: var(--bg-surface, #fff);
      color: var(--ink-muted, #4b6075);
      flex-shrink: 0;
    }
    .voice-mic-btn:hover:not(:disabled) {
      color: var(--brand, #0f4c81);
      border-color: var(--brand-border, #b6d4f0);
      background: var(--brand-soft, #e8f2fc);
    }
    .voice-mic-btn.is-listening {
      color: #fff;
      background: var(--danger, #b91c1c);
      border-color: var(--danger, #b91c1c);
      box-shadow: 0 0 0 3px rgba(185, 28, 28, 0.18);
    }
    .voice-mic-btn .ico { width: 14px; height: 14px; }
    @media (max-width: 760px) {
      .chat-compose .voice-mic-btn { min-height: 32px; height: 32px; }
    }
  `;
  document.head.appendChild(style);
}

/**
 * Gắn nút Micro nhập giọng nói tiếng Việt vào container hoặc input/textarea.
 * @param {HTMLElement} containerOrInput
 * @param {Object} [options]
 * @param {HTMLInputElement|HTMLTextAreaElement|null} [options.targetInput]
 * @param {(text: string, interim: string) => void} [options.onText]
 * @param {(finalText: string, fullValue: string) => void} [options.onFinal]
 * @param {(msg: string) => void} [options.onNotify]
 * @param {string} [options.lang='vi-VN']
 * @param {string} [options.label='']
 * @param {HTMLElement|null} [options.insertBefore]
 */
export function mountVoiceButton(
  containerOrInput,
  {
    targetInput = null,
    onText = null,
    onFinal = null,
    onNotify = null,
    lang = 'vi-VN',
    label = '',
    insertBefore = null,
  } = {},
) {
  if (!containerOrInput || typeof document === 'undefined') return null;
  ensureVoiceStyle();

  const notify = typeof onNotify === 'function' ? onNotify : defaultNotify;
  const isInputEl =
    containerOrInput.tagName === 'TEXTAREA' || containerOrInput.tagName === 'INPUT';
  const isButtonEl = containerOrInput.tagName === 'BUTTON';

  const inputEl =
    targetInput ||
    (isInputEl
      ? containerOrInput
      : containerOrInput.closest?.('form')?.querySelector('textarea, input[type="text"], input[type="search"]') ||
        null);

  let btn;
  if (isButtonEl) {
    btn = containerOrInput;
  } else {
    const existing = !isInputEl ? containerOrInput.querySelector('.voice-mic-btn[data-voice-mounted="1"]') : null;
    if (existing) return existing._voiceController || { button: existing, stop: () => {}, isListening: () => false };
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'voice-mic-btn';
    btn.dataset.voiceMounted = '1';
    if (isInputEl) {
      containerOrInput.insertAdjacentElement('afterend', btn);
    } else if (insertBefore && insertBefore.parentNode === containerOrInput) {
      containerOrInput.insertBefore(btn, insertBefore);
    } else {
      containerOrInput.appendChild(btn);
    }
  }

  let recognition = null;
  let listening = false;
  let baseSnapshot = '';
  let finalizedSegment = '';

  const renderBtn = () => {
    btn.classList.toggle('is-listening', listening);
    btn.setAttribute('aria-pressed', String(listening));
    btn.setAttribute(
      'aria-label',
      listening ? 'Dừng nhập giọng nói tiếng Việt' : 'Nhập bằng giọng nói tiếng Việt',
    );
    btn.title = listening
      ? 'Đang nghe (tiếng Việt) · Bấm để dừng'
      : 'Nhập bằng giọng nói tiếng Việt (vi-VN)';
    btn.innerHTML = (listening ? STOP_ICON_SVG : MIC_ICON_SVG) + (label ? `<span>${listening ? 'Đang nghe…' : label}</span>` : '');
  };

  const applyValue = (fullText, isFinal = false) => {
    if (inputEl) {
      inputEl.value = fullText;
      inputEl.dispatchEvent(new Event('input', { bubbles: true }));
    }
    if (typeof onText === 'function') {
      onText(fullText, isFinal ? '' : fullText);
    }
  };

  const stop = () => {
    if (!listening) return;
    listening = false;
    try {
      recognition?.stop();
    } catch {}
    if (activeSession === controller) activeSession = null;
    renderBtn();
  };

  const start = () => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      notify('Trình duyệt hiện tại chưa hỗ trợ nhập giọng nói (Web Speech API). Thầy cô hãy dùng Chrome hoặc Edge.');
      return;
    }
    if (activeSession && activeSession !== controller) {
      activeSession.stop();
    }
    baseSnapshot = inputEl ? String(inputEl.value || '') : '';
    finalizedSegment = '';
    recognition = new Ctor();
    recognition.lang = lang || 'vi-VN';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      listening = true;
      activeSession = controller;
      renderBtn();
    };

    recognition.onresult = (event) => {
      let interim = '';
      let finalChunk = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const res = event.results[i];
        const transcript = String(res?.[0]?.transcript || '').trim();
        if (!transcript) continue;
        if (res.isFinal) {
          finalChunk = joinTranscript(finalChunk, transcript);
        } else {
          interim = joinTranscript(interim, transcript);
        }
      }
      if (finalChunk) {
        finalizedSegment = joinTranscript(finalizedSegment, finalChunk);
      }
      const combined = joinTranscript(joinTranscript(baseSnapshot, finalizedSegment), interim);
      applyValue(combined, Boolean(finalChunk && !interim));
      if (finalChunk && typeof onFinal === 'function') {
        onFinal(finalChunk, joinTranscript(baseSnapshot, finalizedSegment));
      }
    };

    recognition.onerror = (event) => {
      const msg = translateVoiceError(event?.error);
      if (msg) notify(msg);
      listening = false;
      if (activeSession === controller) activeSession = null;
      renderBtn();
    };

    recognition.onend = () => {
      const wasListening = listening;
      listening = false;
      if (activeSession === controller) activeSession = null;
      if (wasListening && finalizedSegment && inputEl) {
        applyValue(joinTranscript(baseSnapshot, finalizedSegment), true);
      }
      renderBtn();
    };

    try {
      recognition.start();
    } catch {
      notify('Không khởi động được micro. Hãy kiểm tra quyền truy cập micro rồi thử lại.');
      listening = false;
      renderBtn();
    }
  };

  const controller = {
    button: btn,
    start,
    stop,
    isListening: () => listening,
  };

  btn._voiceController = controller;
  btn.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (listening) stop();
    else start();
  });

  renderBtn();
  return controller;
}
