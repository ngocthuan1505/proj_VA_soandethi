import {examRequestDefaults} from './subject-profiles.js';
import {esc, LEVELS, QUESTION_TYPES, validateMatrixRows} from './core.js';
import {richTextHTML} from './math-content.js';
import {
 openMatrixSynthesis,
 isAutoPilotEnabled,
 setAutoPilotEnabled,
 parseAutoCreateSse,
 renderAutoCreateCardHTML,
 streamAutoCreateExam,
 runAutoCreateExam as runAutoCreateExamCore,
} from './matrix-synthesis.js';
import {flushEditor} from './editor.js';
import {workspaceHeaders} from './storage.js';
import {summarizeReverseMatrixReport, rowFlagForReverseReport, reverseMatrixWarningBannerHTML} from './reference.js';
export {
 summarizeReverseMatrixReport,
 rowFlagForReverseReport,
 reverseMatrixWarningBannerHTML,
 isAutoPilotEnabled,
 setAutoPilotEnabled,
 parseAutoCreateSse,
 renderAutoCreateCardHTML,
 streamAutoCreateExam,
};

const flows=new Map(),restoring=new Set(),reverseReports=new Map();
let latestChatContext=null,autoCreateListenerBound=false;
export const matrixChatRunning=c=>flows.get(c.exam().id)?.phase==='running';
export const isMatrixRequest=text=>!/^(?:giải thích|hướng dẫn|tại sao|cách)\b/iu.test(text)&&/(?:soạn|tạo|sinh|gen|làm)\b/iu.test(text.normalize('NFC'))&&/ma\s*trận/iu.test(text);

export async function runAutoCreateExam(ctx,promptText,opts={}){
 flushEditor();
 if(typeof document!=='undefined')document.querySelector('#dialog')?.close?.();
 return runAutoCreateExamCore(ctx,promptText,{
  ...opts,
  onOpenManualMatrix:opts.onOpenManualMatrix||((targetCtx,req)=>openMatrixChat(targetCtx,{request:req,manual:true})),
 });
}

export function setReverseMatrixReport(examId,revision,report){
 if(!examId)return;
 if(!report)reverseReports.delete(examId);
 else reverseReports.set(examId,{revision,report});
}

export function getReverseMatrixReport(examId,revision){
 const entry=reverseReports.get(examId);
 if(!entry)return null;
 if(revision!=null&&entry.revision!==revision)return null;
 return entry.report;
}

export function clearReverseMatrixReport(examId){
 if(examId)reverseReports.delete(examId);
}

/** Gọi backend lập ma trận ngược và lưu báo cáo cảnh báo theo phiên bản đề. */
export async function requestReverseMatrix(exam){
 if(!exam?.id)throw Error('Chưa có đề đang mở để lập ma trận.');
 const resp=await fetch(`/api/exams/${encodeURIComponent(exam.id)}/reverse-matrix`,{
  method:'POST',
  headers:{'Content-Type':'application/json',...workspaceHeaders()},
  body:JSON.stringify({exam,baseRevision:exam.revision}),
 });
 const res=await resp.json();
 if(!resp.ok)throw Error(res.error||res.detail?.message||'Chưa lập được ma trận ngược.');
 setReverseMatrixReport(exam.id,exam.revision,res);
 return res;
}

