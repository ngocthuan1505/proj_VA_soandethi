import {openQuestionCheck} from './question-check.js';
import {richTextHTML as katexFragment} from './math-content.js';
import {documentPlain} from './rich-document.js';
import {mountReference,handleReferenceAction,handleReferenceSubmit,handleRubricSubmit,showDropdown,closeFloating,effortInstruction,questionTablesHTML,validateDroppedSourceFile} from './reference.js';
import {AI_PROVIDERS,PROVIDER_INFO,aiRequestError} from './ai-providers.js';
import {connectionSettings,connectionFormData,refreshPocConnections,renderProvidersHealthHTML,formatProviderTestResultHTML} from './connections.js';
import {esc,uid,clone,touch,check,LEVELS,usesTable,commit,blank,isApproved,isConfirmedPreference} from './core.js';
import {mountEditor,initEditor,flushEditor,format,equationHTML,newFormula} from './editor.js';
import katex from './assets/katex/katex.mjs';
import * as db from './storage.js';
let c,status=null,prepared=null,config=null,zoom=100,hideChat=false,activeSourcePage=1,activeSourceDoc=null,ocrAbortController=null,lastExportClassLabel='',latestExportPreflight=null;
const SAFE_LAYOUT_IMAGE_RE=/^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/i;
const $=s=>document.querySelector(s),btn=(a,t,cls='',attrs='')=>`<button data-action="${a}" class="${cls}" ${attrs}>${t}</button>`;
const foot=s=>`<div class="modal-foot">${s}</div>`;
const field=(label,html)=>`<label>${label}${html}</label>`;
const note=s=>`<p class="hint">${s}</p>`;
const consent=id=>`<label class="consent"><input type="checkbox" id="${id}"> Cho phép gửi nội dung đã chọn đến dịch vụ ngoài nếu tác vụ dùng API hoặc máy chủ ngoài máy.</label>`;
async function api(path,data,signal){
 const response=await fetch(path,{signal,headers:{...db.workspaceHeaders(),...(data===undefined?{}:{'Content-Type':'application/json'})},...(data===undefined?{}:{method:'POST',body:JSON.stringify(data)})});
 let result={};
 try{result=await response.json();}catch{}
 if(!response.ok){
  const error=await aiRequestError(path,result.error||result.detail?.message||'Tác vụ chưa thực hiện được.',()=>api('/api/status'));
  error.status=response.status;
  error.code=result.code||result.detail?.code;
  error.data=result;
  throw error;
 }
 return result;
}
async function computeFileSha256(file){
 try{
  if(!globalThis.crypto?.subtle||typeof file?.arrayBuffer!=='function')return null;
  const buf=await file.arrayBuffer();
  const digest=await globalThis.crypto.subtle.digest('SHA-256',buf);
  return Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join('');
 }catch{return null;}
}
export const WORKFLOW_STATUS_LABELS={draft:'Dự thảo',reviewed:'Đã rà soát',approved:'Bản duyệt',printed:'Bản đã in'};
export function normalizeWorkflowStatus(wf){
 return Object.prototype.hasOwnProperty.call(WORKFLOW_STATUS_LABELS,wf)?wf:'draft';
}
export function shouldConfirmStudentExport({batch=false,teacher=false,confirmed=false,classLabel='',workflowStatus='draft',unapprovedCount=0,preflightFailed=false}={}){
 if(batch||teacher||confirmed)return false;
 const officialContext=Boolean(String(classLabel||'').trim())||['approved','printed'].includes(normalizeWorkflowStatus(workflowStatus));
 return officialContext&&(unapprovedCount>0||preflightFailed);
}
export function shouldRequireDraftConfirmation({batch=false,teacher=false,confirmed=false,classLabel='',workflowStatus='draft',unapprovedCount=0,preflightFailed=false}={}){
 if(confirmed)return false;
 if(preflightFailed)return true;
 return shouldConfirmStudentExport({batch,teacher,confirmed,classLabel,workflowStatus,unapprovedCount,preflightFailed});
}
const current=()=>c.exam();
function pagesOf(d){return d.pages?.length?d.pages:d.text?[{number:1,text:d.text,method:'text'}]:[];}
function sourcePageNeedsReview(d,p){return p.needsReview??Boolean(d.needsReview||p.uncertain===true||p.uncertain?.length);}
function sourcesFor(e,onlyDoc=null){return e.docs.filter(d=>!onlyDoc||d.id===onlyDoc).flatMap(d=>pagesOf(d).filter(p=>p.text?.trim()).map(p=>({docId:d.id,page:p.number,text:p.text,location:d.kind==='slides'?'Slide '+p.number:d.kind==='pdf'?'Trang '+p.number:'Văn bản • '+d.name})));}
async function refreshStatus(){status=await api('/api/status');config=status.config;document.querySelectorAll('.mode-notice').forEach(n=>n.innerHTML=`<span class="connection-dot"></span>${status.localPoC?(status.aiProvider==='gemini'?'Gemini API đã chọn: ':'Mô hình trên máy đã chọn: ')+esc(status.model):AI_PROVIDERS.some(p=>config[p]?.model)?'Đã cấu hình đường xử lý · kiểm tra kết nối trong cài đặt':'Chọn kết nối AI để sinh & sửa đề'}<br><small>Tài liệu được đọc và lưu tại máy.</small>`);return status;}
export function renderExportHistoryHTML(rows){
 if(!Array.isArray(rows)||!rows.length)return '<p class="hint">Chưa có bản xuất nào được lưu cho đề này.</p>';
 return rows.slice(0,15).map(item=>{
  const ver=item.revision!=null?`v${item.revision}`:'';
  const roleLabel=(item.audience==='teacher'||item.teacher===true)?'Giáo viên':'Học sinh';
  const fmt=String(item.format||'').toUpperCase();
  const when=item.createdAt||item.at?new Date(item.createdAt||item.at).toLocaleString('vi-VN'):'';
  const label=item.classLabel?` · <b>${esc(item.classLabel)}</b>`:'';
  const draftBadge=item.isDraft?' <span class="pill warn">Nháp</span>':'';
  const href=item.url||item.downloadUrl||'';
  return `<div class="export-history-row"><span>${esc(ver)}${label}${draftBadge} · ${roleLabel} · ${esc(fmt)} · <small>${esc(when)}</small></span>${href?`<a href="${esc(href)}" target="_blank" rel="noopener">Tải lại</a>`:''}</div>`;
 }).join('');
}
export function exportConfirmationNote(format){
 return String(format||'').toLowerCase()==='docx'
  ?'Word giữ công thức sửa được, bảng và định dạng. Hình học trong Word được nhúng thành ảnh; giữ bản JSON nếu cần sửa tọa độ.'
  :'';
}
export function serializeTableCell(cell,cellTokens){
 if(cell&&typeof cell==='object'){
  const tok=cell.data?`[Ảnh #${cellTokens.size+1}${cell.caption?': '+cell.caption:''}]`:cell.type==='doc'?documentPlain(cell):String(cell.text??'');
  if(cell.data||cell.type==='doc')cellTokens.set(tok,clone(cell));
  return tok;
 }
 return String(cell??'');
}
export function buildVisualTableEditorHTML(rows,cellTokens){
 const normalized=(Array.isArray(rows)&&rows.length?rows:[['Đại lượng','Giá trị'],['a','3'],['b','4']]).map(r=>Array.isArray(r)?r:[String(r??'')]);
 const cols=Math.max(1,...normalized.map(r=>r.length));
 const gridRows=normalized.map(r=>Array.from({length:cols},(_,ci)=>serializeTableCell(r[ci]??'',cellTokens)));
 const textValue=gridRows.map(r=>r.join(' | ')).join('\n');
 return `<div class="visual-table-bar buttons" style="margin-bottom:8px">${btn('table-row-add','+ Hàng','tiny-btn','type="button"')}${btn('table-row-del','− Hàng cuối','tiny-btn','type="button"')}${btn('table-col-add','+ Cột','tiny-btn','type="button"')}${btn('table-col-del','− Cột cuối','tiny-btn','type="button"')}</div><table id="visual-table-grid" class="visual-table-editor" aria-label="Bảng dữ liệu câu hỏi"><tbody>${gridRows.map((row,ri)=>`<tr>${row.map((val,ci)=>`<td><input type="text" data-tcell="${ri}:${ci}" value="${esc(val)}" aria-label="Hàng ${ri+1} cột ${ci+1}"></td>`).join('')}</tr>`).join('')}</tbody></table><details><summary>Sửa nhanh dạng văn bản (|)</summary><textarea name="text" rows="4" spellcheck="false">${esc(textValue)}</textarea></details>`;
}
export function readVisualTableRows(form,cellTokens){
 const grid=form?.querySelector?.('#visual-table-grid');
 const textEl=form?.elements?.namedItem?.('text');
 if(grid&&form.dataset.tableMode!=='text'){
  const trs=[...grid.querySelectorAll('tbody tr')];
  if(trs.length){
   return trs.map(tr=>[...tr.querySelectorAll('input[data-tcell]')].map(inp=>{
    const val=String(inp.value??'').trim();
    return cellTokens?.has(val)?clone(cellTokens.get(val)):val;
   }));
  }
 }
 const text=String(textEl?.value||'');
 return text.split('\n').map(l=>l.split('|').map(x=>{const t=x.trim();return cellTokens?.has(t)?clone(cellTokens.get(t)):t;}));
}
function syncVisualTableTextArea(form){
 const grid=form?.querySelector('#visual-table-grid'),ta=form?.elements?.namedItem?.('text');
 if(!grid||!ta)return;
 const lines=[...grid.querySelectorAll('tbody tr')].map(tr=>[...tr.querySelectorAll('input[data-tcell]')].map(inp=>inp.value.trim()).join(' | '));
 ta.value=lines.join('\n');
 form.dataset.tableMode='grid';
}
function updateOllamaModelsUI(models){
 const list=$('#ollama-models-list');
 const chips=$('#ollama-discovered-models');
 const items=(Array.isArray(models)?models:[]).map(m=>typeof m==='string'?m:m?.name).filter(Boolean);
 if(list)list.innerHTML=items.map(id=>`<option value="${esc(id)}"></option>`).join('');
 if(chips)chips.innerHTML=items.slice(0,8).map(id=>`<button type="button" class="tiny-btn" data-action="pick-ollama-model" data-model="${esc(id)}">${esc(id)}</button>`).join('');
}
async function loadProvidersHealth(){
 const strip=$('#providers-health-strip');
 if(!strip)return;
 try{
  const health=await api('/api/providers/health');
  if(!strip.isConnected)return;
  strip.innerHTML=renderProvidersHealthHTML(health,config||{});
  const ollamaModels=health?.providers?.ollama?.models||health?.ollama?.models||[];
  updateOllamaModelsUI(ollamaModels);
 }catch{}
}
let workflowBound=false;
function workflowStripHTML(e){
 const attached=(e.assistantSources||[]).filter(id=>e.docs.some(d=>d.id===id)).length;
 const srcCount=attached||e.docs.length;
 const qCount=e.questions.length,approved=e.questions.filter(isApproved).length,teacher=c.isTeacher();
 return `<nav class="workflow-strip" aria-label="Quy trình và chế độ đề"><div class="wf-steps">${btn('workflow-edit',`${c.icon('file')}<b>Đề gốc</b>${qCount?`<small>${approved}/${qCount}</small>`:''}`,'wf-step wf-step-edit is-active')}${btn('workflow-sources',`<b>Nguồn</b>${srcCount?`<small>${attached||srcCount}</small>`:''}`,'wf-step'+(attached?' is-done':''))}${btn('workflow-matrix',`<b>Ma trận</b>${e.matrixConfirmed?'<small>✓</small>':''}`,'wf-step'+(e.matrixConfirmed?' is-done':''))}${btn('workflow-export',`${c.icon('grid')}<b>Tạo mã đề</b>`,'wf-step wf-step-export')}${btn('question-bank','<b>Ngân hàng</b>','wf-step wf-step-vip','title="Mở Ngân hàng câu hỏi thông minh"')}${btn('exam-analytics','<b>Phân tích</b>','wf-step wf-step-vip','title="Phân tích chất lượng & Ma trận đề"')}</div>${btn('workflow-toggle-view',`<span class="wf-mode-dot"></span><span>${teacher?'Giáo viên · Hiện đáp án':'Học sinh · Ẩn đáp án'}</span>`,'wf-mode-pill '+(teacher?'is-teacher':'is-student'),'title="Chuyển giữa bản Học sinh và bản Giáo viên"')}</nav>`;
}
function renderQuestionAssets(){
 document.querySelectorAll('.question').forEach(el=>{const q=c.qget(el.dataset.q);el.classList.toggle('page-break',!!q.pageBreak);el.querySelector('.q-label').textContent=`${q.type==='essay'?'Bài':'Câu'} ${current().questions.indexOf(q)+1}${q.points?' ('+q.points+' điểm)':''}.`;el.querySelector('.question-assets')?.remove();const assets=document.createElement('div');assets.className='question-assets';assets.innerHTML=equationHTML(q,katex)+questionTablesHTML(q,btn)+(q.images||[]).map(im=>`<figure><img src="${esc(im.data)}" alt="${esc(im.caption||'Hình câu hỏi')}"><figcaption>${esc(im.caption||'')} ${btn('edit-image','Sửa hình','tiny-btn',`data-id="${q.id}" data-image="${im.id}"`)}</figcaption></figure>`).join('');const anchor=el.querySelector('.question-audio-card,.options,.essay-answer,.answer-area');if(anchor)anchor.before(assets);else el.append(assets);});
}
function syncWorkflowStrip(){if(!c)return;const strip=$('.main-footer .workflow-strip')||$('.workflow-strip');if(!strip)return;strip.outerHTML=workflowStripHTML(current());}
export async function initMVP(context){c=context;initEditor(c);try{await refreshStatus();await c.persist();}catch(error){c.toast(error.message);}}
export function mountMVP(context){c=context;c.importDroppedFile=(file,opts)=>importFile(file,opts);const e=current();const wf=normalizeWorkflowStatus(e.workflowStatus);const header=$('header.top');const unified=header?.dataset.unifiedHeader==='1';if(!unified&&header){header.innerHTML=`<div class="mvp-document"><button class="doc-emblem" data-action="new" title="Đề mới">${c.icon('file')}</button><div><div class="document-title-line"><button class="header-title" data-action="metadata">${esc(e.title)}</button><span class="saved"><span data-save-status>Đã lưu trên máy</span></span><select id="workflow-status-select" class="workflow-status-select" data-wf="${esc(wf)}" aria-label="Trạng thái quy trình đề">${Object.entries(WORKFLOW_STATUS_LABELS).map(([k,lbl])=>`<option value="${k}" ${wf===k?'selected':''}>${lbl}</option>`).join('')}</select></div><div class="menubar">${[['file','Tệp'],['edit','Chỉnh sửa'],['view','Xem'],['insert','Chèn'],['format','Định dạng'],['tools','Công cụ']].map(([id,name])=>btn('menu',name,'menu-button',`data-menu="${id}"`)).join('')}</div></div></div><div class="header-actions">${btn('share',c.icon('globe')+'Chia sẻ','quiet')}${btn('library',c.icon('folder')+'Xem kho đề của tôi','quiet')}${btn('toggle-ai',c.icon('chat')+'Hỏi AI','ai-button')}<span class="avatar" title="Nguyễn Hữu Ngọc Thuận">NT</span></div>`;}
 const mainFooter=$('.main-footer');
 if(mainFooter&&!mainFooter.querySelector('.workflow-strip')){
  const legacySpan=mainFooter.querySelector(':scope > span:first-child');
  if(legacySpan)legacySpan.classList.add('footer-legacy-meta');
  const saveWarn=mainFooter.querySelector('[data-save-warning]');
  if(saveWarn)saveWarn.insertAdjacentHTML('afterend',workflowStripHTML(e));
  else mainFooter.insertAdjacentHTML('beforeend',workflowStripHTML(e));
 }
 if(!unified){
  $('.main .workflow-strip')?.remove();
  if($('.document-bar')&&!$('.document-bar .ruler'))$('.document-bar').innerHTML=`<div class="ruler"><i></i>${Array.from({length:17},(_,i)=>`<span>${i+1}</span>`).join('')}<i></i></div>`;
  if($('.editing-bar'))$('.editing-bar').innerHTML=`<div class="editor-toolbar">${btn('toggle-left',c.icon('list'),'tool mobile-nav','aria-label="Mở mục lục"')}<div class="toolgroup">${btn('undo',c.icon('undo'),'tool',`title="Hoàn tác" aria-label="Hoàn tác" ${e.undo.length?'':'disabled'}`)}${btn('redo',c.icon('redo'),'tool',`title="Làm lại" aria-label="Làm lại" ${e.redo.length?'':'disabled'}`)}${btn('export',c.icon('print'),'tool','title="In / Xuất Word, PDF"')}<select id="zoom" aria-label="Độ thu phóng"><option value="75" ${zoom===75?'selected':''}>75%</option><option value="85" ${zoom===85?'selected':''}>85%</option><option value="90" ${zoom===90?'selected':''}>90%</option><option value="100" ${zoom===100?'selected':''}>100%</option><option value="110" ${zoom===110?'selected':''}>110%</option></select></div><span class="toolbar-divider"></span><select id="doc-font" aria-label="Phông chữ"><option ${e.layout?.font!=='Arial'?'selected':''}>Times New Roman</option><option ${e.layout?.font==='Arial'?'selected':''}>Arial</option></select><input id="doc-fontsize" aria-label="Cỡ chữ" type="number" min="10" max="22" value="${e.layout?.fontSize||15}"><span class="toolbar-divider"></span>${btn('format','<b>B</b>','tool','data-command="bold" title="In đậm" aria-label="In đậm"')}${btn('format','<i>I</i>','tool','data-command="italic" title="In nghiêng" aria-label="In nghiêng"')}${btn('format','<u>U</u>','tool','data-command="underline" title="Gạch chân" aria-label="Gạch chân"')}<span class="toolbar-divider"></span>${btn('formula','∑','tool formula-tool','title="Chèn công thức" aria-label="Chèn công thức"')}${btn('chemistry',c.icon('chemistry'),'tool','title="Công thức hóa học" aria-label="Công thức hóa học"')}${btn('subject-library','<span class="formula-tool-symbol">ƒ</span>','tool design-library-open','aria-label="Chèn nội dung theo môn" title="Thư viện công thức & mẫu theo môn"')}${btn('menu','⋮','tool','data-menu="insert" title="Thêm công cụ"')}<span class="toolbar-spacer"></span>${btn('view-student','Đề',!c.isTeacher()?'view-tab active':'view-tab')}${btn('view-teacher','Đáp án',c.isTeacher()?'view-tab active':'view-tab')}</div>`;
 }
 const zoomSel=$('#zoom');if(zoomSel)zoomSel.value=String(zoom);
 const wfSel=$('#workflow-status-select');if(wfSel){wfSel.value=wf;wfSel.dataset.wf=wf;}
 if(!workflowBound){workflowBound=true;document.addEventListener('studio-refreshed',syncWorkflowStrip);}
 const paper=$('.paper');
 if(paper){
  paper.style.setProperty('--doc-font',e.layout?.font||'Times New Roman');paper.style.setProperty('--doc-size',(e.layout?.fontSize||15)+'pt');paper.style.setProperty('--doc-line-height',String(Number(e.layout?.lineHeight)||1.5));paper.classList.toggle('mcq-two-col',Number(e.layout?.mcqColumns)===2);paper.style.zoom=zoom/100;
  $('.paper-watermark-img')?.remove();
  if(typeof e.layout?.watermarkImage==='string'&&SAFE_LAYOUT_IMAGE_RE.test(e.layout.watermarkImage)){const wm=document.createElement('img');wm.className='paper-watermark-img';wm.src=e.layout.watermarkImage;wm.alt='';wm.setAttribute('aria-hidden','true');paper.prepend(wm);}
  const title=$('.paper .title-input'),school=$('.paper-school'),subtitle=$('.paper-subtitle');
  if(title&&school&&subtitle&&!$('.exam-heading')){const block=document.createElement('div');block.className='exam-heading';block.innerHTML=`<div class="school-column"><div>${esc(e.department||'PHÒNG GIÁO DỤC VÀ ĐÀO TẠO')}</div><div>${esc(e.school)}</div><span class="official-label">${e.sample?'ĐỀ MINH HỌA':e.workflowStatus==='printed'?'BẢN ĐÃ IN':(e.workflowStatus==='approved'||e.approvalStatus==='approved')?'ĐỀ CHÍNH THỨC':'ĐỀ KIỂM TRA'}</span></div><div class="exam-heading-main"></div>`;paper.insertBefore(block,school);block.querySelector('.exam-heading-main').append(title,subtitle);school.remove();$('.paper .rule')?.remove();}
 }
 if($('.sidebar-top .eyebrow'))$('.sidebar-top .eyebrow').textContent='Tài liệu & cấu trúc';
 if($('.sidebar-top h2'))$('.sidebar-top h2').textContent=e.subject+' · Lớp '+e.grade;
 if(!unified&&$('.assistant-head .assistant-title'))$('.assistant-head .assistant-title').innerHTML=`<div>Trợ lý AI soạn đề<small>Chỉnh đúng câu · có nguồn để đối chiếu</small></div>`;
 const connBtn=$('.assistant-head [data-action="connections"]');if(connBtn)connBtn.title='Kết nối AI & tìm nguồn';
 const chatInp=$('.chat-compose textarea');if(chatInp)chatInp.placeholder='Nhập yêu cầu tạo, sửa hoặc kiểm tra đề…';
 $('.workspace')?.classList.toggle('chat-hidden',hideChat);
 renderQuestionAssets();
 mountEditor(c);mountReference(c);
 if(status)refreshMode();
}
function refreshMode(){const model=config?.[config?.routes?.generate]?.model;const notice=$('.mode-notice');if(notice)notice.innerHTML=`<span class="connection-dot ${model?'configured':''}"></span>${model?'Đường tạo đề: '+esc(config.routes.generate==='api'&&/127\.0\.0\.1|localhost/.test(config.api.url)?'Cục bộ':PROVIDER_INFO[config.routes.generate]?.label||config.routes.generate)+' · '+esc(model):'Chưa chọn mô hình AI'}<br><small>${config?.localPoC&&config.routes.generate==='gemini'?'Khi sinh đề, ngữ liệu đã chọn được gửi tới Google.':'Tài liệu được đọc và lưu tại máy.'}</small>`;}
function menu(id){const items={file:[['new','Tạo đề mới'],['generate','Tạo đề từ tài liệu'],['library','Mở kho đề'],['import-doc','Thêm tài liệu'],['exam-audio','Gắn Audio nghe cho đề'],['export','Xuất Word / PDF'],['backup-local','Tải bản sao toàn bộ'],['import-backup','Khôi phục bản sao JSON']],edit:[['undo','Hoàn tác'],['redo','Làm lại'],['studio-replace','Tìm và thay thế (Ctrl+H)'],['replace','Thay đoạn đã chọn'],['question-meta','Thuộc tính câu'],['history','Lịch sử phiên bản']],view:[['scroll-marking','Đến hướng dẫn chấm'],['view-student','Xem đề học sinh'],['view-teacher','Xem đáp án'],['matrix','Ma trận'],['toggle-ai','Ẩn / hiện trợ lý']],insert:[['add-question','Thêm câu trắc nghiệm'],['add-essay','Thêm bài tự luận'],['insert-audio','Gắn Audio nghe cho câu'],['formula','Chèn công thức'],['insert-image','Chèn ảnh'],['geometry','Chèn hình hình học'],['insert-table','Chèn bảng'],['page-break','Ngắt trang trước câu']],format:[['align-left','Căn trái'],['align-center','Căn giữa'],['align-justify','Căn đều'],['bullet-list','Danh sách dấu đầu dòng'],['number-list','Danh sách đánh số'],['metadata','Thông tin & đầu đề'],['layout','Định dạng trang']],tools:[['question-bank','Ngân hàng câu hỏi'],['exam-rooms','Phòng thi & giao bài'],['exam-analytics','Phân tích chất lượng đề'],['export-omr-student','Xuất phiếu tô OMR (Bộ GD&ĐT 2025)'],['check-all','Kiểm tra bằng phép tính'],['ai-check','Giải lại câu bằng AI'],['quotes','Đối chiếu đoạn trích'],['extract','Rút trích đề thi'],['memory','Cách ra đề của thầy cô'],['connections','Kết nối AI & tìm nguồn']]};const anchor=document.querySelector(`[data-action="menu"][data-menu="${id}"]`);showDropdown(anchor,`<div class="menu-list" role="menu">${items[id].map(([a,t])=>btn(a,t,'menu-item','role="menuitem"')).join('')}</div>`,'document-menu');}
function showConfig(){if(status?.localPoC&&!config?.gemini){c.modal('AI trên máy',`<p>Hệ thống đang dùng Ollama cục bộ với mô hình <b>${esc(status.model)}</b>. Bật ứng dụng bằng tệp khởi động để chuẩn bị kết nối.</p><p class="hint">Chế độ cục bộ này chưa cấu hình API Gemini, GPT hoặc Claude trong giao diện. Nội dung nguồn chỉ được gửi khi bạn xác nhận.</p>`);return;}c.modal(status?.localPoC?'Kết nối AI':'Kết nối AI & tìm nguồn',connectionSettings(config||{}));void loadProvidersHealth();}
async function saveConfig(){const f=$('#connections-form'),input=connectionFormData(f),changed=AI_PROVIDERS.filter(p=>input[p].url!==config[p]?.url||input[p].model!==config[p]?.model||input[p].key||input[p].clearKey);config=await api('/api/config',input);for(const p of changed){const result=$('#'+p+'-result');if(result)result.textContent='Cấu hình đã đổi. Kiểm tra lại kết nối.';const list=$('#'+p+'-models');if(list)list.innerHTML='';}for(const p of AI_PROVIDERS){const input=f.elements.namedItem(p+'-key');if(input){input.value='';input.placeholder=config[p]?.hasKey?(config.localPoC&&config.persistence?.saved?'Đã lưu mã hóa trên máy — để trống để giữ':'Đã có khóa trong phiên — để trống để giữ'):p==='greennode'?'Để trống nếu Jupyter không yêu cầu token':'Chưa nhập khóa';}const clear=f.elements.namedItem(p+'-clear-key');if(clear)clear.checked=false;}if(config.localPoC){const backup=f.elements.namedItem('gemini-backup-key');if(backup){backup.value='';backup.placeholder=config.gemini?.hasBackupKey?'Đã có key dự phòng — để trống để giữ':'Nhập key của project thứ hai';}const clearBackup=f.elements.namedItem('gemini-clear-backup-key');if(clearBackup)clearBackup.checked=false;const extra=f.elements.namedItem('gemini-extra-keys');if(extra){extra.value='';if(config.gemini?.extraKeysCount)extra.placeholder=`Đã có ${config.gemini.extraKeysCount} khóa bổ sung — để trống để giữ`;}const clearExtra=f.elements.namedItem('gemini-clear-extra-keys');if(clearExtra)clearExtra.checked=false;const dsKey=f.elements.namedItem('deepseek-key');if(dsKey){dsKey.value='';dsKey.placeholder=config.deepseek?.hasKey?'Đã có khóa DeepSeek — để trống để giữ':'Nhập khóa DeepSeek API…';}const clearDs=f.elements.namedItem('deepseek-clear-key');if(clearDs)clearDs.checked=false;if(config.fixedRouter?.timePreset&&c?.exam()){c.exam().aiTimePreset=config.fixedRouter.timePreset;c.refreshInline?.();}}const searchKey=f.elements.namedItem('search-key');if(searchKey)searchKey.value='';refreshMode();return config;}
function showGenerate(){const e=current(),sources=sourcesFor(e);c.modal('Tạo đề từ tài liệu',`<form id="generate-form">${note('Chọn nội dung căn cứ và xác nhận ma trận trước khi tạo. Câu sinh ra được xem trước, chưa tự thay đề hiện tại.')}<div class="generation-summary"><span>${esc(e.subject)} · Lớp ${esc(e.grade)}</span><span>${e.matrix.flatMap(r=>r.targets).reduce((s,n)=>s+n,0)} câu theo ma trận</span>${btn('matrix','Xem / xác nhận ma trận','tiny-btn')}</div>${!e.matrixConfirmed?'<div class="alert">Ma trận chưa xác nhận. Mở ma trận, xem cơ cấu và đánh dấu xác nhận trước khi tạo.</div>':''}<h3>Trang / đoạn được dùng làm nguồn</h3><div class="source-picker">${sources.length?sources.map((s,i)=>`<label class="source-choice"><input name="source" type="checkbox" value="${i}" ${!e.assistantSources?.length||e.assistantSources.includes(s.docId)?'checked':''}><span><b>${esc(e.docs.find(d=>d.id===s.docId)?.name)}</b><small>${esc(s.location)} · ${s.text.length.toLocaleString('vi-VN')} ký tự</small><p>${esc(s.text.slice(0,160))}…</p></span></label>`).join(''):note('Chưa có văn bản đọc được. Thêm tài liệu hoặc chạy rút trích trước.')}</div>${btn('import-doc','Thêm tài liệu','ghost','type="button"')}${field('Dạng câu hỏi',`<select name="questionType"><option value="mcq">Trắc nghiệm nhiều lựa chọn</option><option value="essay" ${e.questions.some(q=>q.type==='essay')?'selected':''}>Tự luận · lời giải và thang điểm</option></select>`)}${field('Yêu cầu cho đề',`<textarea name="request" rows="3" placeholder="Ví dụ: câu hỏi rõ ràng, bám nội dung đã chọn"></textarea>`)}${note('Yêu cầu đã nhớ: '+(e.appliedPrefs.filter(isConfirmedPreference).map(p=>esc(p.text)).join(' · ')||'Chưa có'))}${field('Cách đưa vào đề',`<select name="mode"><option value="append">Thêm câu vào đề hiện tại</option><option value="replace">Thay danh sách câu hiện tại (có hoàn tác)</option></select>`)}<label class="consent"><input type="checkbox" id="auto-check" checked> Tự giải lại câu vừa tạo bằng đường kiểm tra đã cấu hình. Nếu chưa nối, chỉ rà soát tại máy.</label>${consent('generate-consent')}${foot(btn('connections','Kết nối AI','','type="button"')+'<button type="submit" class="primary">Tạo & xem đề xuất</button>')}</form>`);prepared={type:'generation-form',sources,examId:e.id,revision:e.revision};}
function sourceBundleForQuestion(q){return sourcesFor(current(),q.source?.docId).map(s=>({...s,text:s.text.slice(0,14000)}));}
async function generateSubmit(f){const e=current();if(!e.matrixConfirmed)throw Error('Cần xác nhận ma trận trước.');const fd=new FormData(f),sources=fd.getAll('source').map(i=>prepared.sources[Number(i)]);const input={subject:e.subject,grade:e.grade,sources,matrix:clone(e.matrix),prefs:e.appliedPrefs.filter(isConfirmedPreference).map(p=>p.text),questionType:fd.get('questionType'),instructions:fd.get('request')+'\n'+effortInstruction(e),consent:$('#generate-consent').checked};const origin={examId:e.id,revision:e.revision,mode:fd.get('mode'),autoCheck:$('#auto-check').checked,consent:input.consent};c.modal('Đang tạo đề',`<div class="busy"><span class="spinner"></span><p>Đang gửi các đoạn đã chọn tới đường xử lý ${esc(config.routes.generate)}…</p><small>Chỉ thêm vào đề sau khi thầy cô xem và xác nhận.</small></div>`);const result=await api('/api/ai/generate',input);c.addChat('assistant','Đã tạo '+result.questions.length+' câu bằng '+result.model+'. Thầy cô xem đề xuất và xác nhận để đưa vào trang.');c.refreshInline();prepared={type:'generated',...origin,...result};c.modal('Xem câu hỏi vừa tạo',`${note('Kết quả trực tiếp từ '+esc(result.provider)+' · '+esc(result.model)+'. Đoạn trích nguồn đã đối chiếu khớp chữ với tài liệu chọn; chưa bảo đảm nội dung câu đúng.')}<div class="generated-preview">${result.questions.map((q,i)=>`<div class="small-card"><b>${q.type==='essay'?'Bài':'Câu'} ${i+1}${q.points?' ('+q.points+' điểm)':''}. ${q.stem.includes('$')?katexFragment(q.stem):esc(q.stem)}</b>${(q.images||[]).map(im=>`<img class="import-image-preview" src="${esc(im.data)}" alt="${esc(im.caption)}">`).join('')}<p>${q.options.map((o,j)=>`${String.fromCharCode(65+j)}. ${esc(o)}`).join('<br>')}</p><p>Đáp án đề xuất: ${q.type==='essay'?'Tự luận':String.fromCharCode(65+q.answer)} · ${esc(q.explanation)}</p>${q.type==='essay'?`<table class="rubric-table"><tr><th>Nội dung</th><th>Điểm</th></tr>${q.rubric.map(r=>`<tr><td>${esc(r.text)}</td><td>${r.points}</td></tr>`).join('')}</table>`:''}<blockquote>${esc(q.source.quote)}</blockquote><small>${esc(q.source.location)} · ${esc(q.topic)} · ${LEVELS[q.level]}</small></div>`).join('')}</div>${foot(btn('apply-generated','Xác nhận đưa vào đề','primary'))}`);}
async function handleChat(f){const text=$('#chat-input').value.trim();if(!text)return;flushEditor();if(/^đổi thành\s*:/i.test(text)||/^kiểm tra/i.test(text))return false;c.addChat('user',text);c.refreshInline();$('#assistant-body').scrollTop=$('#assistant-body').scrollHeight;$('#chat-input').value='';if(/^tạo|^soạn/iu.test(text)||!current().questions.length){showGenerate();const area=$('#generate-form textarea');if(area)area.value=text;const type=$('#generate-form select[name="questionType"]');if(type&&/tự luận/iu.test(text))type.value='essay';c.refreshInline();return true;}const scope=c.currentScope();if(!scope)throw Error('Chọn một câu hoặc đoạn trước khi nhờ sửa.');prepared={type:'patch-request',scope,request:text,examId:current().id};c.modal('Sửa phần đang chọn',`<div class="scope"><small>CÂU v${scope.version}</small><p>${esc(scope.text)}</p></div><p>${esc(text)}</p>${note('AI sẽ đề xuất chữ thay thế và những phần phụ thuộc trong cùng câu. Các câu khác và ngữ liệu đã duyệt được giữ nguyên.')}${consent('patch-consent')}${foot(btn('request-patch','Gửi yêu cầu sửa','primary'))}`);return true;}
async function requestPatch(){const p=prepared,q=c.qget(p.scope.id),consentValue=$('#patch-consent').checked;if(q.v!==p.scope.version)throw Error('Câu đã đổi, hãy chọn lại.');c.modal('Đang đề xuất sửa','<div class="busy"><span class="spinner"></span>Đang xử lý phần được chọn…</div>');const result=await api('/api/ai/patch',{question:{type:q.type,stem:q.stem,options:q.options,answer:q.answer,explanation:q.explanation},selectedText:p.scope.text,request:p.request+'\n'+effortInstruction(current()),sources:sourceBundleForQuestion(q),consent:consentValue});c.addChat('assistant','Đã có đề xuất sửa: '+(result.reason||'Cập nhật vùng được chọn và lời giải phụ thuộc.')+' Thầy cô xem bản so sánh trước khi áp dụng.');c.refreshInline();const stem=q.stem.slice(0,p.scope.start)+result.replacement+q.stem.slice(p.scope.end);prepared={type:'ai-patch',...p,result,stem,consent:consentValue};prepared.type='ai-patch';c.modal('Xem đề xuất sửa',`<div class="diff"><del>${katexFragment(q.stem)}\nĐáp án: ${String.fromCharCode(65+q.answer)}\n${katexFragment(q.explanation)}</del><ins>${katexFragment(stem)}\nĐáp án: ${String.fromCharCode(65+result.answer)}\n${katexFragment(result.explanation)}</ins></div><h3>Phương án sau sửa</h3>${result.options.map((o,i)=>`<p>${String.fromCharCode(65+i)}. ${katexFragment(o)}</p>`).join('')}<div class="alert">${esc(result.reason||'Cập nhật thân câu và phần phụ thuộc của câu được chọn.')}<br>Chỉ áp dụng cho câu này; cần kiểm tra lại bản mới.</div>${foot(btn('apply-ai-patch','Xác nhận thay đổi','primary'))}`);}
function showAICheck(){const q=c.qget(c.getSelected());if(!q)throw Error('Chọn một câu trước.');prepared={type:'ai-check-request',examId:current().id,id:q.id,version:q.v};c.modal('Giải lại câu bằng AI',`<div class="scope"><small>CÂU v${q.v}</small><p>${esc(q.stem)}</p></div>${note('Bộ giải chỉ nhận thân câu, phương án và căn cứ. Đáp án/giải thích đang lưu được giữ lại để so sánh sau khi có lời giải mới.')}${consent('check-consent')}${foot(btn('request-ai-check','Giải lại & đối chiếu','primary'))}`);}
async function requestCheck(){const p=prepared,q=c.qget(p.id);if(q.v!==p.version)throw Error('Câu đã đổi phiên bản.');const consentValue=$('#check-consent').checked;c.modal('Đang giải lại','<div class="busy"><span class="spinner"></span>Đang giải mà không đưa đáp án đã lưu cho mô hình…</div>');const result=await api('/api/ai/check',{question:{type:q.type,stem:q.stem,options:q.options},sources:sourceBundleForQuestion(q),consent:consentValue});if(current().id!==p.examId||c.qget(p.id)?.v!==p.version)throw Error('Câu đã đổi khi đang giải; chưa lưu kết quả cũ.');const problems=[...(result.issues||[])];if(q.type==='essay')problems.push('Lời giải tự luận cần giáo viên đối chiếu; chưa so sánh tương đương với lời giải đang lưu.');if(q.type!=='essay'&&result.answer!==q.answer)problems.push(`Bất đồng: đáp án lưu ${String.fromCharCode(65+q.answer)}, lời giải lại cho ${String.fromCharCode(65+result.answer)}.`);if(result.uncertain)problems.push('Mô hình báo chưa đủ chắc chắn.');if(!result.sourceVerified)problems.push('Chưa có đoạn trích căn cứ khớp với nguồn.');c.change('Giải lại bằng AI cho câu '+(current().questions.indexOf(q)+1),()=>{q.check={version:q.v,status:problems.length?'review':'consistent',problems,evidence:result.explanation,at:Date.now(),method:'AI giải lại không nhận đáp án cũ · '+result.provider+' · '+result.model,solver:result};});c.addChat('assistant',result.explanation+'\n'+(problems.length?problems.join(' '):'Giáo viên cần đối chiếu lời giải trước khi duyệt.'));c.refreshInline();prepared={type:'ai-check-result',...p,result};prepared.type='ai-check-result';c.modal('Kết quả giải lại',`<div class="alert ${problems.length?'':'success'}">${problems.length?problems.map(esc).join('<br>'):'Chưa thấy bất đồng trong lần giải lại này; giáo viên cần rà soát.'}</div><p>${esc(result.explanation)}</p>${(result.evidence||[]).map(s=>`<blockquote>${esc(s.quote)}<br><small>${s.matched?'Khớp chữ với nguồn đã chọn':'Chưa khớp nguồn'}</small></blockquote>`).join('')}${foot(btn('apply-ai-answer','Dùng đáp án & lời giải này')+btn('approve-question','Tôi đã rà soát · duyệt câu','primary',`data-id="${q.id}"`))}`);}
function showFormula(id,formulaId){const q=c.qget(id||c.getSelected());if(!q)throw Error('Chọn câu cần chèn công thức.');const f=q.formulas?.find(f=>f.id===formulaId);prepared={type:'formula',id:q.id,formulaId};c.modal(f?'Sửa công thức':'Chèn công thức',`<form id="formula-form">${field('Công thức LaTeX',`<textarea id="formula-input" rows="3" required>${esc(f?.latex||'x^2 - 4x + 3 = 0')}</textarea>`)}<div class="formula-presets">${['\\frac{a}{b}','\\sqrt{x}','x^{2}','\\Delta = b^{2}-4ac'].map(l=>btn('formula-preset',esc(l),'tiny-btn',`type="button" data-latex="${esc(l)}"`)).join('')}</div><label>Xem trước</label><div id="formula-preview" class="formula-preview"></div>${note('Chỉ nhập công thức; không chạy lệnh hoặc tải tài nguyên ngoài. Công thức được lưu cùng câu và đưa vào Word/PDF.')}${foot((f?btn('formula-delete','Xóa công thức','danger','type="button"'):'')+'<button type="submit" class="primary">Lưu công thức</button>')}</form>`);previewFormula();}
function previewFormula(){try{$('#formula-preview').innerHTML=katex.renderToString($('#formula-input').value,{throwOnError:true,trust:false,displayMode:true});$('#formula-input').setCustomValidity('');}catch(error){$('#formula-preview').textContent='Công thức chưa hợp lệ: '+error.message;$('#formula-input').setCustomValidity('Kiểm tra cú pháp công thức.');}}
function showImport(){c.modal('Thêm tài liệu vào đề',`${note(status?.localPoC?'Đọc TXT/MD, DOCX, PPTX và PDF có chữ tại máy. PDF scan/ảnh chỉ gửi Gemini sau khi thầy cô cho phép, rồi đối chiếu bản gốc.':'Đọc PDF có chữ, PPTX, DOCX, TXT/MD tại máy. Với trang scan hoặc ảnh, chạy rút trích tiếng Việt/Anh rồi đối chiếu bản gốc.')}<div class="upload-zone"><label for="mvp-file">Chọn hoặc kéo–thả tài liệu</label><input id="mvp-file" type="file" accept=".pdf,.pptx,.docx,.txt,.md,.png,.jpg,.jpeg,.webp"><p class="hint">Tối đa 15 MB · hỗ trợ .docx, .pdf, .pptx, .txt, .md, ảnh. Không tự gửi tài liệu sang AI khi tải tệp.</p></div><form id="mvp-paste"><h3>Hoặc dán văn bản</h3>${field('Tên tài liệu','<input name="name" required maxlength="180">')}${field('Nội dung','<textarea name="text" rows="7" required></textarea>')}${foot('<button type="submit" class="primary">Lưu tài liệu</button>')}</form>`);}
async function finishSourceImport(origin,result){
 if(current().id!==origin.examId)throw Error('Đã chuyển đề trong lúc đọc. Chưa thêm tài liệu; mở lại ở đúng đề.');
 if(origin.data){
  await db.put('file:'+origin.fileId,origin.data);
  if(current().id!==origin.examId)throw Error('Đã chuyển đề trong lúc lưu tệp; mở lại ở đúng đề.');
 }
 const d={id:uid(),fileId:origin.fileId,name:origin.name,sha256:origin.sha256||null,version:1,kind:origin.kind||(origin.ext==='pdf'?'pdf':origin.ext==='pptx'?'slides':['docx','txt','md'].includes(origin.ext)?'text':'image'),sample:false,pages:result.pages,text:result.pages.map(p=>p.text).join('\n\n'),method:result.method,needsReview:!!result.needsReview,notes:result.notes||'',warnings:result.warnings||[],uploaded:Date.now()};
 c.change('Nhập tài liệu '+d.name,e=>{
  e.docs.push(d);
  if(origin.attachToAssistant){
   e.assistantSources=[...new Set([...(e.assistantSources||[]),d.id])];
   const readableNums=(d.pages||[]).filter(p=>p.text?.trim()).map(p=>p.number);
   if(readableNums.length){
    e.assistantSourcePages={...(e.assistantSourcePages||{}),[d.id]:readableNums};
   }
  }
 });
 await showSource(d.id,1);
 if(origin.attachToAssistant)c.toast('Đã nạp và gắn nguồn cho Trợ lý: '+d.name);
}
function showSourceConsent(origin){
 prepared={type:'source-ocr',...origin};
 const pending=prepared;
 $('#dialog').addEventListener('close',()=>{if(prepared===pending)prepared=null;},{once:true});
 c.modal('Đọc PDF / ảnh bằng Gemini',`<form id="source-ocr-form"><p><b>${esc(origin.name)}</b></p><p>Tệp cần nhận dạng. Chưa gửi tệp ra ngoài. Sau khi cho phép, nội dung được gửi tới Gemini và cần đối chiếu trước khi dùng làm nguồn.</p><label><input type="checkbox" id="source-ocr-consent" required> Cho phép gửi đúng tệp này tới Gemini để đọc chữ.</label>${foot('<button type="button" data-action="close">Hủy</button><button type="submit" class="primary">Đọc bằng Gemini</button>')}</form>`);
}
async function importFile(file,options={}){
 if(file&&/\.xlsx?$/i.test(file.name||'')){
  throw Error('Tệp Excel (.xlsx) dùng để nhập Ma trận đề. Hãy mở tab Ma trận ở thanh bên trái và chọn Nhập Excel / JSON.');
 }
 const checkFile=validateDroppedSourceFile(file);
 if(!checkFile.ok)throw Error(checkFile.error);
 const examId=current().id,ext=checkFile.ext;
 const sha256=await computeFileSha256(file);
 if(current().id!==examId)throw Error('Đã chuyển đề; chọn lại tệp ở đúng đề.');
 const dupDoc=sha256?current().docs.find(d=>d.sha256&&d.sha256===sha256):null;
 if(dupDoc){
  if(options.attachToAssistant&&!(current().assistantSources||[]).includes(dupDoc.id)){
   c.change('Gắn lại tài liệu trùng vào trợ lý',e=>{e.assistantSources=[...(e.assistantSources||[]),dupDoc.id];},{renderPage:false});
  }
  c.toast(`Tệp "${dupDoc.name}" đã có trong đề (trùng nội dung SHA-256). Đang mở lại bản đã nhập.`);
  await showSource(dupDoc.id,1);
  return;
 }
 const fileId=uid(),data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file);});
 if(current().id!==examId)throw Error('Đã chuyển đề; chọn lại tệp ở đúng đề.');
 const origin={examId,fileId,name:file.name,ext,sha256,kind:checkFile.kind,attachToAssistant:Boolean(options.attachToAssistant)};
 if(status?.localPoC)origin.data=data;
 else await db.put('file:'+fileId,data);
 c.modal('Đang đọc tài liệu','<div class="busy" role="status"><span class="spinner"></span>Đang đọc nội dung tại máy…</div>');
 const waiting=$('#dialog .busy');
 try{
  const result=await api('/api/extract',{name:file.name,...(origin.data?{data}:{fileId})});
  if(waiting.isConnected&&$('#dialog').open)await finishSourceImport(origin,result);
 }catch(error){
  if(!waiting.isConnected||!$('#dialog').open)return;
  if(error.code==='document_ai_consent')showSourceConsent(origin);
  else{showImport();sourceImportError('.upload-zone',error);}
 }
}
function sourceImportError(selector,error){
 $('#dialog '+selector)?.insertAdjacentHTML('afterbegin',`<p class="alert" role="alert">${esc(error.message)}</p>`);
}
async function showSource(docId,page=1){const e=current(),q=c.qget(c.getSelected()),d=e.docs.find(d=>d.id===(docId||q?.source?.docId));if(!d){c.showSource(docId,q?.id);return;}activeSourceDoc=d.id;activeSourcePage=Number(page);if(d.fileId)await db.get('file:'+d.fileId);const pages=pagesOf(d),matchedPage=pages.find(p=>p.number===activeSourcePage);
if(!matchedPage&&(pages.length||activeSourcePage!==1)){
 c.modal(d.name,`<p class="alert" role="alert">Trang ${esc(activeSourcePage)} không còn trong tài liệu. Hãy đối chiếu tệp nguồn và xác định lại trang của câu.</p>${pages.length?foot(btn('open-source','Mở tài liệu từ đầu','','data-doc="'+esc(d.id)+'"')):''}`);
 return;
}
const p=matchedPage||{number:1,text:''};activeSourcePage=p.number;const original=d.fileId?await db.get('file:'+d.fileId):null;const image=d.kind==='pdf'&&!status?.localPoC?`/api/page-image?file=${d.fileId}&page=${p.number}`:d.kind==='image'?original:null;const warningsHtml=(d.warnings||[]).length?`<div class="alert">${d.warnings.map(w=>esc(w.message)).join('<br>')}</div>`:'';c.modal(d.name,`<div class="source-controls"><span class="pill">${d.sample?'Tài liệu mẫu tự soạn':d.method==='gemini_document_ocr'?'AI đã đọc':p.method==='tesseract-local'?'Đã rút trích tại máy':'Nội dung đọc từ tệp'}</span>${pages.length>1?`<select id="source-page" aria-label="Trang / slide">${pages.map(x=>`<option value="${x.number}" ${x.number===p.number?'selected':''}>${d.kind==='slides'?'Slide':'Trang'} ${x.number}</option>`).join('')}</select>`:''}${d.kind==='pdf'&&status?.localPoC?`<a href="/api/source-file/${esc(d.fileId)}#page=${esc(p.number)}" target="_blank" rel="noopener noreferrer">Mở PDF gốc</a>`:''}${btn('remove-doc','Gỡ tài liệu','danger tiny-btn',`data-doc="${d.id}"`)}${btn('source-extract',status?.localPoC?'Đọc lại tài liệu':'Rút trích trang này','',`data-doc="${d.id}"`)}${btn('parse-old','Tách câu từ văn bản','',`data-doc="${d.id}"`)}${btn('matrix-from-source','Đọc ma trận','',`data-doc="${d.id}"`)}</div>${warningsHtml}${sourcePageNeedsReview(d,p)?note('Trang này cần đối chiếu bản gốc trước khi dùng làm nguồn.'+(d.notes?' '+esc(d.notes):'')):p.needsReview===false?note('Trang này đã được đối chiếu.'):''}${q?.source?.docId===d.id&&q.source.page===p.number&&q.source.quote?`<blockquote class="matched-quote">Đoạn căn cứ của câu đang chọn:<br>${esc(q.source.quote)}</blockquote>`:''}<div class="${image?'scan-layout':'source-text-layout'}">${image?`<div><h3>Bản gốc · trang ${p.number}</h3><img class="source-frame source-page-image" src="${esc(image)}" alt="Bản gốc trang ${p.number}"></div>`:''}<div><h3>${d.kind==='slides'?'Văn bản slide':'Văn bản chỉnh sửa được'}</h3><form id="source-text-form" data-exam="${esc(e.id)}" data-doc="${esc(d.id)}" data-page="${p.number}" data-version="${d.version||1}"><textarea name="text" rows="14" aria-label="Nội dung nguồn trang ${p.number}" ${d.personalLesson?'readonly':''}>${esc(p.text||'')}</textarea>${p.uncertain?.length?`<div class="uncertain-words">Chỗ cần đối chiếu: ${p.uncertain.slice(0,40).map(w=>`<mark title="Độ tin cậy máy: ${Math.round(w.confidence)}%">${esc(w.text)}</mark>`).join(' ')}</div>`:''}${note(p.needsOCR?'Trang chưa có văn bản. Bấm rút trích hoặc nhập tay.':'Sửa văn bản nguồn sẽ làm các câu đang gắn nguồn này cần rà soát lại. Chỉ vị trí/đoạn trích có thật mới được dùng khi sinh đề.')}${d.personalLesson?note('Sửa nội dung này trong Học liệu theo bài, mục Kho cá nhân.'):'<button type="submit">Lưu bản đối chiếu</button>'}</form></div></div>${foot(btn('generate-from-source','Dùng tài liệu để tạo đề','primary','data-doc="'+esc(d.id)+'"'))}`);}
async function runOCR(docId){const d=current().docs.find(d=>d.id===docId);if(status?.localPoC){if(!d?.fileId)throw Error('Chưa có tệp gốc.');showSourceConsent({examId:current().id,fileId:d.fileId,name:d.name,ext:d.name.split('.').pop().toLowerCase(),docId:d.id,page:activeSourcePage});return;}if(!d?.fileId)throw Error('Tài liệu này không có ảnh/PDF gốc.');if(!['image','pdf'].includes(d.kind))throw Error('Tệp này đã đọc văn bản trực tiếp; không cần nhận dạng ảnh.');await db.get('file:'+d.fileId);const page=activeSourcePage;ocrAbortController?.abort();ocrAbortController=new AbortController();const signal=ocrAbortController.signal;c.modal('Rút trích đề thi',`<div class="busy"><span class="spinner"></span>Đang nhận dạng tiếng Việt và tiếng Anh tại máy…<p>Đối chiếu công thức, ký hiệu và các từ bị đánh dấu sau khi xong.</p></div>${foot(btn('cancel-ocr','Hủy nhận dạng','danger'))}`);try{const result=await api('/api/ocr',{fileId:d.fileId,name:d.name,page},signal);c.change('Rút trích trang '+page+' của '+d.name,e=>{d.pages??=[{number:1,text:''}];const p=d.pages.find(p=>p.number===page);Object.assign(p,{...result,needsOCR:false});d.text=d.pages.map(p=>p.text).join('\n\n');e.questions.filter(q=>q.source?.docId===d.id).forEach(q=>{touch(q);check(e,q);});});await showSource(d.id,page);}catch(error){if(error?.name==='AbortError'){c.toast('Đã hủy quá trình nhận dạng OCR.');return;}throw error;}finally{ocrAbortController=null;}}
function showExtract(){const docs=current().docs.filter(d=>['image','pdf'].includes(d.kind));c.modal('Rút trích đề thi',`${note('Nhận dạng tại máy bằng dữ liệu tiếng Việt/Anh. Văn bản và vị trí chưa chắc được giữ để thầy cô đối chiếu; ký hiệu Toán cần kiểm tra lại.')}<div class="small-card">${docs.length?docs.map(d=>`<div class="row space"><span>${esc(d.name)}</span>${btn('open-source','Mở & rút trích','',`data-doc="${d.id}"`)}</div>`).join(''):note('Chưa có ảnh hoặc PDF trong đề này.')}</div>${foot(btn('import-doc','Thêm ảnh / PDF gốc','primary'))}`);}
async function parseOld(id,allPages=false){const d=current().docs.find(d=>d.id===id),pages=pagesOf(d),currentPage=pages.find(p=>p.number===activeSourcePage);const payload=allPages?{text:'',pages:pages.map(p=>({number:p.number,text:p.text||'',images:p.images||[]}))}:{text:currentPage?.text||d.text||'',images:currentPage?.images||[],page:activeSourcePage};const result=await api('/api/parse-questions',payload);if(!result.questions?.length)throw Error(result.issues?.[0]?.message||'Chưa tìm thấy câu đánh số “Câu 1.” hoặc “Bài 1.”. Có thể sửa bản nhập rồi thử lại.');prepared={type:'old-questions',docId:id,page:activeSourcePage,allPages,questions:result.questions,examId:current().id,revision:current().revision};const summary=result.summary,issuesHtml=result.issues?.length?`<div class="alert" id="parse-issues"><b>Cần rà ${result.issues.length} mục theo trang/câu:</b><ul>${result.issues.map(issue=>`<li>${esc(issue.message)}</li>`).join('')}</ul></div>`:'';c.modal('Xem câu tách từ đề cũ',`${note('Đây là tách cấu trúc bằng quy tắc, chưa suy luận đáp án. Thầy cô cần điền đáp án và rà soát ký hiệu trước khi duyệt.')}${pages.length>1?`<div class="toolbar-row">${btn(allPages?'parse-old':'parse-old-all',allPages?'Chỉ tách trang '+activeSourcePage:'Tách toàn bộ tài liệu ('+pages.length+' trang)','tiny-btn',`type="button" data-doc="${esc(id)}"`)}${summary?`<span class="pill">${summary.totalQuestions} câu · ${summary.pagesScanned} trang</span>`:''}</div>`:summary?`<p class="hint">Đã đọc ${summary.totalQuestions} câu · ${summary.completeCount} đủ phương án · ${summary.needsReviewCount} cần rà.</p>`:''}${issuesHtml}<div class="generated-preview">${result.questions.map((q,i)=>`<div class="small-card"><b>${q.type==='essay'?'Bài':'Câu'} ${i+1}${q.points?' ('+q.points+' điểm)':''}. ${q.stem.includes('$')?katexFragment(q.stem):esc(q.stem)}</b>${q.sourcePage?`<span class="pill">Trang ${q.sourcePage}</span> `:''}${q.incomplete?'<span class="pill warn">Cần bổ sung phương án</span> ':''}${q.needsReview&&!q.incomplete?'<span class="pill warn">Cần rà lại (OCR/công thức)</span>':''}${(q.images||[]).map(im=>`<img class="import-image-preview" src="${esc(im.data)}" alt="${esc(im.caption)}">`).join('')}<p>${q.options.map((o,j)=>String.fromCharCode(65+j)+'. '+esc(o||'[chưa đọc được]')).join('<br>')}</p></div>`).join('')}</div>${foot(btn('apply-old-questions','Thêm vào đề hiện tại')+btn('apply-old-questions','Mở thành đề mới','primary','data-mode="new"'))}`);}
let exportVariantSelection;
function collectEditorPages(){
 const sheets=[...document.querySelectorAll('.document-page')];
 if(!sheets.length)return null;
 return sheets.map((sheet,index)=>({
  page:Number(sheet.dataset.page)||index+1,
  questionIds:[...sheet.querySelectorAll('.question[data-q]')].map(node=>node.dataset.q).filter(Boolean),
  oversize:sheet.classList.contains('oversize-page'),
 }));
}
async function loadExportPreflight(examSnapshot){
 const panel=$('#export-preflight-panel');
 if(!panel)return;
 try{
  const report=await api('/api/exports/preflight',{exam:examSnapshot,editorPages:collectEditorPages()});
  if(!panel.isConnected||!$('#dialog').open||current().id!==examSnapshot.id||current().revision!==examSnapshot.revision)return;
  latestExportPreflight={examId:examSnapshot.id,revision:examSnapshot.revision,report};
  const align=report.pageBreakAlignment||{},ocr=report.ocrReviewItems||[],blocking=report.blockingIssues||[],warnings=report.warnings||[];
  const statusClass=!report.ready?'preflight-status-block':report.needsAttention?'preflight-status-warn':'preflight-status-ok';
  const statusLabel=!report.ready?`Có ${blocking.length} lỗi cần sửa trước khi in`:report.needsAttention?'Cần rà soát ngắt trang / OCR trước khi in':'Bản in đạt kiểm tra cơ bản';
  const editorText=align.editorPageCount!=null?`Bàn soạn: ${align.editorPageCount} trang · `:'';
  const pageLine=`${editorText}Dự kiến A4: ${align.estimatedA4PageCount??0} trang${align.explicitPageBreakOrdinals?.length?` · Ngắt trang tay trước câu ${align.explicitPageBreakOrdinals.join(', ')}`:''}${align.oversizePages?.length?` · Trang vượt khổ A4: ${align.oversizePages.join(', ')}`:''}`;
  const mismatchMessages=(align.pageMismatches||[]).map(m=>m.message||`Câu ${m.ordinal}: bàn soạn trang ${m.editorPage} / dự kiến A4 trang ${m.estimatedA4Page}`);
  const seenIssues=new Set(mismatchMessages);
  const mismatchHtml=mismatchMessages.length?`<ul class="preflight-list">${mismatchMessages.slice(0,5).map(msg=>`<li>${esc(msg)}</li>`).join('')}</ul>`:'';
  const ocrHtml=ocr.length?`<div class="preflight-ocr"><b>Thành phần OCR / nguồn cần giáo viên duyệt (${ocr.length}):</b><ul class="preflight-list">${ocr.slice(0,6).map(item=>`<li><span>${esc(item.message)}</span>${item.docId?` ${btn('source','Mở nguồn','tiny-btn',`type="button" data-doc="${esc(item.docId)}" data-page="${esc(item.page||1)}"`)}`:''}</li>`).join('')}</ul></div>`:'<p class="hint">Không có vùng OCR chưa duyệt cần gắn cờ.</p>';
  const uniqueIssues=[...blocking,...warnings].filter(issue=>issue?.message&&!seenIssues.has(issue.message)&&(seenIssues.add(issue.message),true));
  const issuesHtml=uniqueIssues.length?`<ul class="preflight-list">${uniqueIssues.slice(0,6).map(issue=>`<li>${esc(issue.message)}</li>`).join('')}</ul>`:'';
  panel.dataset.preflightLoaded='true';
  panel.dataset.preflightReady=String(Boolean(report.ready));
  panel.innerHTML=`<div class="preflight-head"><b>1. Đối chiếu bản in &amp; OCR</b><span class="pill ${statusClass}">${esc(statusLabel)}</span></div><p class="hint">${esc(pageLine)}</p>${mismatchHtml}${ocrHtml}${issuesHtml}`;
 }catch(error){
  if(!panel.isConnected)return;
  panel.dataset.preflightLoaded='error';
  panel.innerHTML=`<p class="hint">Chưa tải được đối chiếu bản in: ${esc(error.message)}</p>`;
 }
}
async function loadExportHistory(examId){
 const box=$('#export-history-list');
 if(!box)return;
 try{
  const res=await fetch('/api/exams/'+encodeURIComponent(examId)+'/exports',{headers:db.workspaceHeaders()});
  if(!box.isConnected||!$('#dialog').open||current().id!==examId)return;
  if(res.status===404||!res.ok){
   box.innerHTML='<p class="hint">Chưa có lịch sử bản đã xuất cho đề này.</p>';
   return;
  }
  const data=await res.json();
  const rows=Array.isArray(data?.exports)?data.exports:(Array.isArray(data?.items)?data.items:[]);
  box.innerHTML=renderExportHistoryHTML(rows);
  }catch{
   if(box.isConnected)box.innerHTML='<p class="hint">Chưa tải được lịch sử bản đã xuất.</p>';
  }
 }
