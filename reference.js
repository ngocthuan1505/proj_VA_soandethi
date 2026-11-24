import {separateMarking,approveQuestion,isApproved,QUESTION_TYPES,clone} from './core.js';
import {documentPages,selectedDocumentPages,sourcePageLabel} from './assistant-sources.js';
import {documentPlain,renderRichDocument} from './rich-document.js';
import {composerHTML,mountComposer,cleanupComposer,handleComposerAction,submitComposerText,refreshComposerPreview} from './composer.js';
import {richTextHTML} from './math-content.js';
import {esc,uid,touch,check,mathSample} from './core.js';
import katex from './assets/katex/katex.mjs';
import {captureDOMSelection,flushEditor,updateInlineMath,insertInlineMath,currentEditorKey,insertRichContent} from './editor.js';
let c,formula=null,initialized=false,dropInitialized=false,activeDropHost=null,sourceModalDraft=null;
const $=s=>document.querySelector(s);
const b=(action,label,attrs='')=>`<button type="button" data-action="${action}" ${attrs}>${label}</button>`;
export const effortNames=['Nhanh','Trung bình','Kỹ hơn'];
export const CHAT_TIME_PRESETS=[
 ['fast','Thời gian: Nhanh (2p · API nhanh)',120],
 ['standard','Thời gian: Chuẩn (5p · AGY)',300],
 ['deep','Thời gian: Kỹ sâu (20p · AGY)',1200],
 ['extended','Thời gian: Sâu (60p · AGY)',3600],
];
export const ASSISTANT_DROP_EXTENSIONS=['docx','pdf','txt','md','pptx','png','jpg','jpeg','webp'];
export const MAX_ASSISTANT_DROP_BYTES=15*1024*1024;
const DROP_ZONE_SELECTOR='.assistant, .assistant-panel, .chat, #chat-form, #prompt, .upload-zone';

/** Kiểm tra định dạng và dung lượng tệp kéo–thả hợp lệ trước khi đọc hoặc gửi OCR. */
export function validateDroppedSourceFile(file){
 if(!file||typeof file.name!=='string'||!file.name.trim()){
  return {ok:false,ext:'',error:'Chưa có tệp hợp lệ để tải lên.'};
 }
 const dot=file.name.lastIndexOf('.');
 const ext=dot>=0?file.name.slice(dot+1).toLowerCase():'';
 if(!ASSISTANT_DROP_EXTENSIONS.includes(ext)){
  return {
   ok:false,
   ext,
   error:'Định dạng chưa hỗ trợ. Kéo thả tệp .docx, .pdf, .txt, .md, .pptx hoặc ảnh PNG/JPEG/WEBP.',
  };
 }
 if(typeof file.size==='number'){
  if(file.size<=0)return {ok:false,ext,error:'Tệp đang trống (0 byte).'};
  if(file.size>MAX_ASSISTANT_DROP_BYTES)return {ok:false,ext,error:'Tệp vượt quá giới hạn 15 MB.'};
 }
 const kind=ext==='pdf'?'pdf':ext==='pptx'?'slides':['docx','txt','md'].includes(ext)?'text':'image';
 return {ok:true,ext,kind,name:file.name,size:file.size||0};
}

/** Rút danh sách File từ DataTransfer khi kéo–thả vào trình duyệt. */
export function extractDroppedFiles(dataTransfer){
 if(!dataTransfer)return [];
 if(dataTransfer.files?.length)return Array.from(dataTransfer.files);
 if(dataTransfer.items?.length){
  return Array.from(dataTransfer.items)
   .filter(item=>item.kind==='file'&&typeof item.getAsFile==='function')
   .map(item=>item.getAsFile())
   .filter(Boolean);
 }
 return [];
}

/** Chỉ chặn/nổi bật vùng thả khi đang kéo tệp thực sự, không ảnh hưởng kéo chữ trong editor. */
export function hasDraggedFiles(dataTransfer){
 if(!dataTransfer)return false;
 if(dataTransfer.files?.length)return true;
 const types=Array.from(dataTransfer.types||[]);
 if(types.includes('Files')||types.includes('application/x-moz-file'))return true;
 return Array.from(dataTransfer.items||[]).some(item=>item.kind==='file');
}

/** Lọc danh sách tệp kéo–thả thành các tệp hợp lệ và tệp bị từ chối kèm thông báo lỗi. */
export function filterDroppedSourceFiles(fileList){
 const accepted=[],rejected=[];
 for(const file of Array.from(fileList||[])){
  const checkFile=validateDroppedSourceFile(file);
  if(checkFile.ok)accepted.push(file);
  else rejected.push({file,error:checkFile.error,ext:checkFile.ext});
 }
 return {accepted,rejected};
}

function refreshRichNodeIds(node){
 if(!node||typeof node!=='object')return node;
 if(Array.isArray(node))return node.map(refreshRichNodeIds);
 const next={...node};
 if(next.attrs&&typeof next.attrs==='object'&&next.attrs.id)next.attrs={...next.attrs,id:uid()};
 if(Array.isArray(next.content))next.content=next.content.map(refreshRichNodeIds);
 return next;
}

/** Nhân bản một câu hỏi với UUID mới cho câu, block và công thức/bảng/ảnh đính kèm. */
export function duplicateQuestionInExam(exam,questionId){
 const idx=(exam?.questions||[]).findIndex(q=>q.id===questionId);
 if(idx<0)return null;
 const copy=clone(exam.questions[idx]);
 copy.id=uid();
 copy.v=1;
 copy.check=null;
 delete copy.blockIds;
 delete copy.approval;
 delete copy.verification;
 delete copy.generated;
 if(copy.richDoc)copy.richDoc=refreshRichNodeIds(copy.richDoc);
 if(copy.explanationDoc)copy.explanationDoc=refreshRichNodeIds(copy.explanationDoc);
 if(Array.isArray(copy.optionDocs))copy.optionDocs=copy.optionDocs.map(doc=>doc?refreshRichNodeIds(doc):doc);
 if(Array.isArray(copy.rubric))copy.rubric=copy.rubric.map(r=>({...r,...(r.richDoc?{richDoc:refreshRichNodeIds(r.richDoc)}:{})}));
 if(Array.isArray(copy.formulas))copy.formulas=copy.formulas.map(f=>({...f,id:uid()}));
 if(Array.isArray(copy.tables))copy.tables=copy.tables.map(t=>({...t,id:uid()}));
 if(Array.isArray(copy.images))copy.images=copy.images.map(im=>({...im,id:uid()}));
 exam.questions.splice(idx+1,0,copy);
 return copy;
}

/** Hoán đổi vị trí câu hỏi lên (-1) hoặc xuống (+1) trong đề. */
export function moveQuestionInExam(exam,questionId,delta){
 const list=exam?.questions;
 if(!Array.isArray(list))return false;
 const idx=list.findIndex(q=>q.id===questionId),target=idx+delta;
 if(idx<0||target<0||target>=list.length)return false;
 [list[idx],list[target]]=[list[target],list[idx]];
 return true;
}

/** Bật/tắt trạng thái giáo viên đã duyệt trên câu hỏi mà không mất kiểm chứng cấu trúc. */
export function toggleQuestionApprovalInExam(exam,question){
 if(!question)return false;
 if(isApproved(question)){
  question.approval=null;
  if(question.check?.version===question.v&&question.check.status==='approved'){
   check(exam,question);
  }
  return false;
 }
 approveQuestion(question);
 return true;
}

/** Tạo thanh thao tác nhanh gọn ngay trên đầu mỗi block câu hỏi. */
export function questionQuickActionsHTML(q,index,total,iconFn){
 const approved=isApproved(q);
 const needsReview=q.check?.version===q.v&&q.check.status==='review';
 const ico=typeof iconFn==='function'?iconFn:()=>'';
 return [
  b('select','Chọn câu',`class="q-quick-btn" data-id="${q.id}" title="Chọn câu để sửa cùng Trợ lý"`),
  b('quick-formula','ƒ',`class="q-quick-btn q-quick-symbol" data-id="${q.id}" data-editor-key="${q.id}" aria-label="Chèn công thức hoặc mẫu câu ${index+1}" title="Mở nhanh composer công thức & mẫu"`),
  b('quick-image',ico('image')||'Ảnh',`class="icon q-quick-btn" data-id="${q.id}" aria-label="Chèn ảnh câu ${index+1}" title="Chèn ảnh"`),
  b('quick-table',ico('grid')||'Bảng',`class="icon q-quick-btn" data-id="${q.id}" aria-label="Chèn hoặc sửa bảng câu ${index+1}" title="Chèn bảng"`),
  b('quick-figure','◇',`class="q-quick-btn q-quick-symbol" data-id="${q.id}" aria-label="Chèn hoặc sửa hình học câu ${index+1}" title="Hình học tọa độ"`),
  b('toggle-approve-question',(ico('check')||'✓')+`<span>${approved?'Đã duyệt':'Duyệt'}</span>`,`class="q-quick-btn q-approve-btn${approved?' is-approved':needsReview?' is-review':''}" data-id="${q.id}" aria-pressed="${approved}" aria-label="${approved?'Bỏ duyệt':'Duyệt'} câu ${index+1}" title="${approved?'Bấm để bỏ duyệt câu':'Đánh dấu giáo viên đã duyệt'}"`),
  b('duplicate-question','❐',`class="q-quick-btn q-quick-symbol" data-id="${q.id}" aria-label="Nhân bản câu ${index+1}" title="Nhân bản câu"`),
  b('quick-move-up','↑',`class="q-quick-btn q-quick-symbol" data-id="${q.id}" ${index===0?'disabled':''} aria-label="Đưa câu ${index+1} lên" title="Đưa câu lên"`),
  b('quick-move-down','↓',`class="q-quick-btn q-quick-symbol" data-id="${q.id}" ${index>=total-1?'disabled':''} aria-label="Đưa câu ${index+1} xuống" title="Đưa câu xuống"`),
  b('question-meta',ico('settings')||'⚙',`class="icon q-quick-btn" data-id="${q.id}" aria-label="Thông tin câu ${index+1}" title="Thuộc tính, nguồn & xóa câu"`),
 ].join('');
}