export function matrixRowsFromForm(form){
 const ptFields=val=>{
  if(val==='')return {};
  const n=Number(val);
  return Number.isInteger(Math.round(n*100)/25)?{pointsQ4:Math.round(n*4)}:{points:Math.round(n*100)/100};
 };
 const rows=[...form.querySelectorAll('[data-chat-matrix-row]')].map(row=>{
  const lvlInputs=[...row.querySelectorAll('[name=level-points]')];
  const grp=row.querySelector('[name=choiceGroup]')?.value?.trim();
  const lvlVals=lvlInputs.map(n=>n.value===''?null:Number(n.value));
  const useDecLvl=lvlInputs.length&&lvlVals.some(v=>v!=null&&!Number.isInteger(Math.round(v*100)/25));
  return {
   topic:row.querySelector('[name=topic]').value.trim(),
   type:row.querySelector('[name=type]')?.value||'mcq',
   ...(grp?{choiceGroup:grp}:{}),
   ...(!lvlInputs.length?ptFields(row.querySelector('[name=points]')?.value||''):{}),
   targets:[...row.querySelectorAll('[name=target]')].map(n=>Number(n.value)),
   ...(lvlInputs.length?(useDecLvl?{pointsByLevel:lvlVals.map(v=>v==null?null:Math.round(v*100)/100)}:{pointsByLevelQ4:lvlVals.map(v=>v==null?null:Math.round(v*4))}):{}),
  };
 });
 validateMatrixRows(rows);
 const picker=form.querySelector('[name=matrix-choice-group]');
 if(!picker)return rows;
 if(!picker.value)throw Error('Chọn một nhánh tự chọn để sinh.');
 const selected=rows.filter(row=>!row.choiceGroup||row.choiceGroup.toLocaleLowerCase()===picker.value);
 validateMatrixRows(selected);
 return selected;
}

function clearPreview(flow){
 flow.paper?.parentElement?.classList.remove('matrix-preview-active');
 const node=flow.paper?.querySelector('#matrix-preview');
 if(node){flow.root.append(node);node.innerHTML='';}
 flow.paper?.remove();flow.paper=null;
}

function presentPreview(c,flow,node){
 const exam=c.getState().exams.find(e=>e.id===flow.examId);
 if(!flow.paper){
  const paper=document.createElement('article');paper.className='matrix-document-preview';
  paper.setAttribute('aria-label','Đề xuất AI chưa lưu');
  paper.innerHTML=`<div class="matrix-preview-banner"><b>Đề xuất chưa lưu</b><span>Đọc bộ câu rồi chọn ✓ hoặc ✕ trong chat.</span></div><header><p>${esc(exam.school||'')}</p><h2>${esc(exam.title)}</h2><p>${esc(exam.subject)} · Lớp ${esc(exam.grade)}</p></header>`;
  flow.paper=paper;
 }
 flow.paper.append(node);
 node.querySelectorAll('[data-matrix-question]').forEach(section=>{section.style.cssText='';});
 mountMatrixChat(c);
 if(c.exam().id===flow.examId)document.querySelector('.paper-scroll')?.scrollTo({top:0});
}


