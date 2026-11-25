import {openSharing,createSharing,openCommunity,attachCommunitySource,cloneCommunityExam} from './sharing.js';
import {selectedDocumentPages,sourcePageLabel} from './assistant-sources.js';
import {openMatrixChat,mountMatrixChat,isMatrixRequest,matrixChatRunning} from './matrix-chat.js';
import {refreshUsability} from './assets/usability.js';
import {closeFloating,contextualSuggestionsHTML,CHAT_TIME_PRESETS,formatProviderName,formatLatencyLabel,chatMetaBadgeText,captureAssistantSourceDraft} from './reference.js';
import {stripVietnameseDiacritics} from './vip-tools.js';
import {aiRequestError} from './ai-providers.js';
import {assistantText} from './studio.js';
import {esc,uid,clone,snapshot,touch,blank,duplicateExam,separateMarking} from './core.js';
import {ensureBlocks,blocksOf,applyEdits,validateEdits,refreshScope,requestScopes,contextForScopes,scopeInstructions,scopeValue,FIELD_LABELS,contentEqual} from './blocks.js';
import {intentOf} from './subject-profiles.js';
import {renderFigure,solveFigure,triangleFigure} from './geometry.js';
import {richTextHTML,validateMath,diffContentHTML} from './math-content.js';
import {flushEditor,setEditorsLocked,scopeForFormula,reconcileEditorRich} from './editor.js';
import {get as getWorkspace,setIdentity,workspaceHeaders} from './storage.js';
let c,accountInfo=null,scopes=[],busy=false,stage='',stageStartedAt=0,stageTimer=null,consentPulseTimer=null,proposal=null,initialized=false,recovery=null,mountedExam=null,watchedJob=null,jobTimer=null,streamingState=null,libraryTab='active',pendingChatAction=null;let writeController=null,patchController=null,chatController=null,activeJobId=null,cancelRequested=false,writtenCount=0;let contextMuted=false;const drafts=new Map(),autoTimers=new Map();
const $=s=>document.querySelector(s),b=(a,t,attrs='')=>`<button type="button" data-action="${a}" ${attrs}>${t}</button>`;
const api=async(path,data,headers={},signal)=>{
 const r=await fetch(path,{signal,headers:{...workspaceHeaders(),...headers,...(data===undefined?{}:{'Content-Type':'application/json'})},...(data===undefined?{}:{method:'POST',body:JSON.stringify(data)})});
 const value=await r.json();
 if(!r.ok)throw await aiRequestError(path,value.error||'Mình chưa thực hiện được tác vụ. Hãy thử lại.',()=>api('/api/status'));
 return value;
};
export function parseSseRecords(chunkBuffer){
 const records=[];
 let buffer=String(chunkBuffer||'').replace(/\r\n/g,'\n');
 let end;
 while((end=buffer.indexOf('\n\n'))>=0){
  const raw=buffer.slice(0,end);
  buffer=buffer.slice(end+2);
  const type=raw.match(/^event:\s*(.+)$/m)?.[1]?.trim()||'message';
  const dataLines=raw.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trim());
  if(!dataLines.length)continue;
  try{records.push({type,data:JSON.parse(dataLines.join('\n'))});}catch{}
 }
 return {records,rest:buffer};
}
export async function streamAssistantChat(payload,{signal,fetchImpl=fetch,onMeta,onDelta,headers={}}={}){
 const response=await fetchImpl('/api/assistant/chat/stream',{
  signal,
  method:'POST',
  headers:{...headers,...workspaceHeaders(),'Content-Type':'application/json'},
  body:JSON.stringify(payload),
 });
 const ct=String(response.headers?.get?.('content-type')||'');
 if([404,405,501].includes(response.status)){
  const fallbackRes=await fetchImpl('/api/assistant/chat',{
   signal,
   method:'POST',
   headers:{...headers,...workspaceHeaders(),'Content-Type':'application/json'},
   body:JSON.stringify(payload),
  });
  const val=await fallbackRes.json();
  if(!fallbackRes.ok)throw await aiRequestError('/api/assistant/chat',val.error||'Mình chưa trả lời được.',()=>api('/api/status'));
  return val;
 }
 if(!response.ok){
  let errVal={};
  try{errVal=await response.json();}catch{}
  if(response.status===503&&(errVal?.code==='not_migrated'||errVal?.error==='not_migrated')){
   const fallbackRes=await fetchImpl('/api/assistant/chat',{
    signal,
    method:'POST',
    headers:{...headers,...workspaceHeaders(),'Content-Type':'application/json'},
    body:JSON.stringify(payload),
   });
   const val=await fallbackRes.json();
   if(!fallbackRes.ok)throw await aiRequestError('/api/assistant/chat',val.error||'Mình chưa trả lời được.',()=>api('/api/status'));
   return val;
  }
  throw await aiRequestError('/api/assistant/chat/stream',errVal.error||'Mình chưa trả lời được.',()=>api('/api/status'));
 }
 if(!ct.includes('text/event-stream')||!response.body?.getReader){
  return await response.json();
 }
 const reader=response.body.getReader(),decoder=new TextDecoder();
 let buffer='',donePayload=null,accText='';
 while(true){
  const {value,done}=await reader.read();
  if(done)break;
  buffer+=decoder.decode(value,{stream:true});
  const parsed=parseSseRecords(buffer);
  buffer=parsed.rest;
  for(const rec of parsed.records){
   if(rec.type==='meta'){onMeta?.(rec.data);}
   else if(rec.type==='delta'){const chunk=String(rec.data?.text||'');accText+=chunk;onDelta?.(chunk,accText,rec.data);}
   else if(rec.type==='error'){throw Error(rec.data?.error||rec.data?.message||'Chưa nhận được phản hồi.');}
   else if(rec.type==='done'){donePayload=rec.data;}
  }
 }
 if(buffer.trim()){
  const parsed=parseSseRecords(buffer+'\n\n');
  for(const rec of parsed.records){
   if(rec.type==='meta')onMeta?.(rec.data);
   else if(rec.type==='delta'){const chunk=String(rec.data?.text||'');accText+=chunk;onDelta?.(chunk,accText,rec.data);}
   else if(rec.type==='error')throw Error(rec.data?.error||rec.data?.message||'Chưa nhận được phản hồi.');
   else if(rec.type==='done')donePayload=rec.data;
  }
 }
 return donePayload?{...donePayload,message:donePayload.message||accText}:{message:accText};
}
export async function bootstrapWorkbench(){accountInfo=await api('/api/account');setIdentity(accountInfo.workspace||accountInfo.user?.id);document.body.classList.toggle('online-member',!!accountInfo.online&&!accountInfo.admin);}
async function refreshAccount(){try{accountInfo=await api('/api/account');paintAccount();}catch{}}
function paintAccount(){const actions=$('.header-actions');if(!actions)return;const name=accountInfo?.user?.name||(accountInfo?.localPoC?'Máy này':'Tài khoản');const balance=accountInfo?.credits?.balance??'…';const creditsHTML=accountInfo?.localPoC?'':b('credits','⌄','class="credits-button" title="Hạn mức sử dụng trợ lý cục bộ"');const markup=`<div class="account-control">${b('account',`<span class="studio-avatar">${esc(name[0].toUpperCase())}</span><span class="studio-account-text">${esc(name)}<small>${accountInfo?.teamMode?'Kho riêng · tại máy':accountInfo?.localPoC?'Làm việc tại máy':(balance.toLocaleString?.('vi-VN')||balance)+' điểm trợ lý'}</small></span>`,`class="account-button" title="Tài khoản cục bộ" aria-label="Tài khoản: ${esc(name)}"`)}${creditsHTML}</div>`;const old=actions.querySelector('.account-control');if(old?.outerHTML===markup)return;actions.querySelectorAll('.avatar,.account-control').forEach(n=>n.remove());actions.insertAdjacentHTML('beforeend',markup);}

function stageElapsedSeconds(){
 return stageStartedAt?Math.max(0,Math.floor((Date.now()-stageStartedAt)/1000)):0;
}
function updateStageClockDOM(){
 const el=typeof document!=='undefined'?document.querySelector('.ai-stage-timer'):null;
 if(!el)return;
 el.textContent=`${stageElapsedSeconds()}s`;
}
function startStageTimer(label){
 stopStageTimer();
 stage=label;
 stageStartedAt=Date.now();
 busy=true;
 refreshWorkbench();
 stageTimer=setInterval(updateStageClockDOM,1000);
}
function stopStageTimer(){
 if(stageTimer){clearInterval(stageTimer);stageTimer=null;}
 stageStartedAt=0;
}
function aiStageStepsHTML(stageText){
 const text=String(stageText||'').toLocaleLowerCase('vi-VN');
 const step=text.includes('lưu')||text.includes('đồng bộ')?2:text.includes('trả lời')||text.includes('soạn thảo')||text.includes('sửa')||text.includes('điều chỉnh')?1:0;
 const labels=['Đọc đề & ngữ cảnh','Xử lý yêu cầu AI','Kiểm tra & sẵn sàng'];
 return `<ol class="ai-steps">${labels.map((label,i)=>`<li class="ai-step ${i<step?'is-done':i===step?'is-active':''}"><span class="ai-step-dot" aria-hidden="true"></span><span>${label}</span></li>`).join('')}</ol>`;
}
function statusHTML(){
 if(!busy)return '';
 const sec=stageElapsedSeconds();
 const earlyHTML=writeController?`<div class="ai-stage-actions">${b('early-stop-ai','Dừng &amp; Lấy câu đã xong','class="early-stop-ai-button" aria-label="Dừng & Lấy câu đã xong" title="Dừng & Lấy câu đã xong"')}</div>`:'';
 return `<div class="ai-stage" role="status"><div class="ai-stage-head"><i class="ai-orbit">✧</i><span class="ai-stage-label">${esc(stage||'Đang trả lời AI…')}</span><span class="ai-stage-timer" aria-live="off">${sec}s</span></div>${aiStageStepsHTML(stage)}${earlyHTML}</div>`;
}
function planHTML(plan){return `<div class="plan-card"><b>Phương án đề · ${esc(plan.subject)} ${esc(plan.grade)}</b><p>${esc(plan.period)} · ${plan.minutes} phút · Tổng ${plan.totalPoints} điểm</p><ol>${plan.slots.map(s=>`<li>${esc(s.topic)} <small>${{essay:'Tự luận',mcq:'Trắc nghiệm',truefalse:'Đúng–sai',short:'Trả lời ngắn'}[s.type]}</small> <strong>${s.points.toLocaleString('vi-VN')} điểm</strong>${s.figure?' · có hình dựng từ tọa độ':''}</li>`).join('')}</ol><label class="plan-consent"><input type="checkbox" id="plan-consent" ${c.exam().aiConsent?'checked':''}> Cho phép gửi yêu cầu và các nguồn đã chọn đến kết nối AI hiện tại.</label><div class="plan-decisions">${b('approve-plan','Có · Bắt đầu soạn','class="primary"')}${b('reject-plan','Không · Chỉnh cấu trúc')}</div><small>Ước tính tối đa ${Math.ceil(plan.slots.length*27*(1+(c.exam().aiEffort??1)*.5))} điểm trợ lý; cập nhật theo độ dài kết quả.</small></div>`;}
function contextPlanHTML(e){
 const active=activeScopes();
 const {plan,buttons,contextHeaderHTML}=contextualSuggestionsHTML(e,{selectedId:c.getSelected?.(),scope:active[0]||null,matrixOpen:matrixChatRunning(c)});
 return {plan,buttons,contextHeaderHTML};
}
function welcomeHTML(){
 const e=c.exam();
 const {plan,buttons}=contextPlanHTML(e);
 const subtitle=plan.mode==='empty'
  ?'Chọn câu hoặc bôi đen để sửa đúng phần cần đổi, hoặc kéo–thả tệp nguồn vào khung này.'
  :plan.summary;
 return `<div class="assistant-welcome" style="text-align:center;padding:8px 4px 6px"><span class="ctx-badge assistant-context-badge" style="display:inline-block;margin:0 0 8px;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:600;line-height:1.35;background:#e6f4ef;color:#11695b">${esc(plan.badge)}</span><h2 style="color:#2563eb;font-weight:700;line-height:1.35;margin:0 0 6px">${plan.mode==='empty'?'Thầy cô muốn soạn đề<br>cho lớp nào trước?':'Gợi ý thao tác tiếp theo'}</h2><p class="ctx-summary" style="display:block;margin:0 0 8px;font-size:12.5px;line-height:1.45;color:#4f645d">${esc(subtitle)}</p></div><div class="welcome-prompts contextual-prompts">${buttons}</div>`;
}
export {formatProviderName,formatLatencyLabel,chatMetaBadgeText};