/** Suy luận ngữ cảnh làm việc hiện tại của đề để gợi ý hành động Trợ lý phù hợp. */
export function inferAssistantContextState(exam,{selectedId=null,scope=null,matrixOpen=false,matrixPhase=null}={}){
 const questions=exam?.questions||[];
 const docs=exam?.docs||[];
 const attachedIds=new Set(exam?.assistantSources||[]);
 const attachedDocs=docs.filter(d=>attachedIds.has(d.id));
 const reviewQuestions=questions.map((q,index)=>({q,index})).filter(({q})=>q?.check?.version===q?.v&&q.check.status==='review');
 const unapprovedQuestions=questions.map((q,index)=>({q,index})).filter(({q})=>!isApproved(q));
 const activeSelectedId=scope?.id||selectedId;
 const selectedIndex=activeSelectedId?questions.findIndex(q=>q.id===activeSelectedId):-1;
 const selectedQuestion=selectedIndex>=0?questions[selectedIndex]:null;
 const reqCount=(exam?.matrix||[]).reduce((n,r)=>n+(r.targets||[]).reduce((a,b)=>a+(Number(b)||0),0),0);
 const readableDocs=docs.filter(d=>documentPages(d).some(p=>p.text?.trim()));
 let mode='empty';
 if(matrixOpen)mode='matrix-open';
 else if(selectedQuestion||scope)mode='selected-question';
 else if(questions.length&&(reviewQuestions.length||unapprovedQuestions.length))mode='needs-review';
 else if(questions.length)mode='ready';
 else if(attachedDocs.length||docs.length)mode='has-sources';
 return {
  mode,
  matrixPhase,
  questionCount:questions.length,
  docsCount:docs.length,
  attachedCount:attachedDocs.length,
  readableDocsCount:readableDocs.length,
  reviewCount:reviewQuestions.length,
  unapprovedCount:unapprovedQuestions.length,
  approvedCount:questions.length-unapprovedQuestions.length,
  reqCount,
  selectedIndex,
  selectedQuestion,
  firstIssue:reviewQuestions[0]||unapprovedQuestions[0]||null,
 };
}

/** Sinh các hành động gợi ý thông minh theo 5 trạng thái đề thay cho 3 nút tĩnh. */
export function buildContextualAssistantSuggestions(exam,options={}){
 const st=inferAssistantContextState(exam,options);
 const subject=exam?.subject||'Môn học';
 const grade=exam?.grade?`Lớp ${exam.grade}`:'';
 if(st.mode==='matrix-open'){
  return {
   ...st,
   badge:'Đang mở ma trận đề',
   summary:st.matrixPhase==='running'
    ?'Trợ lý đang tự sinh và giải lại từng câu theo ma trận.'
    :st.matrixPhase==='review'
     ?'Xem bản đề xuất trên trang rồi bấm ✓ Chấp nhận hoặc ✕ Bỏ đề xuất.'
     :`Kiểm tra chủ đề, điểm và ${st.attachedCount?st.attachedCount+' nguồn đang gắn':'gắn nguồn'} trước khi sinh.`,
   actions:[
    {kind:'action',action:'assistant-sources',label:st.attachedCount?`Nguồn đang gắn (${st.attachedCount})`:'Gắn nguồn cho ma trận',hint:'SGK, Đề cá nhân, Cộng đồng, Tệp',tag:'Nguồn đối chiếu'},
    {kind:'action',action:'matrix',label:'Mở bảng ma trận đầy đủ',hint:`${st.reqCount} câu yêu cầu`,tag:'Cơ cấu đề'},
   ],
  };
 }
 if(st.mode==='selected-question'&&st.selectedQuestion){
  const qNum=st.selectedIndex+1;
  const q=st.selectedQuestion;
  const typeLabel=QUESTION_TYPES[q.type||'mcq']||'Câu hỏi';
  return {
   ...st,
   badge:options.scope?.text&&!options.scope.wholeField?`Đang bôi đen Câu ${qNum}`:`Đang chọn Câu ${qNum} · ${typeLabel}`,
   summary:`Sửa đúng Câu ${qNum} hoặc kiểm tra độc lập trước khi duyệt.`,
   actions:[
    {kind:'prompt',action:'studio-prompt',label:`Viết lại Câu ${qNum} rõ hơn, giữ đáp án`,prompt:`Viết lại câu ${qNum} cho rõ ràng và chuẩn mực hơn, giữ nguyên ý chính và đáp án đúng.`,hint:'Tạo diff 2 cột để đối chiếu',tag:'Sửa đúng câu chọn',primary:true},
    {kind:'action',action:'ai-check',label:`Giải lại độc lập Câu ${qNum} bằng AI`,dataId:q.id,hint:'Không đưa đáp án lưu cho AI',tag:'Kiểm tra độc lập'},
    {kind:'action',action:'quick-formula',label:`Chèn công thức / mẫu Câu ${qNum}`,dataId:q.id,hint:'Mở composer trực quan',tag:'Công thức & mẫu'},
   ],
  };
 }
 if(st.mode==='needs-review'&&st.firstIssue){
  const issueNum=st.firstIssue.index+1;
  return {
   ...st,
   badge:st.reviewCount?`${st.reviewCount} câu cần rà · ${st.approvedCount}/${st.questionCount} đã duyệt`:`${st.unapprovedCount}/${st.questionCount} câu chờ duyệt`,
   summary:'Mở nhanh câu cần kiểm tra, giải lại bằng AI hoặc lập ma trận ngược từ đề.',
   actions:[
    {kind:'action',action:'jump-first-review',label:`Mở câu cần rà đầu tiên (Câu ${issueNum})`,dataId:st.firstIssue.q.id,hint:st.reviewCount?'Có cảnh báo cần xem lại':'Chưa gắn dấu duyệt',tag:'Ưu tiên rà soát',primary:true},
    {kind:'action',action:'ai-check',label:`Giải lại Câu ${issueNum} bằng AI`,dataId:st.firstIssue.q.id,hint:'Đối chiếu đáp án & căn cứ',tag:'Giải độc lập'},
    {kind:'action',action:'local-matrix',label:exam?.matrixConfirmed?'Sinh thêm theo ma trận':'Lập ma trận ngược từ đề',hint:`${st.questionCount} câu hiện có`,tag:'Ma trận đề'},
   ],
  };
 }
 if(st.mode==='has-sources'){
  const srcCount=st.attachedCount||st.docsCount;
  const actions=[
   {kind:'action',action:'local-matrix',label:`Sinh đề từ ${srcCount} nguồn đã nạp`,hint:exam?.matrixConfirmed?`Ma trận ${st.reqCount} câu đã xác nhận`:'Đề xuất / chỉnh ma trận rồi sinh',tag:'Theo nguồn đã gắn',primary:true},
   {kind:'action',action:'assistant-sources',label:'Chọn trang & 4 kênh nguồn',hint:`${st.attachedCount} đang gắn · ${st.docsCount} tài liệu`,tag:'Quản lý nguồn'},
  ];
  if(st.readableDocsCount)actions.push({kind:'action',action:'parse-first-doc',label:'Tách câu từ đề cũ trong nguồn',hint:'Nhận diện Câu 1 / Bài 1 tại máy',tag:'Tách câu nhanh'});
  return {
   ...st,
   badge:`Đã có ${srcCount} nguồn sẵn sàng`,
   summary:'Sinh đề bám sát trang nguồn đã chọn hoặc tách câu hỏi từ tệp vừa nạp.',
   actions,
  };
 }
 if(st.mode==='ready'){
  return {
   ...st,
   badge:`Đã duyệt ${st.questionCount}/${st.questionCount} câu`,
   summary:'Đề đã sẵn sàng kiểm tra ngắt trang A4, tạo nhiều mã đề hoặc lập ma trận đối chiếu.',
   actions:[
    {kind:'action',action:'export',label:'Kiểm tra A4 & Xuất đề / Mã đề',hint:'Preflight · Word, PDF, HTML',tag:'Sẵn sàng xuất',primary:true},
    {kind:'action',action:'local-matrix',label:'Lập ma trận ngược / Sinh thêm',hint:'Đối chiếu chủ đề & mức độ',tag:'Ma trận đối chiếu'},
    {kind:'action',action:'assistant-sources',label:'Xem nguồn đang gắn',hint:`${st.attachedCount} nguồn`,tag:'Nguồn tài liệu'},
   ],
  };
 }
 return {
  ...st,
  badge:`Đề trống · ${subject}${grade?' '+grade:''}`,
  summary:'Kéo–thả tệp (.docx, .pdf, ảnh…) vào khung này hoặc chọn học liệu, ma trận để bắt đầu.',
  actions:[
   {kind:'action',action:'import-doc',label:'Tải hoặc kéo–thả nguồn tài liệu',hint:'.docx, .pdf, .txt, .md, .pptx, ảnh',tag:'Từ kho của thầy cô',primary:true},
   {kind:'action',action:'lesson-sources',label:'Chọn học liệu mẫu / SGK',hint:[subject,grade].filter(Boolean).join(' · '),tag:'Bám sát chương trình'},
   {kind:'action',action:'local-matrix',label:`Soạn đề ${subject} theo ma trận`,hint:'Gợi ý cơ cấu & tự kiểm câu',tag:'Đề xuất theo ma trận'},
  ],
 };
}

