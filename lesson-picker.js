import {esc,touch,check} from './core.js';
import {selectedDocumentPages} from './assistant-sources.js';
import {workspaceHeaders} from './storage.js';
import {mergeAssistantSourceDraft} from './reference.js';

const personalRoute='/api/lesson-catalog/sources';
const KNTT_SERIES='Kết nối tri thức với cuộc sống';
const usable=record=>['allowed','teacher_owned'].includes(record.license_status);
const normSubject=v=>String(v??'').normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().replace(/đ/g,'d').trim();
export function normalizeLessonSearch(value){
 return String(value??'').normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().replace(/đ/g,'d').replace(/[.,;:()[\]{}"'’“”?!\-–—/]+/g,' ').replace(/\s+/g,' ').trim();
}
function foldVietnameseOrthography(norm){
 return String(norm||'').replace(/\bquy/g,'qui').replace(/([bcdfghklmnpqrstvwxz])y(?![aeiou])/g,'$1i').replace(/\s+/g,' ').trim();
}
export function expandLessonSearchVariants(query){
 const base=normalizeLessonSearch(query);
 if(!base)return [];
 const out=new Set([base]);
 const folded=foldVietnameseOrthography(base);
 if(folded)out.add(folded);
 for(const item of [...out]){
  if(/\bphep the\b/.test(item)){
   out.add(item.replace(/\bphep the\b/g,'phuong phap the'));
  }
  if(/\bphuong phap the\b/.test(item))out.add(item.replace(/\bphuong phap the\b/g,'phep the'));
  if(/\bgiai he phuong trinh\b/.test(item))out.add('giai he');
  if(/\bti so\b/.test(item))out.add(item.replace(/\bti so\b/g,'ti le'));
  if(/\bti le\b/.test(item))out.add(item.replace(/\bti le\b/g,'ti so'));
 }
 return [...out].filter(Boolean);
}
export function lessonMatchesSearch(collection,lesson,query){
 const variants=expandLessonSearchVariants(query);
 if(!variants.length)return true;
 const rawHay=[
  collection?.name,collection?.subject,collection?.book,collection?.series,collection?.volume,
  lesson?.chapter,lesson?.title,lesson?.outcome,lesson?.text,lesson?.summary,lesson?.pageRange,
  ...(Array.isArray(lesson?.learningOutcomes)?lesson.learningOutcomes:[]),
 ].filter(Boolean).join(' ');
 const hay=foldVietnameseOrthography(normalizeLessonSearch(rawHay));
 if(!hay)return false;
 const hayWords=hay.split(' ');
 return variants.some(v=>{
  if(hay.includes(v))return true;
  const toks=v.split(' ').filter(Boolean);
  return toks.length>=2&&toks.every(t=>hayWords.includes(t)||(t.length>=4&&hayWords.some(w=>w.startsWith(t))));
 });
}
const isLiteratureSubject=v=>['ngu van','tieng viet'].includes(normSubject(v));
export function lessonSubjectMatches(selected,candidate){
 if(!selected)return true;
 if(selected===candidate)return true;
 return isLiteratureSubject(selected)&&isLiteratureSubject(candidate);
}
const asCollection=record=>({
 id:record.id,version:record.updated_at,grade:String(record.grade),subject:record.subject,
 book:record.series||'Học liệu cá nhân',series:record.series||'Học liệu cá nhân',
 volume:record.volume||'Chưa xếp tập',catalogKind:'personal',
 name:record.title,record,lessons:[{
  id:record.id+'-b1',number:1,chapter:record.chapter||'Chưa xếp chương',title:record.lesson||record.title,
  outcome:record.locator||'',text:record.content_excerpt||'',
  summary:record.content_excerpt||'',learningOutcomes:record.locator?[record.locator]:[],
 }],
});

function chapterPageLabel(rows){
 const starts=rows.map(r=>Number(r.pageStart)).filter(n=>Number.isFinite(n)&&n>0);
 const ends=rows.map(r=>Number(r.pageEnd)).filter(n=>Number.isFinite(n)&&n>0);
 if(!starts.length||!ends.length)return '';
 const minStart=Math.min(...starts), maxEnd=Math.max(...ends);
 return maxEnd>minStart?`tr. ${minStart}-${maxEnd}`:`tr. ${minStart}`;
}

export async function openLessonPicker(context) {
 const examId=context.exam().id;
 const baseDialog=document.querySelector('#dialog');
 const returnFocusEl=document.activeElement instanceof HTMLElement?document.activeElement:null;
 const origin=baseDialog?.open&&baseDialog.querySelector('#assistant-source-form');
 const useLayer2=Boolean(origin&&document.querySelector('#dialog-layer2'));
 const dialog=useLayer2?document.querySelector('#dialog-layer2'):baseDialog;
 const headers=workspaceHeaders();
 const [response,personal]=await Promise.all([
  fetch('/api/lesson-catalog',{headers}),
  fetch(personalRoute,{headers}).then(r=>r.ok?r.json():null).catch(()=>null),
 ]);
 if(!response.ok)throw Error('Chưa mở được học liệu theo bài.');
 const {collections}=await response.json();
 collections.push(...(personal?.sources||[]).map(asCollection));
 if(context.exam().id!==examId||(origin&&(!origin.isConnected||!baseDialog.open)))return;
 const exam=context.exam(), choices=new Map(), changed=new Set();
 const editedCopy=doc=>doc?.catalog===true&&doc.version>1&&doc.pages?.some(page=>page.method==='manual');
 const editedDocs=new Map(exam.docs.filter(editedCopy).map(doc=>[doc.id,doc]));
 for(const collection of collections){
  const saved=exam.docs.find(doc=>doc.id===collection.id);
  choices.set(collection.id,new Set(saved&&exam.assistantSources?.includes(saved.id)
   ?selectedDocumentPages(exam,saved).map(page=>page.number):[]));
  if(collection.record&&(!usable(collection.record)||!collection.record.content_excerpt.trim())){
   if(choices.get(collection.id).size)changed.add(collection.id);
   choices.get(collection.id).clear();
  }else if(saved&&!editedDocs.has(saved.id)&&exam.assistantSources?.includes(saved.id)&&(saved.version!==collection.version||Boolean(collection.record)&&saved.sourceLocator!==collection.record.locator)){
   const available=new Set(collection.lessons.map(lesson=>lesson.number));
   choices.set(collection.id,new Set([...choices.get(collection.id)].filter(number=>available.has(number))));
   changed.add(collection.id);
  }
 }
 const select=(label,name,values,selected)=>`<label>${label}<select name="${name}"><option value="">Tất cả</option>${values.map(value=>`<option ${value===selected?'selected':''}>${esc(value)}</option>`).join('')}</select></label>`;
 const grades=[...new Set(collections.map(c=>c.grade))].sort((a,b)=>Number(a)-Number(b));
 const subjects=[...new Set(collections.map(c=>c.subject))];
 const initialSubject=subjects.find(s=>lessonSubjectMatches(exam.subject,s))||'';
 context.modal('Kho học liệu & SGK theo bài',`
 <div class="sgk-modal">
  <div class="sgk-tabs" role="tablist" aria-label="Nguồn học liệu">
   <button type="button" role="tab" class="sgk-tab is-active" aria-selected="true" data-sgk-tab="library">Kho tài liệu</button>
   <button type="button" role="tab" class="sgk-tab" aria-selected="false" data-sgk-tab="sgk">Sách giáo khoa</button>
   <button type="button" role="tab" class="sgk-tab" aria-selected="false" data-sgk-tab="community">Đề cộng đồng</button>
   <button type="button" role="tab" class="sgk-tab" aria-selected="false" data-sgk-tab="my-exams">Đề của tôi</button>
   <button type="button" role="tab" class="sgk-tab" aria-selected="false" data-sgk-tab="my-matrices">Ma trận của tôi</button>
  </div>
  <div data-sgk-panel="catalog">
   ${personal?`<details data-personal-editor class="sgk-personal-box"><summary>Thêm học liệu cá nhân</summary>
   <form id="personal-lesson-form">
   <div class="grid2">
   <label>Lớp<input name="grade" type="number" min="1" max="12" required value="${esc(String(exam.grade??''))}"></label>
   <label>Môn<input name="subject" maxlength="200" required value="${esc(exam.subject)}"></label>
   <label>Bộ học liệu<input name="series" maxlength="200"></label>
   <label>Tập<input name="volume" maxlength="100"></label>
   <label>Chương<input name="chapter" maxlength="300"></label>
   <label>Bài<input name="lesson" maxlength="300"></label>
   </div>
   <label>Tên học liệu<input name="title" maxlength="400" required></label>
   <label>Vị trí trích dẫn<input name="locator" maxlength="300" placeholder="Ví dụ: Mục 2, trang 3"></label>
   <label>Đọc tệp tại máy<input type="file" data-lesson-file accept=".docx,.pdf,.txt,.md,.pptx"></label>
   <div data-lesson-preview hidden>
    <label>Trang hoặc slide<select data-lesson-page></select></label>
    <label>Văn bản đã đọc<textarea rows="5" readonly data-lesson-extract></textarea></label>
    <button type="button" data-lesson-use>Dùng phần đã đọc</button>
   </div>
   <label>Nội dung học liệu<textarea name="content_excerpt" rows="5" maxlength="12000" required></textarea></label>
   <label class="consent"><input type="checkbox" name="usage"> Tôi có quyền dùng nội dung này cho trợ lý</label>
   <p role="status" data-personal-status></p>
   <button type="submit" class="primary">Lưu học liệu</button>
   </form></details>`:'<p class="hint">Chưa tải được kho học liệu cá nhân.</p>'}
   <form id="lesson-picker">
    <div class="sgk-filters">
     <div class="sgk-filter-row">
      ${select('Lớp','grade',grades,String(exam.grade))}
      ${select('Môn','subject',subjects,initialSubject)}
      <label class="sgk-search-field">Tìm bài hoặc chương<input type="search" name="query" placeholder="Ví dụ: phép thế, mệnh đề, tập hợp…"></label>
     </div>
     <div class="sgk-filter-sub">
      <label>Kho<select name="library"><option value="">Tất cả</option><option value="sample">Học liệu mẫu</option><option value="personal">Kho cá nhân</option></select></label>
      ${select('Bộ học liệu','book',[])}
      ${select('Tập','volume',[])}
     </div>
     <div class="sgk-volume-bar">
      <div class="sgk-volume-pills" data-sgk-volume-pills></div>
      <span class="sgk-series-badge" data-sgk-series-badge>Bộ ${esc(KNTT_SERIES)}</span>
     </div>
    </div>
    <div class="sgk-split">
     <div class="sgk-tree-pane">
      <div data-lesson-list></div>
     </div>
     <aside class="sgk-detail-pane" data-sgk-detail aria-label="Chi tiết bài học"></aside>
    </div>
    <div class="sgk-footer">
     <div class="sgk-footer-summary">
      <p data-lesson-count role="status"></p>
      <div data-lesson-selected-chips class="lesson-selected-chips" hidden></div>
     </div>
     <div class="sgk-footer-actions">
      <button type="button" data-sgk-clear>Bỏ chọn bài</button>
      <button type="button" data-action="${useLayer2?'close-top-modal':'assistant-sources'}">Hủy</button>
      <button type="button" data-sgk-quick-compose>Soạn đề nhanh từ bài này</button>
      <button type="submit" class="primary">Dùng bài đã chọn</button>
     </div>
    </div>
   </form>
  </div>
  <div data-sgk-panel="community" class="sgk-aux-panel" hidden></div>
  <div data-sgk-panel="my-exams" class="sgk-aux-panel" hidden></div>
  <div data-sgk-panel="my-matrices" class="sgk-aux-panel" hidden></div>
 </div>`,'',{layer:useLayer2?2:1});

 const modalRoot=dialog.querySelector('.sgk-modal');
 const form=dialog.querySelector('#lesson-picker'),list=form.querySelector('[data-lesson-list]');
 const detailPane=form.querySelector('[data-sgk-detail]');
 const volumePillsHost=form.querySelector('[data-sgk-volume-pills]');
 const seriesBadge=form.querySelector('[data-sgk-series-badge]');
 const editor=dialog.querySelector('[data-personal-editor]'),personalForm=editor?.querySelector('form');
 let editing=null, importSequence=0, imported=null, sourceOrigin='';
 let activeTab='library';
 let activePreview=null; // {collectionId, lessonNumber}
 const collapsedChapters=new Set();
 const fileInput=personalForm?.querySelector('[data-lesson-file]');
 const preview=personalForm?.querySelector('[data-lesson-preview]');
 const pageSelect=preview?.querySelector('select'),previewText=preview?.querySelector('textarea');
 const importStatus=personalForm?.querySelector('[data-personal-status]');

 function editPersonal(record){
  importSequence++;
  imported=null;
  preview.hidden=true;
  sourceOrigin=record?.source_origin||'';
  editing=record;
  personalForm.reset();
  if(record){
   for(const field of ['grade','subject','series','volume','chapter','lesson','title','locator','content_excerpt']){
    personalForm.elements[field].value=record[field]??'';
   }
   personalForm.elements.usage.checked=usable(record);
  }
  editor.querySelector('summary').textContent=record?'Sửa học liệu cá nhân':'Thêm học liệu cá nhân';
  const linkedCount=record?context.exam().questions.filter(q=>q.source?.docId===record.id).length:0;
  personalForm.querySelector('[data-personal-status]').textContent=linkedCount?`Cảnh báo: có ${linkedCount} câu trong đề đang dùng học liệu này; sửa hoặc bỏ quyền dùng sẽ đánh dấu rà soát lại.`:'';
 }
 fileInput?.addEventListener('change',async()=>{
  const turn=++importSequence, file=fileInput.files[0];
  imported=null;
  preview.hidden=true;
  if(!file)return;
  const current=()=>turn===importSequence&&personalForm.isConnected&&dialog.open&&context.exam().id===examId;
  importStatus.textContent='Đang đọc tệp tại máy…';
  try{
   if(!/\.(docx|pdf|txt|md|pptx)$/i.test(file.name))throw Error('Chọn tệp Word, PDF, TXT, Markdown hoặc PowerPoint.');
   if(file.size>15*1024*1024)throw Error('Tệp lớn hơn 15 MB.');
   const data=await new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onload=()=>resolve(reader.result);
    reader.onerror=()=>reject(Error('Chưa đọc được tệp đã chọn.'));
    reader.readAsDataURL(file);
   });
   if(!current())return;
   const response=await fetch('/api/extract',{
    method:'POST',headers:{...headers,'Content-Type':'application/json'},
    body:JSON.stringify({name:file.name,data}),
   });
   const result=await response.json();
   if(!current())return;
   if(result.code==='document_ai_consent')throw Error('Tệp chưa có lớp chữ. Dùng bản có chữ hoặc dán đoạn đã đối chiếu.');
   if(!response.ok)throw Error(result.error||'Chưa đọc được nội dung tệp.');
   const pages=result.pages.filter(page=>page.text.trim());
   if(!pages.length)throw Error('Tệp chưa có nội dung chữ.');
   const unit=/\.pptx$/i.test(file.name)?'Slide':'Trang';
   imported={name:file.name,pages,unit};
   pageSelect.replaceChildren(...pages.map(page=>new Option(unit+' '+page.number,page.number)));
   previewText.value=pages[0].text;
   preview.hidden=false;
   importStatus.textContent='Chọn trang hoặc bôi đen đoạn cần đưa vào học liệu.';
  }catch(error){if(current())importStatus.textContent=error.message;}
 });
 pageSelect?.addEventListener('change',()=>{
  previewText.value=imported.pages.find(page=>page.number===Number(pageSelect.value)).text;
 });
 preview?.querySelector('[data-lesson-use]').addEventListener('click',()=>{
  const {selectionStart,selectionEnd,value}=previewText;
  const excerpt=(selectionStart<selectionEnd?value.slice(selectionStart,selectionEnd):value).trim();
  const fields=personalForm.elements;
  if(!excerpt){importStatus.textContent='Chọn phần nội dung có chữ.';return;}
  if(excerpt.length>fields.content_excerpt.maxLength){importStatus.textContent='Đoạn vượt 12.000 ký tự. Chọn phần ngắn hơn.';return;}
  fields.content_excerpt.value=excerpt;
  fields.locator.value=imported.unit+' '+pageSelect.value;
  if(!fields.title.value.trim())fields.title.value=imported.name.replace(/\.[^.]+$/,'').slice(0,400);
  sourceOrigin=imported.name.slice(0,500);
  fields.usage.checked=false;
  fields.content_excerpt.focus();
  importStatus.textContent='Đã chèn văn bản. Kiểm đoạn trích và xác nhận quyền trước khi lưu.';
 });
 personalForm?.addEventListener('submit',async event=>{
  event.preventDefault();
  event.stopPropagation();
  const button=personalForm.querySelector('[type=submit]');
  if(button.disabled)return;
  const status=personalForm.querySelector('[data-personal-status]');
  const {usage,...fields}=Object.fromEntries(new FormData(personalForm));
  const payload={...fields,source_origin:sourceOrigin,grade:Number(fields.grade),license_status:usage?(editing&&usable(editing)?editing.license_status:'allowed'):'pending_review'};
  if(!payload.content_excerpt.trim()){status.textContent='Nhập nội dung trước khi lưu.';return;}
  button.disabled=true;
  try{
   const result=await fetch(editing?personalRoute+'/'+encodeURIComponent(editing.id):personalRoute,{
    method:editing?'PATCH':'POST',
    headers:{...headers,'Content-Type':'application/json',...(editing?{'If-Match':String(editing.updated_at)}:{})},
    body:JSON.stringify(payload),
   });
   if(result.status===409)throw Error('Học liệu đã đổi. Mở lại kho trước khi lưu.');
   if(!result.ok)throw Error('Chưa lưu được học liệu. Kiểm tra các trường hoặc thử lại.');
   const record=await result.json();
   if(context.exam().id!==examId||!form.isConnected||!dialog.open)return;
   const collection=asCollection(record),index=collections.findIndex(item=>item.id===record.id);
   if(index<0)collections.push(collection);
   else collections[index]=collection;
   const previous=choices.get(record.id)?.size>0;
   choices.set(record.id,new Set(previous&&usable(record)?[1]:[]));
   if(previous)changed.add(record.id);
   const linkedDoc=context.exam().docs.find(d=>d.id===record.id);
   const linkedQs=context.exam().questions.filter(q=>q.source?.docId===record.id);
   if(linkedDoc||linkedQs.length){
    context.change('Cập nhật học liệu cá nhân liên kết',cur=>{
     const d=cur.docs.find(item=>item.id===record.id);
     if(d){
      Object.assign(d,{name:record.title,version:record.updated_at,pages:[{number:1,text:record.content_excerpt,title:record.lesson||record.title}],text:record.content_excerpt,sourceLocator:record.locator,licenseStatus:record.license_status});
      if(!usable(record)||!record.content_excerpt.trim()){
       cur.assistantSources=(cur.assistantSources||[]).filter(id=>id!==record.id);
       if(cur.assistantSourcePages)delete cur.assistantSourcePages[record.id];
      }
     }
     for(const q of cur.questions.filter(item=>item.source?.docId===record.id)){
      touch(q);check(cur,q);
     }
    },{renderPage:false});
   }
   form.elements.library.value='personal';
   form.elements.query.value='';
   updateFilter(form.elements.grade,[...new Set(collections.map(c=>c.grade))].sort((a,b)=>Number(a)-Number(b)),collection.grade);
   updateFilter(form.elements.subject,[...new Set(collections.map(c=>c.subject))],collection.subject);
   form.elements.book.value='';
   form.elements.volume.value='';
   editor.open=false;
   editPersonal(null);
   render();
   form.elements.library.focus();
   context.toast('Đã lưu học liệu cá nhân.');
  }catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
 });

 function renderDetailPane(){
  if(!detailPane)return;
  if(!activePreview){
   detailPane.innerHTML='<div class="sgk-detail-empty"><p class="hint">Chọn một bài học ở cột trái để xem tóm tắt, số trang, số tiết và yêu cầu cần đạt theo GDPT 2018.</p></div>';
   return;
  }
  const col=collections.find(c=>c.id===activePreview.collectionId);
  const lesson=col?.lessons.find(l=>l.number===activePreview.lessonNumber);
  if(!col||!lesson){
   detailPane.innerHTML='<div class="sgk-detail-empty"><p class="hint">Chưa chọn bài học.</p></div>';
   return;
  }
  const edited=editedDocs.get(col.id);
  const badgeText=col.record?'Tài liệu cá nhân':(col.catalogKind==='sgk'?'SGK':'Học liệu mẫu');
  const badgeKind=col.record?'personal':(col.catalogKind==='sgk'?'sgk':'sample');
  const metaParts=[
   col.subject,
   `Lớp ${col.grade}`,
   col.volume,
   lesson.pageRange||'',
   lesson.periods?`${lesson.periods} tiết`:'',
  ].filter(Boolean);
  const outcomes=Array.isArray(lesson.learningOutcomes)&&lesson.learningOutcomes.length
   ?lesson.learningOutcomes
   :(lesson.outcome?[lesson.outcome]:[]);
  const summaryText=lesson.summary||lesson.text||'';
  const rawText=edited?.pages?.find(page=>page.number===lesson.number)?.text??lesson.text??'';
  const detailsBlock=col.record
   ?`<details class="sgk-detail-raw"><summary>Chi tiết trích đoạn</summary><p><b>Mục tiêu</b> · ${esc(lesson.outcome||'Tài liệu cá nhân')}</p><p style="white-space:pre-wrap">${esc(rawText)}</p></details>`
   :`<details class="sgk-detail-raw"><summary>Xem học liệu</summary><p><b>Mục tiêu</b> · ${esc(lesson.outcome)}</p><p style="white-space:pre-wrap">${esc(rawText)}</p></details>`;
  const detailHeading=col.record
   ?`Học liệu · ${lesson.title}`
   :`Bài ${lesson.number} · ${lesson.title}`;
  detailPane.innerHTML=`
   <div class="sgk-detail-card">
    <div class="sgk-detail-head">
     <span class="pill source-channel-badge" data-channel="${esc(badgeKind)}">${esc(badgeText)}</span>
     <span class="sgk-detail-meta">${esc(metaParts.join(' · '))}</span>
    </div>
    <h4 class="sgk-detail-title">${esc(detailHeading)}</h4>
    <p class="sgk-detail-chapter">Thuộc: ${esc(lesson.chapter)}</p>
    <p class="sgk-detail-summary">${esc(summaryText)}</p>
    ${outcomes.length?`<div class="sgk-outcomes-box"><div class="sgk-outcomes-label">YÊU CẦU CẦN ĐẠT</div><ul class="sgk-outcomes">${outcomes.map(o=>`<li>${esc(o)}</li>`).join('')}</ul></div>`:''}
    ${detailsBlock}
   </div>`;
 }

 function updateRowHighlight(){
  for(const row of list.querySelectorAll('.sgk-lesson-row')){
   const match=activePreview
    &&row.dataset.collectionId===activePreview.collectionId
    &&Number(row.dataset.lessonNumber)===activePreview.lessonNumber;
   row.classList.toggle('is-selected',Boolean(match));
  }
 }

 function updateCheckboxes(){
  const visibleSelected=new Set();
  for(const group of list.querySelectorAll('[data-lesson-collection]')){
   const {id,lessons}=collections.find(c=>c.id===group.dataset.lessonCollection);
   const all=group.querySelector('[name=collection]'),picked=choices.get(id).size;
   for(const row of group.querySelectorAll('[name=lesson]'))if(row.checked)visibleSelected.add(`${id}::${row.value}`);
   if(all){
    all.checked=picked===lessons.length;
    all.indeterminate=picked>0&&picked<lessons.length;
   }
  }
  for(const chapter of list.querySelectorAll('[data-lesson-chapter]')){
   const rows=[...chapter.querySelectorAll('[name=lesson]')];
   const all=chapter.querySelector('[name=chapter]'), picked=rows.filter(row=>row.checked).length;
   if(all){
    all.checked=picked===rows.length&&rows.length>0;
    all.indeterminate=picked>0&&picked<rows.length;
   }
   const counter=chapter.querySelector('[data-chapter-count]');
   if(counter)counter.textContent=`${picked}/${rows.length}`;
  }
  const chips=[];
  for(const c of collections){
   const picked=[...(choices.get(c.id)||[])].sort((a,b)=>a-b);
   for(const num of picked){
    const lesson=c.lessons.find(l=>l.number===num);
    const label=c.record?c.name:`${c.name} · ${lesson?.title||('Bài '+num)}`;
    const hiddenInFilter=!visibleSelected.has(`${c.id}::${num}`);
    chips.push(`<span class="lesson-selected-chip${hiddenInFilter?' is-hidden-filter':''}">${esc(label)}${hiddenInFilter?' <em>(đang ẩn ngoài bộ lọc)</em>':''} <button type="button" class="tiny-btn" data-unselect-lesson data-collection-id="${esc(c.id)}" data-lesson-number="${num}" aria-label="Bỏ chọn ${esc(label)}">×</button></span>`);
   }
  }
  const chipsHost=form.querySelector('[data-lesson-selected-chips]');
  if(chipsHost){
   chipsHost.innerHTML=chips.join('');
   chipsHost.hidden=!chips.length;
  }
  const count=[...choices.values()].reduce((total,items)=>total+items.size,0);
  form.querySelector('[data-lesson-count]').textContent=`Đã chọn ${count} bài${changed.size?' · chưa lưu':''}`;
  const submitBtn=form.querySelector('[type=submit]');
  submitBtn.disabled=!changed.size;
  submitBtn.textContent=count>0?`Dùng bài đã chọn · ${count} bài`:'Dùng bài đã chọn';
 }

 function updateFilter(control,values,selected=control.value){
  control.replaceChildren(new Option('Tất cả',''),...[...new Set(values)].map(value=>new Option(value)));
  control.value=values.includes(selected)?selected:'';
 }

 function renderVolumePills(books,selectedVolume){
  if(!volumePillsHost)return;
  const counts=new Map();
  for(const c of books){
   counts.set(c.volume,(counts.get(c.volume)||0)+c.lessons.length);
  }
  const volumes=[...counts.keys()];
  if(!volumes.length){
   volumePillsHost.innerHTML='';
   return;
  }
  const totalLessons=books.reduce((s,c)=>s+c.lessons.length,0);
  const pills=[
   `<button type="button" class="sgk-vol-pill${!selectedVolume?' is-active':''}" data-sgk-volume="">Tất cả · ${totalLessons}</button>`,
   ...volumes.map(v=>`<button type="button" class="sgk-vol-pill${selectedVolume===v?' is-active':''}" data-sgk-volume="${esc(v)}">${esc(v)} · ${counts.get(v)}</button>`),
  ];
  volumePillsHost.innerHTML=pills.join('');
 }

 function render(){
  const {grade,subject,book,volume,query,library}=form.elements;
  const eligible=collections.filter(c=>(!library.value||(library.value==='personal')===Boolean(c.record))
   &&(!grade.value||grade.value===c.grade)&&lessonSubjectMatches(subject.value,c.subject));
  updateFilter(book,eligible.map(c=>c.book));
  const books=eligible.filter(c=>!book.value||book.value===c.book);
  updateFilter(volume,books.map(c=>c.volume));
  renderVolumePills(books,volume.value);
  if(seriesBadge){
   seriesBadge.textContent=book.value?`Bộ ${book.value}`:`Bộ ${KNTT_SERIES}`;
  }
  const rawQuery=query.value.trim();
  const hasSearch=Boolean(normalizeLessonSearch(rawQuery));
  const visibleItems=[];
  list.innerHTML=books.filter(c=>!volume.value||volume.value===c.volume).map(c=>{
   const lessons=c.lessons.filter(l=>lessonMatchesSearch(c,l,rawQuery));
   if(!lessons.length)return '';
   for(const l of lessons)visibleItems.push({collectionId:c.id,lessonNumber:l.number});
   const chapters=Map.groupBy(lessons,l=>l.chapter);
   const edited=editedDocs.get(c.id);
   if(c.record){
    const [lesson]=lessons,available=usable(c.record)&&lesson.text.trim();
    return `<section class="small-card sgk-collection" data-lesson-collection="${esc(c.id)}">
     <h3><span class="pill source-channel-badge" data-channel="personal">Tài liệu cá nhân</span> ${esc(c.name)}</h3><p class="hint">${esc([c.book,c.volume,lesson.chapter,lesson.title].join(' · '))}</p>
     <label class="consent"><input type="checkbox" name="lesson" value="1" ${available?'':'disabled'} ${choices.get(c.id).has(1)?'checked':''}> Dùng học liệu này</label>
     ${available?'':'<p class="hint">Chưa đủ điều kiện dùng cho trợ lý.</p>'}
     <details><summary>Xem học liệu</summary><p>${esc(lesson.outcome)}</p><p style="white-space:pre-wrap">${esc(lesson.text)}</p></details>
     <button type="button" data-edit-personal>Sửa học liệu</button></section>`;
   }
   const badgeText=c.catalogKind==='sgk'?'SGK':'Học liệu mẫu';
   const badgeChannel=c.catalogKind==='sgk'?'sgk':'sample';
   const pagesTag=c.totalPages?`<span class="sgk-page-tag">${esc(String(c.totalPages))} trang</span>`:'';
   return `<section class="small-card sgk-collection" data-lesson-collection="${esc(c.id)}">
    <div class="sgk-collection-head">
     <h3><span class="pill source-channel-badge" data-channel="${esc(badgeChannel)}">${esc(badgeText)}</span> ${esc(c.name)}</h3>
     ${pagesTag}
    </div>
    ${edited?'<p class="hint">Đang dùng bản đã đối chiếu trong đề.</p>':''}
    <label class="consent sgk-select-all"><input type="checkbox" name="collection"> Chọn cả tập (${c.lessons.length} bài)</label>
    ${[...chapters].map(([chapter,rows])=>{
     const chKey=`${c.id}::${chapter}`;
     const isCollapsed=collapsedChapters.has(chKey)&&!hasSearch;
     const pickedInChapter=rows.filter(r=>choices.get(c.id).has(r.number)).length;
     const chRange=chapterPageLabel(rows);
     return `<fieldset data-lesson-chapter class="sgk-chapter${isCollapsed?' is-collapsed':''}" data-chapter-key="${esc(chKey)}">
      <legend>
       <button type="button" class="sgk-chapter-toggle" data-sgk-toggle-chapter="${esc(chKey)}" aria-expanded="${isCollapsed?'false':'true'}">${isCollapsed?'▸':'▾'}</button>
       <span class="sgk-chapter-title">${esc(chapter)}</span>
       <span class="sgk-chapter-meta">
        <span class="sgk-chapter-count" data-chapter-count>${pickedInChapter}/${rows.length}</span>
        ${chRange?`<span class="sgk-page-tag">${esc(chRange)}</span>`:''}
       </span>
      </legend>
      <div class="sgk-chapter-body"${isCollapsed?' hidden':''}>
       <label class="consent"><input type="checkbox" name="chapter"> ${hasSearch?'Chọn tất cả kết quả trong chương':'Chọn cả chương'}</label>
       ${rows.map(l=>`<div class="source-choice sgk-lesson-row" data-collection-id="${esc(c.id)}" data-lesson-number="${l.number}">
        <label class="sgk-lesson-label"><input type="checkbox" name="lesson" value="${l.number}" ${choices.get(c.id).has(l.number)?'checked':''}> <span class="sgk-lesson-title">${esc(l.title)}</span></label>
        ${l.pageRange?`<span class="sgk-page-tag">${esc(l.pageRange)}</span>`:''}
       </div>`).join('')}
      </div>
     </fieldset>`;
    }).join('')}
   </section>`;
  }).join('')||'<p class="hint">Chưa có bài phù hợp với bộ lọc.</p>';

  const stillVisible=activePreview&&visibleItems.some(i=>i.collectionId===activePreview.collectionId&&i.lessonNumber===activePreview.lessonNumber);
  if(!stillVisible)activePreview=visibleItems[0]||null;
  updateRowHighlight();
  renderDetailPane();
  updateCheckboxes();
 }

 function commitSelectedToExam(){
  const addedIds=[],removedIds=[],addedPages={};
  context.change('Chọn học liệu theo bài',current=>{
   const attached=new Set(current.assistantSources||[]);
   current.assistantSourcePages??={};
   for(const collection of collections.filter(c=>changed.has(c.id))){
    const numbers=[...choices.get(collection.id)].sort((a,b)=>a-b);
    if(!numbers.length){
     attached.delete(collection.id);
     delete current.assistantSourcePages[collection.id];
     removedIds.push(collection.id);
     continue;
    }
    const saved=current.docs.find(d=>d.id===collection.id);
    if(collection.record){
     const record=collection.record;
     if(!usable(record)||!record.content_excerpt.trim())continue;
     const source={id:record.id,name:record.title,kind:'text',version:record.updated_at,
      pages:[{number:1,text:record.content_excerpt,title:record.lesson||record.title}],
      text:record.content_excerpt,personalLesson:true,sourceOrigin:record.source_origin||'personal_lesson',sourceLocator:record.locator,licenseStatus:record.license_status};
     if(saved)Object.assign(saved,source);
     else current.docs.push(source);
    }else if(!saved||(!editedCopy(saved)&&saved.version!==collection.version)){
     const pages=collection.lessons.map(lesson=>({
      ...lesson,text:`Bài ${lesson.number}. ${lesson.title}\n${lesson.text}\nMục tiêu: ${lesson.outcome}`,
     }));
     const source={id:collection.id,name:collection.name,kind:'text',version:collection.version,
      pages,text:pages.map(page=>page.text).join('\n\n'),catalog:true,sourceOrigin:'lesson_catalog'};
     if(saved)Object.assign(saved,source);
     else current.docs.push(source);
    }
    attached.add(collection.id);
    current.assistantSourcePages[collection.id]=numbers;
    addedIds.push(collection.id);
    addedPages[collection.id]=numbers;
   }
   current.assistantSources=[...attached];
  });
  mergeAssistantSourceDraft(examId,addedIds,addedPages,removedIds);
 }

 function attachReferenceTextDoc(id,name,text,originTag){
  if(!text.trim()){context.toast('Nội dung nguồn đang trống.');return;}
  context.change('Đính kèm nguồn tham khảo',current=>{
   const existing=current.docs.find(d=>d.id===id);
   const docObj={
    id,name,kind:'text',version:Date.now(),
    pages:[{number:1,text:text.slice(0,12000),title:name}],
    text:text.slice(0,12000),sourceOrigin:originTag,licenseStatus:'allowed',
   };
   if(existing)Object.assign(existing,docObj);
   else current.docs.push(docObj);
   current.assistantSources=[...new Set([...(current.assistantSources||[]),id])];
   current.assistantSourcePages??={};
   current.assistantSourcePages[id]=[1];
  });
  mergeAssistantSourceDraft(examId,[id],{[id]:[1]},[]);
  dialog.close();
  context.toast(`Đã đính kèm "${name}" làm nguồn tham khảo.`);
 }

 async function loadCommunityTab(panel){
  panel.innerHTML='<p class="hint">Đang tải danh sách đề cộng đồng…</p>';
  const res=await fetch('/api/community-exams',{headers}).catch(()=>null);
  if(!panel.isConnected)return;
  if(!res||!res.ok){
   panel.innerHTML='<p class="hint">Chưa có đề cộng đồng công khai hoặc chưa thể tải lúc này.</p>';
   return;
  }
  const data=await res.json().catch(()=>({items:[]}));
  const items=data.items||data.exams||[];
  if(!items.length){
   panel.innerHTML='<p class="hint">Chưa có đề cộng đồng nào được chia sẻ trong không gian làm việc này.</p>';
   return;
  }
  panel.innerHTML=`<div class="sgk-aux-list">${items.map(item=>`
   <article class="small-card sgk-aux-card">
    <div>
     <h4>${esc(item.title||'Đề cộng đồng')}</h4>
     <p class="hint">${esc([item.subject,item.grade?`Lớp ${item.grade}`:'',item.questionCount?`${item.questionCount} câu`:'',item.series||''].filter(Boolean).join(' · '))}</p>
    </div>
    <button type="button" data-use-community="${esc(item.token||item.id||'')}" data-title="${esc(item.title||'Đề cộng đồng')}" data-meta="${esc([item.subject,item.grade?`Lớp ${item.grade}`:'',item.chapter||''].filter(Boolean).join(' · '))}">Dùng làm nguồn tham khảo</button>
   </article>`).join('')}</div>`;
 }

 function loadMyExamsTab(panel){
  const allExams=(context.getState?.().exams||[]).filter(e=>e.id!==examId);
  if(!allExams.length){
   panel.innerHTML='<p class="hint">Chưa có đề kiểm tra nào khác trong không gian làm việc của bạn.</p>';
   return;
  }
  panel.innerHTML=`<div class="sgk-aux-list">${allExams.map(e=>`
   <article class="small-card sgk-aux-card">
    <div>
     <h4>${esc(e.title||'Đề chưa đặt tên')}</h4>
     <p class="hint">${esc([e.subject,e.grade?`Lớp ${e.grade}`:'',`${(e.questions||[]).length} câu`,e.minutes?`${e.minutes} phút`:''].filter(Boolean).join(' · '))}</p>
    </div>
    <button type="button" data-use-my-exam="${esc(e.id)}">Dùng làm nguồn tham khảo</button>
   </article>`).join('')}</div>`;
 }

 async function loadMyMatricesTab(panel){
  panel.innerHTML='<p class="hint">Đang tải mẫu ma trận đã lưu…</p>';
  const res=await fetch('/api/matrix-templates',{headers}).catch(()=>null);
  if(!panel.isConnected)return;
  const data=res&&res.ok?await res.json().catch(()=>({templates:[]})):{templates:[]};
  const templates=data.templates||[];
  if(!templates.length){
   panel.innerHTML='<p class="hint">Chưa có mẫu ma trận cá nhân nào. Bạn có thể lưu mẫu trong hộp thoại Ma trận đề.</p>';
   return;
  }
  panel.innerHTML=`<div class="sgk-aux-list">${templates.map(t=>{
   const rows=t.rows||[];
   const summary=rows.map(r=>`${r.topic||r.name||'Chủ đề'} (${(r.targets||[]).reduce((a,b)=>a+Number(b||0),0)} câu)`).join('; ');
   return `<article class="small-card sgk-aux-card">
    <div>
     <h4>${esc(t.name||'Mẫu ma trận')}</h4>
     <p class="hint">${esc([t.subject,t.grade?`Lớp ${t.grade}`:'',`${rows.length} dòng chủ đề`].filter(Boolean).join(' · '))}</p>
     ${summary?`<p class="hint">${esc(summary)}</p>`:''}
    </div>
    <button type="button" data-use-matrix="${esc(t.id)}" data-name="${esc(t.name||'Mẫu ma trận')}" data-summary="${esc(summary)}">Dùng làm nguồn tham khảo</button>
   </article>`;
  }).join('')}</div>`;
 }

 modalRoot.addEventListener('click',async event=>{
  const tabBtn=event.target.closest('[data-sgk-tab]');
  if(tabBtn){
   const nextTab=tabBtn.dataset.sgkTab;
   activeTab=nextTab;
   for(const btn of modalRoot.querySelectorAll('[data-sgk-tab]')){
    const on=btn.dataset.sgkTab===nextTab;
    btn.classList.toggle('is-active',on);
    btn.setAttribute('aria-selected',on?'true':'false');
   }
   const showCatalog=nextTab==='library'||nextTab==='sgk';
   modalRoot.querySelector('[data-sgk-panel="catalog"]').hidden=!showCatalog;
   modalRoot.querySelector('[data-sgk-panel="community"]').hidden=nextTab!=='community';
   modalRoot.querySelector('[data-sgk-panel="my-exams"]').hidden=nextTab!=='my-exams';
   modalRoot.querySelector('[data-sgk-panel="my-matrices"]').hidden=nextTab!=='my-matrices';
   if(nextTab==='sgk'){
    form.elements.library.value='sample';
    render();
    if([...form.elements.book.options].some(o=>o.value===KNTT_SERIES)){
     form.elements.book.value=KNTT_SERIES;
     render();
    }
   }else if(nextTab==='library'){
    form.elements.library.value='';
    form.elements.book.value='';
    render();
   }else if(nextTab==='community'){
    await loadCommunityTab(modalRoot.querySelector('[data-sgk-panel="community"]'));
   }else if(nextTab==='my-exams'){
    loadMyExamsTab(modalRoot.querySelector('[data-sgk-panel="my-exams"]'));
   }else if(nextTab==='my-matrices'){
    await loadMyMatricesTab(modalRoot.querySelector('[data-sgk-panel="my-matrices"]'));
   }
   return;
  }
  const useCommunity=event.target.closest('[data-use-community]');
  if(useCommunity){
   const token=useCommunity.dataset.useCommunity;
   const title=useCommunity.dataset.title;
   const meta=useCommunity.dataset.meta;
   const text=`Đề cộng đồng tham khảo: ${title}\n${meta}`;
   attachReferenceTextDoc(`community-${token}`,`Đề cộng đồng · ${title}`,text,'community');
   return;
  }
  const useMyExam=event.target.closest('[data-use-my-exam]');
  if(useMyExam){
   const targetExam=(context.getState?.().exams||[]).find(e=>e.id===useMyExam.dataset.useMyExam);
   if(!targetExam)return;
   const body=(targetExam.questions||[]).map((q,i)=>`Câu ${i+1}: ${q.stem||''}`).join('\n');
   attachReferenceTextDoc(`my-exam-${targetExam.id}`,`Đề tham khảo · ${targetExam.title||'Đề của tôi'}`,body||targetExam.title||'Đề tham khảo','teacher_exam');
   return;
  }
  const useMatrix=event.target.closest('[data-use-matrix]');
  if(useMatrix){
   const id=useMatrix.dataset.useMatrix, name=useMatrix.dataset.name, summary=useMatrix.dataset.summary;
   attachReferenceTextDoc(`matrix-${id}`,`Ma trận · ${name}`,`Mẫu ma trận: ${name}\n${summary}`,'matrix_template');
   return;
  }
 });

 form.addEventListener('click',event=>{
  const volPill=event.target.closest('[data-sgk-volume]');
  if(volPill){
   form.elements.volume.value=volPill.dataset.sgkVolume;
   render();
   return;
  }
  const toggleBtn=event.target.closest('[data-sgk-toggle-chapter]');
  if(toggleBtn){
   const key=toggleBtn.dataset.sgkToggleChapter;
   if(collapsedChapters.has(key))collapsedChapters.delete(key);
   else collapsedChapters.add(key);
   render();
   return;
  }
  const clearBtn=event.target.closest('[data-sgk-clear]');
  if(clearBtn){
   for(const [id,set] of choices.entries()){
    if(set.size){set.clear();changed.add(id);}
   }
   for(const cb of list.querySelectorAll('[name=lesson]'))cb.checked=false;
   updateCheckboxes();
   return;
  }
  const quickBtn=event.target.closest('[data-sgk-quick-compose]');
  if(quickBtn){
   if(context.exam().id!==examId)return;
   if(activePreview){
    const set=choices.get(activePreview.collectionId);
    if(set&&!set.has(activePreview.lessonNumber)){
     set.add(activePreview.lessonNumber);
     changed.add(activePreview.collectionId);
    }
   }
   if(changed.size)commitSelectedToExam();
   const col=activePreview?collections.find(c=>c.id===activePreview.collectionId):null;
   const lesson=col?.lessons.find(l=>l.number===activePreview?.lessonNumber);
   dialog.close();
   if(lesson&&typeof context.addChat==='function'){
    context.addChat('user',`Soạn nhanh đề kiểm tra bám sát ${col.subject} lớp ${col.grade} – ${lesson.title} (${col.volume}).`);
   }
   context.toast(lesson?`Đã đính kèm "${lesson.title}" để soạn đề nhanh.`:'Đã áp dụng bài đã chọn.');
   return;
  }
  const unselect=event.target.closest('[data-unselect-lesson]');
  if(unselect){
   const colId=unselect.dataset.collectionId, num=Number(unselect.dataset.lessonNumber);
   choices.get(colId)?.delete(num);
   changed.add(colId);
   const cb=list.querySelector(`[data-lesson-collection="${CSS.escape(colId)}"] [name="lesson"][value="${num}"]`);
   if(cb)cb.checked=false;
   updateCheckboxes();
   return;
  }
  const button=event.target.closest('[data-edit-personal]');
  if(button){
   const id=button.closest('[data-lesson-collection]').dataset.lessonCollection;
   editPersonal(collections.find(c=>c.id===id).record);
   editor.open=true;
   personalForm.elements.title.focus();
   return;
  }
  const row=event.target.closest('.sgk-lesson-row');
  if(row){
   activePreview={collectionId:row.dataset.collectionId,lessonNumber:Number(row.dataset.lessonNumber)};
   updateRowHighlight();
   renderDetailPane();
  }
 });
 form.addEventListener('input',event=>{if(event.target.type==='search')render();});
 form.addEventListener('change',event=>{
  if(event.target.tagName==='SELECT'){render();return;}
  const collection=event.target.closest('[data-lesson-collection]');
  if(!collection)return;
  const id=collection.dataset.lessonCollection, selected=choices.get(id);
  if(event.target.name==='collection'){
   selected.clear();
   if(event.target.checked)for(const lesson of collections.find(c=>c.id===id).lessons)selected.add(lesson.number);
   changed.add(id);
   for(const row of collection.querySelectorAll('[name=lesson]'))row.checked=selected.has(Number(row.value));
   updateCheckboxes();
   return;
  }
  const rows=event.target.name==='chapter'?event.target.closest('fieldset').querySelectorAll('[name=lesson]'):[event.target];
  for(const row of rows){
   row.checked=event.target.checked;
   if(row.checked)selected.add(Number(row.value));
   else selected.delete(Number(row.value));
  }
  if(event.target.name==='lesson'){
   activePreview={collectionId:id,lessonNumber:Number(event.target.value)};
   updateRowHighlight();
   renderDetailPane();
  }
  changed.add(id);
  updateCheckboxes();
 });
 form.addEventListener('submit',async event=>{
  event.preventDefault();
  event.stopPropagation();
  if(context.exam().id!==examId)return;
  commitSelectedToExam();
  dialog.close();
  if(useLayer2)await context.act('assistant-sources');
 });
 render();
 form.elements.query?.focus();
 if(returnFocusEl){
  dialog.addEventListener('close',()=>{
   if(!dialog.open&&returnFocusEl.isConnected)returnFocusEl.focus?.();
  },{once:true});
 }
}