function renderChatBodyHTML(m){
 const raw=String(m.text||'').replace(/\$\$([\s\S]+?)\$\$/g,(_,tex)=>'$$'+tex.replace(/\r?\n/g,' ')+'$$').replace(/\\\[([\s\S]+?)\\\]/g,(_,tex)=>'$$'+tex.replace(/\r?\n/g,' ')+'$$');
 return m.role==='assistant'?assistantText(raw):richTextHTML(raw);
}
export function buildSuggestedActionPreview(act,exam){
 if(!act||typeof act!=='object')return {kind:'',summary:''};
 const kind=act.kind||'';
 if(kind==='propose_questions'){
  const rawList=Array.isArray(act.questions)&&act.questions.length?act.questions:Array.isArray(act.data?.questions)&&act.data.questions.length?act.data.questions:act.stem?[act]:[];
  return {kind,count:rawList.length,questions:rawList,summary:`${rawList.length||1} câu hỏi mới (chưa tự lưu vào đề)`};
 }
 if(kind==='propose_patch'){
  const patch=act.patch||act.question||act.data||act;
  const ord=Number(act.questionNumber||act.ordinal||patch.questionNumber||patch.ordinal||0);
  const targetQ=(act.questionId&&exam?.questions?.find(q=>q.id===act.questionId))||(ord>=1&&exam?.questions?.[ord-1])||exam?.questions?.[0]||null;
  return {kind,targetQ,patch,ordinal:targetQ?exam.questions.indexOf(targetQ)+1:(ord||1),summary:`Đề xuất sửa Câu ${targetQ?exam.questions.indexOf(targetQ)+1:(ord||1)} (cần bấm xác nhận)`};
 }
 if(kind==='propose_matrix'){
  const rows=Array.isArray(act.matrix)&&act.matrix.length?act.matrix:Array.isArray(act.rows)&&act.rows.length?act.rows:Array.isArray(act.data?.matrix)?act.data.matrix:(exam?.matrix||[]);
  return {kind,rows,summary:`Ma trận ${rows.length} dòng (cần bấm xác nhận để nạp)`};
 }
 return {kind,summary:String(act.summary||act.description||'')};
}
function chatActionCardsHTML(m,msgIndex,e){
 if(!Array.isArray(m.suggestedActions)||!m.suggestedActions.length)return '';
 return `<div class="chat-action-cards">${m.suggestedActions.map((act,actIndex)=>{
  if(!act||typeof act!=='object')return '';
  const kind=act.kind||'';
  let btnHTML='';
  if(kind==='propose_questions'){
   btnHTML=b('apply-chat-questions','Xem &amp; xác nhận đưa vào đề',`class="primary" data-msg-index="${msgIndex}" data-action-index="${actIndex}"`);
  }else if(kind==='propose_patch'){
   const qNum=act.questionNumber||act.ordinal||(act.questionId?e.questions.findIndex(q=>q.id===act.questionId)+1:0)||(c.getSelected?.()?e.questions.findIndex(q=>q.id===c.getSelected())+1:0)||1;
   btnHTML=b('apply-chat-patch',`Xem &amp; xác nhận sửa Câu ${qNum}`,`class="primary" data-msg-index="${msgIndex}" data-action-index="${actIndex}"`);
  }else if(kind==='propose_matrix'){
   btnHTML=b('apply-chat-matrix','Xem &amp; xác nhận nạp ma trận',`class="primary" data-msg-index="${msgIndex}" data-action-index="${actIndex}"`);
  }else return '';
  const defaultTitle=kind==='propose_questions'?'Đề xuất câu hỏi mới':kind==='propose_patch'?'Đề xuất sửa câu hỏi':'Đề xuất cấu trúc ma trận';
  const prev=buildSuggestedActionPreview(act,e);
  const desc=act.summary||act.description||prev.summary||'';
  return `<div class="chat-action-card" data-action-kind="${esc(kind)}"><b>${esc(act.title||defaultTitle)}</b>${desc?`<p>${richTextHTML(String(desc))}</p>`:''}<div class="chat-action-buttons">${btnHTML}${act.appliedRevision?`<span class="pill ok">Đã xác nhận (v${act.appliedRevision})</span>`:''}</div></div>`;
 }).join('')}</div>`;
}
function chatFollowUpsHTML(m){
 if(!Array.isArray(m.followUps)||!m.followUps.length)return '';
 const chips=m.followUps.map(item=>{
  const prompt=typeof item==='string'?item:(item?.prompt||item?.text||item?.label||'');
  return prompt?b('chat-followup',esc(prompt),`class="chat-followup-chip" data-prompt="${esc(prompt)}"`):'';
 }).filter(Boolean).join('');
 return chips?`<div class="chat-followup-list">${chips}</div>`:'';
}
function streamingBubbleHTML(){
 if(!streamingState||streamingState.examId!==c?.exam()?.id)return '';
 const meta=streamingState.provider?`<span class="chat-provider-meta">${esc(formatProviderName(streamingState.provider))}${streamingState.model?' · '+esc(streamingState.model):''}</span>`:'';
 return `<div class="assistant-message role-assistant streaming-reply"><span class="chat-spark">✧</span><div>${streamingState.text?assistantText(streamingState.text):'<span class="hint">Đang kết nối luồng trả lời…</span>'}<span class="streaming-caret" aria-hidden="true"></span>${meta?`<div class="chat-msg-tools">${meta}</div>`:''}</div></div>`;
}
function chatHTML(){
 const e=c.exam(),messages=e.chat.filter((m,i)=>!(m.needsAIConsent&&e.aiConsent)&&!(i===0&&m.role==='assistant'&&/^(Đây là ví dụ Toán|Thầy cô đang mở ví dụ|Đề mới đã áp dụng)/.test(m.text)));
 const listHTML=messages.length?messages.map(m=>{
  const msgIndex=e.chat.indexOf(m);
  if(m.needsAIConsent&&!e.aiConsent){
   return `<div class="assistant-message role-assistant is-consent"><span class="chat-spark">✧</span><div class="chat-consent-card" tabindex="-1"><strong class="chat-consent-title">Cho phép bật Trợ lý AI cho đề này</strong><p class="chat-consent-text">${esc(m.text)}</p><div class="chat-consent-request">${b('chat-consent-send','✓ Cho phép và gửi ngay','class="primary"')}</div></div></div>`;
  }
  const metaBadge=m.role==='assistant'?chatMetaBadgeText(m):'';
  const msgTools=m.role==='assistant'&&!m.needsAIConsent
   ?`<div class="chat-msg-tools">${metaBadge?`<span class="chat-provider-meta"${m.fallbackReason?` title="${esc(m.fallbackReason)}"`:''}>${esc(metaBadge)}</span>`:''}${b('copy-chat-msg','Sao chép',`class="chat-copy-btn" data-msg-index="${msgIndex}" title="Sao chép nội dung trả lời" aria-label="Sao chép phản hồi trợ lý"`)}</div>`
   :'';
  return `<div class="assistant-message ${m.role==='user'?'user':'role-assistant'}">${m.role==='assistant'?'<span class="chat-spark">✧</span>':''}<div>${renderChatBodyHTML(m)}${m.role==='assistant'?chatActionCardsHTML(m,msgIndex,e)+chatFollowUpsHTML(m):''}${msgTools}${m.undoRevision?b('undo-ai','↶ Hoàn tác lần AI vừa sửa',`class="chat-undo" data-revision="${m.undoRevision}"`):''}</div></div>`;
 }).join(''):welcomeHTML();
 return `${listHTML}${streamingBubbleHTML()}${e.aiPlan&&!busy?planHTML(e.aiPlan):''}${statusHTML()}${proposal&&!busy?`<div class="proposal-card"><b>Đề xuất sửa ${proposal.edits.length} khối</b><p>${esc(proposal.message)}</p>${proposal.checks?.length?'<p class=hint>Đã qua: '+proposal.checks.map(esc).join(' · ')+'. Vẫn cần thầy cô rà lại.</p>':''}${b('apply-block-patch','✓ Chấp nhận','class=primary')}${b('discard-block-patch','✕ Bỏ đề xuất')}${b('show-block-diff','Xem thay đổi xanh/đỏ','class="proposal-diff"')}</div>`:''}${recovery&&!busy?(recovery.status==='running'?`<div class="recovery-card" role="status">AI vẫn đang soạn trên server. Mình sẽ kiểm tra kết quả để bạn khôi phục; không cần gửi lại yêu cầu.</div>`:`<div class="recovery-card"><b>Có kết quả AI đã hoàn tất trên server</b><p>Khôi phục thành một đề riêng để giữ nội dung đang mở.</p>${b('recover-ai','Khôi phục đề đã soạn','class="primary"')}</div>`):''}`;
}
function activeScopes(){return scopes.length?clone(scopes):!contextMuted&&c.currentScope()?[c.currentScope()]:[];}
function syncTimePresetSelect(){
 const select=$('#chat-time-preset');
 if(!select||!c)return;
 const current=c.exam().aiTimePreset;
 select.value=CHAT_TIME_PRESETS.some(([id])=>id===current)?current:'standard';
}
function applyTimePreset(preset){
 const meta=CHAT_TIME_PRESETS.find(([id])=>id===preset)||CHAT_TIME_PRESETS[1];
 c.exam().aiTimePreset=meta[0];
 syncTimePresetSelect();
 void c.persist();
 void api('/api/config',{fixedRouter:{enabled:true,timePreset:meta[0],timeoutSeconds:meta[2]}}).catch(()=>{});
}
function buildFlexibleChatContext(e,selected,history){
 const ctx=[
  {kind:'conversation',messages:history},
  {kind:'exam-summary',subject:e.subject,grade:e.grade,questionCount:e.questions.length},
  ...selected,
 ];
 const MAX_JSON=54000;
 const qSummaries=(e.questions||[]).map((q,i)=>({
  number:i+1,
  id:q.id,
  type:q.type||'mcq',
  points:q.points||0,
  topic:String(q.topic||'').slice(0,80),
  stem:String(q.stem||'').slice(0,260),
  ...(Array.isArray(q.options)&&q.options.length?{options:q.options.slice(0,4).map(o=>String(o||'').slice(0,90))}:{}),
  ...(q.type==='mcq'&&Number.isInteger(q.answer)?{answer:q.answer}:{}),
  ...(q.answerText?{answerText:String(q.answerText).slice(0,80)}:{}),
 }));
 if(qSummaries.length){
  const kept=[];
  for(const item of qSummaries){
   kept.push(item);
   if(JSON.stringify([...ctx,{kind:'exam-questions-summary',total:e.questions.length,questions:kept}]).length>MAX_JSON-14000){
    kept.pop();
    break;
   }
  }
  if(kept.length)ctx.push({kind:'exam-questions-summary',total:e.questions.length,questions:kept});
 }
 const attachedIds=Array.isArray(e.assistantSources)&&e.assistantSources.length?e.assistantSources:null;
 const basePool=e.strictTeacherOnly?(e.docs||[]).filter(d=>!d.sample):(e.docs||[]);
 const docPool=attachedIds?basePool.filter(d=>attachedIds.includes(d.id)):basePool;
 const docs=(docPool.length?docPool:e.strictTeacherOnly?[]:(e.docs||[])).slice(0,3);
 for(const doc of docs){
  const rawText=String(doc.text||(doc.pages||[]).map(p=>p.text||'').join('\n\n')||'');
  const remaining=MAX_JSON-JSON.stringify(ctx).length-220;
  if(remaining<=200)break;
  const excerpt=rawText.slice(0,Math.min(4000,remaining));
  ctx.push({kind:'attached-source',id:doc.id,name:doc.name,excerpt});
 }
 return ctx;
}
function paintScopes(){const box=$('.compose-box');if(!box)return;box.querySelectorAll('.selection-chip').forEach(n=>n.remove());document.querySelectorAll('.time-preset-bar').forEach(n=>n.remove());let chips=box.querySelector('#context-chips');if(!chips){chips=document.createElement('div');chips.id='context-chips';box.prepend(chips);}const visible=activeScopes(),mode=c.exam().aiChatMode||'auto';let modeControl=document.querySelector('.chat-context-mode');if(!modeControl){modeControl=document.createElement('div');modeControl.innerHTML=`<div class="chat-context-mode"><label for="chat-mode">Khi gửi</label><select id="chat-mode" aria-label="Chế độ chat"><option value="auto" >Tự hiểu yêu cầu</option><option value="ask" >Chỉ hỏi / giải thích</option><option value="edit" >Đề xuất sửa</option></select></div>`;modeControl=modeControl.firstElementChild;box.prepend(modeControl);}modeControl.querySelector('select').value=mode;const markup=(visible.length?visible.map((s,i)=>{let stale=false,current=s;try{current=refreshScope(c.exam(),s);}catch{stale=true;}const index=c.exam().questions.findIndex(q=>q.id===s.id),field=FIELD_LABELS[s.field]||'Đề bài',part=Number.isInteger(s.index)?` · ${s.field==='rubric'?'bước':'mục'} ${s.index+1}`:'';return `<div class="context-chip ${stale?'context-stale':''}"><span title="${esc(current.text)}"><b>Bài ${index+1} · ${esc(field)}${part}</b><small>${stale?'Đã đổi · bôi đen lại':current.wholeField?'Toàn phần đang chọn':esc(current.text.slice(0,95))}</small></span>${b('remove-context','×',`data-index="${i}" aria-label="Gỡ ngữ cảnh ${i+1}"`)}</div>`;}).join(''):'<p class="context-empty">Chưa chọn vùng · có thể ghi “sửa bài 2” trong tin nhắn.</p>');if(chips._markup!==markup){chips.innerHTML=markup;chips._markup=markup;}syncTimePresetSelect();}
function clearContext(){scopes=[];contextMuted=true;c.setSelection(null);getSelection()?.removeAllRanges();$('.selection-ask')?.remove();paintScopes();}
function advanceScopes(previous){scopes=previous.map(old=>{const q=c.qget(old.id);if(!q)return null;if(old.wholeField)return refreshScope(c.exam(),old);const value=scopeValue(q,old),oldValue=old.fieldValue??old.text;const suffixLength=oldValue.length-old.end,end=value.length-suffixLength;return {...old,version:q.v,end,text:value.slice(old.start,end),fieldValue:value};}).filter(Boolean);contextMuted=false;if(scopes[0])c.setSelected(scopes[0].id);c.setSelection(scopes[0]||null);}
function scrollConsentCardIntoView(body){
 const card=body?.querySelector?.('.chat-consent-card');
 if(!card)return false;
 body.scrollTop=body.scrollHeight;
 if(typeof requestAnimationFrame==='function'){
  requestAnimationFrame(()=>{
   if(!body.isConnected)return;
   body.scrollTop=body.scrollHeight;
   card.scrollIntoView?.({block:'end',behavior:'smooth'});
  });
 }
 return true;
}
function focusConsentCard(){
 openAI();
 const body=$('.assistant-body');
 const card=body?.querySelector?.('.chat-consent-card');
 if(card){
  card.classList.remove('is-attention');
  void card.offsetWidth;
  card.classList.add('is-attention');
  clearTimeout(consentPulseTimer);
  consentPulseTimer=setTimeout(()=>card.classList.remove('is-attention'),1400);
  if(body)body.scrollTop=body.scrollHeight;
  card.scrollIntoView?.({block:'nearest',behavior:'smooth'});
  (card.querySelector('[data-action="chat-consent-send"]')||card).focus?.();
 }
 c.toast('Bấm "Cho phép và gửi ngay" phía trên để bật AI cho đề này.');
}
export function refreshWorkbench(){if(!c)return;const body=$('.assistant-body');if(body){const bottom=body.scrollTop+body.clientHeight>=body.scrollHeight-80;const html=chatHTML();if(body._chatMarkup!==html){const position=body.scrollTop;body.innerHTML=html;body._chatMarkup=html;const showingWelcome=Boolean(body.querySelector('.assistant-welcome'))&&!body.querySelector('.assistant-message,.msg');if(showingWelcome){body.scrollTop=0;if(typeof requestAnimationFrame==='function')requestAnimationFrame(()=>{if(body.isConnected&&body.querySelector('.assistant-welcome')&&!body.querySelector('.assistant-message,.msg'))body.scrollTop=0;});}else if(!scrollConsentCardIntoView(body))body.scrollTop=bottom?body.scrollHeight:position;}}paintScopes();paintAccount();lockEditors();document.querySelectorAll('#chat-form button[type=submit],[data-action=approve-plan],[data-action=reject-plan]').forEach(n=>n.disabled=busy);document.querySelectorAll('.stop-ai-button,.early-stop-ai-button').forEach(n=>{if(!n.closest('.ai-stage-actions'))n.remove();});const send=$('#chat-form button[type=submit]');if(patchController&&send){send.hidden=true;send.insertAdjacentHTML('afterend',b('stop-ai','■','class="stop-ai-button" aria-label="Dừng chờ đề xuất" title="Dừng chờ đề xuất"'));}else if(writeController&&send){send.hidden=true;send.insertAdjacentHTML('afterend',b('stop-ai','■',`class="stop-ai-button" aria-label="Dừng soạn đề" title="Dừng soạn đề" ${activeJobId?'':'disabled'}`));}else if(busy&&send){send.hidden=true;send.insertAdjacentHTML('afterend',b('stop-ai','■','class="stop-ai-button" aria-label="Dừng tác vụ" title="Dừng tác vụ"'));}else if(send)send.hidden=false;mountMatrixChat(c);refreshUsability();}
function lockEditors(){setEditorsLocked(busy);document.querySelectorAll('.paper input,.paper textarea').forEach(n=>n.disabled=busy);$('.paper')?.classList.toggle('ai-writing',busy);$('.writing-chip')?.remove();if(busy)$('.paper-scroll')?.insertAdjacentHTML('afterbegin','<div class="writing-chip" role="status">✧ Trợ lý AI đang viết vào đề… Đã khóa chỉnh sửa</div>');}
export function mountWorkbench(context){c=context;if(mountedExam!==c.exam().id){mountedExam=c.exam().id;scopes=[];contextMuted=false;proposal=null;recovery=null;watchedJob=null;streamingState=null;pendingChatAction=null;clearTimeout(jobTimer);if(c.exam().activeAIJob)setTimeout(()=>watchJob(c.exam().activeAIJob),0);}ensureBlocks(c.exam());const title=$('.header-title');if(title?.tagName==='BUTTON'){const input=document.createElement('input');input.className='header-title';input.maxLength=180;input.value=c.exam().title;input.dataset.examField='title';input.setAttribute('aria-label','Tên tài liệu');title.replaceWith(input);}paintAccount();
 document.querySelectorAll('.question').forEach(el=>{const q=c.qget(el.dataset.q);el.dataset.blockId=q.blockIds.stem;el.querySelector('.stem-editor')?.setAttribute('data-block-id',q.blockIds.stem);if(q.figure&&!el.querySelector('.geometry-figure')){const figure=document.createElement('figure');figure.className='geometry-figure';figure.style.width=Math.min(700,Math.max(180,Number(q.figure.width)||480))+'px';figure.dataset.blockId=q.blockIds.figure;figure.innerHTML=renderFigure(q.figure)+`<figcaption>${esc(q.figure.caption||'')}${b('edit-figure','Sửa hình',`class="tiny-btn" data-id="${q.id}"`)}</figcaption>`;el.querySelector('.question-assets')?.append(figure);}});
 if(c.exam().questions.length&&!$('.document-summary')){$('.paper').classList.remove('empty-paper');$('.paper-footer')?.before(Object.assign(document.createElement('div'),{className:'document-summary',textContent:'Tổng điểm: '+c.exam().questions.reduce((n,q)=>n+(q.points||0),0).toLocaleString('vi-VN')}));}
 if(separateMarking(c.exam())&&!$('#marking-guide')){const sec=$('.paper-section');if(sec?.firstChild)sec.firstChild.textContent='PHẦN ĐỀ THI';document.querySelectorAll('.question .essay-answer').forEach(n=>n.remove());document.querySelectorAll('.answer-area').forEach(n=>n.remove());const guide=document.createElement('section');guide.id='marking-guide';guide.className='marking-guide';guide.dataset.blockId=c.exam().blockIds.marking;guide.innerHTML=`<h2>HƯỚNG DẪN CHẤM VÀ BIỂU ĐIỂM</h2><h3 id="marking-general">A. HƯỚNG DẪN CHUNG</h3><p>${esc(c.exam().markingGuidance||'Chấm theo các bước nêu trong đáp án. Học sinh có cách giải khác đúng được điểm tương ứng. Làm tròn và đơn vị theo yêu cầu của từng bài.')}</p><h3 id="marking-table">B. ĐÁP ÁN VÀ THANG ĐIỂM</h3><table class="full-rubric-table"><thead><tr><th>Bài</th><th>Nội dung / lời giải</th><th>Điểm</th></tr></thead><tbody>${c.exam().questions.map((q,i)=>`<tr><td rowspan="${(q.rubric?.length||0)+1}"><b>Bài ${i+1}</b><br>(${q.points} điểm)</td><td>${richTextHTML(q.explanation)} ${b('rubric','Sửa lời giải / barem',`class="tiny-btn" data-id="${q.id}"`)}</td><td></td></tr>${(q.rubric||[]).map(r=>`<tr><td>${richTextHTML(r.text)}</td><td>${r.points.toLocaleString('vi-VN')}</td></tr>`).join('')}`).join('')}</tbody></table>`;$('.paper-footer').before(guide);}
 const compose=$('.chat-compose');if(compose&&!$('#ai-consent'))compose.insertAdjacentHTML('beforeend',`<label class="compose-consent"><input id="ai-consent" type="checkbox" ${c.exam().aiConsent?'checked':''}> Cho phép gửi nội dung đến kết nối AI đã chọn</label>`);if(c.exam().fullExam&&!$('#auto-update-answers'))compose.insertAdjacentHTML('beforeend',`<label class="compose-consent"><input id="auto-update-answers" type="checkbox" ${c.exam().autoUpdate!==false?'checked':''}> Tự cập nhật lời giải / barem sau sửa tay</label>`);$('#chat-input').value=drafts.get(c.exam().id)||'';refreshWorkbench();paginate();
 if(!initialized){initialized=true;document.addEventListener('editor-selection-changed',ev=>{if(ev.detail?.origin==='selection'||document.activeElement?.closest('.stem-editor,.rich-field-editor')){scopes=[];contextMuted=false;}});document.addEventListener('question-selected',()=>{scopes=[];contextMuted=false;});document.addEventListener('change',ev=>{if(ev.target.id==='chat-mode'){c.exam().aiChatMode=ev.target.value;c.persist();}if(ev.target.id==='chat-time-preset'){applyTimePreset(ev.target.value);}});window.addEventListener('online',()=>{if(c?.exam().activeAIJob)watchJob(c.exam().activeAIJob);});document.addEventListener('input',ev=>{if(ev.target.id==='chat-input')drafts.set(c.exam().id,ev.target.value);if(ev.target.id==='library-filter')filterLibrary(ev.target.value);if(ev.target.id==='figure-spec'){try{$('#figure-preview').innerHTML=renderFigure(JSON.parse(ev.target.value));$('#figure-error').textContent='';}catch(e){$('#figure-error').textContent=friendlyClientMessage(e);}}});document.addEventListener('change',ev=>{if(ev.target.id==='auto-update-answers'){c.exam().autoUpdate=ev.target.checked;c.persist();}if(ev.target.id==='ai-consent'){c.exam().aiConsent=ev.target.checked;c.persist();}if(ev.target.id==='doc-alignment')import('./editor.js').then(m=>m.format(ev.target.value));});document.addEventListener('keydown',ev=>{if((ev.ctrlKey||ev.metaKey)&&ev.key.toLowerCase()==='z'&&!ev.target.closest('.tiptap,input,textarea,math-field,.composer-shell')){ev.preventDefault();if(!busy)c.act(ev.shiftKey?'redo':'undo');}});document.addEventListener('click',ev=>{const section=ev.target.closest('.question');if(section&&!ev.target.closest('button,textarea,input,[contenteditable]'))c.setSelected(section.dataset.q);});}
}
function paginate(){const paper=$('.paper');if(!paper)return;paper.querySelectorAll('.page-separator').forEach(n=>n.remove());const max=1123*paper.offsetWidth/794,children=[...paper.querySelectorAll(':scope>.question,:scope>.marking-guide')];let next=max-80;for(const child of children){const top=child.offsetTop-paper.offsetTop;if(top+Math.min(child.offsetHeight,180)>next){const gap=document.createElement('div');gap.className='page-separator';gap.setAttribute('aria-label','Ngắt trang');child.before(gap);next=top+max-80;}}}
export async function initWorkbench(context){c=context;await refreshAccount();const copy=new URLSearchParams(location.search).get('copy');if(copy){try{const result=await api('/api/share/read/'+encodeURIComponent(copy));if(!result.allowCopy)throw Error('Liên kết chỉ cho xem.');const e=duplicateExam(result.exam);c.getState().exams.push(e);c.getState().current=e.id;await c.persist();history.replaceState({},'',location.pathname);c.render();}catch(e){c.toast(e.message);}}await watchJob(c.exam().activeAIJob||null); }

