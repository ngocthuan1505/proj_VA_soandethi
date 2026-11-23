// Presentation state stays separate from the exam, undo history and AI scope.
let ctx,body,observer,layoutObserver,initialized=false,expanded=false,fitZoom=true,workspaceObserver;
const positions=new Map(),$=s=>document.querySelector(s);
const state=()=>{const id=ctx.exam().id;if(!positions.has(id))positions.set(id,{top:0,follow:true,unread:false});return positions.get(id);};
function resizeInput(){const input=$('#chat-input');if(!input)return;const limit=innerHeight<600?64:120;input.style.height='auto';input.style.height=Math.min(limit,Math.max(42,input.scrollHeight))+'px';input.style.overflowY=input.scrollHeight>limit?'auto':'hidden';}
function paintJump(){const button=$('[data-ux-action=latest]');if(!button||!body)return;const s=state();button.hidden=s.follow||body.scrollHeight-body.clientHeight<30;button.textContent=s.unread?'↓ Có tin mới':'↓ Cuối hội thoại';}
function goLatest(){if(!body)return;const s=state();s.follow=true;s.unread=false;body.scrollTop=body.scrollHeight;paintJump();}
function closeOptions(focus=false){const panel=$('.ux-chat-options');if(!panel||panel.hidden)return;panel.hidden=true;const button=$('[data-ux-action=options]');button?.setAttribute('aria-expanded','false');if(focus)button?.focus();}
function closeAttachments(focus=false){const panel=$('.ux-attach-menu');if(!panel||panel.hidden)return;panel.hidden=true;const button=$('[data-ux-action=attach]');button?.setAttribute('aria-expanded','false');if(focus)button?.focus();}
function setExpanded(value){expanded=value;$('.assistant')?.classList.toggle('ux-expanded',value);const button=$('[data-ux-action=expand]');if(button){button.setAttribute('aria-pressed',String(value));button.setAttribute('aria-label',value?'Thu gọn trò chuyện':'Mở rộng trò chuyện');button.title=button.getAttribute('aria-label');button.textContent=value?'⤡':'⤢';}}
function fitPaper(){if(!fitZoom)return;const paper=$('.paper'),scroll=$('.paper-scroll'),select=$('#zoom');if(!paper||!scroll||!select)return;const style=getComputedStyle(scroll),available=scroll.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight)-4,width=paper.querySelector('.document-page')?.offsetWidth||paper.offsetWidth||920,scale=Math.max(.2,Math.min(1,available/width));if(Math.abs((Number(paper.style.zoom)||1)-scale)>.001)paper.style.zoom=String(scale);select.querySelector('[value=fit]').textContent='Vừa ngang ('+Math.round(scale*100)+'%)';}
function updateViewport(){const viewport=window.visualViewport;if(!viewport||viewport.scale===1)document.documentElement.style.setProperty('--chat-viewport-height',(viewport?.height||innerHeight)+'px');resizeInput();fitPaper();}
function syncTimePresetSelect(){
 const compose=$('.chat-compose');
 if(!compose)return;
 const bottom=compose.querySelector('.compose-bottom');
 const bar=compose.querySelector('.time-preset-bar');
 const existing=compose.querySelector('.chat-time-select');
 if(existing&&!existing.hasAttribute('data-ux-time-select')){
  bar?.classList.add('ux-time-bar-hidden');
  return;
 }
 if(!bar||!bottom)return;
 let select=existing;
 if(!select){
  select=document.createElement('select');
  select.className='chat-time-select';
  select.setAttribute('data-ux-time-select','');
  select.setAttribute('aria-label','Thời gian chạy AI');
  select.title='Thời gian chạy AI';
  select.innerHTML='<option value="fast">2p Nhanh</option><option value="standard">5p Chuẩn</option><option value="deep">20p Kỹ</option><option value="extended">60p Sâu</option>';
  const send=bottom.querySelector('button[type=submit]');
  if(send)send.before(select);else bottom.append(select);
 }
 bar.classList.add('ux-time-bar-hidden');
 const activePreset=bar.querySelector('.time-preset-pill.is-active,.time-preset-pill.active')?.dataset.preset||ctx?.exam()?.aiTimePreset||'standard';
 if(select.value!==activePreset)select.value=activePreset;
}
export function mountUsability(context){ctx=context;const assistant=$('.assistant'),head=$('.assistant-head .row');
 if(!assistant||!head)return;$('#chat-input').rows=1;const zoom=$('#zoom');if(zoom){zoom.insertAdjacentHTML('afterbegin','<option value="fit">Vừa chiều ngang</option>');if(fitZoom)zoom.value='fit';}
 const panel=document.createElement('section');panel.id='chat-options';panel.className='ux-chat-options';panel.hidden=true;panel.setAttribute('aria-label','Cài đặt trò chuyện');
 panel.innerHTML='<strong>Cài đặt trò chuyện</strong><p>Áp dụng cho đề đang mở</p><div class="ux-mode-slot"></div>';
 const options=$('.studio-ai-options');if(options)panel.append(options);
 const actions=document.createElement('div');actions.className='ux-option-actions';
 for(const action of ['connections','reset-chat']){const button=head.querySelector('[data-action='+action+']');if(button){button.textContent=action==='connections'?'Kết nối mô hình AI':'Xóa hội thoại…';actions.append(button);}}
 panel.append(actions);assistant.append(panel);
 head.insertAdjacentHTML('afterbegin','<button type="button" data-ux-action="expand" aria-label="Mở rộng trò chuyện" aria-pressed="false" title="Mở rộng trò chuyện">⤢</button><button type="button" data-ux-action="options" aria-label="Cài đặt trò chuyện" aria-expanded="false" aria-controls="chat-options" title="Cài đặt trò chuyện">⋯</button>');
 const toolbar=$('.editor-toolbar');if(toolbar){toolbar.querySelector('[data-action=export]')?.setAttribute('aria-label','In hoặc xuất đề');toolbar.querySelector('[data-action=menu]')?.setAttribute('aria-label','Thêm công cụ định dạng');toolbar.setAttribute('role','toolbar');toolbar.setAttribute('aria-label','Công cụ định dạng, cuộn ngang để xem thêm');const views=document.createElement('div');views.className='ux-view-tabs';for(const tab of toolbar.querySelectorAll('.view-tab'))views.append(tab);toolbar.parentElement.append(views);}
 const attachments=$('.compose-attachments'),tools=$('.design-assistant-tools');
 if(attachments){
  const menu=document.createElement('section');menu.className='ux-attach-menu';menu.id='chat-attachments';menu.hidden=true;menu.setAttribute('aria-label','Thêm vào cuộc trò chuyện');
  for(const button of [...attachments.querySelectorAll('button'),tools?.querySelector('.assistant-library')].filter(Boolean)){
   button.textContent=button.dataset.action==='import-doc'?'Thêm tài liệu':button.dataset.action==='assistant-sources'?'Chọn nguồn từ kho':'Công thức và mẫu theo môn';menu.append(button);
  }
  if(!menu.querySelector('[data-action=subject-library]')){
   const libBtn=document.createElement('button');libBtn.type='button';libBtn.dataset.action='subject-library';libBtn.textContent='Công thức và mẫu theo môn';menu.append(libBtn);
  }
  attachments.innerHTML='<button type="button" data-ux-action="attach" aria-label="Thêm tài liệu, nguồn hoặc công thức" aria-expanded="false" aria-controls="chat-attachments">＋</button>';
  assistant.append(menu);
 }
 tools?.remove();
 const sources=$('.assistant-sources');if(sources){sources.classList.add('ux-source-summary');sources.hidden=!(ctx.exam().assistantSources||[]).some(id=>ctx.exam().docs.some(d=>d.id===id));}
 const footer=$('.chat-foot');if(footer){footer.hidden=true;$('#chat-input').title='Enter gửi · Shift+Enter xuống dòng';}
 $('.chat-compose').insertAdjacentHTML('beforebegin','<button type="button" class="ux-jump-latest" data-ux-action="latest" hidden>↓ Cuối hội thoại</button>');
 body=$('.assistant-body');body.setAttribute('role','log');body.setAttribute('aria-label','Lịch sử trò chuyện');body.setAttribute('aria-live','polite');body.setAttribute('aria-relevant','additions');body.tabIndex=0;
 observer?.disconnect();layoutObserver?.disconnect();workspaceObserver?.disconnect();const mountedBody=body,mountedState=state();
 body.addEventListener('scroll',()=>{mountedState.top=mountedBody.scrollTop;mountedState.follow=mountedBody.scrollHeight-mountedBody.clientHeight-mountedBody.scrollTop<50;if(mountedState.follow)mountedState.unread=false;paintJump();},{passive:true});
 observer=new MutationObserver(()=>{const s=state();if(!s.follow)s.unread=true;requestAnimationFrame(()=>{if(mountedBody!==body)return;resizeInput();if(s.follow)goLatest();else paintJump();});});observer.observe(body,{childList:true});
 layoutObserver=new ResizeObserver(()=>{fitPaper();const form=$('.chat-compose');assistant.style.setProperty('--chat-form-height',(form?.getBoundingClientRect().height||160)+'px');if(state().follow)body.scrollTop=body.scrollHeight;paintJump();});layoutObserver.observe($('.chat-compose'));layoutObserver.observe(body);layoutObserver.observe($('.paper-scroll'));workspaceObserver=new MutationObserver(()=>{const focus=$('.workspace').classList.contains('focus-mode'),button=$('[data-action=design-focus]');if(button){button.setAttribute('aria-pressed',String(focus));const span=button.querySelector('span');if(span)span.textContent=focus?'Thoát tập trung':'Tập trung';}});workspaceObserver.observe($('.workspace'),{attributes:true,attributeFilter:['class']});
 requestAnimationFrame(()=>{if(mountedState.follow)goLatest();else{body.scrollTop=mountedState.top;paintJump();}});
 setExpanded(expanded);updateViewport();refreshUsability();
 if(!initialized){initialized=true;
  document.addEventListener('change',event=>{if(event.target.matches('[data-ux-time-select]')){const preset=event.target.value;const pill=document.querySelector(`.time-preset-bar [data-action="set-time-preset"][data-preset="${preset}"]`);if(pill)pill.click();else if(ctx?.exam()){ctx.exam().aiTimePreset=preset;ctx.persist?.();}return;}if(event.target.id==='zoom'){fitZoom=event.target.value==='fit';if(fitZoom){event.stopImmediatePropagation();fitPaper();}}if(['ai-consent','auto-update-answers'].includes(event.target.id))refreshUsability();},true);
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
export function refreshUsability(){if(!ctx||!$('.ux-chat-options'))return;resizeInput();syncTimePresetSelect();const mode=$('.chat-context-mode');if(mode&&!$('.ux-mode-slot').contains(mode))$('.ux-mode-slot').replaceChildren(mode);const effort=$('.effort-toggle');if(effort)effort.textContent=effort.textContent.replace(/^Mức:\s*/,'');const on=$('#ai-consent')?.checked,automatic=$('#auto-update-answers')?.checked,button=$('[data-ux-action=options]');if(button){button.title='Cài đặt trò chuyện · AI '+(on?'bật':'tắt')+' · Tự cập nhật '+(automatic?'bật':'tắt');button.classList.toggle('ux-auto-on',!!automatic);}paintJump();}
