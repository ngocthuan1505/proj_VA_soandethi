import {flushEditor,hasPendingEditorChanges,reconcileEditorRich} from './editor.js';
import {richTextHTML,validateMath} from './math-content.js';
import {mountStudio,refreshStudio,handleStudioAction,handleStudioSubmit} from './studio.js';
import {openMatrixChat as openMatrixSynthesis,mountMatrixChat,reverseMatrixWarningBannerHTML,rowFlagForReverseReport,getReverseMatrixReport,clearReverseMatrixReport,requestReverseMatrix} from './matrix-chat.js';
import {bootstrapWorkbench,scheduleAutoReconcile,friendlyClientMessage,accountSaveLabel,initWorkbench,mountWorkbench,refreshWorkbench,handleWorkbenchAction,handleWorkbenchSubmit} from './workbench.js';
import {ensureBlocks,questionScope} from './blocks.js';
import {referenceSide,referenceChat,rubricHTML,refreshReferenceScope,closeFloating,questionQuickActionsHTML,duplicateQuestionInExam,moveQuestionInExam,toggleQuestionApprovalInExam,setQuestionMcqAnswer,buildAudioAttachmentMeta,audioAttachmentCardHTML,emptyCanvasHTML} from './reference.js';
import {mountMVP,initMVP,handleMVPAction,handleMVPSubmit,WORKFLOW_STATUS_LABELS,normalizeWorkflowStatus} from './mvp.js';
import {mountVipTools,handleVipAction} from './vip-tools.js';
import {mountExamRooms,handleExamRoomAction,handleExamRoomSubmit} from './exam-rooms.js';
import {mountDesign,setActiveWorkspaceNav} from './design.js';
import {renderHomeViewHTML,mountHomeView,refreshProactiveUI,handleHomeAction,handleHomeSubmit} from './home.js';
import {mountVoiceButton} from './voice-input.js';
import {citationContextHTML} from './citation-context.js';
import {approveQuestion,isApproved,isConfirmedPreference,filterPrefsForExam,rebalanceMatrixRowsToTen,LEVELS,clone,uid,esc,sample,blank,commit,commitTyping,undo,redo,touch,derive,check,planDataUpdate,matrix,exportHTML,snapshot,usesTable,dataChartSVG,QUESTION_TYPES,validateMatrixRows} from './core.js';
import * as db from './storage.js';
const paths={home:'M3 10.5L12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',bell:'M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0',search:'M21 21l-5-5 M10 3a7 7 0 1 0 0 14a7 7 0 0 0 0-14',print:'M6 9V3h12v6 M6 18H3V9h18v9h-3 M6 14h12v8H6z M17 12h1',image:'M4 5h16v15H4z M4 16l5-5 5 5 3-3 3 3 M8 8h1',paperclip:'M9 13l6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l8-8 M7 15l8-8',chemistry:'M9 3h6 M10 3v7L5 19q-1 2 2 2h10q3 0 2-2l-5-9V3 M8 15h8',globe:'M21 12a9 9 0 1 1-18 0a9 9 0 0 1 18 0 M3 12h18 M12 3c-5 5-5 13 0 18c5-5 5-13 0-18',book:'M4 4h6c2 0 2 2 2 2s0-2 2-2h6v15h-6c-2 0-2 1-2 1s0-1-2-1H4z M12 6v14',plus:'M12 5v14 M5 12h14',folder:'M3 6h7l2 3h9v11H3z',save:'M4 3h13l3 3v15H4z M8 3v6h8V3 M8 21v-7h8v7',download:'M12 3v12 M7 10l5 5 5-5 M4 17v4h16v-4',undo:'M8 4L3 9l5 5 M3 9h10a7 7 0 0 1 0 14',redo:'M16 4l5 5-5 5 M21 9h-10a7 7 0 0 0 0 14',spark:'M12 3l2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3z',check:'M4 12l5 5L20 6',alert:'M12 3l10 18H2z M12 9v5 M12 17v1',link:'M9 15l6-6 M8 17H6a4 4 0 0 1 0-8h4 M14 7h4a4 4 0 0 1 0 8h-4',file:'M5 2h9l5 5v15H5z M14 2v6h5 M8 12h8 M8 16h8',grid:'M3 3h18v18H3z M9 3v18 M15 3v18 M3 9h18 M3 15h18',clock:'M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18 M12 7v5l4 2',settings:'M4 7h16 M4 17h16 M8 4v6 M16 14v6',close:'M6 6l12 12 M18 6L6 18',arrow:'M5 12h14 M14 7l5 5-5 5',send:'M12 20V4 M5 11l7-7 7 7',trash:'M4 6h16 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7',chat:'M3 3h18v14H8l-5 4z',list:'M8 6h13 M8 12h13 M8 18h13 M3 6h1 M3 12h1 M3 18h1',memory:'M12 3a7 7 0 0 0-5 12v4h10v-4A7 7 0 0 0 12 3 M9 22h6 M10 10l2 2 3-3',eye:'M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12 M12 9a3 3 0 1 0 0 6a3 3 0 0 0 0-6',edit:'M4 16L16 4l4 4L8 20H4z M13 7l4 4'};
const icon=n=>`<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[n]||paths.file}"/></svg>`;
const $=s=>document.querySelector(s);
let inlineTimer;
let state,tab='outline',selected=null,selection=null,teacher=false,assistantOpen=false,sidebarOpen=false,saveChain=Promise.resolve(),pending=null,toastTimer,activeRailNav='design-workspace',viewMode='workspace',lastDigestFetchAt=0;
function detectInitialViewMode(){const p=location.pathname.replace(/\/+$/,''),q=new URLSearchParams(location.search);return p==='/home'||q.get('view')==='home'||location.hash==='#home'?'home':'workspace';}
function syncHomeUrl(mode){if(typeof location==='undefined'||!location?.href||typeof history?.replaceState!=='function')return;const url=new URL(location.href);if(mode==='home'){url.hash='home';}else{if(url.pathname.replace(/\/+$/,'')==='/home')url.pathname='/';if(url.searchParams.get('view')==='home')url.searchParams.delete('view');if(url.hash==='#home')url.hash='';}const next=url.pathname+url.search+url.hash;if(next!==location.pathname+location.search+location.hash)history.replaceState({},'',next);}
function ensureWorkspaceVoiceButton(){
 const form=$('#chat-form'),bottom=form?.querySelector('.compose-bottom'),input=$('#chat-input');
 if(!bottom||!input)return;
 const submitBtn=bottom.querySelector('button[type="submit"]');
 mountVoiceButton(bottom,{targetInput:input,insertBefore:submitBtn,lang:'vi-VN',onNotify:toast});
}
const app=$('#app'),dialog=$('#dialog'),dialogLayer2=$('#dialog-layer2');
const exam=()=>state.exams.find(e=>e.id===state.current);
const qget=id=>exam().questions.find(q=>q.id===id);
const sourceWarningText=(q,e)=>{
 if(Array.isArray(q?.evidence)&&q.evidence.some(ev=>ev?.stale))return 'Ngữ liệu đã đổi · cần đối chiếu';
 const docId=q?.source?.docId;
 if(!docId||!e?.docs)return '';
 const doc=e.docs.find(d=>d.id===docId);
 if(!doc)return 'Nguồn đã gỡ';
 const docVer=Number(doc.version||1);
 const parsedSrcVer=Number(q.source?.version);
 const srcVer=Number.isFinite(parsedSrcVer)&&parsedSrcVer>=1?parsedSrcVer:1;
 if(srcVer!==docVer)return `Nguồn đổi v${srcVer}→v${docVer}`;
 return '';
};
const statusText=(q,e=state?exam():null)=>{
 const srcWarn=sourceWarningText(q,e);
 const reviewTag=q?.needsReview&&!(q.check?.version===q.v&&q.check.status==='review')?'Cần rà soát':'';
 return [isApproved(q)?'Giáo viên đã duyệt':'',srcWarn,reviewTag,q.check?.version===q.v?({review:'Cần xem lại',consistent:'Chưa thấy bất đồng trong lần kiểm',unverified:'Chưa giải lại nội dung'}[q.check.status]||''):'Chưa kiểm tra'].filter(Boolean).join(' · ');
};
const statusClass=(q,e=state?exam():null)=>{
 const srcWarn=sourceWarningText(q,e);
 if(srcWarn)return 'review is-stale-source';
 if(q?.check?.version===q.v&&q.check.status==='review')return 'review';
 if(q?.needsReview&&!isApproved(q))return 'review';
 return isApproved(q)?'approved':q.check?.version===q.v?q.check.status:'';
};
const date=n=>new Date(n).toLocaleString('vi-VN',{hour:'2-digit',minute:'2-digit',day:'2-digit',month:'2-digit'});
function activeModalDialog(){return dialogLayer2?.open?dialogLayer2:(dialog?.open?dialog:null);}
function closeTopModal(){const top=activeModalDialog();if(top)top.close();}
function toast(text){const topDialog=activeModalDialog();if(topDialog){let feedback=topDialog.querySelector('[data-dialog-feedback]');if(!feedback){feedback=document.createElement('p');feedback.dataset.dialogFeedback='';feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');const foot=topDialog.querySelector('.modal-foot');if(foot)foot.before(feedback);else topDialog.querySelector('.modal-body')?.append(feedback);}feedback.textContent=text;feedback.scrollIntoView({block:'nearest'});return;}const composerFeedback=$('.composer-shell #composer-feedback');if(composerFeedback){composerFeedback.textContent=text;composerFeedback.scrollIntoView({block:'nearest'});return;}$('#toast').textContent=text;$('#toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),3500);}
let saveRequested=0,persistRunning=false,saveWarning=false;
function saveWarningText(){
 return db.hasStateConflict()?'Xung đột lưu · Đề trên máy chủ đã đổi. Bản nháp còn tại máy.':'Chưa đồng bộ · Kiểm tra mạng hoặc đăng nhập lại';
}
function showSaveWarning(active){
 saveWarning=active;
 const node=$('[data-save-warning]');
 if(!node)return;
 node.hidden=!active;
 node.querySelector('[data-save-message]').textContent=saveWarningText();
 node.querySelector('button').hidden=!db.hasStateConflict();
}
function saveStatusLabel(){
 if(persistRunning)return 'Đang lưu…';
 if(db.hasStateConflict())return 'Xung đột lưu';
 return db.hasPendingWrites()?'Đã lưu tạm · chờ đồng bộ':accountSaveLabel();
}
window.addEventListener('online',async()=>{
 if(!db.hasPendingWrites())return;
 await db.retryPendingWrites().catch(()=>{});
 if(persistRunning)return;
 document.querySelectorAll('[data-save-status]').forEach(node=>node.textContent=saveStatusLabel());
 showSaveWarning(db.hasPendingWrites());
});
window.addEventListener('beforeunload',event=>{
 if(persistRunning||db.hasPendingWrites()||hasPendingEditorChanges()){
  event.preventDefault();
  event.returnValue='';
 }
});
function persist(){saveRequested++;document.querySelectorAll('[data-save-status]').forEach(n=>n.textContent='Đang lưu…');if(persistRunning)return saveChain;persistRunning=true;saveChain=(async()=>{let failure=null;try{for(;;){const epoch=saveRequested;try{await db.put('state',clone(state));failure=null;}catch(err){failure=err;}if(epoch===saveRequested)break;}if(failure){document.querySelectorAll('[data-save-status]').forEach(n=>n.textContent=db.hasStateConflict()?'Xung đột lưu':'Đã lưu tạm · chờ đồng bộ');showSaveWarning(true);throw failure;}document.querySelectorAll('[data-save-status]').forEach(n=>n.textContent=accountSaveLabel());showSaveWarning(false);}finally{persistRunning=false;}})();return saveChain;}

let warnedApprovedRevision=null;
function change(label,fn,{renderPage=true,coalesceKey=null}={}){const cur=exam(),wasLocked=['approved','printed'].includes(cur?.workflowStatus);if(coalesceKey)commitTyping(cur,label,fn,coalesceKey);else commit(cur,label,fn);if(wasLocked&&cur.workflowStatus===exam().workflowStatus&&warnedApprovedRevision!==cur.id){warnedApprovedRevision=cur.id;toast('Đang sửa từ bản '+WORKFLOW_STATUS_LABELS[cur.workflowStatus]+'. Đã tạo bản nháp mới · Ctrl+Z để hoàn tác.');}persist().catch(()=>{});if(renderPage)render();else mountMatrixChat(mvpContext);}
let modalReturnFocus=null,layer2ReturnFocus=null;
function modal(title,body,subtitle='',opts={}){
 const useLayer2=(opts?.layer===2||(!opts?.layer&&opts?.nested))&&dialogLayer2;
 const target=useLayer2?dialogLayer2:dialog;
 const titleId=useLayer2?'dialog2-title':'dialog-title';
 if(!target.open&&document.activeElement instanceof HTMLElement){
  if(useLayer2)layer2ReturnFocus=document.activeElement;
  else modalReturnFocus=document.activeElement;
 }
 target.innerHTML=`<div class="modal-head"><div><h2 id="${titleId}">${title}</h2>${subtitle?`<p>${subtitle}</p>`:''}</div><button type="button" class="icon ghost" data-action="${useLayer2?'close-top-modal':'close'}" aria-label="Đóng">${icon('close')}</button></div><div class="modal-body">${body}</div>`;
 if(!target.open)target.showModal();
}
const foot=html=>`<div class="modal-foot">${html}</div>`;
const button=(action,label,cls='',attrs='')=>`<button type="button" data-action="${action}" class="${cls}" ${attrs}>${label}</button>`;
const empty=message=>`<div class="empty">${message}</div>`;
const mvpContext={onManualChange:q=>scheduleAutoReconcile(q),act:(a,n)=>handleAction(a,n||document.createElement('button')),exam,qget,getState:()=>state,workspaceHeaders:()=>db.workspaceHeaders(),getViewMode:()=>viewMode,setViewMode:mode=>{viewMode=mode==='home'?'home':'workspace';activeRailNav=viewMode==='home'?'design-home':'design-workspace';syncHomeUrl(viewMode);render();},openExamInWorkspace:id=>{if(!state.exams.some(x=>x.id===id))return;state.current=id;selected=null;selection=null;viewMode='workspace';activeRailNav='design-workspace';syncHomeUrl('workspace');dialog.close();persist();render();},createBlankExamForHome:({subject,grade,title}={})=>{const e=blank(subject||'Toán',state.prefs,state.teacherProfile);if(grade)e.grade=String(grade);if(title)e.title=String(title);state.exams.push(e);state.current=e.id;selected=null;selection=null;teacher=false;persist();return e;},onAutoCreateExam:({prompt,examId,campaignId,subject,grade,durationMinutes,consentGiven,saveWorkspaceConsent}={})=>{if(examId&&state.exams.some(x=>x.id===examId))state.current=examId;viewMode='workspace';activeRailNav='design-workspace';syncHomeUrl('workspace');assistantOpen=true;dialog.close();if(dialogLayer2?.open)dialogLayer2.close();render();setTimeout(()=>{if(!prompt)return;const cur=exam();const resolvedConsent=consentGiven!==undefined?Boolean(consentGiven):Boolean(cur?.aiConsent);window.dispatchEvent(new CustomEvent('mach:auto-create-exam',{detail:{prompt,examId:cur?.id||examId,campaignId:campaignId||null,subject:subject||cur?.subject||'',grade:grade||cur?.grade||'',durationMinutes:durationMinutes||cur?.minutes||null,consentGiven:resolvedConsent,saveWorkspaceConsent:saveWorkspaceConsent===true}}));},40);},setTab:value=>{tab=['outline','templates'].includes(value)?value:'outline';},getSelected:()=>selected,setSelected:id=>{const changed=selected!==id;selected=id;document.querySelectorAll('.question').forEach(n=>n.classList.toggle('selected',n.dataset.q===id));if(changed)refreshWorkbench();},setSelection:s=>{selection=s;},isTeacher:()=>teacher,change,persist,render,modal,toast,icon,refreshInline,currentScope,showSource,showQuotes,showMatrix,chooseFile,importDroppedFile:file=>importFile(file),addChat};
async function hydratePaperAudioPlayers(){
 const players=[...document.querySelectorAll('audio[data-audio-file-id]')];
 for(const el of players){
  const fid=el.dataset.audioFileId;
  if(!fid||el.dataset.loaded==='1')continue;
  try{
   const data=await db.get('file:'+fid);
   if(typeof data==='string'&&data.startsWith('data:audio/')&&el.isConnected){
    el.src=data;
    el.dataset.loaded='1';
   }
  }catch{}
 }
}
const normMatrixKey=v=>String(v||'').trim().toLocaleLowerCase('vi-VN');
function rowUnitPointsForLevel(row,level){
 const lvl=row?.pointsByLevelQ4||row?.pointsByLevel;
 if(Array.isArray(lvl)&&lvl[level]!=null){
  const val=Number(lvl[level]);
  if(Number.isFinite(val))return row.pointsByLevelQ4?val/4:val;
 }
 if(row?.pointsQ4!=null&&Number.isFinite(Number(row.pointsQ4)))return Number(row.pointsQ4)/4;
 if(row?.points!=null&&Number.isFinite(Number(row.points)))return Number(row.points);
 return null;
}
function rowMatchesQuestionShape(row,q){
 const rTopic=normMatrixKey(row?.topic),qTopic=normMatrixKey(q?.topic);
 if(!rTopic||!qTopic)return false;
 if(rTopic!==qTopic&&!rTopic.startsWith(qTopic+' ('))return false;
 if(row.type&&(q.type||'mcq')!==row.type)return false;
 if(normMatrixKey(row.choiceGroup)!==normMatrixKey(q.choiceGroup))return false;
 return true;
}
function computeMatrixRowActuals(rows,questions){
 const list=Array.isArray(rows)?rows:[],qs=Array.isArray(questions)?questions:[];
 const counts=list.map(()=>LEVELS.map(()=>0));
 const matchedQ=new Set();
 for(const q of qs){
  const l=Number(q?.level);
  const qPt=Number(q?.points);
  const candidates=list.map((r,idx)=>({r,idx})).filter(({r})=>rowMatchesQuestionShape(r,q));
  if(!candidates.length)continue;
  let picked=candidates;
  if(candidates.length>1&&Number.isFinite(qPt)){
   const byPt=candidates.filter(({r})=>{
    const rp=rowUnitPointsForLevel(r,Number.isInteger(l)?l:0);
    return rp!=null&&Math.abs(rp-qPt)<0.005;
   });
   if(byPt.length)picked=byPt;
  }
  const exactTopic=picked.filter(({r})=>normMatrixKey(r.topic)===normMatrixKey(q.topic));
  const chosen=(exactTopic.length?exactTopic:picked)[0];
  matchedQ.add(q);
  if(Number.isInteger(l)&&l>=0&&l<LEVELS.length)counts[chosen.idx][l]++;
 }
 return {counts,unmappedCount:qs.filter(q=>!matchedQ.has(q)).length};
}
function questionChoiceGroup(e,q){
 const direct=String(q?.choiceGroup||'').trim();
 if(direct)return direct;
 if(!Array.isArray(e?.matrix)||!e.matrix.some(r=>String(r?.choiceGroup||'').trim()))return '';
 const qTopic=normMatrixKey(q?.topic);
 if(!qTopic)return '';
 const qType=q?.type||'mcq';
 const groups=[...new Set(e.matrix.filter(r=>(normMatrixKey(r?.topic)===qTopic||normMatrixKey(r?.topic).startsWith(qTopic+' ('))&&(!r.type||r.type===qType)).map(r=>String(r.choiceGroup||'').trim()))];
 return groups.length===1?groups[0]:'';
}
function effectiveExamTotals(e){
 const qs=Array.isArray(e?.questions)?e.questions:[];
 let commonCount=0,commonPts100=0;
 const tracks=new Map();
 for(const q of qs){
  const grp=questionChoiceGroup(e,q);
  const pt100=Math.round((Number(q?.points)||0)*100);
  if(!grp){
   commonCount++;
   commonPts100+=pt100;
  }else{
   const key=normMatrixKey(grp);
   const cur=tracks.get(key)||{count:0,pts100:0};
   cur.count++;
   cur.pts100+=pt100;
   tracks.set(key,cur);
  }
 }
 const hasTracks=tracks.size>0;
 const maxTrackCount=hasTracks?Math.max(...[...tracks.values()].map(v=>v.count)):0;
 const maxTrackPts100=hasTracks?Math.max(...[...tracks.values()].map(v=>v.pts100)):0;
 const effectiveCount=commonCount+maxTrackCount;
 const effectivePoints=(commonPts100+maxTrackPts100)/100;
 const rawPoints=(commonPts100+[...tracks.values()].reduce((s,v)=>s+v.pts100,0))/100;
 return {hasTracks,effectiveCount,effectivePoints,rawCount:qs.length,rawPoints};
}
function examFooterSummaryText(e){
 if(!e?.questions?.length)return 'Đề trống · Chọn thao tác bên trên hoặc hỏi Trợ lý AI';
 const totals=effectiveExamTotals(e),approved=e.questions.filter(isApproved).length;
 if(totals.hasTracks){
  const pts=totals.effectivePoints.toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2});
  return `${totals.effectiveCount} câu hiệu lực · ${pts} điểm (Phần chung + max/hướng) · ${approved} câu đã duyệt · Bản ${e.revision}`;
 }
 return `${e.questions.length} câu · ${totals.rawPoints.toLocaleString('vi-VN')} điểm · ${approved} câu đã duyệt · Bản ${e.revision}`;
}
function syncDocumentSummary(e){
 const totals=effectiveExamTotals(e);
 const summary=$('.document-summary');
 if(summary&&e?.questions?.length){
  if(totals.hasTracks){
   const pts=totals.effectivePoints.toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2});
   summary.textContent=`Tổng điểm hiệu lực: ${pts} (Phần chung + max/hướng · ${totals.effectiveCount}/${e.questions.length} câu)`;
  }else{
   summary.textContent='Tổng điểm: '+totals.rawPoints.toLocaleString('vi-VN');
  }
 }
 const qCount=$('.studio-q-count');
 if(qCount&&e?.questions?.length&&totals.hasTracks){
  const pts=totals.effectivePoints.toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2});
  qCount.textContent=`${totals.effectiveCount} câu hiệu lực · ${pts}đ`;
 }
}
function render(){const e=ensureBlocks(exam());if(!['outline','templates'].includes(tab))tab='outline';if(!e.questions.some(q=>q.id===selected)){selected=e.questions[0]?.id||null;selection=null;}
 document.body.classList.toggle('view-teacher',teacher);document.body.classList.toggle('view-student',!teacher);
 const saveLabel=saveStatusLabel();
 const wf=normalizeWorkflowStatus(e.workflowStatus);
 const menus=[['file','Tệp'],['edit','Chỉnh sửa'],['view','Xem'],['insert','Chèn'],['format','Định dạng'],['tools','Công cụ']].map(([id,name])=>button('menu',name,'menu-button',`data-menu="${id}"`)).join('');
 const railItems=[
  ['design-home','home','Trang chủ','Trang chủ'],
  ['design-workspace','edit','Soạn đề','Bàn soạn đề'],
  ['library','folder','Kho đề','Mở kho đề'],
  ['question-bank','book','Ngân hàng','Ngân hàng câu hỏi'],
  ['exam-rooms','grid','Phòng thi','Phòng thi'],
  ['exam-analytics','spark','Phân tích','Phân tích chất lượng đề'],
 ].map(([act,ic,lbl,aria])=>`<button type="button" data-action="${act}" class="${activeRailNav===act?'rail-active':''}" aria-label="${esc(aria)}" title="${esc(aria)}">${icon(ic)}<span class="rail-label">${esc(lbl)}</span></button>`).join('')
 +`<button type="button" data-action="design-command" class="rail-icon-only" aria-label="Tìm nhanh công cụ (Ctrl+K)" title="Tìm nhanh công cụ (Ctrl+K)">${icon('search')}</button>`;
 const summaryText=examFooterSummaryText(e);
 const headerHTML=`<header class="top${viewMode==='home'?' home-top':''}" data-unified-header="1">
  <div class="mvp-document">
   <a class="mach-logo" href="#home" data-action="design-home" aria-label="Soạn đề thi · Bàn soạn"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 13c0-4.2 3.8-7 8.8-7 3.6 0 6.2 1.8 6.8 4.4l2.9-1.7c.3-.2.7.1.6.4-.5 2-1.4 3.4-2.8 4.2-.8 2.4-3.7 3.7-7.7 3.7C6.6 17 3 15.6 3 13z" fill="currentColor" fill-opacity="0.22" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="7.5" cy="11.8" r="1" fill="currentColor"/><path d="M4 19.2c2.2 1.1 4.4 1.1 6.6 0s4.4-1.1 6.6 0c1.1.5 2 .7 2.8.6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></a>
   <input class="header-title" maxLength="180" value="${esc(e.title)}" data-exam-field="title" aria-label="Tên tài liệu">
   <span class="saved"><span data-save-status>${esc(saveLabel)}</span></span>
   <select id="workflow-status-select" class="workflow-status-select" data-wf="${esc(wf)}" aria-label="Trạng thái quy trình đề">${Object.entries(WORKFLOW_STATUS_LABELS).map(([k,lbl])=>`<option value="${k}" ${wf===k?'selected':''}>${lbl}</option>`).join('')}</select>
  </div>
  <nav class="design-rail" aria-label="Không gian làm việc">${railItems}</nav>
  <div class="header-actions">${button('open-proactive-center',icon('bell'),'proactive-bell-btn','aria-label="Thông báo Trợ lý Chủ động" title="Trợ lý Chủ động · Chiến dịch & nhắc lịch"')}${button('new',icon('plus')+'<span>Tạo đề mới</span>','header-new-btn','aria-label="Tạo đề mới"')}${button('export',icon('download')+'<span>Xuất đề</span>','header-export-btn primary','aria-label="Xuất đề"')}${button('share',icon('globe')+'<span>Chia sẻ</span>','quiet','aria-label="Chia sẻ"')}${button('toggle-ai',icon('chat')+'<span>Hỏi AI</span>','ai-button','aria-label="Hỏi AI"')}</div>
 </header>`;
 if(viewMode==='home'){
  app.innerHTML=headerHTML+renderHomeViewHTML(state);
  mountDesign(mvpContext);
  setActiveWorkspaceNav('design-home');
  mountHomeView(mvpContext);
  document.querySelectorAll('[data-save-status]').forEach(n=>n.textContent=saveLabel);
  return;
 }
 app.innerHTML=headerHTML+`
 <div class="workspace ${assistantOpen?'mobile-ai-view':''}"><aside class="sidebar ${sidebarOpen?'open':''}"><div class="sidebar-top"><button type="button" class="icon ghost mobile-nav" data-action="toggle-left" style="float:right" aria-label="Đóng mục lục">${icon('close')}</button><div class="eyebrow">Tài liệu &amp; cấu trúc</div><h2>${esc(e.subject)} · Lớp ${esc(e.grade)}</h2><div class="meta">${e.questions.length} câu hỏi · ${e.minutes} phút ${e.sample?'· Ví dụ mẫu':''}</div></div><nav class="tabs" aria-label="Nội dung bên trái">${[['outline','Mục lục'],['templates','Mẫu đề thi']].map(([id,t])=>button('tab',t,tab===id?'active':'',`data-tab="${id}"`)).join('')}</nav><div class="side-content">${sideHTML()}</div><div class="design-side-actions">${button('library',icon('folder')+'Xem kho đề của tôi','design-library-open')}${button('subject-library','<span class="formula-tool-symbol">ƒ</span> Công thức &amp; mẫu','subtle')}${button('exam-rooms',icon('grid')+'Phòng thi &amp; giao bài','subtle')}${button('memory',icon('memory')+`Cách ra đề (${state.prefs.length})`,'subtle')}</div></aside>
 <main class="main">
  <div class="menubar-row"><div class="menubar" aria-label="Trình đơn thao tác">${menus}</div><div class="breadcrumb">${button('toggle-left',icon('list'),'icon mobile-nav','aria-label="Mở mục lục"')}<span>Đề của tôi</span><span>/</span><b>${esc(e.title)}</b></div></div>
  <div class="editing-bar"><div class="editor-toolbar">${button('toggle-left',icon('list'),'tool mobile-nav','aria-label="Mở mục lục"')}<div class="toolgroup">${button('undo',icon('undo'),'tool',`title="Hoàn tác" aria-label="Hoàn tác" ${(e.undo.length||hasPendingEditorChanges())?'':'disabled'}`)}${button('redo',icon('redo'),'tool',`title="Làm lại" aria-label="Làm lại" ${e.redo.length?'':'disabled'}`)}${button('export',icon('print'),'tool','title="In / Xuất Word, PDF" aria-label="Xuất đề"')}<select id="zoom" aria-label="Độ thu phóng"><option value="75">75%</option><option value="85">85%</option><option value="90">90%</option><option value="100" selected>100%</option><option value="110">110%</option></select></div><span class="toolbar-divider"></span><select id="doc-font" aria-label="Phông chữ"><option ${e.layout?.font!=='Arial'?'selected':''}>Times New Roman</option><option ${e.layout?.font==='Arial'?'selected':''}>Arial</option></select><input id="doc-fontsize" aria-label="Cỡ chữ" type="number" min="10" max="22" value="${e.layout?.fontSize||15}"><span class="toolbar-divider"></span>${button('format','<b>B</b>','tool','data-command="bold" title="In đậm" aria-label="In đậm"')}${button('format','<i>I</i>','tool','data-command="italic" title="In nghiêng" aria-label="In nghiêng"')}${button('format','<u>U</u>','tool','data-command="underline" title="Gạch chân" aria-label="Gạch chân"')}<span class="toolbar-divider"></span>${button('formula','∑','tool formula-tool','title="Chèn công thức" aria-label="Chèn công thức"')}${button('chemistry',icon('chemistry'),'tool','title="Công thức hóa học" aria-label="Công thức hóa học"')}${button('subject-library','<span class="formula-tool-symbol">ƒ</span>','tool design-library-open','aria-label="Chèn nội dung theo môn" title="Thư viện công thức & mẫu theo môn"')}${button('exam-audio','🔊 Audio','tool','title="Gắn Audio nghe cho đề" aria-label="Gắn Audio nghe cho đề"')}${button('menu','⋮','tool','data-menu="insert" title="Thêm công cụ" aria-label="Thêm công cụ"')}</div><div class="ux-view-tabs" role="tablist" aria-label="Chế độ xem">${button('view-student','Đề',!teacher?'view-tab active':'view-tab')}${button('view-teacher','Đáp án',teacher?'view-tab active':'view-tab')}<button type="button" class="view-tab ux-mobile-only ${assistantOpen?'':'active'}" data-ux-action="mobile-show-editor">Bàn soạn</button><button type="button" class="view-tab ux-mobile-only ${assistantOpen?'active':''}" data-action="toggle-ai">Trợ lý</button></div></div>
  <div class="document-bar"><div class="ruler"><i></i>${Array.from({length:17},(_,i)=>`<span>${i+1}</span>`).join('')}<i></i></div></div>
  <div class="paper-scroll"><article class="paper ${!e.questions.length?'empty-paper':''}"><span class="paper-ribbon">${e.sample?'VÍ DỤ MẪU':'BẢN NHÁP'}</span><div class="exam-heading"><div class="school-column"><div>${esc(e.department||'PHÒNG GIÁO DỤC VÀ ĐÀO TẠO')}</div><div>${esc(e.school)}</div><span class="official-label">${e.sample?'ĐỀ MINH HỌA':wf==='printed'?'BẢN ĐÃ IN':wf==='approved'?'ĐỀ CHÍNH THỨC':'ĐỀ KIỂM TRA'}</span></div><div class="exam-heading-main"><input class="title-input" aria-label="Tên đề" data-exam-field="title" value="${esc(e.title)}"><div class="paper-subtitle">Môn: ${esc(e.subject)} &nbsp; | &nbsp; Lớp ${esc(e.grade)} &nbsp; | &nbsp; Thời gian: ${e.minutes} phút</div></div></div><div class="student-line"><span>Họ và tên: ................................................</span><span>Lớp: .................</span></div><textarea class="instructions" aria-label="Hướng dẫn làm bài" data-exam-field="instructions" rows="1">${esc(e.instructions)}</textarea>${e.audio?audioAttachmentCardHTML(e.audio,{scope:'exam',label:'Audio đề thi'}):''}${e.appliedPrefs.length?`<div class="apply-pref">Yêu cầu đang áp dụng: ${e.appliedPrefs.map(p=>esc(p.text)).join(' · ')}</div>`:''}${e.questions.length?`<div class="paper-section">${teacher?'ĐÁP ÁN & GIẢI THÍCH':'PHẦN ĐỀ THI'} <span>${e.questions.length} câu hỏi</span></div>`:''}${(e.subject==='Ngữ văn'||e.quote.chosen)&&e.quote.text?`<div class="quote-box">${esc(e.quote.text)}<div class="quote-caption"><span>${e.quote.chosen?'Đã chọn bản dùng':'Ngữ liệu tự soạn · chưa duyệt'}</span>${button('quotes','Đối chiếu','tiny-btn')}</div></div>`:''}${e.questions.some(usesTable)?dataHTML():''}${e.questions.map((q,i)=>questionHTML(q,i)).join('')}${!e.questions.length?emptyCanvasHTML(e):''}<div class="paper-add-actions">${button('add-question',icon('plus')+'Thêm câu hỏi','add-question')}${button('studio-question',icon('plus')+'Thêm câu theo dạng ▾','add-question')}</div><div class="paper-footer">— Hết —<br><span style="font-size:9px">${e.sample?'Ngữ liệu và số liệu tự tạo để trải nghiệm; thầy cô duyệt trước khi sử dụng.':'Bản nháp do thầy cô biên soạn.'}</span></div></article></div>
  <div class="main-footer"><span class="footer-legacy-meta">${esc(summaryText)}</span><span data-save-warning role="status" ${saveWarning?'':'hidden'}><span data-save-message>${saveWarningText()}</span> <button type="button" data-action="backup" ${db.hasStateConflict()?'':'hidden'}>Tải bản nháp</button></span></div>
 </main>
 <aside class="assistant ${assistantOpen?'open':''}"><div class="assistant-head"><div class="assistant-title"><span class="ai-symbol">${icon('spark')}</span><div>Trợ lý AI soạn đề<small>Chỉnh đúng câu · có nguồn để đối chiếu</small></div></div><div class="row">${button('connections',icon('settings'),'icon ghost','aria-label="Kết nối AI & tìm nguồn"')}${button('toggle-chat',icon('close'),'icon ghost mobile-nav','aria-label="Đóng trợ lý"')}</div></div><div class="mode-notice">Chưa kết nối AI · Đang dùng công cụ tại máy<br>Gợi ý mẫu luôn được ghi rõ trước khi áp dụng.</div><div class="assistant-body" id="assistant-body">${rightHTML()}</div><form id="chat-form" class="chat-compose"><div class="compose-box"><textarea id="chat-input" aria-label="Nhắn với trợ lý" placeholder="Nhập yêu cầu tạo, sửa hoặc kiểm tra đề…" rows="2"></textarea><div class="compose-bottom"><small>${selected?'Đang chọn câu '+(e.questions.findIndex(q=>q.id===selected)+1):'Chưa chọn câu'}</small><button id="chat-send" class="primary" type="submit" aria-label="Gửi yêu cầu">${icon('send')}</button></div></div><div class="chat-foot">Thầy cô xem và xác nhận mọi đề xuất sửa.</div></form></aside></div>`;
 autosize();mountMVP(mvpContext);mountWorkbench(mvpContext);mountStudio(mvpContext);syncDocumentSummary(e);mountMatrixChat(mvpContext);mountVipTools(mvpContext);mountExamRooms(mvpContext);
 ensureWorkspaceVoiceButton();
 setActiveWorkspaceNav(activeRailNav);
 void hydratePaperAudioPlayers();
 if(Date.now()-lastDigestFetchAt>30000){lastDigestFetchAt=Date.now();void refreshProactiveUI(mvpContext);}
 document.querySelectorAll('[data-save-status]').forEach(n=>n.textContent=saveLabel);
}
function autosize(){document.querySelectorAll('textarea.stem,textarea.instructions').forEach(t=>{t.style.height='auto';t.style.height=t.scrollHeight+'px';});}
function refreshInline(){const e=exam();const outlineHTML=sideHTML();if($('.side-content')&&$('.side-content')._markup!==outlineHTML){$('.side-content').innerHTML=outlineHTML;$('.side-content')._markup=outlineHTML;}refreshReferenceScope(mvpContext);ensureWorkspaceVoiceButton();refreshWorkbench();refreshStudio();syncDocumentSummary(e);if($('.breadcrumb b'))$('.breadcrumb b').textContent=e.title;if($('.header-title')&&document.activeElement!==$('.header-title'))$('.header-title').value=e.title;const wfSel=$('#workflow-status-select');if(wfSel){const wf=normalizeWorkflowStatus(e.workflowStatus);wfSel.value=wf;wfSel.dataset.wf=wf;}const metaSpan=$('.main-footer .footer-legacy-meta')||$('.main-footer span');if(metaSpan)metaSpan.textContent=examFooterSummaryText(e);for(const [idx,q] of e.questions.entries()){const card=document.querySelector(`[data-q="${q.id}"]`),el=card?.querySelector('.q-status');if(el){const sc=statusClass(q,e);el.className='q-status '+sc;el.innerHTML=`<span class="dot ${sc}"></span>${esc(statusText(q,e))}`;}const appBtn=card?.querySelector('.q-approve-btn');if(appBtn){const approved=isApproved(q),needsReview=q.check?.version===q.v&&q.check.status==='review';appBtn.className='q-quick-btn q-approve-btn'+(approved?' is-approved':needsReview?' is-review':'');appBtn.setAttribute('aria-pressed',String(approved));appBtn.setAttribute('aria-label',`${approved?'Bỏ duyệt':'Duyệt'} câu ${idx+1}`);appBtn.title=approved?'Bấm để bỏ duyệt câu':'Đánh dấu giáo viên đã duyệt';const span=appBtn.querySelector('span');if(span)span.textContent=approved?'Đã duyệt':'Duyệt';}}document.querySelectorAll('[data-action="undo"]').forEach(n=>n.disabled=!e.undo.length&&!hasPendingEditorChanges());document.querySelectorAll('[data-action="redo"]').forEach(n=>n.disabled=!e.redo.length);}
function sideHTML(){const e=exam();const ref=referenceSide(e,selected,tab);if(ref!==null)return ref;return `<div class="section-label"><span>NỘI DUNG ĐỀ</span><span>${String(e.questions.length).padStart(2,'0')}</span></div>${e.questions.map((q,i)=>`<button class="outline-item ${selected===q.id?'active':''}" data-action="select" data-id="${q.id}"><span class="number">${String(i+1).padStart(2,'0')}</span><span style="flex:1"><span class="outline-title">${esc(q.stem||'Câu hỏi mới')}</span><span class="outline-sub">${esc(q.topic)} · ${LEVELS[q.level]}</span></span><span class="dot ${statusClass(q)}" title="${statusText(q)}"></span></button>`).join('')}${button('add-question',icon('plus')+'Thêm câu hỏi','wide ghost')}<div class="section-label" style="margin-top:18px">CÔNG CỤ NHANH</div>${button('assistant-sources',icon('paperclip')+'Tài liệu nguồn ('+e.docs.length+')','wide ghost')}${button('matrix',icon('grid')+'Ma trận đề','wide ghost')}${button('quotes',icon('book')+'Đối chiếu đoạn trích','wide ghost')}${button('extract',icon('file')+'Rút trích đề thi','wide ghost')}${button('library',icon('folder')+'Đề đã lưu','wide ghost')}`;}
function unmappedHTML(){const e=exam();const {unmappedCount}=computeMatrixRowActuals(e.matrix,e.questions);return unmappedCount?`<p class="unmapped">${unmappedCount} câu thuộc chủ đề chưa có trong ma trận.</p>`:'';}
function dataHTML(){const e=exam();let diagram;try{diagram=dataChartSVG(e.data);}catch{diagram='<p role="alert">Dữ kiện chưa hợp lệ. Chọn Sửa dữ kiện để kiểm tra.</p>';}return `<div class="data-card"><div class="data-heading">Bảng 1. Số người sử dụng thư viện ${button('data',icon('edit')+'Sửa dữ kiện')}</div><p class="data-sub">Dữ liệu minh họa tự tạo · Đơn vị: người</p><div class="data-body"><table><tr><th>Khu vực</th><th class="num">Số người</th></tr>${e.data.map(d=>`<tr><td>${esc(d.label)}</td><td class="num">${esc(d.value)}</td></tr>`).join('')}</table>${diagram}</div></div>`;}
function answerInputs(q,i){
 if(q.type==='short')return `<input data-q-field="answerText" data-id="${q.id}" aria-label="Đáp án ngắn câu ${i+1}" value="${esc(q.answerText||'')}">`;
 if(q.type==='truefalse')return [0,1,2,3].map(j=>`<label>${j+1}. <select data-q-field="truthValue" data-index="${j}" data-id="${q.id}" aria-label="Nhận định ${j+1} câu ${i+1}"><option value="" ${q.answerKnown===false&&!q.truthValues?.some(x=>x===null)?'selected':''}>Chưa xác nhận</option>${[true,false].map(value=>`<option value="${value}" ${q.truthValues?.[j]===value&&(q.answerKnown!==false||q.truthValues?.some(x=>x===null))?'selected':''}>${value?'Đúng':'Sai'}</option>`).join('')}</select></label>`).join('');
 return `<select class="answer-select" aria-label="Đáp án câu ${i+1}" data-q-field="answer" data-id="${q.id}">${q.answerKnown===false?'<option value="" selected>Chưa xác nhận</option>':''}${q.options.map((_,j)=>`<option value="${j}" ${j===q.answer&&q.answerKnown!==false?'selected':''}>${String.fromCharCode(65+j)}</option>`).join('')}</select>`;
}
function questionHTML(q,i){const e=exam(),sc=statusClass(q,e),st=statusText(q,e),isMcq=!q.type||q.type==='mcq';return `<section class="question ${selected===q.id?'selected':''}" id="q-${q.id}" data-q="${q.id}"><div class="q-top"><b class="q-label">Câu ${i+1}.</b><div class="q-actions">${questionQuickActionsHTML(q,i,e.questions.length,icon)}${button('save-to-bank','★','tiny-btn q-quick-btn q-bank-star',`data-id="${q.id}" title="Lưu vào Ngân hàng câu hỏi" aria-label="Lưu vào Ngân hàng câu hỏi"`)}</div><span class="q-status ${sc}"><span class="dot ${sc}"></span>${esc(st==='Chưa thấy bất đồng trong phép tính'?'Phép tính chưa thấy bất đồng':st)}</span></div><textarea class="stem" rows="1" data-q-field="stem" data-id="${q.id}" aria-label="Nội dung câu ${i+1}">${esc(q.stem)}</textarea>${q.audio?audioAttachmentCardHTML(q.audio,{scope:'question',targetId:q.id,label:'Audio câu '+(i+1)}):''}<div class="options">${q.options.map((o,j)=>{const isCorrect=isMcq&&q.answerKnown!==false&&q.answer===j;return `<div class="option ${isCorrect?'is-correct-option':''}">${isMcq?`<button type="button" class="option-answer-btn ${isCorrect?'is-correct':''}" data-action="set-mcq-answer" data-id="${q.id}" data-index="${j}" aria-pressed="${isCorrect}" title="Đánh dấu ${String.fromCharCode(65+j)} là đáp án đúng" aria-label="Đánh dấu ${String.fromCharCode(65+j)} là đáp án đúng câu ${i+1}">${String.fromCharCode(65+j)}</button>`:`<span>${String.fromCharCode(65+j)}.</span>`}<input data-q-field="option" data-index="${j}" data-id="${q.id}" aria-label="Phương án ${String.fromCharCode(65+j)} câu ${i+1}" value="${esc(o)}"></div>`;}).join('')}</div>${button('source',icon('link')+esc(q.source?.location||'Chưa gắn nguồn'),'source-link',`data-id="${q.id}"`)}${q.type==='essay'?button('rubric','Lời giải & thang điểm','essay-rubric-link',`data-id="${q.id}"`):''}${teacher&&q.type==='essay'?rubricHTML(q):teacher?`<div class="answer-area"><div class="row"><span>${q.answerKnown===false?'Chưa nhập đáp án (chọn lại để xác nhận):':'Đáp án lưu:'}</span>${answerInputs(q,i)}<span class="key">Câu v${q.v}</span></div><textarea data-q-field="explanation" data-id="${q.id}" aria-label="Giải thích câu ${i+1}" rows="2">${esc(q.explanation)}</textarea></div>`:''}</section>`;}
function showAudioModal({scope='question',questionId=null}={}){
 const e=exam();
 const q=scope==='question'?qget(questionId||selected):null;
 if(scope==='question'&&!q)throw Error('Chọn một câu hỏi để gắn Audio nghe.');
 const cur=scope==='exam'?e.audio:q?.audio;
 const heading=scope==='exam'?'Gắn Audio nghe cho đề thi':`Gắn Audio nghe · Câu ${e.questions.indexOf(q)+1}`;
 modal(heading,`<form id="audio-attach-form" data-scope="${esc(scope)}" data-id="${esc(q?.id||'')}">
  <p class="hint">Đính kèm tệp âm thanh <code>.mp3</code> hoặc <code>.wav</code> (tối đa 20 MB). Tệp được lưu riêng và tự gắn khi mở Phòng thi.</p>
  ${cur?`<div class="audio-attach-preview"><span>🔊 Đang gắn: <b>${esc(cur.title||cur.filename)}</b> (${cur.maxPlays||2} lượt nghe)</span></div>`:''}
  <label>Chọn tệp âm thanh (.mp3 / .wav)${cur?' — để trống nếu chỉ đổi số lượt nghe':''}<input type="file" name="audioFile" accept=".mp3,.wav,audio/mpeg,audio/wav" ${cur?'':'required'}></label>
  <label>Tên hiển thị đoạn nghe (tùy chọn)<input type="text" name="title" maxlength="120" value="${esc(cur?.title||'')}" placeholder="Ví dụ: Listening Part 1 · At the Library"></label>
  <label>Số lượt nghe tối đa cho thí sinh (1–20)<input type="number" name="maxPlays" min="1" max="20" value="${Number(cur?.maxPlays)||2}" required></label>
  ${foot((cur?button('remove-audio','Xóa Audio','danger',`type="button" data-scope="${esc(scope)}" data-id="${esc(q?.id||'')}"`):'')+'<button type="submit" class="primary">Lưu Audio nghe</button>')}
 </form>`);
}
function rightHTML(){return referenceChat(exam());}
function selectQ(id,scroll=true){const q=qget(id);if(!q)return;selected=id;selection=null;document.querySelectorAll('.question').forEach(n=>n.classList.toggle('selected',n.dataset.q===id));document.querySelectorAll('.outline-item').forEach(n=>n.classList.toggle('active',n.dataset.id===id));if(scroll)document.getElementById('q-'+id)?.scrollIntoView({block:'center',behavior:'smooth'});sidebarOpen=false;document.querySelector('.sidebar')?.classList.remove('open');}
function addChat(role,text){exam().chat.push({role,text,at:Date.now()});persist();}
function currentScope(){const q=qget(selected);if(!q)return null;if(selection?.id===q.id)return clone(selection);return questionScope(q);}
function showNew(){modal('Tạo đề mới',`<p class="hint">Chọn môn học. Thầy cô có thể nhập nội dung, dùng mẫu hoặc nhờ trợ lý soạn sau đó.</p><div class="new-subject-grid">${[['Toán','ƒ','Biểu thức và hình học'],['Vật lí','Ω','Công thức và đại lượng'],['Hoá học','H₂','Chất và phản ứng'],['Sinh học','Aa','Di truyền và tế bào'],['Ngữ văn','“','Ngữ liệu và câu hỏi'],['Tiếng Anh','En','Reading và bài tập']].map(([name,symbol,hint])=>`<button type="button" data-action="design-new-subject" data-subject="${name}" aria-pressed="${exam().subject===name}"><span>${symbol}</span><b>${name}</b><small>${hint}</small></button>`).join('')}</div><label for="new-subject">Môn học (có thể nhập môn khác)</label><input id="new-subject" value="${esc(exam().subject)}" maxlength="80"><p class="hint">Các yêu cầu soạn đề đã lưu sẽ được áp dụng cho đề mới.</p><details class="new-examples"><summary>Hoặc mở đề minh họa có sẵn</summary><div class="buttons">${button('essay-sample','Toán · 5 bài tự luận')}${button('create-sample','Địa lí · Bảng số liệu','','data-subject="Địa lí"')}${button('create-sample','Ngữ văn · Đọc hiểu','','data-subject="Ngữ văn"')}</div></details>${foot(button('create-blank',icon('plus')+'Tạo đề mới','primary'))}`);}

