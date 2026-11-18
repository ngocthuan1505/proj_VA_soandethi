// --live chỉ chạy trên kho QA 4184; mặc định dùng fixture 4183.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {blank,uid} from '../core.js';
import {ensureBlocks} from '../blocks.js';

const live=process.argv.includes('--live'),base=live?'http://127.0.0.1:4184':(process.env.POC_BASE||'http://127.0.0.1:4183'),out=path.resolve(process.env.POC_OUTPUT||'outputs/local-demo/ui-model-audit-15-11/'+(live?'patch-live':'patch-fixture'));
await fs.mkdir(out,{recursive:true});
const api=async(url,body)=>{const r=await fetch(base+url,body?{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)}:{});assert(r.ok,await r.clone().text());return r.json();};
assert.equal((await api('/api/status')).fixture,!live);
const exam=blank('Toán',[]);Object.assign(exam,{title:'QA sửa câu · '+(live?'AI thật':'fixture'),grade:'1',chat:[],aiConsent:true,aiChatMode:'edit',autoUpdate:false,questions:[{id:uid(),v:1,type:'mcq',stem:'Một cộng một bằng mấy?',options:['1','2','3','4'],answer:1,explanation:'Một cộng một bằng hai.',topic:'Phép cộng',level:0,points:5,source:null,check:null},{id:uid(),v:1,type:'mcq',stem:'Hai cộng hai bằng mấy?',options:['1','2','3','4'],answer:3,explanation:'Hai cộng hai bằng bốn.',topic:'Phép cộng',level:0,points:5,source:null,check:null}]});ensureBlocks(exam);
const prior=(await api('/api/kv?key=state')).value??{version:1,exams:[],prefs:[]};prior.exams.push(exam);prior.current=exam.id;await api('/api/kv',{key:'state',value:prior});
const saved=async()=>(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1366,height:768}}),errors=[];page.setDefaultTimeout(live?310000:30000);page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.waitForLoadState('networkidle');
 const submit=async(text='Viết lại câu này rõ ràng hơn, giữ phép tính một cộng một và đáp án đúng.')=>{
  if(!await page.locator('#chat-mode').isVisible())await page.locator('[data-ux-action=options]').click();await page.locator('#chat-mode').selectOption('edit');await page.keyboard.press('Escape');await page.locator('#chat-input').fill(text);await page.locator('#chat-form button[type=submit]').click();
 };
 const send=async text=>{await submit(text);await page.locator('.proposal-card').waitFor();};
 if(!live){
  const stopText='Sửa câu này cho rõ hơn và giữ phép tính một cộng một.';
  const pattern='**/api/assistant/patch';
  let releaseResponse, capturedResponse;
  const hold=new Promise(resolve=>{releaseResponse=resolve;});
  const captured=new Promise(resolve=>{capturedResponse=resolve;});
  await page.route(pattern,async route=>{
   try{
    const response=await route.fetch();
    capturedResponse(response.ok());
    await hold;
    await route.fulfill({response});
   }catch{capturedResponse(false);}
  },{times:1});
  try{
   await page.locator('.outline-item').first().click();
   await submit(stopText);
   assert(await captured,'FastAPI chưa trả đề xuất fixture để kiểm phản hồi đến muộn');
   await page.getByRole('button',{name:'Dừng chờ đề xuất',exact:true}).click();
   await page.getByText('Đã dừng chờ đề xuất sửa. Bạn có thể gửi lại yêu cầu.',{exact:true}).waitFor();
   assert.equal(await page.locator('#chat-input').inputValue(),stopText);
   assert.deepEqual((await saved()).questions,exam.questions);
  }finally{releaseResponse();await page.unroute(pattern);}
  await page.locator('.outline-item').first().click();
  assert.equal(await page.locator('.proposal-card').count(),0);
  await send(stopText);
  assert.deepEqual((await saved()).questions,exam.questions);
  await page.locator('.proposal-card [data-action=discard-block-patch]').click();
 }
 await page.locator('.outline-item').first().click();const started=performance.now();await send();
 assert.deepEqual((await saved()).questions,exam.questions);
 assert((await page.locator('.proposal-card').innerText()).includes('Giải độc lập'));
 await page.locator('[data-action=show-block-diff]').click();await page.locator('.block-diffs').waitFor();await page.screenshot({path:path.join(out,'01-xem-thay-doi.png')});await page.locator('#dialog [data-action=close]').click();
 if(!live){
  await page.locator('.proposal-card [data-action=discard-block-patch]').click();assert.deepEqual((await saved()).questions,exam.questions);await page.locator('.outline-item').first().click();await send();
 }
 await page.locator('.proposal-card [data-action=apply-block-patch]').click();await page.waitForFunction(()=>document.querySelector('.question .stem-editor')?.textContent!== 'Một cộng một bằng mấy?');await page.waitForTimeout(250);
 let current=await saved();assert.notEqual(current.questions[0].stem,exam.questions[0].stem);assert.equal(current.questions[0].id,exam.questions[0].id);assert.equal(current.questions[0].v,2);assert.deepEqual(current.questions[1],exam.questions[1]);
 const proposalSeconds=(performance.now()-started)/1000;
 if(!live){
  await page.locator('[data-action=undo]').first().click();await page.waitForTimeout(200);assert.deepEqual((await saved()).questions,exam.questions);
  await page.locator('[data-action=redo]').first().click();await page.waitForTimeout(200);
  // Dùng lựa chọn DOM thật trong TipTap, không tự nhét scope vào request.
  const before=await saved();const word='cộng';
  await page.locator('.question').first().locator('.tiptap').first().evaluate((node,word)=>{
   const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let text;while(text=walker.nextNode()){const start=text.textContent.indexOf(word);if(start>=0){node.focus();const range=document.createRange();range.setStart(text,start);range.setEnd(text,start+word.length);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);return;}}throw Error('Không thấy chữ cần bôi đen');
  },word);
  await page.evaluate(async()=>{(await import('/editor.js')).captureDOMSelection();});
  await send('Sửa đoạn đang bôi đen cho rõ hơn, giữ các chữ khác.');await page.locator('.proposal-card [data-action=apply-block-patch]').click();await page.waitForTimeout(300);current=await saved();
  assert.equal(current.questions[0].stem,before.questions[0].stem.replace(word,word+' (đã sửa)'));assert.deepEqual(current.questions[1],exam.questions[1]);
  await page.locator('.outline-item').first().click();await send();await page.locator('.header-title').fill('Tên sửa tay sau đề xuất');await page.locator('.header-title').press('Tab');await page.locator('.proposal-card [data-action=apply-block-patch]').click();assert((await page.locator('#toast').innerText()).includes('Nội dung đã đổi'));assert.equal((await saved()).title,'Tên sửa tay sau đề xuất');
 }
 await page.screenshot({path:path.join(out,'02-sua-dung-cau.png')});assert.deepEqual(errors,[]);
 const result={mode:live?'real_ai':'fixture',examId:exam.id,previewBeforeAccept:true,stopWaitingVerified:!live,otherQuestionUnchanged:true,idsPreserved:true,checksVisible:true,discardUndoPartialStaleTested:!live,proposalSeconds,pageErrors:errors};await fs.writeFile(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();}