export function contextualSuggestionsHTML(exam,options={}){
 const plan=buildContextualAssistantSuggestions(exam,options);
 const contextHeaderHTML=`<div class="assistant-context-head" style="display:flex;flex-direction:column;align-items:flex-start;gap:6px;width:100%;margin:0 0 8px"><span class="ctx-badge assistant-context-badge" style="display:inline-block;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:600;line-height:1.35;background:#e6f4ef;color:#11695b">${esc(plan.badge)}</span><p class="ctx-summary" style="display:block;margin:0;font-size:12.5px;line-height:1.45;color:#4f645d">${esc(plan.summary)}</p></div>`;
 const buttons=plan.actions.map(item=>{
  const attrs=item.kind==='prompt'
   ?`class="suggestion-card${item.primary?' is-primary':''}" data-prompt="${esc(item.prompt)}"`
   :`class="suggestion-card${item.primary?' is-primary':''}"${item.dataId?` data-id="${esc(item.dataId)}"`:''}`;
  const sub=item.hint?`<small>${esc(item.hint)}</small>`:'';
  const tag=item.tag?`<em class="suggestion-tag" style="display:inline-flex;align-self:flex-start;font-style:normal;font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;margin-top:3px;background:${item.primary?'#eef2ff':'#f1f5f9'};color:${item.primary?'#3730a3':'#475569'};line-height:1.35">${esc(item.tag)}</em>`:'';
  return b(item.action,`<span><b>${esc(item.label)}</b>${sub}${tag}</span><span>→</span>`,attrs);
 }).join('');
 return {plan,buttons,contextHeaderHTML};
}

function setDropOverlayState(active,message=''){
 document.querySelectorAll('.assistant, .assistant-panel, .chat, #chat-form, #prompt, .upload-zone').forEach(el=>{
  if(el!==activeDropHost)el.classList.remove('is-drop-active');
 });
 const overlay=document.querySelector('.assistant-drop-overlay');
 if(overlay){
  overlay.hidden=!active||activeDropHost?.classList?.contains('upload-zone');
  overlay.style.display=overlay.hidden?'none':'grid';
  if(message&&overlay.querySelector('strong'))overlay.querySelector('strong').textContent=message;
 }
}

function clearDropState(){
 if(activeDropHost)activeDropHost.classList.remove('is-drop-active');
 activeDropHost=null;
 setDropOverlayState(false);
}

