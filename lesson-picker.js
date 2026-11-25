import {esc,touch,check} from './core.js';
import {selectedDocumentPages} from './assistant-sources.js';
import {workspaceHeaders} from './storage.js';
import {mergeAssistantSourceDraft} from './reference.js';

const personalRoute='/api/lesson-catalog/sources';
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
   out.add(item.replace(/\bbang phep the\b/g,'the').replace(/\bphep the\b/g,'the'));
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
 const rawHay=[collection?.name,collection?.subject,collection?.book,collection?.volume,lesson?.chapter,lesson?.title,lesson?.outcome,lesson?.text].filter(Boolean).join(' ');
 const hay=foldVietnameseOrthography(normalizeLessonSearch(rawHay));
 if(!hay)return false;
 return variants.some(v=>{
  if(hay.includes(v))return true;
  const toks=v.split(' ').filter(Boolean);
  return toks.length>=2&&toks.every(t=>hay.includes(t));
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
 book:record.series||'Học liệu cá nhân',volume:record.volume||'Chưa xếp tập',
 name:record.title,record,lessons:[{
  number:1,chapter:record.chapter||'Chưa xếp chương',title:record.lesson||record.title,
  outcome:record.locator,text:record.content_excerpt,
 }],
});

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
 context.modal('Học liệu theo bài',`
 ${personal?`<details data-personal-editor><summary>Thêm học liệu cá nhân</summary>
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
 <form id="lesson-picker"><p class="hint">Chọn học liệu mẫu của dự án hoặc bài trong kho cá nhân.</p><div class="grid2">
 <label>Kho<select name="library"><option value="">Tất cả</option><option value="sample">Học liệu mẫu</option><option value="personal">Kho cá nhân</option></select></label>${select('Lớp','grade',grades,String(exam.grade))}${select('Môn','subject',subjects,initialSubject)}${select('Bộ học liệu','book',[])}${select('Tập','volume',[])}</div><label>Tìm bài hoặc chương<input type="search" name="query" placeholder="Ví dụ: phép thế"></label><div data-lesson-list></div><p data-lesson-count role="status"></p><div data-lesson-selected-chips class="lesson-selected-chips" hidden></div><div class="modal-foot"><button type="button" data-action="${useLayer2?'close-top-modal':'assistant-sources'}">Quay lại nguồn</button><button type="submit" class="primary">Dùng bài đã chọn</button></div></form>`,'',{layer:useLayer2?2:1});
 const form=dialog.querySelector('#lesson-picker'),list=form.querySelector('[data-lesson-list]');
 const editor=dialog.querySelector('[data-personal-editor]'),personalForm=editor?.querySelector('form');
 let editing=null, importSequence=0, imported=null, sourceOrigin='';
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
   all.checked=picked===rows.length;
   all.indeterminate=picked>0&&picked<rows.length;
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
  form.querySelector('[data-lesson-count]').textContent=count+` bài được chọn${changed.size?' · chưa lưu':''}`;
  form.querySelector('[type=submit]').disabled=!changed.size;
 }
 function updateFilter(control,values,selected=control.value){
  control.replaceChildren(new Option('Tất cả',''),...[...new Set(values)].map(value=>new Option(value)));
  control.value=values.includes(selected)?selected:'';
 }
 function render(){
  const {grade,subject,book,volume,query,library}=form.elements;
  const eligible=collections.filter(c=>(!library.value||(library.value==='personal')===Boolean(c.record))
   &&(!grade.value||grade.value===c.grade)&&lessonSubjectMatches(subject.value,c.subject));
  updateFilter(book,eligible.map(c=>c.book));
  const books=eligible.filter(c=>!book.value||book.value===c.book);
  updateFilter(volume,books.map(c=>c.volume));
  const rawQuery=query.value.trim();
  const hasSearch=Boolean(normalizeLessonSearch(rawQuery));
  list.innerHTML=books.filter(c=>!volume.value||volume.value===c.volume).map(c=>{
   const lessons=c.lessons.filter(l=>lessonMatchesSearch(c,l,rawQuery));
   if(!lessons.length)return '';
   const chapters=Map.groupBy(lessons,l=>l.chapter);
   const edited=editedDocs.get(c.id);
   if(c.record){
    const [lesson]=lessons,available=usable(c.record)&&lesson.text.trim();
    return `<section class="small-card" data-lesson-collection="${esc(c.id)}">
     <h3><span class="pill source-channel-badge" data-channel="personal">Tài liệu cá nhân</span> ${esc(c.name)}</h3><p class="hint">${esc([c.book,c.volume,lesson.chapter,lesson.title].join(' · '))}</p>
     <label class="consent"><input type="checkbox" name="lesson" value="1" ${available?'':'disabled'} ${choices.get(c.id).has(1)?'checked':''}> Dùng học liệu này</label>
     ${available?'':'<p class="hint">Chưa đủ điều kiện dùng cho trợ lý.</p>'}
     <details><summary>Xem học liệu</summary><p>${esc(lesson.outcome)}</p><p style="white-space:pre-wrap">${esc(lesson.text)}</p></details>
     <button type="button" data-edit-personal>Sửa học liệu</button></section>`;
   }
   return `<section class="small-card" data-lesson-collection="${esc(c.id)}"><h3><span class="pill source-channel-badge" data-channel="sample">Học liệu mẫu</span> ${esc(c.name)}</h3>${edited?'<p class="hint">Đang dùng bản đã đối chiếu trong đề.</p>':''}<label class="consent"><input type="checkbox" name="collection"> Chọn cả tập (${c.lessons.length} bài)</label>${[...chapters].map(([chapter,rows])=>`<fieldset data-lesson-chapter><legend>${esc(chapter)}</legend><label class="consent"><input type="checkbox" name="chapter"> ${hasSearch?'Chọn tất cả kết quả trong chương':'Chọn cả chương'}</label>${rows.map(l=>`<div class="source-choice"><label><input type="checkbox" name="lesson" value="${l.number}" ${choices.get(c.id).has(l.number)?'checked':''}> ${esc(l.title)}</label><details><summary>Xem học liệu</summary><p><b>Mục tiêu</b> · ${esc(l.outcome)}</p><p>${esc(edited?.pages.find(page=>page.number===l.number)?.text??l.text)}</p></details></div>`).join('')}</fieldset>`).join('')}</section>`;
  }).join('')||'<p>Chưa có bài phù hợp với bộ lọc.</p>';
  updateCheckboxes();
 }
 form.addEventListener('click',event=>{
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
  if(!button)return;
  const id=button.closest('[data-lesson-collection]').dataset.lessonCollection;
  editPersonal(collections.find(c=>c.id===id).record);
  editor.open=true;
  personalForm.elements.title.focus();
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
  changed.add(id);
  updateCheckboxes();
 });
 form.addEventListener('submit',async event=>{
  event.preventDefault();
  event.stopPropagation();
  if(context.exam().id!==examId)return;
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
