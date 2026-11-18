// Kiểm lại đúng mẫu Sinh học qua UI chat. --live chỉ dùng app QA riêng có key được cấp.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {blank,uid} from '../core.js';

const live=process.argv.includes('--live');
const base=process.env.POC_URL||(live?'http://127.0.0.1:4184':'http://127.0.0.1:4183');
assert(['http://127.0.0.1:4183','http://127.0.0.1:4184'].includes(base),'Chỉ chạy trên app QA riêng.');
const out=path.resolve(process.env.POC_OUTPUT||'outputs/local-demo/poc-regression-15-11-2026/'+(live?'live-ui':'bio-ui'));
await fs.mkdir(out,{recursive:true});
const request=async(url,body,method='POST')=>{
 const r=await fetch(base+url,body===undefined?{}:{method,headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)});
 const data=await r.json();assert(r.ok,JSON.stringify(data));return data;
};
const status=await request('/api/status');assert.equal(status.fixture,!live);
let cases=live?[['live',null]]:[['repair','answer_disagreement'],['missing_question','invalid_plan'],['multiple_correct','option_verdicts_failed'],['unsupported','unsupported_answer'],['unknown','uncertain_answer'],['wrong_level','level_disagreement'],['duplicate','semantic_duplicate'],['budget','call_budget'],['cancel',null],['stale_exam',null],['stale_source',null],['feedback','answer_disagreement']];
const selectedCase=process.argv.find(a=>a.startsWith('--case='))?.slice(7);
if(selectedCase)cases=cases.filter(([name])=>name===selectedCase);
assert(cases.length,'Ca kiểm không tồn tại.');
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const results=[];
try{
 for(const [name,expectedError] of cases){
  const directory=path.join(out,name);await fs.mkdir(directory,{recursive:true});
  if(!live)await request('/qa/scenario',{case:name.startsWith('stale_')||name==='feedback'?'repair':name});
  const sample=await request('/api/poc/sample');assert.equal(sample.subject,'Sinh học');
  const exam=blank(sample.subject,[]),doc=uid();
  Object.assign(exam,{title:(live?'AI THẬT':'FIXTURE')+' · Kiểm lại PoC Sinh học R4',grade:sample.grade,matrix:sample.matrix,matrixConfirmed:true,aiInstructions:sample.instructions,chat:[],docs:[{id:doc,name:'S1–S3 · Ngữ liệu nhóm tự viết',kind:'text',version:1,text:sample.text}],assistantSources:[doc]});
  const before=await request('/api/kv?key=state'),state=before.value||{exams:[],prefs:[]};
  state.exams.push(exam);state.current=exam.id;
  await request('/api/kv',{key:'state',value:state},'PUT');
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.goto(base);await page.waitForLoadState('networkidle');
   await page.locator('#chat-input').fill('Soạn đề theo ma trận này');await page.locator('#chat-form button[type=submit]').click();
   await page.locator('#matrix-source-text').waitFor();assert.equal(await page.locator('#dialog[open]').count(),0);
   assert.equal(await page.locator('#matrix-source-text').inputValue(),sample.text);
   await page.locator('#matrix-request-settings').evaluate(n=>n.open=true);await page.locator('#matrix-inputs').evaluate(n=>n.open=true);await page.locator('#matrix-consent').check();
   const submitted=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/proposals/generate'));
   const started=performance.now();await page.locator('#matrix-request-settings').evaluate(n=>n.open=true);await page.locator('#matrix-start').click();
   const submission=await (await submitted).json();assert.equal(submission.status,'running');
   const prefix='/api/exams/'+exam.id+'/proposals/'+submission.jobId;
   if(name==='cancel'){await page.locator('#matrix-composer-stop').waitFor();await page.locator('#matrix-composer-stop').click();}
   let job,lastPrint=0;
   do{
    job=await request(prefix+'/status');
    if(job.status!=='running')break;
    if(live&&performance.now()-lastPrint>10000){console.log(JSON.stringify({case:name,jobId:job.jobId,stage:await page.locator('#matrix-status').innerText()}));lastPrint=performance.now();}
    await page.waitForTimeout(live?1500:250);
   }while(performance.now()-started<930000);
   assert.notEqual(job.status,'running');
   await page.waitForFunction(()=>!document.querySelector('#matrix-start').disabled,{},{timeout:10000});
   const trace=await request(prefix+'/trace'),report=await request(prefix+'/report');
   const latest=await request('/api/exams/'+exam.id+'/proposals/latest');
   let saved=(await request('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);
   assert.equal(saved.questions.length,0);assert.equal(saved.revision,exam.revision);
   const item={case:name,mode:live?'real_ai_new_generation':'fixture_no_real_ai',examId:exam.id,jobId:job.jobId,status:job.status,errorCode:job.errorCode||null,seconds:(performance.now()-started)/1000,modelCalls:report.summary?.modelCalls||0,questions:job.proposal?.questions.length||0,baseRevision:exam.revision,savedBeforeConfirmation:false,pageErrors:errors};
   if(job.status==='complete'){
    assert.equal(job.proposal.questions.length,4);
    assert.deepEqual(job.proposal.questions.map(q=>q.level),[0,1,0,2]);
    assert.deepEqual(job.proposal.questions.map(q=>q.pointsQ4),[10,10,10,10]);
    assert.equal(report.checks.length,10);assert(report.checks.every(r=>r.status==='PASS'&&r.candidateHash===report.candidateHash));
    await page.locator('.matrix-document-preview [data-matrix-question]').first().waitFor();await page.locator('#matrix-result-details').evaluate(n=>n.open=true);
    assert.equal(await page.locator('[data-matrix-question]').count(),4);
    assert(!(await page.locator('#matrix-confirm-save').isDisabled()));
    item.previewOnDocument=true;item.allChecksPassed=true;
    const audit=await request(prefix+'/audit');await fs.writeFile(path.join(directory,'audit.json'),JSON.stringify(audit,null,2));
    item.traceVerified=audit.traceVerified;item.actualRepairObserved=audit.successfulRepairObserved;
    if(!live){
     const reports=trace.filter(t=>t.event==='generation_result');
     assert(reports.length>=2);assert(reports[0].errors.some(e=>e.code===expectedError)||name.startsWith('stale_'));
     item.errorReceivedThenRechecked=true;
    }
    if(name.startsWith('stale_')){
     if(name==='stale_exam'){
      const current=await request('/api/kv?key=state');const changed=current.value.exams.find(e=>e.id===exam.id);
      changed.revision++;changed.title='Bản người dùng sửa · giữ lại';
      await request('/api/kv',{key:'state',value:current.value},'PUT');
     }else await request('/api/exams/'+exam.id+'/matrix/approve',{baseRevision:exam.revision,sourceText:sample.text+'\nNguồn mới của người dùng.',sourceName:'Nguồn mới'});
     const current=await request('/api/kv?key=state');
     await page.locator('#matrix-confirm-save').click();
     await page.waitForTimeout(500);
     saved=(await request('/api/kv?key=state')).value.exams.find(e=>e.id===exam.id);
     assert.deepEqual(saved,current.value.exams.find(e=>e.id===exam.id));item.staleRejected=true;
    }else{
     const pack=page.waitForEvent('download');await page.locator('#matrix-review-pack').click();await (await pack).saveAs(path.join(directory,'phieu-ra.zip'));
     const log=page.waitForEvent('download');await page.locator('#matrix-download').click();await (await log).saveAs(path.join(directory,'log-ui.json'));
     item.reviewPackDownloaded=true;item.logDownloaded=true;
    }
    if(name==='feedback'){
     const reason='Góp ý fixture: cần viết lại câu 1 để kiểm luồng nhận xét, không phải nhãn sư phạm.';
     await page.locator('#matrix-reviewer').fill('QA phần mềm');
     const form=page.locator('[data-matrix-review="0"]');await form.locator('xpath=..').locator('summary').click();
     await form.locator('[name=observed]').selectOption('2');await form.locator('[name=reason]').fill(reason);
     await form.locator('button[type=submit]').click();await page.waitForFunction(()=>document.querySelector('#matrix-confirm-save').disabled);
     const submittedAgain=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/proposals/generate'));
     await page.locator('#matrix-request-settings').evaluate(n=>n.open=true);await page.locator('#matrix-start').click();const next=await (await submittedAgain).json();assert.notEqual(next.jobId,job.jobId);
     await page.locator('.matrix-document-preview').waitFor();await page.waitForFunction(()=>!document.querySelector('#matrix-start').disabled);
     const followup=await request('/api/exams/'+exam.id+'/proposals/latest');
     assert.equal(followup.status,'complete');assert(followup.input.approval.plan.instructions.includes(reason));
     item.feedbackBlocksSave=true;item.feedbackForwardedToNextRun=true;item.followupJobId=next.jobId;
     await fs.writeFile(path.join(directory,'followup.json'),JSON.stringify(followup,null,2));
    }
   }else{
    assert(await page.locator('#matrix-confirm-save').isDisabled());
    assert.equal(await page.locator('.matrix-document-preview').count(),0);
    if(name==='cancel')assert.equal(job.status,'cancelled');
    else if(!live){assert.equal(job.errorCode,expectedError);assert(trace.filter(t=>t.event==='generation_result').length>2);}
    item.partialSaveBlocked=true;
   }
   assert.deepEqual(errors,[]);
   await page.screenshot({path:path.join(directory,'ui.png')});
   for(const [file,data] of Object.entries({result:item,job,trace,report,latest}))await fs.writeFile(path.join(directory,file+'.json'),JSON.stringify(data,null,2));
   results.push(item);console.log(JSON.stringify(item));
  }finally{await page.close();}
 }
}finally{
 await browser.close();await fs.writeFile(path.join(out,'summary.json'),JSON.stringify({mode:live?'real_ai_new_generation':'fixture_no_real_ai',results},null,2));
}