function selectedSources(e){const ids=e.assistantSources||[];return e.docs.filter(d=>ids.includes(d.id)).flatMap(d=>selectedDocumentPages(e,d).filter(p=>p.text).map(p=>({docId:d.id,page:p.number,location:d.name+' · '+sourcePageLabel(d,p.number),text:p.text})));}
function addMessage(role,text,extra={}){c.exam().chat.push({role,text,at:Date.now(),...extra});c.persist();refreshWorkbench();}
function openAI(){document.querySelector('.workspace')?.classList.remove('chat-hidden','focus-mode');document.querySelector('.assistant')?.classList.add('open');}
async function planRequest(text){if(accountInfo?.localPoC){await openMatrixChat(c,{request:text});return;}startStageTimer('Hệ thống đang phân tích yêu cầu của bạn…');try{const e=c.exam(),result=await api('/api/assistant/plan',{text,exam:{subject:e.subject,grade:e.grade},pending:e.aiClarification||null,sources:selectedSources(e),matrix:e.matrixConfirmed?e.matrix:null,consent:e.aiConsent});if(result.kind==='clarify'){e.aiClarification=result;addMessage('assistant',result.message);}else{e.aiClarification=null;e.aiPlan=result;addMessage('assistant',result.message);}await c.persist();}finally{stopStageTimer();busy=false;stage='';refreshWorkbench();}}
async function writePlan(){const e=c.exam(),plan=e.aiPlan;if(!plan)return;const planConsent=$('#plan-consent');const consent=planConsent?planConsent.checked:e.aiConsent;e.aiConsent=consent;if(!consent){c.toast('Đánh dấu cho phép gửi nội dung đến kết nối AI trước khi soạn.');return;}flushEditor();await c.persist();const original=snapshot(e);writeController=new AbortController();activeJobId=null;cancelRequested=false;writtenCount=0;stopStageTimer();stageStartedAt=Date.now();busy=true;stage='Đang soạn thảo nội dung đề thi…';e.aiPlan=null;e.questions=[];e.fullExam=true;e.title=plan.title;e.subject=plan.subject;e.grade=plan.grade;e.minutes=plan.minutes;e.instructions='Thí sinh thực hiện theo yêu cầu của từng phần. Đề gồm '+plan.slots.length+' bài, tổng 10 điểm.';c.render();stageTimer=setInterval(updateStageClockDOM,1000);let completed=false;try{const response=await fetch('/api/assistant/stream',{signal:writeController.signal,method:'POST',headers:{'Content-Type':'application/json',...workspaceHeaders()},body:JSON.stringify({plan,effort:e.aiEffort??1,examId:e.id,revision:original.revision,sources:selectedSources(original),consent})});if(!response.ok){const result=await response.json();throw await aiRequestError('/api/assistant/stream',result.error||'Chưa bắt đầu được lần soạn.');}const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let end;while((end=buffer.indexOf('\n\n'))>=0){const record=buffer.slice(0,end);buffer=buffer.slice(end+2);const type=record.match(/^event: (.+)$/m)?.[1],dataText=record.match(/^data: (.+)$/m)?.[1];if(!type||!dataText)continue;const data=JSON.parse(dataText);if(type==='job'){activeJobId=data.id;if(data.credits){accountInfo={...accountInfo,credits:data.credits};paintAccount();}original.activeAIJob=data.id;e.activeAIJob=data.id;const working=snapshot(e);Object.assign(e,clone(original));await c.persist();Object.assign(e,working);}if(type==='stage'){stage=data.text;refreshWorkbench();}if(type==='block'){writtenCount++;e.questions.push(data.question);ensureBlocks(e);c.render();document.getElementById('q-'+data.question.id)?.scrollIntoView({block:'nearest'});}if(type==='error')throw await aiRequestError('/api/assistant/stream',data.message);if(type==='done'){completed=true;(c.getState().seenAIJobs??=[]).push(data.id);original.activeAIJob=null;Object.assign(e,clone(original));stopStageTimer();busy=false;c.change('AI soạn toàn bộ đề theo cấu trúc đã duyệt',target=>{target.questions=data.questions;target.sample=false;target.fullExam=true;target.title=plan.title;target.subject=plan.subject;target.grade=plan.grade;target.minutes=plan.minutes;target.instructions='Đề gồm '+data.questions.length+' bài. Thí sinh thực hiện theo yêu cầu của từng phần.';target.aiPlan=null;target.aiClarification=null;target.activeAIJob=null;});addMessage('assistant',data.message,{undoRevision:c.exam().revision});accountInfo={...accountInfo,credits:data.credits};c.render();}}}if(!completed)throw Error('Kết nối bị ngắt trước khi nhận đủ đề. Kết quả trên server có thể khôi phục khi tải lại.');}catch(error){Object.assign(e,clone(original));if(cancelRequested)e.activeAIJob=null;stopStageTimer();busy=false;stage='';c.render();addMessage('assistant',cancelRequested?'Mình đã dừng lần soạn này và giữ nguyên bản đề trước đó. Tác vụ hiện tại trên máy chủ sẽ kết thúc rồi hoàn điểm.':friendlyClientMessage(error));if(e.activeAIJob&&!cancelRequested)try{const job=await api('/api/assistant/job?id='+encodeURIComponent(e.activeAIJob));if(job.status==='complete')recovery=job;}catch{}}finally{stopStageTimer();writeController=null;activeJobId=null;busy=false;stage='';refreshWorkbench();await refreshAccount();}}
async function requestEdit(text,intent,overrideScopes=null,autoApply=false){if(accountInfo?.localPoC)autoApply=false;if(!flushEditor())throw Error('Gõ xong chữ đang nhập rồi thử lại.');await c.persist();const e=ensureBlocks(c.exam()),selected=requestScopes(e,text,{scopes:overrideScopes||activeScopes(),fallback:null,muted:contextMuted,intent}).map(s=>({...s,fieldValue:scopeValue(e.questions.find(q=>q.id===s.id),s)}));if(accountInfo?.localPoC&&selected.some(s=>{const type=e.questions.find(q=>q.id===s.id)?.type;return !({mcq:['stem','options','answer','explanation','rubric'],essay:['stem','explanation','rubric'],short:['stem','answerText','explanation','rubric'],truefalse:['stem','options','truthValues','explanation','rubric']}[type]||[]).includes(s.field);}))throw Error('Chọn đề bài, lời giải hoặc trường đáp án/barem phù hợp với dạng câu. Lượt này chưa sửa khối hình vẽ.');scopes=clone(selected);contextMuted=false;const examId=e.id,revision=e.revision;const recent=e.chat.slice(0,e.chat.at(-1)?.role==='user'&&e.chat.at(-1)?.text===text?-1:undefined).slice(-6).map(m=>({role:m.role,text:String(m.text).slice(0,1800)}));const conversation='\nMôn '+e.subject+' · Lớp '+e.grade+'. Hội thoại gần đây chỉ để hiểu các từ như “câu vừa gợi ý”, không mở rộng phạm vi sửa: '+JSON.stringify(recent);const controller=new AbortController();patchController=controller;proposal=null;startStageTimer('Mình đang sửa đúng phần đã chọn và kiểm tra phần liên quan…');try{const patchHeaders=accountInfo?.localPoC?{'X-PoC-Config':(await api('/api/config',undefined,{},controller.signal)).fingerprint}:{};let result,validated,feedback='';for(let attempt=0;attempt<2;attempt++){result=await api('/api/assistant/patch',{exam:clone(e),effort:e.aiEffort??1,scopes:selected,request:text+conversation+'\nPhạm vi bắt buộc:\n'+scopeInstructions(e,selected)+(intent==='verify'?'\nChỉ thay lời giải, barem, đáp án hoặc hình khi cần; giữ nguyên đề và phương án.':'')+feedback,consent:e.aiConsent},patchHeaders,controller.signal);controller.signal.throwIfAborted();if(c.exam().id!==examId||c.exam().revision!==revision)throw Error('Nội dung đã đổi trong lúc AI xử lý. Kết quả chưa được áp dụng.');try{validated=validateEdits(e,result,selected,validateMath);break;}catch(error){if(attempt===1)throw error;feedback='\nĐề xuất trước sai phạm vi: '+error.message+'. Giữ nguyên các chữ, ô và bước ngoài phạm vi, trả lại đầy đủ các trường cần thay.';stage='Mình đang điều chỉnh đề xuất để giữ nguyên phần ngoài vùng chọn…';refreshWorkbench();}}
 const current=blocksOf(e);const edits=validated.edits.filter(edit=>!contentEqual(edit.field,current.find(b=>b.id===edit.blockId)?.content,edit.content));if(!edits.length){addMessage('assistant','Không có thay đổi nội dung cần áp dụng trong phần đang chọn.');return;}proposal={...result,edits,message:validated.message,examId,revision,scopes:clone(selected)};accountInfo={...accountInfo,credits:result.credits};if(autoApply){const pending=proposal;applyEdits(clone(e),pending.edits,{richTransform:reconcileEditorRich});proposal=null;stopStageTimer();busy=false;c.change('Tự đồng bộ lời giải và barem sau sửa tay',target=>applyEdits(target,pending.edits,{richTransform:reconcileEditorRich}));advanceScopes(pending.scopes);addMessage('assistant','Mình đã cập nhật lời giải và barem theo nội dung bạn vừa sửa.',{undoRevision:c.exam().revision});c.render();}}finally{stopStageTimer();patchController=null;busy=false;stage='';refreshWorkbench();if(!controller.signal.aborted)await refreshAccount();}}