function createExam(subject,isSample){tab='outline';viewMode='workspace';activeRailNav='design-workspace';syncHomeUrl('workspace');const e=isSample?sample(subject,state.prefs):blank(subject,state.prefs,state.teacherProfile);if(isSample)e.questions.forEach(q=>check(e,q));state.exams.push(e);state.current=e.id;selected=null;selection=null;teacher=false;dialog.close();persist();render();toast('Đã tạo đề riêng · '+e.appliedPrefs.length+' yêu cầu được áp dụng');}
function showLibrary(){modal('Đề của tôi',`${state.exams.map(e=>`<div class="small-card library-meta"><div><b>${esc(e.title)}</b><p>${esc(e.subject)} · ${e.questions.length} câu · ${date(e.updated)}${e.sample?' · Mẫu':''}</p></div><div class="buttons">${button('open-exam',e.id===state.current?'Đang mở':'Mở đề',e.id===state.current?'ghost':'',`data-id="${e.id}"`)}${button('delete-exam',icon('trash'),'icon danger',`data-id="${e.id}" aria-label="Xóa đề ${esc(e.title)}"`)}</div></div>`).join('')}<p class="hint">Đề và hội thoại được lưu trong trình duyệt này. Xuất bản sao JSON để giữ một bản ngoài trình duyệt.</p>${foot(button('import-backup','Nhập bản sao JSON')+button('backup','Tải bản sao toàn bộ')+button('new','Tạo đề mới','primary'))}`);}
function readMatrixFormRows(form){
 const ptField=val=>{
  if(!val)return {};
  const n=Number(val);
  return Number.isInteger(Math.round(n*100)/25)?{pointsQ4:Math.round(n*4)}:{points:Math.round(n*100)/100};
 };
 const rows=[...form.querySelectorAll('[data-matrix-row]')].map(r=>{
  const lvlInputs=[...r.querySelectorAll('[name=matrix-level-points]')];
  const lvlVals=lvlInputs.map(n=>n.value===''?null:Number(n.value));
  const useDecLvl=lvlInputs.length&&lvlVals.some(v=>v!=null&&!Number.isInteger(Math.round(v*100)/25));
  const grp=r.dataset.choiceGroup?.trim();
  return {
   topic:r.querySelector('.topic').value.trim(),
   type:r.querySelector('[name=matrix-type]').value,
   ...(grp?{choiceGroup:grp}:{}),
   ...(!lvlInputs.length?ptField(r.querySelector('[name=matrix-points]').value):{}),
   targets:[...r.querySelectorAll('[data-matrix-target]')].map(n=>Number(n.value)),
   ...(lvlInputs.length?(useDecLvl?{pointsByLevel:lvlVals.map(v=>v==null?null:Math.round(v*100)/100)}:{pointsByLevelQ4:lvlVals.map(v=>v==null?null:Math.round(v*4))}):{}),
  };
 });
 validateMatrixRows(rows);return rows;
}
function mountMatrixTemplates(e){
 const panel=document.getElementById('matrix-templates-panel'),list=document.getElementById('matrix-templates-list'),saveBtn=document.getElementById('matrix-template-save'),nameInput=document.getElementById('matrix-template-name');
 if(!panel||!list)return;
 const renderList=async()=>{
  const response=await fetch('/api/matrix-templates',{headers:db.workspaceHeaders()}).catch(()=>null);
  if(!response||response.status===404){panel.hidden=true;return;}
  if(!response.ok){list.innerHTML='<p class="hint">Chưa tải được mẫu ma trận cá nhân.</p>';return;}
  const {templates=[]}=await response.json();
  if(!templates.length){list.innerHTML='<p class="hint">Chưa có mẫu ma trận đã lưu.</p>';return;}
  list.innerHTML=templates.map(t=>`<div class="small-card library-meta" data-template-id="${esc(t.id)}"><div><b>${esc(t.name)}</b><p>${esc(t.subject)} · Lớp ${esc(t.grade)} · ${t.total_questions} câu</p></div><div class="buttons"><button type="button" data-apply-template="${esc(t.id)}">Áp dụng mẫu</button><button type="button" class="danger" data-delete-template="${esc(t.id)}">Xóa</button></div></div>`).join('');
  list.querySelectorAll('[data-apply-template]').forEach(btn=>btn.onclick=()=>{
   const tpl=templates.find(item=>item.id===btn.dataset.applyTemplate);if(!tpl)return;
   validateMatrixRows(tpl.rows);
   change('Áp dụng mẫu ma trận cá nhân (chưa xác nhận)',target=>{target.matrix=clone(tpl.rows);target.matrixConfirmed=false;});
   showMatrix();toast('Đã nạp mẫu “'+tpl.name+'”. Hãy kiểm và xác nhận trước khi sinh.');
  });
  list.querySelectorAll('[data-delete-template]').forEach(btn=>btn.onclick=async()=>{
   const res=await fetch('/api/matrix-templates/'+encodeURIComponent(btn.dataset.deleteTemplate),{method:'DELETE',headers:db.workspaceHeaders()});
   if(!res.ok)throw Error('Chưa xóa được mẫu ma trận.');
   await renderList();toast('Đã xóa mẫu ma trận.');
  });
 };
 saveBtn.onclick=async()=>{
  try{
   const rows=readMatrixFormRows(document.getElementById('matrix-form'));
   const name=(nameInput.value||'').trim()||`${e.subject} ${e.grade} · ${rows.length} chủ đề`;
   const res=await fetch('/api/matrix-templates',{method:'POST',headers:{'Content-Type':'application/json',...db.workspaceHeaders()},body:JSON.stringify({name,subject:e.subject||'Chưa rõ môn',grade:String(e.grade||'10'),rows})});
   if(!res.ok){const err=await res.json().catch(()=>({}));throw Error(err.detail?.[0]?.msg||err.error||'Chưa lưu được mẫu ma trận.');}
   nameInput.value='';await renderList();toast('Đã lưu mẫu ma trận cá nhân.');
  }catch(error){toast(error.message);}
 };
 void renderList().catch(err=>{list.innerHTML='<p class="hint">'+esc(err.message)+'</p>';});
}
const formatPoints=n=>(n/100).toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2});
function updateMatrixSummary(form){
 if(!form)return;
 const e=exam(),rows=[...form.querySelectorAll('[data-matrix-row]')];
 const eff=effectiveExamTotals(e);
 let commonQ=0,commonFixed=0,commonAuto=0,actualTotal=eff.hasTracks?eff.effectiveCount:e.questions.length;
 const levelReq=[0,0,0,0],trackQ=new Map(),trackFixed=new Map(),trackAuto=new Map(),keys=new Set();
 const issues=[];
 for(const r of rows){
  const topic=(r.querySelector('.topic')?.value||'').trim(),type=r.querySelector('[name=matrix-type]')?.value||'mcq',grp=(r.dataset.choiceGroup||'').trim();
  const key=topic.toLocaleLowerCase('vi-VN')+'|'+type+'|'+grp.toLocaleLowerCase('vi-VN');
  if(!topic)issues.push('Có dòng chưa nhập tên chủ đề.');
  else if(keys.has(key))issues.push(`Trùng chủ đề/loại/nhánh “${topic}”.`);
  keys.add(key);
  const ptInput=r.querySelector('[name=matrix-points]'),lvlInputs=[...r.querySelectorAll('[name=matrix-level-points]')];
  const basePt=ptInput&&!ptInput.disabled&&ptInput.value!==''?Math.round(Number(ptInput.value)*100):null;
  const targets=[...r.querySelectorAll('[data-matrix-target]')];
  targets.forEach((inp,l)=>{
   const n=Math.max(0,Number(inp.value)||0);
   const hintEl=inp.parentElement?.querySelector('.matrix-cell-actual');
   if(hintEl){const act=Number(hintEl.dataset.actual||0);hintEl.classList.toggle('match',act===n);hintEl.classList.toggle('miss',act!==n);}
   let p100=basePt;
   if(lvlInputs.length&&lvlInputs[l]){p100=lvlInputs[l].value!==''?Math.round(Number(lvlInputs[l].value)*100):null;}
   if(p100!=null&&(!Number.isFinite(p100)||p100<5||p100>1000))issues.push(`Điểm/câu “${topic||'chủ đề'}” cần từ 0,05 đến 10,00.`);
   if(!grp)levelReq[l]+=n;
   if(grp){trackQ.set(grp,(trackQ.get(grp)||0)+n);if(p100==null)trackAuto.set(grp,(trackAuto.get(grp)||0)+n);else trackFixed.set(grp,(trackFixed.get(grp)||0)+n*p100);}
   else{commonQ+=n;if(p100==null)commonAuto+=n;else commonFixed+=n*p100;}
  });
 }
 const maxTrackQ=trackQ.size?Math.max(...trackQ.values()):0;
 if(trackQ.size){
  const firstGrp=[...trackQ.keys()][0];
  for(const r of rows)if((r.dataset.choiceGroup||'').trim()===firstGrp)[...r.querySelectorAll('[data-matrix-target]')].forEach((inp,l)=>{levelReq[l]+=Math.max(0,Number(inp.value)||0);});
 }
 const reqTotal=commonQ+maxTrackQ;
 if(reqTotal<1||reqTotal>30)issues.push('Tổng số câu hiệu lực cần từ 1 đến 30.');
 const tracks=trackQ.size?[...trackQ.keys()]:[''];
 let primaryFixed=commonFixed,primaryAuto=commonAuto;
 const trackBadges=[];
 for(const grp of tracks){
  const fixed=commonFixed+(grp?trackFixed.get(grp)||0:0),auto=commonAuto+(grp?trackAuto.get(grp)||0:0),rem=1000-fixed;
  if(grp)primaryFixed=fixed,primaryAuto=auto;
  if(auto&&rem<auto*5)issues.push(`${grp?`Nhánh ${grp}: `:''}Điểm cố định (${formatPoints(fixed)} đ) quá cao, phần tự chia không đủ tối thiểu 0,05 đ/câu.`);
  else if(!auto&&rem!==0&&reqTotal>0)issues.push(`${grp?`Nhánh ${grp}: `:''}Tổng điểm cố định đang là ${formatPoints(fixed)}/10,00 đ (cần đúng 10,00 đ).`);
  if(grp){
   const gTotal=commonQ+(trackQ.get(grp)||0);
   trackBadges.push(`<span class="pill ${(auto&&rem>=auto*5)||rem===0?'ok':'warn'}">Nhánh ${esc(grp)}: ${gTotal} câu · ${auto?`${formatPoints(fixed)} đ + ${auto} ô tự chia`:`${formatPoints(fixed)} đ`}</span>`);
  }
 }
 const ratioSum=Math.max(1,levelReq.reduce((a,b)=>a+b,0));
 const ratioColors=['#1a7a68','#2b6cb0','#d97706','#c53030'];
 const ratioBar=`<div class="matrix-ratio-bar" aria-label="Tỉ lệ mức nhận thức">${LEVELS.map((_,l)=>{const pct=Math.round((levelReq[l]/ratioSum)*100);return pct?`<span style="width:${pct}%;background:${ratioColors[l]}" title="${LEVELS[l]}: ${levelReq[l]} câu (${pct}%)"></span>`:'';}).join('')}</div>`;
 const ratioPills=LEVELS.map((name,l)=>{const pct=reqTotal?Math.round((levelReq[l]/ratioSum)*100):0;return `<span class="matrix-level-chip" style="--lvl-color:${ratioColors[l]}"><i></i><b>${name}</b> ${levelReq[l]} (${pct}%)</span>`;}).join('');
 const pointsStatus=!reqTotal?'Chưa có câu yêu cầu':primaryAuto?(1000-primaryFixed>=primaryAuto*5?`10,00 đ (${formatPoints(primaryFixed)} đ cố định + ${primaryAuto} câu tự chia)`:`${formatPoints(primaryFixed)} / 10,00 đ · Quá 10 đ`):(primaryFixed===1000?'10,00 / 10,00 đ (Chuẩn)':'Lệch '+formatPoints(primaryFixed)+' / 10,00 đ');
 const box=form.querySelector('#matrix-live-summary');
 if(!box)return;
 box.innerHTML=`<div class="matrix-kpi-row"><span class="matrix-kpi ${actualTotal===reqTotal?'is-ok':'is-warn'}"><b>Thực có:</b> ${actualTotal} câu · <b>Yêu cầu:</b> ${reqTotal} câu</span><span class="matrix-kpi ${!issues.length?'is-ok':'is-warn'}"><b>Tổng điểm:</b> ${esc(pointsStatus)}</span><span class="pill ${issues.length?'warn':'preflight-status-ok'}">${issues.length?'Cần điều chỉnh':'Cơ cấu hợp lệ 10,00 đ'}</span></div>${trackBadges.length?`<div class="matrix-track-row">${trackBadges.join('')}</div>`:''}${ratioBar}<div class="matrix-level-chips">${ratioPills}</div>${issues.length?`<div class="alert matrix-live-warning" role="status">${issues.slice(0,3).map(esc).join(' · ')}</div>`:''}`;
}
function showMatrix(){const e=exam(),report=getReverseMatrixReport(e.id,e.revision)||{matrix:e.matrix};modal('Ma trận đề',`<p class="hint">Mỗi ô gồm số câu thực tế (<i>Có X</i>) và số câu yêu cầu. Hỗ trợ điểm thập phân bước <code>0,05</code> (như <code>0,10</code> · <code>0,20</code> · <code>0,40</code> đ/câu) và 2 nhánh tự chọn (<code>+ Nhánh</code>).</p><form id="matrix-form"><div id="matrix-reverse-warnings-host">${reverseMatrixWarningBannerHTML(report)}</div><div class="matrix-table-scroll"><table class="matrix-full"><thead><tr><th>Chủ đề / Nhánh</th><th>Loại câu</th><th>Điểm/câu</th>${LEVELS.map(l=>`<th>${l}</th>`).join('')}<th></th></tr></thead><tbody id="matrix-rows">${matrix(e).map((r,i)=>matrixRow(r.topic,r.targets,r.cells.map(c=>c.actual),i,r,report)).join('')}</tbody></table></div><div class="matrix-actions-bar">${button('matrix-add',icon('plus')+'Thêm chủ đề','ghost','type="button"')}${button('matrix-rebalance','Phân bổ lại về 10,00đ','ghost','type="button"')}${e.questions.length?button('reverse-matrix','↻ Lập ma trận từ đề','ghost','type="button"'):''}<span class="hint">Nhấn <b>+ Nhánh</b> để gán các dòng thuộc nhánh Tự chọn A / Tự chọn B.</span></div><div id="matrix-live-summary" class="matrix-total">Thực có: ${e.questions.length} câu · Yêu cầu: ${e.matrix.flatMap(r=>r.targets).reduce((a,b)=>a+b,0)} câu</div>${unmappedHTML()}<p class="hint">NB = Nhận biết · TH = Thông hiểu · VD = Vận dụng · VDC = Vận dụng cao. Nhãn nhận thức do thầy cô tự gán.</p><label class="consent"><input type="checkbox" id="matrix-confirm" ${e.matrixConfirmed?'checked':''}> Tôi xác nhận cơ cấu này</label>${foot('<button class="primary" type="submit">Lưu ma trận</button>')}</form><div class="toolbar-row">${button('matrix-import','Nhập ma trận JSON')}${button('matrix-export','Tải ma trận JSON')}<button type="button" id="open-matrix-synthesis">Sinh theo ma trận · Python</button></div><details id="matrix-templates-panel"><summary>Mẫu ma trận cá nhân tái sử dụng</summary><div class="matrix-template-save-row"><input id="matrix-template-name" maxlength="160" placeholder="Ví dụ: Giữa kỳ I Toán 9 · Chuẩn 10đ" aria-label="Tên mẫu ma trận"><button type="button" id="matrix-template-save">Lưu mẫu hiện tại</button></div><div id="matrix-templates-list" class="matrix-templates-list"><p class="hint">Đang tải mẫu đã lưu…</p></div></details><small class="hint">JSON: [{"topic":"Chủ đề","targets":[2,1,1]}]. Nhập xong vẫn cần xem và xác nhận.</small>`);const mForm=document.getElementById('matrix-form');mForm.addEventListener('input',()=>updateMatrixSummary(mForm));mForm.addEventListener('change',()=>updateMatrixSummary(mForm));updateMatrixSummary(mForm);document.getElementById('open-matrix-synthesis').onclick=()=>openMatrixSynthesis(mvpContext).catch(error=>toast(error.message));mountMatrixTemplates(e);}
function matrixRow(topic,targets,counts,i,row={},report=null){const ptVal=row.pointsQ4!=null?row.pointsQ4/4:(row.points??'');const lvlPts=row.pointsByLevelQ4||row.pointsByLevel;const lvlScale=row.pointsByLevelQ4?4:1;const grp=row.choiceGroup||'';const flag=rowFlagForReverseReport(report,row);return `<tr data-matrix-row="${i}" ${grp?`data-choice-group="${esc(grp)}"`:''}><td><input class="topic" aria-label="Chủ đề ${i+1}" value="${esc(topic)}" maxlength="80" required placeholder="Tên chủ đề…"><div class="matrix-topic-meta">${grp?`<span class="pill matrix-group-pill">${esc(grp)}</span>`:''}${flag?`<span class="pill warn matrix-row-flag" data-row-flag="${flag.pointConflict?'pointConflict':'needsReview'}">${esc(flag.label)}</span>`:''}<button type="button" class="matrix-group-toggle tiny-btn" data-action="matrix-cycle-group" title="Gắn hoặc đổi nhánh tự chọn">${grp?'Đổi nhánh':'+ Nhánh'}</button></div></td><td><select name="matrix-type" aria-label="Loại câu chủ đề ${i+1}">${Object.entries(QUESTION_TYPES).map(([key,label])=>`<option value="${key}" ${(row.type||'mcq')===key?'selected':''}>${label}</option>`).join('')}</select></td><td><input name="matrix-points" aria-label="Điểm mỗi câu chủ đề ${i+1}" type="number" min="0.05" max="10" step="0.05" placeholder="Tự chia" value="${ptVal}" ${lvlPts?'disabled':''}></td>${LEVELS.map((_,l)=>`<td><div class="hint matrix-cell-actual ${counts[l]===(targets[l]||0)?'match':'miss'}" data-actual="${counts[l]}">Có ${counts[l]}</div><input aria-label="${LEVELS[l]} chủ đề ${i+1}" data-matrix-target type="number" min="0" max="30" value="${targets[l]||0}" required>${lvlPts?`<label class="hint matrix-lvl-pt">Điểm/câu<input name="matrix-level-points" type="number" min="0.05" max="10" step="0.05" value="${lvlPts[l]==null?'':lvlPts[l]/lvlScale}"></label>`:''}</td>`).join('')}<td>${button('matrix-remove',icon('trash'),'icon ghost','type="button" aria-label="Xóa dòng ma trận"')}</td></tr>`;}
function showMetadata(){const e=exam(),prof=state.teacherProfile||{};modal('Thông tin đề',`<form id="meta-form"><label>Tên đề</label><input name="title" value="${esc(e.title)}" required maxlength="180"><label>Sở / Phòng GD&amp;ĐT / Đơn vị quản lý</label><input name="department" value="${esc(e.department??prof.department??'')}" maxlength="180" placeholder="Ví dụ: PHÒNG GIÁO DỤC VÀ ĐÀO TẠO"><label>Đơn vị / trường</label><input name="school" value="${esc(e.school||prof.school||'')}" required maxlength="180"><div class="grid3"><div><label>Môn</label><input name="subject" value="${esc(e.subject)}" required maxlength="80"></div><div><label>Lớp</label><input name="grade" value="${esc(e.grade)}" required maxlength="40"></div><div><label>Thời gian (phút)</label><input name="minutes" type="number" min="1" max="300" value="${e.minutes}" required></div></div><label>Trạng thái quy trình đề</label><select name="workflowStatus">${Object.entries(WORKFLOW_STATUS_LABELS).map(([k,lbl])=>`<option value="${k}" ${normalizeWorkflowStatus(e.workflowStatus)===k?'selected':''}>${lbl}</option>`).join('')}</select><label class="consent"><input type="checkbox" name="saveProfileDefault"> Lưu đơn vị/trường làm mặc định cho đề mới</label><label>Hướng dẫn làm bài</label><textarea name="instructions" rows="3">${esc(e.instructions)}</textarea>${foot('<button type="submit" class="primary">Lưu thông tin</button>')}</form>`);}
function showQuestionMeta(id){const e=exam(),q=qget(id);if(!q)return;modal('Thông tin câu '+(e.questions.indexOf(q)+1),`<form id="q-meta-form" data-id="${q.id}"><div class="grid2"><div><label>Chủ đề</label><input name="topic" value="${esc(q.topic)}" list="topics" required maxlength="80"><datalist id="topics">${e.matrix.map(r=>`<option>${esc(r.topic)}</option>`).join('')}</datalist></div><div><label>Mức nhận thức (thầy cô gán)</label><select name="level">${LEVELS.map((l,i)=>`<option value="${i}" ${i===q.level?'selected':''}>${l}</option>`).join('')}</select></div></div><label>Tài liệu căn cứ</label><select name="docId"><option value="">Chưa gắn nguồn</option>${e.docs.map(d=>`<option value="${d.id}" ${q.source?.docId===d.id?'selected':''}>${esc(d.name)}</option>`).join('')}</select><label>Vị trí trong nguồn (thầy cô nhập)</label><input name="location" value="${esc(q.source?.location||'')}" maxlength="180"><label>Loại câu hỏi</label><select name="type">${Object.entries(QUESTION_TYPES).map(([key,label])=>`<option value="${key}" ${q.type===key?'selected':''}>${label}</option>`).join('')}</select><label>Điểm</label><input name="points" type="number" min="0.05" max="10" step="0.05" value="${q.points||1}"><label class="consent"><input type="checkbox" name="lockPosition" ${q.lockPosition?'checked':''}> Giữ nguyên vị trí khi trộn mã đề</label>${q.type==='mcq'?'<label>Đáp án lưu (trắc nghiệm)</label><select name="answer">':'<p class="hint">Sửa đáp án đúng–sai/ngắn ở tab Đáp án trên trang đề.</p>'}${q.type==='mcq'?`${q.answerKnown===false?'<option value="" selected>Chưa xác nhận</option>':''}${q.options.map((o,i)=>`<option value="${i}" ${q.answer===i&&q.answerKnown!==false?'selected':''}>${String.fromCharCode(65+i)}. ${esc(o)}</option>`).join('')}</select>`:''}<label>Giải thích</label><textarea name="explanation" rows="3">${esc(q.explanation)}</textarea><div class="hint">Liên kết do thầy cô chọn. Hệ thống không tự xác nhận nguồn hỗ trợ nội dung câu hỏi.</div>${q.rule?.startsWith('math-')?'<div class="alert">Phép kiểm Toán chỉ hỗ trợ đúng dạng câu mẫu. Có thể đổi các số trong câu; dạng chưa hỗ trợ sẽ báo chưa giải lại nội dung. Không dùng AI.</div>':q.rule?'<div class="alert">Câu này dùng phép tính liên kết với Bảng 1. Sửa thân câu thủ công sẽ ngừng phép giải theo mẫu; bảng vẫn giữ liên kết dữ kiện.</div>':''}${foot(button('delete-question','Xóa câu','danger',`type="button" data-id="${q.id}"`)+button('move-up','↑ Đưa lên','',`type="button" data-id="${q.id}" ${e.questions.indexOf(q)===0?'disabled':''}`)+button('move-down','↓ Đưa xuống','',`type="button" data-id="${q.id}" ${e.questions.indexOf(q)===e.questions.length-1?'disabled':''}`)+'<button class="primary" type="submit">Lưu câu</button>')}</form>`);}
function showReplace(sampleMode=false){const s=currentScope();if(!s){toast('Thêm hoặc chọn một câu trước.');return;}if(s.field&&s.field!=='stem'){toast('Chọn thân câu để dùng lệnh thay đoạn. Có thể sửa lời giải hoặc phương án trực tiếp trên trang.');return;}const q=qget(s.id);pending={...s,type:'replace'};const suggestion=sampleMode?(q.rule==='math-square'?s.text.replace(/=\s*[−-]?\d+/, '= −9'):q.rule==='max'?'Khu vực nào có nhiều người sử dụng thư viện nhất theo Bảng 1?':q.rule==='difference'?'Theo Bảng 1, chênh lệch số người sử dụng thư viện giữa khu vực B và A là bao nhiêu?':s.text.replace(/^Theo tư liệu, /,'').replace(/^Ngữ liệu lấy bối cảnh ở đâu\?$/,'Câu chuyện diễn ra ở đâu?')):s.text;
 modal(sampleMode?'Thử gợi ý mẫu':'Sửa phần đã chọn',`<div class="scope"><small>CÂU ${exam().questions.indexOf(q)+1} · v${q.v} · ${s.start===0&&s.end===q.stem.length?'TOÀN BỘ THÂN CÂU':'ĐOẠN ĐƯỢC CHỌN'}</small><div class="read-formula">${richTextHTML(s.text)}</div></div>${sampleMode?'<div class="alert">Gợi ý dựng sẵn để thử luồng duyệt thay đổi. Đây không phải câu trả lời từ AI.</div>':'<p class="hint">Nhập nội dung thay thế. Thầy cô sẽ xem trước thay đổi trước khi áp dụng.</p>'}<label for="replacement">Nội dung thay thế</label><textarea id="replacement" rows="4">${esc(suggestion)}</textarea>${foot(button('preview-replace','Xem thay đổi','primary'))}`);}