function bindAssistantDropZone(){
 const assistant=document.querySelector('.assistant');
 if(assistant&&!assistant.querySelector('.assistant-drop-overlay')){
  const overlay=document.createElement('div');
  overlay.className='assistant-drop-overlay';
  overlay.hidden=true;
  overlay.setAttribute('aria-hidden','true');
  overlay.style.cssText='position:absolute;inset:8px;z-index:25;display:none;place-items:center;pointer-events:none;border:2px dashed #12675d;border-radius:14px;background:rgba(242,248,245,0.94);color:#124e42;text-align:center;padding:20px';
  overlay.innerHTML='<div class="assistant-drop-card"><strong>Thả tệp để nạp nguồn cho Trợ lý</strong><p style="margin:6px 0 0;font-size:12px;color:#3d6155">Hỗ trợ .docx, .pdf, .txt, .md, .pptx và ảnh PNG/JPEG/WEBP (tối đa 15 MB)</p></div>';
  assistant.append(overlay);
 }
 if(dropInitialized)return;
 dropInitialized=true;
 const resolveZone=target=>target?.closest?.(DROP_ZONE_SELECTOR)||null;
 const resolveHost=zone=>!zone?null:zone.classList.contains('upload-zone')?zone:(zone.closest('.assistant, .assistant-panel, .chat')||zone);
 document.addEventListener('dragenter',event=>{
  if(!hasDraggedFiles(event.dataTransfer))return;
  const host=resolveHost(resolveZone(event.target));
  if(!host)return;
  event.preventDefault();
  activeDropHost=host;
  host.classList.add('is-drop-active');
  setDropOverlayState(true);
 });
 document.addEventListener('dragover',event=>{
  if(!hasDraggedFiles(event.dataTransfer))return;
  const host=resolveHost(resolveZone(event.target));
  if(!host){clearDropState();return;}
  event.preventDefault();
  if(event.dataTransfer)event.dataTransfer.dropEffect='copy';
  if(activeDropHost!==host){
   activeDropHost?.classList.remove('is-drop-active');
   activeDropHost=host;
  }
  host.classList.add('is-drop-active');
  setDropOverlayState(true);
 });
 document.addEventListener('dragleave',event=>{
  if(!activeDropHost)return;
  if(event.relatedTarget&&activeDropHost.contains(event.relatedTarget))return;
  if(!event.relatedTarget||!resolveHost(resolveZone(event.relatedTarget)))clearDropState();
 });
 document.addEventListener('dragend',clearDropState);
 document.addEventListener('drop',async event=>{
  const zone=resolveZone(event.target);
  const host=resolveHost(zone);
  clearDropState();
  if(!host)return;
  const files=extractDroppedFiles(event.dataTransfer);
  if(!files.length)return;
  event.preventDefault();
  event.stopPropagation();
  if(document.querySelector('.paper.ai-writing')){
   c?.toast?.('Chờ AI xử lý xong rồi nạp thêm nguồn.');
   return;
  }
  const {accepted,rejected}=filterDroppedSourceFiles(files);
  if(!accepted.length){
   c?.toast?.(rejected[0]?.error||'Định dạng tệp chưa hỗ trợ.');
   return;
  }
  if(rejected.length)c?.toast?.(rejected[0].error);
  else if(accepted.length>1)c?.toast?.(`Đang nạp tệp "${accepted[0].name}" (hỗ trợ đối chiếu từng tệp một).`);
  const attachToAssistant=!host.classList.contains('upload-zone');
  try{
   if(typeof c?.importDroppedFile==='function')await c.importDroppedFile(accepted[0],{attachToAssistant});
   else c?.toast?.('Chưa sẵn sàng bộ đọc tệp tại đây.');
  }catch(err){
   c?.toast?.(err?.message||'Chưa đọc được tệp đã thả.');
  }
 });
}
export function formatProviderName(raw){
 const s=String(raw||'').trim();
 if(!s)return '';
 const low=s.toLowerCase();
 if(low==='deepseek'||low.startsWith('deepseek'))return 'DeepSeek';
 if(low==='gemini'||low.startsWith('gemini'))return 'Gemini';
 if(low==='ollama'||low.startsWith('ollama'))return 'Ollama';
 if(low==='agy'||low==='agy_cli'||low==='agy-cli'||low.startsWith('agy'))return 'AGY CLI';
 if(low==='openai'||low.startsWith('gpt'))return 'OpenAI';
 return s;
}
export function formatLatencyLabel(ms){
 const n=Number(ms);
 if(!Number.isFinite(n)||n<=0)return '';
 return Math.max(0.1,n/1000).toFixed(1).replace('.',',')+'s';
}
export function chatMetaBadgeText(m){
 const provider=formatProviderName(m?.providerUsed);
 const fallbackFrom=formatProviderName(m?.fallbackFrom);
 const latency=formatLatencyLabel(m?.latencyMs);
 const label=fallbackFrom?(provider?`${provider} (dự phòng từ ${fallbackFrom})`:`Dự phòng từ ${fallbackFrom}`):provider;
 if(label&&latency)return `${label} · ${latency}`;
 return label||latency;
}
export function effortInstruction(e){return ['Trả lời ngắn gọn, giữ đủ đáp án và căn cứ cần thiết.','Trình bày lời giải theo các bước chính và đối chiếu các điều kiện.','Phân tích kỹ điều kiện, trường hợp đặc biệt; tự kiểm tra kết quả và nêu các bước giải, thang điểm chi tiết.'][e.aiEffort??1];}
export function referenceSide(e,selected,tab){
 if(tab==='templates')return `<button class="template-card reference-featured" data-action="load-reference-exam"><strong>Tuyển sinh 10 · Đề hoàn chỉnh</strong><small>5 bài · 10 điểm · hình, tham số và barem chi tiết</small></button><button class="template-card" data-action="load-ai-demo"><strong>Đề minh họa AI · 5 bài + hình</strong><small>Qwen3:8b đã tạo · cần giáo viên rà soát</small></button>${[['Tuyển sinh vào lớp 10',120],['Giữa học kỳ',90],['Cuối học kỳ II',90]].map(([period,minutes])=>`<button class="template-card" data-action="template-frame" data-period="${period}" data-minutes="${minutes}"><strong>${period} · Toán 9</strong><small>Khung 5 bài, tổng 10 điểm, đáp án và barem</small></button>`).join('')}<div class="template-intro">Chọn mẫu để tạo một đề riêng</div>${[['essay-sample','Toán 9 · Tự luận','5 bài · 90 phút · đáp án và thang điểm'],['create-sample','Toán 9 · Trắc nghiệm','Phương trình, hàm số, hình học'],['create-sample','Địa lí 10','Bảng số liệu và biểu đồ'],['create-sample','Ngữ văn 9','Đọc hiểu và đối chiếu ngữ liệu']].map(([a,t,d],i)=>`<button class="template-card" data-action="${a}" data-subject="${['Toán','Toán','Địa lí','Ngữ văn'][i]}"><div class="mini-sheet">${Array.from({length:5},()=>'<i></i>').join('')}</div><strong>${t}</strong><small>${d}</small></button>`).join('')}`;
 if(tab!=='outline')return null;
 if(!e.questions.length)return '<p class="outline-empty">Các tiêu đề và câu hỏi trong tài liệu sẽ xuất hiện ở đây.</p>';
 return `<button class="outline-section" data-action="scroll-heading">${e.questions.every(q=>q.type==='essay')?'PHẦN I. CÂU HỎI TỰ LUẬN':'PHẦN I. CÂU HỎI'}</button>${e.questions.map((q,i)=>`<button class="outline-item ${selected===q.id?'active':''}" data-action="select" data-id="${q.id}" title="${esc(q.stem)}"><span class="outline-title">${q.type==='essay'?'Bài':'Câu'} ${i+1}${q.points?' ('+q.points+' điểm)':''}. ${esc(q.stem||'Câu hỏi mới')}</span></button>`).join('')}${b(separateMarking(e)?'scroll-marking':'view-teacher','HƯỚNG DẪN CHẤM VÀ THANG ĐIỂM','class="outline-section"')}${separateMarking(e)?b('scroll-marking','A. HƯỚNG DẪN CHUNG','class="outline-section" data-target="marking-general"')+b('scroll-marking','B. ĐÁP ÁN VÀ THANG ĐIỂM','class="outline-section" data-target="marking-table"'):''}`;
}
export function referenceChat(e,options={}){
 const welcome=e.chat.length<=1;
 const {plan,buttons,contextHeaderHTML}=contextualSuggestionsHTML(e,options);
 return `${welcome?`<div class="assistant-welcome"><h2 style="color:#2563eb;font-weight:700;text-align:center;line-height:1.35;margin:2px 0 6px">Thầy cô muốn soạn đề<br>cho lớp nào trước?</h2><p style="text-align:center;margin:0 0 8px">${esc(plan.summary)}</p></div>`:e.chat.filter((m,i)=>!(i===0&&m.role==='assistant'&&/^(Đây là ví dụ Toán|Thầy cô đang mở ví dụ|Đề mới đã áp dụng)/.test(m.text))).map(m=>`<div class="assistant-message ${m.role==='assistant'?'role-assistant':'user'}">${m.role==='assistant'?'<span class="chat-spark">✧</span>':''}<div>${esc(m.text).replace(/\n/g,'<br>')}</div></div>`).join('')}<div class="assistant-shortcuts" data-context-mode="${esc(plan.mode)}">${contextHeaderHTML}${buttons}</div>`;
}
function sourceBadge(d){if(d.catalog||d.personalLesson)return 'SGK';if(d.communityToken)return 'CỘNG ĐỒNG';if(d.sourceExamId)return 'ĐỀ';return 'TỆP';}
function sourceChannelKey(d){if(d.catalog||d.personalLesson)return 'sgk';if(d.communityToken)return 'community';if(d.sourceExamId)return 'exam';return 'file';}
function examSummaryText(ex){return (ex.questions||[]).map((q,i)=>`Câu ${i+1}. ${q.stem||''}`).join('\n').trim()||(ex.instructions||'').trim()||ex.title||'Đề cá nhân';}
export function referenceCompose(e,scope){const ico=k=>c?.icon?.(k)||'';const attached=(e.assistantSources||[]).map(id=>e.docs.find(d=>d.id===id)).filter(Boolean);const currentPreset=CHAT_TIME_PRESETS.some(([id])=>id===e?.aiTimePreset)?e.aiTimePreset:'standard';const quickBtnStyle='font-size:10.5px;line-height:1.2;padding:2px 5px;min-height:22px;border-radius:6px;border:1px solid #d5dfda;background:#f8fbf9;color:#1e3a32;white-space:nowrap;cursor:pointer;font-weight:500';return `<div class="assistant-source-bar" style="display:flex;align-items:center;justify-content:space-between;gap:4px;flex-wrap:wrap;padding:1px 0 5px;margin:0"><span class="assistant-source-label" style="font-size:9.5px;font-weight:700;letter-spacing:0;color:#52665f;white-space:nowrap;flex-shrink:0">NGUỒN CHO TRỢ LÝ</span><div class="assistant-source-actions" style="display:inline-flex;align-items:center;gap:3px;flex-wrap:wrap">${b('import-doc','+ Kho tài liệu',`class="source-quick-btn" style="${quickBtnStyle}" title="Tải tài liệu từ máy"`)}${b('lesson-sources','Bài SGK',`class="source-quick-btn" style="${quickBtnStyle}" title="Mở danh sách Bộ sách / Chương / Bài SGK"`)}${b('community-exams','Đề cộng đồng',`class="source-quick-btn" style="${quickBtnStyle}" title="Mở kho đề cộng đồng"`)}</div></div><div class="assistant-sources"><div><b>NGUỒN ĐÃ GẮN (${attached.length})</b><span>Chọn SGK, tệp OCR, đề cá nhân hoặc đề cộng đồng</span></div><div class="source-chips">${attached.map(d=>`<span class="source-chip-wrap" data-channel="${sourceChannelKey(d)}">${b('source',`<span class="pill source-channel-badge" data-channel="${sourceChannelKey(d)}">${sourceBadge(d)}</span> ${esc(d.name)}`,`class="source-chip" data-doc="${esc(d.id)}" title="Mở xem nguồn: ${esc(d.name)}"`)}${b('detach-source','×',`class="source-detach" aria-label="Gỡ nguồn ${esc(d.name)}" title="Gỡ nguồn này khỏi trợ lý" data-doc="${esc(d.id)}"`)}</span>`).join('')}${b('assistant-sources','＋ Nguồn (4 kênh)','class="add-source"')}</div></div><div class="compose-box">${scope?`<div class="selection-chip" title="${esc(scope.text)}">${b('scope-details',`↳ Câu ${e.questions.findIndex(q=>q.id===scope.id)+1} · ${esc(scope.text.slice(0,64))}`)}</div>`:''}<textarea id="chat-input" aria-label="Nhắn với trợ lý" placeholder="Nhập yêu cầu tạo, sửa, giải hoặc kéo–thả tài liệu vào đây…" rows="2"></textarea><div class="compose-bottom"><div class="compose-attachments">${b('import-doc',ico('image'),'title="Thêm ảnh hoặc tài liệu" aria-label="Thêm ảnh hoặc tài liệu"')}${b('assistant-sources',ico('paperclip'),'title="Đính kèm nguồn" aria-label="Đính kèm nguồn"')}</div><select id="chat-time-preset" name="chat-time-preset" class="chat-time-select" aria-label="Thời gian chạy AI" style="margin-left:auto;max-width:225px;height:30px;min-height:30px;padding:2px 8px;font-size:12px;border:1px solid #d5dfda;border-radius:8px;background:#f8fbf9;color:#27443d;cursor:pointer">${CHAT_TIME_PRESETS.map(([id,label])=>`<option value="${id}"${currentPreset===id?' selected':''}>${label}</option>`).join('')}</select><button class="primary" type="submit" aria-label="Gửi yêu cầu">${ico('send')}</button></div></div><div class="chat-foot">Trợ lý AI có thể mắc sai sót. Hãy kiểm tra nội dung nhé.</div>`;}
export function mountReference(context){c=context;$('.sidebar-top').innerHTML=`<div class="sidebar-title">Tài liệu ${b('collapse-outline','◧','title="Thu gọn mục lục" aria-label="Thu gọn mục lục"')}</div>`;$('.chat-compose').innerHTML=referenceCompose(c.exam(),c.currentScope());$('.assistant-head .assistant-title').innerHTML=`<span>Trợ lý AI soạn đề</span>${b('memory','· Trí nhớ','class="assistant-memory-btn" title="Cách ra đề của thầy cô (Trí nhớ trợ lý)" aria-label="Mở Trí nhớ trợ lý"')}`;$('.assistant-head .row').innerHTML=b('reset-chat','↶','title="Xóa lịch sử trò chuyện" aria-label="Xóa lịch sử trò chuyện"')+b('connections',c.icon('settings'),'title="Kết nối AI" aria-label="Xem kết nối"')+b('toggle-ai','×','title="Đóng trợ lý" aria-label="Đóng trợ lý"');
 bindAssistantDropZone();
 const more=document.createElement('div');more.className='reference-toolbar-extra';more.innerHTML=`<select id="paragraph-style" aria-label="Kiểu văn bản"><option value="normal">Văn bản thường</option><option value="bold">Tiêu đề</option><option value="italic">Phụ đề</option></select>`;$('.toolbar-divider').after(more);const size=$('#doc-fontsize');size.before(Object.assign(document.createElement('button'),{type:'button',textContent:'−',ariaLabel:'Giảm cỡ chữ'}));size.previousSibling.dataset.action='font-smaller';size.after(Object.assign(document.createElement('button'),{type:'button',textContent:'+',ariaLabel:'Tăng cỡ chữ'}));size.nextSibling.dataset.action='font-larger';
 const formats=document.createElement('span');formats.className='color-tools';formats.innerHTML=`<label title="Màu chữ">A<input type="color" id="text-color" value="#111111" aria-label="Màu chữ"></label><label title="Màu đánh dấu">▰<input type="color" id="highlight-color" value="#fff29d" aria-label="Màu đánh dấu"></label>`;$('.formula-tool').before(formats);
 const section=$('.paper-section'),instructions=$('.paper .instructions');if(section&&instructions)instructions.before(section);$('.paper').classList.toggle('empty-paper',!c.exam().questions.length);$('.paper-section').firstChild.textContent=c.isTeacher()?'HƯỚNG DẪN CHẤM VÀ THANG ĐIỂM':c.exam().questions.every(q=>q.type==='essay')?'PHẦN I. CÂU HỎI TỰ LUẬN':'PHẦN I. CÂU TRẮC NGHIỆM NHIỀU LỰA CHỌN';
 $('.paper-scroll').addEventListener('scroll',()=>{if(!document.querySelector('.inline-math-panel,.document-menu'))closeFloating();},{passive:true});if(!initialized){initialized=true;document.addEventListener('pointerdown',ev=>{if(!ev.target.closest('.floating-panel,[data-action="menu"],[data-action="effort-menu"],.formula-block'))closeFloating();});document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closeFloating();});document.addEventListener('selectionchange',selectionAsk);document.addEventListener('input',ev=>{if(ev.target.id==='inline-math-input')preview();});document.addEventListener('change',ev=>{if(ev.target.id==='formula-display')preview();if(ev.target.id==='effort-range'){const value=Number(ev.target.value);c.change('Đổi mức trình bày của trợ lý',e=>e.aiEffort=value,{renderPage:false});const cur=$('#effort-current'),toggle=$('.effort-toggle');if(cur)cur.textContent=effortNames[value];if(toggle)toggle.textContent='Mức: '+effortNames[value]+'⌄';}});}
}
export function closeFloating(){cleanupComposer();document.querySelectorAll('.floating-panel').forEach(n=>n.remove());}
export function showDropdown(anchor,html,cls=''){const anchorRect=anchor.getBoundingClientRect();closeFloating();const panel=document.createElement('div');panel.className='floating-panel '+cls;panel.innerHTML=html;document.body.append(panel);const r=anchorRect;panel.style.left=Math.max(8,Math.min(r.left,innerWidth-panel.offsetWidth-8))+'px';panel.style.top=Math.max(8,Math.min(r.bottom+5,innerHeight-panel.offsetHeight-8))+'px';if(panel.getBoundingClientRect().bottom>innerHeight)panel.style.top=Math.max(8,r.top-panel.offsetHeight-5)+'px';return panel;}
function selectionAsk(){setTimeout(()=>{const sel=getSelection(),n=sel?.anchorNode?.parentElement?.closest('.stem-editor,.rich-field-editor');$('.selection-ask')?.remove();if(!n||sel.isCollapsed||!sel.toString().trim())return;const scope=captureDOMSelection();if(!scope)return;const r=sel.getRangeAt(0).getBoundingClientRect();const ask=document.createElement('button');ask.className='selection-ask';ask.dataset.action='ask-selection';ask.textContent='✧ Hỏi AI';ask.style.left=Math.max(8,Math.min(r.left,innerWidth-140))+'px';ask.style.top=Math.max(8,Math.min(r.top-39,innerHeight-55))+'px';ask.addEventListener('mousedown',e=>e.preventDefault());document.body.append(ask);},0);}
function mathEditor(node,chemistry=false){flushEditor();const q=c.qget(node.dataset.id||c.getSelected());const f=q?.formulas?.find(x=>x.id===node.dataset.formula);formula={qid:q?.id,id:f?.id,version:q?.v,examRevision:c.exam().revision,examId:c.exam().id,chemistry,inlinePos:node.dataset.pos,editorKey:node.dataset.editorKey||currentEditorKey()};const latex=f?.latex||node.dataset.latex||'',editing=!!f||node.dataset.pos!==undefined;const panel=showDropdown(node,composerHTML({latex,subject:chemistry?'Hoá học':node.dataset.subject||c.exam().subject,editing,display:f?f.display!==false:node.dataset.display!=='false',canDelete:editing,aiButton:node.dataset.pos!==undefined?b('ask-formula-ai','Hỏi AI',`data-id="${q.id}" data-editor-key="${esc(formula.editorKey||q.id)}" data-pos="${esc(formula.inlinePos)}" data-latex="${esc(latex)}"`):''}),'inline-math-panel composer-shell');panel.setAttribute('role','dialog');panel.setAttribute('aria-label',editing?'Sửa nội dung theo môn':'Chèn nội dung theo môn');mountComposer(panel,{subject:chemistry?'Hoá học':node.dataset.subject||c.exam().subject,latex,editing,onText:content=>{const target=validFormula();if(target)insertRichContent(target.id,content,formula.editorKey);else createContentQuestion(content);closeFloating();}});}