function showExport(){latestExportPreflight=null;const e=current(),snapshot=clone(e);c.modal('Xuất đề & Mã đề',`${note('Xuất Word, PDF hoặc HTML. Bản Word giữ công thức sửa được; hình học được nhúng dưới dạng ảnh.')}<section id="export-preflight-panel" class="small-card export-preflight-panel" aria-live="polite" data-preflight-loaded="false"><p class="hint">Đang đối chiếu ngắt trang bàn soạn ↔ A4 và thành phần OCR…</p></section>${status?.matrixPython&&e.questions.length>=2?`<details id="export-variants"><summary>Tạo nhiều mã đề (trộn câu &amp; phương án)</summary><fieldset><legend>Câu được đổi thứ tự</legend><p>Chọn ít nhất hai câu độc lập, cùng dạng. Thứ tự phương án và đáp án từng câu được giữ.</p>${e.questions.map((q,i)=>`<label class="consent"><input type="checkbox" value="${esc(q.id)}" data-kind="${esc(q.type||'mcq')}"> Câu ${i+1} · ${esc((q.stem||'').slice(0,90))}</label>`).join('')}</fieldset><label for="export-variant-code">Bản xuất</label><select id="export-variant-code"></select><p data-variant-status role="status"></p></details>`:''}<h3 class="export-section-title">2. Tách bản Học sinh &amp; Giáo viên</h3><div class="export-class-row"><label for="export-class-label">Lớp / đợt thi (tùy chọn)</label><input id="export-class-label" maxlength="80" placeholder="Ví dụ: Lớp 9A · Giữa kỳ I" value="${esc(lastExportClassLabel)}"></div><div class="grid2 export-cards-grid">${[false,true].map(t=>`<div class="choice-card export-choice-card ${t?'is-teacher':'is-student'}"><span class="pill ${t?'export-badge-teacher':'export-badge-student'}">${t?'GIÁO VIÊN · ĐỦ ĐÁP ÁN &amp; BAREM':'HỌC SINH · SẠCH 100% ĐÁP ÁN'}</span><h3>${t?'Bản giáo viên':'Bản học sinh'}</h3><p>${t?'Có đáp án, lời giải, nguồn căn cứ và trạng thái rà soát.':'Chỉ chứa câu hỏi và ngữ liệu; không lộ đáp án hay hội thoại.'}</p><div class="export-formats">${['docx','pdf','html'].map(format=>btn('export-file',format==='docx'?'Word (.docx)':format==='pdf'?'PDF':'HTML',format==='docx'?'primary':'',`data-teacher="${t}" data-format="${format}"`)).join('')}</div></div>`).join('')}</div><details id="export-extended-a4"><summary>3. Đáp án/Barem, Ma trận/Đặc tả A4 &amp; Gói khóa QR</summary><label class="consent"><input type="checkbox" id="export-matrix-landscape"> Khổ A4 ngang (landscape) cho Ma trận &amp; Đặc tả</label><div class="export-formats">${btn('export-extended','Đáp án &amp; Barem (HTML A4)','','data-kind="answer-key-rubric" data-format="html"')}${btn('export-extended','Đáp án &amp; Barem (Word)','','data-kind="answer-key-rubric" data-format="docx"')}${btn('export-extended','Ma trận &amp; Đặc tả (HTML A4)','','data-kind="matrix-specification" data-format="html"')}${btn('export-extended','Ma trận &amp; Đặc tả (Word)','','data-kind="matrix-specification" data-format="docx"')}${btn('export-tnmaker','Gói khóa đáp án &amp; QR (.zip)','','type="button"')}</div><p class="hint">Gói khóa đáp án &amp; QR xuất bảng <code>DapAn.xlsx</code> và ảnh <code>QR_DapAn.png</code> theo định dạng chuẩn chung (chưa xác minh tương thích trực tiếp phần mềm TNMaker bên thứ ba).</p></details><section id="export-omr-panel" class="small-card export-omr-panel"><div class="export-omr-head"><b>4. Phiếu trả lời trắc nghiệm OMR (Bộ GD&amp;ĐT 2025)</b><span class="pill export-badge-student">CHUẨN A4 2025</span></div><p class="hint">Xuất phiếu tô đáp án chuẩn Bộ GD&amp;ĐT 2025 (Phần I Trắc nghiệm, Phần II Đúng–Sai, Phần III Trả lời ngắn) sẵn sàng in A4 hoặc PDF.</p><div class="export-formats">${btn('export-omr-student','Phiếu OMR Học sinh (A4)','primary','type="button"')}${btn('export-omr-pdf','Phiếu OMR Học sinh (PDF)','','type="button"')}${btn('export-omr-teacher','Phiếu OMR Đáp án GV','','type="button"')}</div></section><section id="export-history-panel" class="small-card export-history-panel" aria-live="polite"><div class="export-history-head"><b>5. Lịch sử bản đã xuất</b></div><div id="export-history-list"><p class="hint">Đang tải lịch sử bản đã xuất…</p></div></section><div class="alert">${e.questions.filter(q=>!isApproved(q)).length} câu chưa được giáo viên duyệt.</div>${foot(btn('backup-local','Sao lưu toàn bộ đề (.json)'))}`);
 void loadExportPreflight(snapshot);
 void loadExportHistory(snapshot.id);
 const variants=$('#export-variants');
 if(!variants)return;
 const guide=variants.querySelector('fieldset p');
 guide.textContent='Chọn ít nhất hai câu cùng phần, cùng dạng và cùng ngữ liệu bảng.';
 variants.insertAdjacentHTML('beforeend',`<label class="consent"><input type="checkbox" id="export-shuffle-options"> Trộn phương án trắc nghiệm phù hợp và đổi đáp án theo</label>
 <p class="hint">Phương án phụ thuộc vị trí, ví dụ “Cả hai phương án trên”, được giữ theo thứ tự gốc.</p>
 <button type="button" data-action="preview-variant">Xem trước mã đã chọn</button>`);
 variants.insertAdjacentHTML('beforeend',`<div data-variant-pack hidden>
  <p>Mỗi mã có một bản học sinh sạch đáp án. Bảng đối chiếu đáp án nằm trong thư mục giáo viên.</p>
  <div class="export-formats">${['docx','pdf','html'].map(format=>btn('export-pack','Bộ '+({docx:'Word',pdf:'PDF',html:'HTML'}[format]),'',`data-format="${format}"`)).join('')}${btn('export-tnmaker','Gói khóa đáp án &amp; QR (.zip)','','type="button"')}</div>
 </div><div data-variant-preview aria-live="polite"></div>`);
 const code=$('#export-variant-code'), previous=exportVariantSelection?.examId===e.id?exportVariantSelection:null;
 const shuffle=$('#export-shuffle-options');
 for(const input of variants.querySelectorAll('input[data-kind]'))input.checked=previous?.questionIds.includes(input.value)===true;
 shuffle.checked=previous?.shuffleOptions===true;
 variants.open=Boolean(previous?.questionIds.length);
 function update(preferred){
  const selected=[...variants.querySelectorAll('input[data-kind]:checked')];
  const valid=selected.length>=2&&new Set(selected.map(input=>input.dataset.kind)).size===1;
  code.replaceChildren(new Option('Đề gốc',''));
  if(valid)for(let i=0;i<Math.min(selected.length,6);i++)code.add(new Option('Mã đề '+(101+i),String(i)));
  code.value=[...code.options].some(option=>option.value===preferred)?preferred:'';
  shuffle.disabled=!valid||selected[0]?.dataset.kind!=='mcq';
  variants.querySelector('[data-action="preview-variant"]').disabled=!code.value;
  variants.querySelector('[data-variant-pack]').hidden=!valid;
  variants.querySelector('[data-variant-status]').textContent=valid?'Chọn mã để xem trước hoặc tải.':'Chọn ít nhất hai câu cùng dạng để tạo mã.';
 }
 update(previous?.code);
 variants.addEventListener('change',()=>{
  update(code.value);
  variants.querySelector('[data-variant-preview]').replaceChildren();
 });
}
function exportVariantSettings(){
 const shuffle=$('#export-shuffle-options');
 return {
  questionIds:[...document.querySelectorAll('#export-variants input[data-kind]:checked')].map(input=>input.value),
  shuffleOptions:Boolean(shuffle?.checked&&!shuffle.disabled),
 };
}
async function previewVariant(node){
 if(!flushEditor())throw Error('Gõ xong chữ đang nhập rồi thử lại.');
 const exam=clone(current()),view=node.parentElement.querySelector('[data-variant-preview]');
 const code=$('#export-variant-code').value;
 if(!code)return;
 const pending=document.createElement('p');
 pending.textContent='Đang chuẩn bị thứ tự câu…';
 view.replaceChildren(pending);
 try{
  const result=await api('/api/preview-variant',{exam,variant:{...exportVariantSettings(),offset:Number(code)}});
  if(!pending.isConnected||!$('#dialog').open||current().id!==exam.id||current().revision!==exam.revision)return;
  view.innerHTML=`<section class="small-card variant-preview"><h3>${esc(result.title)}</h3><p>Đối chiếu đề gốc theo số ghi cạnh mỗi câu.</p><ol tabindex="0" aria-label="Thứ tự câu hỏi và phương án">${result.questions.map((q,i)=>{const pInfo=result.questionPassages?.[i]||q;return `<li>${(pInfo.passageTitle||pInfo.passageText)?`<div class="passage-box" style="margin-bottom:6px;background:var(--bg-subtle,#edf3fa);padding:6px 10px;border-left:3px solid var(--brand,#0f4c81);border-radius:4px;"><b>${esc(pInfo.passageTitle||'')}</b><p style="margin:2px 0 0;">${esc(pInfo.passageText||'')}</p></div>`:''}<p>${katexFragment(String(q.stem||''))} <small>· Câu gốc ${q.originalNumber}</small></p>${Array.isArray(q.options)&&q.options.length?`<ol type="A">${q.options.map(o=>`<li>${katexFragment(String(o))}</li>`).join('')}</ol>`:''}</li>`;}).join('')}</ol></section>`;
  view.scrollIntoView({block:'nearest'});
 }catch(error){
  if(pending.isConnected){
   pending.textContent=error.message;
   pending.scrollIntoView({block:'nearest'});
  }
 }
}
async function exportExtended(node){
 if(!flushEditor())throw Error('Gõ xong chữ đang nhập rồi thử lại.');
 const kind=node.dataset.kind,format=node.dataset.format;
 const orientation=$('#export-matrix-landscape')?.checked?'landscape':'portrait';
 const response=await fetch('/api/exports/'+encodeURIComponent(kind),{
  method:'POST',
  headers:{...db.workspaceHeaders(),'Content-Type':'application/json'},
  body:JSON.stringify(kind==='answer-key-rubric'?{exam:clone(current()),audience:'teacher',teacher:true,format}:{exam:clone(current()),format,orientation}),
 });
 if(!response.ok){
  let message='Chưa xuất được bản tổng hợp.';
  try{const err=await response.json();message=err.detail?.message||err.error||message;}catch{}
  throw Error(message);
 }
 const blob=await response.blob();
 const url=URL.createObjectURL(blob);
 const link=document.createElement('a');
 link.href=url;
 link.download=`${kind==='answer-key-rubric'?'Dap_an_barem':'Ma_tran_dac_ta'}.${format}`;
 document.body.append(link);link.click();link.remove();
 setTimeout(()=>URL.revokeObjectURL(url),10000);
}
function resolveExportDraftSettings(exam){
 const hasDomVariants=Boolean($('#export-variants'));
 const codeEl=$('#export-variant-code');
 if(hasDomVariants||codeEl){
  const settings=exportVariantSettings();
  const code=codeEl?.value;
  exportVariantSelection={examId:exam.id,...settings,code};
  return {settings,code};
 }
 if(exportVariantSelection?.examId===exam.id){
  return {
   settings:{
    questionIds:Array.isArray(exportVariantSelection.questionIds)?[...exportVariantSelection.questionIds]:[],
    shuffleOptions:Boolean(exportVariantSelection.shuffleOptions),
   },
   code:exportVariantSelection.code,
  };
 }
 return {settings:exportVariantSettings(),code:undefined};
}
function showDraftExportConfirmationModal({format,isBatch,teacher,classLabel,unapprovedCount,preflightFailed,blockingIssues=[],extraMessage=''}){
 const title=isBatch?'Xác nhận xuất Bộ mã đề':teacher?'Xác nhận xuất Bản giáo viên':'Xác nhận xuất Bản học sinh';
 const heading=isBatch?'Cần lưu ý trước khi xuất Bộ mã đề':teacher?'Cần lưu ý trước khi xuất Bản giáo viên':'Cần lưu ý trước khi phát đề cho học sinh';
 const issues=Array.isArray(blockingIssues)?blockingIssues.map(item=>typeof item==='string'?item:(item?.message||'')).filter(Boolean):[];
 const issuesHTML=issues.length?`<ul class="preflight-list">${issues.slice(0,10).map(msg=>`<li>${esc(msg)}</li>`).join('')}</ul>`:'';
 c.modal(title,`<div class="alert" role="alert"><b>${heading}</b><p>${unapprovedCount?`Còn ${unapprovedCount} câu chưa được giáo viên duyệt. `:''}${preflightFailed?'Kiểm tra bản in vẫn còn lỗi chặn cần rà soát. ':''}${classLabel?`Đợt/lớp: <b>${esc(classLabel)}</b>.`:''}</p>${extraMessage?`<p>${esc(extraMessage)}</p>`:''}${issuesHTML}</div>${foot(btn('review-first-unapproved','Quay lại duyệt câu')+btn('export-file','Vẫn tải bản nháp','primary',`data-teacher="${teacher}" data-batch="${isBatch}" data-format="${esc(format)}" data-confirmed="true" data-class-label="${esc(classLabel)}"`)+btn('export','Quay lại phần xuất'))}`);
}
async function exportFile(node,batch=false){
 if(!flushEditor())throw Error('Gõ xong chữ đang nhập rồi thử lại.');
 const exam=clone(current()),format=node.dataset.format;
 const isBatch=Boolean(batch||node.dataset.batch==='true');
 const confirmed=node.dataset.confirmed==='true';
 const teacher=node.dataset.teacher==='true';
 const classLabel=($('#export-class-label')?.value??node.dataset.classLabel??'').trim();
 if(classLabel)lastExportClassLabel=classLabel;
 const {settings,code}=resolveExportDraftSettings(exam);
 const {questionIds}=settings;
 const cachedPreflight=latestExportPreflight&&latestExportPreflight.examId===exam.id&&latestExportPreflight.revision===exam.revision?latestExportPreflight.report:null;
 const preflightPanel=$('#export-preflight-panel');
 const preflightFailed=cachedPreflight?cachedPreflight.ready===false:(preflightPanel?.dataset.preflightLoaded==='true'&&preflightPanel?.dataset.preflightReady==='false');
 const blockingIssues=Array.isArray(cachedPreflight?.blockingIssues)?cachedPreflight.blockingIssues:[];
 const unapprovedCount=exam.questions.filter(q=>!isApproved(q)).length;
 if(shouldRequireDraftConfirmation({batch:isBatch,teacher,confirmed,classLabel,workflowStatus:normalizeWorkflowStatus(exam.workflowStatus),unapprovedCount,preflightFailed})){
  showDraftExportConfirmationModal({format,isBatch,teacher,classLabel,unapprovedCount,preflightFailed,blockingIssues});
  return;
 }
 const variant=code?{...settings,offset:Number(code)}:null;
 c.modal('Đang xuất tệp',`<div class="busy"><span class="spinner"></span><span role="status">Đang tạo ${format.toUpperCase()} từ đề hiện tại…</span></div>`);
 const pendingExport=document.querySelector('#dialog .busy');
 try{
  const allowDraft=confirmed?{allowDraft:true}:{};
  const result=await api('/api/save-export',isBatch
   ?{type:'variant-pack',exam,format,...settings,...(classLabel?{classLabel}:{}),...allowDraft}
   :{type:'exam',exam,format,teacher,...(variant?{variant}:{}),...(classLabel?{classLabel}:{}),...allowDraft});
  if(!pendingExport.isConnected||!$('#dialog').open){c.toast('Đã tạo tệp '+result.filename);return;}
  if(isBatch){
   c.modal('Bộ mã đề đã sẵn sàng',`<p>${Math.min(6,questionIds.length)} mã đề · ${format.toUpperCase()} · ${result.bytes.toLocaleString('vi-VN')} byte</p><a class="saved-export-link" href="${esc(result.url)}" download>Tải bộ mã đề (.zip)</a>${foot(btn('export','Quay lại phần xuất'))}`);
   return;
  }
  const extraNote=exportConfirmationNote(format);
  c.modal('Tệp đã lưu tại máy',`<div class="alert success">${esc(result.filename)}<br>${result.bytes.toLocaleString('vi-VN')} byte · Tệp ${format.toUpperCase()} thật</div><a class="saved-export-link" href="${esc(result.url)}" target="_blank" rel="noopener" ${format==='docx'?'download':''}>Mở / tải tệp vừa xuất</a>${note('Bản xuất: '+esc(exam.title)+(variant?' · Mã đề '+(101+variant.offset):'')+' · bản '+exam.revision)}${extraNote?note(extraNote):''}${foot(btn('export','Xuất bản khác'))}`);
 }catch(error){
  if(error?.status===409&&(error?.data?.requiresDraftConfirmation===true||Array.isArray(error?.data?.blockingIssues)||Array.isArray(error?.data?.preflight?.blockingIssues))){
   const serverReport=error.data.preflight||null;
   if(serverReport)latestExportPreflight={examId:exam.id,revision:exam.revision,report:serverReport};
   const serverIssues=Array.isArray(error.data.blockingIssues)?error.data.blockingIssues:(Array.isArray(serverReport?.blockingIssues)?serverReport.blockingIssues:blockingIssues);
   if($('#dialog').open){
    showDraftExportConfirmationModal({format,isBatch,teacher,classLabel,unapprovedCount,preflightFailed:true,blockingIssues:serverIssues,extraMessage:error.message});
    return;
   }
  }
  if(!pendingExport.isConnected||!$('#dialog').open){c.toast(error.message);return;}
  c.modal('Chưa xuất được tệp',`<p class="alert" role="alert">${esc(error.message)}</p>${note('Nội dung đề được giữ nguyên. Sửa nội dung được báo lỗi hoặc chọn định dạng khác rồi thử lại.')}${foot(btn('export','Quay lại phần xuất','primary'))}`);
 }
}
function showSearch(){c.modal('Tìm các bản trên web',`<form id="web-form">${field('Đoạn trích hoặc cụm từ cần tìm',`<textarea name="query" rows="4" required maxlength="2000">${esc(current().quote.text.slice(0,600))}</textarea>`)}${note('Tìm kiếm trực tiếp qua dịch vụ đã chọn. Kết quả tìm kiếm chỉ là gợi ý nguồn; cần mở bản nguồn và chọn đoạn trước khi đưa vào đề.')}<p class="hint">Dịch vụ hiện tại: ${esc(config?.search?.provider||'chưa bật')}</p>${consent('web-consent')}${foot(btn('connections','Cấu hình tìm kiếm','','type="button"')+'<button type="submit" class="primary">Tìm nguồn</button>')}</form>`);}
async function searchSubmit(f){const query=new FormData(f).get('query'),consentValue=$('#web-consent').checked;c.modal('Đang tìm nguồn','<div class="busy"><span class="spinner"></span>Đang truy vấn dịch vụ tìm kiếm…</div>');const result=await api('/api/search',{query,consent:consentValue});prepared={type:'search',result};c.modal('Nguồn tìm được trên web',`${note('Kết quả trực tiếp từ '+esc(result.provider)+' · '+new Date(result.at).toLocaleString('vi-VN')+'. Chưa xác minh nội dung hoặc chọn bản dùng.')}<div class="search-results">${result.results.length?result.results.map((r,i)=>`<article class="small-card"><b><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></b><small>${esc(new URL(r.url).hostname)}</small><p>${esc(r.snippet)}</p>${btn('read-web-result','Đọc nội dung & chọn đoạn','',`data-index="${i}"`)}</article>`).join(''):note('Không tìm thấy bản phù hợp trong lượt tìm này. Có thể đổi cụm từ hoặc nhập nguồn đã có.')}</div>${foot(btn('web-search','Tìm lại')+btn('add-variant','Nhập bản khác'))}`);}
async function readResult(index){const item=prepared.result.results[index];c.modal('Đang mở bản nguồn','<div class="busy"><span class="spinner"></span>Đang lấy văn bản có thể truy cập…</div>');const result=await api('/api/read-web',{url:item.url,consent:true});prepared={type:'web-source',result};c.modal('Chọn đoạn từ bản nguồn',`<form id="web-source-form"><h3>${esc(result.title)}</h3><a href="${esc(result.url)}" target="_blank" rel="noopener">Mở trang gốc</a>${note('Nội dung truy cập trực tiếp; có thể chứa phần điều hướng hoặc thiếu nội dung tải bằng JavaScript. Chỉ giữ đoạn thầy cô muốn đối chiếu, không coi trang web là bản chuẩn.')}<label>Văn bản lấy được — sửa ô này để giữ đúng đoạn cần đối chiếu</label><textarea name="text" rows="14" required maxlength="6000">${esc(result.text.slice(0,6000))}</textarea>${foot('<button type="submit" class="primary">Thêm bản để đối chiếu</button>')}</form>`);}