function previewReplace(value){
 const scope=pending;
 if(scope?.type!=='replace')return;
 const q=qget(scope.id);
 if(scope.field&&scope.field!=='stem'){toast('Chọn thân câu để dùng lệnh thay đoạn.');return;}
 if(!q||q.v!==scope.version||q.stem.slice(scope.start,scope.end)!==scope.text){
  toast('Câu đã đổi phiên bản. Vui lòng chọn lại đoạn cần sửa.');return;
 }
 if(value===scope.text){toast('Nội dung chưa thay đổi.');return;}
 const next=q.stem.slice(0,scope.start)+value+q.stem.slice(scope.end);
 try{validateMath(next);}catch(error){toast('Công thức chưa hợp lệ trong thân câu mới. Kiểm tra cú pháp hoặc dấu đóng. '+error.message);return;}
 pending={...scope,next,examId:exam().id};
 modal('Xem thay đổi trước khi áp dụng',`<div class="diff manual-diff diff-side-by-side"><div class="diff-col"><span class="diff-col-label">TRƯỚC</span><del>${richTextHTML(q.stem)}</del></div><div class="diff-col"><span class="diff-col-label">SAU</span><ins>${richTextHTML(next)}</ins></div></div><div class="alert">Phạm vi: thân câu ${exam().questions.indexOf(q)+1}. Đáp án và giải thích được giữ để thầy cô rà soát; trạng thái duyệt cũ hết hiệu lực.${q.rule?.startsWith('math-')?' Phép kiểm Toán đọc lại dữ kiện từ thân câu nếu dạng mới được hỗ trợ.':q.rule?' Phép giải theo câu mẫu sẽ dừng sau khi đổi nội dung.':''} Các câu khác và ngữ liệu đã chọn không thay đổi.</div>${foot(button('close','✕ Bỏ đề xuất')+button('apply-replace','Xác nhận thay đổi','primary'))}`);
}
function showData(){const e=exam();if(!e.data.length){modal('Dữ kiện của đề Toán','<p class="hint">Các dữ kiện nằm trực tiếp trong câu hỏi. Thầy cô sửa số ngay trên trang đề, ví dụ x² = 9 thành x² = −9. Phép kiểm đọc nội dung hiện tại cho các dạng được hỗ trợ.</p>');return;}modal('Dữ kiện dùng chung cho bảng & biểu đồ',`<p class="hint">Dữ liệu minh họa tự tạo, không phải khảo sát thực. Một lần cập nhật sẽ đổi bảng, cột biểu đồ và rà soát các câu đang liên kết.</p><form id="data-form" data-exam="${esc(e.id)}" data-revision="${e.revision}"><table><tr><th>Khu vực</th><th>Số người</th></tr>${e.data.map((d,i)=>`<tr><td>${esc(d.label)}</td><td><input class="data-value" aria-label="Số người ${esc(d.label)}" data-data-index="${i}" type="number" min="0" max="1000000" step="1" value="${d.value}" required></td></tr>`).join('')}</table><div class="alert">Đáp án không tự chốt theo số mới. Hệ thống tính lại, báo bất đồng hoặc phương án chưa khớp; thầy cô xem đề xuất sửa rồi duyệt.</div>${foot('<button type="submit" class="primary">Xem ảnh hưởng</button>')}</form>`);}
function showDataPreview(values){const e=exam(),test=planDataUpdate(e,values);if(!test)return toast('Dữ kiện chưa thay đổi.');pending={type:'data',update:test,examId:e.id,revision:e.revision};modal('Xem ảnh hưởng khi đổi dữ kiện',`<div class="diff"><del>${e.data.map(d=>`${esc(d.label)}: ${d.value}`).join(' · ')}</del><ins>${test.data.map(d=>`${esc(d.label)}: ${d.value}`).join(' · ')}</ins></div><h3>Phần sẽ cập nhật</h3><p class="hint">Bảng 1, biểu đồ cột và trạng thái các câu liên kết. Giữ nguyên nội dung các câu khác và đoạn trích đã duyệt.</p>${test.questions.filter(usesTable).map(q=>`<div class="small-card"><b>Câu ${test.questions.indexOf(q)+1} · ${statusText(q)}</b><p>${esc(q.check.evidence)}</p>${q.check.problems.length?`<p>${esc(q.check.problems.join(' '))}</p>`:''}</div>`).join('')}${foot(button('apply-data','Xác nhận cập nhật','primary'))}`);}
function runCheck(id){change('Kiểm tra câu '+(exam().questions.findIndex(q=>q.id===id)+1),e=>check(e,e.questions.find(q=>q.id===id)));showReview(id);}
function questionCitationBlocks(e,q){
 const citationOptions={
  currentSource:q.source,
  questionVersion:q.v,
  currentQuoteText:q.quote?e.quote?.text:undefined,
  chosenQuoteId:q.quote?e.quote?.chosen:undefined,
 };
 if(Array.isArray(q.evidence)&&q.evidence.length)return q.evidence.map(ev=>citationContextHTML(ev,e.docs,citationOptions)).join('');
 if(q.source?.docId||q.source?.quote){
  const doc=e.docs.find(d=>d.id===q.source.docId);
  const page=Number(q.source.page)||1;
  const parsedSrcVer=Number(q.source.version);
  const srcVer=Number.isFinite(parsedSrcVer)&&parsedSrcVer>=1?parsedSrcVer:1;
  return citationContextHTML({
   sourceId:q.source.docId||'unknown',
   sourceVersion:srcVer,
   locator:{kind:'page',index:page},
   quote:q.source.quote||doc?.pages?.find(p=>p.number===page)?.text?.slice(0,140)||doc?.text?.slice(0,140)||q.source.location||'',
  },e.docs,{
   ...citationOptions,
   currentSource:q.source?.docId?q.source:undefined,
  });
 }
 return '';
}
function showReview(id){const e=exam(),q=qget(id);if(!q)return;const c=q.check?.version===q.v?q.check:null;const d=derive(e,q);const citations=questionCitationBlocks(e,q);modal('Rà soát câu '+(e.questions.indexOf(q)+1),`<div class="scope"><small>CÂU v${q.v}</small><div class="read-formula">${richTextHTML(q.stem)}</div></div>${c?`<div class="alert ${c.status==='review'?'':'success'}"><b>${statusText(q,e)}</b><br>${esc(c.problems.join(' ')||c.evidence)}</div><p class="hint">${esc(c.method||'Thầy cô tự duyệt')} · Lần kiểm tra ${date(c.at)} · Gắn với câu v${c.version}</p><h3>Căn cứ của phép kiểm</h3><p>${esc(c.evidence)}</p>`:'<div class="alert">Bản hiện tại chưa kiểm tra. Kết quả cũ không được dùng cho phiên bản mới.</div>'}${citations?`<div class="review-citations"><h3>Đối chiếu trích dẫn nguồn</h3>${citations}</div>`:''}${usesTable(q)?dataHTML():''}<div class="toolbar-row">${button('source',icon('link')+'Mở nguồn','',`data-id="${id}"`)}${button('check-one','Kiểm tra lại','',`data-id="${id}"`)}</div>${d&&(!d.error||d.result!==undefined)?`<div class="small-card"><b>Đề xuất sửa có căn cứ phép tính</b><p>${esc(d.explanation)}${d.answer===null?' Cần thay một phương án để chứa kết quả này.':''}</p>${button('repair-preview','Xem đề xuất sửa','',`data-id="${id}"`)}</div>`:''}<p class="hint">Phép kiểm này không đánh giá mọi khía cạnh kiến thức, cách diễn đạt hoặc mức nhận thức. Thầy cô quyết định bản dùng.</p>${foot(button('approve-question','Tôi đã rà soát · duyệt câu','primary',`data-id="${id}" data-version="${q.v}"`))}`);}
function showRepair(id){const e=exam(),q=qget(id),d=derive(e,q);if(!d||d.error&&d.result===undefined){toast('Cần sửa thủ công câu hoặc phương án trước.');return;}const options=clone(q.options);let answer=d.answer;if(answer===null){answer=0;options[0]=d.replacement??d.result+' người';}pending={type:'repair',id,version:q.v,answer,options,explanation:d.explanation};modal('Đề xuất sửa theo phép tính',`<p class="hint">Câu ${e.questions.indexOf(q)+1} · v${q.v}. Chỉ cập nhật đáp án, giải thích và phương án cần thiết của câu này.</p><div class="diff"><del>Đáp án: ${String.fromCharCode(65+q.answer)}\n${richTextHTML(q.explanation)}${d.answer===null?'\nA. '+richTextHTML(q.options[0]):''}</del><ins>Đáp án: ${String.fromCharCode(65+answer)}\n${richTextHTML(d.explanation)}${d.answer===null?'\nA. '+richTextHTML(options[0]):''}</ins></div><div class="alert">Sau khi áp dụng, công cụ tính lại từ dữ kiện và lưu kết quả ở phiên bản mới. Thầy cô vẫn cần duyệt nội dung.</div>${foot(button('apply-repair','Áp dụng & kiểm tra lại','primary'))}`);}
async function showSource(docId,qid){const e=exam(),q=qget(qid);const doc=e.docs.find(d=>d.id===(docId||q?.source?.docId));if(!doc){modal('Nguồn của câu hỏi','<p class="hint">Chưa gắn tài liệu cho câu này. Thầy cô có thể thêm tài liệu và chọn nguồn trong thuộc tính câu.</p>'+foot(button('import-doc','Thêm tài liệu','primary')));return;}
 const original=doc.fileId?await db.get('file:'+doc.fileId):null;modal('Tài liệu căn cứ',`<h3>${esc(doc.name)}</h3><p class="hint">${esc(q?.source?.location||doc.location||'Toàn bộ tài liệu')}${doc.sample?' · Ngữ liệu minh họa do nhóm tự soạn':''}</p>${doc.kind==='text'?`<div class="source-preview">${esc(doc.text)}</div>`:original?`<div class="alert">Tệp gốc đã lưu tại máy. Chưa rút trích hoặc sinh câu bằng AI.</div>${doc.kind==='image'?`<img class="source-frame" src="${original}" alt="Bản gốc ${esc(doc.name)}">`:doc.kind==='pdf'?`<iframe class="source-frame" title="PDF gốc" src="${original}"></iframe>`:'<p class="hint">Trình xem slide chưa kết nối. Tải tệp gốc để mở bằng phần mềm trình chiếu.</p>'}`:'<div class="alert">Không tìm thấy tệp gốc trong trình duyệt này.</div>'}${original?foot(button('download-original','Tải tệp gốc','',`data-doc="${doc.id}"`)):''}${q?`<p class="hint">Liên kết nguồn giúp đối chiếu vị trí. Hệ thống chưa xác minh nội dung câu hỏi dựa đủ vào nguồn này.</p>`:''}`);}