function preview(){if(document.querySelector('.composer-shell')){refreshComposerPreview();return;}const area=$('#inline-math-input');if(!area)return;try{$('#inline-math-preview').innerHTML=katex.renderToString(area.value,{throwOnError:true,trust:false,displayMode:$('#formula-display').value==='block'});area.setCustomValidity('');}catch(e){$('#inline-math-preview').textContent='Kiểm tra cú pháp: '+e.message;area.setCustomValidity('Công thức chưa hợp lệ.');}const panel=area.closest('.floating-panel');if(panel){const r=panel.getBoundingClientRect();if(r.bottom>innerHeight-8)panel.style.top=Math.max(8,innerHeight-panel.offsetHeight-8)+'px';}}
function createContentQuestion(content){const doc={type:'doc',content},id=uid();c.change('Chèn nội dung vào câu đầu tiên',e=>{e.questions.push({id,v:1,type:'essay',stem:documentPlain(doc),richDoc:doc,options:[],answer:0,points:1,explanation:'',rubric:[],topic:e.matrix[0]?.topic||'Chủ đề mới',level:0,source:null,check:null});});c.setSelected(id);}
function validFormula(){if(formula&&!formula.qid){if(c.exam().id!==formula.examId||c.exam().revision!==formula.examRevision)throw Error('Đề đã thay đổi. Mở lại thư viện để chọn vị trí chèn.');return null;}const q=c.qget(formula?.qid);if(!q||c.exam().id!==formula.examId||q.v!==formula.version)throw Error('Câu đã đổi. Mở lại công thức để chỉnh sửa.');return q;}
export function captureAssistantSourceDraft(form,examId){
 if(!form||!examId)return null;
 const groups=[...form.querySelectorAll('[data-source-group]')];
 const pages=Object.fromEntries(groups.map(group=>[group.dataset.sourceGroup,[...group.querySelectorAll('[name=page]:checked')].map(input=>Number(input.value))]));
 const sources=groups.filter(group=>group.querySelector('[name=source]')?.checked).map(group=>group.dataset.sourceGroup);
 const personalExams=[...form.querySelectorAll('[name=personalExam]:checked')].map(input=>input.value);
 const strictTeacherOnly=Boolean(form.querySelector('[name=strictTeacherOnly]')?.checked);
 sourceModalDraft={examId,sources,pages,personalExams,strictTeacherOnly};
 return sourceModalDraft;
}
export function handleReferenceSubmit(f){if(f.id==='inline-math-form'){if(submitComposerText())return true;const q=validFormula(),latex=$('#inline-math-input').value,display=$('#formula-display').value==='block';katex.renderToString(latex,{throwOnError:true,trust:false});if(!q){createContentQuestion([{type:'paragraph',content:[{type:'mathInline',attrs:{id:uid(),latex,display}}]}]);closeFloating();return true;}if(formula.inlinePos!==undefined){updateInlineMath(q.id,formula.inlinePos,{latex,display},false,formula.editorKey);closeFloating();return true;}if(!formula.id&&insertInlineMath(q.id,latex,display,formula.editorKey)){closeFloating();return true;}closeFloating();c.change('Sửa công thức trên trang',()=>{q.formulas??=[];const old=q.formulas.find(x=>x.id===formula.id);if(old)Object.assign(old,{latex,display});else q.formulas.push({id:uid(),latex,display});touch(q);check(c.exam(),q);});return true;}if(f.id==='assistant-source-form'){const groups=[...f.querySelectorAll('[data-source-group]')];
 const pages=Object.fromEntries(groups.filter(group=>group.querySelector('[name=source]').checked)
  .map(group=>[group.dataset.sourceGroup,[...group.querySelectorAll('[name=page]:checked')].map(input=>Number(input.value))])
  .filter(([,numbers])=>numbers.length));
 const pickedExams=[...f.querySelectorAll('[name=personalExam]:checked')].map(input=>input.value);
 const strictTeacherOnly=Boolean(f.querySelector('[name=strictTeacherOnly]')?.checked);
 const allExams=c.getState?.().exams||[];
 sourceModalDraft=null;
 c.change('Chọn nguồn cho trợ lý',e=>{
  const attached=new Set(Object.keys(pages)),nextPages={...pages};
  for(const exId of pickedExams){
   const target=allExams.find(x=>x.id===exId);
   if(!target)continue;
   const text=examSummaryText(target),docId='exam-src-'+target.id;
   const rec={id:docId,sourceExamId:target.id,name:target.title||'Đề cá nhân',kind:'text',version:target.revision||1,text,pages:[{number:1,text}],sample:false};
   const old=e.docs.find(d=>d.id===docId);
   if(old)Object.assign(old,rec);else e.docs.push(rec);
   attached.add(docId);nextPages[docId]=[1];
  }
  e.assistantSources=[...attached];e.assistantSourcePages=nextPages;e.strictTeacherOnly=strictTeacherOnly;
 });$('#dialog').close();return true;}return false;}
