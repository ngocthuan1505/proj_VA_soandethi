import {subjectId} from './authoring-catalog.js';
let ctx,initialized=false;const $=s=>document.querySelector(s),b=(a,t,attr='')=>`<button type="button" data-action="${a}" ${attr}>${t}</button>`;

export function mountDesign(c){
 ctx=c;
 document.body.classList.add('mach');
 refreshDesign();
 if(!initialized){
  initialized=true;
  document.addEventListener('keydown',ev=>{
   if(ev.key==='Escape'&&$('#dialog').open&&$('#command-query')){ev.preventDefault();$('#dialog').close();return;}
   if((ev.ctrlKey||ev.metaKey)&&ev.key.toLowerCase()==='k'&&!$('.composer-shell')){ev.preventDefault();showCommands();}
  });
  document.addEventListener('input',ev=>{if(ev.target.id==='command-query')paintCommands(ev.target.value);});
 }
}

export function refreshDesign(){
 if(!ctx)return;
 const e=ctx.exam();
 document.querySelectorAll('.subject-shortcuts button').forEach(n=>n.classList.toggle('active',subjectId(n.dataset.subject)===subjectId(e.subject)));
}

const commands=[
 ['design-home','Trang chủ Cá Voi Xanh','Tạo đề nhanh, chiến dịch nhiều đề và đề gần đây','⌂'],
 ['question-bank','Ngân hàng câu hỏi','Tìm không dấu, lọc, lưu và chèn lại câu hỏi','★'],
 ['exam-analytics','Phân tích chất lượng đề','Điểm sẵn sàng, mức độ nhận thức, trùng lặp','◔'],
 ['exam-rooms','Phòng thi trực tuyến','Giao bài theo mã phòng/QR, chấm tự luận, xuất điểm','▤'],
 ['subject-library','Chèn nội dung theo môn','Công thức, phản ứng, ngữ liệu','ƒ'],
 ['studio-replace','Tìm và thay thế','Tìm nội dung trong đề và đáp án','⌕'],
 ['import-doc','Nhập học liệu','Word, PDF, hình ảnh, tài liệu','↗'],
 ['library','Mở kho đề','Tìm và tiếp tục các đề đã lưu','▤'],
 ['export','Xuất Word / PDF','Bản học sinh, giáo viên và phiếu OMR','↓'],
 ['metadata','Thông tin đề','Môn, lớp, thời gian và đầu đề','◷'],
 ['connections','Kết nối AI','Mô hình cục bộ hoặc API','✦'],
];

function showCommands(){
 ctx.modal('Bạn muốn làm gì?',`<input id="command-query" type="search" aria-label="Tìm thao tác" placeholder="Tìm công cụ, ví dụ: công thức, Word, phòng thi…" autofocus><div id="command-results"></div><p class="command-hint">Ctrl+K để mở nhanh · Esc để đóng</p>`);
 paintCommands('');
 $('#command-query').focus();
}

function paintCommands(query){
 const q=query.toLocaleLowerCase('vi-VN');
 $('#command-results').innerHTML=commands.filter(a=>a.join(' ').toLocaleLowerCase('vi-VN').includes(q)).map(([a,title,desc,symbol])=>b('design-execute',`<span>${symbol}</span><div><b>${title}</b><small>${desc}</small></div><i>↵</i>`,`data-command="${a}" class="command-result"`)).join('')||'<p>Chưa thấy công cụ. Thử từ khóa ngắn hơn.</p>';
}

export function setActiveWorkspaceNav(action='design-workspace'){
 document.querySelectorAll('.design-rail button[data-action]').forEach(btn=>{
  btn.classList.toggle('rail-active',btn.dataset.action===action);
 });
}

export function handleDesignAction(action,node){
 if(!action.startsWith('design-'))return false;
 if(action==='design-focus'){
  const mode=$('.workspace').classList.toggle('focus-mode');
  node.setAttribute('aria-pressed',String(mode));
  const span=node.querySelector('span');
  if(span)span.textContent=mode?'Thoát tập trung':'Tập trung';
 }else if(action==='design-command')showCommands();
 else if(action==='design-execute'){$('#dialog').close();ctx.act(node.dataset.command).catch(e=>ctx.toast(e.message));}
 else if(action==='design-new-subject'){
  document.getElementById('new-subject').value=node.dataset.subject;
  document.querySelectorAll('[data-action=design-new-subject]').forEach(n=>n.setAttribute('aria-pressed',String(n===node)));
 }else if(action==='design-templates'){
  ctx.setTab('templates');ctx.render();
  $('.sidebar')?.classList.add('open');
  $('.workspace')?.classList.remove('outline-collapsed');
 }else if(action==='design-home'){
  setActiveWorkspaceNav('design-home');
  ctx.setViewMode?.('home');
 }else if(action==='design-workspace'){
  if(ctx.getViewMode?.()==='home')ctx.setViewMode?.('workspace');
  $('.workspace')?.classList.remove('focus-mode','outline-collapsed','mobile-ai-view');
  $('aside.assistant')?.classList.remove('open');
  setActiveWorkspaceNav('design-workspace');
  ctx.setTab('outline');ctx.render();
 }
 return true;
}
