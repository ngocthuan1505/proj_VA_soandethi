import {format,formattingState,applyParagraphLayout,insertPageBreak} from '../editor.js';
import {esc} from '../core.js';
import {closeFloating} from '../reference.js';
let context,popup,initialized=false;
function sizeDocumentTitle(){const input=document.querySelector('input.header-title');if(!input)return;const canvas=document.createElement('canvas'),measure=canvas.getContext('2d');if(!measure)return;measure.font=getComputedStyle(input).font;input.style.width=Math.ceil(measure.measureText(input.value||input.placeholder||'Đề thi mới').width+22)+'px';}
const colors=['#000000','#434343','#666666','#999999','#cccccc','#ffffff','#990000','#ff0000','#ff9900','#ffff00','#00ff00','#00ffff','#0000ff','#9900ff','#ff00ff','#f4cccc','#fce5cd','#fff2cc','#d9ead3','#d0e0e3','#cfe2f3','#d9d2e9','#ead1dc','#0b5394'];
const paths={align:'M4 5h16M4 10h11M4 15h16M4 20h11',spacing:'M8 4v16M5 7l3-3 3 3M5 17l3 3 3-3M15 5h6M15 12h6M15 19h6',bullets:'M8 5h13M8 12h13M8 19h13M3 5h.1M3 12h.1M3 19h.1',numbers:'M9 5h12M9 12h12M9 19h12M3 3v5M2 3h1M2 12q3-3 3 0l-3 4h3',outdent:'M10 5h11M10 12h11M10 19h11M6 8l-4 4 4 4',indent:'M10 5h11M10 12h11M10 19h11M2 8l4 4-4 4',image:'M3 4h18v16H3zM3 16l5-5 4 4 3-3 6 6M8 8h.1',table:'M3 4h18v16H3zM3 10h18M10 4v16',link:'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71',paragraph:'M4 5h16M4 12h16M4 19h16M8 2v6M16 9v6M8 16v6',highlight:'M5 15l7-11 6 4-7 11H5zM3 21h16',pageBreak:'M5 3h14v5M5 16v5h14v-5M3 12h5m3 0h2m3 0h5M9 17l3-3 3 3'};
const icon=name=>`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"/></svg>`;
const button=(name,label,body,extra='')=>`<button type="button" data-toolbar="${name}" title="${label}" aria-label="${label}" ${extra}>${body}</button>`;
const divider='<span class="toolbar-divider" aria-hidden="true"></span>';
const chevron='<svg class="toolbar-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
function closePopup(){popup?.remove();popup=null;document.querySelectorAll('[data-toolbar][aria-expanded=true]').forEach(n=>n.setAttribute('aria-expanded','false'));}
function openPopup(anchor,label,html,cls=''){
 closePopup();closeFloating();popup=document.createElement('section');popup.className='document-toolbar-popup '+cls;popup.setAttribute('aria-label',label);popup.innerHTML=html;document.body.append(popup);anchor.setAttribute('aria-expanded','true');
 const r=anchor.getBoundingClientRect();popup.style.left=Math.max(8,Math.min(r.left,innerWidth-popup.offsetWidth-12))+'px';popup.style.top=Math.max(8,Math.min(r.bottom+9,innerHeight-popup.offsetHeight-12))+'px';
 return popup;
}
function headingMenu(anchor){
 const state=formattingState(),current=state?.heading||0;
 const choices=[['normal','Văn bản thường',0],['title','Tiêu đề',1],['subtitle','Phụ đề',0],...[1,2,3,4,5,6].map(n=>['h'+n,'Tiêu đề '+n,n])];
 const panel=openPopup(anchor,'Kiểu đoạn văn',choices.map(([key,label,level])=>button('style-choice',label,`<span class="style-check">${key==='normal'&&current===0?'✓':''}</span><span class="style-${key}">${label}</span><span class="style-chevron">›</span>`,`data-style="${key}" data-level="${level}"`)).join(''),'style-menu');
 panel.addEventListener('click',event=>{const target=event.target.closest('[data-style]');if(!target)return;const style=target.dataset.style;
  format(style==='normal'||style==='subtitle'?'normal':'heading',Number(target.dataset.level));
  if(style==='title')format('fontSize',28);if(style==='subtitle'){format('italic');format('fontSize',18);}
  closePopup();refreshDocumentToolbar();
 });
}
function colorMenu(anchor,highlight){
 const name=highlight?'Màu nền chữ':'Màu chữ',command=highlight?'hiliteColor':'foreColor';
 const panel=openPopup(anchor,name,`<h3>${name}</h3><div class="toolbar-color-grid">${colors.map(color=>button('swatch',color,'',`data-color="${color}" style="background:${color}"`)).join('')}</div><label class="toolbar-custom-color">Màu tùy chỉnh<input type="color" value="${highlight?'#ffff00':'#000000'}" aria-label="${name} tùy chỉnh"></label>${button('remove-color',highlight?'Bỏ màu nền':'Màu chữ mặc định',highlight?'Bỏ màu nền':'Màu chữ mặc định')}`);
 const apply=value=>{format(command,value);anchor.style.setProperty('--swatch',value);closePopup();};
 panel.addEventListener('click',event=>{const swatch=event.target.closest('[data-color]');if(swatch)apply(swatch.dataset.color);if(event.target.closest('[data-toolbar=remove-color]')){if(highlight)format('removeHighlight');else format('foreColor','#000000');closePopup();}});
 panel.querySelector('input').addEventListener('change',event=>apply(event.target.value));
}
function alignmentMenu(anchor){
 const panel=openPopup(anchor,'Căn lề',`<h3>Căn lề đoạn văn</h3>${[['left','Căn trái'],['center','Căn giữa'],['right','Căn phải'],['justify','Căn đều']].map(([value,label])=>button('align-choice',label,label,`data-alignment="${value}"`)).join('')}`);
 panel.addEventListener('click',event=>{const node=event.target.closest('[data-alignment]');if(node){format(node.dataset.alignment);closePopup();}});
}
function spacingMenu(anchor){
 const panel=openPopup(anchor,'Giãn dòng',`<h3>Giãn dòng</h3>${[1,1.15,1.5,1.7,2].map(value=>button('spacing-choice','Giãn dòng '+value,String(value),`data-spacing="${value}"`)).join('')}${button('paragraph-options','Tùy chỉnh đoạn văn','Tùy chỉnh đoạn văn…')}`);
 panel.addEventListener('click',event=>{const node=event.target.closest('[data-spacing]');if(node){applyParagraphLayout({lineHeight:Number(node.dataset.spacing)});closePopup();}else if(event.target.closest('[data-toolbar=paragraph-options]'))paragraphMenu(anchor);});
}
function paragraphMenu(anchor){
 const attrs=formattingState()?.attrs||{};
 const fields=[['lineHeight','Giãn dòng',1.7,0.5,5,0.05],['spaceBefore','Khoảng trước đoạn (px)',0,0,200,1],['spaceAfter','Khoảng sau đoạn (px)',0,0,200,1],['firstIndent','Thụt đầu dòng (cm)',0,-5,10,0.1],['leftIndent','Lề trái (cm)',0,0,10,0.1],['rightIndent','Lề phải (cm)',0,0,10,0.1],['borderWidth','Độ dày viền đoạn (px)',0,0,10,1]];
 const panel=openPopup(anchor,'Định dạng đoạn văn',`<form class="toolbar-paragraph-form"><header><h3>Định dạng đoạn văn</h3>${button('dismiss','Đóng','×')}</header><div class="toolbar-paragraph-grid">${fields.map(([key,label,value,min,max,step])=>`<label>${label}<input type="number" name="${key}" aria-label="${label}" min="${min}" max="${max}" step="${step}" value="${attrs[key]??value}" required></label>`).join('')}<label>Màu viền đoạn<input type="color" name="borderColor" value="${esc(attrs.borderColor||'#000000')}" aria-label="Màu viền đoạn"></label></div><label class="toolbar-background"><input type="checkbox" name="backgroundEnabled" ${attrs.paragraphBackground?'checked':''}> Tô màu nền đoạn<input type="color" name="paragraphBackground" aria-label="Màu nền đoạn" value="${esc(attrs.paragraphBackground||'#fff2cc')}"></label><footer>${button('dismiss','Hủy','Hủy')}<button type="submit" class="primary">Áp dụng</button></footer></form>`,'paragraph-menu');
 panel.querySelector('form').addEventListener('submit',event=>{event.preventDefault();const data=new FormData(event.target),value=Object.fromEntries(fields.map(([key])=>[key,Number(data.get(key))]));value.borderColor=data.get('borderColor');value.paragraphBackground=data.has('backgroundEnabled')?data.get('paragraphBackground'):null;applyParagraphLayout(value);closePopup();});
}
function imageMenu(anchor){
 const panel=openPopup(anchor,'Chèn hình',`<h3>Chèn hình vào câu đang chọn</h3>${button('image-local','Chèn ảnh từ máy',icon('image')+'Chèn ảnh từ máy')}${button('image-sketch','Vẽ hình minh họa','✎ Vẽ hình minh họa')}${button('image-geometry','Dựng hình học','◇ Dựng hình học từ tọa độ')}`);
 panel.addEventListener('click',event=>{const key=event.target.closest('[data-toolbar]')?.dataset.toolbar,action={'image-local':'insert-image','image-sketch':'studio-sketch','image-geometry':'geometry'}[key];if(action){closePopup();context.act(action);}});
}
export function refreshDocumentToolbar(){sizeDocumentTitle();const state=formattingState();if(!state)return;const root=document.querySelector('.document-toolbar');if(!root)return;root.querySelectorAll('[data-editor-format]').forEach(node=>{const key=node.dataset.editorFormat,active=key==='superscript'?state.text.script==='super':key==='subscript'?state.text.script==='sub':!!state.active[key];node.classList.toggle('is-active',active);node.setAttribute('aria-pressed',String(active));});const label=root.querySelector('.toolbar-style-label');if(label)label.textContent=state.heading?'Tiêu đề '+state.heading:'Văn bản thường';}
export function mountDocumentToolbar(c){
 context=c;document.body.classList.add('toolbar-reference');
 if(!document.querySelector('#document-toolbar-style')){const link=document.createElement('link');link.id='document-toolbar-style';link.rel='stylesheet';link.href='/assets/document-toolbar.css';document.head.append(link);}
 const bar=document.querySelector('.editing-bar'),workspace=document.querySelector('.workspace'),old=bar.querySelector('.editor-toolbar');
 const take=selector=>old.querySelector(selector),undo=take('[data-action=undo]'),redo=take('[data-action=redo]'),print=take('[data-action=export]'),zoom=take('#zoom'),font=take('#doc-font'),size=take('#doc-fontsize'),formula=take('[data-action=formula]'),chemistry=take('[data-action=chemistry]');
 old.querySelectorAll('.view-tab').forEach(tab=>tab.remove());
 const group=document.createElement('div');group.className='editor-toolbar document-toolbar';group.setAttribute('role','toolbar');group.setAttribute('aria-label','Định dạng tài liệu');
 const add=html=>group.insertAdjacentHTML('beforeend',html),fmt=(command,label,body)=>button('format',label,body,`data-action="format" data-command="${command}" data-editor-format="${command}" aria-pressed="false"`);
 group.append(undo,redo,print,zoom);add(divider+button('styles','Kiểu đoạn văn','<span class="toolbar-style-label">Văn bản thường</span>'+chevron,'class="toolbar-styles" aria-haspopup="true" aria-expanded="false"')+divider);group.append(font);
 add(button('smaller','Giảm cỡ chữ','−'));group.append(size);add(button('larger','Tăng cỡ chữ','+')+divider+fmt('bold','In đậm','<b>B</b>')+fmt('italic','In nghiêng','<i>I</i>')+fmt('underline','Gạch chân','<u>U</u>'));group.append(formula,chemistry);
 add(divider+button('text-color','Màu chữ','<span class="toolbar-color-letter">A</span>'+chevron,'class="toolbar-color" aria-haspopup="true"')+button('highlight','Màu nền chữ',icon('highlight')+chevron,'class="toolbar-color toolbar-highlight" aria-haspopup="true"')+divider+button('alignment','Căn lề',icon('align')+chevron,'aria-haspopup="true"')+button('spacing','Giãn dòng',icon('spacing')+chevron,'aria-haspopup="true"')+divider+fmt('bulletList','Danh sách dấu đầu dòng',icon('bullets'))+fmt('orderedList','Danh sách đánh số',icon('numbers'))+fmt('outdent','Giảm thụt lề',icon('outdent'))+fmt('indent','Tăng thụt lề',icon('indent'))+divider+button('link','Chèn liên kết',icon('link'))+button('table','Chèn bảng',icon('table'))+button('image','Chèn hình',icon('image'))+button('page-break','Ngắt trang (Ctrl+Enter)',icon('pageBreak'))+divider+button('paragraph','Định dạng đoạn văn',icon('paragraph'))+fmt('strike','Gạch ngang chữ','<s>S</s>')+fmt('superscript','Chỉ số trên','x²')+fmt('subscript','Chỉ số dưới','x₂'));
 add('<span class="toolbar-spacer"></span>');
 old.replaceWith(group);workspace.prepend(bar);
 group.addEventListener('mousedown',event=>{if(event.target.closest('button'))event.preventDefault();});
 group.addEventListener('click',event=>{const node=event.target.closest('[data-toolbar]');if(!node)return;event.preventDefault();event.stopPropagation();const key=node.dataset.toolbar;
  if(key==='format'){format(node.dataset.editorFormat);refreshDocumentToolbar();return;}
  if(key==='styles')headingMenu(node);if(key==='text-color'||key==='highlight')colorMenu(node,key==='highlight');if(key==='alignment')alignmentMenu(node);if(key==='spacing')spacingMenu(node);if(key==='paragraph')paragraphMenu(node);if(key==='image')imageMenu(node);
  if(key==='link')context.act('studio-link');if(key==='table')context.act('studio-table',node);if(key==='page-break')insertPageBreak();
  if(key==='smaller'||key==='larger'){size.value=Math.max(10,Math.min(22,Number(size.value)+(key==='larger'?1:-1)));size.dispatchEvent(new Event('change',{bubbles:true}));}
 });
 if(!initialized){initialized=true;document.addEventListener('input',event=>{if(event.target.matches('.header-title'))sizeDocumentTitle();});window.addEventListener('resize',sizeDocumentTitle);document.addEventListener('pointerdown',event=>{if(popup&&!popup.contains(event.target)&&!event.target.closest('[data-toolbar]'))closePopup();});document.addEventListener('keydown',event=>{if(event.key==='Escape')closePopup();});document.addEventListener('click',event=>{if(event.target.closest('.document-toolbar-popup [data-toolbar=dismiss]'))closePopup();});document.addEventListener('editor-selection-changed',refreshDocumentToolbar);}
 refreshDocumentToolbar();
 document.fonts.ready.then(sizeDocumentTitle);
 document.querySelector('#document-toolbar-style')?.addEventListener('load',sizeDocumentTitle,{once:true});
}
