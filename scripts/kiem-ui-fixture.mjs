// Kiểm luồng giao diện bằng model giả lập. Không dùng làm kết quả AI thật.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {blank,uid} from '../core.js';

const url=process.env.POC_URL||'http://127.0.0.1:4183';
const out=path.resolve(process.argv[2]||'outputs/local-demo/fixture-ui-check');
const cancel=process.argv.includes('--cancel');
const destinationOnly=process.argv.includes('--gemini-label');
const expectFailure=process.argv.includes('--expect-failure');
const stale=process.argv.includes('--stale');
await fs.mkdir(out,{recursive:true});
async function api(route,options={}){
 const response=await fetch(url+route,{...options,headers:{Origin:url,'Content-Type':'application/json',...options.headers}});
 assert(response.ok,await response.clone().text());return response.json();
}
const source='Mai mở cửa thư viện. Nam xếp sách lên kệ. Cô giáo ghi nhận việc giúp đỡ của hai bạn.';
const capabilities=await api('/api/status');
const before=await api('/api/kv?key=state'),state=before.value||{exams:[],prefs:[]};
const exam=blank('Ngữ văn',[]),docId=uid();
exam.title='KIỂM THỬ BẰNG MODEL GIẢ LẬP';exam.grade='8';
exam.matrix=[{topic:'Đọc hiểu',targets:[1,1,0]}];exam.matrixConfirmed=true;
exam.docs=[{id:docId,kind:'text',version:1,name:'Nguồn giả lập',text:source,pages:[{number:1,text:source}]}];
exam.assistantSources=[docId];state.exams.push(exam);state.current=exam.id;
await api('/api/kv',{method:'PUT',headers:{'If-Match':String(before.revision)},body:JSON.stringify({key:'state',value:state})});
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 if(destinationOnly)await page.route('**/api/status',async route=>{
  const response=await route.fetch(),status=await response.json();
  await route.fulfill({json:{...status,aiProvider:'gemini',model:'GIA_LAP_GEMINI'}});
 });
 await page.goto(url);await page.waitForLoadState('networkidle');
 await page.locator('[data-action="account"]').first().click();
 assert((await page.locator('#dialog').textContent()).includes('Dữ liệu trên máy'));
 await page.locator('#dialog [data-action="close"]').click();
 await page.locator('[data-action="connections"]').first().click();
 if(capabilities.config?.gemini)await page.locator('#connections-form').waitFor();
 else await page.getByRole('heading',{name:'AI trên máy'}).waitFor();
 if(capabilities.fixture){
  const form=page.locator('#connections-form');
  await form.locator('[name="route-generate"]').selectOption('gemini');
  await form.locator('[name="route-check"]').selectOption('gemini');
  await form.locator('[name="gemini-model"]').selectOption('gemini-3.5-flash-lite');
  await form.locator('[name="gemini-check-model"]').selectOption('gemini-3.6-flash');
  await form.locator('[name="gemini-key"]').fill('fake-key-only-for-ui-fixture');
  await form.locator('[name="gemini-free-tier"]').check();
  await form.getByText('Cài đặt nâng cao',{exact:true}).click();
  await form.locator('[name="max-model-calls"]').fill('16');
  const saved=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/config')&&r.request().method()==='POST'),form.locator('button[type="submit"]').click()]);
  const settings=await saved[0].json();assert.equal(settings.gemini.checkModel,'gemini-3.6-flash');assert.equal(settings.runBudget.maxModelCalls,16);
  assert.equal(await form.locator('[name="gemini-key"]').inputValue(),'');
  await form.locator('[name="gemini-clear-key"]').check();
  await form.locator('[name="route-generate"]').selectOption('ollama');
  await form.locator('[name="route-check"]').selectOption('ollama');
  await form.locator('[name="max-model-calls"]').fill('24');
  const reset=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/config')&&r.request().method()==='POST'),form.locator('button[type="submit"]').click()]);
  assert.equal((await reset[0].json()).gemini.hasKey,false);
 }
 await page.locator('#dialog [data-action="close"]').click();
 await page.locator('[data-action="menu"][data-menu="file"]').click();
 await page.getByRole('menuitem',{name:'Tạo đề từ tài liệu'}).click();
 await page.locator('.matrix-chat-session').waitFor();
 await page.locator('#matrix-consent').waitFor();
 assert(capabilities.fixture);assert((await page.locator('.matrix-chat-session').textContent()).includes(destinationOnly?'GIA_LAP_GEMINI':capabilities.model));
 if(destinationOnly){
  assert((await page.locator('#matrix-consent').locator('xpath=..').textContent()).includes('Gemini API của Google'));
  assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(out,'result.json'),JSON.stringify({mode:'ui_destination_fixture',providerLabel:'Gemini API của Google',sourceSubmitted:false,pageErrors:errors},null,2));
  console.log('Nhãn gửi nguồn hiển thị Gemini; chưa gửi nguồn hoặc gọi model.');
 }else{
 await page.locator('#matrix-consent').check();
 await page.locator('#matrix-start').click();
 if(expectFailure){
  await page.getByText('Chưa hoàn tất.',{exact:false}).waitFor();
  const unchanged=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);
  const latest=await api('/api/exams/'+exam.id+'/proposals/latest');
  const trace=await api('/api/exams/'+exam.id+'/proposals/'+latest.jobId+'/trace');
  assert.equal(latest.errorCode,'call_budget');
  const attempts=trace.filter(e=>e.event==='generation_result').length;
  assert(attempts>2);
  assert.equal(unchanged.revision,1);assert.equal(unchanged.questions.length,0);
  assert(await page.locator('#matrix-confirm-save').isDisabled());
  assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(out,'result.json'),JSON.stringify({mode:'fixture_no_real_ai',errorCode:'call_budget',attempts,revision:1,questionCount:0,saveBlocked:true,pageErrors:errors},null,2));
  console.log('Giao diện giả lập: hết ngân sách, chặn lưu và giữ nguyên bản đề.');
 }else if(cancel){
  await page.locator('#matrix-composer-stop:not([disabled])').waitFor();
  await page.locator('#matrix-composer-stop').click();
  await page.getByText('Đã dừng. Đề được giữ nguyên.',{exact:false}).waitFor();
  const unchanged=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);
  assert.equal(unchanged.revision,1);assert.equal(unchanged.questions.length,0);
  assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(out,'result.json'),JSON.stringify({mode:'fixture_no_real_ai',cancelled:true,revision:1,questionCount:0,pageErrors:errors},null,2));
  console.log('Giao diện giả lập: dừng giữa tác vụ giữ nguyên bản đề.');
  process.exitCode=0;
 }else{
 await page.locator('[data-matrix-question]').first().waitFor({timeout:30000});await page.locator('#matrix-result-details').evaluate(n=>n.open=true);
 assert.equal(await page.locator('[data-matrix-question]').count(),2);
 assert((await page.locator('#matrix-checks').textContent()).includes('Bốn phương án'));
 assert((await page.locator('#matrix-checks').textContent()).includes('Mã bản:'));
 const latest=await api('/api/exams/'+exam.id+'/proposals/latest');
 const checkReport=await api('/api/exams/'+exam.id+'/proposals/'+latest.jobId+'/report');
 assert.equal(checkReport.checks.length,10);
 assert(checkReport.checks.every(r=>r.status==='PASS'&&r.candidateHash===checkReport.candidateHash));
 await fs.writeFile(path.join(out,'checks.json'),JSON.stringify(checkReport,null,2));
 await page.locator('#matrix-checks summary').click();
 await page.locator('#matrix-checks').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(out,'02-bao-cao-kiem.png'),fullPage:true});
 const unchanged=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);
 assert.equal(unchanged.revision,1);assert.equal(unchanged.questions.length,0);
 const [reviewPack]=await Promise.all([page.waitForEvent('download'),page.locator('#matrix-review-pack').click()]);
 const reviewPath=path.join(out,'phieu-ra-doc-lap.zip');await reviewPack.saveAs(reviewPath);
 assert((await fs.readFile(reviewPath)).subarray(0,2).equals(Buffer.from('PK')));
 assert((await page.locator('#matrix-audit').textContent()).includes('Chưa xác minh'));
 if(stale){
  const latest=await api('/api/kv?key=state');
  const edited=latest.value.exams.find(e=>e.id===exam.id);
  edited.revision++;edited.title='Bản sửa trong lúc chờ xác nhận';
  await api('/api/kv',{method:'PUT',headers:{'If-Match':String(latest.revision)},body:JSON.stringify({key:'state',value:latest.value})});
  await page.locator('#matrix-confirm-save').click();
  await page.waitForFunction(()=>document.querySelector('#matrix-status')?.textContent.includes('đã thay đổi'));
  const saved=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);
  assert.equal(saved.revision,2);assert.equal(saved.questions.length,0);
  assert.equal(saved.title,'Bản sửa trong lúc chờ xác nhận');assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(out,'result.json'),JSON.stringify({mode:'fixture_no_real_ai',staleRejected:true,revision:2,questionCount:0,humanEditPreserved:true,pageErrors:errors},null,2));
  console.log('Giao diện giả lập: từ chối đề xuất cũ và giữ bản sửa mới.');
 }else{
 await page.locator('#matrix-result-details').evaluate(n=>n.open=true);await page.locator('#matrix-reviewer').fill('Người kiểm thử fixture');
 let review=page.locator('[data-matrix-review="0"]');
 await review.locator('xpath=..').locator('summary').click();
 await review.locator('select').selectOption('1');
 await review.locator('input[name="reason"]').fill('Mức nhận thức chưa phù hợp.');
 await review.locator('button').click();
 await review.locator('output').getByText('Mức chưa phù hợp.',{exact:false}).waitFor();
 await page.reload();await page.waitForLoadState('networkidle');
 await page.locator('[data-action="menu"][data-menu="view"]').click();
 await page.locator('[data-action="matrix"]').first().click();
 await page.locator('#open-matrix-synthesis').click();
 await page.locator('[data-matrix-question]').first().waitFor();await page.locator('#matrix-result-details').evaluate(n=>n.open=true);
 review=page.locator('[data-matrix-review="0"]');
 await review.locator('xpath=..').locator('summary').click();
 assert.equal(await review.locator('input[name="reason"]').inputValue(),'Mức nhận thức chưa phù hợp.');
 assert(await page.locator('#matrix-confirm-save').isDisabled());
 await review.locator('select').selectOption('0');
 await review.locator('input[name="contentOk"]').check();
 await review.locator('button').click();
 await review.locator('output').getByText('Đã ghi nhận.',{exact:false}).waitFor();
 await page.screenshot({path:path.join(out,'01-xem-truoc-gia-lap.png'),fullPage:true});
 await page.locator('#matrix-confirm-save').click();
 await page.locator('.matrix-document-preview').waitFor({state:'detached'});
 const saved=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);
 assert.equal(saved.revision,2);assert.equal(saved.questions.length,2);
 assert.equal(saved.quote.text,source);assert.equal(saved.undo.at(-1).state.questions.length,0);
 await page.reload();await page.waitForLoadState('networkidle');
 await page.getByText('Câu giả lập 0?',{exact:true}).first().waitFor();
 assert.deepEqual(errors,[]);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({mode:'fixture_no_real_ai',examId:exam.id,revisionBefore:1,revisionAfter:2,questionCount:2,sourceRestored:true,undoPresent:true,reloadPreserved:true,pageErrors:errors},null,2));
 console.log('Giao diện giả lập: tự sửa, xem trước, xác nhận, lưu và tải lại đều đạt.');
 }
 }
 }
}finally{await browser.close();}
