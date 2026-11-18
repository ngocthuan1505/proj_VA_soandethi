// Kho fixture riêng: kiểm mạng chậm, lỗi đồng bộ, phạm vi đề và bố cục nhiều cỡ màn hình.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {blank,uid} from '../core.js';

const base=process.env.POC_URL||'http://127.0.0.1:4183',out=path.resolve(process.argv[2]||'outputs/local-demo/ui-model-audit-15-11/resilience');
assert.equal(base,'http://127.0.0.1:4183','Chỉ chạy trên app fixture QA.');
await fs.mkdir(out,{recursive:true});
const api=async(url,body)=>{const r=await fetch(base+url,body?{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)}:{});assert(r.ok,await r.clone().text());return r.json();};
assert((await api('/api/status')).fixture);
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1366,height:768}}),errors=[],results=[];
page.on('pageerror',e=>errors.push(e.message));
const seed=async()=>{
 const exam=blank('Sinh học',[]),id=uid();
 Object.assign(exam,{title:'QA độ bền · ngữ liệu tự viết',chat:[],matrixConfirmed:true,matrix:[{topic:'Thẩm thấu',targets:[1,1,0]}],docs:[{id,name:'Nguồn QA',kind:'text',version:1,text:'Nước đi qua màng bán thấm từ nơi có nồng độ chất tan thấp sang nơi có nồng độ chất tan cao.'}],assistantSources:[id]});
 const state=(await api('/api/kv?key=state')).value;state.exams.push(exam);state.current=exam.id;await api('/api/kv',{key:'state',value:state});
 await page.goto(base);await page.waitForLoadState('networkidle');
 await page.locator('#chat-input').fill('Soạn theo ma trận');await page.locator('#chat-form button[type=submit]').click();await page.locator('#matrix-source-text').waitFor();return exam;
};
const generate=async()=>{await page.locator('#matrix-consent').check();await page.locator('#matrix-start').click({clickCount:2});await page.locator('#matrix-confirm-save:not([disabled])').waitFor();};
try{
 await page.goto(base);await page.waitForLoadState('networkidle');
 const scope=await page.evaluate(async()=>{
  const {blank}=await import('/core.js'),{openMatrixChat,mountMatrixChat}=await import('/matrix-chat.js');
  const a=blank('Sinh học',[]),b=blank('Vật lí',[]);a.matrix=[{topic:'ĐỀ A',targets:[1,0,0]}];b.matrix=[{topic:'ĐỀ B',targets:[0,1,1]}];a.matrixConfirmed=b.matrixConfirmed=false;
  const state={exams:[a,b],current:a.id};let resolve,waiting=true;const pending=new Promise(r=>resolve=r);
  const c={exam:()=>state.exams.find(e=>e.id===state.current),getState:()=>state,persist:()=>waiting?pending:Promise.resolve(),toast:()=>{},render:()=>{}};
  const opening=openMatrixChat(c);state.current=b.id;waiting=false;resolve();await opening;state.current=a.id;mountMatrixChat(c);
  const wrongScope=document.querySelector('.matrix-chat-plan [name=topic]')?.value==='ĐỀ B';
  c.persist=()=>Promise.reject(Error('Mất mạng QA'));let rejected=false;try{await openMatrixChat(c);}catch{rejected=true;}
  c.persist=()=>Promise.resolve();await openMatrixChat(c);mountMatrixChat(c);
  return {wrongScope,matrixUnchanged:a.matrix[0].topic==='ĐỀ A'&&b.matrix[0].topic==='ĐỀ B',reopenAfterSaveFailure:rejected&&document.querySelector('.matrix-chat-plan [name=topic]')?.value==='ĐỀ A'};
 });assert(!scope.wrongScope&&scope.matrixUnchanged&&scope.reopenAfterSaveFailure);results.push({case:'chuyển đề trong lúc mở thẻ; mở lại sau lỗi lưu không bị thẻ trắng',passed:true});
 let exam=await seed();
 await page.route('**/matrix/approve',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'Lỗi mạng QA có chủ đích'})}));
 await page.locator('#matrix-consent').check();await page.locator('#matrix-start').click();await page.waitForFunction(()=>document.querySelector('#matrix-status').textContent.includes('Lỗi mạng QA'));
 assert(!await page.locator('#matrix-start').isDisabled());assert.equal((await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id).questions.length,0);
 await page.unroute('**/matrix/approve');results.push({case:'lỗi HTTP không lưu dở, cho thử lại',passed:true});
 let generations=0;page.on('request',r=>{if(r.url().endsWith('/proposals/generate')&&r.method()==='POST')generations++;});
 await generate();assert.equal(generations,1);results.push({case:'nhấp đúp chỉ tạo một job',passed:true});
 for(let round=1;round<=3;round++)for(const [width,height] of [[1920,1080],[1366,768],[1024,768],[768,1024],[390,844],[360,640]]){
  await page.setViewportSize({width,height});
  if(width<=760&&!await page.locator('.assistant.open').count())await page.locator('[data-action=toggle-ai]').first().click();
  await page.locator('#matrix-confirm-save').scrollIntoViewIfNeeded();
  const layout=await page.evaluate(()=>{
   const r=s=>{const n=document.querySelector(s),v=n.getBoundingClientRect();return {x:v.x,y:v.y,w:v.width,h:v.height};};
   const chat=r('.assistant-body'),jump=r('.ux-jump-latest'),accept=r('#matrix-confirm-save');
   const overlap=jump.w>0&&jump.h>0&&Math.min(jump.x+jump.w,accept.x+accept.w)>Math.max(jump.x,accept.x)&&Math.min(jump.y+jump.h,accept.y+accept.h)>Math.max(jump.y,accept.y);
   return {overflow:document.documentElement.scrollWidth>innerWidth+1,main:r('.main'),chat,overlap};
  });assert(!layout.overflow&&!layout.overlap);assert(layout.chat.h>=180);if(width>760)assert(layout.main.w>200);
  if(round===1)await page.screenshot({path:path.join(out,`proposal-${width}.png`)});
  results.push({case:'bố cục',round,width,height,...layout,passed:true});
 }
 await page.setViewportSize({width:1366,height:768});
 await page.locator('#matrix-confirm-save').focus();await page.keyboard.press('Tab');assert.equal(await page.locator('#matrix-discard').evaluate(n=>n===document.activeElement),true);
 results.push({case:'bàn phím tới ✓ rồi ✕',passed:true});
 // Tạm giữ bản đọc sau confirm: UI phải khóa sửa, không ghi đè bằng bản trả về trễ.
 let confirmed=false,held=false,release,seen;const gate=new Promise(r=>release=r),entered=new Promise(r=>seen=r);
 page.on('response',r=>{if(r.url().endsWith('/confirm')&&r.ok())confirmed=true;});
 await page.route('**/api/kv?key=state',async route=>{if(confirmed&&!held){held=true;const response=await route.fetch();seen();await gate;await route.fulfill({response});}else await route.continue();});
 await page.locator('#matrix-confirm-save').click();await entered;
 assert(await page.locator('.header-title').evaluate(n=>!!n.closest('[inert]')));await page.keyboard.press('Control+s');release();
 await page.locator('.matrix-document-preview').waitFor({state:'detached'});await page.unroute('**/api/kv?key=state');
 await page.waitForFunction(()=>!document.querySelector('#app').inert);assert.equal((await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id).questions.length,2);
 results.push({case:'mạng chậm lúc xác nhận khóa sửa, lưu đúng một lần',passed:true});
 exam=await seed();await generate();confirmed=false;held=false;
 await page.route('**/api/kv?key=state',async route=>{if(confirmed)await route.abort('failed');else await route.continue();});
 await page.locator('#matrix-confirm-save').click();await page.getByRole('heading',{name:'Bộ câu đã lưu',exact:true}).waitFor();
 assert(await page.locator('#app').evaluate(n=>n.inert));await page.keyboard.press('Escape');assert(await page.getByRole('heading',{name:'Bộ câu đã lưu',exact:true}).isVisible());
 const saved=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);assert.equal(saved.questions.length,2);
 await page.getByRole('button',{name:'Thử đồng bộ',exact:true}).click();await page.getByText('Chưa kết nối được. Bộ câu đã lưu vẫn giữ nguyên trên máy chủ.').waitFor();
 await page.unroute('**/api/kv?key=state');await page.getByRole('button',{name:'Thử đồng bộ',exact:true}).click();await page.locator('.matrix-document-preview').waitFor({state:'detached'});await page.waitForFunction(()=>!document.querySelector('#app').inert);await page.reload();await page.waitForLoadState('networkidle');assert.equal(await page.locator('.question').count(),2);
 const reloaded=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);assert.deepEqual(reloaded.questions.map(q=>q.id),saved.questions.map(q=>q.id));
 results.push({case:'mất kết nối sau lưu không lấy cache cũ ghi ngược, reload giữ ID',passed:true});
 await page.setViewportSize({width:360,height:640});if(!await page.locator('.assistant.open').count())await page.locator('[data-action=toggle-ai]').first().click();await page.locator('[data-ux-action=options]').click();await page.locator('.ux-chat-options [data-action=connections]').click();await page.locator('#dialog[open]').waitFor();
 const modal=await page.locator('#dialog').boundingBox();assert(modal.x>=0&&modal.x+modal.width<=361&&modal.y>=0&&modal.y+modal.height<=641);await page.screenshot({path:path.join(out,'connections-360.png')});
 results.push({case:'hộp kết nối vừa màn hình 360×640',passed:true});assert.deepEqual(errors,[]);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({fixtureOnly:true,results,pageErrors:errors},null,2));console.log(JSON.stringify({cases:results.length,passed:true,pageErrors:errors}));
}finally{await browser.close();}
