import {mountUsability,refreshUsability} from './assets/usability.js';
import {mountDesign,handleDesignAction,refreshDesign} from './design.js';
import {esc,uid,touch,check,clone,separateMarking} from './core.js';
import {mountEditor,format,flushEditor,currentEditorKey,selectedTypography,reconcileEditorRich} from './editor.js';
import {mountPages,schedulePages,jumpPage,updatePageStatus} from './pages.js';
import {showDropdown,closeFloating} from './reference.js';
import {richTextHTML,mathParts} from './math-content.js';
import {renderFigure,solveFigure,triangleFigure} from './geometry.js';
import {openSketchBoard} from './sketch-board.js';
let c,initialized=false,outlineObserver=null,figureState=null;const $=s=>document.querySelector(s);
const b=(action,text,attrs='')=>`<button type="button" data-action="${action}" ${attrs}>${text}</button>`;
const field=(q,name,index,label,text)=>`<textarea class="rich-field" data-id="${q.id}" data-rich-field="${name}" data-rich-index="${index}" aria-label="${esc(label)}">${esc(text)}</textarea>`;
function formatInlineSegment(text){
 return String(text||'').split(/(`[^`\n]+`)/g).map((chunk,idx)=>{
  if(idx%2===1&&chunk.startsWith('`')&&chunk.endsWith('`'))return `<code>${esc(chunk.slice(1,-1))}</code>`;
  return esc(chunk).replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>');
 }).join('');
}
function renderAssistantInline(line){
 return mathParts(line).map(p=>p.latex?richTextHTML(p.display?`$$${p.latex}$$`:`$${p.latex}$`):formatInlineSegment(p.text)).join('');
}
export function assistantText(text){
 const source=String(text||'').replace(/```(?:json|latex|markdown|text)?\n?([\s\S]*?)```/g,'$1');
 const blocks=source.split('\n').map(rawLine=>{
  const line=String(rawLine||'');
  const headMatch=line.match(/^#{1,3}\s+(.+)$/);
  if(headMatch)return {block:true,html:`<h4>${renderAssistantInline(headMatch[1])}</h4>`};
  const bulletMatch=line.match(/^[-•]\s+(.+)$/);
  if(bulletMatch)return {block:true,html:`<div class="chat-list-item">${renderAssistantInline(bulletMatch[1])}</div>`};
  const ordMatch=line.match(/^(\d+[.)])\s+(.+)$/);
  if(ordMatch)return {block:true,html:`<div class="chat-list-item chat-list-ordered"><span class="chat-list-num">${esc(ordMatch[1])}</span> <span>${renderAssistantInline(ordMatch[2])}</span></div>`};
  if(!line.trim())return {block:false,empty:true,html:'<br>'};
  return {block:false,empty:false,html:renderAssistantInline(line)};
 });
 let out='';
 for(let i=0;i<blocks.length;i++){
  const cur=blocks[i],next=blocks[i+1];
  out+=cur.html;
  if(!cur.block&&!cur.empty&&next&&!next.block&&!next.empty)out+='<br>';
 }
 return out;
}
function inlineAnswers(){const e=c.exam();if(separateMarking(e)){const body=$('#marking-guide .full-rubric-table tbody');if(body){let i=0;for(const q of e.questions){const row=body.children[i++];if(!row)break;row.children[1].innerHTML=field(q,'explanation',0,'Lời giải bài '+(e.questions.indexOf(q)+1),q.explanation);for(const [j,r]of(q.rubric||[]).entries()){const line=body.children[i++];if(!line)break;line.firstElementChild.innerHTML=field(q,'rubric',j,'Bước chấm '+(j+1)+' bài '+(e.questions.indexOf(q)+1),r.text);line.lastElementChild.innerHTML=`<input class="rubric-point-input" type="number" min="0.05" max="10" step="0.05" data-rubric-point="${q.id}" data-index="${j}" value="${r.points}" aria-label="Điểm bước ${j+1} bài ${e.questions.indexOf(q)+1}">`;}}}}for(const q of e.questions){const root=document.getElementById('q-'+q.id);if(!root)continue;root.querySelectorAll('.option input').forEach((input,i)=>{const area=document.createElement('textarea');area.className='rich-field';Object.assign(area.dataset,{id:q.id,richField:'option',richIndex:String(i)});area.setAttribute('aria-label',input.getAttribute('aria-label'));area.value=q.options[i];input.replaceWith(area);});}mountEditor(c);}
function compactCompose(){const compose=$('.chat-compose');if(!compose)return;const labels=[...compose.querySelectorAll(':scope > .compose-consent')];if(labels.length){const target=$('#chat-options')||compose;let row=$('.studio-ai-options');if(!row){row=document.createElement('div');row.className='studio-ai-options';target.append(row);}for(const label of labels){if(label.querySelector('#ai-consent'))label.lastChild.textContent=' Dùng AI đã kết nối';else label.lastChild.textContent=' Tự cập nhật đáp án';row.append(label);}}const input=$('#chat-input');if(input){input.rows=2;input.setAttribute('placeholder','Nhập yêu cầu tạo, sửa đề hoặc kéo thả tệp nguồn vào đây…');input.setAttribute('aria-label','Nhắn với trợ lý');}}
export function latexToReadableUnicode(latex){
 let s=String(latex||'').trim();
 for(let i=0;i<4;i++){
  const prev=s;
  s=s
   .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g,(_,num,den)=>{
    const n=/^[a-zA-Z0-9]+$/.test(num.trim())?num.trim():`(${num.trim()})`;
    const d=/^[a-zA-Z0-9]+$/.test(den.trim())?den.trim():`(${den.trim()})`;
    return `${n}/${d}`;
   })
   .replace(/\\sqrt\[([^\]]+)\]\{([^{}]+)\}/g,'$1√($2)')
   .replace(/\\sqrt\{([^{}]+)\}/g,'√($1)');
  if(s===prev)break;
 }
 return s
  .replace(/\\mathbb\{([A-Za-z])\}/g,(_,ch)=>({R:'ℝ',N:'ℕ',Z:'ℤ',Q:'ℚ',C:'ℂ'}[ch]||ch))
  .replace(/\\triangle\s*/g,'△')
  .replace(/\\pi\b/g,'π')
  .replace(/\\(?:geq|ge)\b/g,'≥')
  .replace(/\\(?:leq|le)\b/g,'≤')
  .replace(/\\(?:neq|ne)\b/g,'≠')
  .replace(/\\infty\b/g,'∞')
  .replace(/\\(?:times|cdot)\b/g,'·')
  .replace(/\\pm\b/g,'±')
  .replace(/\\perp\b/g,'⊥')
  .replace(/\\angle\b/g,'∠')
  .replace(/\\in\b/g,'∈')
  .replace(/\^\\circ|\\circ\b/g,'°')
  .replace(/[{}$\\]/g,'')
  .replace(/\s+/g,' ')
  .trim();
}
export function formatOutlineTitleUnicode(title){
 return mathParts(String(title||'')).map(p=>{
  if(!p.latex)return p.text;
  const readable=latexToReadableUnicode(p.latex);
  return readable.length>28?readable.slice(0,27)+'…':readable;
 }).join('');
}
function decorateOutline(){document.querySelectorAll('.outline-item .outline-title').forEach(n=>{if(n.dataset.mathRendered)return;n.dataset.mathRendered='true';const title=n.textContent.split('\n')[0];n.textContent=formatOutlineTitleUnicode(title);});const root=$('.paper-scroll');if(root&&!root.dataset.outlineScroll){root.dataset.outlineScroll='true';let queued=false;root.addEventListener('scroll',()=>{if(!queued){queued=true;requestAnimationFrame(()=>{queued=false;paintOutline();});}},{passive:true});}paintOutline();}
function paintOutline(){const root=$('.paper-scroll');if(!root)return;const limit=root.getBoundingClientRect().top+90,nodes=[...document.querySelectorAll('.paper .question,.paper #marking-guide,.paper #marking-general,.paper #marking-table')];let current=null;for(const node of nodes)if(node.getClientRects().length&&node.getBoundingClientRect().top<=limit)current=node;document.querySelectorAll('.outline-item,.outline-section').forEach(n=>{const match=current?(current.dataset.q?n.dataset.id===current.dataset.q:n.dataset.action==='scroll-marking'&&(n.dataset.target||'marking-guide')===current.id):n.dataset.action==='scroll-heading';n.classList.toggle('in-view',match);if(match)n.setAttribute('aria-current','location');else n.removeAttribute('aria-current');});}

export function mountStudio(context){c=context;document.body.classList.add('studio');prepareHeading();prepareSections();inlineAnswers();compactCompose();const footer=$('.main-footer');if(footer&&!$('.studio-page-controls'))footer.insertAdjacentHTML('beforeend',`<div class="studio-page-controls"><span class="studio-page-status">Trang 1</span><span class="footer-sep" aria-hidden="true">·</span><span class="studio-q-count"></span><span class="footer-sep" aria-hidden="true">·</span><span class="studio-word-count"></span></div>`);const ribbon=$('.document-bar');if(ribbon&&!$('.page-navigation'))ribbon.insertAdjacentHTML('beforeend',`<div class="page-navigation"><label for="page-jump">Trang</label><input id="page-jump" type="number" min="1" value="1" aria-label="Đến trang"><span id="page-total"></span></div>`);mountPages(c);mountDesign(c);mountUsability(c);decorateOutline();paintWords();if(document.querySelector('.paper.ai-writing'))document.querySelectorAll('.paper input,.paper textarea').forEach(n=>n.disabled=true);
if(!initialized){initialized=true;document.addEventListener('editor-content-changed',()=>{paintWords();decorateOutline();});document.addEventListener('change',handleChange);document.addEventListener('change',ev=>{if(ev.target.id==='doc-font'&&selectedTypography('fontFamily',ev.target.value)||ev.target.id==='doc-fontsize'&&selectedTypography('fontSize',Number(ev.target.value)))ev.stopImmediatePropagation();},true);document.addEventListener('input',handleInput);document.addEventListener('pointerdown',dragPoint);document.addEventListener('keydown',ev=>{if((ev.ctrlKey||ev.metaKey)&&ev.key==='Enter'&&ev.target.id==='chat-input'){ev.preventDefault();$('#chat-form').requestSubmit();}if((ev.ctrlKey||ev.metaKey)&&['f','h'].includes(ev.key.toLowerCase())&&!$('#dialog').open&&!$('.composer-shell')){ev.preventDefault();showFind(ev.key.toLowerCase()==='h');}if(ev.key==='Escape'&&$('.studio-find')){ev.preventDefault();closeFind(true);}});}}
function paintWords(){const e=c.exam(),qEl=$('.studio-q-count');if(qEl)qEl.textContent=e.questions.length+' câu';const n=$('.studio-word-count');if(n)n.textContent=e.questions.reduce((s,q)=>s+q.stem.trim().split(/\s+/).filter(Boolean).length,0).toLocaleString('vi-VN')+' từ';}
function handleInput(ev){if(ev.target.matches('.paper .title-input')){ev.target.style.height='auto';ev.target.style.height=ev.target.scrollHeight+'px';}if(ev.target.id==='chat-input'){ev.target.style.height='auto';ev.target.style.height=Math.min(150,Math.max(52,ev.target.scrollHeight))+'px';}if(ev.target.closest('.studio-find'))findMatches();if(ev.target.matches('[data-point-axis]')&&figureState){const {pointAxis:axis,pointName:name}=ev.target.dataset;const next=clone(figureState);next.points[name][axis]=Number(ev.target.value);previewFigure(next);}if(ev.target.id==='figure-spec'){try{const next=JSON.parse(ev.target.value);solveFigure(next);figureState=next;decoratePoints();}catch{}}if(ev.target.id==='figure-caption'&&figureState){figureState.caption=ev.target.value;syncFigure();}}
function handleChange(ev){if(ev.target.id==='page-jump')jumpPage(ev.target.value);if(ev.target.matches('[data-rubric-point]')){const q=c.qget(ev.target.dataset.rubricPoint),index=Number(ev.target.dataset.index),value=Number(ev.target.value),old=q.rubric[index].points,other=q.rubric.reduce((n,r,i)=>n+(i===index?0:r.points),0);if(value<=0||Math.abs(value*20-Math.round(value*20))>0.001||Math.abs(other+value-q.points)>.001){ev.target.value=old;c.toast('Tổng các bước phải bằng '+q.points+' điểm. Dùng “Điều chỉnh barem” để phân bổ lại.');return;}c.change('Sửa điểm một bước chấm',()=>{q.rubric[index].points=value;touch(q);},{renderPage:false});}if(ev.target.matches('[data-figure-object]')&&figureState){const value=ev.target.dataset.figureObject;if(ev.target.checked&&!figureState.objects.some(o=>JSON.stringify(o)===value))figureState.objects.push(JSON.parse(value));if(!ev.target.checked)figureState.objects=figureState.objects.filter(o=>JSON.stringify(o)!==value);syncFigure();}}
function menuItem(action,label,icon='',extra=''){return b(action,`<span class="studio-menu-icon">${icon}</span><span>${label}</span>${extra}`,`class="menu-item" role="menuitem"`);}
function insertMenu(anchor){showDropdown(anchor,`<div class="menu-list studio-insert-menu" role="menu">${menuItem('formula','Công thức toán','∑')}${menuItem('chemistry','Công thức hoá học','⚗')}<hr>${menuItem('studio-table','Bảng','▦','<span class="menu-chevron">›</span>')}${menuItem('insert-image','Hình','▧')}${menuItem('studio-sketch','Vẽ phác','✎')}${menuItem('geometry','Hình minh họa SVG','◇','<span class="menu-chevron">›</span>')}<hr>${menuItem('metadata','Đầu đề','▤')}${menuItem('studio-question','Câu hỏi','▱','<span class="menu-chevron">›</span>')}${menuItem('studio-paragraph','Nội dung','≡')}${menuItem('studio-layout','Bố cục','▥')}<hr>${menuItem('studio-link','Liên kết','↗')}${menuItem('page-break','Ngắt trang','▯','<kbd>Ctrl+↵</kbd>')}${menuItem('studio-rule','Đường kẻ ngang','—')}</div>`,'document-menu');}
function tablePicker(anchor){showDropdown(anchor,`<div class="table-picker"><strong id="table-size-label">Chèn bảng</strong><div class="table-grid">${Array.from({length:64},(_,i)=>b('studio-table-size','',`data-rows="${Math.floor(i/8)+1}" data-cols="${i%8+1}" aria-label="Bảng ${Math.floor(i/8)+1} hàng ${i%8+1} cột"`)).join('')}</div><small>Chọn số hàng và cột</small></div>`,'table-picker-panel');$('.table-grid').addEventListener('pointerover',ev=>{const cell=ev.target.closest('button');if(!cell)return;$('#table-size-label').textContent=cell.dataset.rows+' × '+cell.dataset.cols;document.querySelectorAll('.table-grid button').forEach(n=>n.classList.toggle('hover-cell',Number(n.dataset.rows)<=Number(cell.dataset.rows)&&Number(n.dataset.cols)<=Number(cell.dataset.cols)));});}
let findIndex=0,lastFindMatches=[],findReturnFocus=null;
export function collectFindMatches(exam,query,sensitive=false){
 if(!query||!exam?.questions?.length)return [];
 const needle=sensitive?query:query.toLocaleLowerCase('vi-VN'),matches=[];
 const scan=(q,qIndex,field,subIndex,text,editable=true)=>{
  if(!text)return;
  const hay=sensitive?text:text.toLocaleLowerCase('vi-VN');
  let pos=0;
  while((pos=hay.indexOf(needle,pos))!==-1){
   matches.push({qId:q.id,qIndex,field,subIndex,start:pos,end:pos+needle.length,editable,snippet:text.slice(Math.max(0,pos-20),pos+needle.length+35)});
   pos+=Math.max(1,needle.length);
  }
 };
 for(const [i,q]of exam.questions.entries()){
  scan(q,i,'stem',null,q.stem,true);
  (q.options||[]).forEach((o,j)=>scan(q,i,'option',j,o,true));
  scan(q,i,'explanation',null,q.explanation,true);
  (q.rubric||[]).forEach((r,k)=>scan(q,i,'rubric',k,r.text,true));
  (q.tables||[]).forEach((t,ti)=>(t?.rows||[]).forEach((row,ri)=>(row||[]).forEach((cell,ci)=>{
   const text=typeof cell==='string'?cell:(cell&&typeof cell==='object'&&cell.text!=null?String(cell.text):null);
   if(text)scan(q,i,'table',`${ti}:${ri}:${ci}`,text,true);
  })));
  (q.formulas||[]).forEach((f,k)=>scan(q,i,'formula',k,f.latex,false));
 }
 return matches;
}
function preserveRich(doc,before,after){
 if(!doc)return null;
 try{return reconcileEditorRich(doc,before,after);}catch{return null;}
}
function replaceStringPreservingRich(text,doc,pattern,replacement){
 if(!pattern.global)return {text,doc};
 const hits=[...text.matchAll(pattern)];
 if(!hits.length)return {text,doc};
 let cur=text,curDoc=doc;
 for(let i=hits.length-1;i>=0;i--){
  const m=hits[i],next=cur.slice(0,m.index)+replacement+cur.slice(m.index+m[0].length);
  curDoc=preserveRich(curDoc,cur,next);
  cur=next;
 }
 return {text:cur,doc:curDoc};
}
export function applySingleFindReplacement(exam,match,replacement){
 if(!match?.editable)return false;
 const q=exam.questions.find(x=>x.id===match.qId);
 if(!q)return false;
 const splice=s=>s.slice(0,match.start)+replacement+s.slice(match.end);
 if(match.field==='stem'){const old=q.stem,next=splice(old);q.stem=next;q.richDoc=preserveRich(q.richDoc,old,next);q.runs=null;}
 else if(match.field==='explanation'){const old=q.explanation,next=splice(old);q.explanation=next;q.explanationDoc=preserveRich(q.explanationDoc,old,next);}
 else if(match.field==='option'){const old=q.options[match.subIndex],next=splice(old);q.options[match.subIndex]=next;if(Array.isArray(q.optionDocs))q.optionDocs[match.subIndex]=preserveRich(q.optionDocs[match.subIndex],old,next);}
 else if(match.field==='rubric'){const old=q.rubric[match.subIndex].text,next=splice(old);q.rubric[match.subIndex].text=next;q.rubric[match.subIndex].richDoc=preserveRich(q.rubric[match.subIndex].richDoc,old,next);}
 else if(match.field==='table'&&typeof match.subIndex==='string'){
  const [ti,ri,ci]=match.subIndex.split(':').map(Number);
  const row=q.tables?.[ti]?.rows?.[ri];
  if(!row||ci<0||ci>=row.length)return false;
  const cell=row[ci];
  if(typeof cell==='string')row[ci]=splice(cell);
  else if(cell&&typeof cell==='object'&&cell.text!=null)cell.text=splice(String(cell.text));
  else return false;
 }
 else return false;
 touch(q);check(exam,q);
 return true;
}
function closeFind(restoreFocus=true){
 const panel=$('.studio-find');
 if(!panel)return;
 panel.remove();
 if(restoreFocus&&findReturnFocus?.isConnected)findReturnFocus.focus?.();
 findReturnFocus=null;
}
function showFind(replace=false){try{closeFloating?.();}catch{}document.querySelectorAll('.menubar .open, .menubar-menu.open, .menu-pop.open, .menu-pop, .open').forEach(el=>{el.classList?.remove('open');if(el.classList?.contains('menu-pop'))el.remove?.();});if(!$('.studio-find'))findReturnFocus=document.activeElement instanceof HTMLElement?document.activeElement:null;const prevQuery=$('#find-query')?.value||'';$('.studio-find')?.remove();findIndex=0;lastFindMatches=[];const node=document.createElement('div');node.className='studio-find';node.innerHTML=`<div class="find-top"><input id="find-query" placeholder="Tìm chữ, bảng hoặc công thức LaTeX…" aria-label="Tìm trong tài liệu" value="${esc(prevQuery)}"><span id="find-count">0 / 0</span>${b('studio-find-prev','↑','title="Kết quả trước (Shift+Enter)" aria-label="Kết quả trước" disabled')}${b('studio-find-next','↓','title="Kết quả sau (Enter)" aria-label="Kết quả sau" disabled')}${b('studio-find-close','×','aria-label="Đóng tìm kiếm"')}</div><div class="find-replace-row"><input id="replace-query" placeholder="Thay thế bằng…" aria-label="Nội dung thay thế">${b('studio-replace-one','Thay','disabled')}${b('studio-replace-all','Thay tất cả','disabled')}</div><label><input id="find-case" type="checkbox"> Phân biệt hoa thường</label><div id="find-results"></div>`;$('.main').append(node);if(!replace)node.querySelector('.find-replace-row').hidden=true;const qInput=$('#find-query');qInput.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();stepFind(ev.shiftKey?-1:1);}if(ev.key==='Escape'){ev.preventDefault();closeFind(true);}});node.addEventListener('keydown',ev=>{if(ev.key==='Escape'){ev.preventDefault();closeFind(true);}});findMatches();qInput.focus();}
function stepFind(delta=1){if(!lastFindMatches.length)return;findIndex=(findIndex+delta+lastFindMatches.length)%lastFindMatches.length;renderFindMatches();}
function renderFindMatches(){const countEl=$('#find-count'),resultsEl=$('#find-results');if(!countEl||!resultsEl)return;const total=lastFindMatches.length,qVal=$('#find-query')?.value||'';countEl.textContent=total?`${findIndex+1} / ${total}`:(qVal?'Không tìm thấy (0 / 0)':'0 / 0');document.querySelectorAll('[data-action="studio-replace-one"],[data-action="studio-replace-all"],[data-action="studio-find-prev"],[data-action="studio-find-next"]').forEach(btn=>{btn.disabled=!total;});resultsEl.innerHTML=lastFindMatches.map((m,idx)=>{const q=c.exam().questions[m.qIndex];return b('studio-find-result',`<b>${q?.type==='essay'?'Bài':'Câu'} ${m.qIndex+1}</b><span>${esc(m.snippet)}</span><small>${m.field==='formula'?'LaTeX':m.field==='table'?'Bảng':idx+1}</small>`,`class="${idx===findIndex?'find-hit active':'find-hit'}" data-id="${m.qId}" data-match-idx="${idx}"`);}).join('');const cur=lastFindMatches[findIndex];if(cur){c.setSelected(cur.qId);document.getElementById('q-'+cur.qId)?.scrollIntoView({block:'center',behavior:'smooth'});}}
function captureFindState(){const panel=$('.studio-find'),rRow=panel?.querySelector('.find-replace-row');return {query:$('#find-query')?.value||'',replacement:$('#replace-query')?.value||'',sensitive:Boolean($('#find-case')?.checked),showReplace:Boolean(rRow&&!rRow.hidden),returnFocus:findReturnFocus};}
function restoreFindAfterChange(state,nextIndex=0){if(!$('.studio-find')){showFind(state.showReplace);findReturnFocus=state.returnFocus;}const qEl=$('#find-query'),rEl=$('#replace-query'),cEl=$('#find-case');if(qEl)qEl.value=state.query;if(rEl)rEl.value=state.replacement;if(cEl)cEl.checked=state.sensitive;findIndex=nextIndex;findMatches();}
function findMatches(){const query=$('#find-query')?.value||'',sensitive=$('#find-case')?.checked;lastFindMatches=collectFindMatches(c.exam(),query,sensitive);if(findIndex>=lastFindMatches.length)findIndex=0;renderFindMatches();return {query,sensitive,count:lastFindMatches.length};}
function replaceOne(){flushEditor();if(!lastFindMatches.length)return;const idx=findIndex,match=lastFindMatches[idx];if(!match.editable){c.toast('Công thức tách riêng cần sửa trực tiếp trong khung công thức.');return;}const state=captureFindState();c.change('Thay 1 vị trí trong tài liệu',e=>{applySingleFindReplacement(e,match,state.replacement);});restoreFindAfterChange(state,idx);c.toast('Đã thay 1 vị trí. Có thể hoàn tác.');}
function replaceAll(){flushEditor();const state=captureFindState(),{query,sensitive,count}=findMatches(),replacement=state.replacement;if(!query||!count)return;const pattern=new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),sensitive?'gu':'giu');c.change('Thay '+count+' vị trí trong tài liệu',e=>{for(const q of e.questions){let changed=false;for(const field of ['stem','explanation']){const docKey=field==='stem'?'richDoc':field+'Doc';const res=replaceStringPreservingRich(q[field],q[docKey],pattern,replacement);if(res.text!==q[field]){q[field]=res.text;q[docKey]=res.doc;if(field==='stem')q.runs=null;changed=true;}}q.options=q.options.map((t,oi)=>{const res=replaceStringPreservingRich(t,Array.isArray(q.optionDocs)?q.optionDocs[oi]:null,pattern,replacement);if(res.text!==t){changed=true;if(Array.isArray(q.optionDocs))q.optionDocs[oi]=res.doc;}return res.text;});for(const r of q.rubric||[]){const res=replaceStringPreservingRich(r.text,r.richDoc,pattern,replacement);if(res.text!==r.text){r.text=res.text;r.richDoc=res.doc;changed=true;}}for(const t of q.tables||[]){for(const row of t?.rows||[]){for(let ci=0;ci<(row?.length||0);ci++){const cell=row[ci];if(typeof cell==='string'){const next=cell.replace(pattern,()=>replacement);if(next!==cell){row[ci]=next;changed=true;}}else if(cell&&typeof cell==='object'&&cell.text!=null){const oldT=String(cell.text),next=oldT.replace(pattern,()=>replacement);if(next!==oldT){cell.text=next;changed=true;}}}}}if(changed){touch(q);check(e,q);}}});restoreFindAfterChange(state,0);c.toast('Đã thay '+count+' vị trí. Có thể hoàn tác cả lần thay.');}
function showLayout(){const e=c.exam();c.modal('Thiết lập trang',`<form id="studio-layout-form"><div class="layout-preview"><span>A4</span><small>210 × 297 mm</small></div><div class="grid2"><div><label>Phông chữ mặc định</label><select name="font"><option>Times New Roman</option><option>Arial</option><option>Calibri</option></select></div><div><label>Cỡ chữ (pt)</label><input name="size" type="number" min="10" max="22" value="${e.layout?.fontSize||15}"></div></div><label>Lề trang (px trên bản soạn)</label><input name="margin" type="range" min="45" max="110" value="${e.layout?.pageMargin||78}"><p>Giấy A4, các trang và bảng chấm tự sắp theo nội dung. Word/PDF có phân trang riêng khi xuất.</p><div class="modal-foot"><button class="primary" type="submit">Áp dụng</button></div></form>`);$('#studio-layout-form select').value=e.layout?.font||'Times New Roman';}
function showQuestion(anchor){anchor?.scrollIntoView?.({block:'nearest'});showDropdown(anchor,`<div class="menu-list">${[['mcq','Trắc nghiệm · 4 lựa chọn'],['truefalse','Đúng–sai · 4 nhận định'],['short','Trả lời ngắn'],['essay','Tự luận · đáp án và barem']].map(([type,label])=>b('studio-add-question',label,`class="menu-item" data-type="${type}"`)).join('')}</div>`,'document-menu studio-question-menu');}
function addQuestion(type){c.change('Thêm câu hỏi '+type,e=>{e.questions.push({id:uid(),v:1,type,stem:'',options:['mcq','truefalse'].includes(type)?['','','','']:[],answer:0,answerKnown:false,answerText:'',truthValues:[false,false,false,false],explanation:'',rubric:[],points:1,topic:'Nội dung mới',level:1,source:null});});const q=c.exam().questions.at(-1);c.setSelected(q.id);document.getElementById('q-'+q.id)?.scrollIntoView({block:'center'});document.querySelector('[data-rich-id="'+q.id+'"] .tiptap')?.focus();}
export function figureEditor(q){figureState=clone(q.figure||triangleFigure());const solved=solveFigure(figureState);for(const name of Object.keys(figureState.points))figureState.points[name]=solved.points[name];c.modal('Sửa hình minh họa',`<form id="figure-form" class="visual-figure-form" data-id="${q.id}" data-version="${q.v}"><div class="visual-figure-layout"><div><div class="figure-preview-toolbar"><span>Kéo các điểm màu xanh để điều chỉnh</span>${b('studio-reset-figure','Đặt lại')}</div><div id="figure-preview">${renderFigure(figureState)}</div><p id="figure-error" role="alert"></p></div><aside><h3>Điểm tự do</h3>${Object.entries(figureState.points).map(([name,p])=>`<div class="point-controls"><b>${esc(name)}</b><label>x <input type="number" step="any" value="${p.x}" data-point-name="${name}" data-point-axis="x" aria-label="Tọa độ x điểm ${name}"></label><label>y <input type="number" step="any" value="${p.y}" data-point-name="${name}" data-point-axis="y" aria-label="Tọa độ y điểm ${name}"></label></div>`).join('')}<h3>Hiển thị</h3>${['circle(O,A)',{type:'segment',points:['A','D'],dashed:true}].filter(o=>typeof o!=='string'||solved.points.O).map(o=>`<label class="source-choice"><input type="checkbox" data-figure-object='${JSON.stringify(o)}' ${figureState.objects.some(v=>JSON.stringify(v)===JSON.stringify(o))?'checked':''}> ${typeof o==='string'?'Đường tròn ngoại tiếp':'Đường cao AD'}</label>`).join('')}<label>Chú thích</label><input id="figure-caption" value="${esc(figureState.caption||'')}"><label>Độ rộng hình (px)</label><input name="width" type="number" min="180" max="700" value="${figureState.width||480}"></aside></div><details class="figure-advanced"><summary>Mô tả hình và ràng buộc</summary><textarea id="figure-spec" name="spec" rows="9" spellcheck="false">${esc(JSON.stringify(figureState,null,2))}</textarea></details><div class="modal-foot"><span>Các điểm phụ thuộc được tính lại theo ràng buộc.</span><button class="primary" type="submit">Lưu hình</button></div></form>`);decoratePoints();}
function previewFigure(next){try{solveFigure(next);figureState=next;syncFigure();$('#figure-error').textContent='';}catch(e){$('#figure-error').textContent=e.message;}}
function syncFigure(){if(!figureState)return;$('#figure-spec').value=JSON.stringify(figureState,null,2);$('#figure-preview').innerHTML=renderFigure(figureState);decoratePoints();for(const n of document.querySelectorAll('[data-point-axis]'))if(n!==document.activeElement)n.value=Number(figureState.points[n.dataset.pointName][n.dataset.pointAxis].toFixed(2));}
function decoratePoints(){const svg=$('#figure-preview svg');if(!svg||!figureState)return;const names=Object.keys(solveFigure(figureState).points),circles=[...svg.querySelectorAll('circle')].filter(n=>Number(n.getAttribute('r'))<3);circles.forEach((n,i)=>{const name=names[i];if(name in figureState.points){n.dataset.dragPoint=name;n.setAttribute('r','5');n.setAttribute('fill','#4b86c4');n.style.cursor='grab';}});}
function dragPoint(ev){const point=ev.target.closest('[data-drag-point]');if(!point||!figureState)return;ev.preventDefault();const svg=point.ownerSVGElement,name=point.dataset.dragPoint,p=figureState.points[name],rect=svg.getBoundingClientRect(),view=svg.viewBox.baseVal;const start={x:ev.clientX,y:ev.clientY},points=solveFigure(figureState).points;const coords=[...svg.querySelectorAll('circle')].filter(n=>Number(n.getAttribute('r'))<6);const names=Object.keys(points);const p2=names.find(n=>n!==name&&Math.abs(points[n].x-p.x)>.1);let scale=40;if(p2){const a=coords[names.indexOf(name)],b=coords[names.indexOf(p2)];if(a&&b)scale=Math.abs((Number(a.getAttribute('cx'))-Number(b.getAttribute('cx')))/(p.x-points[p2].x));}const startSpec=clone(figureState),worldPerPixel=view.width/(rect.width*scale);const move=e=>{const next=clone(startSpec);next.points[name]={x:p.x+(e.clientX-start.x)*worldPerPixel,y:p.y-(e.clientY-start.y)*worldPerPixel};previewFigure(next);};const end=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);};window.addEventListener('pointermove',move);window.addEventListener('pointerup',end,{once:true});}
export async function handleStudioAction(action,node){if(handleDesignAction(action,node))return true;if($('.paper.ai-writing')&&(['geometry','edit-figure','quick-figure'].includes(action)||action.startsWith('studio-')&&!['studio-find','studio-find-close','studio-find-result'].includes(action))){c.toast('Chờ AI viết xong hoặc bấm Dừng trước khi sửa.');return true;}switch(action){case 'menu':if(node.dataset.menu==='insert'){insertMenu(node);return true;}return false;case 'studio-table':tablePicker(node);return true;case 'studio-table-size':format('insertTable',{rows:Number(node.dataset.rows),cols:Number(node.dataset.cols)});closeFloating();schedulePages();return true;case 'studio-paragraph':format('paragraph');closeFloating();return true;case 'studio-rule':format('horizontalRule');closeFloating();schedulePages();return true;case 'studio-link':c.modal('Chèn liên kết',`<form id="studio-link-form"><label>Địa chỉ liên kết</label><input name="url" type="url" placeholder="https://…" required><div class="modal-foot"><button type="submit" class="primary">Chèn liên kết</button></div></form>`);return true;case 'studio-question':showQuestion(node);return true;case 'studio-add-question':closeFloating();addQuestion(node.dataset.type);return true;case 'studio-find':showFind();return true;case 'studio-replace':showFind(true);return true;case 'studio-find-prev':stepFind(-1);return true;case 'studio-find-next':stepFind(1);return true;case 'studio-find-close':closeFind(true);return true;case 'studio-find-result':if(node.dataset.matchIdx!=null){findIndex=Number(node.dataset.matchIdx);renderFindMatches();}else{c.setSelected(node.dataset.id);document.getElementById('q-'+node.dataset.id)?.scrollIntoView({block:'center',behavior:'smooth'});}return true;case 'studio-replace-one':replaceOne();return true;case 'studio-replace-all':replaceAll();return true;case 'studio-layout':showLayout();return true;case 'studio-prompt':{const input=$('#chat-input');input.value=node.dataset.prompt;input.dispatchEvent(new Event('input',{bubbles:true}));$('#chat-form').requestSubmit();return true;}case 'geometry':case 'edit-figure':case 'quick-figure':{flushEditor();const q=c.qget(node.dataset.id||c.getSelected());if(q){if(node.dataset.id&&c.getSelected()!==q.id)c.setSelected(q.id);figureEditor(q);}else c.toast('Thêm hoặc chọn một bài để chèn hình.');return true;}case 'studio-sketch':{closeFloating();if(flushEditor())openSketchBoard(c);return true;}case 'studio-reset-figure':figureState=triangleFigure();const solved=solveFigure(figureState);for(const name of Object.keys(figureState.points))figureState.points[name]=solved.points[name];syncFigure();return true;default:return false;}}
export function handleStudioSubmit(form){if(form.id==='studio-layout-form'){const fd=new FormData(form);c.change('Thiết lập trang A4',e=>e.layout={...e.layout,font:fd.get('font'),fontSize:Number(fd.get('size')),pageMargin:Number(fd.get('margin'))});$('#dialog').close();return true;}if(form.id==='studio-link-form'){const url=new FormData(form).get('url');if(!/^https?:\/\//i.test(url))throw Error('Dùng địa chỉ bắt đầu bằng https:// hoặc http://.');format('link',url);$('#dialog').close();return true;}return false;}

export function refreshStudio(){if(!c)return;decorateOutline();paintWords();updatePageStatus();refreshDesign();refreshUsability();document.dispatchEvent(new CustomEvent('studio-refreshed'));}

function prepareHeading(){const old=document.querySelector('.paper .title-input');if(old?.tagName==='INPUT'){const title=document.createElement('textarea');title.className=old.className;title.dataset.examField='title';title.setAttribute('aria-label','Tên đề');title.rows=2;title.value=old.value;old.replaceWith(title);title.style.height='auto';title.style.height=title.scrollHeight+'px';}}
function prepareSections(){if(document.querySelector('.paper-section[data-section-part]'))return;const questions=c.exam().questions,types=[...new Set(questions.map(q=>q.type||'mcq'))],head=document.querySelector('.paper-section');if(!questions.length)return;if(types.length===1&&types[0]==='essay'){head?.remove();return;}const names={mcq:'TRẮC NGHIỆM NHIỀU LỰA CHỌN',truefalse:'TRẮC NGHIỆM ĐÚNG – SAI',short:'TRẢ LỜI NGẮN',essay:'TỰ LUẬN'},roman=['I','II','III','IV','V','VI','VII','VIII'];let previous=null,part=0;questions.forEach((q,index)=>{const type=q.type||'mcq';if(type===previous)return;previous=type;const group=[];for(let j=index;j<questions.length&&(questions[j].type||'mcq')===type;j++)group.push(questions[j]);const points=group.reduce((n,q)=>n+(q.points||0),0),title='PHẦN '+(roman[part]||part+1)+'. '+names[type]+(points?' ('+points.toLocaleString('vi-VN',{minimumFractionDigits:1})+' điểm)':'');if(part===0&&head){head.textContent=title;head.dataset.sectionPart=String(part);}else{const section=document.createElement('h2');section.className='paper-section';section.dataset.sectionPart=String(part);section.textContent=title;document.getElementById('q-'+q.id)?.before(section);}part++;});}
