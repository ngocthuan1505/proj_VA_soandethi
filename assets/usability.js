// Presentation state stays separate from the exam, undo history and AI scope.
import {uiIcon} from './ui-icons.js';
let ctx,body,observer,layoutObserver,initialized=false,expanded=false,fitZoom=true,workspaceObserver;
const positions=new Map(),$=s=>document.querySelector(s);
const state=()=>{const id=ctx.exam().id;if(!positions.has(id))positions.set(id,{top:0,follow:true,unread:false});return positions.get(id);};
function resizeInput(){const input=$('#chat-input');if(!input)return;const limit=innerHeight<600?64:120;input.style.height='auto';input.style.height=Math.min(limit,Math.max(42,input.scrollHeight))+'px';input.style.overflowY=input.scrollHeight>limit?'auto':'hidden';}
function paintJump(){const button=$('[data-ux-action=latest]');if(!button||!body)return;const s=state();button.hidden=s.follow||body.scrollHeight-body.clientHeight<30;button.textContent=s.unread?'↓ Có tin mới':'↓ Cuối hội thoại';}
function goLatest(){if(!body)return;const s=state();s.follow=true;s.unread=false;body.scrollTop=body.scrollHeight;paintJump();}
function closeOptions(focus=false){const panel=$('.ux-chat-options');if(!panel||panel.hidden)return;panel.hidden=true;const button=$('[data-ux-action=options]');button?.setAttribute('aria-expanded','false');if(focus)button?.focus();}
function closeAttachments(focus=false){const panel=$('.ux-attach-menu');if(!panel||panel.hidden)return;panel.hidden=true;const button=$('[data-ux-action=attach]');button?.setAttribute('aria-expanded','false');if(focus)button?.focus();}
function setExpanded(value){expanded=value;$('.assistant')?.classList.toggle('ux-expanded',value);const button=$('[data-ux-action=expand]');if(button){button.setAttribute('aria-pressed',String(value));button.setAttribute('aria-label',value?'Thu gọn trò chuyện':'Mở rộng trò chuyện');button.title=button.getAttribute('aria-label');button.textContent=value?'⤡':'⤢';}}
function fitPaper(){if(!fitZoom)return;const paper=$('.paper'),scroll=$('.paper-scroll'),select=$('#zoom');if(!paper||!scroll||!select)return;const style=getComputedStyle(scroll),available=scroll.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight)-4,width=paper.querySelector('.document-page')?.offsetWidth||paper.offsetWidth||920,scale=Math.max(.2,Math.min(1,available/width));if(Math.abs((Number(paper.style.zoom)||1)-scale)>.001)paper.style.zoom=String(scale);select.querySelector('[value=fit]').textContent=Math.round(scale*100)+'%';}
function updateViewport(){const viewport=window.visualViewport;if(!viewport||viewport.scale===1)document.documentElement.style.setProperty('--chat-viewport-height',(viewport?.height||innerHeight)+'px');resizeInput();fitPaper();}
export function mountUsability(context){ctx=context;const assistant=$('.assistant'),head=$('.assistant-head .row');
 if(!document.querySelector('#chat-polish-style')){const style=document.createElement('link');style.id='chat-polish-style';style.rel='stylesheet';style.href='/assets/chat-polish.css';document.head.append(style);}
 if(!assistant||!head)return;$('#chat-input').rows=1;const zoom=$('#zoom');if(zoom){zoom.insertAdjacentHTML('afterbegin','<option value="fit" hidden>100%</option>');if(fitZoom)zoom.value='fit';}
 const panel=document.createElement('section');panel.id='chat-options';panel.className='ux-chat-options';panel.hidden=true;panel.setAttribute('aria-label','Cài đặt trò chuyện');
 panel.innerHTML='<strong>Cài đặt trò chuyện</strong><p>Áp dụng cho đề đang mở</p><div class="ux-mode-slot"></div>';
 const options=$('.studio-ai-options');if(options)panel.append(options);
 const actions=document.createElement('div');actions.className='ux-option-actions';
 for(const action of ['connections','reset-chat']){const button=head.querySelector('[data-action='+action+']');if(button){button.textContent=action==='connections'?'Kết nối mô hình AI':'Xóa hội thoại…';actions.append(button);}}
 panel.append(actions);assistant.append(panel);
 head.insertAdjacentHTML('afterbegin','<button type="button" data-ux-action="expand" aria-label="Mở rộng trò chuyện" aria-pressed="false" title="Mở rộng trò chuyện">⤢</button><button type="button" data-ux-action="options" aria-label="Cài đặt trò chuyện" aria-expanded="false" aria-controls="chat-options" title="Cài đặt trò chuyện">⋯</button>');
 const toolbar=$('.editor-toolbar');if(toolbar){toolbar.querySelector('[data-action=export]')?.setAttribute('aria-label','In hoặc xuất đề');toolbar.querySelector('[data-action=menu]')?.setAttribute('aria-label','Thêm công cụ định dạng');toolbar.setAttribute('role','toolbar');toolbar.setAttribute('aria-label','Công cụ định dạng, cuộn ngang để xem thêm');toolbar.querySelectorAll('.view-tab').forEach(tab=>tab.remove());}
 const attachments=$('.compose-attachments'),tools=$('.design-assistant-tools');
 if(attachments){
  const menu=document.createElement('section');menu.className='ux-attach-menu';menu.id='chat-attachments';menu.hidden=true;menu.setAttribute('aria-label','Thêm vào cuộc trò chuyện');
  for(const button of [...attachments.querySelectorAll('button'),tools?.querySelector('.assistant-library')].filter(Boolean)){
   button.textContent=button.dataset.action==='import-doc'?'Thêm tài liệu':button.dataset.action==='assistant-sources'?'Chọn nguồn từ kho':'Công thức và mẫu theo môn';menu.append(button);
  }
  attachments.innerHTML='<button type="button" data-ux-action="attach" aria-label="Thêm tài liệu, nguồn hoặc công thức" aria-expanded="false" aria-controls="chat-attachments">＋</button>';
  assistant.append(menu);
 }
 tools?.remove();
 const sources=$('.assistant-sources');if(sources){sources.classList.add('ux-source-summary');sources.hidden=!(ctx.exam().assistantSources||[]).some(id=>ctx.exam().docs.some(d=>d.id===id));}
 assistant.classList.add('chat-polished');
const composer=$('.compose-box');composer?.insertAdjacentHTML('beforebegin','<section class="chat-source-tools" aria-label="Nguồn cho trợ lý"><div><b>Tài liệu & mẫu</b><span>Bổ sung khi cần</span></div><nav>'+[['assistant-sources','Kho tài liệu','folder'],['subject-library','Theo môn học','book'],['import-doc','Tải tệp','upload']].map(([action,label,symbol])=>'<button type="button" data-action="'+action+'">'+uiIcon(symbol)+'<span>'+label+'</span></button>').join('')+'</nav></section>');
 $('.compose-bottom')?.insertAdjacentHTML('afterbegin','<span class="chat-ai-mark" title="Trợ lý biên soạn">'+uiIcon('sparkle')+'</span>');
 const footer=$('.chat-foot');if(footer){footer.hidden=false;footer.textContent='AI có thể nhầm. Thầy cô kiểm tra lại trước khi dùng.';$('#chat-input').title='Enter gửi · Shift+Enter xuống dòng';}
 $('.chat-compose').insertAdjacentHTML('beforebegin','<button type="button" class="ux-jump-latest" data-ux-action="latest" hidden>↓ Cuối hội thoại</button>');
 body=$('.assistant-body');body.setAttribute('role','log');body.setAttribute('aria-label','Lịch sử trò chuyện');body.setAttribute('aria-live','polite');body.setAttribute('aria-relevant','additions');body.tabIndex=0;
 observer?.disconnect();layoutObserver?.disconnect();workspaceObserver?.disconnect();const mountedBody=body,mountedState=state();
 body.addEventListener('scroll',()=>{mountedState.top=mountedBody.scrollTop;mountedState.follow=mountedBody.scrollHeight-mountedBody.clientHeight-mountedBody.scrollTop<50;if(mountedState.follow)mountedState.unread=false;paintJump();},{passive:true});
 observer=new MutationObserver(()=>{const s=state();if(!s.follow)s.unread=true;requestAnimationFrame(()=>{if(mountedBody!==body)return;resizeInput();if(s.follow)goLatest();else paintJump();});});observer.observe(body,{childList:true});
 layoutObserver=new ResizeObserver(()=>{fitPaper();const form=$('.chat-compose');assistant.style.setProperty('--chat-form-height',(form?.getBoundingClientRect().height||160)+'px');if(state().follow)body.scrollTop=body.scrollHeight;paintJump();});layoutObserver.observe($('.chat-compose'));layoutObserver.observe(body);layoutObserver.observe($('.paper-scroll'));workspaceObserver=new MutationObserver(()=>{const focus=$('.workspace').classList.contains('focus-mode'),button=$('[data-action=design-focus]');if(button){button.setAttribute('aria-pressed',String(focus));button.querySelector('span').textContent=focus?'Thoát tập trung':'Tập trung';}});workspaceObserver.observe($('.workspace'),{attributes:true,attributeFilter:['class']});
 requestAnimationFrame(()=>{if(mountedState.follow)goLatest();else{body.scrollTop=mountedState.top;paintJump();}});
 setExpanded(expanded);updateViewport();refreshUsability();
 if(!initialized){initialized=true;
  document.addEventListener('change',event=>{if(event.target.id==='zoom'){fitZoom=event.target.value==='fit';if(fitZoom){event.stopImmediatePropagation();fitPaper();}}if(['ai-consent','auto-update-answers'].includes(event.target.id))refreshUsability();},true);
  document.addEventListener('input',event=>{if(event.target.id==='chat-input')resizeInput();});
  document.addEventListener('submit',event=>{if(event.target.id==='chat-form'){const s=state();s.follow=true;s.unread=false;}},true);
  document.addEventListener('click',event=>{if(event.target.closest('.ux-attach-menu [data-action]'))closeAttachments();const button=event.target.closest('[data-ux-action]');if(!button)return;const action=button.dataset.uxAction;if(action==='latest')goLatest();if(action==='expand')setExpanded(!expanded);if(action==='attach'){closeOptions();const menu=$('.ux-attach-menu');menu.hidden=!menu.hidden;button.setAttribute('aria-expanded',String(!menu.hidden));if(!menu.hidden)menu.querySelector('button')?.focus();}if(action==='options'){closeAttachments();const panel=$('.ux-chat-options');panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden)panel.querySelector('input,button,select')?.focus();}});
  document.addEventListener('pointerdown',event=>{if(!event.target.closest('.ux-chat-options,[data-ux-action=options]'))closeOptions();if(!event.target.closest('.ux-attach-menu,[data-ux-action=attach]'))closeAttachments();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('#dialog')?.open&&!$('.composer-shell')){if(!$('.ux-chat-options')?.hidden){event.preventDefault();closeOptions(true);}else if(expanded){event.preventDefault();setExpanded(false);$('[data-ux-action=expand]')?.focus();}}
   if(event.key==='Escape'&&!$('.ux-attach-menu')?.hidden){event.preventDefault();closeAttachments(true);}
   if(event.target.id==='chat-input'&&event.key==='Enter'&&!event.shiftKey&&!event.ctrlKey&&!event.metaKey&&!event.isComposing&&event.keyCode!==229){event.preventDefault();$('#chat-form')?.requestSubmit();}});
  window.addEventListener('resize',updateViewport,{passive:true});window.visualViewport?.addEventListener('resize',updateViewport,{passive:true});
 }
}
export function refreshUsability(){if(!ctx||!$('.ux-chat-options'))return;resizeInput();const mode=$('.chat-context-mode');if(mode&&!$('.ux-mode-slot').contains(mode))$('.ux-mode-slot').replaceChildren(mode);const effort=$('.effort-toggle');if(effort)effort.textContent=effort.textContent.replace(/^Mức:\s*/,'');const on=$('#ai-consent')?.checked,automatic=$('#auto-update-answers')?.checked,button=$('[data-ux-action=options]');if(button){button.title='Cài đặt trò chuyện · AI '+(on?'bật':'tắt')+' · Tự cập nhật '+(automatic?'bật':'tắt');button.classList.toggle('ux-auto-on',!!automatic);}paintJump();}