function quickPlanForm(c,flow){
 const defaults=examRequestDefaults(flow.request||'',c.exam());
 flow.phase='plan';
 flow.root.innerHTML=`<h3>Để trợ lý đề xuất một đề phù hợp</h3><p>Trợ lý tự chọn số câu, dạng câu và thời gian theo môn/lớp. Thầy cô xem gợi ý trước khi sinh, có thể đổi nếu muốn.</p><form class="quick-exam-plan"><label>Yêu cầu<textarea name="request" maxlength="4000" required>${esc(flow.request||'Soạn đề có đáp án và barem')}</textarea></label><p class="quick-plan-context">${esc(defaults.subject)} · Lớp ${esc(defaults.grade)}${defaults.count?' · '+esc(defaults.count)+' câu/ý theo yêu cầu':''}${defaults.minutes?' · '+esc(defaults.minutes)+' phút':''}</p><details class="quick-plan-options"><summary>Tùy chỉnh yêu cầu (không bắt buộc)</summary><div class="quick-plan-fields"><label>Môn<input name="subject" required maxlength="100" value="${esc(defaults.subject)}"></label><label>Lớp<input name="grade" type="number" min="1" max="12" required value="${esc(defaults.grade)}"></label><label>Phạm vi / học kì<select name="term">${['cuối kì (chưa nêu học kì)','cuối học kì I','cuối học kì II','cả năm','ôn tập theo yêu cầu'].map(x=>`<option ${x===defaults.term?'selected':''}>${x}</option>`).join('')}</select></label><label>Số câu/ý<input name="count" type="number" min="1" max="30" placeholder="Trợ lý đề xuất" value="${defaults.count}"></label><label>Thời gian (phút)<input name="minutes" type="number" min="5" max="300" placeholder="Trợ lý đề xuất" value="${defaults.minutes}"></label><label>Dạng câu<select name="types">${[['','Trợ lý chọn phù hợp'],['mcq,essay','Trắc nghiệm và tự luận'],['essay','Chỉ tự luận'],['mcq','Chỉ nhiều lựa chọn'],['truefalse','Chỉ đúng–sai'],['short','Chỉ trả lời ngắn']].map(([v,label])=>`<option value="${v}" ${v===defaults.types?'selected':''}>${label}</option>`).join('')}</select></label></div><p class="hint">Để trống số câu/thời gian nếu chưa biết. Ghi thêm bộ sách, chủ đề hoặc yêu cầu của trường nếu có.</p></details><label><input name="consent" type="checkbox" required> Cho phép gửi yêu cầu này tới AI đã kết nối.</label><p role="alert"></p><button class="primary" type="submit">Đề xuất đề phù hợp</button><button type="button" data-use-file>Tôi có file ma trận</button><details><summary>Tự lập cơ cấu (tùy chọn)</summary><button type="button" data-manual>Lập / sửa ma trận thủ công</button></details></form>`;
 const form=flow.root.querySelector('form');
 form.querySelector('[data-use-file]').onclick=()=>{flow.forceFile=true;matrixForm(c,flow);flow.root.querySelector('.matrix-file-import').open=true;};
 form.querySelector('[data-manual]').onclick=()=>matrixForm(c,flow);
 form.onsubmit=async event=>{event.preventDefault();event.stopPropagation();const button=form.querySelector('[type=submit]');if(button.disabled)return;button.disabled=true;const error=form.querySelector('[role=alert]');error.textContent='Đang đề xuất số câu, dạng câu và thời gian phù hợp…';try{
  const data=Object.fromEntries(new FormData(form));data.grade=Number(data.grade);for(const key of ['count','minutes'])data[key]=data[key]?Number(data[key]):null;data.types=data.types?data.types.split(','):null;data.consent=form.elements.consent.checked;
  const response=await fetch('/api/ai/exam-plan',{method:'POST',headers:{'Content-Type':'application/json',...workspaceHeaders()},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error||'Chưa đề xuất được cơ cấu.');
  if(c.exam().id!==flow.examId||!form.isConnected)throw Error('Đã chuyển đề hoặc đóng yêu cầu.');
  flow.request=data.request;flow.rows=result.matrix;flow.metadata=result.metadata;flow.notes=result.notes;flow.autoPreview=true;matrixForm(c,flow);
 }catch(e){error.textContent=e.message;}finally{button.disabled=false;}};
}

export function buildMatrixPlanOverviewHTML({rows,notes='',reverseReport=null}){
 const safeRows=Array.isArray(rows)?rows:[];
 const formatPreviewPt=v=>{
  const n=Number(v);
  if(!Number.isFinite(n)||n<=0)return '';
  return n.toFixed(2).replace('.',',')+'đ';
 };
 const stripTopicPointTag=t=>String(t??'').replace(/\s*\(\s*\d+(?:[.,]\d+)?\s*đ(?:\s*·\s*#\d+)?\s*\)\s*$/iu,'').trim();
 const sumTargets=r=>(r.targets||[]).reduce((a,b)=>a+(Number(b)||0),0);
 const commonQ=safeRows.filter(r=>!(r.choiceGroup||'').trim()).reduce((n,r)=>n+sumTargets(r),0);
 const trackGroups=[...new Set(safeRows.map(r=>(r.choiceGroup||'').trim()).filter(Boolean))];
 const trackMaxQ=trackGroups.length?Math.max(...trackGroups.map(g=>safeRows.filter(r=>(r.choiceGroup||'').trim()===g).reduce((n,r)=>n+sumTargets(r),0))):0;
 const effCount=commonQ+trackMaxQ;
 return `<h4>Cơ cấu đề xuất · ${effCount} câu/ý · 10 điểm</h4><p>${esc(notes||'Xem lại chủ đề, mức và điểm trước khi dùng.')}</p><div class="matrix-overview-scroll"><table><thead><tr><th>Chủ đề / dạng câu</th>${LEVELS.map((x,i)=>`<th title="${x}" aria-label="${x}">${['NB','TH','VD','VDC'][i]}</th>`).join('')}</tr></thead><tbody>${safeRows.map(r=>{
  const flag=rowFlagForReverseReport(reverseReport,r);
  const flagTag=flag?` <span class="pill warn matrix-row-flag" data-row-flag="${flag.pointConflict?'pointConflict':'needsReview'}">${esc(flag.label)}</span>`:'';
  const cellPts=LEVELS.map((_,i)=>{
   const pts=r.pointsByLevelQ4?r.pointsByLevelQ4[i]/4:r.pointsByLevel?r.pointsByLevel[i]:r.pointsQ4!=null?r.pointsQ4/4:r.points;
   return (r.targets?.[i])&&pts?pts:null;
  });
  const hasCellPts=cellPts.some(Boolean);
  const displayTopic=hasCellPts?(stripTopicPointTag(r.topic)||r.topic):r.topic;
  return `<tr><td>${esc(displayTopic)}${r.choiceGroup?` <small>[${esc(r.choiceGroup)}]</small>`:''}${flagTag}<small style="display:block">${esc(QUESTION_TYPES[r.type||'mcq'])}</small></td>${LEVELS.map((_,i)=>{
   const ptText=cellPts[i]!=null?formatPreviewPt(cellPts[i]):'';
   return `<td>${r.targets?.[i]||0}${ptText?`<small style="display:block">${esc(ptText)}</small>`:''}</td>`;
  }).join('')}</tr>`;
 }).join('')}</tbody></table></div><p class="hint">NB: Nhận biết · TH: Thông hiểu · VD: Vận dụng · VDC: Vận dụng cao. Điểm ghi dưới số câu là điểm mỗi câu.</p>`;
}

function matrixForm(c,flow){
 flow.controller=null;flow.phase='plan';flow.dock?.remove();flow.dock=null;
 const exam=c.getState().exams.find(e=>e.id===flow.examId);
 const rows=flow.rows||(exam.matrix?.length?exam.matrix:[{topic:'',targets:[2,1,1,0]}]);
 const reverseReport=flow.reverseReport||getReverseMatrixReport(flow.examId,exam?.revision);
 const reverseBannerHTML=reverseMatrixWarningBannerHTML(reverseReport);
 const groups=new Map(rows.filter(row=>row.choiceGroup?.trim()).map(row=>{const name=row.choiceGroup.trim();return [name.toLocaleLowerCase(),name];}));
 const choiceHTML=groups.size>1?`<label>Nhánh tự chọn để sinh<select name="matrix-choice-group" required><option value="">Chọn nhánh</option>${[...groups].map(([key,name])=>`<option value="${esc(key)}">${esc(name)}</option>`).join('')}</select></label>`:'';
 const rowHTML=row=>{
  const ptVal=row.pointsQ4!=null?row.pointsQ4/4:(row.points??'');
  const lvlPts=row.pointsByLevelQ4||row.pointsByLevel;
  const lvlScale=row.pointsByLevelQ4?4:1;
  const flag=rowFlagForReverseReport(reverseReport,row);
  const flagBadge=flag?` <span class="pill warn matrix-row-flag" data-row-flag="${flag.pointConflict?'pointConflict':'needsReview'}">${esc(flag.label)}</span>`:'';
  return `<fieldset data-chat-matrix-row><label>Chủ đề${row.choiceGroup?` <span class="pill">${esc(row.choiceGroup)}</span><input type="hidden" name="choiceGroup" value="${esc(row.choiceGroup)}">`:''}${flagBadge}<input name="topic" maxlength="160" required value="${esc(row.topic)}"></label><label>Loại câu<select name="type">${Object.entries(QUESTION_TYPES).map(([key,label])=>`<option value="${key}" ${(row.type||'mcq')===key?'selected':''}>${label}</option>`).join('')}</select></label><label>Điểm mỗi câu<input name="points" type="number" min="0.05" max="10" step="0.01" placeholder="Tự chia phần điểm còn lại" value="${ptVal}" ${lvlPts?'disabled':''}></label><div class="matrix-chat-counts">${LEVELS.map((level,i)=>`<label>${level}<input name="target" type="number" min="0" max="30" required value="${row.targets[i]||0}">${lvlPts?`<span>Điểm/câu</span><input name="level-points" aria-label="Điểm mỗi câu ${level}" type="number" min="0.05" max="10" step="0.01" value="${lvlPts[i]==null?'':lvlPts[i]/lvlScale}">`:''}</label>`).join('')}</div><button type="button" data-remove-row aria-label="Bỏ chủ đề này">Bỏ chủ đề</button></fieldset>`;
 };
 flow.root.innerHTML=`<h3>${flow.autoPreview?'Xem lại cơ cấu đề':'Soạn theo ma trận'}</h3><p>${flow.autoPreview?'Kiểm tra bản tóm tắt rồi xác nhận. Chỉ mở phần chỉnh chi tiết khi cần đổi.':'Tải file, lập ngược từ đề đang mở hoặc tự điền cơ cấu bên dưới. Chưa sinh câu hỏi.'}</p><div class="matrix-reverse-bar"><button type="button" data-reverse-matrix ${exam.questions?.length?'':'disabled'}>Lập ma trận ngược từ đề đang mở</button><p class="hint" data-reverse-status role="status"></p></div>${reverseBannerHTML}<form class="matrix-chat-plan">${choiceHTML}<div data-rows>${rows.map(rowHTML).join('')}</div><button type="button" data-add-row>＋ Thêm chủ đề</button><p class="matrix-chat-error" role="alert"></p><div class="matrix-chat-actions"><button type="submit" class="primary">${flow.autoPreview&&!flow.fromFile?'Dùng gợi ý này':'Dùng ma trận này'}</button><button type="button" data-close-plan>Để sau</button></div></form>`;
 const form=flow.root.querySelector('form');
 const revBtn=flow.root.querySelector('[data-reverse-matrix]'),revStatus=flow.root.querySelector('[data-reverse-status]');
 revBtn.onclick=async()=>{
  if(!flushEditor())return;
  revBtn.disabled=true;revStatus.textContent='Đang đọc cấu trúc câu hỏi tại máy…';
  try{
   const currentExam=c.getState().exams.find(e=>e.id===flow.examId);
   const res=await requestReverseMatrix(currentExam);
   if(c.exam().id!==flow.examId||!form.isConnected)return;
   flow.rows=res.matrix;flow.reverseReport=res;
   flow.notes=(res.warnings?.join(' · ')||'Đã lập ma trận ngược tại máy từ đề đang mở.');flow.fromFile=false;flow.autoPreview=true;matrixForm(c,flow);
   const st=flow.root.querySelector('[data-reverse-status]');
   if(st)st.textContent=`Đã đọc ${res.totalQuestions} câu (${res.countedQuestions} câu hiệu lực · ${res.totalPoints.toFixed(2).replace('.',',')} điểm).`+(res.warnings?.length?' Có mục cần rà lại ở cảnh báo bên dưới.':'');
   flow.root.querySelector('#matrix-reverse-warnings')?.scrollIntoView?.({block:'nearest'});
  }catch(err){revStatus.textContent=err.message;}finally{if(revBtn.isConnected)revBtn.disabled=false;}
 };
 if(flow.autoPreview){
  const summary=document.createElement('div');summary.className='matrix-plan-overview';summary.innerHTML=buildMatrixPlanOverviewHTML({rows,notes:flow.notes,reverseReport});
  const mix=document.createElement('p');mix.className='matrix-plan-types';mix.textContent=Object.entries(QUESTION_TYPES).map(([key,label])=>{const n=rows.filter(r=>(r.type||'mcq')===key).reduce((sum,r)=>sum+r.targets.reduce((a,b)=>a+b,0),0);return n?n+' '+label.toLocaleLowerCase():'';}).filter(Boolean).join(' · ');summary.querySelector('h4').after(mix);if(!flow.fromFile){const detail=document.createElement('details');detail.className='matrix-auto-distribution';detail.innerHTML='<summary>Xem phân bố chủ đề và mức độ</summary>';detail.append(summary.querySelector('.matrix-overview-scroll'),summary.querySelector('.hint'));summary.append(detail);}form.prepend(summary);const advanced=document.createElement('details');advanced.className='matrix-plan-advanced';advanced.innerHTML='<summary>Chỉnh từng chủ đề, số câu và điểm</summary>';advanced.append(form.querySelector('[data-rows]'),form.querySelector('[data-add-row]'));summary.after(advanced);
 }
 if(flow.metadata){const meta=flow.metadata;const info=document.createElement('p');info.className='matrix-plan-metadata';info.textContent=[meta.title,meta.subject,meta.grade?'Nội dung lớp '+meta.grade:'',meta.minutes?meta.minutes+' phút':''].filter(Boolean).join(' · ');form.prepend(info);
  if(flow.fromFile){const choice=document.createElement('label');choice.innerHTML=`Thông tin từ file có thể khác đề đang mở<select name="file-metadata" required><option value="">Chọn cách dùng thông tin môn/lớp/thời gian</option><option value="file">Dùng thông tin từ file trên</option><option value="current">Giữ thông tin đề đang mở (${esc(exam.subject)} lớp ${esc(exam.grade)})</option></select>`;info.after(choice);}
 }
 if(flow.fileURL){const original=document.createElement('a');original.href=flow.fileURL;original.target='_blank';original.rel='noopener';original.textContent='Mở file gốc để đối chiếu';form.prepend(original);}
 const filePanel=document.createElement('details');filePanel.className='matrix-file-import';
 filePanel.innerHTML='<summary>Tải file ma trận · Word, Excel, PDF hoặc ảnh</summary><p>Chọn tệp để đọc cơ cấu. Xem lại bảng bên dưới rồi bấm Dùng ma trận này. Ngữ liệu ra câu chọn ở bước tiếp theo.</p><label>File ma trận<input type="file" accept=".docx,.xlsx,.csv,.tsv,.txt,.md,.pdf,.png,.jpg,.jpeg,.webp" data-matrix-file></label><label><input type="checkbox" data-matrix-file-consent> Cho phép gửi tệp này tới Gemini để đọc nếu cần (PDF/ảnh/bảng phức tạp).</label><button type="button" data-read-matrix-file>Đọc file ma trận</button><p data-matrix-file-status role="status"></p>';
 form.before(filePanel);
 const readButton=filePanel.querySelector('[data-read-matrix-file]'),fileStatus=filePanel.querySelector('[data-matrix-file-status]');
 filePanel.after(fileStatus);fileStatus.className='hint';
 filePanel.querySelector('[data-matrix-file-consent]').style.cssText='width:auto;flex:0 0 auto;margin:4px 0 0';
 readButton.onclick=async()=>{
  const file=filePanel.querySelector('[data-matrix-file]').files[0];
  if(!file){fileStatus.textContent='Chọn file ma trận trước.';return;}
  if(file.size>15*1024*1024){fileStatus.textContent='Tệp tối đa 15 MB.';return;}
  readButton.disabled=true;fileStatus.textContent='Đang đọc file ma trận…';
  try{
   const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
   const response=await fetch('/api/ai/matrix',{method:'POST',headers:{'Content-Type':'application/json',...workspaceHeaders()},body:JSON.stringify({name:file.name,data,consent:filePanel.querySelector('[data-matrix-file-consent]').checked})});
   const result=await response.json();if(!response.ok)throw Error(result.error||result.detail?.message||'Chưa đọc được ma trận.');
   if(c.exam().id!==flow.examId||!form.isConnected)throw Error('Đã chuyển đề hoặc đóng bảng. Chọn lại tệp ở đúng đề.');
   if(flow.fileURL)URL.revokeObjectURL(flow.fileURL);flow.fileURL=URL.createObjectURL(file);flow.rows=result.matrix;flow.reverseReport=null;clearReverseMatrixReport(flow.examId);flow.metadata=result.metadata;flow.notes=result.notes;flow.fromFile=true;flow.autoPreview=true;matrixForm(c,flow);const currentStatus=flow.root.querySelector('[data-matrix-file-status]');currentStatus.textContent=`Đã đọc ${result.count} câu/ý · ${result.sentToAI?'có gửi AI':'xử lý tại máy'}. Xem bảng, chọn thông tin đề và xác nhận trước khi sinh.`;return;
  }catch(error){fileStatus.textContent=error.message;}
  finally{readButton.disabled=false;}
 };
 form.querySelector('[data-add-row]').onclick=()=>form.querySelector('[data-rows]').insertAdjacentHTML('beforeend',rowHTML({topic:'',targets:[0,0,0]}));
 form.onclick=event=>{if(event.target.closest('[data-remove-row]'))event.target.closest('fieldset').remove();};
 form.querySelector('[data-close-plan]').onclick=()=>finish(c,flow,'dismissed');
 form.onsubmit=async event=>{
  event.preventDefault();event.stopPropagation();
  const submit=form.querySelector('[type=submit]');if(submit.disabled)return;submit.disabled=true;
  try{
   if(c.exam().id!==flow.examId)throw Error('Đã chuyển đề. Mở lại tác vụ ở đúng đề cần soạn.');
   const rows=matrixRowsFromForm(form);
   clearReverseMatrixReport(flow.examId);flow.reverseReport=null;
   c.change('Xác nhận ma trận trong chat',exam=>{exam.matrix=rows;exam.matrixConfirmed=true;if(flow.metadata&&(!flow.fromFile||form.elements['file-metadata']?.value==='file'))Object.assign(exam,flow.metadata);if(flow.request)exam.generationRequest=flow.request;},{renderPage:false});
   await c.persist();c.render();await startSession(c,flow);
  }catch(error){form.querySelector('[role=alert]').textContent=error.message;}
  finally{if(form.isConnected)submit.disabled=false;}
 };
}

async function finish(c,flow,kind){
 clearPreview(flow);if(flow.fileURL)URL.revokeObjectURL(flow.fileURL);flow.dock?.remove();flow.root.remove();flows.delete(flow.examId);placeChatControls(c,null);
 const exam=c.getState().exams.find(e=>e.id===flow.examId);
 if(c.getState().matrixChatExamId===flow.examId)c.getState().matrixChatExamId=null;
 if(exam){exam.chat.push({role:'assistant',text:kind==='saved'?'Đã chấp nhận và lưu bộ câu. Có thể Hoàn tác để về bản trước.':'Đã bỏ đề xuất. Các câu trong đề được giữ nguyên.'});}
 await c.persist();c.render();
}

async function startSession(c,flow){
 flow.controller=await openMatrixSynthesis(c,{
  host:flow.root,
  examId:flow.examId,
  phase:state=>{Object.assign(flow,state,{dock:state.decisions||flow.dock});if(c.exam().id===flow.examId)placeChatControls(c,flow);},
  preview:node=>presentPreview(c,flow,node),
  clearPreview:()=>clearPreview(flow),
  find:id=>flow.paper?.querySelector('#'+id)||flow.dock?.querySelector('#'+id),
  editMatrix:()=>matrixForm(c,flow),
  viewPreview:()=>{if(innerWidth<=760){document.querySelector('.workspace')?.classList.remove('mobile-ai-view');document.querySelector('.assistant')?.classList.remove('open');document.querySelector('[data-ux-action="mobile-show-editor"]')?.classList.add('active');document.querySelector('.ux-view-tabs [data-action="toggle-ai"]')?.classList.remove('active');}document.querySelector('.paper-scroll')?.scrollTo({top:0});},
  finish:kind=>finish(c,flow,kind),
 });
}

export async function openMatrixChat(c,options={}){
 flushEditor();
 document.querySelector('#dialog')?.close();
 const exam=c.exam();
 document.querySelector('.workspace')?.classList.remove('chat-hidden');
 document.querySelector('.assistant')?.classList.add('open');
 if(innerWidth<=760){document.querySelector('.workspace')?.classList.add('mobile-ai-view');document.querySelector('[data-ux-action="mobile-show-editor"]')?.classList.remove('active');document.querySelector('.ux-view-tabs [data-action="toggle-ai"]')?.classList.add('active');}
 if(flows.has(exam.id)){mountMatrixChat(c);flows.get(exam.id).root.scrollIntoView({block:'nearest'});return;}
 const root=document.createElement('section');root.className='matrix-chat-session';root.setAttribute('aria-label','Soạn theo ma trận');
 const flow={examId:exam.id,root,paper:null,controller:null,request:options.request||''};flows.set(exam.id,flow);
 c.getState().matrixChatExamId=exam.id;
 try{await c.persist();}
 catch(error){flows.delete(exam.id);root.remove();if(c.getState().matrixChatExamId===exam.id)c.getState().matrixChatExamId=null;throw error;}
 if(c.exam().id!==exam.id){flows.delete(exam.id);root.remove();if(c.getState().matrixChatExamId===exam.id)c.getState().matrixChatExamId=null;return;}
 mountMatrixChat(c);
 const count=(exam.matrix||[]).flatMap(row=>row.targets).reduce((n,x)=>n+x,0);
 try{if(options.manual)matrixForm(c,flow);else if(options.request&&!/ma\s*trận/iu.test(options.request))quickPlanForm(c,flow);else if(!exam.matrixConfirmed||count<1||count>30)matrixForm(c,flow);else await startSession(c,flow);}
 catch(error){root.innerHTML=`<h3>Chưa mở được tác vụ</h3><p role="alert">${esc(error.message)}</p><button type="button">Đóng</button>`;root.querySelector('button').onclick=()=>finish(c,flow,'dismissed');}
 root.scrollIntoView({block:'nearest'});
}

export function mountMatrixChat(c){
 latestChatContext=c;
 if(!autoCreateListenerBound&&typeof globalThis.window?.addEventListener==='function'){
  autoCreateListenerBound=true;
  globalThis.window.addEventListener('mach:auto-create-exam',event=>{
   const detail=event?.detail||{};
   if(!latestChatContext||!detail.prompt)return;
   if(detail.examId&&latestChatContext.getState?.()?.exams?.some(e=>e.id===detail.examId)){
    latestChatContext.getState().current=detail.examId;
   }
   void runAutoCreateExam(latestChatContext,detail.prompt,{
    examId:detail.examId,
    campaignId:detail.campaignId,
    subject:detail.subject,
    grade:detail.grade,
    durationMinutes:detail.durationMinutes,
    consentGiven:detail.consentGiven,
    saveWorkspaceConsent:detail.saveWorkspaceConsent,
    onOpenManualMatrix:(ctx,p)=>openMatrixChat(ctx,{request:p,manual:true}),
   });
  });
 }
 const flow=flows.get(c.exam().id),body=document.querySelector('.assistant-body'),scroll=document.querySelector('.paper-scroll');
 if(flow){
  if(body&&!body.contains(flow.root))body.append(flow.root);
  if(flow.paper&&scroll){scroll.classList.add('matrix-preview-active');if(!scroll.contains(flow.paper))scroll.append(flow.paper);}
  flow.controller?.refresh();
 }else if(c.getState().matrixChatExamId===c.exam().id&&!restoring.has(c.exam().id)){
  const examId=c.exam().id;restoring.add(examId);queueMicrotask(async()=>{try{if(c.exam().id===examId)await openMatrixChat(c);}catch(error){c.toast(error.message);}finally{restoring.delete(examId);}});
 }
 placeChatControls(c,flow);
}

function placeChatControls(c,flow){
 const assistant=document.querySelector('.assistant'),compose=assistant?.querySelector('.chat-compose');if(!compose)return;
 assistant.classList.toggle('is-matrix-wide',Boolean(flow));
 assistant.querySelectorAll('.matrix-decision-dock').forEach(node=>{if(node!==flow?.dock)node.remove();});
 if(flow?.dock){
  flow.dock.classList.add('matrix-decision-dock');flow.dock.hidden=flow.phase!=='review';
  if(flow.phase==='review')compose.before(flow.dock);else if(!flow.root.contains(flow.dock))flow.root.append(flow.dock);
 }
 const running=flow?.phase==='running',send=compose.querySelector('button[type=submit]');
 let stop=compose.querySelector('#matrix-composer-stop');
 if(running&&!stop){stop=document.createElement('button');stop.type='button';stop.id='matrix-composer-stop';stop.textContent='■';stop.setAttribute('aria-label','Dừng tác vụ');stop.title='Dừng tác vụ';send.after(stop);}
 if(stop){stop.hidden=!running;stop.disabled=!flow?.cancellable;stop.onclick=()=>flow?.stop?.();}
 if(send){if(running){send.hidden=true;send.dataset.matrixHeld='true';}else if(send.dataset.matrixHeld){send.hidden=false;delete send.dataset.matrixHeld;}}
 assistant.dataset.matrixRunning=String(running);
}