export async function handleReferenceAction(action,node){if(handleComposerAction(action,node))return true;switch(action){
 case 'quick-formula':{const qid=node.dataset.id||c.getSelected();if(qid)c.setSelected(qid);const activeKey=currentEditorKey();if(qid&&(!activeKey||activeKey!==qid&&!activeKey.startsWith(qid+':')))node.dataset.editorKey=qid;mathEditor(node,false);return true;}
 case 'subject-library':case 'formula':case 'formula-edit':case 'chemistry':case 'math-inline-edit':mathEditor(node,action==='chemistry');return true;
 case 'math-symbol':{const a=$('#inline-math-input'),start=a.selectionStart,end=a.selectionEnd;a.setRangeText(node.dataset.latex,start,end,'end');a.focus();preview();return true;}
 case 'math-tab':{const chemistry=node.dataset.mode==='chemistry';formula.chemistry=chemistry;document.querySelectorAll('.math-editor-tabs button').forEach(n=>n.classList.toggle('active',n===node));$('#inline-math-input').placeholder=chemistry?'Ví dụ: H_{2}O, CO_{2}':'Nhập công thức LaTeX';return true;}
 case 'inline-math-delete':{const q=validFormula();if(formula.inlinePos!==undefined){updateInlineMath(q.id,formula.inlinePos,{},true,formula.editorKey);closeFloating();return true;}closeFloating();c.change('Xóa công thức',()=>{q.formulas=q.formulas.filter(x=>x.id!==formula.id);touch(q);check(c.exam(),q);});return true;}
 case 'floating-close':closeFloating();return true;
 case 'font-smaller':case 'font-larger':{const n=$('#doc-fontsize');n.value=Math.min(22,Math.max(10,Number(n.value)+(action==='font-larger'?1:-1)));n.dispatchEvent(new Event('change',{bubbles:true}));return true;}
 case 'collapse-outline':if(innerWidth<=1100&&$('.sidebar').classList.contains('open'))$('.sidebar').classList.remove('open');else $('.workspace').classList.toggle('outline-collapsed');return true;
 case 'scroll-heading':$('.paper-scroll').scrollTo({top:0,behavior:'smooth'});return true;
 case 'ask-selection':{const scope=c.currentScope();if(!scope)return true;$('.selection-ask')?.remove();$('.workspace').classList.remove('chat-hidden');$('aside.assistant').classList.add('open');$('.chat-compose').innerHTML=referenceCompose(c.exam(),scope);$('#chat-input').focus();return true;}
 case 'scope-details':{const q=c.qget(c.getSelected());if(q)c.modal('Nội dung đang chọn',`<p>${esc(c.currentScope()?.text)}</p><div class="buttons">${b('question-meta','Thuộc tính câu',`data-id="${q.id}"`)}${b('review','Xem rà soát và căn cứ',`data-id="${q.id}"`)}${b('ai-check','Giải lại bằng AI')}</div>`);return true;}
 case 'chat-suggestion':$('#chat-input').value=node.dataset.prompt;$('#chat-input').focus();return true;
 case 'reset-chat':c.modal('Xóa lịch sử trò chuyện?',`<p>Đề thi và các tài liệu vẫn được lưu. Có thể hoàn tác từ menu Chỉnh sửa.</p><div class="modal-foot">${b('close','Hủy')}${b('confirm-reset-chat','Xóa hội thoại','class="danger"')}</div>`);return true;
 case 'confirm-reset-chat':c.change('Xóa lịch sử trợ lý',e=>e.chat=[]);$('#dialog').close();return true;
 case 'effort-menu':showDropdown(node,`<div class="effort-heading">Mức trình bày <b id="effort-current">${effortNames[c.exam().aiEffort??1]}</b></div><p>Điều chỉnh độ chi tiết của hướng dẫn gửi cho AI.</p><input id="effort-range" type="range" min="0" max="2" step="1" value="${c.exam().aiEffort??1}" aria-label="Mức trình bày của AI"><div class="effort-labels"><span>Ngắn gọn</span><span>Kỹ hơn</span></div>`,'effort-panel');return true;
 case 'detach-source':{
  const id=node.dataset.doc;
  const detachBtns=typeof document!=='undefined'?[...document.querySelectorAll('.assistant-sources .source-detach')]:[];
  const idx=Math.max(0,detachBtns.indexOf(node));
  c.change('Gỡ nguồn khỏi trợ lý',e=>{e.assistantSources=(e.assistantSources||[]).filter(x=>x!==id);if(e.assistantSourcePages)delete e.assistantSourcePages[id];});
  pickDetachFocusTarget(idx)?.focus?.();
  return true;
 }
 case 'lesson-sources':captureAssistantSourceDraft($('#assistant-source-form'),c.exam()?.id);await (await import('./lesson-picker.js')).openLessonPicker(c);return true;
  case 'assistant-sources':{
   const e=c.exam(),allExams=(c.getState?.().exams||[]).filter(x=>x.id!==e.id);
   const draft=sourceModalDraft&&sourceModalDraft.examId===e.id?sourceModalDraft:null;
   if(!draft)sourceModalDraft=null;
   const attachedSet=new Set(draft?draft.sources:(e.assistantSources||[]));
   const personalSet=new Set(draft?draft.personalExams:allExams.filter(ex=>attachedSet.has('exam-src-'+ex.id)).map(ex=>ex.id));
   const strictTeacherOnly=draft?draft.strictTeacherOnly:Boolean(e.strictTeacherOnly);
   const groups=e.docs.map(d=>{
    const pages=documentPages(d).filter(p=>p.text?.trim());
    const selected=new Set(draft&&Array.isArray(draft.pages?.[d.id])?draft.pages[d.id]:selectedDocumentPages(e,d).map(p=>p.number));
    const warn=(d.warnings||[]).map(w=>`<p class="alert">${esc(w.message)}</p>`).join('');
    const isAttached=attachedSet.has(d.id);
    return `<div class="small-card source-group-card ${isAttached?'is-attached':''}" data-source-group="${esc(d.id)}"><div class="source-group-head"><label class="source-group-label"><input type="checkbox" name="source" value="${esc(d.id)}" ${isAttached?'checked':''} ${pages.length?'':'disabled'}> <span class="pill source-channel-badge" data-channel="${sourceChannelKey(d)}">${sourceBadge(d)}</span> <span class="source-group-title">${esc(d.name)}</span></label><span class="source-group-meta">${pages.length} ${d.catalog?'bài':'trang'}${isAttached?' · <b class="source-attached-tag">Đang gắn</b>':''}</span></div>${warn}<details><summary>Xem và chọn từng trang</summary>${pages.map(p=>`<label class="source-choice"><input type="checkbox" name="page" value="${esc(p.number)}" ${selected.has(p.number)?'checked':''}><span><b>${esc(sourcePageLabel(d,p.number))}${p.title?' · '+esc(p.title):''}</b><small>${esc(p.text.trim().slice(0,150))}</small></span></label>`).join('')||'<p>Đọc hoặc đối chiếu tài liệu trước khi chọn trang.</p>'}</details></div>`;
   });
   const personalCards=allExams.map(ex=>{
    const text=examSummaryText(ex),checked=personalSet.has(ex.id);
    return `<div class="small-card source-group-card ${checked?'is-attached':''}"><div class="source-group-head"><label class="source-group-label"><input type="checkbox" name="personalExam" value="${esc(ex.id)}" ${checked?'checked':''}> <span class="pill source-channel-badge" data-channel="exam">ĐỀ</span> <span class="source-group-title">${esc(ex.title)}</span></label><span class="source-group-meta">${ex.questions.length} câu · v${ex.revision||1}${checked?' · <b class="source-attached-tag">Đang gắn</b>':''}</span></div><details><summary>Xem nhanh nội dung (${text.length} ký tự)</summary><pre class="source-preview">${esc(text.slice(0,600))}</pre></details></div>`;
   });
   const draftCount=attachedSet.size+personalSet.size-(draft?[...personalSet].filter(id=>attachedSet.has('exam-src-'+id)).length:0);
   c.modal('Nguồn cho trợ lý (4 kênh)',`<form id="assistant-source-form"><div class="source-summary-banner"><span>Đang gắn cho trợ lý: <b>${draftCount} nguồn</b></span><div class="source-legend"><span class="pill source-channel-badge" data-channel="sgk">SGK</span><span class="pill source-channel-badge" data-channel="exam">ĐỀ</span><span class="pill source-channel-badge" data-channel="community">CỘNG ĐỒNG</span><span class="pill source-channel-badge" data-channel="file">TỆP</span></div></div><label class="source-strict-toggle"><input type="checkbox" name="strictTeacherOnly" ${strictTeacherOnly?'checked':''}> Chỉ bám tài liệu tôi tải lên (không dùng nguồn mẫu/chung)</label><div class="source-tabs" role="tablist"><button type="button" role="tab" aria-selected="true" data-src-tab="docs" class="active">Tệp &amp; Tài liệu đề (${e.docs.length})</button><button type="button" role="tab" aria-selected="false" data-src-tab="personal">Đề cá nhân (${allExams.length})</button>${b('lesson-sources','SGK / Bài học','class="source-tab-link" data-channel="sgk"')}${b('community-exams','Đề cộng đồng','class="source-tab-link" data-channel="community"')}</div><div data-src-panel="docs">${groups.join('')||'<p class="hint">Chưa có tài liệu/SGK trong đề này. Dùng Thêm tệp tại máy hoặc SGK / Bài học.</p>'}</div><div data-src-panel="personal" hidden><p class="hint">Hiển thị toàn bộ đề cá nhân (gồm cả đề ngắn). Xem nhanh tách biệt khỏi ô chọn.</p>${personalCards.join('')||'<p class="hint">Chưa có đề cá nhân khác trong kho.</p>'}</div><div class="modal-foot">${b('import-doc','Thêm tệp tại máy')}${b('close','Hủy')}<button class="primary" type="submit">Dùng các nguồn đã chọn</button></div></form>`);
   const form=$('#assistant-source-form'),dlg=$('#dialog');
   if(dlg&&!dlg.dataset.sourceDraftBound){dlg.dataset.sourceDraftBound='1';dlg.addEventListener('close',()=>{sourceModalDraft=null;});}
   form.addEventListener('click',ev=>{const t=ev.target.closest('[data-src-tab]');if(!t)return;form.querySelectorAll('[data-src-tab]').forEach(x=>{const on=x===t;x.classList.toggle('active',on);x.setAttribute('aria-selected',String(on));});form.querySelectorAll('[data-src-panel]').forEach(p=>p.hidden=p.dataset.srcPanel!==t.dataset.srcTab);});
   form.addEventListener('change',event=>{
    if(event.target.name==='page'&&event.target.checked)event.target.closest('[data-source-group]').querySelector('[name=source]').checked=true;
    captureAssistantSourceDraft(form,e.id);
   });
   return true;
  }
 case 'essay-sample':{const e=essaySample(c.getState().prefs);e.fullExam=true;c.getState().exams.push(e);c.getState().current=e.id;c.setTab('outline');c.setSelected(e.questions[0].id);c.persist();$('#dialog').close();c.render();return true;}
 case 'add-essay':{const q={id:uid(),v:1,type:'essay',stem:'Nhập nội dung bài tự luận…',options:[],answer:0,points:2,explanation:'',rubric:[],topic:c.exam().matrix[0]?.topic||'Chủ đề mới',level:1,source:null};c.change('Thêm bài tự luận',e=>e.questions.push(q));c.setSelected(q.id);c.render();return true;}
 case 'rubric':{const q=c.qget(node.dataset.id||c.getSelected());if(!q)return true;c.modal('Lời giải và thang điểm',`<form id="rubric-form" data-id="${q.id}"><label>Điểm của bài</label><input name="points" type="number" min="0.05" max="10" step="0.05" required value="${q.points||2}"><label>Lời giải</label><textarea name="explanation" rows="5">${esc(q.explanation)}</textarea><label>Thang điểm: mỗi dòng “Nội dung | Điểm”</label><textarea name="rubric" rows="6">${esc((q.rubric||[]).map(r=>r.text+' | '+r.points).join('\n'))}</textarea><div class="modal-foot"><button type="submit" class="primary">Lưu thang điểm</button></div></form>`);return true;}
 default:return false;
}}
export function handleRubricSubmit(f){if(f.id!=='rubric-form')return false;const q=c.qget(f.dataset.id),fd=new FormData(f),points=Number(fd.get('points')),rubric=String(fd.get('rubric')).split('\n').filter(x=>x.trim()).map(line=>{const i=line.lastIndexOf('|');return {text:line.slice(0,i).trim(),points:Number(line.slice(i+1))};});if(rubric.some(r=>!r.text||!Number.isFinite(r.points)||r.points<=0)||rubric.length&&Math.abs(rubric.reduce((s,r)=>s+r.points,0)-points)>0.001)throw Error('Các dòng phải có nội dung và điểm dương; tổng thang điểm phải bằng điểm bài.');c.change('Sửa lời giải và thang điểm',()=>{q.points=points;q.rubric=rubric;q.explanation=String(fd.get('explanation'));touch(q);check(c.exam(),q);});$('#dialog').close();return true;}
export function rubricHTML(q){return `<div class="essay-answer"><b>Hướng dẫn giải</b><p>${esc(q.explanation).replace(/\n/g,'<br>')}</p>${q.rubric?.length?`<table class="rubric-table"><thead><tr><th>Nội dung</th><th>Điểm</th></tr></thead><tbody>${q.rubric.map(r=>`<tr><td>${esc(r.text)}</td><td>${r.points}</td></tr>`).join('')}</tbody></table>`:''}${b('rubric','Sửa lời giải và thang điểm',`class="tiny-btn" data-id="${q.id}"`)}</div>`;}
export function essaySample(prefs=[]){const e=mathSample(prefs),doc=e.docs[0];e.title='Đề kiểm tra cuối học kỳ II';e.school='TRƯỜNG THCS …';e.minutes=90;e.layout={font:'Times New Roman',fontSize:15};e.instructions='Thí sinh trình bày lời giải đầy đủ. Đề gồm 5 bài tự luận.';e.chat=[];const entries=[['Phương trình','Giải các phương trình sau:\na) 2x + 3 = 11.\nb) x² − 5x + 6 = 0.','a) 2x = 8, suy ra x = 4.\nb) (x − 2)(x − 3) = 0, suy ra x = 2 hoặc x = 3.',[['Giải đúng phương trình bậc nhất',1],['Phân tích được đa thức thành nhân tử',0.5],['Kết luận đầy đủ hai nghiệm',0.5]]],['Hàm số','Cho hàm số y = 2x + 1.\na) Tính y khi x = 3.\nb) Tìm x để y = 9.','a) Khi x = 3, y = 2 × 3 + 1 = 7.\nb) 2x + 1 = 9 nên x = 4.',[['Tính đúng giá trị y = 7',1],['Tìm đúng x = 4',1]]],['Hình học','Một tam giác ABC vuông tại A có AB = 6 cm, AC = 8 cm.\na) Tính BC.\nb) Tính diện tích tam giác ABC.','a) BC² = AB² + AC² = 36 + 64 = 100 nên BC = 10 cm.\nb) S = AB × AC / 2 = 24 cm².',[['Áp dụng định lý Pythagore và tính BC = 10 cm',1],['Tính diện tích bằng 24 cm²',1]]],['Xác suất','Gieo một xúc xắc cân đối sáu mặt một lần.\na) Liệt kê các kết quả có thể xảy ra.\nb) Tính xác suất xuất hiện số chấm chẵn.','a) Không gian mẫu Ω = {1; 2; 3; 4; 5; 6}.\nb) Có 3 kết quả thuận lợi là 2, 4, 6; xác suất bằng 3/6 = 1/2.',[['Liệt kê đủ sáu kết quả',1],['Xác định 3 kết quả thuận lợi và tính xác suất 1/2',1]]],['Phương trình','Một hình chữ nhật có chiều dài hơn chiều rộng 3 cm và diện tích 40 cm². Tính chiều dài và chiều rộng.','Gọi chiều rộng là x cm (x > 0), chiều dài x + 3 cm.\nTa có x(x + 3) = 40 ⇔ (x + 8)(x − 5) = 0.\nDo x > 0, chọn x = 5. Chiều rộng 5 cm, chiều dài 8 cm.',[['Đặt ẩn và điều kiện',0.5],['Lập đúng phương trình',0.5],['Giải được x = 5, loại nghiệm âm',0.5],['Kết luận đúng hai kích thước',0.5]]]];e.questions=entries.map(([topic,stem,explanation,rubric])=>({id:uid(),v:1,type:'essay',stem,explanation,options:[],answer:0,points:2,topic,level:1,source:{docId:doc.id,location:'Tư liệu ôn tập tự soạn'},rubric:rubric.map(([text,points])=>({text,points}))}));e.matrix=[...new Set(entries.map(x=>x[0]))].map(topic=>({topic,targets:[0,e.questions.filter(q=>q.topic===topic).length,0]}));e.questions.forEach(q=>check(e,q));return e;}

