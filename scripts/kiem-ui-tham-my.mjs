// Rà UI bằng dữ liệu fixture riêng; không dùng khóa hay gọi model thật.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {blank,uid} from '../core.js';
import {ensureBlocks} from '../blocks.js';
import {subjectId} from '../authoring-catalog.js';

const base='http://127.0.0.1:4183',out=path.resolve(process.argv[2]||'outputs/local-demo/ui-polish-15-11/verified');await fs.mkdir(out,{recursive:true});
const api=async(url,body)=>{const r=await fetch(base+url,body?{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)}:{});assert(r.ok,await r.clone().text());return r.json();};
assert((await api('/api/status')).fixture,'Chỉ chạy ở kho fixture QA.');
assert((await fetch(base+'/qa/scenario',{method:'POST',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({case:'repair'})})).ok,'Chưa đặt lại tình huống fixture.');
const exam=blank('Toán',[]),doc=uid();Object.assign(exam,{title:'QA giao diện · Đề thử riêng',chat:[],autoUpdate:false,questions:[{id:uid(),v:1,type:'mcq',stem:'Một cộng một bằng mấy?',options:['1','2','3','4'],answer:1,explanation:'Một cộng một bằng hai.',points:10,level:0,topic:'Phép cộng',source:null,check:null}],docs:[{id:doc,name:'Nguồn tự viết QA',kind:'text',version:1,text:'Một cộng một bằng hai. Hai cộng hai bằng bốn.'}],assistantSources:[doc],matrix:[{topic:'Phép cộng',targets:[1,0,0]}],matrixConfirmed:true});ensureBlocks(exam);
const state=(await api('/api/kv?key=state')).value;state.exams.push(exam);state.current=exam.id;await api('/api/kv',{key:'state',value:state});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
const goto=async()=>{await page.goto(base);await page.waitForLoadState('networkidle');};
const openConnections=async()=>{if(await page.locator('.assistant.open').count()&&page.viewportSize().width<=760){await page.locator('[data-ux-action=options]').click();await page.locator('.ux-chat-options [data-action=connections]').click();}else await page.locator('.design-rail [data-action=connections]').click();await page.locator('#connections-form').waitFor();};
const bounds=async selector=>page.locator(selector).evaluate(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};});
try{
 await goto();assert((await page.locator('.assistant-welcome').innerText()).includes('Chọn câu hoặc bôi đen'));
 await page.screenshot({path:path.join(out,'workspace-1440.png')});
 await openConnections();const form=page.locator('#connections-form');
 assert(!await form.locator('[data-poc-provider=gemini]').first().isVisible());
 await form.locator('[name=route-generate]').selectOption('gemini');assert(await form.locator('[data-poc-provider=gemini]').first().isVisible());assert(await form.locator('[data-poc-provider=ollama]').isVisible());
 await form.locator('[name=route-check]').selectOption('gemini');assert(!await form.locator('[data-poc-provider=ollama]').isVisible());
 await form.locator('[name=gemini-key]').fill('fixture-key-not-a-real-secret');await form.locator('[name=gemini-model]').selectOption('gemini-4-hydrogen');
 await form.locator('[name=route-generate]').selectOption('ollama');await form.locator('[name=route-check]').selectOption('ollama');assert(!await form.locator('[data-poc-provider=gemini]').first().isVisible());
 await form.locator('[name=route-generate]').selectOption('gemini');assert.equal(await form.locator('[name=gemini-key]').inputValue(),'fixture-key-not-a-real-secret');assert.equal(await form.locator('[name=gemini-model]').inputValue(),'gemini-4-hydrogen');await form.locator('[name=gemini-key]').clear();
 await page.screenshot({path:path.join(out,'connections-mixed.png')});
 await form.locator('[name=route-generate]').selectOption('ollama');await form.locator('[name=route-check]').selectOption('ollama');
 await page.route('**/api/config',route=>route.request().method()==='POST'?route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'Lỗi kiểm thử: kết nối chưa lưu, kiểm tra lại cấu hình.'})}):route.continue());
 await form.locator('button[type=submit]').click();await page.locator('[data-dialog-feedback]').waitFor();assert((await page.locator('[data-dialog-feedback]').innerText()).includes('Lỗi kiểm thử'));assert(await page.locator('[data-dialog-feedback]').evaluate(n=>{const r=n.getBoundingClientRect();return r.y>=0&&r.bottom<=innerHeight;}));
 await page.screenshot({path:path.join(out,'connections-error.png')});await page.unroute('**/api/config');await page.keyboard.press('Escape');assert.equal(await page.locator('#dialog[open]').count(),0);results.push({case:'dịch vụ local/cloud/hỗn hợp, giữ dữ liệu form khi chuyển, lỗi lưu hiện trong modal, Escape',passed:true});
 for(const [width,height] of [[1440,900],[1366,768],[1024,768],[390,844],[360,640]]){
  await page.setViewportSize({width,height});await goto();
  const close=page.locator('.assistant.open [data-action=toggle-ai]');if(width<=760&&await close.count())await close.click();
  for(const action of ['new','library','export','import-doc','connections']){
   await page.locator('[data-action='+action+']:visible').first().click();await page.locator('#dialog[open]').waitFor();
   const modal=await bounds('#dialog');assert(modal.x>=-1&&modal.y>=-1&&modal.x+modal.w<=width+1&&modal.y+modal.h<=height+1);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const footer=page.locator('#dialog .modal-foot button').last();if(await footer.count()){
    await footer.scrollIntoViewIfNeeded();assert(await footer.evaluate(n=>{const r=n.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return n===hit||n.contains(hit);}));
   }
   const unlabeled=await page.locator('#dialog input:not([type=hidden]),#dialog select,#dialog textarea').evaluateAll(nodes=>nodes.filter(n=>n.getClientRects().length&&!n.getAttribute('aria-label')&&!n.title&&!n.closest('label')&&![...document.querySelectorAll('label[for]')].some(l=>l.htmlFor===n.id)).map(n=>n.id||n.name));
   assert.deepEqual(unlabeled,[],action+' có trường chưa có nhãn');
   if(width===360||width===1440)await page.screenshot({path:path.join(out,`${action}-${width}.png`)});
   await page.keyboard.press('Escape');assert.equal(await page.locator('#dialog[open]').count(),0);
   results.push({case:'hộp thoại vừa màn hình, nút không bị che, trường có nhãn',action,width,height,passed:true});
  }
 }
 for(const [width,height] of [[1440,900],[390,844],[360,640]]){
  await page.setViewportSize({width,height});await goto();if(width<=760&&!await page.locator('.assistant.open').count())await page.locator('.header-actions [data-action=toggle-ai]').click();
  if(width<=760)await page.locator('[data-ux-action=attach]').click();const launch=width<=760?page.locator('.assistant [data-action=subject-library]').first():page.locator('.design-library-open');await launch.click();await page.locator('.composer-shell').waitFor();
  await page.locator(`[data-action=composer-subject][data-subject="${subjectId('Toán')}"]`).click();
  if(width<=760){assert(await page.locator('.composer-library').isVisible());assert(!await page.locator('.composer-work').isVisible());assert((await bounds('.composer-library')).h>=100);}
  await page.locator('#catalog-search').fill('Phân số');await page.locator('[data-action=composer-template]').first().click();await page.locator('#builder-fields [data-builder-field]:visible,#visual-math-input:visible').first().waitFor();
  const field=page.locator('#builder-fields [data-builder-field]:visible').first();if(await field.count()){await field.evaluate(n=>{n.value='x+2';n.dispatchEvent(new Event('input',{bubbles:true}));});}
  const initial=await page.locator('#inline-math-input').inputValue();assert(initial.includes('frac'));
  await page.locator('.composer-advanced summary').click();await page.locator('#inline-math-input').fill('\\frac{');assert(await page.locator('#composer-save').isDisabled());assert((await page.locator('#composer-feedback').innerText()).length>0);await page.locator('#inline-math-input').fill(initial);assert(!await page.locator('#composer-save').isDisabled());await page.locator('.composer-advanced summary').click();
  if(width<=760){
   assert(!await page.locator('.catalog-filters').isVisible());assert((await bounds('.composer-work')).h>=200);
   await page.locator('[data-action=composer-pane][data-pane=library]').click();assert.equal(await page.locator('#inline-math-input').inputValue(),initial);await page.locator('#composer-save').click();assert(await page.locator('.composer-work').isVisible());assert.equal(await page.locator('#inline-math-input').inputValue(),initial);
  }
  assert(await page.locator('#inline-math-preview .katex').count());await page.locator('#composer-save').scrollIntoViewIfNeeded();assert(await page.locator('#composer-save').evaluate(n=>{const r=n.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return n===hit||n.contains(hit);}));
  await page.screenshot({path:path.join(out,`composer-work-${width}.png`)});await page.keyboard.press('Escape');await page.locator('.composer-shell').waitFor({state:'detached'});results.push({case:'thư viện mẫu, nhập trực quan, chuyển pane không mất nội dung, không chèn sớm',width,height,passed:true});
 }
 await page.setViewportSize({width:1366,height:768});await goto();await page.locator('#chat-input').fill('Soạn đề theo ma trận này');await page.locator('#chat-form button[type=submit]').click();await page.locator('#matrix-source-text').waitFor();
 assert(!await page.locator('#matrix-reviewer').isVisible());await page.locator('#matrix-consent').check();await page.locator('#matrix-start').click();await page.locator('#matrix-confirm-save:not([disabled])').waitFor();assert(!await page.locator('#matrix-reviewer').isVisible());await page.locator('#matrix-result-details summary').first().click();assert(await page.locator('#matrix-reviewer').isVisible());
 assert((await page.locator('.matrix-review-question blockquote small').first().innerText()).includes('Nguồn tự viết QA'));await page.screenshot({path:path.join(out,'matrix-proposal.png')});
 results.push({case:'ma trận giữ vòng kiểm; tên nguồn dễ đọc; chỉ hiện người rà khi có kết quả',passed:true});
 assert.deepEqual(errors,[]);const current=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);assert.deepEqual(current.questions,exam.questions);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({fixtureOnly:true,results,pageErrors:errors,noUnconfirmedDocumentChanges:true},null,2));console.log(JSON.stringify({passed:true,cases:results.length,pageErrors:errors}));
}finally{await browser.close();}
