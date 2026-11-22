import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {blank} from '../core.js';
import {dependency,chromePath} from '../runtime.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),base='http://127.0.0.1:4300',dir=await mkdtemp(path.join(os.tmpdir(),'chat-polish-'));
const server=spawn(process.execPath,[path.join(root,'server.mjs')],{env:{...process.env,PORT:'4300',APP_DATA_DIR:dir},stdio:'ignore',windowsHide:true});let browser;
try{
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/status')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 const exam=blank('Toán');exam.grade='12';exam.autoUpdate=false;exam.aiConsent=true;
 await fetch(base+'/api/kv',{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({key:'state',value:{version:1,current:exam.id,exams:[exam],prefs:[]}})});
 browser=await dependency('playwright-core').chromium.launch({headless:true,executablePath:chromePath()});const page=await browser.newPage({viewport:{width:1740,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));let requests=0;
 await page.route('**/api/assistant/chat',async route=>{requests++;await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({message:'Đã nhận câu hỏi kiểm thử.',credits:{balance:1000}})});});
 await page.goto(base);await page.locator('.chat-polished .chat-suggestion-card').first().waitFor();await page.waitForTimeout(500);
 assert.equal(await page.locator('.menubar [data-menu]>.ui-icon').count(),0);assert.equal(await page.locator('.header-actions [data-action=share]>.ui-icon').count(),1);
 for(const menu of ['file','edit','view','insert','format','tools']){await page.locator(`.menubar [data-menu=${menu}]`).click();const items=page.locator('.document-menu .menu-item');assert.ok(await items.count()>0);assert.equal(await items.filter({has:page.locator('.ui-icon')}).count(),await items.count());}
 await page.locator('.header-title').click();assert.equal(await page.locator('.chat-suggestion-card').count(),3);assert.equal(await page.locator('.chat-source-tools button').count(),3);assert.match(await page.locator('.chat-context-pill').innerText(),/Toán · Lớp 12/);
 await page.screenshot({path:path.join(dir,'chat-and-menus.png')});
 await page.locator('#chat-input').fill('Chào bạn');await page.keyboard.press('Enter');await page.getByText('Đã nhận câu hỏi kiểm thử.',{exact:true}).waitFor();assert.equal(requests,1);
 await page.locator('#chat-input').fill('Dòng đầu');await page.keyboard.press('Shift+Enter');await page.keyboard.insertText('Dòng sau');assert.equal(await page.locator('#chat-input').inputValue(),'Dòng đầu\nDòng sau');assert.equal(requests,1);
 await page.locator('[data-ux-action=options]').click();assert.ok(await page.locator('#chat-options').isVisible());await page.keyboard.press('Escape');
 await page.setViewportSize({width:1280,height:800});await page.waitForTimeout(300);const assistant=await page.locator('.assistant').boundingBox(),input=await page.locator('#chat-input').boundingBox();assert.ok(input.y>=assistant.y&&input.y+input.height<=assistant.y+assistant.height);
 assert.deepEqual(errors,[]);console.log('PASS: menu ngoài chỉ chữ; icon từng tác vụ và chia sẻ; chat/gợi ý/nguồn; Enter gửi, Shift+Enter xuống dòng; ô nhập không tràn ở 1280px');console.log('SCREENSHOT',path.join(dir,'chat-and-menus.png'));
}finally{await browser?.close();server.kill();}