export function refreshReferenceScope(context){c=context;const box=$('.compose-box');if(!box)return;box.querySelector('.selection-chip')?.remove();const scope=c.currentScope();if(scope){const chip=document.createElement('div');chip.className='selection-chip';chip.title=scope.text;chip.innerHTML=b('scope-details',`↳ Câu ${c.exam().questions.findIndex(q=>q.id===scope.id)+1} · ${esc(scope.text.slice(0,64))}`);box.prepend(chip);}}

const isVisibleFocusable=el=>Boolean(el&&!el.hidden&&!el.disabled&&(!el.closest||!el.closest('[hidden]'))&&(typeof el.getClientRects!=='function'||el.getClientRects().length>0||typeof document==='undefined'));
/** Chọn phần tử nhận focus kế tiếp hợp lệ sau khi gỡ nguồn khỏi Trợ lý AI. */
export function pickDetachFocusTarget(prevIndex=0,doc=typeof document!=='undefined'?document:null){
 if(!doc)return null;
 const detachBtns=[...doc.querySelectorAll('.assistant-sources .source-detach')].filter(isVisibleFocusable);
 if(detachBtns.length)return detachBtns[Math.min(Math.max(0,prevIndex),detachBtns.length-1)];
 for(const sel of ['.assistant-sources .add-source','[data-action="add-source"]','[data-ux-action="attach"]','[data-action="lesson-sources"]','#chat-input','#prompt']){
  const found=[...doc.querySelectorAll(sel)].find(isVisibleFocusable);
  if(found)return found;
 }
 return null;
}

