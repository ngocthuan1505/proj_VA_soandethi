import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {blank,uid} from '../core.js';
import {dependency,chromePath} from '../runtime.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),base='http://127.0.0.1:4298',dir=await mkdtemp(path.join(os.tmpdir(),'toolbar-'));
const server=spawn(process.execPath,[path.join(root,'server.mjs')],{env:{...process.env,PORT:'4298',APP_DATA_DIR:dir},stdio:'ignore',windowsHide:true});let browser;
try{
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/status')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 const exam=blank('Sinh học');exam.autoUpdate=false;exam.fullExam=true;exam.questions=[{id:uid(),v:1,type:'mcq',points:10,stem:'Một tế bào thực vật có nồng độ chất tan nội bào tương đương dung dịch NaCl 0,9%. Nếu đặt tế bào này vào dung dịch khác thì chiều di chuyển của nước như thế nào?',options:['Phương án thứ nhất','Phương án thứ hai','Phương án thứ ba','Phương án thứ tư'],answer:0,explanation:'',rubric:[],topic:'Tế bào',level:0}];
 await fetch(base+'/api/kv',{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({key:'state',value:{version:1,current:exam.id,exams:[exam],prefs:[]}})});
 browser=await dependency('playwright-core').chromium.launch({headless:true,executablePath:chromePath()});const page=await browser.newPage({viewport:{width:2040,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.locator('.document-toolbar').waitFor();await page.waitForTimeout(600);
const toolbar=page.locator('.document-toolbar'),control=key=>toolbar.locator(`[data-toolbar="${key}"]`),state=async()=>{await page.waitForFunction(()=>/^Đã lưu/.test(document.querySelector('[data-save-status]')?.textContent||''));const data=await (await page.request.get(base+'/api/kv?key=state')).json();return data.value.exams[0].questions[0];};
 const box=await toolbar.boundingBox(),side=await page.locator('.sidebar').boundingBox();assert.ok(box.x<side.x&&box.y+box.height<=side.y,'Thanh công cụ phải ở trên, độc lập với mục lục');
 await page.screenshot({path:path.join(dir,'toolbar.png')});
 assert.match(await page.locator('#zoom option:checked').innerText(),/^\d+%$/);assert.ok((await page.locator('#zoom').boundingBox()).width<90);
 assert.equal(await page.locator('.ux-view-tabs,.toolbar-view-tabs,.editing-bar .view-tab,.design-canvas-label,.page-navigation').count(),0);
 assert.ok(await page.locator('.ruler').isVisible());assert.match(await page.locator('.studio-page-status').innerText(),/Trang 1/);
 for(const key of ['styles','text-color','highlight','alignment','spacing'])assert.equal(await control(key).locator('svg.toolbar-chevron path').getAttribute('d'),'m6 9 6 6 6-6');
 assert.equal(await page.locator('#zoom').evaluate(n=>getComputedStyle(n).backgroundImage),await page.locator('#doc-font').evaluate(n=>getComputedStyle(n).backgroundImage));
 for(let i=0;i<3;i++){
  await page.getByRole('button',{name:'Thu gọn cấu trúc tài liệu',exact:true}).click();await page.getByRole('button',{name:'Mở cấu trúc tài liệu',exact:true}).waitFor();assert.equal(await page.locator('.sidebar').isVisible(),false);assert.equal(await page.locator('.outline-reopen').getAttribute('aria-expanded'),'false');
  assert.notEqual(await page.locator('.outline-reopen .outline-chevron').evaluate(n=>getComputedStyle(n).transform),'none');if(i===0)await page.screenshot({path:path.join(dir,'outline-closed.png')});
  await page.getByRole('button',{name:'Mở cấu trúc tài liệu',exact:true}).focus();await page.keyboard.press('Enter');await page.getByRole('button',{name:'Thu gọn cấu trúc tài liệu',exact:true}).waitFor();assert.ok(await page.locator('.sidebar').isVisible());assert.equal(await page.locator('.outline-reopen').isVisible(),false);
 }
 // Các chế độ xem vẫn truy cập được qua menu, và render lại không làm mất nút mở.
 await page.getByRole('button',{name:'Thu gọn cấu trúc tài liệu',exact:true}).click();await page.locator('.menubar [data-menu=view]').click();await page.locator('.document-menu [data-action=view-teacher]').click();await page.getByRole('button',{name:'Mở cấu trúc tài liệu',exact:true}).waitFor();assert.equal(await page.locator('.sidebar').isVisible(),false);await page.getByRole('button',{name:'Mở cấu trúc tài liệu',exact:true}).click();
 await page.locator('.menubar [data-menu=view]').click();await page.locator('.document-menu [data-action=view-student]').click();await page.locator('.document-toolbar').waitFor();
 await page.setViewportSize({width:900,height:800});await page.getByRole('button',{name:'Mở cấu trúc tài liệu',exact:true}).waitFor();await page.getByRole('button',{name:'Mở cấu trúc tài liệu',exact:true}).click();assert.ok(await page.locator('.sidebar').isVisible());await page.getByRole('button',{name:'Thu gọn cấu trúc tài liệu',exact:true}).click();assert.equal(await page.locator('.sidebar').isVisible(),false);await page.setViewportSize({width:2040,height:1100});
 const selectText=async()=>{await page.locator('.stem-editor .ProseMirror').evaluate(el=>{el.focus();const n=el.querySelector('p,h1,h2,h3,h4,h5,h6').firstChild,r=document.createRange();r.setStart(n,0);r.setEnd(n,Math.min(10,n.length));getSelection().removeAllRanges();getSelection().addRange(r);});};
 await selectText();await control('text-color').click();await page.locator('[data-color="#ff0000"]').click();assert.ok((await state()).richDoc.content[0].content.some(n=>n.marks?.some(m=>m.attrs?.color==='#ff0000')));
 await control('highlight').click();await page.locator('[data-color="#ffff00"]').click();assert.ok((await state()).richDoc.content[0].content.some(n=>n.marks?.some(m=>m.type==='highlight')));
 await toolbar.locator('[data-editor-format=strike]').click();await toolbar.locator('[data-editor-format=superscript]').click();assert.ok((await state()).richDoc.content[0].content.some(n=>n.marks?.some(m=>m.attrs?.script==='super')));
 await control('styles').click();await page.locator('[data-style=h3]').click();assert.equal((await state()).richDoc.content[0].type,'heading');assert.equal((await state()).richDoc.content[0].attrs.level,3);
await control('styles').click();await page.locator('[data-style=normal]').click();await control('alignment').click();await page.locator('[data-alignment=center]').click();assert.equal(await page.locator('.stem-editor .ProseMirror p').first().evaluate(n=>getComputedStyle(n).textAlign),'center');
await control('paragraph').click();await page.getByRole('spinbutton',{name:'Giãn dòng',exact:true}).fill('1.5');await page.getByLabel('Khoảng sau đoạn (px)',{exact:true}).fill('12');await page.getByLabel('Lề trái (cm)',{exact:true}).fill('0.5');await page.screenshot({path:path.join(dir,'paragraph-menu.png')});await page.locator('.toolbar-paragraph-form button[type=submit]').click();
 const attrs=(await state()).richDoc.content[0].attrs;assert.equal(attrs.lineHeight,1.5);assert.equal(attrs.spaceAfter,12);assert.equal(attrs.leftIndent,0.5);
 await control('image').click();assert.equal(await page.getByRole('button',{name:'Chèn ảnh từ máy',exact:true}).count(),1);
 const chooser=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Chèn ảnh từ máy',exact:true}).click();await (await chooser).setFiles({name:'anh-thu.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR1sAAAAASUVORK5CYII=','base64')});
 await page.locator('.question-assets img').waitFor();assert.equal((await state()).images.length,1);
 await page.reload();await page.locator('.document-toolbar').waitFor();assert.equal((await state()).richDoc.content[0].attrs.spaceAfter,12);assert.equal(await page.locator('.stem-editor .ProseMirror p').first().evaluate(n=>getComputedStyle(n).lineHeight),'30px');
 await page.setViewportSize({width:1280,height:850});await page.waitForTimeout(250);assert.ok(await page.locator('.document-toolbar').isVisible());assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
 console.log('PASS: toolbar độc lập; % và mũi tên đồng bộ; bỏ tab/nhãn; mục lục đóng/mở bằng chuột, bàn phím, sau render và màn hình nhỏ; màu chữ/nền, gạch ngang, chỉ số, heading, căn lề, định dạng đoạn, menu ảnh, tải lại và màn hình hẹp');console.log('SCREENSHOTS',dir);
}finally{await browser?.close();server.kill();}