function currentProposal(){if(!proposal||proposal.examId!==c.exam().id||proposal.revision!==c.exam().revision)throw Error('Nội dung đã đổi. Hãy yêu cầu một đề xuất mới.');return proposal;}
async function confirmOnServer(result){
 startStageTimer('Đang lưu đề xuất sửa…');
 try{
  await api('/api/exams/'+encodeURIComponent(result.examId)+'/edits/'+encodeURIComponent(result.confirmationId)+'/confirm',{});
  const fresh=await getWorkspace('state',{requireRemote:true});
  Object.assign(c.getState(),fresh);proposal=null;
  $('#dialog').close();advanceScopes(result.scopes);c.render();c.toast('Đã chấp nhận đề xuất · có thể bấm Hoàn tác để quay lại.');
 }catch(error){c.toast('Chưa đồng bộ đề xuất sửa. '+friendlyClientMessage(error));}
 finally{stopStageTimer();busy=false;stage='';refreshWorkbench();}
}
function showDiff(){
 const result=currentProposal(),e=c.exam(),current=blocksOf(e);
 const fieldNames={stem:'Đề bài',data:'Dữ kiện',explanation:'Lời giải',rubric:'Thang điểm',figure:'Hình vẽ',options:'Phương án',answer:'Đáp án trắc nghiệm',answerText:'Đáp án ngắn',truthValues:'Đáp án đúng–sai'};
 const touchedIds=new Set(result.edits.map(edit=>edit.questionId).filter(Boolean));
 const affectedLabels=[...new Set(result.edits.map(edit=>fieldNames[edit.field]||'Nội dung'))];
 const untouched=Math.max(0,e.questions.length-touchedIds.size);
 const summaryHTML=`<div class="diff-impact-summary" role="status"><b>Sửa ${touchedIds.size||result.edits.length} câu · Giữ nguyên ${untouched} câu còn lại</b><div class="diff-impact-pills">${affectedLabels.map(label=>`<span class="pill">${esc(label)}</span>`).join('')}</div></div>`;
 c.modal('Xem thay đổi trước khi áp dụng',`${summaryHTML}<div class="block-diffs">${result.edits.map(edit=>{const old=current.find(b=>b.id===edit.blockId);return `<article><b>Bài ${e.questions.findIndex(q=>q.id===edit.questionId)+1} · ${esc(fieldNames[edit.field]||'Nội dung')}</b><div class="diff diff-side-by-side"><div class="diff-col"><span class="diff-col-label">Bản gốc hiện tại</span><del>${diffContentHTML(edit.field,old?.content)}</del></div><div class="diff-col"><span class="diff-col-label">Đề xuất thay đổi</span><ins>${diffContentHTML(edit.field,edit.content)}</ins></div></div></article>`;}).join('')}</div><div class="modal-foot">${b('discard-block-patch','✕ Bỏ đề xuất')}${b('undo-from-diff','↶ Hoàn tác bước trước',`class="ghost"${e.undo?.length?'':' disabled'}`)}${b('apply-block-patch','✓ Chấp nhận đề xuất','class="primary"')}</div>`);
}
const WORKFLOW_LABELS={draft:'Dự thảo',approved:'Bản duyệt',printed:'Bản đã in'};
export function examLibrarySearchText(e){
 return stripVietnameseDiacritics([
  e?.title,e?.subject,e?.grade?'lop '+e.grade:'',e?.school,e?.department,e?.instructions,
  ...(e?.questions||[]).flatMap(q=>[q?.stem,q?.topic,q?.explanation,...(q?.options||[]),...(q?.rubric||[]).map(r=>r?.text)]),
 ].filter(Boolean).join(' '));
}
export function filterAndSortLibraryExams(exams,filters={}){
 const list=Array.isArray(exams)?[...exams]:[];
 const qTokens=stripVietnameseDiacritics(filters.q||'').split(/\s+/).filter(Boolean);
 const subj=stripVietnameseDiacritics(filters.subject||'');
 const grade=String(filters.grade??'').trim();
 const status=String(filters.status??'').trim();
 const filtered=list.filter(e=>{
  if(!e||typeof e!=='object')return false;
  if(subj&&stripVietnameseDiacritics(e.subject||'')!==subj)return false;
  if(grade&&String(e.grade??'').trim()!==grade)return false;
  if(status&&(e.workflowStatus||'draft')!==status)return false;
  if(qTokens.length){
   const hay=examLibrarySearchText(e);
   if(!qTokens.every(tok=>hay.includes(tok)))return false;
  }
  return true;
 });
 const sortBy=filters.sort||'updated';
 filtered.sort((a,b)=>{
  if(sortBy==='title')return String(a.title||'').localeCompare(String(b.title||''),'vi-VN');
  if(sortBy==='questions')return (b.questions?.length||0)-(a.questions?.length||0);
  return (Number(b.updated)||0)-(Number(a.updated)||0);
 });
 return filtered;
}
export function moveExamsToTrash(state,ids){
 const targetIds=new Set((ids||[]).filter(Boolean));
 if(!state||!targetIds.size)return 0;
 state.exams=Array.isArray(state.exams)?state.exams:[];
 state.trash=Array.isArray(state.trash)?state.trash:[];
 const moved=[];
 const kept=[];
 for(const item of state.exams){
  if(targetIds.has(item.id)){
   moved.push({...clone(item),deletedAt:Date.now()});
  }else kept.push(item);
 }
 if(!moved.length)return 0;
 state.exams=kept;
 if(!state.exams.length){
  const fallback=blank(moved[0]?.subject||'Toán',state.prefs||[]);
  state.exams.push(fallback);
  state.current=fallback.id;
 }else if(!state.exams.some(e=>e.id===state.current)){
  state.current=state.exams[0].id;
 }
 const seen=new Set(state.trash.map(t=>t.id));
 for(const m of moved){
  if(!seen.has(m.id)){state.trash.unshift(m);seen.add(m.id);}
 }
 return moved.length;
}
export function restoreExamsFromTrash(state,ids){
 const targetIds=new Set((ids||[]).filter(Boolean));
 if(!state||!targetIds.size)return 0;
 state.exams=Array.isArray(state.exams)?state.exams:[];
 state.trash=Array.isArray(state.trash)?state.trash:[];
 const restored=[];
 const remaining=[];
 for(const item of state.trash){
  if(targetIds.has(item.id)){
   const copy=clone(item);
   delete copy.deletedAt;
   copy.updated=Date.now();
   restored.push(copy);
  }else remaining.push(item);
 }
 if(!restored.length)return 0;
 state.trash=remaining;
 const existingIds=new Set(state.exams.map(e=>e.id));
 for(const item of restored){
  if(existingIds.has(item.id))item.id=uid();
  state.exams.push(item);
  existingIds.add(item.id);
 }
 return restored.length;
}
function selectedLibraryIds(){
 return [...document.querySelectorAll('.wb-library-select:checked')].map(n=>n.dataset.id).filter(Boolean);
}
function updateLibraryBatchBar(){
 const count=selectedLibraryIds().length;
 const label=$('#library-selected-count');if(label)label.textContent=count?`Đã chọn ${count} đề`:'Chưa chọn đề nào';
 document.querySelectorAll('[data-action="library-batch-duplicate"],[data-action="library-batch-export"],[data-action="library-batch-delete"],[data-action="library-batch-restore"],[data-action="library-batch-purge"]').forEach(btn=>btn.disabled=!count);
}
function renderLibraryCards(){
 const container=$('.wb-library');if(!container)return;
 const state=c.getState();
 const curId=c.exam()?.id;
 const filters={
  q:$('#library-filter')?.value||'',
  subject:$('#library-subject-filter')?.value||'',
  grade:$('#library-grade-filter')?.value||'',
  status:$('#library-status-filter')?.value||'',
  sort:$('#library-sort')?.value||'updated',
 };
 const prevSelected=new Set(selectedLibraryIds());
 const activeList=state.exams||[];
 const trashList=state.trash||[];
 const activeBadge=$('#library-tab-active-count');if(activeBadge)activeBadge.textContent=String(activeList.length);
 const trashBadge=$('#library-tab-trash-count');if(trashBadge)trashBadge.textContent=String(trashList.length);
 const sourceList=libraryTab==='trash'?trashList:activeList;
 const shown=filterAndSortLibraryExams(sourceList,filters);
 container.innerHTML=shown.map(e=>{
  const wf=e.workflowStatus||'draft';
  const wfLabel=WORKFLOW_LABELS[wf]||WORKFLOW_LABELS.draft;
  const actionButtons=libraryTab==='trash'
   ?`${b('restore-trashed-exam','Khôi phục',`class="primary" data-id="${esc(e.id)}"`)}${b('purge-trashed-exam','Xóa hẳn',`class="danger" data-id="${esc(e.id)}"`)}`
   :`${b('open-exam','Mở',`data-id="${esc(e.id)}"`)}${b('duplicate-exam','Nhân bản',`data-id="${esc(e.id)}"`)}${b('clone-exam-target','Cho lớp mới',`data-id="${esc(e.id)}"`)}${b('delete-exam','Xóa',`data-id="${esc(e.id)}" class="danger"`)}`;
  const dateLabel=libraryTab==='trash'&&e.deletedAt?'Đã xóa '+new Date(e.deletedAt).toLocaleDateString('vi-VN'):new Date(e.updated||Date.now()).toLocaleDateString('vi-VN');
  return `<article class="wb-library-card ${e.id===curId&&libraryTab!=='trash'?'is-current':''}" data-exam-id="${esc(e.id)}" data-search="${esc(examLibrarySearchText(e))}">
   <label class="wb-library-check"><input type="checkbox" class="wb-library-select" data-id="${esc(e.id)}" aria-label="Chọn đề ${esc(e.title)}" ${prevSelected.has(e.id)?'checked':''}></label>
   <div class="wb-library-info"><b>${esc(e.title)}${e.id===curId&&libraryTab!=='trash'?' <span class="pill wb-current-pill">Đang mở</span>':''} <span class="pill wb-wf-pill" data-wf="${esc(wf)}">${esc(wfLabel)}</span></b><small>${esc(e.subject)} ${esc(e.grade)} · ${e.questions.length} bài · ${dateLabel}</small></div>
   <div class="buttons">${actionButtons}</div>
  </article>`;
 }).join('');
 const status=$('#library-status');
 const emptyAll=libraryTab==='trash'?'Thùng rác hiện đang trống.':'Chưa có đề nào trong kho.';
 const message=shown.length?'':(sourceList.length?'Không tìm thấy đề phù hợp.':emptyAll);
 if(status&&status.textContent!==message)status.textContent=message;
 updateLibraryBatchBar();
}
function filterLibrary(){renderLibraryCards();}
function showLibrary(tab=libraryTab||'active'){
 libraryTab=tab==='trash'?'trash':'active';
 const state=c.getState();
 const activeExams=state.exams||[];
 const trashExams=state.trash||[];
 const allKnown=[...activeExams,...trashExams];
 const subjects=[...new Set(allKnown.map(e=>e.subject).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'vi-VN'));
 const grades=[...new Set(allKnown.map(e=>String(e.grade||'').trim()).filter(Boolean))].sort((a,b)=>Number(a)-Number(b));
 const batchButtons=libraryTab==='trash'
  ?`${b('library-batch-restore','Khôi phục bộ đã chọn','class="primary" disabled')}${b('library-batch-purge','Xóa hẳn bộ đã chọn','class="danger" disabled')}`
  :`${b('library-batch-duplicate','Nhân bản bộ đã chọn','disabled')}${b('library-batch-export','Tải JSON bộ đã chọn','disabled')}${b('library-batch-delete','Chuyển vào thùng rác','class="danger" disabled')}`;
 c.modal('Kho đề của tôi',`<div class="wb-library-toolbar"><input id="library-filter" aria-label="Tìm trong kho đề" placeholder="Tìm tên đề, môn, lớp, lời giải, câu hỏi (không dấu)…">${accountInfo?.sharedSnapshots?b('community-exams','Kho đề cộng đồng'):''}</div><div class="wb-library-tabs" role="tablist" aria-label="Phân loại kho đề"><button type="button" role="tab" aria-selected="${libraryTab==='active'}" class="${libraryTab==='active'?'active':''}" data-action="library-tab" data-tab="active">Đang sử dụng (<span id="library-tab-active-count">${activeExams.length}</span>)</button><button type="button" role="tab" aria-selected="${libraryTab==='trash'}" class="${libraryTab==='trash'?'active':''}" data-action="library-tab" data-tab="trash">Thùng rác (<span id="library-tab-trash-count">${trashExams.length}</span>)</button></div><div class="wb-library-filters"><select id="library-subject-filter" aria-label="Lọc theo môn"><option value="">Tất cả môn</option>${subjects.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join('')}</select><select id="library-grade-filter" aria-label="Lọc theo lớp"><option value="">Tất cả lớp</option>${grades.map(g=>`<option value="${esc(g)}">Lớp ${esc(g)}</option>`).join('')}</select><select id="library-status-filter" aria-label="Lọc trạng thái"><option value="">Tất cả trạng thái</option><option value="draft">Dự thảo</option><option value="approved">Bản duyệt</option><option value="printed">Bản đã in</option></select><select id="library-sort" aria-label="Sắp xếp đề"><option value="updated">Mới sửa nhất</option><option value="title">Tên A–Z</option><option value="questions">Nhiều câu nhất</option></select></div><div class="wb-library-batch">${b('library-select-all','Chọn tất cả')}<span id="library-selected-count">Chưa chọn đề nào</span>${batchButtons}</div><div class="wb-library"></div><div id="library-status" role="status"></div><div class="modal-foot">${b('backup','Tải bản sao toàn bộ')}${b('import-backup','Khôi phục bản sao JSON')}${b('new','Tạo đề mới','class="primary"')}</div>`);
 renderLibraryCards();
 const root=$('#dialog .modal-body');
 root?.addEventListener('change',ev=>{
  if(ev.target.classList.contains('wb-library-select'))updateLibraryBatchBar();
  else if(['library-subject-filter','library-grade-filter','library-status-filter','library-sort'].includes(ev.target.id))renderLibraryCards();
 });
}
function showAccount(){if(accountInfo?.localPoC&&!accountInfo?.user){c.modal('Dữ liệu trên máy',`<p>Các đề và tài liệu của thầy cô được lưu trực tiếp trên máy đang chạy ứng dụng.</p><p>Chọn Xuất đề → Sao lưu toàn bộ để giữ bản sao JSON dự phòng.</p>`);return;}const user=accountInfo?.user;c.modal(user?(accountInfo.online?'Tài khoản':'Tài khoản cục bộ'):'Đăng nhập / tạo tài khoản',user?`<p>${esc(user.name)} · ${esc(user.email)}</p><p>Đề và hội thoại của tài khoản này được lưu riêng trên ${accountInfo.teamMode?'máy chạy app':accountInfo.online?'máy chủ':'máy hiện tại'}.</p><div class="modal-foot">${accountInfo.teamMode&&accountInfo.admin?b('team-invite','Mời thành viên'):''}${b('logout','Đăng xuất')}</div>`:`<p>Tài khoản được lưu trên máy này. Mật khẩu được băm; đây chưa phải tài khoản cloud Supabase.</p><form id="account-form"><label>Họ tên (khi tạo mới)</label><input name="name" autocomplete="name"><label>Email</label><input name="email" type="email" required autocomplete="username"><label>Mật khẩu (ít nhất 10 ký tự khi tạo mới)</label><input name="password" type="password" required autocomplete="current-password"><div class="modal-foot"><button type="submit" name="mode" value="login">Đăng nhập</button><button type="submit" name="mode" value="register" class="primary">Tạo tài khoản</button></div></form>`);}
export function confirmSuggestedActionModalHTML(act,e){
 const preview=buildSuggestedActionPreview(act,e);
 if(preview.kind==='propose_questions'){
  const items=(preview.questions.length?preview.questions:[{stem:act.summary||act.title||'Câu hỏi đề xuất từ Trợ lý',type:'mcq',options:['Phương án A','Phương án B','Phương án C','Phương án D'],answer:0}]);
  return `<div class="chat-confirm-preview" data-kind="propose_questions"><p><b>Sẽ thêm ${items.length} câu hỏi mới vào cuối đề</b> (chưa lưu cho đến khi thầy cô bấm xác nhận bên dưới).</p><div class="chat-preview-list">${items.slice(0,5).map((item,i)=>`<article class="choice-card"><b>Câu đề xuất ${i+1} (${esc(item.type||'mcq')})</b><p>${richTextHTML(String(item.stem||''))}</p>${Array.isArray(item.options)&&item.options.length?`<small>${item.options.slice(0,4).map((o,oi)=>`${String.fromCharCode(65+oi)}. ${esc(o)}`).join(' · ')}</small>`:''}</article>`).join('')}${items.length>5?`<p class="hint">Và ${items.length-5} câu hỏi khác…</p>`:''}</div><div class="modal-foot">${b('close-top-modal','Hủy')}${b('confirm-chat-action','✓ Xác nhận thêm vào đề','class="primary"')}</div></div>`;
 }
 if(preview.kind==='propose_patch'){
  const q=preview.targetQ,p=preview.patch||{};
  const beforeStem=q?.stem||'',afterStem=(typeof p.stem==='string'&&p.stem.trim())?p.stem:(typeof p.replacement==='string'&&p.replacement.trim()?p.replacement:beforeStem);
  const beforeExpl=q?.explanation||'',afterExpl=(typeof p.explanation==='string'&&p.explanation.trim())?p.explanation:beforeExpl;
  return `<div class="chat-confirm-preview" data-kind="propose_patch"><p><b>Đề xuất chỉnh sửa Câu ${preview.ordinal}</b> — xem trước thay đổi trước khi áp dụng:</p><div class="diff diff-side-by-side"><div class="diff-col"><span class="diff-col-label">Hiện tại</span><div>${richTextHTML(beforeStem)}${beforeExpl?`<p class="hint">${richTextHTML(beforeExpl.slice(0,220))}</p>`:''}</div></div><div class="diff-col"><span class="diff-col-label">Sau khi áp dụng</span><div>${richTextHTML(afterStem)}${afterExpl?`<p class="hint">${richTextHTML(afterExpl.slice(0,220))}</p>`:''}</div></div></div><div class="modal-foot">${b('close-top-modal','Hủy')}${b('confirm-chat-action','✓ Xác nhận áp dụng bản sửa','class="primary"')}</div></div>`;
 }
 if(preview.kind==='propose_matrix'){
  const rows=preview.rows||[];
  return `<div class="chat-confirm-preview" data-kind="propose_matrix"><p><b>Đề xuất cập nhật Ma trận đề (${rows.length} dòng)</b> — bấm xác nhận để nạp vào ma trận và mở trình chỉnh ma trận:</p><table class="full-rubric-table"><thead><tr><th>Chủ đề</th><th>Số câu / tỉ trọng</th></tr></thead><tbody>${rows.slice(0,8).map(r=>`<tr><td>${esc(r.topic||r.name||'Chủ đề')}</td><td>${esc(String(r.count??r.total??r.points??''))}</td></tr>`).join('')}</tbody></table><div class="modal-foot">${b('close-top-modal','Hủy')}${b('confirm-chat-action','✓ Xác nhận nạp ma trận','class="primary"')}</div></div>`;
 }
 return `<div class="chat-confirm-preview"><p>${esc(preview.summary||'Xác nhận áp dụng đề xuất từ Trợ lý AI?')}</p><div class="modal-foot">${b('close-top-modal','Hủy')}${b('confirm-chat-action','✓ Xác nhận áp dụng','class="primary"')}</div></div>`;
}
export async function handleWorkbenchAction(action,node){if(busy&&!['toggle-ai','toggle-chat','credits','stop-ai','early-stop-ai','set-time-preset','copy-chat-msg'].includes(action)){c.toast('AI đang viết vào đề. Chờ hoàn tất để tránh xung đột.');return true;}switch(action){case 'copy-chat-msg':{const msg=c.exam().chat[Number(node.dataset.msgIndex)];const text=String(msg?.text||'');if(!text){c.toast('Không có nội dung để sao chép.');return true;}try{if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(text);else{const ta=document.createElement('textarea');ta.value=text;ta.setAttribute('readonly','');ta.style.position='fixed';ta.style.opacity='0';document.body.append(ta);ta.select();document.execCommand('copy');ta.remove();}const prev=node.textContent;node.textContent='✓ Đã chép';setTimeout(()=>{if(node.isConnected)node.textContent=prev;},1500);c.toast('Đã sao chép phản hồi trợ lý.');}catch{c.toast('Không thể tự sao chép. Hãy chọn văn bản và nhấn Ctrl+C.');}return true;}case 'set-time-preset':{applyTimePreset(node.dataset.preset||'standard');return true;}case 'early-stop-ai':{const jobId=activeJobId||c.exam()?.activeAIJob||'current';try{await api('/api/assistant/early-stop',{id:jobId});}catch{}c.toast('Đã yêu cầu chốt sớm các câu đã đạt kiểm tra');return true;}case 'apply-chat-questions':case 'apply-chat-patch':case 'apply-chat-matrix':{const e=c.exam(),msgIndex=Number(node.dataset.msgIndex),actionIndex=Number(node.dataset.actionIndex),msg=e.chat[msgIndex],act=msg?.suggestedActions?.[actionIndex];if(!act)return true;if(action==='apply-chat-patch'&&!e.questions?.length)throw Error('Chưa có câu hỏi trong đề để áp dụng bản sửa.');pendingChatAction={examId:e.id,msgIndex,actionIndex,kind:act.kind||''};c.modal('Xác nhận thay đổi từ Trợ lý AI',confirmSuggestedActionModalHTML(act,e));return true;}case 'confirm-chat-action':{const pending=pendingChatAction;if(!pending||pending.examId!==c.exam().id)throw Error('Đề xuất không còn hợp lệ.');const e=c.exam(),msg=e.chat[pending.msgIndex],act=msg?.suggestedActions?.[pending.actionIndex];if(!act)throw Error('Không tìm thấy đề xuất cần xác nhận.');pendingChatAction=null;const kind=act.kind||(pending.kind);if(kind==='propose_questions'){const rawList=Array.isArray(act.questions)&&act.questions.length?act.questions:Array.isArray(act.data?.questions)&&act.data.questions.length?act.data.questions:act.stem?[act]:[{stem:act.summary||act.title||msg?.text||'Câu hỏi đề xuất từ Trợ lý',type:'mcq',options:['Phương án A','Phương án B','Phương án C','Phương án D'],answer:0,explanation:'Giáo viên rà soát lại nội dung câu hỏi và đáp án.'}];c.change('Nhận câu hỏi từ Trợ lý chat',target=>{for(const item of rawList){const qType=['mcq','truefalse','short','essay'].includes(item.type)?item.type:'mcq';target.questions.push({id:uid(),v:1,type:qType,stem:String(item.stem||'Câu hỏi đề xuất từ Trợ lý'),options:Array.isArray(item.options)&&item.options.length?item.options.map(String):(['mcq','truefalse'].includes(qType)?['','','','']:[]),answer:Number.isInteger(item.answer)?item.answer:0,answerKnown:item.answerKnown??true,answerText:String(item.answerText||''),truthValues:Array.isArray(item.truthValues)?item.truthValues:[false,false,false,false],explanation:String(item.explanation||''),rubric:Array.isArray(item.rubric)?item.rubric:[],points:Number(item.points)||1,topic:String(item.topic||target.matrix?.[0]?.topic||'Chủ đề mới'),level:Number.isInteger(item.level)?item.level:1,source:item.source||null,check:null});}ensureBlocks(target);});act.appliedRevision=c.exam().revision;if(msg)msg.undoRevision=c.exam().revision;$('#dialog')?.close();await c.persist();c.render();c.toast('Đã xác nhận đưa câu hỏi vào đề · có thể bấm Hoàn tác.');return true;}if(kind==='propose_patch'){const patch=act.patch||act.question||act.data||act;const ord=Number(act.questionNumber||act.ordinal||patch.questionNumber||patch.ordinal||0);const targetQ=(act.questionId&&e.questions.find(q=>q.id===act.questionId))||(ord>=1&&e.questions[ord-1])||(c.getSelected?.()&&c.qget(c.getSelected()))||e.questions[0];if(!targetQ)throw Error('Chưa có câu hỏi trong đề để áp dụng bản sửa.');const qIndex=e.questions.indexOf(targetQ)+1;c.change('Áp dụng bản sửa Câu '+qIndex+' từ Trợ lý chat',target=>{const q=target.questions.find(item=>item.id===targetQ.id);if(!q)return;if(typeof patch.stem==='string'&&patch.stem.trim()){q.stem=patch.stem;q.richDoc=null;q.runs=null;}else if(typeof patch.replacement==='string'&&patch.replacement.trim()){q.stem=patch.replacement;q.richDoc=null;q.runs=null;}if(Array.isArray(patch.options)&&patch.options.length){q.options=patch.options.map(String);q.optionDocs=null;}if(Number.isInteger(patch.answer))q.answer=patch.answer;if(typeof patch.answerText==='string')q.answerText=patch.answerText;if(Array.isArray(patch.truthValues))q.truthValues=patch.truthValues.map(Boolean);if(typeof patch.explanation==='string'&&patch.explanation.trim()){q.explanation=patch.explanation;q.explanationDoc=null;}if(Array.isArray(patch.rubric))q.rubric=patch.rubric;touch(q);ensureBlocks(target);});act.appliedRevision=c.exam().revision;if(msg)msg.undoRevision=c.exam().revision;$('#dialog')?.close();await c.persist();c.render();c.toast(`Đã áp dụng bản sửa Câu ${qIndex} · có thể bấm Hoàn tác.`);return true;}if(kind==='propose_matrix'){const rows=Array.isArray(act.matrix)&&act.matrix.length?act.matrix:Array.isArray(act.rows)&&act.rows.length?act.rows:Array.isArray(act.data?.matrix)&&act.data.matrix.length?act.data.matrix:e.matrix;c.change('Nạp ma trận đề xuất từ Trợ lý chat',target=>{if(Array.isArray(rows)&&rows.length)target.matrix=clone(rows);target.matrixConfirmed=false;});act.appliedRevision=c.exam().revision;if(msg)msg.undoRevision=c.exam().revision;$('#dialog')?.close();await c.persist();if(typeof c.showMatrix==='function')c.showMatrix();else await c.act('matrix');return true;}return true;}case 'chat-followup':{const prompt=node.dataset.prompt||'',input=$('#chat-input');if(input){input.value=prompt;drafts.set(c.exam().id,prompt);input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();}return true;}case 'chat-consent-send':{const e=c.exam();e.aiConsent=true;e.chat=(e.chat||[]).filter(m=>!m?.needsAIConsent);const consent=$('#ai-consent');if(consent)consent.checked=true;const input=$('#chat-input');if(input&&!input.value.trim()&&drafts.get(e.id))input.value=drafts.get(e.id);await c.persist();refreshWorkbench();$('#chat-form')?.requestSubmit();return true;}case 'stop-ai':{if(chatController){chatController.abort(Error('Đã dừng yêu cầu trả lời.'));return true;}if(patchController){patchController.abort(Error('Đã dừng chờ đề xuất sửa. Bạn có thể gửi lại yêu cầu.'));return true;}if(writeController){cancelRequested=true;if(activeJobId)await api('/api/assistant/cancel',{id:activeJobId});writeController.abort();}return true;}case 'load-reference-exam':case 'load-ai-demo':{const demo=await api(action==='load-reference-exam'?'/assets/reference-exam.json':'/assets/demo-ai-exam.json');const e=blank(demo.subject,c.getState().prefs);Object.assign(e,{title:demo.title,grade:demo.grade,minutes:demo.minutes,questions:demo.questions,instructions:demo.instructions||'Thí sinh trình bày lời giải cho từng bài. Các phương trình được xét trên tập số thực.',fullExam:true,sample:true,chat:[{role:'assistant',text:demo.note}],layout:{font:'Times New Roman',fontSize:15}});ensureBlocks(e);c.getState().exams.push(e);c.getState().current=e.id;c.setTab('outline');await c.persist();c.render();return true;}case 'template-frame':{const e=blank('Toán',c.getState().prefs);e.title='Đề '+node.dataset.period+' — Toán 9';e.grade='9';e.minutes=Number(node.dataset.minutes);e.fullExam=true;e.instructions='Thí sinh trình bày lời giải cho từng bài.';e.layout={font:'Times New Roman',fontSize:15};e.chat=[];e.questions=['Biểu thức và phương trình','Hàm số','Bài toán thực tế','Hình học','Xác suất'].map(topic=>({id:uid(),v:1,type:'essay',stem:'Nhập nội dung bài '+topic.toLocaleLowerCase('vi-VN')+'…',points:2,options:[],answer:0,explanation:'',rubric:[],topic,level:1,source:null}));ensureBlocks(e);c.getState().exams.push(e);c.getState().current=e.id;c.setTab('outline');await c.persist();c.render();return true;}case 'local-poc-sample':{const sample=await api('/api/poc/sample');const e=blank(sample.subject,[]);e.title='Đề mẫu '+sample.subject+' · Ngữ liệu tự viết';e.aiInstructions=sample.instructions||'';e.grade=sample.grade;e.matrix=sample.matrix;e.matrixConfirmed=true;const id=uid();e.docs=[{id,name:'Ngữ liệu '+sample.subject+' · Nhóm tự viết',kind:'text',version:1,text:sample.text,pages:[{number:1,text:sample.text}]}];e.assistantSources=[id];c.getState().exams.push(e);c.getState().current=e.id;await c.persist();c.render();await openMatrixChat(c);return true;}case 'local-matrix':await openMatrixChat(c);return true;case 'generate':if(accountInfo?.localPoC){await openMatrixChat(c);return true;}openAI();$('#chat-input').value='Soạn đề Toán lớp 9 tuyển sinh, 5 bài tự luận, có hình và barem.';drafts.set(c.exam().id,$('#chat-input').value);$('#chat-input').focus();return true;case 'ask-selection':{const scope=c.currentScope();if(scope){scopes=[refreshScope(c.exam(),scope)];contextMuted=false;}$('.selection-ask')?.remove();openAI();paintScopes();$('#chat-input').focus();return true;}case 'ask-formula-ai':{const scope=scopeForFormula(node.dataset.editorKey||node.dataset.id,node.dataset.latex,node.dataset.pos);if(!scope)throw Error('Chọn lại công thức trong nội dung để hỏi AI.');scopes=[scope];contextMuted=false;closeFloating();openAI();paintScopes();$('#chat-input').focus();return true;}case 'remove-context':{if(scopes.length)scopes.splice(Number(node.dataset.index),1);if(!scopes.length)clearContext();else paintScopes();return true;}case 'discard-block-patch':{const discarded=proposal;proposal=null;$('#dialog').close();refreshWorkbench();if(accountInfo?.localPoC&&discarded?.confirmationId)await api('/api/exams/'+encodeURIComponent(discarded.examId)+'/edits/'+encodeURIComponent(discarded.confirmationId)+'/discard',{});return true;}case 'approve-plan':await writePlan();return true;case 'reject-plan':{const plan=c.exam().aiPlan;c.modal('Chỉnh phương án đề',`<form id="revise-plan-form"><label>Yêu cầu cấu trúc mới</label><textarea name="text" rows="4">${esc(plan.request)}</textarea><div class="modal-foot"><button class="primary" type="submit">Đề xuất lại cấu trúc</button></div></form>`);return true;}case 'show-block-diff':showDiff();return true;case 'apply-block-patch':{const result=currentProposal(),exam=c.exam();if(accountInfo?.localPoC&&result.confirmationId){await confirmOnServer(result);return true;}applyEdits(clone(exam),result.edits,{richTransform:reconcileEditorRich});proposal=null;c.change('AI sửa các block được chọn và phần phụ thuộc',e=>applyEdits(e,result.edits,{richTransform:reconcileEditorRich}));const revision=exam.revision;$('#dialog').close();advanceScopes(result.scopes);refreshWorkbench();c.toast('Đã chấp nhận đề xuất · có thể bấm Hoàn tác để quay lại.');try{await c.persist();}catch(error){c.toast('Chưa đồng bộ đề xuất sửa. '+friendlyClientMessage(error));return true;}if(c.exam()===exam)addMessage('assistant',result.message,{undoRevision:revision});return true;}case 'undo-from-diff':proposal=null;$('#dialog').close();await c.act('undo');return true;case 'undo-ai':if(c.exam().revision!==Number(node.dataset.revision))throw Error('Đề đã có thay đổi mới hơn. Mở Lịch sử để chọn phiên bản cần khôi phục.');await c.act('undo');return true;case 'recover-ai':{(c.getState().seenAIJobs??=[]).push(recovery.id);const e=clone(c.exam());e.id=uid();e.title=recovery.plan.title+' — Khôi phục';e.subject=recovery.plan.subject;e.grade=recovery.plan.grade;e.minutes=recovery.plan.minutes;e.questions=recovery.questions;e.fullExam=true;e.sample=false;e.aiPlan=null;e.aiClarification=null;e.instructions='Đề gồm '+recovery.questions.length+' câu/bài, tổng 10 điểm.';e.history=[];e.undo=[];e.redo=[];e.revision=1;e.chat=[];e.activeAIJob=null;c.getState().exams.push(e);c.getState().current=e.id;recovery=null;await c.persist();c.render();return true;}case 'library':showLibrary('active');return true;case 'library-tab':showLibrary(node.dataset.tab||'active');return true;case 'duplicate-exam':{const original=c.getState().exams.find(e=>e.id===node.dataset.id),copy=duplicateExam(original);c.getState().exams.push(copy);await c.persist();showLibrary();return true;}case 'clone-exam-target':{const original=c.getState().exams.find(e=>e.id===node.dataset.id);if(!original)throw Error('Không tìm thấy đề cần nhân bản.');c.modal('Nhân bản cho lớp / năm mới',`<form id="clone-exam-target-form" data-id="${esc(original.id)}"><label>Tên đề mới</label><input name="title" value="${esc(original.title)}" required maxlength="180"><div class="grid2"><div><label>Lớp mới</label><input name="grade" value="${esc(original.grade||'')}" required maxlength="40" placeholder="Ví dụ: 9A hoặc 10"></div><div><label>Năm học / đợt thi</label><input name="schoolYear" value="" maxlength="40" placeholder="Ví dụ: 2026–2027"></div></div><div class="modal-foot">${b('library','Quay lại kho đề')}<button class="primary" type="submit">Tạo bản sao &amp; mở đề</button></div></form>`);return true;}case 'library-select-all':{const boxes=[...document.querySelectorAll('.wb-library-select')];const allChecked=boxes.length>0&&boxes.every(x=>x.checked);boxes.forEach(x=>x.checked=!allChecked);updateLibraryBatchBar();return true;}case 'library-batch-duplicate':{const ids=selectedLibraryIds();if(!ids.length)return true;let copied=0;for(const id of ids){const orig=c.getState().exams.find(e=>e.id===id);if(!orig)continue;c.getState().exams.push(duplicateExam(orig));copied++;}await c.persist();showLibrary();c.toast(`Đã nhân bản ${copied} đề.`);return true;}case 'library-batch-export':{const ids=new Set(selectedLibraryIds());const chosen=(c.getState().exams||[]).filter(e=>ids.has(e.id));if(!chosen.length)return true;const payload={format:'tro-ly-soan-de-batch',version:1,savedAt:new Date().toISOString(),exams:clone(chosen)};const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const a=Object.assign(document.createElement('a'),{href:URL.createObjectURL(blob),download:'Bo-de-da-chon.json'});a.click();URL.revokeObjectURL(a.href);c.toast(`Đã tải JSON ${chosen.length} đề.`);return true;}case 'library-batch-delete':{const ids=selectedLibraryIds();if(!ids.length)return true;const moved=moveExamsToTrash(c.getState(),ids);await c.persist();c.render();showLibrary('active');c.toast(`Đã chuyển ${moved} đề vào thùng rác.`);return true;}case 'restore-trashed-exam':{const count=restoreExamsFromTrash(c.getState(),[node.dataset.id]);if(count){await c.persist();showLibrary('trash');c.toast('Đã khôi phục đề về Kho đề.');}return true;}case 'library-batch-restore':{const ids=selectedLibraryIds();const count=restoreExamsFromTrash(c.getState(),ids);if(count){await c.persist();showLibrary('trash');c.toast(`Đã khôi phục ${count} đề về Kho đề.`);}return true;}case 'purge-trashed-exam':{const state=c.getState();state.trash=(state.trash||[]).filter(t=>t.id!==node.dataset.id);await c.persist();showLibrary('trash');c.toast('Đã xóa hẳn khỏi thùng rác.');return true;}case 'library-batch-purge':{const ids=new Set(selectedLibraryIds());if(!ids.size)return true;const state=c.getState();const before=(state.trash||[]).length;state.trash=(state.trash||[]).filter(t=>!ids.has(t.id));await c.persist();showLibrary('trash');c.toast(`Đã xóa hẳn ${before-state.trash.length} đề khỏi thùng rác.`);return true;}case 'team-invite':c.modal('Mời thành viên',`<form id="team-invite-form"><p>Lời mời dùng một lần trong 24 giờ, chỉ dành cho email này.</p><label>Email thành viên<input name="email" type="email" required maxlength="254" autocomplete="off"></label><div class="modal-foot"><button class="primary" type="submit">Tạo lời mời</button></div></form>`);return true;case 'account':showAccount();return true;case 'logout':await api('/api/account/logout',{});location.reload();return true;case 'credits':c.modal('Hạn mức sử dụng AI',`<p><b>${accountInfo?.credits?.balance??1000} lượt quy đổi</b> còn lại.</p><p>Đây là hạn mức dùng thử tại máy để ước lượng chi phí, không phải tiền và không phải số dư API nhà cung cấp.</p><div class="credit-ledger">${(accountInfo?.credits?.ledger||[]).slice(-10).reverse().map(r=>`<p>${r.delta>0?'+':''}${r.delta} · ${esc(r.reason)}</p>`).join('')}</div>`);return true;case 'community-exams':captureAssistantSourceDraft($('#assistant-source-form'),c.exam()?.id);await openCommunity(c,api);return true;case 'community-clone':await cloneCommunityExam(c,api,node);return true;case 'community-source':await attachCommunitySource(c,api,node);return true;case 'share':await openSharing(c,api,accountInfo||{});return true;case 'copy-share':{try{await navigator.clipboard.writeText(node.dataset.url||$('#share-url').value);c.toast('Đã sao chép liên kết.');}catch{(node.closest('.shared-link-row')?.querySelector('input')||$('#share-url'))?.select();c.toast('Nhấn Ctrl+C để sao chép.');}return true;}case 'revoke-share':await api('/api/share/revoke',{token:node.dataset.token});await openSharing(c,api,accountInfo||{});c.toast('Đã thu hồi liên kết.');return true;case 'geometry':case 'edit-figure':{const q=c.qget(node.dataset.id||c.getSelected());if(!q)throw Error('Chọn một bài để chèn hình.');c.modal('Sửa hình từ mô tả tọa độ',`<form id="figure-form" data-id="${q.id}" data-version="${q.v}"><p>Bộ tính dựng trung điểm, chân đường vuông góc, giao điểm, tâm ngoại tiếp và trực tâm. Không nhận mã SVG tự do.</p><textarea id="figure-spec" name="spec" rows="11" spellcheck="false">${esc(JSON.stringify(q.figure||triangleFigure(),null,2))}</textarea><p id="figure-error" role="alert"></p><div id="figure-preview">${renderFigure(q.figure||triangleFigure())}</div><label>Độ rộng hình (px)</label><input name="width" type="number" min="180" max="700" value="${q.figure?.width||480}"><div class="modal-foot"><button class="primary" type="submit">Lưu hình</button></div></form>`);return true;}case 'scroll-marking':document.getElementById(node.dataset.target||'marking-guide')?.scrollIntoView({block:'start',behavior:'smooth'});return true;default:return false;}}
export async function handleWorkbenchSubmit(form){if(form.id==='chat-form'){const text=$('#chat-input').value.trim();if(!text||busy||matrixChatRunning(c))return true;if(!flushEditor()){c.toast('Gõ xong chữ đang nhập rồi thử lại.');return true;}const e=c.exam(),examId=e.id,mode=$('#chat-mode')?.value||e.aiChatMode||'auto',context=activeScopes(),isLocalPoC=!!accountInfo?.localPoC;const pureMatrix=text.length<40&&!/\?/.test(text)&&(isMatrixRequest(text)||/^(?:mở|lập)\s+ma\s*trận(?:\s+(?:đề|này|mới))?[.!\s]*$/iu.test(text.normalize('NFC')));const pureCreate=!/\?/.test(text)&&intentOf(text,context)==='create';e.aiConsent=!!$('#ai-consent')?.checked;e.aiChatMode=mode;if(!e.aiConsent&&!(isLocalPoC&&mode==='auto'&&(pureMatrix||pureCreate))){drafts.set(examId,text);if(!e.chat.at(-1)?.needsAIConsent)addMessage('assistant','Cho phép gửi yêu cầu và phần nội dung đang chọn đến kết nối AI đã cấu hình để tiếp tục.',{needsAIConsent:true});else focusConsentCard();return true;}drafts.set(examId,'');$('#chat-input').value='';addMessage('user',text);let success=false;try{if(isLocalPoC&&mode==='auto'&&pureMatrix){await openMatrixChat(c);success=true;return true;}if(e.aiPlan&&/^(?:có|đồng ý|ok|được|yes)[.!\s]*$/iu.test(text)){await writePlan();success=true;return true;}const inferred=intentOf(text,context),intent=mode==='ask'?'explain':mode==='edit'?'edit':inferred;if(mode==='auto'&&(e.aiClarification||pureCreate)){await planRequest(text);success=true;return true;}const shouldPatch=mode==='edit'||((intent==='edit'||intent==='verify')&&(context.length>0||!isLocalPoC||(e.questions.length>0&&/(?:bài|câu)\s*\d/iu.test(text))));if(shouldPatch)await requestEdit(text,intent);else{const chatStartedAt=Date.now();const controller=new AbortController();chatController=controller;startStageTimer('Đang kết nối luồng trả lời AI…');let chosen=context;if(/(?:bài|câu)\s*\d|toàn bộ đề|cả đề/iu.test(text)){try{chosen=requestScopes(e,text,{scopes:context,muted:contextMuted});}catch{chosen=context;}}const selected=contextForScopes(e,chosen);const history=e.chat.slice(0,-1).slice(-6).map(m=>({role:m.role,text:String(m.text).slice(0,1200)}));const chatContext=buildFlexibleChatContext(e,selected,history);streamingState={examId,text:'',provider:'',model:''};refreshWorkbench();let streamQueued=false;const scheduleStreamPaint=()=>{if(streamQueued)return;streamQueued=true;const sched=typeof requestAnimationFrame==='function'?requestAnimationFrame:fn=>setTimeout(fn,16);sched(()=>{streamQueued=false;if(streamingState?.examId===examId)refreshWorkbench();});};const result=await streamAssistantChat({text,effort:e.aiEffort??1,timePreset:e.aiTimePreset||'standard',teacherFilesOnly:Boolean(e.strictTeacherOnly),context:chatContext,consent:e.aiConsent},{signal:controller.signal,onMeta:meta=>{if(streamingState&&streamingState.examId===examId){streamingState.provider=meta.provider||meta.providerUsed||'';streamingState.model=meta.model||'';scheduleStreamPaint();}},onDelta:delta=>{if(streamingState&&streamingState.examId===examId){streamingState.text+=delta;scheduleStreamPaint();}}});controller.signal.throwIfAborted();if(c.exam().id!==examId)throw Error('Đã đổi đề trong lúc chờ trả lời.');const measuredMs=Math.max(0,Date.now()-chatStartedAt);const latencyMs=Number.isFinite(Number(result.latencyMs))&&Number(result.latencyMs)>0?Number(result.latencyMs):(measuredMs>=100?measuredMs:0);const streamedProvider=streamingState?.provider||'';streamingState=null;stopStageTimer();chatController=null;busy=false;addMessage('assistant',result.message,{providerUsed:result.providerUsed||streamedProvider||'',fallbackFrom:result.fallbackFrom||'',fallbackReason:result.fallbackReason||'',attemptedProviders:Array.isArray(result.attemptedProviders)?result.attemptedProviders:[],latencyMs,suggestedActions:result.suggestedActions||[],followUps:result.followUps||[]});accountInfo={...accountInfo,credits:result.credits};}success=true;}catch(error){const stopped=error?.name==='AbortError'||/Đã dừng/.test(String(error?.message||''));streamingState=null;stopStageTimer();chatController=null;busy=false;addMessage('assistant',stopped?'Đã dừng yêu cầu trả lời.':friendlyClientMessage(error));}finally{if(!success){drafts.set(examId,text);if(c.exam().id===examId&&$('#chat-input')&&!$('#chat-input').value)$('#chat-input').value=text;}streamingState=null;stopStageTimer();chatController=null;busy=false;stage='';refreshWorkbench();await refreshAccount();}return true;}
 if(form.id==='clone-exam-target-form'){const orig=c.getState().exams.find(e=>e.id===form.dataset.id);if(!orig)throw Error('Không tìm thấy đề gốc để nhân bản.');const fd=new FormData(form),copy=duplicateExam(orig);const rawTitle=String(fd.get('title')||'').trim(),grade=String(fd.get('grade')||'').trim(),yr=String(fd.get('schoolYear')||'').trim();if(!rawTitle)throw Error('Tên đề mới không được để trống.');copy.title=rawTitle+(yr?' ('+yr+')':'');if(grade)copy.grade=grade;c.getState().exams.push(copy);c.getState().current=copy.id;await c.persist();$('#dialog').close();c.render();c.toast('Đã nhân bản đề cho lớp/năm mới.');return true;}
 if(form.id==='revise-plan-form'){const text=new FormData(form).get('text');$('#dialog').close();c.exam().aiClarification={request:c.exam().aiPlan?.request||''};await planRequest(text);return true;}if(form.id==='team-invite-form'){const result=await api('/api/account/invitations',Object.fromEntries(new FormData(form)));const url=location.origin+'/login#invite='+encodeURIComponent(result.inviteCode);c.modal('Lời mời đã tạo',`<p>Gửi liên kết này riêng cho ${esc(result.email)}. Liên kết có hiệu lực 24 giờ và dùng một lần.</p><label>Liên kết nhận lời mời<input readonly value="${esc(url)}" aria-label="Liên kết nhận lời mời"></label><p>Chế độ này chạy tại máy. Người nhận cần truy cập đúng máy đang chạy app.</p>`);return true;}if(form.id==='account-form'){const fd=new FormData(form),mode=form.__submitter?.value||'login';await api('/api/account/'+mode,Object.fromEntries(fd));location.reload();return true;}if(form.id==='share-form'){await createSharing(c,api,form);return true;}if(form.id==='figure-form'){const q=c.qget(form.dataset.id);if(q.v!==Number(form.dataset.version))throw Error('Bài đã đổi, mở lại hình để sửa.');const fd=new FormData(form);let spec;try{spec=JSON.parse(fd.get('spec'));}catch{throw Error('Mô tả hình chưa hợp lệ. Kiểm tra dấu ngoặc và dấu phẩy theo mẫu JSON.');}spec.width=Number(fd.get('width'));solveFigure(spec);c.change('Sửa hình bằng bộ dựng tọa độ',()=>{q.figure=spec;touch(q);});$('#dialog').close();return true;}return false;}
