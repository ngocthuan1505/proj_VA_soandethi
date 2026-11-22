import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {blank,uid} from '../core.js';
import {dependency,chromePath} from '../runtime.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),base='http://127.0.0.1:4301',dir=await mkdtemp(path.join(os.tmpdir(),'page-break-'));
const server=spawn('uv',['run','--project','backend','--frozen','--python','3.12','python','-m','uvicorn','mach_backend.local_workspace:app','--app-dir','backend/src','--host','127.0.0.1','--port','4301'],{cwd:root,env:{...process.env,MACH_DATA_DIR:dir},stdio:'ignore',windowsHide:true});let browser;
try{
 for(let i=0;i<150;i++){try{if((await fetch(base+'/api/status')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 const exam=blank('Toán');exam.autoUpdate=false;
 const put=await fetch(base+'/api/kv',{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({key:'state',value:{version:1,current:exam.id,exams:[exam],prefs:[]}})});assert.ok(put.ok);
 browser=await dependency('playwright-core').chromium.launch({headless:true,executablePath:chromePath()});const page=await browser.newPage({viewport:{width:2040,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.locator('.document-body-editor .ProseMirror').waitFor();await page.waitForTimeout(450);
 assert.equal(await page.locator('.design-breadcrumb').count(),0);assert.equal(await page.locator('.menubar .ui-icon').count(),0);
 const fonts=await page.evaluate(()=>Object.fromEntries(['.menu-button','.sidebar-title','#chat-input'].map(s=>[s,parseFloat(getComputedStyle(document.querySelector(s)).fontSize)])));assert.ok(fonts['.menu-button']>=15&&fonts['.sidebar-title']>=16&&fonts['#chat-input']>=14);
 const editors=page.locator('.document-body-editor .ProseMirror'),sheets=page.locator('.document-page');
 await editors.first().click();await page.keyboard.insertText('Phần đầu. Phần sau.');await editors.first().evaluate(node=>{const range=document.createRange();range.setStart(node.querySelector('p').firstChild,9);range.collapse(true);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);});await page.waitForTimeout(100);
 await page.locator('[data-toolbar=page-break]').click();await page.waitForFunction(()=>document.querySelectorAll('.document-body-editor').length===2);assert.equal(await sheets.count(),2);assert.equal(await editors.first().innerText(),'Phần đầu.');assert.equal(await editors.nth(1).innerText(),' Phần sau.');
 assert.equal(await page.evaluate(()=>document.activeElement.closest('.document-page')?.dataset.page),'2');await page.keyboard.insertText('Trang hai.');await page.keyboard.press('Control+End');await page.keyboard.press('Enter');await page.keyboard.insertText('Thêm dòng.');await page.waitForTimeout(750);
 // Enter thường sau ngắt trang không được nhân thêm dấu ngắt trang.
 const stored=async()=>{await page.waitForFunction(()=>/^Đã lưu/.test(document.querySelector('[data-save-status]')?.textContent||''));const state=(await(await page.request.get(base+'/api/kv?key=state')).json()).value;return state.exams.find(e=>e.id===state.current);};
 let saved=await stored();assert.equal(saved.bodyTextDoc.content.filter(n=>n.attrs?.pageBreakBefore).length,1);assert.equal(saved.questions.length,0);
 await page.keyboard.press('Control+Enter');await page.waitForFunction(()=>document.querySelectorAll('.document-page').length===3);assert.equal(await page.evaluate(()=>document.activeElement.closest('.document-page')?.dataset.page),'3');await page.keyboard.insertText('Trang ba.');await page.waitForTimeout(700);
 await page.reload();await editors.nth(2).waitFor();assert.equal(await sheets.count(),3);assert.match(await editors.nth(2).innerText(),/Trang ba/);saved=await stored();assert.equal(saved.bodyTextDoc.content.filter(n=>n.attrs?.pageBreakBefore).length,2);
 const ids=[];const collect=n=>{if(n.attrs?.id)ids.push(n.attrs.id);for(const child of n.content||[])collect(child);};collect(saved.bodyTextDoc);assert.equal(new Set(ids).size,ids.length);
 // Hoàn tác/làm lại đúng thao tác ngắt trang, không mất phần nội dung ở trang trước.
 await editors.nth(2).click();await page.keyboard.press('Control+End');const before=saved.bodyText;await page.keyboard.press('Control+Enter');await page.waitForFunction(()=>document.querySelectorAll('.document-page').length===4);await page.keyboard.press('Control+z');await page.waitForFunction(()=>document.querySelectorAll('.document-page').length===3);assert.equal((await stored()).bodyText,before);await editors.nth(2).click();await page.keyboard.press('Control+Shift+z');await page.waitForFunction(()=>document.querySelectorAll('.document-page').length===4);
 await page.screenshot({path:path.join(dir,'page-break.png')});
 await page.setViewportSize({width:1280,height:800});await page.waitForTimeout(250);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const composer=await page.locator('#chat-input').boundingBox(),assistant=await page.locator('.assistant').boundingBox();assert.ok(composer.y+composer.height<=assistant.y+assistant.height);
 await page.goto('about:blank');const structured=blank('Sinh học');structured.autoUpdate=false;structured.questions=Array.from({length:3},(_,i)=>({id:uid(),v:1,type:'mcq',points:2.5,stem:'Nội dung câu '+(i+1),options:['Một','Hai','Ba','Bốn'],answer:0,explanation:'',rubric:[],topic:'Tế bào',level:0}));
 await page.request.put(base+'/api/kv',{headers:{Origin:base},data:{key:'state',value:{version:1,current:structured.id,exams:[structured],prefs:[]}}});await page.setViewportSize({width:2040,height:1100});await page.goto(base);const question=page.locator('.question').nth(1);await question.locator('.stem-editor .ProseMirror').click();await page.locator('[data-toolbar=page-break]').click();await page.waitForTimeout(500);
 const locations=await page.locator('.question').evaluateAll(nodes=>nodes.map(n=>({id:n.dataset.q,page:n.closest('.document-page').dataset.page})));assert.deepEqual(locations.map(n=>n.id),structured.questions.map(q=>q.id));assert.notEqual(locations[0].page,locations[1].page);assert.equal((await stored()).questions[1].pageBreak,true);assert.equal(await page.evaluate(()=>document.activeElement.closest('.question')?.dataset.q),structured.questions[1].id);
 assert.deepEqual(errors,[]);console.log('PASS: FastAPI; ngắt giữa đoạn/chuyển con trỏ; Ctrl+Enter; Enter không lặp dấu ngắt; lưu/tải lại; UUID; undo/redo; ngắt trước câu có sẵn; chữ lớn/menu/breadcrumb; bố cục 1280px');console.log('SCREENSHOT',path.join(dir,'page-break.png'));
}finally{await browser?.close();server.kill();}
