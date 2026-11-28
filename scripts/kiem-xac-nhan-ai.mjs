// Xác nhận dữ liệu thử từ đề xuất AI thật đã hoàn tất. Đây là kiểm phần mềm, không duyệt sư phạm.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';

const [examId,jobId]=process.argv.slice(2);
assert(examId&&jobId&&process.argv.includes('--confirm-test'),'Cần examId jobId --confirm-test; chỉ dùng đề thử của nhóm.');
const url=process.env.POC_URL||'http://127.0.0.1:4182';
const out=path.resolve(process.env.POC_OUTPUT||'outputs/local-demo/real-confirm-'+jobId);
await fs.mkdir(out,{recursive:true});
async function api(route){const r=await fetch(url+route);assert(r.ok,await r.clone().text());return r.json();}
const info=await api('/api/status'),before=(await api('/api/kv?key=state')).value;
assert.equal(before.current,examId,'Mở đúng đề thử trước khi kiểm, tránh đổi đề người dùng đang mở.');
const original=before.exams.find(e=>e.id===examId),base='/api/exams/'+examId+'/proposals/'+jobId;
const pending=await api(base+'/status');
assert.equal(pending.status,'complete');assert.equal(original.revision,pending.baseRevision);
assert.equal(original.questions.length,0,'Ca này yêu cầu đề thử trống trước xác nhận.');
const latest=await api('/api/exams/'+examId+'/proposals/latest');
assert.equal(latest.jobId,jobId);
assert.equal(pending.proposal.questions.length,4);
assert.equal(pending.proposal.questions.reduce((n,q)=>n+q.pointsQ4,0),40);
for(const q of pending.proposal.questions)for(const e of q.evidence)assert(latest.input.sourceText.includes(e.quote));
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);await page.waitForLoadState('networkidle');
 await page.locator('[data-action="menu"][data-menu="view"]').click();
 await page.locator('[data-action="matrix"]').first().click();
 await page.locator('#open-matrix-synthesis').click();
 await page.locator('[data-matrix-question]').first().waitFor();
 assert.equal(await page.locator('[data-matrix-question]').count(),4);
 await page.screenshot({path:path.join(out,'01-xem-truoc.png'),fullPage:true});
 await page.locator('#matrix-confirm-save').click();
 await page.locator('.matrix-document-preview').waitFor({state:'detached'});
 const saved=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===examId);
 assert.equal(saved.revision,original.revision+1);assert.equal(saved.questions.length,4);
 assert.equal(saved.quote.text,latest.input.sourceText);assert.equal(saved.undo.at(-1).state.questions.length,0);
 assert.deepEqual(saved.questions.map(q=>({stem:q.stem,options:q.options,answer:q.answer})),pending.proposal.questions.map(q=>({stem:q.stem,options:q.options,answer:q.answer})));
 await page.reload();await page.waitForLoadState('networkidle');
 assert.equal(await page.locator('.question').count(),4);
 await page.screenshot({path:path.join(out,'02-da-luu-tai-lai.png'),fullPage:true});
 const exports=[];
 for(const [format,teacher] of [['html',false],['html',true],['docx',false],['pdf',false]]){
  await page.locator('[data-action="export"]').first().click();
  await page.locator(`[data-action="export-file"][data-format="${format}"][data-teacher="${teacher}"]`).click();
  const link=page.locator('.saved-export-link');await link.waitFor();
  const response=await fetch(url+await link.getAttribute('href')),data=Buffer.from(await response.arrayBuffer());
  assert(response.ok);
  if(format==='html'){
   const html=data.toString('utf8');assert(html.includes(saved.questions[0].stem));
   assert.equal(html.includes('Hướng dẫn chấm'),teacher);
   assert.equal(html.includes('Đáp án '+String.fromCharCode(65+saved.questions[0].answer)+'.'),teacher);
  }else assert(data.subarray(0,format==='pdf'?5:2).equals(Buffer.from(format==='pdf'?'%PDF-':'PK')));
  await fs.writeFile(path.join(out,(teacher?'giao-vien':'hoc-sinh')+'.'+format),data);
  exports.push({format,teacher,bytes:data.length});
  await page.locator('#dialog [data-action="close"]').click();
 }
 await page.locator('[data-action="undo"]').first().click();
 await page.waitForFunction(()=>document.querySelectorAll('.question').length===0);
 await page.locator('[data-action="redo"]').first().click();
 await page.waitForFunction(()=>document.querySelectorAll('.question').length===4);
 await page.waitForLoadState('networkidle');
 const redone=(await api('/api/kv?key=state')).value.exams.find(e=>e.id===examId);
 assert.deepEqual(redone.questions.map(q=>q.id),saved.questions.map(q=>q.id));
 assert.deepEqual(errors,[]);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({mode:process.argv.includes('--saved-output')?'saved_real_ai_output_regression':'real_ai_proposal_software_confirmation_test',examId,jobId,provider:info.aiProvider,model:info.model,beforeRevision:original.revision,afterRevision:saved.revision,questions:4,points:10,sourcePreserved:true,undoPresent:true,undoRedoPreservesIds:true,reloadPreserved:true,studentTeacherExports:true,exports,pedagogicalApproval:false,pageErrors:errors},null,2));
 console.log('Đã kiểm xem trước, xác nhận dữ liệu thử, lưu, tải lại và xuất HTML từ đề xuất AI thật.');
}finally{await browser.close();}
