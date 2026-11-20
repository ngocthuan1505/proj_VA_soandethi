import {esc} from './core.js';
import {selectedDocumentPages} from './assistant-sources.js';
import {workspaceHeaders} from './storage.js';

const personalRoute='/api/lesson-catalog/sources';
const usable=record=>['allowed','teacher_owned'].includes(record.license_status);
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
 const dialog=document.querySelector('#dialog');
 const origin=dialog.querySelector('#assistant-source-form');
 const headers=workspaceHeaders();
 const [response,personal]=await Promise.all([
  fetch('/api/lesson-catalog',{headers}),
  fetch(personalRoute,{headers}).then(r=>r.ok?r.json():null).catch(()=>null),
 ]);
 if(!response.ok)throw Error('Chưa mở được học liệu theo bài.');
 const {collections}=await response.json();
 collections.push(...(personal?.sources||[]).map(asCollection));
 if(context.exam().id!==examId||!origin?.isConnected||!dialog.open)return;
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
  }else if(saved&&!editedDocs.has(saved.id)&&exam.assistantSources?.includes(saved.id)&&saved.version!==collection.version){
   const available=new Set(collection.lessons.map(lesson=>lesson.number));
   choices.set(collection.id,new Set([...choices.get(collection.id)].filter(number=>available.has(number))));
   changed.add(collection.id);
  }
 }
 const select=(label,name,values,selected)=>`<label>${label}<select name="${name}"><option value="">Tất cả</option>${values.map(value=>`<option ${value===selected?'selected':''}>${esc(value)}</option>`).join('')}</select></label>`;
 const grades=[...new Set(collections.map(c=>c.grade))].sort((a,b)=>Number(a)-Number(b));
 const subjects=[...new Set(collections.map(c=>c.subject))];
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
 <label>Nội dung học liệu<textarea name="content_excerpt" rows="5" maxlength="12000" required></textarea></label>
 <label class="consent"><input type="checkbox" name="usage"> Tôi có quyền dùng nội dung này cho trợ lý</label>
 <p role="status" data-personal-status></p>
 <button type="submit" class="primary">Lưu học liệu</button>
 </form></details>`:'<p class="hint">Chưa tải được kho học liệu cá nhân.</p>'}
 <form id="lesson-picker"><p class="hint">Chọn học liệu mẫu của dự án hoặc bài trong kho cá nhân.</p><div class="grid2">
 <label>Kho<select name="library"><option value="">Tất cả</option><option value="sample">Học liệu mẫu</option><option value="personal">Kho cá nhân</option></select></label>${select('Lớp','grade',grades,String(exam.grade))}${select('Môn','subject',subjects,exam.subject)}${select('Bộ học liệu','book',[])}${select('Tập','volume',[])}</div><label>Tìm bài hoặc chương<input type="search" name="query" placeholder="Ví dụ: phép thế"></label><div data-lesson-list></div><p data-lesson-count role="status"></p><div class="modal-foot"><button type="button" data-action="assistant-sources">Quay lại nguồn</button><button type="submit" class="primary">Dùng bài đã chọn</button></div></form>`);
 const form=dialog.querySelector('#lesson-picker'),list=form.querySelector('[data-lesson-list]');
 const editor=dialog.querySelector('[data-personal-editor]'),personalForm=editor?.querySelector('form');
 let editing=null;
 function editPersonal(record){
  editing=record;
  personalForm.reset();
  if(record){
   for(const field of ['grade','subject','series','volume','chapter','lesson','title','locator','content_excerpt']){
    personalForm.elements[field].value=record[field]??'';
   }
   personalForm.elements.usage.checked=usable(record);
  }
  editor.querySelector('summary').textContent=record?'Sửa học liệu cá nhân':'Thêm học liệu cá nhân';
  personalForm.querySelector('[data-personal-status]').textContent='';
 }
 personalForm?.addEventListener('submit',async event=>{
  event.preventDefault();
  event.stopPropagation();
  const button=personalForm.querySelector('button');
  if(button.disabled)return;
  const status=personalForm.querySelector('[data-personal-status]');
  const {usage,...fields}=Object.fromEntries(new FormData(personalForm));
  const payload={...fields,grade:Number(fields.grade),license_status:usage?(editing&&usable(editing)?editing.license_status:'allowed'):'pending_review'};
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
 const normalize=value=>value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().replace(/đ/g,'d');
 function updateCheckboxes(){
  for(const group of list.querySelectorAll('[data-lesson-collection]')){
   const {id,lessons}=collections.find(c=>c.id===group.dataset.lessonCollection);
   const all=group.querySelector('[name=collection]'),picked=choices.get(id).size;
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
   &&(!grade.value||grade.value===c.grade)&&(!subject.value||subject.value===c.subject));
  updateFilter(book,eligible.map(c=>c.book));
  const books=eligible.filter(c=>!book.value||book.value===c.book);
  updateFilter(volume,books.map(c=>c.volume));
  const search=normalize(query.value.trim());
  list.innerHTML=books.filter(c=>!volume.value||volume.value===c.volume).map(c=>{
   const lessons=c.lessons.filter(l=>normalize([l.title,l.chapter,l.outcome,c.book,c.volume].join(' ')).includes(search));
   if(!lessons.length)return '';
   const chapters=Map.groupBy(lessons,l=>l.chapter);
   const edited=editedDocs.get(c.id);
   if(c.record){
    const [lesson]=lessons,available=usable(c.record)&&lesson.text.trim();
    return `<section class="small-card" data-lesson-collection="${esc(c.id)}">
     <h3>${esc(c.name)}</h3><p class="hint">${esc([c.book,c.volume,lesson.chapter,lesson.title].join(' · '))}</p>
     <label class="consent"><input type="checkbox" name="lesson" value="1" ${available?'':'disabled'} ${choices.get(c.id).has(1)?'checked':''}> Dùng học liệu này</label>
     ${available?'':'<p class="hint">Chưa đủ điều kiện dùng cho trợ lý.</p>'}
     <details><summary>Xem học liệu</summary><p>${esc(lesson.outcome)}</p><p style="white-space:pre-wrap">${esc(lesson.text)}</p></details>
     <button type="button" data-edit-personal>Sửa học liệu</button></section>`;
   }
   return `<section class="small-card" data-lesson-collection="${esc(c.id)}"><h3>${esc(c.name)}</h3>${edited?'<p class="hint">Đang dùng bản đã đối chiếu trong đề.</p>':''}<label class="consent"><input type="checkbox" name="collection"> Chọn cả tập (${c.lessons.length} bài)</label>${[...chapters].map(([chapter,rows])=>`<fieldset data-lesson-chapter><legend>${esc(chapter)}</legend><label class="consent"><input type="checkbox" name="chapter"> ${search?'Chọn tất cả kết quả trong chương':'Chọn cả chương'}</label>${rows.map(l=>`<div class="source-choice"><label><input type="checkbox" name="lesson" value="${l.number}" ${choices.get(c.id).has(l.number)?'checked':''}> ${esc(l.title)}</label><details><summary>Xem học liệu</summary><p><b>Mục tiêu</b> · ${esc(l.outcome)}</p><p>${esc(edited?.pages.find(page=>page.number===l.number)?.text??l.text)}</p></details></div>`).join('')}</fieldset>`).join('')}</section>`;
  }).join('')||'<p>Chưa có bài phù hợp với bộ lọc.</p>';
  updateCheckboxes();
 }
 form.addEventListener('click',event=>{
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
 form.addEventListener('submit',event=>{
  event.preventDefault();
  event.stopPropagation();
  if(context.exam().id!==examId)return;
  context.change('Chọn học liệu theo bài',current=>{
   const attached=new Set(current.assistantSources||[]);
   current.assistantSourcePages??={};
   for(const collection of collections.filter(c=>changed.has(c.id))){
    const numbers=[...choices.get(collection.id)].sort((a,b)=>a-b);
    if(!numbers.length){
     attached.delete(collection.id);
     delete current.assistantSourcePages[collection.id];
     continue;
    }
    const saved=current.docs.find(d=>d.id===collection.id);
    if(collection.record){
     const record=collection.record;
     if(!usable(record)||!record.content_excerpt.trim())continue;
     const source={id:record.id,name:record.title,kind:'text',version:record.updated_at,
      pages:[{number:1,text:record.content_excerpt,title:record.lesson||record.title}],
      text:record.content_excerpt,personalLesson:true,licenseStatus:record.license_status};
     if(saved)Object.assign(saved,source);
     else current.docs.push(source);
    }else if(!saved||(!editedCopy(saved)&&saved.version!==collection.version)){
     const pages=collection.lessons.map(lesson=>({
      ...lesson,text:`Bài ${lesson.number}. ${lesson.title}\n${lesson.text}\nMục tiêu: ${lesson.outcome}`,
     }));
     const source={id:collection.id,name:collection.name,kind:'text',version:collection.version,
      pages,text:pages.map(page=>page.text).join('\n\n'),catalog:true};
     if(saved)Object.assign(saved,source);
     else current.docs.push(source);
    }
    attached.add(collection.id);
    current.assistantSourcePages[collection.id]=numbers;
   }
   current.assistantSources=[...attached];
  });
  dialog.close();
 });
 render();
}
