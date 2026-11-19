import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {approveQuestion, check, sample} from '../core.js';
import {ensureBlocks} from '../blocks.js';

const base=process.env.POC_URL||'http://127.0.0.1:4183';
const out=path.resolve(process.argv[2]||'outputs/qa-nguon-ab');
await fs.mkdir(out,{recursive:true});

async function api(route, body) {
 const response=await fetch(base+route, body ? {
  method:'PUT', headers:{Origin:base,'Content-Type':'application/json','If-Match':'0'},
  body:JSON.stringify(body),
 } : {});
 assert(response.ok, await response.clone().text());
 return response.json();
}
assert((await api('/api/status')).fixture);
const savePath='/api/kv';
const saved=()=>api(savePath+'?key=state');
const exam=sample('Ngữ văn');
const doc=exam.docs[0];
const [,variant]=exam.quote.versions;
variant.page=2;
doc.version=1;
doc.pages=[{number:1,text:exam.quote.text},{number:2,text:variant.text}];
exam.questions[0].source.page=1;
exam.questions[2].quote=false;
exam.questions[2].source=null;
ensureBlocks(exam);
exam.questions.forEach(q=>{check(exam,q);approveQuestion(q,1);});
await api(savePath,{key:'state',value:{exams:[exam],prefs:[],current:exam.id}});
const browser=await chromium.launch({
 executablePath:process.env.BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',
 headless:true,
});
try {
 const page=await browser.newPage({viewport:{width:1366,height:830}}),errors=[];
 page.setDefaultTimeout(10000);
 const dialog=page.locator('#dialog');
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base);
 await page.waitForLoadState('networkidle');
 const initial=await saved();
 const write=()=>page.waitForResponse(r=>r.url()===base+savePath&&r.request().method()==='PUT'&&r.ok());
 await page.locator('[data-action="quotes"]:visible').first().click();
 await dialog.locator('[data-action="choose-variant"][data-id="'+variant.id+'"]').click();
 await dialog.locator('.diff').waitFor();
 assert.deepEqual(await saved(),initial);
 await Promise.all([write(),dialog.getByRole('button',{name:'Xác nhận bản dùng',exact:true}).click()]);

 const chosen=(await saved()).value.exams[0];
 assert.equal(chosen.quote.chosen,variant.id);
 assert.equal(chosen.quote.text,variant.text);
 for(let i=0;i<2;i++){
  assert.equal(chosen.questions[i].id,exam.questions[i].id);
  assert.equal(chosen.questions[i].answer,exam.questions[i].answer);
  assert.equal(chosen.questions[i].source.docId,doc.id);
  assert.equal(chosen.questions[i].source.page,2);
  assert.equal(chosen.questions[i].approval,null);
 }
 assert.deepEqual(chosen.questions[2],initial.value.exams[0].questions[2]);
 await dialog.locator('[data-action="source"][data-doc="'+doc.id+'"][data-page="2"]').click();
 const form=dialog.locator('#source-text-form[data-page="2"]');
 assert.equal(await form.locator('textarea').inputValue(),variant.text);
 const edited=variant.text+' Đây là bản trích xuất đã đối chiếu.';
 await form.locator('textarea').fill(edited);
 await Promise.all([write(),form.locator('[type="submit"]').click()]);
 const updated=(await saved()).value.exams[0];
 assert.equal(updated.docs[0].id,doc.id);
 assert.equal(updated.docs[0].version,2);
 assert.equal(updated.docs[0].pages[0].text,doc.pages[0].text);
 assert.equal(updated.docs[0].pages[1].text,edited);
 assert.deepEqual(updated.quote,chosen.quote);
 assert.deepEqual(updated.questions[2],chosen.questions[2]);
 await page.setViewportSize({width:390,height:844});
 await page.reload();
 await page.waitForLoadState('networkidle');
 await page.locator('.paper .quote-box').filter({hasText:variant.text.slice(0,35)}).waitFor();
 assert.deepEqual(errors,[]);
 await page.screenshot({path:path.join(out,'mobile.png')});
 await page.setViewportSize({width:1366,height:830});
 if(!await page.locator('[data-ux-action="attach"]').isVisible())await page.locator('[data-action="toggle-ai"]').first().click();
 await page.locator('[data-ux-action="attach"]').click();
 await page.locator('.ux-attach-menu [data-action="assistant-sources"]').click();
 await dialog.getByRole('button',{name:'Học liệu theo bài',exact:true}).click();
 const picker=dialog.locator('#lesson-picker');
 await picker.locator('[name=subject]').selectOption('Toán');
 await picker.locator('[name=grade]').selectOption('9');
 const chapter=picker.locator('fieldset').filter({has:picker.getByText('Phương trình và hệ phương trình',{exact:true})});
 await chapter.getByRole('checkbox',{name:'Chọn cả chương',exact:true}).check();
 await picker.locator('[name=query]').fill('phep the');
 await picker.getByText('Giải hệ bằng phép thế',{exact:true}).waitFor();
 assert.equal(await picker.locator('[name=lesson]:checked').count(),1);
 await picker.getByText('Xem học liệu',{exact:true}).click();
 assert.match(await picker.locator('details[open]').innerText(),/Mục tiêu/);
 await picker.locator('[name=grade]').selectOption('5');
 await picker.locator('[name=query]').fill('');
 await picker.getByRole('checkbox',{name:'So sánh số thập phân'}).check();
 await Promise.all([write(),picker.getByRole('button',{name:'Dùng bài đã chọn'}).click()]);
 const library=(await saved()).value.exams[0];
 const algebra=library.docs.find(d=>d.catalog&&d.name.includes('Toán 9'));
 const arithmetic=library.docs.find(d=>d.catalog&&d.name.includes('Toán 5'));
 assert.deepEqual(library.assistantSourcePages[algebra.id],[1,2,3]);
 assert.deepEqual(library.assistantSourcePages[arithmetic.id],[1]);
 assert.deepEqual(library.docs.find(d=>d.id===doc.id),updated.docs[0]);
 await page.reload();await page.waitForLoadState('networkidle');
 assert.deepEqual((await saved()).value.exams[0].assistantSourcePages,library.assistantSourcePages);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({
  scenario:'IT-09',previewReadOnly:true,sourceIdPreserved:true,linkedPageOpened:true,
  chosenQuotePreserved:true,answerPreserved:true,relatedApprovalInvalidated:true,
  unrelatedQuestionUnchanged:true,sourcePageEdited:2,sourceVersion:2,mobileReload:true,fixture:true,
  lessonPicker:{chapter:3,individual:1,accentInsensitiveSearch:true,selectionPersisted:true},
 },null,2));
} finally {
 await browser.close();
}