const SAFE_CELL_IMAGE_RE=/^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/i;
export function tableCellHTML(cell){
 if(cell&&typeof cell==='object'){
  if(typeof cell.data==='string'&&cell.data.length){
   const cap=cell.caption?`<small class="cell-caption">${esc(cell.caption)}</small>`:'';
   if(SAFE_CELL_IMAGE_RE.test(cell.data)){
    return `<img class="cell-image" src="${esc(cell.data)}" alt="${esc(cell.caption||'Hình câu hỏi')}">${cap}`;
   }
   return cap||esc('[Ảnh chưa hợp lệ]');
  }
  if(cell.type==='doc')return renderRichDocument(cell);
  if(cell.text!=null)return richTextHTML(String(cell.text));
  return '';
 }
 return richTextHTML(String(cell??''));
}
export function questionTablesHTML(q,actionBtn=b){
 return (q.tables||[]).map(t=>`<div class="asset-tools">${actionBtn('edit-table','Sửa bảng','tiny-btn',`data-id="${q.id}" data-table="${t.id}"`)}</div><table class="inserted-table">${(t.rows||[]).map(row=>`<tr>${row.map(cell=>`<td>${tableCellHTML(cell)}</td>`).join('')}</tr>`).join('')}</table>`).join('');
}

const normMatrixKey=v=>String(v||'').trim().toLocaleLowerCase('vi-VN');
const formatReversePts=v=>v==null?'chưa rõ điểm':`${Number(v).toLocaleString('vi-VN',{minimumFractionDigits:0,maximumFractionDigits:2})}đ`;

/** Tổng hợp đầy đủ cảnh báo P2, lệch điểm và cờ cần rà từ reverse_matrix hoặc dòng ma trận. */
export function summarizeReverseMatrixReport(report){
 if(!report||typeof report!=='object'){
  return {hasIssues:false,reviewRequired:false,warnings:[],pointConflicts:[],flaggedOrdinals:[],conflictOrdinals:[],slots:[],matrix:[]};
 }
 const warnings=[],seenWarn=new Set();
 const pushWarn=msg=>{
  const text=String(msg||'').trim();
  if(text&&!seenWarn.has(text)){seenWarn.add(text);warnings.push(text);}
 };
 for(const w of report.warnings||[])pushWarn(w);
 const pointConflicts=Array.isArray(report.pointConflicts)?report.pointConflicts.filter(Boolean):[];
 const slots=Array.isArray(report.slots)?report.slots.filter(Boolean):[];
 const matrix=Array.isArray(report.matrix)?report.matrix.filter(Boolean):[];
 const flaggedOrdinals=[],conflictOrdinals=[];
 for(const s of slots){
  if(s.pointConflict&&Number.isInteger(s.ordinal))conflictOrdinals.push(s.ordinal);
  if((s.needsReview||s.pointConflict)&&Number.isInteger(s.ordinal))flaggedOrdinals.push(s.ordinal);
 }
 if(Array.isArray(report.missingPointsOrdinals)){
  for(const ord of report.missingPointsOrdinals){
   if(Number.isInteger(ord)&&!flaggedOrdinals.includes(ord))flaggedOrdinals.push(ord);
  }
 }
 const rowHasFlag=matrix.some(r=>r.needsReview||r.pointConflict||(Array.isArray(r.warnings)&&r.warnings.length));
 for(const r of matrix){
  for(const w of r.warnings||[])pushWarn(w);
 }
 if((report.pointConflict||pointConflicts.length)&&!warnings.length){
  const summary=pointConflicts.map(c=>`${c.topic||'Chủ đề'} (${(c.distinctPoints||[]).map(formatReversePts).join(', ')})`).join('; ');
  pushWarn(summary?`Phát hiện lệch điểm trong cùng chủ đề/mức: ${summary}. Giáo viên cần kiểm tra lại trước khi xác nhận.`:'Phát hiện lệch điểm giữa các câu cùng chủ đề/mức; cần giáo viên kiểm lại.');
 }
 const reviewRequired=Boolean(report.reviewRequired||report.needsReview||report.pointConflict||pointConflicts.length||flaggedOrdinals.length||rowHasFlag||warnings.length);
 if(reviewRequired&&!warnings.length){
  pushWarn('Có câu hoặc dòng ma trận được gắn cờ cần rà (thiếu điểm, chủ đề, mức hoặc lệch điểm).');
 }
 return {
  hasIssues:reviewRequired,
  reviewRequired,
  warnings,
  pointConflicts,
  flaggedOrdinals:[...new Set(flaggedOrdinals)].sort((a,b)=>a-b),
  conflictOrdinals:[...new Set(conflictOrdinals)].sort((a,b)=>a-b),
  slots,
  matrix,
 };
}

/** Khớp từng dòng ma trận với cờ `pointConflict` / `needsReview` từ báo cáo reverse_matrix hoặc ngay trên dòng. */
export function rowFlagForReverseReport(report,row){
 if(!row)return null;
 const directConflict=Boolean(row.pointConflict||(Array.isArray(row.pointConflicts)&&row.pointConflicts.length));
 const directReview=Boolean(row.needsReview||(Array.isArray(row.warnings)&&row.warnings.length));
 const summary=summarizeReverseMatrixReport(report);
 const topic=normMatrixKey(row.topic),type=row.type||'mcq',grp=normMatrixKey(row.choiceGroup);
 const matchTarget=(itemTopic,itemType,itemGroup)=>{
  const t=normMatrixKey(itemTopic);
  if((itemType||'mcq')!==type||normMatrixKey(itemGroup)!==grp)return false;
  return topic===t||topic.startsWith(t+' (');
 };
 const matchedConflict=summary.pointConflicts?.some(c=>matchTarget(c.topic,c.type,c.choiceGroup))||summary.slots?.some(s=>s.pointConflict&&matchTarget(s.topic,s.type,s.choiceGroup));
 const matchedReview=summary.slots?.some(s=>s.needsReview&&matchTarget(s.topic,s.type,s.choiceGroup));
 const pointConflict=directConflict||Boolean(matchedConflict);
 const needsReview=pointConflict||directReview||Boolean(matchedReview);
 if(!needsReview)return null;
 return {pointConflict,needsReview,label:pointConflict?'Lệch điểm':'Cần rà'};
}

/** Dựng HTML banner cảnh báo P2 reverse_matrix ngay trong modal/khung Ma trận. */
export function reverseMatrixWarningBannerHTML(report){
 const summary=summarizeReverseMatrixReport(report);
 if(!summary.hasIssues)return '';
 const conflictItems=summary.pointConflicts.map(c=>{
  const pts=(c.distinctPoints||[]).map(formatReversePts).join(', ');
  const grp=c.choiceGroup?` · nhánh ${esc(c.choiceGroup)}`:'';
  const mode=c.action==='requires_manual_decision'?'Vượt giới hạn dòng — cần chốt tay':'Đã tách dòng theo từng mức điểm';
  return `<li><b>${esc(c.topic||'Chủ đề')}</b> (${esc(QUESTION_TYPES[c.type||'mcq']||c.type||'mcq')}${grp}): ${esc(pts)} — ${esc(mode)}</li>`;
 }).join('');
 const ordBadge=summary.flaggedOrdinals.length
  ?`<p class="matrix-reverse-ordinals"><b>Câu cần rà:</b> ${summary.flaggedOrdinals.map(n=>`<span class="pill warn">Câu ${n}${summary.conflictOrdinals.includes(n)?' · lệch điểm':''}</span>`).join(' ')}</p>`
  :'';
 const warnList=summary.warnings.map(w=>`<li>${esc(w)}</li>`).join('');
 return `<div id="matrix-reverse-warnings" class="alert matrix-reverse-alert" role="alert" data-reverse-warnings="true"><b>⚠ Ma trận lập ngược cần giáo viên kiểm lại trước khi xác nhận</b><ul>${warnList}${conflictItems}</ul>${ordBadge}</div>`;
}
