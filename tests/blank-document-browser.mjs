import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {blank} from '../core.js';
import {dependency,chromePath} from '../runtime.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),base='http://127.0.0.1:4299',dir=await mkdtemp(path.join(os.tmpdir(),'blank-doc-'));
const server=spawn(process.execPath,[path.join(root,'server.mjs')],{env:{...process.env,PORT:'4299',APP_DATA_DIR:dir},stdio:'ignore',windowsHide:true});let browser;
try{
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/status')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 const exam=blank('Toán');exam.autoUpdate=false;
 await fetch(base+'/api/kv',{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({key:'state',value:{version:1,current:exam.id,exams:[exam],prefs:[]}})});
 browser=await dependency('playwright-core').chromium.launch({headless:true,executablePath:chromePath()});const page=await browser.newPage({viewport:{width:2040,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.locator('.document-body-editor .ProseMirror').waitFor();await page.waitForTimeout(500);
 assert.equal(await page.locator('.paper .exam-heading').count(),0);assert.equal(await page.locator('[data-editor-format=clear],[data-toolbar=line]').count(),0);
 const title=page.getByRole('textbox',{name:'Tên tài liệu',exact:true});assert.ok((await title.boundingBox()).width<250);const saved=await page.locator('.document-title-line .saved').boundingBox(),titleBox=await title.boundingBox();assert.ok(saved.x-titleBox.x-titleBox.width<25);
 await page.screenshot({path:path.join(dir,'blank-page.png')});
 const editor=page.locator('.document-body-editor .ProseMirror');await editor.click();await page.keyboard.type('De thi cua toi');await page.keyboard.press('Enter');await page.keyboard.insertText('Nội dung tự soạn trên trang trắng.');await page.getByRole('button',{name:'In đậm',exact:true}).click();await page.keyboard.insertText(' Chữ đậm.');await page.waitForTimeout(750);
 const state=async()=>{await page.waitForFunction(()=>/^Đã lưu/.test(document.querySelector('[data-save-status]')?.textContent||''));const value=(await(await page.request.get(base+'/api/kv?key=state')).json()).value;return value.exams.find(e=>e.id===value.current);};
 assert.equal((await state()).questions.length,0);assert.ok((await state()).bodyText.includes('Nội dung tự soạn'));await page.reload();await editor.waitFor();assert.match(await editor.innerText(),/Chữ đậm/);
 await editor.click();await page.keyboard.press('Control+End');await page.locator('[data-action=formula]').click();await page.locator('.compact-composer-shell').waitFor();assert.equal(await page.locator('.compact-formula-modes button').count(),2);assert.equal(await page.locator('.compact-formula-library').getAttribute('open'),null);
 await page.locator('.composer-advanced summary').click();await page.locator('#inline-math-input').fill('x^2+1');await page.locator('#inline-math-input').dispatchEvent('input');await page.screenshot({path:path.join(dir,'compact-formula.png')});await page.locator('#composer-save').click();await page.waitForTimeout(700);assert.ok((await state()).bodyText.includes('$x^2+1$'));assert.equal((await state()).questions.length,0);
 await page.locator('[data-action=chemistry]').click();await page.locator('.compact-composer-shell').waitFor();assert.equal(await page.locator('[data-action=composer-subject][data-subject=chemistry]').getAttribute('aria-pressed'),'true');await page.locator('[data-action=floating-close]').first().click();
 await page.locator('.document-body-editor .math-atom').first().click();await page.locator('.compact-composer-shell').waitFor();await page.locator('.composer-advanced summary').click();await page.locator('#inline-math-input').fill('x^3+1');await page.locator('#inline-math-input').dispatchEvent('input');await page.locator('#composer-save').click();await page.waitForTimeout(700);assert.ok((await state()).bodyText.includes('$x^3+1$'));
 await editor.click();await page.keyboard.press('Control+End');const beforeUndo=(await state()).bodyText;await page.keyboard.press('Control+z');await page.waitForTimeout(650);assert.notEqual((await state()).bodyText,beforeUndo);await editor.click();await page.keyboard.press('Control+Shift+z');await page.waitForTimeout(650);assert.equal((await state()).bodyText,beforeUndo);
 await title.fill('Tên đề dài hơn để kiểm tra');await title.dispatchEvent('input');await title.blur();assert.ok((await title.boundingBox()).width>titleBox.width);await page.waitForTimeout(650);await page.reload();await editor.waitFor();assert.match(await editor.innerText(),/x/);assert.equal(await title.inputValue(),'Tên đề dài hơn để kiểm tra');assert.deepEqual(errors,[]);
 console.log('PASS: giấy trắng gõ/lưu/tải lại; không sinh câu giả; font/công thức Toán-Hóa; ô tên co giãn; bỏ Tx/đường kẻ');console.log('SCREENSHOTS',dir);
}finally{await browser?.close();server.kill();}