if(typeof document!=='undefined')document.addEventListener('submit',event=>{event.target.__submitter=event.submitter;},true);

export function accountSaveLabel(){return accountInfo?.user?'Đã lưu vào tài khoản':'Đã lưu trên máy';}

export function friendlyClientMessage(error){const text=String(error?.message||error||'');if(/fetch|network|ECONN|Unexpected|Expected|JSON|TypeError|invalid_|timeout/i.test(text))return 'Kết nối hoặc dữ liệu vừa nhận chưa hợp lệ. Nội dung của bạn vẫn được giữ; hãy thử lại nhé.';return text||'Mình chưa hoàn tất được tác vụ. Bạn thử lại nhé.';}

export function scheduleAutoReconcile(q){if(!c||!c.exam().fullExam||c.exam().autoUpdate!==true||!c.exam().aiConsent||!q.explanation)return;const examId=c.exam().id,version=q.v;clearTimeout(autoTimers.get(q.id));const run=async()=>{if(c.exam().id!==examId||c.exam().autoUpdate!==true||c.qget(q.id)?.v!==version)return;if(busy||proposal||document.querySelector('dialog')?.open){autoTimers.set(q.id,setTimeout(run,3000));return;}const scope={id:q.id,version:q.v,field:'stem',start:0,end:q.stem.length,text:q.stem,blockId:q.blockIds.stem};try{await requestEdit('Cập nhật lời giải, barem và hình liên quan theo nội dung hiện tại vừa được sửa tay. Giữ nguyên đề bài và điểm bài.', 'verify',[scope],true);}catch(error){addMessage('assistant','Mình chưa tự đồng bộ được bài vừa sửa: '+friendlyClientMessage(error));}finally{autoTimers.delete(q.id);}};autoTimers.set(q.id,setTimeout(run,4000));}

async function watchJob(jobId){if(!c||busy||accountInfo?.localPoC)return;const examId=c.exam().id;const read=async()=>{if(!c||c.exam().id!==examId)return;try{const job=await api('/api/assistant/job?'+(jobId?'id='+encodeURIComponent(jobId):'examId='+encodeURIComponent(examId)));if(c.getState().seenAIJobs?.includes(job.id))return;watchedJob=job.id;if(job.status==='complete'){recovery=job;refreshWorkbench();return;}if(job.status==='failed'){(c.getState().seenAIJobs??=[]).push(job.id);c.exam().activeAIJob=null;addMessage('assistant',job.error||'Lần soạn trên server chưa hoàn tất. Đề trước đó được giữ lại.');return;}recovery=job;refreshWorkbench();jobTimer=setTimeout(read,4000);}catch{}};if(jobId&&watchedJob===jobId&&jobTimer)return;await read();}