function showImport(){modal('Thêm tài liệu',`<p class="hint">Tài liệu được lưu tại trình duyệt này. Chưa gửi đi dịch vụ ngoài.</p><div class="upload-zone"><label for="doc-file">Chọn tệp TXT, MD, PDF, PPTX hoặc ảnh</label><input id="doc-file" type="file" accept=".txt,.md,.pdf,.pptx,.png,.jpg,.jpeg,.webp"><p class="hint">Tối đa 15 MB/tệp. TXT/MD đọc được ngay. PDF/PPTX/ảnh chỉ lưu bản gốc khi chưa có kết nối.</p></div><div class="alert">Chưa kết nối AI: hệ thống không tự sinh câu từ tệp vừa tải. Có thể đọc văn bản, thêm câu bằng tay và gắn nguồn.</div><h3>Hoặc dán nội dung</h3><form id="paste-doc-form"><label>Tên tài liệu</label><input name="name" placeholder="Ví dụ: Bài 3 — Đô thị hóa" required maxlength="180"><label>Nội dung tư liệu</label><textarea name="text" rows="6" required maxlength="1000000"></textarea>${foot('<button class="primary" type="submit">Lưu tư liệu tại máy</button>')}</form>`);}
function prefScopeLabel(p){
 const s=p?.scopeType||'all';
 if(s==='subject')return p.subject?`Môn ${p.subject}`:'Môn cụ thể';
 if(s==='subject_grade')return [p.subject||'',p.grade?'Lớp '+p.grade:''].filter(Boolean).join(' · ')||'Môn & lớp';
 return 'Mọi môn & lớp';
}
function showMemory(){const e=exam();modal('Cách ra đề của thầy cô',`<p class="hint">Chỉ lưu những yêu cầu thầy cô xác nhận và gắn phạm vi (môn/lớp) để tránh rò quy tắc sang môn khác.</p>${state.prefs.length?state.prefs.map(p=>`<div class="preference-row"><div class="row"><span class="grow"><b>${esc(p.text)}</b><p class="hint" style="margin-bottom:0">${isConfirmedPreference(p)?'Đã xác nhận':'Chưa xác nhận'} · Phạm vi: <b>${esc(prefScopeLabel(p))}</b></p></span>${button('edit-pref','Sửa','',`data-id="${p.id}"`)}${button('delete-pref',icon('trash'),'icon danger',`data-id="${p.id}" aria-label="Xóa yêu cầu"`)}</div></div>`).join(''):empty('Chưa có yêu cầu dùng lâu dài.')}<form id="pref-form"><label for="pref-text">Yêu cầu muốn dùng lại</label><textarea id="pref-text" rows="3" required placeholder="Ví dụ: Câu hỏi ngắn, tránh dùng phủ định kép." maxlength="500"></textarea><div class="grid3"><div><label for="pref-scope-type">Phạm vi áp dụng</label><select id="pref-scope-type" name="scopeType"><option value="all">Mọi môn &amp; mọi lớp</option><option value="subject">Theo môn</option><option value="subject_grade">Đúng môn &amp; lớp</option></select></div><div><label for="pref-scope-subject">Môn</label><input id="pref-scope-subject" name="subject" value="${esc(e.subject||'')}" maxlength="80" placeholder="Ví dụ: Toán"></div><div><label for="pref-scope-grade">Lớp</label><input id="pref-scope-grade" name="grade" value="${esc(e.grade||'')}" maxlength="40" placeholder="Ví dụ: 9"></div></div><label>Cách áp dụng khi rà soát đề mới</label><select id="pref-kind"><option value="instruction">Lưu làm yêu cầu biên soạn</option><option value="short">Nhắc khi thân câu dài hơn 30 từ</option></select><label><input id="pref-confirm" type="checkbox" required style="width:auto"> Tôi xác nhận dùng yêu cầu này cho những đề sau</label>${foot('<button type="submit" class="primary">Xác nhận & ghi nhớ</button>')}</form><div class="alert success">Đề hiện tại đang áp dụng ${e.appliedPrefs.filter(isConfirmedPreference).length} yêu cầu phù hợp phạm vi (${esc(e.subject)} · Lớp ${esc(e.grade)}).</div>${foot(button('apply-prefs-current','Áp dụng các yêu cầu khớp phạm vi cho đề này'))}`);}
function showQuotes(){const e=exam();modal('Tìm nguồn & đối chiếu đoạn trích',`<div class="toolbar-row">${button('web-search','Tìm các bản trên web')}${button('add-variant','Thêm bản để đối chiếu')}</div><div class="alert">Có thể bấm tìm nguồn để truy vấn dịch vụ đã cấu hình. Các bản dưới đây là ${e.quote.versions.some(v=>v.external)?'nội dung nhập tay và ví dụ mẫu':'ví dụ tự soạn hoặc nội dung nhập tay'}, không phải kết quả vừa tìm trên mạng. Khác biệt không mặc nhiên là lỗi.</div><label>Đoạn đang dùng trong đề ${e.quote.chosen?'· đã được giáo viên chọn':''}</label><div class="source-preview">${esc(e.quote.text||'Chưa có đoạn trích')}</div><p class="hint">Các từ, dấu câu và xuống dòng khác so với đoạn đang dùng được tô vàng. Phần bị lược trong một bản sẽ thấy ở bản đối chiếu. Thầy cô quyết định bản phù hợp.</p><div class="grid2">${e.quote.versions.map(v=>`<div class="variant"><div class="row space"><b>${esc(v.label)}</b>${e.quote.chosen===v.id?'<span class="pill">Đang dùng</span>':''}</div><div class="version-text">${diffText(e.quote.text,v.text)}</div><p class="hint">${esc(v.location||'Người dùng nhập')} · ${v.webRetrieved?'Đã truy cập web, chưa xác minh bản chuẩn':v.external?'Nguồn do người dùng nhập, chưa xác minh':'Ngữ liệu tự soạn minh họa'}</p><div class="row">${v.docId?button('source','Mở nguồn','tiny-btn',`data-doc="${v.docId}" data-page="${Number.isInteger(v.page)&&v.page>0?v.page:1}"`):v.url?`<a href="${esc(v.url)}" target="_blank" rel="noopener noreferrer">Mở nguồn đã nhập</a>`:''}${button('choose-variant','Chọn bản này','tiny-btn',`data-id="${v.id}"`)}</div></div>`).join('')}</div>`);}
function diffText(a,b){const aa=a.match(/\s+|[\p{L}\p{N}]+|[^\s\p{L}\p{N}]/gu)||[],bb=b.match(/\s+|[\p{L}\p{N}]+|[^\s\p{L}\p{N}]/gu)||[];if(aa.length*bb.length>200000)return esc(b)+'<p class="hint">Văn bản dài: thu ngắn hai bản để tô khác biệt.</p>';const dp=Array.from({length:aa.length+1},()=>new Uint16Array(bb.length+1));for(let i=aa.length-1;i>=0;i--)for(let j=bb.length-1;j>=0;j--)dp[i][j]=aa[i]===bb[j]?1+dp[i+1][j+1]:Math.max(dp[i+1][j],dp[i][j+1]);const same=new Set();let i=0,j=0;while(i<aa.length&&j<bb.length){if(aa[i]===bb[j]){same.add(j);i++;j++;}else if(dp[i+1][j]>=dp[i][j+1])i++;else j++;}return bb.map((t,i)=>same.has(i)?esc(t):`<mark>${esc(t).replace(/\n/g,'↵<br>')}</mark>`).join('');}
function showAddVariant(){modal('Thêm bản đối chiếu',`<p class="hint">Dán bản thầy cô đã tìm được, ghi nguồn và vị trí. Hệ thống chỉ đối chiếu văn bản; chưa xác minh tác giả hay độ tin cậy.</p><form id="variant-form"><label>Tên bản / ấn bản</label><input name="label" required maxlength="120"><label>Nội dung đoạn trích</label><textarea name="text" rows="7" required maxlength="6000"></textarea><label>Nguồn web (nếu có, https://…)</label><input name="url" type="url" placeholder="https://…"><label>Hoặc tài liệu đã nhập</label><select name="docId"><option value="">Không gắn tệp</option>${exam().docs.map(d=>`<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select><label>Vị trí / ghi chú</label><input name="location" required maxlength="180">${foot('<button type="submit" class="primary">Thêm & đối chiếu</button>')}</form>`);}
function showHistory(){const e=exam();modal('Lịch sử của đề',`<p class="hint">Mỗi thay đổi lưu cả nội dung và phần phụ thuộc. Khôi phục tạo thêm một mốc lịch sử; vẫn có thể hoàn tác.</p>${e.history.length?[...e.history].reverse().slice(0,50).map(h=>`<div class="history-row"><b>${esc(h.label)}</b><small>${date(h.at)} · Bản đề ${h.revision} · ${h.state.questions.length} câu</small><div class="buttons">${button('rename-history','Đặt tên mốc','ghost',`data-id="${h.id}"`)}${button('restore','Xem bản này','',`data-id="${h.id}"`)}</div></div>`).join(''):empty('Chưa có thay đổi. Hãy sửa một câu để tạo mốc lịch sử.')}`);}
function showExport(){modal('Xuất đề đang soạn',`<p class="hint">Bản xuất lấy trực tiếp từ nội dung hiện tại. Thầy cô có thể tải HTML, mở và chọn In / Lưu PDF trong trình duyệt.</p><div class="grid2"><div class="choice-card"><h3>Bản học sinh</h3><p>Câu hỏi, phương án, bảng và ngữ liệu. Không chứa đáp án, giải thích hoặc hội thoại.</p>${button('export-html','Tải bản học sinh','primary','data-teacher="false"')}${button('save-local','Lưu tệp tại máy','','data-teacher="false"')}${button('print','Xem / In','ghost','data-teacher="false"')}</div><div class="choice-card"><h3>Bản giáo viên</h3><p>Thêm đáp án lưu, giải thích, vị trí nguồn và trạng thái kiểm tra của từng câu.</p>${button('export-html','Tải bản giáo viên','','data-teacher="true"')}${button('save-local','Lưu tệp tại máy','','data-teacher="true"')}${button('print','Xem / In','ghost','data-teacher="true"')}</div></div><div class="alert">${exam().questions.filter(q=>statusClass(q)!=='approved').length} câu chưa được giáo viên duyệt. Bản xuất giữ nguyên trạng thái nội dung, không tự sửa đáp án.</div><p class="hint">Chưa hỗ trợ DOCX. HTML tải về là tệp HTML đúng định dạng. Lưu PDF qua hộp thoại in.</p>${foot(button('backup-local','Lưu bản sao JSON tại máy')+button('backup','Tải bản sao dữ liệu JSON'))}`);}
function showConnections(){modal('Kết nối & dữ liệu',`<div class="config-row"><div><strong>Soạn đề tại máy</strong><p>Sửa, lưu, ma trận, lịch sử, đối chiếu văn bản và xuất HTML.</p></div><span class="pill">Đang hoạt động</span></div>${[['Sinh & sửa câu bằng AI','Cần cấu hình máy chủ mô hình hoặc dịch vụ được cho phép.'],['Giải lại bằng AI theo phiên bản','Hiện chỉ có phép tính bảng và kiểm tra cấu trúc tại máy.'],['Rút trích PDF, slide và ảnh scan','Hiện lưu tệp gốc, đối chiếu và nhập văn bản bằng tay.'],['Tìm các bản trên web','Hiện đối chiếu các bản mẫu hoặc bản thầy cô dán vào.']].map(([t,d])=>`<div class="config-row"><div><strong>${t}</strong><p>${d}</p></div><span class="pill warn">Chưa kết nối</span></div>`).join('')}<p class="hint" style="margin-top:20px">Hệ thống chỉ kết nối máy chủ tại máy để mở và lưu bản xuất, không gửi dữ liệu ra dịch vụ ngoài. Dữ liệu nằm trong bộ nhớ cục bộ của trình duyệt, theo địa chỉ mở trang web. Xóa dữ liệu trình duyệt sẽ xóa bản lưu tại đây; nên tải bản sao JSON.</p>`);}
async function showExtract(docId){const docs=exam().docs.filter(d=>d.kind==='image'||d.kind==='pdf');const d=docs.find(d=>d.id===docId)||docs[0];const original=d?.fileId?await db.get('file:'+d.fileId):null;modal('Rút trích đề thi',`<div class="alert">Chưa kết nối nhận dạng ảnh/scan. Thầy cô có thể đối chiếu bản gốc và gõ hoặc dán nội dung thủ công; hệ thống không tự báo đã nhận dạng.</div><div class="toolbar-row">${button('import-doc','Thêm ảnh / PDF gốc')}${docs.length?`<select id="scan-doc" aria-label="Chọn bản gốc">${docs.map(x=>`<option value="${x.id}" ${x.id===d?.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select>`:''}</div><div class="scan-layout"><div><h3>Bản gốc</h3>${original?d.kind==='image'?`<img class="source-frame" src="${original}" alt="Ảnh đề gốc">`:`<iframe class="source-frame" title="PDF đề gốc" src="${original}"></iframe>`:empty('Thêm ảnh hoặc PDF để đối chiếu tại đây.')}</div><div><h3>Văn bản nhập thủ công</h3><form id="scan-form" data-doc="${d?.id||''}"><textarea name="text" rows="12" required aria-label="Văn bản đối chiếu bản gốc" placeholder="Gõ lại nội dung tại đây. Dùng [chưa rõ: …] để đánh dấu chỗ cần xem bản gốc.">${esc(d?.manualText||'')}</textarea><p class="hint">Các chỗ [chưa rõ: …] được giữ trong tư liệu để thầy cô rà soát.</p><button class="primary" type="submit">Lưu bản nhập tay</button></form></div></div>`);}
function download(name,content,type){const a=document.createElement('a');const url=URL.createObjectURL(new Blob([content],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}
function safeName(s){return s.replace(/[<>:"/\\|?*\x00-\x1f]/g,'-').slice(0,100);}
async function backup(){flushEditor();await saveChain.catch(()=>{});const saved=clone(state),ids=new Set(),stack=[saved];while(stack.length){const item=stack.pop();if(!item||typeof item!=='object')continue;if(item.fileId)ids.add(item.fileId);stack.push(...Object.values(item).filter(v=>v&&typeof v==='object'));}const [files,curriculumSources,matrixTemplates,questionBank]=await Promise.all([db.allFiles(ids),db.allPersonalLessons(),db.allMatrixTemplates(),db.allQuestionBank()]);if([...ids].some(id=>!files[id]))throw Error('Chưa tải đủ tệp gốc (kể cả lịch sử/hoàn tác). Kết nối lại rồi sao lưu; chưa tạo bản thiếu tệp.');const data={format:'tro-ly-soan-de',version:1,savedAt:new Date().toISOString(),state:saved,files,...(curriculumSources?{curriculumSources}:{}),...(matrixTemplates?.length?{matrixTemplates}:{}),...(questionBank?{questionBank}:{})},content=JSON.stringify(data,null,2);if(new Blob([content]).size>150*1024*1024)throw Error('Bản sao vượt 150MB. Tách bớt tài liệu trước khi sao lưu.');download('Ban-sao-tro-ly-soan-de.json',content,'application/json');toast(curriculumSources===null&&questionBank===null?'Đã tải bản sao đề và tệp gốc. Kho học liệu và ngân hàng câu hỏi chưa có trong bản sao.':db.hasPendingWrites()?'Đã tải bản sao gồm cả nháp chưa đồng bộ':'Đã tải bản sao đề, tệp gốc, học liệu và ngân hàng câu hỏi.');}
async function saveLocal(payload){const response=await fetch('/api/save-export',{method:'POST',headers:{'Content-Type':'application/json',...db.workspaceHeaders()},body:JSON.stringify(payload)});if(!response.ok)throw Error(await response.text());const result=await response.json();modal('Tệp đã lưu tại máy',`<div class="alert success">Đã ghi tệp thật: ${esc(result.filename)} · ${result.bytes.toLocaleString('vi-VN')} byte</div><p class="hint">Tệp nằm trong thư mục xuất bản tại máy. Bản HTML có thể mở để in hoặc lưu PDF.</p><a class="saved-export-link" href="${esc(result.url)}" target="_blank" rel="noopener">Mở tệp vừa lưu</a>${foot(button('export','Quay lại xuất đề'))}`);}
function chooseFile(accept,callback){const input=document.createElement('input');input.type='file';input.accept=accept;input.onchange=()=>{if(input.files[0])Promise.resolve(callback(input.files[0])).catch(err=>toast(err.message));};input.click();}
async function importFile(file){if(file&&/\.xlsx?$/i.test(file.name||''))throw Error('Tệp Excel (.xlsx) dùng để nhập Ma trận đề. Hãy mở mục Ma trận ở thanh bên trái và chọn Nhập Excel / JSON.');if(file.size>15*1024*1024)throw Error('Tệp lớn hơn 15 MB. Chọn tệp nhỏ hơn.');const ext=file.name.split('.').pop().toLowerCase();if(!['txt','md','pdf','pptx','png','jpg','jpeg','webp'].includes(ext))throw Error('Định dạng chưa hỗ trợ.');const id=uid();let d={id,name:file.name,sample:false};if(['txt','md'].includes(ext)){d.kind='text';d.text=await file.text();}else{d.kind=ext==='pdf'?'pdf':ext==='pptx'?'slides':'image';d.fileId=uid();const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error('Không đọc được tệp'));r.readAsDataURL(file);});await db.put('file:'+d.fileId,data);}change('Thêm tài liệu '+d.name,e=>e.docs.push(d));tab='outline';render();await showSource(d.id);toast(d.kind==='text'?'Đã đọc nội dung văn bản tại máy':'Đã lưu tệp gốc · chưa rút trích nội dung');}
// Only declarative data is restored from backups. No HTML or code is executed.

const commitBeforeAction=new Set(['ai-check','approve-question','toggle-approve-question','duplicate-question','quick-move-up','quick-move-down','quick-formula','quick-image','quick-table','quick-figure','quick-audio','exam-audio','insert-audio','set-mcq-answer','reverse-matrix','apply-block-patch','show-block-diff','undo','redo','view-student','view-teacher','export','export-html','print','save-local','backup','backup-local','save-to-bank','save-all-to-bank','exam-analytics','exam-rooms','export-omr-student','export-omr-teacher','export-omr-pdf']);
async function handleAction(a,n){
 if(commitBeforeAction.has(a)&&!flushEditor()){toast('Gõ xong chữ đang nhập rồi thử lại.');return;}
 if(['design-home','design-workspace','library','question-bank','exam-rooms','exam-analytics'].includes(a)){activeRailNav=a;setActiveWorkspaceNav(a);}
 if(a==='design-home'){viewMode='home';activeRailNav='design-home';syncHomeUrl('home');render();return;}
 if(a==='design-workspace'){viewMode='workspace';activeRailNav='design-workspace';syncHomeUrl('workspace');assistantOpen=false;render();$('.workspace')?.classList.remove('focus-mode','outline-collapsed','mobile-ai-view');$('aside.assistant')?.classList.remove('open');return;}
 if(await handleHomeAction(a,n,mvpContext))return;
 const stayHome=new Set(['close','close-top-modal','open-proactive-center','open-new-campaign','open-new-reminder','library','library-tab','library-select-all','library-batch-duplicate','library-batch-export','library-batch-delete','library-batch-restore','library-batch-purge','delete-exam','confirm-delete-exam','restore-trashed-exam','purge-trashed-exam','duplicate-exam','clone-exam-target','question-bank','save-to-bank','save-all-to-bank','delete-bank-item','load-more-bank','reset-bank-filters','exam-rooms','exam-analytics','design-command','design-execute','new','backup','backup-local','import-backup','confirm-backup','community-exams','community-clone','community-source','share','copy-share','revoke-share','connections','refresh-providers-health','test-single-provider','pick-ollama-model','export','export-file','export-extended','export-tnmaker','export-pack','preview-variant','export-omr-student','export-omr-teacher','export-omr-pdf']);
 if(viewMode==='home'&&!stayHome.has(a)&&!a.startsWith('home-')&&!a.startsWith('proactive-')&&!a.startsWith('er-')){
  viewMode='workspace';
  syncHomeUrl('workspace');
  if(activeRailNav==='design-home')activeRailNav='design-workspace';
  if(a==='toggle-ai'||a==='toggle-chat'){
   assistantOpen=true;
   render();
   $('.workspace')?.classList.remove('chat-hidden','focus-mode');
   document.querySelector('[data-ux-action="mobile-show-editor"]')?.classList.remove('active');
   document.querySelector('.ux-view-tabs [data-action="toggle-ai"]')?.classList.add('active');
   return;
  }
  render();
 }
 if(await handleStudioAction(a,n))return;if(a!=='menu'&&!n?.closest?.('.floating-panel:not(.document-menu),.inline-math-panel,.composer-shell'))closeFloating();if(await handleVipAction(a,n,mvpContext))return;if(await handleExamRoomAction(a,n,mvpContext))return;if(await handleWorkbenchAction(a,n))return;if(await handleMVPAction(a,n))return;const e=exam();switch(a){
 case 'close':dialog.close();break;
 case 'close-top-modal':closeTopModal();break;
 case 'new':showNew();break;
 case 'create-sample':createExam(n.dataset.subject,true);break;
 case 'create-blank':{const s=$('#new-subject').value.trim();if(!s)return toast('Nhập môn học.');createExam(s,false);break;}
 case 'library':showLibrary();break;
 case 'open-exam':state.current=n.dataset.id;selected=null;selection=null;viewMode='workspace';activeRailNav='design-workspace';syncHomeUrl('workspace');dialog.close();persist().catch(()=>{});render();break;
 case 'delete-exam':{const target=state.exams.find(x=>x.id===n.dataset.id);modal('Chuyển đề vào thùng rác?',`<p>${esc(target.title)}</p><p class="hint">Đề sẽ nằm trong Thùng rác để khôi phục nếu cần. Thầy cô cũng có thể tải bản sao JSON trước.</p>${foot(button('backup','Tải bản sao')+button('confirm-delete-exam','Chuyển vào thùng rác','danger',`data-id="${target.id}"`))}`);break;}
 case 'confirm-delete-exam':{const victim=state.exams.find(x=>x.id===n.dataset.id);if(victim){state.trash=Array.isArray(state.trash)?state.trash:[];state.trash.unshift({...clone(victim),deletedAt:Date.now()});}state.exams=state.exams.filter(x=>x.id!==n.dataset.id);if(!state.exams.length)state.exams.push(blank('Lịch sử',state.prefs,state.teacherProfile));if(!state.exams.some(x=>x.id===state.current))state.current=state.exams[0].id;persist();render();await handleAction('library',n);break;}
 case 'tab':tab=['outline','templates'].includes(n.dataset.tab)?n.dataset.tab:'outline';render();break;
 case 'select':selectQ(n.dataset.id);document.dispatchEvent(new CustomEvent('question-selected'));refreshInline();break;
 case 'jump-first-review':{const target=qget(n.dataset.id)||e.questions.find(q=>q.check?.version===q.v&&q.check.status==='review')||e.questions.find(q=>!isApproved(q))||e.questions[0];if(!target)return toast('Chưa có câu hỏi trong đề.');selectQ(target.id);document.dispatchEvent(new CustomEvent('question-selected'));refreshInline();document.querySelector(`#q-${target.id} textarea.stem, #q-${target.id} .tiptap`)?.focus();break;}
 case 'toggle-chat':assistantOpen=!assistantOpen;$('.assistant')?.classList.toggle('open',assistantOpen);$('.workspace')?.classList.toggle('mobile-ai-view',assistantOpen&&innerWidth<=760);break;
 case 'toggle-left':sidebarOpen=!$('.sidebar').classList.contains('open');$('.sidebar').classList.toggle('open',sidebarOpen);break;
 case 'view-student':teacher=false;render();break;
 case 'view-teacher':teacher=true;render();break;
 case 'metadata':showMetadata();break;
 case 'question-meta':showQuestionMeta(n.dataset.id||selected);break;
 case 'set-mcq-answer':{const qid=n.dataset.id,idx=Number(n.dataset.index),targetQ=qget(qid);if(!targetQ)break;change('Đánh dấu đáp án đúng Câu '+(e.questions.indexOf(targetQ)+1),target=>setQuestionMcqAnswer(target,qid,idx));toast(`Đã đặt ${String.fromCharCode(65+idx)} là đáp án đúng Câu ${e.questions.indexOf(targetQ)+1}.`);break;}
 case 'exam-audio':showAudioModal({scope:'exam'});break;
 case 'insert-audio':case 'quick-audio':showAudioModal({scope:'question',questionId:n.dataset.id||selected});break;
 case 'remove-audio':{const scope=n.dataset.scope||'question',qid=n.dataset.id||selected;change('Xóa Audio nghe',target=>{if(scope==='exam'){delete target.audio;if(Array.isArray(target.passages))target.passages=target.passages.filter(p=>p?.id!=='exam-listening');}else{const q=target.questions.find(x=>x.id===qid);if(q)delete q.audio;}});dialog.close();toast('Đã xóa tệp Audio nghe.');break;}
 case 'add-question':{const q={id:uid(),v:1,stem:'Nhập nội dung câu hỏi…',options:['','','',''],answer:0,explanation:'',topic:e.matrix[0]?.topic||'Chủ đề mới',level:0,source:null,check:null};q.stem='Nhập nội dung câu hỏi…';change('Thêm câu hỏi',e=>{e.questions.push(q);check(e,q);});selectQ(q.id);break;}
 case 'duplicate-question':{const qid=n.dataset.id||selected;let copy=null;change('Nhân bản câu hỏi',target=>{copy=duplicateQuestionInExam(target,qid);if(copy)check(target,copy);});if(copy){selectQ(copy.id);refreshInline();toast('Đã nhân bản câu hỏi.');}break;}
 case 'toggle-approve-question':{const q=qget(n.dataset.id||selected);if(!q)return toast('Chọn câu cần duyệt.');let approvedNow=false;change('Đổi trạng thái duyệt câu '+(e.questions.indexOf(q)+1),target=>{approvedNow=toggleQuestionApprovalInExam(target,target.questions.find(x=>x.id===q.id));},{renderPage:false});refreshInline();toast(approvedNow?'Đã đánh dấu duyệt câu.':'Đã đưa câu về chờ rà soát.');break;}
 case 'delete-question':{const id=n.dataset.id;modal('Xóa câu hỏi?',`<p class="hint">Câu sẽ được bỏ khỏi trang đề và số đếm ma trận. Có thể hoàn tác.</p>${foot(button('confirm-delete-question','Xóa câu','danger',`data-id="${id}"`))}`);break;}
 case 'confirm-delete-question':change('Xóa câu hỏi',e=>{e.questions=e.questions.filter(q=>q.id!==n.dataset.id);});dialog.close();break;
 case 'move-up':case 'move-down':{const i=e.questions.findIndex(q=>q.id===n.dataset.id),j=i+(a==='move-up'?-1:1);if(j<0||j>=e.questions.length)return;change('Đổi thứ tự câu',e=>{[e.questions[i],e.questions[j]]=[e.questions[j],e.questions[i]];});showQuestionMeta(n.dataset.id);break;}
 case 'quick-move-up':case 'quick-move-down':{const qid=n.dataset.id||selected;let moved=false;change('Đổi thứ tự câu',target=>{moved=moveQuestionInExam(target,qid,a==='quick-move-up'?-1:1);});if(moved)selectQ(qid);break;}
 case 'matrix':showMatrix();break;
 case 'reverse-matrix':{
  n.disabled=true;
  try{
   await persist();
   const res=await requestReverseMatrix(e);
   const host=$('#matrix-reverse-warnings-host'),tbody=$('#matrix-rows'),mForm=$('#matrix-form');
   if(!tbody||!mForm)break;
   if(host)host.innerHTML=reverseMatrixWarningBannerHTML(res);
   const {counts:revCounts}=computeMatrixRowActuals(res.matrix,e.questions);
   tbody.innerHTML=res.matrix.map((r,idx)=>matrixRow(r.topic,r.targets,revCounts[idx]||[0,0,0,0],idx,r,res)).join('');
   const confirmBox=$('#matrix-confirm');
   if(confirmBox)confirmBox.checked=false;
   updateMatrixSummary(mForm);
   toast(res.warnings?.length?'Đã lập ma trận từ đề · có cảnh báo cần rà lại ở bảng trên.':'Đã lập ma trận ngược từ '+res.totalQuestions+' câu của đề.');
   if(host&&host.innerHTML.trim())host.scrollIntoView?.({block:'nearest',behavior:'smooth'});
  }finally{if(n.isConnected)n.disabled=false;}
  break;
 }
 case 'matrix-add':$('#matrix-rows').insertAdjacentHTML('beforeend',matrixRow('',[0,0,0,0],[0,0,0,0],$('#matrix-rows').children.length));updateMatrixSummary($('#matrix-form'));break;
 case 'matrix-rebalance':{
  const form=$('#matrix-form'),tbody=$('#matrix-rows');
  if(!form||!tbody)break;
  const rawRows=[...form.querySelectorAll('[data-matrix-row]')].map(r=>{
   const pt=r.querySelector('[name=matrix-points]')?.value;
   const lvlInputs=[...r.querySelectorAll('[name=matrix-level-points]')];
   const lvlVals=lvlInputs.map(x=>{
    const val=Number(x.value);
    return x.value===''||!Number.isFinite(val)?null:Math.round(val*100)/100;
   });
   const grp=r.dataset.choiceGroup?.trim();
   return {
    topic:(r.querySelector('.topic')?.value||'').trim()||'Chủ đề',
    type:r.querySelector('[name=matrix-type]')?.value||'mcq',
    ...(grp?{choiceGroup:grp}:{}),
    ...(!lvlInputs.length&&pt!==''&&pt!=null?{points:Number(pt)}:{}),
    ...(lvlInputs.length?{pointsByLevel:lvlVals}:{}),
    targets:[...r.querySelectorAll('[data-matrix-target]')].map(x=>Math.max(0,Number(x.value)||0)),
   };
  });
  const balanced=rebalanceMatrixRowsToTen(rawRows);
  const {counts:balCounts}=computeMatrixRowActuals(balanced,e.questions);
  const revReport=getReverseMatrixReport(e.id,e.revision);
  tbody.innerHTML=balanced.map((r,idx)=>matrixRow(r.topic,r.targets,balCounts[idx]||[0,0,0,0],idx,r,revReport)).join('');
  updateMatrixSummary(form);
  toast('Đã phân bổ lại điểm ma trận về đúng 10,00đ.');
  break;
 }
 case 'matrix-remove':n.closest('tr').remove();updateMatrixSummary($('#matrix-form'));break;
 case 'matrix-cycle-group':{const tr=n.closest('tr');if(!tr)break;const order=['','Tự chọn A','Tự chọn B'];const cur=tr.dataset.choiceGroup||'';const next=order.includes(cur)?order[(order.indexOf(cur)+1)%order.length]:'';if(next)tr.dataset.choiceGroup=next;else delete tr.dataset.choiceGroup;const meta=tr.querySelector('.matrix-topic-meta');if(meta)meta.innerHTML=`${next?`<span class="pill matrix-group-pill">${esc(next)}</span>`:''}<button type="button" class="matrix-group-toggle tiny-btn" data-action="matrix-cycle-group" title="Gắn hoặc đổi nhánh tự chọn">${next?'Đổi nhánh':'+ Nhánh'}</button>`;updateMatrixSummary($('#matrix-form'));break;}
 case 'matrix-export':download('Ma-tran.json',JSON.stringify(e.matrix,null,2),'application/json');break;
 case 'matrix-import':chooseFile('.json',async f=>{let rows;try{rows=JSON.parse(await f.text());validateMatrixRows(rows);}catch(err){throw Error('Tệp ma trận JSON chưa hợp lệ ('+(err?.message||'sai cú pháp JSON')+'). Kiểm tra mảng dòng ma trận tổng 10 điểm.');}change('Nhập ma trận (chưa xác nhận)',e=>{e.matrix=rows.map(r=>({topic:r.topic.trim(),targets:r.targets,...(r.type?{type:r.type}:{}),...(r.choiceGroup?{choiceGroup:r.choiceGroup}:{}),...(r.pointsQ4!=null?{pointsQ4:r.pointsQ4}:{}),...(r.pointsByLevelQ4?{pointsByLevelQ4:r.pointsByLevelQ4}:{}),...(r.points!=null?{points:r.points}:{}),...(r.pointsByLevel?{pointsByLevel:r.pointsByLevel}:{})}));e.matrixConfirmed=false;});showMatrix();});break;
 case 'replace':showReplace();break;
 case 'sample-suggestion':if(!e.sample){toast('Gợi ý dựng sẵn chỉ dùng cho đề mẫu. Hãy sửa tay hoặc dùng “Đổi thành: …”.');return;}showReplace(true);break;
 case 'preview-replace':previewReplace($('#replacement').value);break;
 case 'apply-replace':{
  const p=pending;
  flushEditor();
  const q=qget(p?.id);
  if(p?.type!=='replace'||p.examId!==e.id||!q||q.v!==p.version||q.stem.slice(p.start,p.end)!==p.text){
   toast('Đề xuất đã cũ. Chọn lại câu để sửa.');break;
  }
  const rich=q.richDoc?reconcileEditorRich(q.richDoc,q.stem,p.next):null;
  if(q.richDoc&&!rich)throw Error('Chưa thể giữ định dạng của câu. Mở lại đề rồi chọn đoạn cần sửa.');
  change('Sửa vùng chọn của câu '+(e.questions.indexOf(q)+1),()=>{
   q.stem=p.next;
   if(rich)q.richDoc=rich;
   q.runs=null;
   if(q.rule&&!q.rule.startsWith('math-')){q.dataLinked=true;q.rule=null;}
   touch(q);check(exam(),q);
  });
  selection=null;pending=null;dialog.close();break;
 }
 case 'data':showData();break;
 case 'apply-data':{const p=pending;flushEditor();if(p?.type!=='data'||p.examId!==e.id||p.revision!==e.revision)return toast('Dữ liệu đề đã đổi. Vui lòng xem lại ảnh hưởng.');change('Cập nhật dữ kiện, bảng, biểu đồ & trạng thái câu',e=>Object.assign(e,p.update));pending=null;n.disabled=true;try{await saveChain;dialog.close();}catch(error){toast('Chưa đồng bộ dữ kiện. '+error.message);}break;}
 case 'check-one':runCheck(n.dataset.id||selected);break;
 case 'check-all':change('Rà soát toàn đề',e=>e.questions.forEach(q=>check(e,q)));modal('Kết quả rà soát',`<p class="hint">Kiểm tra cấu trúc và phép tính của câu có liên kết bảng. Đây là rà soát tại máy; dùng nút giải lại bằng AI trong trợ lý để kiểm tra nội dung.</p>${e.questions.map((q,i)=>`<div class="small-card"><b>Câu ${i+1} · ${statusText(q)}</b><p>${esc(q.check.problems.join(' ')||q.check.evidence)}</p>${button('review','Xem căn cứ','',`data-id="${q.id}"`)}</div>`).join('')}`);break;
 case 'review':showReview(n.dataset.id||selected);break;
 case 'repair-preview':showRepair(n.dataset.id);break;
 case 'apply-repair':{const p=pending,q=qget(p?.id);if(p?.type!=='repair'||!q||q.v!==p.version)return toast('Đề xuất đã cũ. Kiểm tra lại bản hiện tại.');change('Sửa đáp án & kiểm tra lại câu '+(e.questions.indexOf(q)+1),()=>{q.answer=p.answer;q.answerKnown=true;q.options=p.options;q.explanation=p.explanation;touch(q);check(e,q);});pending=null;showReview(q.id);break;}
 case 'approve-question':{const q=qget(n.dataset.id);if(!q||n.dataset.version&&q.v!==Number(n.dataset.version))throw Error('Câu đã đổi phiên bản; mở lại để duyệt.');change('Giáo viên duyệt câu '+(e.questions.indexOf(q)+1),()=>{approveQuestion(q);});dialog.close();break;}
 case 'undo':if(undo(e)){selection=null;persist().catch(()=>{});render();toast('Đã hoàn tác cả phần liên quan');}break;
 case 'redo':if(redo(e)){selection=null;persist().catch(()=>{});render();toast('Đã làm lại thay đổi');}break;
 case 'source':await showSource(n.dataset.doc,n.dataset.id);break;
 case 'import-doc':showImport();break;
 case 'download-original':{const d=e.docs.find(d=>d.id===n.dataset.doc),url=await db.get('file:'+d.fileId);const link=document.createElement('a');link.href=url;link.download=d.name;link.click();break;}
 case 'memory':showMemory();break;
 case 'delete-pref':state.prefs=state.prefs.filter(p=>p.id!==n.dataset.id);persist();render();showMemory();break;
 case 'edit-pref':{const p=state.prefs.find(p=>p.id===n.dataset.id);const st=p?.scopeType||'all';modal('Xem và xác nhận yêu cầu',`<form id="pref-edit-form" data-id="${p.id}"><label>Nội dung yêu cầu</label><textarea name="text" rows="4" required maxlength="500">${esc(p.text)}</textarea><div class="grid3"><div><label>Phạm vi</label><select name="scopeType"><option value="all" ${st==='all'?'selected':''}>Mọi môn &amp; mọi lớp</option><option value="subject" ${st==='subject'?'selected':''}>Theo môn</option><option value="subject_grade" ${st==='subject_grade'?'selected':''}>Đúng môn &amp; lớp</option></select></div><div><label>Môn</label><input name="subject" value="${esc(p.subject||e.subject||'')}" maxlength="80"></div><div><label>Lớp</label><input name="grade" value="${esc(p.grade||e.grade||'')}" maxlength="40"></div></div><p class="hint">Áp dụng đúng phạm vi môn/lớp cho các đề tạo sau.</p>${foot('<button type="submit" class="primary">Xác nhận yêu cầu mới</button>')}</form>`);break;}
 case 'apply-prefs-current':change('Áp dụng yêu cầu đã xác nhận theo phạm vi',e=>{e.appliedPrefs=clone(filterPrefsForExam(state.prefs,e.subject,e.grade));e.questions.forEach(q=>check(e,q));});showMemory();break;
 case 'quotes':showQuotes();break;
 case 'add-variant':showAddVariant();break;
 case 'web-search':modal('Tìm các bản trên web','<div class="alert">Chưa bật tìm nguồn trên web trên máy. Chưa có truy vấn nào được gửi hoặc kết quả nào được tìm.</div><p class="hint">Thầy cô có thể tự tra cứu và dán bản tìm được kèm địa chỉ nguồn để đối chiếu ngay tại máy. Khi nối dịch vụ tìm kiếm, kết quả cần có URL, vị trí và nội dung truy cập được; không tự dùng làm ngữ liệu trước khi thầy cô chọn.</p>'+foot(button('add-variant','Nhập bản đã tìm được','primary')));break;
 case 'choose-variant':{
  const v=e.quote.versions.find(v=>v.id===n.dataset.id);
  if(!v)return toast('Bản ngữ liệu đã đổi. Mở lại danh sách để chọn.');
  pending={type:'quote',examId:e.id,id:v.id,revision:e.revision};
  modal('Chọn bản ngữ liệu dùng trong đề',`<div class="diff"><del>${esc(e.quote.text)}</del><ins>${diffText(e.quote.text,v.text)}</ins></div><p class="hint">Cập nhật ngữ liệu và đánh dấu các câu đọc hiểu liên quan cần kiểm tra lại. Không đổi phương án hoặc tự kết luận dị bản nào sai.</p>${foot(button('apply-quote','Xác nhận bản dùng','primary'))}`);
  break;
 }
 case 'apply-quote':{
  const p=pending;
  if(p?.type!=='quote'||p.examId!==e.id||p.revision!==e.revision)return toast('Đề đã thay đổi, chọn lại bản.');
  const v=e.quote.versions.find(v=>v.id===p.id);
  if(!v)return toast('Bản ngữ liệu đã đổi. Mở lại danh sách để chọn.');
  const page=v.docId&&Number.isInteger(v.page)&&v.page>0?v.page:null;
  change('Giáo viên chọn bản ngữ liệu',e=>{
   e.quote.text=v.text;
   e.quote.chosen=v.id;
   e.questions.filter(q=>q.quote).forEach(q=>{
    const prevVersion=q.v;
    if(Array.isArray(q.evidence)&&q.evidence.length){
     q.evidence=q.evidence.map(ev=>({
      ...ev,
      stale:true,
      staleReason:'quote_variant_changed',
      questionVersion:ev.questionVersion??prevVersion,
     }));
    }
    touch(q);
    q.source={docId:v.docId||null,location:v.location||v.url||'Bản nhập tay',...(page?{page}:{})};
    check(e,q);
   });
  });
  pending=null;
  showQuotes();
  break;
 }
 case 'history':showHistory();break;
 case 'rename-history':{const h=e.history.find(x=>x.id===n.dataset.id);if(!h)break;modal('Đặt tên mốc lịch sử',`<form id="history-rename-form" data-id="${esc(h.id)}"><label>Tên mốc (Bản đề ${h.revision})</label><input name="label" value="${esc(h.label)}" required maxlength="140">${foot(button('history','Quay lại')+'<button type="submit" class="primary">Lưu tên mốc</button>')}</form>`);break;}
 case 'restore':{const h=e.history.find(h=>h.id===n.dataset.id);pending={type:'restore',id:h.id};modal('Xem bản đề '+h.revision,`<h3>${esc(h.state.title)}</h3><p class="hint">${esc(h.label)} · ${date(h.at)}</p>${h.state.questions.map((q,i)=>`<div class="small-card"><b>Câu ${i+1} · v${q.v}</b><div class="read-formula">${richTextHTML(q.stem)}</div></div>`).join('')}${foot(button('apply-restore','Khôi phục bản này','primary'))}`);break;}
 case 'apply-restore':{const h=e.history.find(h=>h.id===pending?.id);if(!h)return;change('Khôi phục bản đề '+h.revision,e=>Object.assign(e,clone(h.state)));selection=null;pending=null;dialog.close();break;}
 case 'export':showExport();break;
 case 'export-html':{const t=n.dataset.teacher==='true';download(safeName(e.title)+(t?' — Giao-vien':' — Hoc-sinh')+'.html',exportHTML(e,t),'text/html;charset=utf-8');break;}
 case 'print':{const win=window.open('about:blank','_blank');if(!win)return toast('Cho phép mở cửa sổ để xem bản in.');win.document.write(exportHTML(e,n.dataset.teacher==='true'));win.document.close();break;}
 case 'backup':await backup();break;
 case 'backup-local':await backup(true);break;
 case 'save-local':await saveLocal({type:'exam',exam:e,teacher:n.dataset.teacher==='true'});break;
 case 'import-backup':
  chooseFile('.json',async file=>{
   if(file.size>150*1024*1024)throw Error('Bản sao quá lớn.');
   const content=await file.text();
   let backup;
   try{backup=JSON.parse(content);}
   catch{throw Error('Tệp JSON bị hỏng. Hãy chọn bản sao tải từ ứng dụng.');}
   await saveChain;
   const preview=await db.previewRestore(backup);
   pending={type:'backup',data:backup,revision:preview.revision};
   modal('Khôi phục bản sao dữ liệu',`<p>Đã kiểm bản sao: ${preview.exams??preview.examCount??0} đề, ${preview.files??preview.fileCount??0} tệp và ${preview.prefs??0} yêu cầu đã xác nhận.</p>${preview.questionBank?`<p>Có ${preview.questionBank} câu hỏi trong Ngân hàng câu hỏi.</p>`:''}${preview.curriculumSources?`<p>Có ${preview.curriculumSources} học liệu cá nhân. Học liệu mới trong kho đích cần được xác nhận lại quyền trước khi dùng cho AI.</p>`:''}${preview.matrixTemplates?`<p>Có ${preview.matrixTemplates} mẫu ma trận cá nhân.</p>`:''}<div class="alert">Thay các đề trong tài khoản hiện tại bằng bản sao này, gồm lịch sử và hoàn tác. Hãy tải bản sao hiện tại nếu cần giữ lại. Khóa AI, tài khoản, liên kết chia sẻ và tác vụ AI cũ không được khôi phục từ JSON.</div>${foot(button('backup','Tải bản sao hiện tại')+button('confirm-backup','Khôi phục kho này','primary'))}`);
  });
  break;
 case 'confirm-backup':{
  const backup=pending;
  if(backup?.type!=='backup'||n.disabled)return;
  n.disabled=true;
  try{
   await saveChain;
   if(pending!==backup||!n.isConnected||!dialog.open)return;
   const result=await db.restoreBackup(backup.data,backup.revision);
   pending=null;
   dialog.close();
   if(result.cacheWarning)toast(result.cacheWarning);
   location.reload();
  }finally{if(n.isConnected)n.disabled=false;}
  break;
 }
 case 'connections':showConnections();break;
 case 'extract':await showExtract();break;
 default:break;
 }}
document.addEventListener('click',async event=>{const n=event.target.closest('[data-action]');if(!n)return;event.preventDefault();try{await handleAction(n.dataset.action,n);}catch(err){console.error(err);toast(friendlyClientMessage(err));if(dialog.open&&dialog.querySelector('.busy'))modal('Chưa thực hiện được',`<div class="alert">${esc(friendlyClientMessage(err))}</div><p class="hint">Chưa áp dụng thay đổi. Có thể điều chỉnh kết nối hoặc thử lại.</p>`);}});
document.addEventListener('input',event=>{const n=event.target;if(n.matches('textarea.stem'))autosize();if(n.dataset.qField||n.dataset.examField){document.querySelectorAll('[data-save-status]').forEach(el=>el.textContent='Đang soạn…');clearTimeout(inlineTimer);inlineTimer=setTimeout(()=>n.dispatchEvent(new Event('change',{bubbles:true})),450);}});
document.addEventListener('change',async event=>{const n=event.target;try{if(n.dataset.qField||n.dataset.examField)clearTimeout(inlineTimer);if(n.dataset.examField){const f=n.dataset.examField;if(f==='title'){const clean=n.value.trim();if(!clean){n.value=exam().title;document.querySelectorAll('[data-save-status]').forEach(el=>el.textContent=saveStatusLabel());toast('Tên đề thi không được để trống.');return;}if(clean!==exam().title)change('Sửa tên đề',e=>{e.title=clean;},{renderPage:false});}else if(n.value!==exam()[f])change('Sửa hướng dẫn',e=>{e[f]=n.value;},{renderPage:false});if($('.breadcrumb b'))$('.breadcrumb b').textContent=exam().title;if($('.header-title'))$('.header-title').textContent=exam().title;}if(n.dataset.examField==='title')document.querySelectorAll('[data-exam-field="title"]').forEach(other=>{if(other!==n)other.value=exam().title;});if(n.dataset.qField){const q=qget(n.dataset.id),f=n.dataset.qField;const value=f==='answer'?Number(n.value):f==='truthValue'?(n.value===''?null:n.value==='true'):n.value;const equal=f==='option'?q.options[Number(n.dataset.index)]===value:f==='truthValue'?q.truthValues?.[Number(n.dataset.index)]===value:q[f]===value;if(equal&&(!['answer','answerText','truthValue'].includes(f)||q.answerKnown!==false))return;change('Sửa '+(f==='stem'?'thân câu':f==='option'?'phương án':f==='answer'?'đáp án':'giải thích')+' câu '+(exam().questions.indexOf(q)+1),()=>{if(f==='option')q.options[Number(n.dataset.index)]=value;else if(f==='truthValue'){if(!Array.isArray(q.truthValues)||q.truthValues.length!==4||(q.answerKnown===false&&q.truthValues.every(x=>typeof x==='boolean')))q.truthValues=[null,null,null,null];q.truthValues[Number(n.dataset.index)]=value;q.answerKnown=q.truthValues.every(x=>typeof x==='boolean');}else q[f]=value;if(f==='answer')q.answerKnown=n.value!=='';if(f==='answerText')q.answerKnown=!!value.trim();if(f==='stem'&&q.rule&&!q.rule.startsWith('math-')){q.dataLinked=true;q.rule=null;}touch(q);check(exam(),q);},{renderPage:false});selection=null;setTimeout(()=>{if(!dialog.open)refreshInline();},500);}if(n.id==='workflow-status-select'){const nextStatus=normalizeWorkflowStatus(n.value);if(nextStatus===n.value&&nextStatus!==normalizeWorkflowStatus(exam().workflowStatus)){change('Đổi trạng thái đề sang '+(WORKFLOW_STATUS_LABELS[nextStatus]||nextStatus),e=>{e.workflowStatus=nextStatus;e.approvalStatus=nextStatus==='approved'||nextStatus==='printed'?'approved':'draft';});}return;}if(n.id==='doc-file'&&n.files[0])await importFile(n.files[0]);if(n.id==='scan-doc')await showExtract(n.value);}catch(err){toast(err.message);}});
function captureSelection(event){const n=event.target;if(!n.matches('textarea.stem'))return;const q=qget(n.dataset.id);if(!q)return;const start=n.selectionStart,end=n.selectionEnd;if(start===end)return;selected=q.id;selection={id:q.id,version:q.v,field:'stem',start,end,text:n.value.slice(start,end)};$('.assistant-body').innerHTML=rightHTML();refreshReferenceScope(mvpContext);refreshWorkbench();document.querySelectorAll('.question').forEach(el=>el.classList.toggle('selected',el.dataset.q===selected));document.querySelectorAll('.outline-item').forEach(el=>el.classList.toggle('active',el.dataset.id===selected));}
document.addEventListener('mouseup',captureSelection);document.addEventListener('keyup',captureSelection);
document.addEventListener('submit',async event=>{event.preventDefault();const f=event.target,e=exam();try{if(await handleHomeSubmit(f,mvpContext))return;if(handleStudioSubmit(f))return;if(await handleWorkbenchSubmit(f))return;if(await handleExamRoomSubmit(f,mvpContext))return;if(await handleMVPSubmit(f))return;if(f.id==='chat-form'){const text=$('#chat-input').value.trim();if(!text)return;addChat('user',text);if(/^đổi thành\s*:/i.test(text)){const s=currentScope();if(!s){addChat('assistant','Chọn một câu trước khi thay nội dung.');render();return;}pending={...s,type:'replace'};previewReplace(text.replace(/^đổi thành\s*:\s*/i,''));render();}else if(/^kiểm tra/i.test(text)&&selected){runCheck(selected);}else{addChat('assistant','Chưa kết nối AI nên tôi chưa thể thực hiện yêu cầu tự do này. Thầy cô có thể chọn chữ và bấm “Sửa phần đã chọn”, hoặc nhập “Đổi thành: …” để xem trước thay đổi. Các nút kiểm tra, dữ kiện và đối chiếu đang hoạt động tại máy.');render();}return;}
 if(f.id==='audio-attach-form'){
  const scope=f.dataset.scope||'question',qid=f.dataset.id||'';
  const fd=new FormData(f);
  const file=f.elements.audioFile?.files?.[0];
  const title=String(fd.get('title')||'').trim();
  const maxPlays=Number(fd.get('maxPlays')||2);
  const curTarget=scope==='exam'?e:qget(qid);
  if(scope==='question'&&!curTarget)throw Error('Không tìm thấy câu hỏi cần gắn Audio.');
  let meta;
  if(file&&file.size>0){
   const fid='aud-'+uid();
   meta=buildAudioAttachmentMeta({fileId:fid,filename:file.name,mimeType:file.type,sizeBytes:file.size,maxPlays,title});
   const dataUri=await new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(String(r.result||''));r.onerror=()=>rej(Error('Không đọc được tệp âm thanh.'));r.readAsDataURL(file);});
   await db.put('file:'+fid,dataUri);
  }else if(curTarget?.audio){
   meta=buildAudioAttachmentMeta({...curTarget.audio,maxPlays,title});
  }else{
   throw Error('Chọn một tệp âm thanh .mp3 hoặc .wav.');
  }
  change('Gắn Audio nghe',target=>{
   if(scope==='exam'){
    target.audio=meta;
    target.passages=Array.isArray(target.passages)?target.passages.filter(p=>p?.id!=='exam-listening'):[];
    target.passages.unshift({id:'exam-listening',title:meta.title||meta.filename||'Bài nghe',audio:clone(meta)});
   }else{
    const q=target.questions.find(x=>x.id===qid);
    if(q){q.audio=meta;touch(q);}
   }
  });
  dialog.close();
  toast('Đã lưu Audio nghe vào đề.');
  return;
 }
 if(f.id==='matrix-form'){const rows=readMatrixFormRows(f);const confirmed=$('#matrix-confirm').checked;clearReverseMatrixReport(e.id);change('Cập nhật ma trận'+(confirmed?' đã xác nhận':''),e=>{e.matrix=rows;e.matrixConfirmed=confirmed;});dialog.close();tab='outline';render();return;}
 if(f.id==='meta-form'){const v=Object.fromEntries(new FormData(f));const cleanTitle=String(v.title||'').trim();if(!cleanTitle)throw Error('Tên đề thi không được để trống.');v.title=cleanTitle;const saveDefault=Boolean(f.elements.saveProfileDefault?.checked);delete v.saveProfileDefault;v.minutes=Number(v.minutes);if(saveDefault){state.teacherProfile={...(state.teacherProfile||{}),school:String(v.school||'').trim(),department:String(v.department||'').trim(),layout:clone(e.layout||state.teacherProfile?.layout||null)};}change('Sửa thông tin đề',e=>{Object.assign(e,v);e.workflowStatus=normalizeWorkflowStatus(e.workflowStatus);e.approvalStatus=['approved','printed'].includes(e.workflowStatus)?'approved':'draft';});dialog.close();return;}
 if(f.id==='q-meta-form'){const q=qget(f.dataset.id),v=Object.fromEntries(new FormData(f));change('Cập nhật thuộc tính câu '+(e.questions.indexOf(q)+1),()=>{q.topic=v.topic.trim();q.level=Number(v.level);q.points=Number(v.points);q.lockPosition=Boolean(f.elements.lockPosition?.checked);const changedType=q.type!==v.type;q.type=v.type;if(['essay','short'].includes(q.type)){q.options=[];q.rule=null;}else if(q.options.length!==4)q.options=['','','',''];q.source=v.docId?{docId:v.docId,location:v.location}:null;if(q.type==='mcq'&&v.answer!==undefined&&v.answer!==''){q.answer=Number(v.answer);q.answerKnown=true;}if(changedType)q.answerKnown=false;q.explanation=v.explanation;touch(q);check(e,q);});dialog.close();return;}
 if(f.id==='data-form'){flushEditor();if(f.dataset.exam!==e.id||Number(f.dataset.revision)!==e.revision)throw Error('Dữ liệu đề đã đổi. Mở lại Sửa dữ kiện.');showDataPreview([...f.querySelectorAll('[data-data-index]')].map(input=>input.valueAsNumber));return;}
 if(f.id==='paste-doc-form'){const v=Object.fromEntries(new FormData(f)),d={id:uid(),name:v.name.trim(),text:v.text,kind:'text',sample:false};change('Thêm tư liệu nhập tay',e=>e.docs.push(d));tab='outline';render();await showSource(d.id);return;}
 if(f.id==='pref-form'){if(!$('#pref-confirm').checked)throw Error('Xác nhận yêu cầu trước khi ghi nhớ.');const text=$('#pref-text').value.trim();if(!text)throw Error('Nhập yêu cầu trước khi xác nhận.');const fd=new FormData(f);state.prefs.push({id:uid(),text,kind:$('#pref-kind').value,maxWords:30,scopeType:String(fd.get('scopeType')||'all'),subject:String(fd.get('subject')||'').trim(),grade:String(fd.get('grade')||'').trim(),confirmedAt:Date.now()});persist();render();showMemory();return;}
 if(f.id==='pref-edit-form'){const p=state.prefs.find(p=>p.id===f.dataset.id),fd=new FormData(f);p.text=String(fd.get('text')||'').trim();p.scopeType=String(fd.get('scopeType')||'all');p.subject=String(fd.get('subject')||'').trim();p.grade=String(fd.get('grade')||'').trim();p.confirmedAt=Date.now();persist();showMemory();return;}
 if(f.id==='history-rename-form'){const h=e.history.find(x=>x.id===f.dataset.id),label=String(new FormData(f).get('label')||'').trim();if(!h||!label)throw Error('Nhập tên mốc lịch sử.');h.label=label;persist();showHistory();toast('Đã cập nhật tên mốc lịch sử.');return;}
 if(f.id==='variant-form'){const v=Object.fromEntries(new FormData(f));if(v.url&&!/^https?:\/\//i.test(v.url))throw Error('Nguồn cần dùng địa chỉ http hoặc https.');const variant={...v,id:uid(),external:true};change('Thêm bản đối chiếu nhập tay',e=>e.quote.versions.push(variant));showQuotes();return;}
 if(f.id==='scan-form'){const text=new FormData(f).get('text'),doc=e.docs.find(d=>d.id===f.dataset.doc);if(!doc)throw Error('Thêm bản gốc trước khi lưu bản đối chiếu.');change('Lưu văn bản nhập tay từ bản gốc',e=>{doc.manualText=text;const existing=e.docs.find(d=>d.originalId===doc.id);if(existing)existing.text=text;else e.docs.push({id:uid(),name:'Bản nhập tay — '+doc.name,kind:'text',text,originalId:doc.id,sample:false});});toast('Đã lưu bản nhập tay · chưa có nhận dạng tự động');await showExtract(doc.id);}
 }catch(err){console.error(err);toast(err.message);const topDlg=activeModalDialog();if(topDlg&&topDlg.querySelector('.busy'))modal('Chưa thực hiện được',`<div class="alert">${esc(friendlyClientMessage(err))}</div><p class="hint">Chưa áp dụng thay đổi. Kiểm tra kết nối hoặc dữ liệu đầu vào.</p>`,'',{layer:topDlg===dialogLayer2?2:1});}});
function trapModalFocus(event,dlg){
 if(!dlg?.open||event.key!=='Tab')return;
 const focusables=[...dlg.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex]:not([tabindex="-1"])')].filter(el=>el.offsetParent!==null||el.getClientRects().length);
 if(!focusables.length)return;
 const first=focusables[0],last=focusables.at(-1);
 if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
 else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
}
for(const [dlg,getFocus,clearFocus] of [[dialog,()=>modalReturnFocus,()=>{modalReturnFocus=null;}],[dialogLayer2,()=>layer2ReturnFocus,()=>{layer2ReturnFocus=null;}]]){
 if(!dlg)continue;
 dlg.addEventListener('click',event=>{if(event.target===dlg){const r=dlg.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dlg.close();}});
 dlg.addEventListener('close',()=>{if(viewMode==='home'){activeRailNav='design-home';setActiveWorkspaceNav('design-home');}const el=getFocus();clearFocus();if(el?.isConnected)el.focus();else if(viewMode==='home')document.querySelector('.design-rail button.rail-active, .design-rail button')?.focus();});
 dlg.addEventListener('keydown',event=>{if(viewMode==='home'&&dlg.open&&event.key==='Enter'&&event.target?.id==='command-query'){const first=dlg.querySelector('#command-results .command-result');if(first){event.preventDefault();first.click();return;}}trapModalFocus(event,dlg);});
}
window.addEventListener('keydown',event=>{if(event.key==='Escape'&&dialogLayer2?.open){event.preventDefault();event.stopPropagation();dialogLayer2.close();return;}if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'&&!event.isComposing){event.preventDefault();if(!flushEditor())return;document.activeElement?.blur();persist().then(()=>toast('Đã lưu đề trên máy')).catch(err=>toast(friendlyClientMessage(err)));}if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='y'&&!event.shiftKey&&!event.isComposing&&!event.target.closest('.tiptap,input,textarea,math-field,.composer-shell')){event.preventDefault();void handleAction('redo');}},true);
window.addEventListener('hashchange',()=>{const next=detectInitialViewMode();if(next!==viewMode){viewMode=next;activeRailNav=viewMode==='home'?'design-home':'design-workspace';if(state)render();}});
async function init(){try{await bootstrapWorkbench();state=await db.get('state');showSaveWarning(db.hasPendingWrites());if(!state){const e=sample();e.questions.forEach(q=>check(e,q));state={version:1,current:e.id,exams:[e],prefs:[]};await persist();}const copyToken=new URLSearchParams(location.search).get('copy');if(copyToken){try{const shareRes=await fetch('/api/share/read/'+encodeURIComponent(copyToken),{headers:db.workspaceHeaders()});if(shareRes.ok){const shareData=await shareRes.json();if(shareData?.allowCopy&&shareData.files&&typeof shareData.files==='object'){for(const [fid,dataUri] of Object.entries(shareData.files)){if(typeof dataUri==='string'&&dataUri)await db.put('file:'+fid,dataUri);}}}}catch{}}if(new URLSearchParams(location.search).get('demo')==='toan'){let target=state.exams.find(e=>e.subject==='Toán'&&e.sample);if(!target){target=sample('Toán',state.prefs);target.questions.forEach(q=>check(target,q));state.exams.push(target);}state.current=target.id;await persist();history.replaceState({},'',location.pathname);}viewMode=detectInitialViewMode();activeRailNav=viewMode==='home'?'design-home':'design-workspace';render();await initMVP(mvpContext);await initWorkbench(mvpContext);}catch(err){app.innerHTML=`<div style="padding:40px"><h1>Chưa mở được dữ liệu tại máy</h1><p>${esc(friendlyClientMessage(err))}</p><p>Mở trang trong cửa sổ trình duyệt thông thường có hỗ trợ lưu trữ cục bộ.</p></div>`;}}
init();
