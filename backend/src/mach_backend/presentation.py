"""Controls embedded into downloaded student HTML for classroom review."""

PRESENTATION_CONTROLS = """
<nav class="exam-presentation-toolbar" aria-label="Điều khiển trình chiếu" hidden>
  <button type="button" id="exam-present">Trình chiếu</button>
  <div id="exam-navigation" hidden>
    <button type="button" id="exam-prev" aria-label="Câu trước">← <span>Câu trước</span></button>
    <output id="exam-progress" aria-live="polite"></output>
    <button type="button" id="exam-next" aria-label="Câu sau"><span>Câu sau</span> →</button>
    <button type="button" id="exam-reference" aria-controls="exam-reading"
            aria-expanded="false" hidden>Ngữ liệu</button>
    <button type="button" id="exam-exit">Thoát trình chiếu</button>
  </div>
</nav>
"""

PRESENTATION_CSS = """
@media print{.exam-presentation-toolbar{display:none!important}}
@media screen{
 body{box-sizing:border-box;padding-inline:clamp(16px,4vw,38px)}
 .exam-presentation-toolbar{font:500 .88rem/1.3 system-ui,sans-serif;margin-block:0 16px}
 .exam-presentation-toolbar button{background:#fff;color:#21463d;border:1px solid #bdcec8;
   font:inherit;padding:.6rem .8rem;border-radius:.6rem;cursor:pointer}
 .exam-presentation-toolbar button:disabled{opacity:.5;cursor:default}
 .exam-presentation-toolbar button:focus-visible{outline:3px solid #176853;outline-offset:3px}
 #exam-present:not([hidden]){display:block;margin-inline-start:auto}
 #exam-navigation:not([hidden]){display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}
 #exam-progress{min-width:6rem;text-align:center;font-variant-numeric:tabular-nums}
 #exam-exit{margin-inline-start:auto}
 .exam-presenting{background:#edf3ee}
 .exam-presenting body{max-width:1100px;margin:0 auto;padding-block:1rem 3rem}
 .exam-presenting .exam-presentation-toolbar{position:sticky;top:0;padding:.65rem 0;
   background:#edf3ee;z-index:1}
 .exam-presenting [data-exam-intro],.exam-presenting [data-exam-question]:not(.is-current),
 .exam-presenting #exam-reading:not(.is-open){display:none}
 .exam-presenting [data-exam-question],.exam-presenting #exam-reading{background:#fff;
   padding:clamp(18px,4vw,44px);border:1px solid #d7e4db;border-radius:14px;
   font-size:clamp(1.12rem,2.3vw,1.65rem);line-height:1.45;overflow-wrap:anywhere}
 .exam-presenting #exam-reading{font-size:clamp(.98rem,2vw,1.25rem);padding-block:1rem}
 .exam-presenting [data-exam-question]>p{margin-block:.45em}
 @media(max-width:440px){
   #exam-prev span,#exam-next span{display:none}
   #exam-progress{min-width:4.5rem}
   #exam-exit{margin-inline-start:0}
 }
}
"""

PRESENTATION_SCRIPT = """
<script>
(() => {
 const root = document.documentElement;
 const toolbar = document.querySelector('.exam-presentation-toolbar');
 const questions = [...document.querySelectorAll('[data-exam-question]')];
 const start = document.querySelector('#exam-present');
 const nav = document.querySelector('#exam-navigation');
 const previous = document.querySelector('#exam-prev');
 const next = document.querySelector('#exam-next');
 const progress = document.querySelector('#exam-progress');
 const reference = document.querySelector('#exam-reference');
 const reading = document.querySelector('#exam-reading');
 const exit = document.querySelector('#exam-exit');
 let index = 0;

 function goTo(nextIndex) {
  index = Math.max(0, Math.min(questions.length - 1, nextIndex));
  questions.forEach((question, i) => question.classList.toggle('is-current', i === index));
  progress.value = 'Câu ' + (index + 1) + ' / ' + questions.length;
  previous.disabled = index === 0;
  next.disabled = index === questions.length - 1;
  window.scrollTo(0, 0);
 }
 function leave() {
  root.classList.remove('exam-presenting');
  nav.hidden = true;
  start.hidden = false;
  reading?.classList.remove('is-open');
  reference.setAttribute('aria-expanded', 'false');
  start.focus();
 }
 if (!questions.length) return;
 toolbar.hidden = false;
 reference.hidden = !reading;
 start.addEventListener('click', () => {
  root.classList.add('exam-presenting');
  start.hidden = true;
  nav.hidden = false;
  goTo(0);
  (next.disabled ? exit : next).focus();
 });
 previous.addEventListener('click', () => {
  goTo(index - 1);
  if (previous.disabled) next.focus();
 });
 next.addEventListener('click', () => {
  goTo(index + 1);
  if (next.disabled) previous.focus();
 });
 reference.addEventListener('click', () => {
  if (reading) reference.setAttribute('aria-expanded', String(reading.classList.toggle('is-open')));
 });
 exit.addEventListener('click', leave);
 document.addEventListener('keydown', event => {
  if (nav.hidden || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const positions = {ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0,
                     End: questions.length - 1};
  if (event.key === 'Escape') {
   leave();
  } else if (Object.hasOwn(positions, event.key)) {
   event.preventDefault();
   goTo(positions[event.key]);
   if (document.activeElement === previous && previous.disabled) next.focus();
   if (document.activeElement === next && next.disabled) previous.focus();
  }
 });
})();
</script>"""
