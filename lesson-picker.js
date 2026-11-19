import {esc} from './core.js';
import {selectedDocumentPages} from './assistant-sources.js';
import {workspaceHeaders} from './storage.js';

export async function openLessonPicker(context) {
 const examId=context.exam().id;
 const dialog=document.querySelector('#dialog');
 const origin=dialog.querySelector('#assistant-source-form');
 const response=await fetch('/api/lesson-catalog',{headers:workspaceHeaders()});
 if(!response.ok)throw Error('Chưa mở được học liệu theo bài.');
 const {collections}=await response.json();
 if(context.exam().id!==examId||!origin?.isConnected||!dialog.open)return;
 const exam=context.exam(), choices=new Map(), changed=new Set();
 for(const collection of collections){
  const saved=exam.docs.find(doc=>doc.id===collection.id);
  choices.set(collection.id,new Set(saved&&exam.assistantSources?.includes(saved.id)
   ?selectedDocumentPages(exam,saved).map(page=>page.number):[]));
  if(saved&&exam.assistantSources?.includes(saved.id)&&saved.version!==collection.version){
   const available=new Set(collection.lessons.map(lesson=>lesson.number));
   choices.set(collection.id,new Set([...choices.get(collection.id)].filter(number=>available.has(number))));
   changed.add(collection.id);
  }
 }
 const select=(label,name,values,selected)=>`<label>${label}<select name="${name}"><option value="">Tất cả</option>${values.map(value=>`<option ${value===selected?'selected':''}>${esc(value)}</option>`).join('')}</select></label>`;
 const grades=[...new Set(collections.map(c=>c.grade))].sort((a,b)=>Number(a)-Number(b));
 const subjects=[...new Set(collections.map(c=>c.subject))];
 context.modal('Học liệu theo bài',`<form id="lesson-picker"><p class="hint">Ghi chú và mục tiêu do dự án biên soạn. Số bài dùng để đối chiếu trong kho.</p><div class="grid2">${select('Lớp','grade',grades,String(exam.grade))}${select('Môn','subject',subjects,exam.subject)}${select('Bộ học liệu','book',[])}${select('Tập','volume',[])}</div><label>Tìm bài hoặc chương<input type="search" name="query" placeholder="Ví dụ: phép thế"></label><div data-lesson-list></div><p data-lesson-count role="status"></p><div class="modal-foot"><button type="button" data-action="assistant-sources">Quay lại nguồn</button><button type="submit" class="primary">Dùng bài đã chọn</button></div></form>`);
 const form=dialog.querySelector('#lesson-picker'),list=form.querySelector('[data-lesson-list]');
 const normalize=value=>value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().replace(/đ/g,'d');
 function updateCheckboxes(){
  for(const group of list.querySelectorAll('[data-lesson-collection]')){
   const {id,lessons}=collections.find(c=>c.id===group.dataset.lessonCollection);
   const all=group.querySelector('[name=collection]'),picked=choices.get(id).size;
   all.checked=picked===lessons.length;
   all.indeterminate=picked>0&&picked<lessons.length;
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
 function render(){
  const {grade,subject,book,volume,query}=form.elements;
  const eligible=collections.filter(c=>(!grade.value||grade.value===c.grade)&&(!subject.value||subject.value===c.subject));
  const fillOptions=(control,values)=>{
   const selected=control.value;
   control.replaceChildren(new Option('Tất cả',''),...[...new Set(values)].map(value=>new Option(value)));
   control.value=values.includes(selected)?selected:'';
  };
  fillOptions(book,eligible.map(c=>c.book));
  const books=eligible.filter(c=>!book.value||book.value===c.book);
  fillOptions(volume,books.map(c=>c.volume));
  const search=normalize(query.value.trim());
  list.innerHTML=books.filter(c=>!volume.value||volume.value===c.volume).map(c=>{
   const lessons=c.lessons.filter(l=>normalize([l.title,l.chapter,l.outcome,c.book,c.volume].join(' ')).includes(search));
   if(!lessons.length)return '';
   const chapters=Map.groupBy(lessons,l=>l.chapter);
   return `<section class="small-card" data-lesson-collection="${esc(c.id)}"><h3>${esc(c.name)}</h3><label class="consent"><input type="checkbox" name="collection"> Chọn cả tập (${c.lessons.length} bài)</label>${[...chapters].map(([chapter,rows])=>`<fieldset data-lesson-chapter><legend>${esc(chapter)}</legend><label class="consent"><input type="checkbox" name="chapter"> ${search?'Chọn tất cả kết quả trong chương':'Chọn cả chương'}</label>${rows.map(l=>`<div class="source-choice"><label><input type="checkbox" name="lesson" value="${l.number}" ${choices.get(c.id).has(l.number)?'checked':''}> ${esc(l.title)}</label><details><summary>Xem học liệu</summary><p><b>Mục tiêu</b> · ${esc(l.outcome)}</p><p>${esc(l.text)}</p></details></div>`).join('')}</fieldset>`).join('')}</section>`;
  }).join('')||'<p>Chưa có bài phù hợp với bộ lọc.</p>';
  updateCheckboxes();
 }
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
    if(!saved||saved.version!==collection.version){
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
