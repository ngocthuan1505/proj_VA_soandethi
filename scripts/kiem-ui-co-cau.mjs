import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';

const base=process.env.POC_URL||'http://127.0.0.1:4183';
const out=path.resolve(process.argv[2]||'outputs/qa-co-cau');
assert((await (await fetch(base+'/api/status')).json()).fixture);
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 const page=await browser.newPage({viewport:{width:1366,height:830}});
 page.setDefaultTimeout(30000);
 await page.goto(base);
 // Đợi bàn soạn dựng xong câu hỏi trước khi chờ initMVP tự lưu ID khối.
 await page.locator('.paper .question').first().waitFor({timeout:30000});
 await page.locator('#chat-input').waitFor({timeout:30000});
 const saved=async()=>{
  const response=await page.request.get(base+'/api/kv?key=state');
  assert(response.ok());
  const {value}=await response.json();
  return value.exams.find(e=>e.id===value.current);
 };
 const getContent=e=>({questions:e.questions,matrix:e.matrix,title:e.title});
 // Đề mẫu thêm ID khối qua autosave khi bàn soạn tải lần đầu.
 await page.waitForFunction(async()=>{
  const response=await fetch('/api/kv?key=state');
  if(!response.ok)return false;
  const {value}=await response.json();
  const current=value?.exams?.find(e=>e.id===value.current);
  return Boolean(current?.questions?.length&&current.questions.every(q=>q.blockIds?.stem));
 },undefined,{polling:150,timeout:30000});
 await page.waitForFunction(
  ()=>/^Đã lưu/.test(document.querySelector('[data-save-status]')?.textContent||''),
  undefined,
  {timeout:30000},
 );
 const initial=getContent(await saved());
 const requests=[];
 page.on('request',r=>{if(r.url()===base+'/api/ai/exam-plan')requests.push(r.postDataJSON());});
 const original='Tạo một đề Toán lớp 5 cuối kì.';
 const edited='Tạo một đề Toán lớp 5 cuối kì, ưu tiên phân số.';
 await page.locator('#chat-input').fill(original);
 await page.locator('#chat-form [type="submit"]').click();
 const quick=page.locator('.quick-exam-plan');
 await quick.waitFor();
 assert.equal(await quick.locator('[name=count]').inputValue(),'');
 assert.equal(await quick.locator('[name=minutes]').inputValue(),'');
 assert.equal(requests.length,0);
 await quick.locator('[name=request]').fill(edited);
 await quick.locator('[name=consent]').check();
 await quick.getByRole('button',{name:'Đề xuất đề phù hợp',exact:true}).click();
 await page.getByRole('heading',{name:'Cơ cấu đề xuất · 4 câu/ý · 10 điểm',exact:true}).waitFor();
 assert.equal(requests[0].request,edited);
 assert.deepEqual(getContent(await saved()),initial);
 const persisted=page.waitForResponse(r=>{
  if(r.url()!==base+'/api/kv'||r.request().method()!=='PUT'||!r.ok())return false;
  const payload=r.request().postDataJSON();
  return payload.key==='state'&&payload.value.exams.some(e=>e.generationRequest===edited);
 });
 await page.getByRole('button',{name:'Dùng gợi ý này',exact:true}).click();
 await persisted;
 const confirmed=await saved();
 assert.equal(confirmed.generationRequest,edited);
 assert(confirmed.matrixConfirmed);
 assert.deepEqual(confirmed.questions,initial.questions);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({
  scenario:'IT-03',fixture:true,autoCountAndTime:true,previewKeptExam:true,
  editedRequestUsed:true,confirmedMatrix:true,questionsUnchanged:true,
 },null,2));
} finally {
 await browser.close();
}
