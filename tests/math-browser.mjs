import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_PATH?{executablePath:process.env.BROWSER_PATH}:{})});
const context=await browser.newContext({viewport:{width:1500,height:1000}}),page=await context.newPage(),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const act=(name,scope=page)=>scope.locator(`[data-action="${name}"]`).first();
const state=()=>page.evaluate(async()=>{const s=await(await import('/storage.js')).get('state');return s.exams.find(e=>e.id===s.current);});
const save=()=>page.waitForFunction(()=>document.querySelector('[data-save-status]')?.textContent==='Đã lưu trên máy');
const close=()=>act('close',page.locator('dialog')).click();
try{
 await page.goto('http://127.0.0.1:4173');await page.locator('.paper').waitFor();
 const geo=await state();await act('new').click();await page.locator('[data-action="create-sample"][data-subject="Toán"]').click();await save();
 let e=await state();assert.equal(e.subject,'Toán');assert.equal(e.questions.length,5);assert.equal(await page.locator('.data-card').count(),0);assert.equal(e.questions[0].check.status,'review');
 const original=structuredClone(e);await page.locator('.question').first().locator('textarea.stem').fill('Trên ℝ, tập nghiệm của phương trình x² = −9 là?');await page.waitForTimeout(750);await save();
 e=await state();assert.equal(e.questions[0].check.status,'review');assert.ok(e.questions[0].check.evidence.includes('vô nghiệm'));assert.deepEqual(e.questions.slice(1),original.questions.slice(1));
 await act('review',page.locator('aside.assistant')).click();assert.equal(await page.locator('dialog .data-card').count(),0);await act('repair-preview',page.locator('dialog')).click();await act('apply-repair',page.locator('dialog')).click();await save();e=await state();assert.equal(e.questions[0].answer,3);assert.equal(e.questions[0].check.status,'consistent');await close();await act('undo').click();await save();assert.equal((await state()).questions[0].answer,1);await act('undo').click();await save();assert.deepEqual((await state()).questions,original.questions);
 await page.reload();await page.locator('.paper').waitFor();assert.equal((await state()).subject,'Toán');
 await act('export').click();await page.locator('[data-action="save-local"][data-teacher="false"]').click();await page.locator('.saved-export-link').waitFor();const url=await page.locator('.saved-export-link').getAttribute('href');const response=await page.request.get('http://127.0.0.1:4173'+url);const html=await response.text();assert.ok(html.includes('x² = 9'));assert.ok(!html.includes('Đáp án lưu'));assert.ok(!html.includes('Số người sử dụng thư viện'));await close();
 await act('library').click();await page.locator(`[data-action="open-exam"][data-id="${geo.id}"]`).click();assert.equal((await state()).subject,'Địa lí');await page.goto('http://127.0.0.1:4173/?demo=toan');await page.locator('.paper').waitFor();assert.equal((await state()).id,original.id);
 await act('new').click();await page.locator('[data-action="create-sample"][data-subject="Ngữ văn"]').click();await save();assert.equal((await state()).subject,'Ngữ văn');await page.goto('http://127.0.0.1:4173/?demo=toan');await page.locator('.paper').waitFor();
 const q2=page.locator('.question').nth(1).locator('textarea.stem');await q2.fill('Một yêu cầu Toán ngoài các dạng được hỗ trợ.');await page.waitForTimeout(750);await save();assert.equal((await state()).questions[1].check.status,'unverified');await act('undo').click();await save();
 await page.screenshot({path:process.env.MATH_SCREENSHOT||'../../work/Toan-demo.png'});assert.deepEqual(errors,[]);console.log('PASS Toán: tạo 5 câu; kiểm tra; đổi 9→−9; sửa đáp án; hoàn tác; giữ câu khác; lưu/mở lại; xuất HTML thật; mở lại Địa lí/Ngữ văn; dạng chưa hỗ trợ không báo đã giải.');
 await writeFile(process.env.MATH_RESULTS||'../../work/math-results.json',JSON.stringify({passed:true,errors,subject:'Toán 9',questions:5,coreTests:14,flows:['create','check','edit-square','repair','undo','persistence','export','preserve-other-subjects','unsupported-status']},null,2));
}finally{await browser.close();}