async function autoCheckQuestions(ids,examId,consentValue){if(!config?.[config?.routes?.check]?.model){c.toast('Đã rà soát tại máy. Chưa chọn mô hình để tự giải lại bằng AI.');return;}let done=0,failed=0;for(const id of ids){const e=c.getState().exams.find(e=>e.id===examId),q=e?.questions.find(q=>q.id===id);if(!q)continue;const version=q.v;try{const result=await api('/api/ai/check',{question:{type:q.type,stem:q.stem,options:q.options},sources:sourcesFor(e,q.source?.docId).map(s=>({...s,text:s.text.slice(0,14000)})),consent:consentValue});if(q.v!==version)continue;const problems=[...(result.issues||[])];if(q.type==='essay')problems.push('Lời giải tự luận cần giáo viên đối chiếu; chưa so sánh tương đương với lời giải đang lưu.');if(q.type!=='essay'&&result.answer!==q.answer)problems.push('Bất đồng: đáp án lưu '+String.fromCharCode(65+q.answer)+', lời giải lại cho '+String.fromCharCode(65+result.answer)+'.');if(result.uncertain)problems.push('Mô hình chưa đủ chắc chắn.');if(!result.sourceVerified)problems.push('Chưa có đoạn trích nguồn khớp chữ.');commit(e,'Tự giải lại câu '+(e.questions.indexOf(q)+1),()=>{q.check={version,status:problems.length?'review':'consistent',problems,evidence:result.explanation,at:Date.now(),method:'AI tự giải lại không nhận đáp án cũ · '+result.provider+' · '+result.model,solver:result};});await c.persist();if(current().id===examId)c.refreshInline();done++;}catch(error){failed++;e.chat.push({role:'assistant',text:'Chưa giải lại được câu '+(e.questions.indexOf(q)+1)+': '+error.message});await c.persist();}}c.toast('Đã giải lại '+done+' câu bằng AI'+(failed?'; '+failed+' câu chưa xử lý được.':'.'));}

