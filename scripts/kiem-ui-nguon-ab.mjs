import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {Document, Packer, Paragraph} from 'docx';
import JSZip from 'jszip';
import PptxGenJS from 'pptxgenjs';
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
 await picker.locator('[name=book]').selectOption('Đại số THCS');
 await picker.locator('[name=volume]').selectOption('Tập 1');
 assert.equal(await picker.locator('[data-lesson-collection]').count(),1);
 const chapter=picker.locator('fieldset').filter({has:page.getByText('Phương trình và hệ phương trình',{exact:true})});
 await picker.locator('[name=query]').fill('giai he bang phep the');
 const volume=picker.getByRole('checkbox',{name:/Chọn cả tập/});
 await volume.check();
 await picker.locator('[name=query]').fill('');
 assert.equal(await picker.locator('[name=lesson]:checked').count(),await picker.locator('[name=lesson]').count());
 await volume.uncheck();
 assert.equal(await picker.locator('[name=lesson]:checked').count(),0);
 await chapter.getByRole('checkbox',{name:'Chọn cả chương',exact:true}).check();
 await picker.locator('[name=query]').fill('giai he bang phep the');
 await picker.getByText('Giải hệ bằng phép thế',{exact:true}).waitFor();
 assert.equal(await picker.locator('[name=lesson]:checked').count(),1);
 await picker.getByText('Xem học liệu',{exact:true}).click();
 assert.match(await picker.locator('details[open]').innerText(),/Mục tiêu/);
 await page.screenshot({path:path.join(out,'bo-chon-hoc-lieu.png')});
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
 if(!await page.locator('[data-ux-action="attach"]').isVisible())await page.locator('[data-action="toggle-ai"]').first().click();
 await page.locator('[data-ux-action="attach"]').click();
 await page.locator('.ux-attach-menu [data-action="assistant-sources"]').click();
 await dialog.getByRole('button',{name:'Học liệu theo bài',exact:true}).click();
 const personal=dialog.locator('#personal-lesson-form');
 await dialog.getByText('Thêm học liệu cá nhân',{exact:true}).click();
 for(const [field,value] of Object.entries({
  grade:'8',subject:'Ngữ văn',series:'Ngữ liệu lớp học',volume:'Tập 2',
  chapter:'Đọc hiểu',lesson:'Thư viện',title:'Nhật ký đọc sách QA',
  content_excerpt:'Nội dung bản nháp cần giữ cho tới lúc áp dụng trang.',
 }))await personal.locator('[name='+field+']').fill(value);
 const file=personal.getByLabel('Đọc tệp tại máy');
 const textPreview=personal.getByLabel('Văn bản đã đọc');
 const excerpt=personal.getByLabel('Nội dung học liệu');
 const originalDraft=await excerpt.inputValue();
 const openFile=async(name,mimeType,buffer)=>{
  const read=page.waitForResponse(response=>response.url()===base+'/api/extract');
  await file.setInputFiles({name,mimeType,buffer});
  const response=await read;
  assert(response.ok(),await response.text());
  assert.equal(response.request().postDataJSON().consent,undefined);
  await textPreview.waitFor();
 };
 await openFile('Giao-an.txt','text/plain',Buffer.from('Văn bản giáo án tự soạn QA.'));
 assert.match(await textPreview.inputValue(),/giáo án tự soạn QA/);
 assert.equal(await excerpt.inputValue(),originalDraft);
 await openFile('Giao-an.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  await Packer.toBuffer(new Document({sections:[{children:[new Paragraph('Mục tiêu giáo án Word QA.')]}]})));
 assert.match(await textPreview.inputValue(),/giáo án Word QA/);
 assert.equal(await excerpt.inputValue(),originalDraft);
 const pdf=execFileSync(process.env.QA_PYTHON||'python',[
  '-c','import sys;from test_source_documents import pdf;sys.stdout.buffer.write(pdf("First page outside scope","Card reading plan QA"))',
 ]);
 await openFile('Giao-an.pdf','application/pdf',pdf);
 await personal.getByLabel('Trang hoặc slide').selectOption('2');
 assert.match(await textPreview.inputValue(),/Card reading plan QA/);
 assert.equal(await excerpt.inputValue(),originalDraft);
 const deck=new PptxGenJS();
 deck.layout='LAYOUT_WIDE';
 deck.addSlide().addText('Chi tiết ngoài đoạn chọn. Học liệu trích từ slide QA.',{
  x:1,y:1,w:10,h:1,margin:0,isTextBox:true,fontSize:24,
 });
 deck.addSlide().addText('Slide mở đầu sau khi đổi thứ tự.',{
  x:1,y:1,w:10,h:1,margin:0,isTextBox:true,fontSize:24,
 });
 deck.addSlide();
 const zip=await JSZip.loadAsync(await deck.write({outputType:'nodebuffer'}));
 const manifest='ppt/presentation.xml';
 const manifestXml=await zip.file(manifest).async('string');
 const reordered=manifestXml.replace(/(<p:sldIdLst>)(.*?)(<\/p:sldIdLst>)/s,(_,start,items,end)=>{
  const parts=items.match(/<p:sldId\b[^>]*\/>/g);
  assert.equal(parts?.length,3);
  return start+parts[1]+parts[2]+parts[0]+end;
 });
 assert.notEqual(reordered,manifestXml);
 zip.file(manifest,reordered);
 const slides=await zip.generateAsync({type:'nodebuffer'});
 await fs.writeFile(path.join(out,'Giao-an-doi-thu-tu.pptx'),slides);
 await openFile('Giao-an-doi-thu-tu.pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation',slides);
 const slideSelect=personal.getByLabel('Trang hoặc slide');
 assert.deepEqual(await slideSelect.locator('option').allTextContents(),['Slide 1','Slide 3']);
 assert.match(await textPreview.inputValue(),/Slide mở đầu sau khi đổi thứ tự/);
 await slideSelect.selectOption('3');
 const selectedExcerpt='Học liệu trích từ slide QA.';
 await textPreview.evaluate((node,text)=>{
  const start=node.value.indexOf(text);
  if(start<0)throw Error('Không thấy đoạn trích trên slide đã chọn.');
  node.focus();
  node.setSelectionRange(start,start+text.length);
 },selectedExcerpt);
 await page.screenshot({path:path.join(out,'chon-trich-doan-slide.png')});
 await personal.getByRole('checkbox').check();
 await personal.getByRole('button',{name:'Dùng phần đã đọc'}).click();
 assert.equal(await excerpt.inputValue(),selectedExcerpt);
 assert.equal(await personal.getByLabel('Vị trí trích dẫn').inputValue(),'Slide 3');
 assert.equal(await personal.getByRole('checkbox').isChecked(),false);
 await personal.getByRole('checkbox').check();
 await personal.getByRole('button',{name:'Lưu học liệu'}).click();
 const privateCard=picker.locator('[data-lesson-collection]').filter({hasText:'Nhật ký đọc sách QA'});
 await privateCard.getByRole('checkbox',{name:'Dùng học liệu này'}).check();
 await privateCard.getByText('Xem học liệu',{exact:true}).click();
 assert.match(await privateCard.locator('details[open]').innerText(),/Học liệu trích từ slide QA/);
 await page.screenshot({path:path.join(out,'kho-hoc-lieu-ca-nhan.png')});
 await Promise.all([write(),picker.getByRole('button',{name:'Dùng bài đã chọn'}).click()]);
 const withPrivate=(await saved()).value.exams[0];
 const privateDoc=withPrivate.docs.find(d=>d.personalLesson);
 const recordResponse=await page.request.get(base+'/api/lesson-catalog/sources/'+privateDoc.id);
 assert(recordResponse.ok());
 const record=await recordResponse.json();
 assert.equal(record.source_origin,'Giao-an-doi-thu-tu.pptx');
 assert.equal(record.locator,'Slide 3');
 assert.equal(record.content_excerpt,selectedExcerpt);
 assert.equal(privateDoc.sourceLocator,'Slide 3');
 assert.ok(privateDoc.version>0);
 assert.deepEqual(withPrivate.assistantSourcePages[privateDoc.id],[1]);
 assert.deepEqual(withPrivate.assistantSourcePages[algebra.id],[1,2,3]);
 await page.locator('[data-ux-action="attach"]').click();
 await page.locator('.ux-attach-menu [data-action="assistant-sources"]').click();
 const attachedSource=dialog.locator('[data-source-group]').filter({hasText:'Nhật ký đọc sách QA'});
 await attachedSource.getByText('Xem và chọn từng trang',{exact:true}).click();
 assert.match(await attachedSource.getByText(/Slide 3/).innerText(),/Slide 3/);
 assert.equal(await attachedSource.getByText(/Trang 1/).count(),0);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({
  scenario:'IT-09',previewReadOnly:true,sourceIdPreserved:true,linkedPageOpened:true,
  chosenQuotePreserved:true,answerPreserved:true,relatedApprovalInvalidated:true,
  unrelatedQuestionUnchanged:true,sourcePageEdited:2,sourceVersion:2,mobileReload:true,fixture:true,
  lessonPicker:{chapter:3,individual:1,accentInsensitiveSearch:true,selectionPersisted:true,wholeVolumeWithActiveSearch:true,personalSourceCreatedAndAttached:true,personalImportFormats:['TXT','DOCX','PDF','PPTX'],previewedPdfPage:2,selectedReorderedSlide:3,selectedExcerptOnly:true,originalLocationShownAfterAttach:true,personalImportNoAiConsent:true},
 },null,2));
} finally {
 await browser.close();
}