export async function handleMVPAction(action,node){flushEditor();if(await handleReferenceAction(action,node))return true;if(action!=='menu')closeFloating();switch(action){
 case 'menu':menu(node.dataset.menu);return true;
 case 'workflow-sources':await c.act('assistant-sources');return true;
 case 'workflow-matrix':await c.act('matrix');return true;
 case 'workflow-export':await c.act('export');return true;
 case 'workflow-toggle-view':await c.act(c.isTeacher()?'view-student':'view-teacher');return true;
 case 'workflow-edit':{
  const e=current();
  if(!e.questions.length){await c.act('add-question');return true;}
  const id=c.getSelected()||e.questions[0].id;
  c.setSelected(id);
  const el=document.getElementById('q-'+id);
  el?.scrollIntoView({block:'center',behavior:'smooth'});
  el?.querySelector('.stem-editor .tiptap, textarea.stem')?.focus();
  return true;
 }
 case 'toggle-chat':case 'toggle-ai':{const workspace=$('.workspace'),focus=workspace.classList.contains('focus-mode');workspace.classList.remove('focus-mode');if(innerWidth<=760){const isOpen=$('aside.assistant').classList.toggle('open');workspace.classList.toggle('mobile-ai-view',isOpen);hideChat=false;workspace.classList.remove('chat-hidden');document.querySelector('[data-ux-action="mobile-show-editor"]')?.classList.toggle('active',!isOpen);document.querySelector('.ux-view-tabs [data-action="toggle-ai"]')?.classList.toggle('active',isOpen);}else{hideChat=focus?false:!workspace.classList.contains('chat-hidden');workspace.classList.toggle('chat-hidden',hideChat);}return true;}
 case 'format':format(node.dataset.command);return true;
 case 'align-left':case 'align-center':case 'align-justify':format(action.slice(6));return true;
 case 'bullet-list':format('bulletList');return true;
 case 'number-list':format('orderedList');return true;
 case 'connections':await refreshStatus();showConfig();return true;
 case 'refresh-providers-health':await loadProvidersHealth();c.toast('Đã làm mới trạng thái các kênh AI.');return true;
 case 'test-single-provider':{
  const provider=node.dataset.provider||'';
  const statusEl=$('#provider-test-status-'+provider);
  if(statusEl)statusEl.textContent='Đang thử kết nối…';
  if($('#connections-form'))await saveConfig().catch(()=>{});
  try{
   const result=await api('/api/providers/'+encodeURIComponent(provider)+'/test',{});
   const formatted=formatProviderTestResultHTML(provider,result);
   if(statusEl){
    statusEl.textContent=formatted.text;
    statusEl.dataset.ok=formatted.ok?'1':'0';
   }
   if(provider==='ollama'&&formatted.models.length)updateOllamaModelsUI(formatted.models);
   void loadProvidersHealth();
  }catch(error){
   if(statusEl)statusEl.textContent='⚠ '+(error.message||'Chưa kết nối được.');
  }
  return true;
 }
 case 'pick-ollama-model':{
  const form=$('#connections-form');
  const model=node.dataset.model||'';
  const modelInput=form?.elements?.namedItem?.('ollama-model');
  if(modelInput&&model){
   modelInput.value=model;
   c.toast('Đã chọn mô hình '+model);
  }
  return true;
 }
 case 'test-provider':{await saveConfig();const provider=node.dataset.provider;$('#'+provider+'-result').textContent='Đang kiểm tra…';const result=await api('/api/test-provider',{provider});$('#'+provider+'-result').textContent=result.connected?(provider==='greennode'?'AI GreenNode đã sẵn sàng: '+result.models.join(', '):'Đã kết nối danh sách mô hình. Chọn ID trong ô tên mô hình rồi lưu. '+result.models.length+' mô hình được trả về.'):'Chưa kết nối: '+result.error;const list=$('#'+provider+'-models');if(list)list.innerHTML=(result.models||[]).map(id=>'<option value=\"'+esc(id)+'\"></option>').join('');return true;}
 case 'generate':if(status?.localPoC)await c.act('matrix');else showGenerate();return true;
 case 'matrix-from-source':{const d=current().docs.find(d=>d.id===node.dataset.doc);prepared={type:'matrix-source',docId:d.id,page:activeSourcePage};c.modal('Đọc ma trận từ tài liệu',`<form id="matrix-source-form">${field('Văn bản chứa ma trận',`<textarea name="text" rows="12" required>${esc(pagesOf(d).find(p=>p.number===activeSourcePage)?.text||d.text||'')}</textarea>`)}${note('Cơ cấu AI đề xuất cần được xem và xác nhận; không tự coi mọi ô là đúng.')}${consent('matrix-source-consent')}${foot('<button type="submit" class="primary">Đọc & xem cơ cấu</button>')}</form>`);return true;}
 case 'apply-read-matrix':{const p=prepared;if(p.type!=='read-matrix'||current().id!==p.examId||current().revision!==p.revision)throw Error('Đề đã đổi. Đọc lại ma trận.');c.change('Nhập cơ cấu đọc từ tài liệu — chưa xác nhận',e=>{e.matrix=p.result.matrix;e.matrixConfirmed=false;});c.showMatrix();return true;}
 case 'apply-generated':{const p=prepared;if(p?.type!=='generated'||p.examId!==current().id||p.revision!==current().revision)throw Error('Đề đã thay đổi; cần tạo hoặc xem lại đề xuất.');let generatedIds=[];c.change('Đưa câu AI vào đề',e=>{const qs=p.questions.map(q=>({...q,id:uid(),v:1,check:null,generated:{provider:p.provider,model:p.model,at:Date.now()}}));if(p.mode==='replace')e.questions=qs;else e.questions.push(...qs);generatedIds=qs.map(q=>q.id);qs.forEach(q=>check(e,q));});$('#dialog').close();if(p.autoCheck)void autoCheckQuestions(generatedIds,current().id,p.consent).catch(error=>c.toast(error.message));return true;}
 case 'request-patch':await requestPatch();return true;
 case 'apply-ai-patch':{const p=prepared,q=c.qget(p?.scope?.id);if(p?.type!=='ai-patch'||p.examId!==current().id||q?.v!==p.scope.version)throw Error('Đề xuất đã cũ. Chọn lại câu để sửa.');c.change('Sửa vùng chọn và phần phụ thuộc qua AI',()=>{q.stem=p.stem;q.runs=null;q.options=p.result.options;q.answer=p.result.answer;q.explanation=p.result.explanation;if(q.type==='essay')q.rubric=[];if(q.rule&&!q.rule.startsWith('math-')){q.dataLinked=true;q.rule=null;}touch(q);check(current(),q);});$('#dialog').close();void autoCheckQuestions([q.id],current().id,p.consent).catch(error=>c.toast(error.message));return true;}
 case 'ai-check':if(status?.localPoC)await openQuestionCheck(c,db.workspaceHeaders());else showAICheck();return true;
 case 'request-ai-check':await requestCheck();return true;
 case 'apply-ai-answer':{const p=prepared,q=c.qget(p?.id);if(p?.type!=='ai-check-result'||current().id!==p.examId||q?.v!==p.version)throw Error('Lời giải thuộc phiên bản cũ.');c.change('Dùng lời giải AI sau khi đối chiếu',()=>{q.answer=p.result.answer;q.explanation=p.result.explanation;if(q.type==='essay')q.rubric=[];touch(q);check(current(),q);});$('#dialog').close();return true;}
 case 'formula':case 'formula-edit':showFormula(node.dataset.id,node.dataset.formula);return true;
 case 'formula-preset':$('#formula-input').value=node.dataset.latex;previewFormula();return true;
 case 'formula-delete':{const q=c.qget(prepared.id);c.change('Xóa công thức',()=>{q.formulas=q.formulas.filter(f=>f.id!==prepared.formulaId);touch(q);check(current(),q);});$('#dialog').close();return true;}
 case 'page-break':{const q=c.qget(c.getSelected());if(!q)throw Error('Chọn câu cần ngắt trang.');c.change('Đổi ngắt trang trước câu',()=>q.pageBreak=!q.pageBreak);return true;}
 case 'layout':{const l=current().layout||{};const curLH=Number(l.lineHeight)||1.5;c.modal('Định dạng trang',`<form id="layout-form">${field('Phông chữ',`<select name="font"><option ${l.font!=='Arial'?'selected':''}>Times New Roman</option><option ${l.font==='Arial'?'selected':''}>Arial</option></select>`)}${field('Cỡ chữ (pt)',`<input name="fontSize" type="number" min="10" max="22" value="${l.fontSize||15}">`)}${field('Giãn dòng',`<select name="lineHeight">${[1.15,1.35,1.5,1.75,2].map(v=>`<option value="${v}" ${Math.abs(curLH-v)<0.05?'selected':''}>${v}</option>`).join('')}</select>`)}${field('Đầu trang (Header)',`<input name="headerText" maxlength="140" placeholder="Ví dụ: Đề kiểm tra giữa kỳ" value="${esc(l.headerText||'')}">`)}${field('Chân trang (Footer)',`<input name="footerText" maxlength="140" placeholder="Ví dụ: Tổ Toán - Tin" value="${esc(l.footerText||'')}">`)}${field('Hình mờ (Watermark chữ)',`<input name="watermarkText" maxlength="60" placeholder="Ví dụ: BẢN NHÁP" value="${esc(l.watermarkText||'')}">`)}${field('Hình mờ ảnh (Watermark PNG/JPG)',`<input name="watermarkImageFile" type="file" accept=".png,.jpg,.jpeg,.webp">${l.watermarkImage?`<label class="consent"><input type="checkbox" name="clearWatermarkImage"> Xóa hình mờ ảnh hiện tại</label>`:''}`)}<label class="consent"><input name="mcqColumns" type="checkbox" ${Number(l.mcqColumns)===2?'checked':''}> Chia 2 cột câu trắc nghiệm (tiết kiệm giấy A4)</label><label class="consent"><input name="showPageNumbers" type="checkbox" ${l.showPageNumbers?'checked':''}> Hiện số trang (Trang X / Y) khi xuất Word</label>${note('Bản in khổ A4, lề 18 mm. Cỡ chữ mặc định 15pt. Áp dụng cho trang soạn và bản xuất.')}${foot('<button class="primary" type="submit">Áp dụng</button>')}</form>`);return true;}
 case 'insert-image':case 'quick-image':{const q=c.qget(node.dataset.id||c.getSelected());if(!q)throw Error('Chọn câu cần chèn hình.');if(node.dataset.id&&c.getSelected()!==q.id)c.setSelected(q.id);c.chooseFile('.png,.jpg,.jpeg,.webp',async file=>{if(file.size>3e6)throw Error('Hình tối đa 3 MB.');const data=await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsDataURL(file);});c.change('Chèn hình vào câu',()=>{q.images??=[];q.images.push({id:uid(),data,caption:file.name});touch(q);check(current(),q);});});return true;}
 case 'edit-table':case 'insert-table':case 'quick-table':{const q=c.qget(node.dataset.id||c.getSelected());if(!q)throw Error('Chọn câu để chèn bảng.');if(node.dataset.id&&c.getSelected()!==q.id)c.setSelected(q.id);const table=q.tables?.find(t=>t.id===node.dataset.table);const cellTokens=new Map();const initialRows=table?table.rows:[['Đại lượng','Giá trị'],['a','3'],['b','4']];prepared={type:'table',id:q.id,tableId:table?.id,cellTokens};c.modal(table?'Sửa bảng của câu':'Chèn bảng vào câu',`<form id="table-form" data-table-mode="grid">${buildVisualTableEditorHTML(initialRows,cellTokens)}${note('Sửa trực tiếp từng ô trong bảng. Giữ nguyên thẻ <code>[Ảnh …]</code> để bảo toàn ảnh trong ô bảng.')}${foot((table?btn('delete-table','Xóa bảng','danger','type="button"'):'')+'<button type="submit" class="primary">Lưu bảng</button>')}</form>`);return true;}
 case 'table-row-add':case 'table-row-del':case 'table-col-add':case 'table-col-del':{
  const form=$('#table-form'),tbody=form?.querySelector('#visual-table-grid tbody');
  if(!tbody)return true;
  const rows=[...tbody.querySelectorAll('tr')];
  const cols=rows[0]?.querySelectorAll('input[data-tcell]').length||2;
  if(action==='table-row-add'){
   if(rows.length>=20){c.toast('Bảng tối đa 20 hàng.');return true;}
   const ri=rows.length;
   const tr=document.createElement('tr');
   tr.innerHTML=Array.from({length:cols},(_,ci)=>`<td><input type="text" data-tcell="${ri}:${ci}" value="" aria-label="Hàng ${ri+1} cột ${ci+1}"></td>`).join('');
   tbody.append(tr);
  }else if(action==='table-row-del'){
   if(rows.length>1)rows.at(-1)?.remove();
  }else if(action==='table-col-add'){
   if(cols>=8){c.toast('Bảng tối đa 8 cột.');return true;}
   rows.forEach((tr,ri)=>{const td=document.createElement('td');td.innerHTML=`<input type="text" data-tcell="${ri}:${cols}" value="" aria-label="Hàng ${ri+1} cột ${cols+1}">`;tr.append(td);});
  }else if(action==='table-col-del'){
   if(cols>1)rows.forEach(tr=>tr.lastElementChild?.remove());
  }
  syncVisualTableTextArea(form);
  return true;
 }
 case 'edit-image':{const q=c.qget(node.dataset.id),im=q.images.find(im=>im.id===node.dataset.image);prepared={type:'image',id:q.id,imageId:im.id};c.modal('Hình của câu hỏi',`<form id="image-form"><img class="source-frame" src="${esc(im.data)}" alt="Hình câu hỏi">${field('Chú thích',`<input name="caption" value="${esc(im.caption||'')}">`)}${foot(btn('delete-image','Xóa hình','danger','type="button"')+'<button class="primary" type="submit">Lưu chú thích</button>')}</form>`);return true;}
 case 'delete-image':{const q=c.qget(prepared.id);c.change('Xóa hình của câu',()=>{q.images=q.images.filter(im=>im.id!==prepared.imageId);touch(q);check(current(),q);});$('#dialog').close();return true;}
 case 'delete-table':{const q=c.qget(prepared.id);c.change('Xóa bảng của câu',()=>{q.tables=q.tables.filter(t=>t.id!==prepared.tableId);touch(q);check(current(),q);});$('#dialog').close();return true;}
 case 'remove-doc':{const docId=node.dataset.doc;prepared={type:'remove-doc',docId};c.modal('Gỡ tài liệu khỏi đề?',`<p class="hint">Các câu gắn với tài liệu này sẽ cần rà soát nguồn. Có thể hoàn tác việc gỡ.</p>${foot(btn('confirm-remove-doc','Gỡ tài liệu','danger'))}`);return true;}
 case 'confirm-remove-doc':{const id=prepared.docId;c.change('Gỡ tài liệu khỏi đề',e=>{e.docs=e.docs.filter(d=>d.id!==id);e.questions.filter(q=>q.source?.docId===id).forEach(q=>{touch(q);check(e,q);});});$('#dialog').close();return true;}
 case 'import-doc':showImport();return true;
 case 'source':{const q=c.qget(node.dataset.id||c.getSelected());await showSource(node.dataset.doc||q?.source?.docId,Number(node.dataset.page)||q?.source?.page||1);return true;}
 case 'open-source':await showSource(node.dataset.doc,1);return true;
 case 'generate-from-source':{
  const doc=current().docs.find(item=>item.id===node.dataset.doc);
  if(!doc||!pagesOf(doc).some(p=>p.text?.trim()))throw Error('Tài liệu chưa có văn bản để soạn đề.');
  const selected=current().assistantSources||[];
  if(selected.length!==1||selected[0]!==doc.id){
   c.change('Chọn tài liệu nguồn để soạn đề',e=>{e.assistantSources=[doc.id];delete e.assistantSourcePages;},{renderPage:false});
  }
  await c.act('generate');
  return true;
 }
 case 'source-extract':await runOCR(node.dataset.doc);return true;
 case 'cancel-ocr':ocrAbortController?.abort(Error('Đã hủy nhận dạng OCR.'));$('#dialog').close();return true;
 case 'review-first-unapproved':{const q=current().questions.find(item=>!isApproved(item))||current().questions[0];$('#dialog').close();if(q){c.setSelected(q.id);document.getElementById('q-'+q.id)?.scrollIntoView({block:'center',behavior:'smooth'});c.act('review',Object.assign(document.createElement('button'),{dataset:{id:q.id}}));}return true;}
 case 'extract':showExtract();return true;
 case 'parse-old':await parseOld(node.dataset.doc);return true;
 case 'parse-first-doc':{const e=current(),preferred=(e.assistantSources||[]).map(id=>e.docs.find(d=>d.id===id)).find(d=>d&&pagesOf(d).some(p=>p.text?.trim()))||e.docs.find(d=>pagesOf(d).some(p=>p.text?.trim()));if(!preferred)throw Error('Chưa có tài liệu có chữ để tách câu.');activeSourceDoc=preferred.id;activeSourcePage=pagesOf(preferred).find(p=>p.text?.trim())?.number||1;await parseOld(preferred.id);return true;}
 case 'parse-old-all':await parseOld(node.dataset.doc,true);return true;
 case 'apply-old-questions':{const p=prepared;if(p?.type!=='old-questions'||p.examId!==current().id||p.revision!==current().revision)throw Error('Đề đã thay đổi. Tách lại để xem bản mới.');if(node.dataset.mode==='new'){const old=current(),e=blank(old.subject,c.getState().prefs);Object.assign(e,{title:old.docs.find(d=>d.id===p.docId)?.name.replace(/\.[^.]+$/,'')||'Đề nhập từ tài liệu',grade:old.grade,school:old.school,minutes:old.minutes,docs:clone(old.docs.filter(d=>d.id===p.docId)),fullExam:true,chat:[],layout:{font:'Times New Roman',fontSize:15}});c.getState().exams.push(e);c.getState().current=e.id;c.setTab('outline');}c.change('Thêm câu tách từ đề cũ',e=>{for(const item of p.questions){const qPage=item.sourcePage||p.page;const q={...item,id:uid(),v:1,topic:e.matrix[0]?.topic||'Đề cũ',level:0,answerKnown:false,explanation:'Chưa nhập hoặc suy luận đáp án. Giáo viên cần rà soát.',source:{docId:p.docId,page:qPage,location:'Trang '+qPage},check:null};e.questions.push(q);check(e,q);}});$('#dialog').close();return true;}
 case 'export':showExport();return true;
 case 'export-file':await exportFile(node);return true;
 case 'export-extended':await exportExtended(node);return true;
 case 'export-tnmaker':{if(!flushEditor())throw Error('Gõ xong chữ đang nhập rồi thử lại.');const exam=clone(current()),settings=exportVariantSettings(),res=await api('/api/exports/tnmaker-pack',{exam,...(settings.questionIds.length>=2?settings:{})});c.modal('Gói khóa đáp án & QR chuẩn chung sẵn sàng',`<div class="alert success">${esc(res.filename)} · ${res.bytes.toLocaleString('vi-VN')} byte</div><p class="hint">Gói gồm bảng <b>DapAn.xlsx</b> (1 sheet <code>DapAn</code>, cột <code>MaDe / Cau / DapAn</code>) và ảnh QR <b>QR_DapAn.png</b> cho mã ${(res.codes||['101']).join(', ')}. Đây là gói xuất chuẩn chung; tương thích nhập trực tiếp với phần mềm TNMaker bên thứ ba chưa được xác minh độc lập.</p><a class="saved-export-link" href="${esc(res.url)}" download>Tải gói khóa đáp án &amp; QR (.zip)</a>${foot(btn('export','Quay lại xuất đề'))}`);return true;}
 case 'export-pack':await exportFile(node,true);return true;
 case 'preview-variant':await previewVariant(node);return true;
 case 'web-search':showSearch();return true;
 case 'read-web-result':await readResult(Number(node.dataset.index));return true;
 default:return false;
}}
export async function handleMVPSubmit(f){if(handleReferenceSubmit(f)||handleRubricSubmit(f))return true;switch(f.id){
 case 'image-form':{
  const q=c.qget(prepared.id),im=q?.images?.find(im=>im.id===prepared.imageId);
  if(!im)throw Error('Hình đã đổi. Mở lại hình để sửa chú thích.');
  const caption=new FormData(f).get('caption');
  if(caption!==(im.caption||''))c.change('Sửa chú thích hình',()=>{
   im.caption=caption;
   touch(q);
   check(current(),q);
  });
  $('#dialog').close();
  return true;
 }
 case 'connections-form':await saveConfig();void loadProvidersHealth();c.toast(config.localPoC?'Đã lưu kết nối. Thầy cô có thể bấm Thử kênh để kiểm tra kết nối thật.':'Đã lưu đường xử lý. Bấm kiểm tra để xác nhận dịch vụ đang chạy.');return true;
 case 'generate-form':await generateSubmit(f);return true;
 case 'source-ocr-form':{
  const origin=prepared;if(origin?.type!=='source-ocr'||current().id!==origin.examId)throw Error('Đề đã đổi; mở lại tài liệu cần đọc.');
  if(!$('#source-ocr-consent').checked)throw Error('Cần cho phép gửi tệp này tới Gemini.');
  ocrAbortController?.abort();ocrAbortController=new AbortController();const signal=ocrAbortController.signal;
  c.modal('Đang nhận dạng nguồn',`<p role="status">Đang đọc tài liệu bằng Gemini… Đề đang lưu được giữ nguyên.</p>${foot(btn('cancel-ocr','Hủy nhận dạng','danger'))}`);
  const waiting=$('#dialog [role=status]');
  try{
   const result=await api('/api/extract',{...(origin.data?{data:origin.data}:{fileId:origin.fileId}),name:origin.name,consent:true,forceAI:!!origin.docId},signal);
   if(!waiting.isConnected||!$('#dialog').open)return true;
   if(current().id!==origin.examId)throw Error('Đã chuyển đề. Chưa áp dụng kết quả đọc.');
   if(origin.docId){c.change('Đọc lại tài liệu bằng AI',e=>{const d=e.docs.find(d=>d.id===origin.docId);if(!d)throw Error('Tài liệu đã gỡ.');Object.assign(d,{pages:result.pages,text:result.pages.map(p=>p.text).join('\n\n'),method:result.method,notes:result.notes||'',needsReview:true,version:(d.version||1)+1});e.questions.filter(q=>q.source?.docId===d.id).forEach(q=>{touch(q);check(e,q);});});await showSource(origin.docId,origin.page);}
   else await finishSourceImport(origin,result);
  }catch(error){
   if(error?.name==='AbortError'){c.toast('Đã hủy nhận dạng OCR.');return true;}
   if(waiting.isConnected&&$('#dialog').open){showSourceConsent(origin);sourceImportError('#source-ocr-form',error);}
  }finally{ocrAbortController=null;}
  return true;
 }

 case 'matrix-source-form':{const text=new FormData(f).get('text'),consentValue=$('#matrix-source-consent').checked,origin={examId:current().id,revision:current().revision};c.modal('Đang đọc ma trận','<div class="busy"><span class="spinner"></span>Đang đọc cơ cấu từ văn bản…</div>');const result=await api('/api/ai/matrix',{text,consent:consentValue});prepared={type:'read-matrix',...origin,result};c.modal('Cơ cấu đọc được',`<table><tr><th>Chủ đề</th><th>Nhận biết</th><th>Thông hiểu</th><th>Vận dụng</th></tr>${result.matrix.map(r=>`<tr><td>${esc(r.topic)}</td>${r.targets.map(n=>`<td>${n}</td>`).join('')}</tr>`).join('')}</table><div class="alert">${esc(result.notes||'Giáo viên cần rà soát và xác nhận trước khi dùng.')}</div>${foot(btn('apply-read-matrix','Đưa vào ma trận để rà soát','primary'))}`);return true;}
 case 'chat-form':return handleChat(f);
 case 'formula-form':{const p=prepared,q=c.qget(p.id),latex=$('#formula-input').value;katex.renderToString(latex,{throwOnError:true,trust:false});c.change('Lưu công thức của câu',()=>{q.formulas??=[];const old=q.formulas.find(f=>f.id===p.formulaId);if(old)old.latex=latex;else q.formulas.push(newFormula(latex));touch(q);check(current(),q);});$('#dialog').close();return true;}
 case 'mvp-paste':{const values=Object.fromEntries(new FormData(f)),doc={id:uid(),name:values.name,text:values.text,kind:'text',sample:false,pages:[{number:1,text:values.text,method:'manual'}]};c.change('Thêm văn bản nguồn',e=>e.docs.push(doc));await showSource(doc.id);return true;}
 case 'source-text-form':{
  const e=current(),d=e.docs.find(item=>item.id===f.dataset.doc),number=Number(f.dataset.page);
  if(!d||e.id!==f.dataset.exam||(d.version||1)!==Number(f.dataset.version))throw Error('Nguồn đã đổi. Mở lại trang trước khi lưu.');
  if(d.personalLesson)throw Error('Sửa học liệu trong kho cá nhân.');
  const pages=pagesOf(d),old=pages.find(item=>item.number===number);
  if(!old&&(pages.length||number!==1))throw Error('Trang nguồn không còn. Mở lại tài liệu.');
  const text=new FormData(f).get('text');
  if(!text.trim()&&old&&(old.needsOCR||sourcePageNeedsReview(d,old)))throw Error('Nhập phần văn bản đã đối chiếu trước khi lưu.');
  if(!old||old.text!==text||old.needsOCR||sourcePageNeedsReview(d,old)){
   c.change('Lưu bản đối chiếu trang '+number,e=>{
    d.pages=pages.length?pages:[{number,text:''}];
    const p=d.pages.find(item=>item.number===number),changed=p.text!==text;
    Object.assign(p,{text,method:'manual',needsOCR:false,needsReview:false});
    delete p.uncertain;
    d.needsReview=d.pages.some(item=>sourcePageNeedsReview(d,item));
    if(changed){
     d.version=(d.version||1)+1;
     d.text=d.pages.map(item=>item.text).join('\n\n');
     e.questions.filter(q=>q.source?.docId===d.id).forEach(q=>{touch(q);check(e,q);});
    }
   });
   await c.persist();
  }
  await showSource(d.id,number);
  return true;
 }
 case 'web-form':await searchSubmit(f);return true;
 case 'web-source-form':{const text=new FormData(f).get('text'),source=prepared.result;c.change('Thêm bản truy cập từ web để đối chiếu',e=>e.quote.versions.push({id:uid(),label:source.title,text,url:source.url,location:'Trang web truy cập '+new Date(source.fetchedAt).toLocaleString('vi-VN'),external:true,fetchedAt:source.fetchedAt,webRetrieved:true}));c.showQuotes();return true;}
 case 'table-form':{const q=c.qget(prepared.id),tokens=prepared.cellTokens,rows=readVisualTableRows(f,tokens);if(!rows.length||rows.length>20||rows.some(r=>r.length>8))throw Error('Bảng tối đa 20 hàng, 8 cột.');c.change('Chèn bảng vào câu',()=>{q.tables??=[];const table=q.tables.find(t=>t.id===prepared.tableId);if(table)table.rows=rows;else q.tables.push({id:uid(),rows});touch(q);check(current(),q);});$('#dialog').close();return true;}
 case 'layout-form':{const values=Object.fromEntries(new FormData(f));const wmFile=f.elements.watermarkImageFile?.files?.[0];let nextWatermarkImg=f.elements.clearWatermarkImage?.checked?'':(current().layout?.watermarkImage||'');if(wmFile&&wmFile.size>0){if(wmFile.size>2e6)throw Error('Hình mờ ảnh tối đa 2 MB.');nextWatermarkImg=await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(String(r.result||''));r.onerror=rej;r.readAsDataURL(wmFile);});}c.change('Đổi định dạng trang',e=>e.layout={...e.layout,font:values.font,fontSize:Number(values.fontSize),lineHeight:Number(values.lineHeight)||1.5,mcqColumns:f.elements.mcqColumns?.checked?2:1,headerText:String(values.headerText||'').trim(),footerText:String(values.footerText||'').trim(),watermarkText:String(values.watermarkText||'').trim(),watermarkImage:nextWatermarkImg,showPageNumbers:Boolean(f.elements.showPageNumbers?.checked)});$('#dialog').close();return true;}
 default:return false;
}}
if(typeof document!=='undefined'){
document.addEventListener('input',event=>{if(event.target.id==='formula-input')previewFormula();const tForm=event.target.closest?.('#table-form');if(tForm){if(event.target.matches?.('[data-tcell]'))syncVisualTableTextArea(tForm);else if(event.target.name==='text')tForm.dataset.tableMode='text';}});
document.addEventListener('change',event=>{const n=event.target,form=n.closest?.('#connections-form');if(form&&n.name==='fixed-time-preset'){const secs={fast:120,standard:300,deep:1200,extended:3600}[n.value]||300;const tInput=form.elements.namedItem('fixed-timeout-seconds');if(tInput)tInput.value=String(secs);form.querySelectorAll('.time-preset-card').forEach(card=>card.classList.toggle('is-active',card.contains(n)));}refreshPocConnections(form);Promise.resolve().then(async()=>{if(n.id==='mvp-file'&&n.files[0])await importFile(n.files[0]);if(n.id==='source-page')await showSource(activeSourceDoc,Number(n.value));if(n.id==='paragraph-style'){format(n.value==='bold'?'heading':n.value==='italic'?'italic':'normal',2);}if(n.id==='text-color')format('foreColor',n.value);if(n.id==='highlight-color')format('hiliteColor',n.value);if(n.id==='zoom'){zoom=Number(n.value);$('.paper').style.zoom=zoom/100;}if(['doc-font','doc-fontsize'].includes(n.id)){const font=$('#doc-font').value,fontSize=Number($('#doc-fontsize').value);if(fontSize<10||fontSize>22)throw Error('Cỡ chữ từ 10 đến 22.');c.change('Đổi phông chữ trang đề',e=>e.layout={font,fontSize});}}).catch(error=>c?.toast(error.message));});
}
