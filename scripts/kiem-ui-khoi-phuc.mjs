// Chỉ dùng hai tài khoản QA đã tạo trên app fixture4183; không gọi AI.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';

const base=process.env.POC_URL||'http://127.0.0.1:4183';
const out=path.resolve(process.argv[2]||'outputs/mvp-18-11/restore-ui');
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const context=await browser.newContext({viewport:{width:1366,height:900},acceptDownloads:true});
const page=await context.newPage(),errors=[],results=[];
page.on('pageerror',e=>errors.push(e.message));
const state=async(tab=page)=>{const r=await tab.request.get(base+'/api/kv?key=state');assert(r.ok());return r.json();};
const choose=async(buffer,tab=page)=>{
 const chooser=tab.waitForEvent('filechooser');
 await tab.locator('[data-action="import-backup"]:visible').click();
 await(await chooser).setFiles({name:'Ban-sao-QA.json',mimeType:'application/json',buffer});
};
const fileMenu=async()=>{await page.getByRole('button',{name:'Tệp',exact:true}).click();};

function wavData(sample){
 const bytes=Buffer.alloc(844,sample);
 Buffer.from('524946464403000057415645666d74201000000001000100401f0000401f0000010008006461746120030000','hex').copy(bytes);
 return 'data:audio/wav;base64,'+bytes.toString('base64');
}

async function verifyBatchAudio(template){
 const tab=await context.newPage();
 tab.on('pageerror',e=>errors.push(e.message));
 try{
  const fileId='qa-audio-trung',historyId='qa-audio-lich-su';
  const originalWav=wavData(48),incomingWav=wavData(160);
  const incoming={...structuredClone(template),id:randomUUID(),title:'Đề audio nhập từ JSON',docs:[]};
  incoming.audio={fileId,filename:'nghe.wav',mimeType:'audio/wav',maxPlays:2};
  incoming.undo=[{label:'Audio trước',state:{audio:{...incoming.audio,fileId:historyId}}}];
  Object.assign(incoming.questions[0],{
   audio:{...incoming.audio},
   stem:'Tính $\\frac{1}{2}$.',
   richDoc:{type:'doc',content:[{type:'paragraph',attrs:{id:randomUUID()},content:[
    {type:'text',text:'Tính ',marks:[{type:'bold'}]},
    {type:'mathInline',attrs:{id:randomUUID(),latex:'\\frac{1}{2}',display:false}},
    {type:'text',text:'.'},
   ]}]},
  });
  const original={...structuredClone(incoming),id:randomUUID(),title:'Đề audio có sẵn',undo:[]};
  const put=async(key,value)=>{
   const headers={Origin:base};
   if(key==='state')headers['If-Match']=String((await state(tab)).revision);
   const response=await tab.request.put(base+'/api/kv',{headers,data:{key,value}});
   assert(response.ok(),await response.text());
  };
  const useExams=async(current,exams)=>put('state',{version:1,current,exams,prefs:[]});
  const openLibrary=()=>tab.getByRole('button',{name:'Mở kho đề',exact:true}).click();
  const player=id=>tab.locator(`audio[data-audio-file-id="${id}"]`).first();
  const checkAudio=async(id,data)=>{
   await player(id).waitFor({state:'attached'});
   await tab.waitForFunction(({id,data})=>{
    const audio=document.querySelector(`audio[data-audio-file-id="${id}"]`);
    return audio?.getAttribute('src')===data&&audio.duration>0;
   },{id,data});
  };
  await put('file:'+fileId,incomingWav);
  await put('file:'+historyId,originalWav);
  await useExams(incoming.id,[incoming,template]);
  await tab.goto(base+'/#workspace');await tab.waitForLoadState('networkidle');
  await openLibrary();
  await tab.getByRole('checkbox',{name:'Chọn đề '+incoming.title,exact:true}).check();
  const filter=tab.locator('#library-filter');
  await filter.fill('Không khớp đề nào');
  assert.equal(await tab.locator('.wb-library-select').count(),0);
  const download=tab.waitForEvent('download');
  await tab.getByRole('button',{name:'Tải JSON bộ đã chọn',exact:true}).click();
  const bytes=await fs.readFile(await(await download).path());
  const batch=JSON.parse(bytes);
  assert.equal(await filter.inputValue(),'Không khớp đề nào');
  assert.deepEqual(batch.exams.map(exam=>exam.id),[incoming.id]);
  assert.deepEqual(batch.files,{[fileId]:incomingWav,[historyId]:originalWav});
  assert.equal(batch.exams[0].questions[0].stem,incoming.questions[0].stem);
  assert.deepEqual(batch.exams[0].questions[0].richDoc,incoming.questions[0].richDoc);

  await put('file:'+fileId,originalWav);
  await useExams(original.id,[original]);
  await tab.reload();await tab.waitForLoadState('networkidle');
  await checkAudio(fileId,originalWav); // Lưu audio cũ vào IndexedDB trước khi ghép lô.
  await openLibrary();await choose(bytes,tab);
  const confirm=tab.locator('[data-action="confirm-backup"]');
  await confirm.waitFor();
  // Giữ vỏ ứng dụng để reload. Chỉ cho đọc state đúng một lần để ghi cache sau POST.
  let readMergedState=false,blockedReads=0;
  await tab.route(url=>url.pathname==='/api/kv',async route=>{
   const request=route.request();
   if(!readMergedState&&request.method()==='GET'&&new URL(request.url()).searchParams.get('key')==='state'){
    readMergedState=true;
    return route.continue();
   }
   if(request.method()==='GET')blockedReads++;
   await route.abort('internetdisconnected');
  });
  const applied=tab.waitForResponse(r=>r.url()===base+'/api/workspace/restore'&&r.request().method()==='POST');
  await Promise.all([tab.waitForEvent('load'),confirm.click()]);
  assert.equal((await applied).status(),200);
  const merged=(await state(tab)).value;
  const imported=merged.exams.find(exam=>exam.id===incoming.id);
  const importedId=imported?.audio?.fileId;
  assert(importedId&&importedId!==fileId);
  await checkAudio(fileId,originalWav);
  const cachedAudio=await tab.evaluate(async examId=>{
   const {get}=await import('/storage.js');
   const {exams}=await get('state');
   const exam=exams.find(item=>item.id===examId);
   const data=await get('file:'+exam.audio.fileId);
   if(!data)return null;
   const audio=new Audio(data);
   await new Promise((resolve,reject)=>{
    audio.addEventListener('loadedmetadata',resolve,{once:true});
    audio.addEventListener('error',()=>reject(Error('Chrome chưa đọc được audio khôi phục.')),{once:true});
   });
   return {data,duration:audio.duration};
  },incoming.id);
  assert.equal(cachedAudio?.data,incomingWav);
  assert(cachedAudio.duration>0);
  assert.equal(imported.questions[0].audio.fileId,importedId);
  assert.equal(imported.questions[0].stem,incoming.questions[0].stem);
  assert.deepEqual(imported.questions[0].richDoc,batch.exams[0].questions[0].richDoc);
  assert(blockedReads>=4,'Reload và cả hai lượt đọc audio phải thiếu kết nối KV.');
 }finally{await tab.close();}
}

try{
 await page.goto(base+'/login');await page.waitForLoadState('networkidle');
 await page.locator('#team-login [name=email]').fill('restore-admin@example.test');
 await page.locator('#team-login [name=password]').fill('mat-khau-qa-18-11');
 await page.locator('#team-login button[type=submit]').click();await page.waitForURL(base+'/');await page.waitForLoadState('networkidle');
 assert((await(await page.request.get(base+'/api/status')).json()).fixture);
 const sourceRoute=base+'/api/lesson-catalog/sources';
 const qaSource=await page.request.post(sourceRoute,{headers:{Origin:base},data:{
  grade:9,subject:'Toán',title:'Học liệu riêng QA',license_status:'teacher_owned',
  content_excerpt:'Bài toán về chu vi hình chữ nhật do nhóm tự soạn.',
 }});
 assert(qaSource.ok(),await qaSource.text());
 const lesson=await qaSource.json();
 // Lấy bản sao bằng đúng nút giao diện, gồm trạng thái rich/ID mà editor đang dùng.
 await page.getByRole('button',{name:'Mở kho đề',exact:true}).click();
 const downloadEvent=page.waitForEvent('download');await page.locator('[data-action="backup"]:visible').click();
 const download=await downloadEvent;await download.saveAs(path.join(out,'backup-qa.json'));
 const bytes=await fs.readFile(path.join(out,'backup-qa.json')),backup=JSON.parse(bytes);
 const [fileId]=Object.keys(backup.files);
 const [exportedLesson]=backup.curriculumSources;
 assert.equal(exportedLesson.id,lesson.id);
 assert.equal(exportedLesson.content_excerpt,lesson.content_excerpt);
 assert(!Object.hasOwn(exportedLesson,'owner_id'));
 assert(fileId,'Fixture cần một tệp được tham chiếu trong bản sao.');
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Tạo đề mới',exact:true}).click();
 const created=page.waitForResponse(response=>{
  const request=response.request();
  return response.url()===base+'/api/kv'&&request.method()==='PUT'&&response.ok()
   &&request.postDataJSON()?.value?.exams?.length>backup.state.exams.length;
 });
 await page.locator('[data-action="create-blank"]:visible').click();
 await created;
 const changed=await state();assert(changed.value.exams.length>backup.state.exams.length);
 await fileMenu();await choose(bytes);await page.locator('[data-action="confirm-backup"]').waitFor();
 assert.deepEqual((await state()).value,changed.value,'Xem trước không được thay kho');
 const submitted=[];
 const track=request=>{if(request.url()===base+'/api/workspace/restore'&&request.method()==='POST')submitted.push(request);};
 page.on('request',track);
 await page.locator('[data-action="confirm-backup"]').evaluate(button=>{
  button.click();
  button.closest('dialog').close();
 });
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 assert.deepEqual(await state(),changed);
 assert.equal(submitted.length,0);
 page.off('request',track);
 results.push({case:'Đóng xem trước khi nút xác nhận đang xử lý: không gửi yêu cầu thay kho',passed:true});
 await fileMenu();await choose(bytes);await page.locator('[data-action="confirm-backup"]').waitFor();
 await page.getByText(/Có 1 học liệu cá nhân/).waitFor();
 await page.screenshot({path:path.join(out,'desktop-preview.png')});
 await Promise.all([page.waitForEvent('load'),page.locator('[data-action="confirm-backup"]').click()]);await page.waitForLoadState('networkidle');
 const restored=await state();assert.deepEqual(restored.value.exams,backup.state.exams);assert.equal(restored.value.current,backup.state.current);
 const restoredFile=await context.request.get(base+'/api/kv?key='+encodeURIComponent('file:'+fileId));
 assert(restoredFile.ok(),await restoredFile.text());
 assert.equal((await restoredFile.json()).value,backup.files[fileId]);
 const restoredLesson=await page.request.get(sourceRoute+'/'+lesson.id);
 assert(restoredLesson.ok(),await restoredLesson.text());
 assert.equal((await restoredLesson.json()).license_status,'teacher_owned');
 results.push({case:'Desktop: tải bản sao → tạo đề → xem trước → xác nhận → reload giữ đề, lịch sử, tệp và học liệu của cùng kho',passed:true});
 // Ghi từ tab/API khác sau preview, rồi xác nhận trên tab cũ phải bị từ chối.
 await fileMenu();await choose(bytes);await page.locator('[data-action="confirm-backup"]').waitFor();
 const remote=await state();remote.value.exams[0].title+=' · thay đổi từ tab khác';
 const update=await context.request.put(base+'/api/kv',{headers:{Origin:base,'If-Match':String(remote.revision)},data:{key:'state',value:remote.value}});assert(update.ok(),await update.text());
 const conflict=page.waitForResponse(r=>r.url()===base+'/api/workspace/restore'&&r.request().method()==='POST');
 await page.locator('[data-action="confirm-backup"]').click();assert.equal((await conflict).status(),409);
 assert.deepEqual((await state()).value,remote.value);assert(await page.locator('#dialog').isVisible());
 results.push({case:'Xung đột sau xem trước: từ chối khôi phục, giữ thay đổi của tab khác',passed:true});
 await page.keyboard.press('Escape');await page.reload();await page.waitForLoadState('networkidle');
 // Mobile: mở từ menu Tệp, nhập file và truy cập nút xác nhận bằng bàn phím.
 await page.setViewportSize({width:390,height:844});await fileMenu();await choose(bytes);
 const confirm=page.locator('[data-action="confirm-backup"]');await confirm.waitFor();await confirm.focus();
 assert(await confirm.evaluate(n=>document.activeElement===n));await page.screenshot({path:path.join(out,'mobile-preview.png')});
 const box=await confirm.boundingBox();assert(box&&box.x>=0&&box.x+box.width<=390);
 const beforeCancel=await state();await page.keyboard.press('Escape');assert.deepEqual(await state(),beforeCancel);
 results.push({case:'Mobile390: menu → nhập → xem trước, focus/scroll nút xác nhận, Escape bỏ giữ nguyên kho',passed:true});
 const beforeBroken=await state();await fileMenu();await choose(Buffer.from('{ JSON hỏng }'));
 await page.getByText('Tệp JSON bị hỏng. Hãy chọn bản sao tải từ ứng dụng.',{exact:true}).waitFor({state:'visible'});
 assert.deepEqual(await state(),beforeBroken);
 results.push({case:'JSON hỏng: báo lỗi, không đổi kho',passed:true});
 const incomplete=structuredClone(backup);
 delete incomplete.files[fileId];
 const previewFailed=page.waitForResponse(r=>r.url()===base+'/api/workspace/restore/preview');
 await fileMenu();await choose(Buffer.from(JSON.stringify(incomplete)));
 assert.equal((await previewFailed).status(),409);
 assert.deepEqual(await state(),beforeBroken);
 assert.equal(await page.locator('[data-action="confirm-backup"]:visible').count(),0);
 results.push({case:'Thiếu tệp tham chiếu: dừng ở bước kiểm bản sao, giữ nguyên kho',passed:true});
 await page.keyboard.press('Escape');
 await page.setViewportSize({width:1366,height:900});
 await page.reload();await page.waitForLoadState('networkidle');
 const rename=async text=>{
  const input=page.locator('.header-title');
  await input.fill(text);await input.press('Tab');
 };
 const waitPut=code=>page.waitForResponse(r=>r.url()===base+'/api/kv'&&r.request().method()==='PUT'&&r.status()===code);
 const waitDraft=()=>page.waitForFunction(()=>Array.from(document.querySelectorAll('[data-save-status]')).some(node=>node.textContent.includes('chờ đồng bộ')));
 const current=({value})=>value.exams.find(exam=>exam.id===value.current);
 const onlineBefore=await state();
 await context.setOffline(true);
 await rename('Nháp tự đồng bộ khi có mạng');await waitDraft();
 assert.deepEqual(await state(),onlineBefore);
 const synced=waitPut(200);
 await context.setOffline(false);await synced;
 const stable=await state();
 assert.equal(current(stable).title,'Nháp tự đồng bộ khi có mạng');
 await page.locator('[data-save-warning]').waitFor({state:'hidden'});
 assert(!((await page.locator('[data-save-status]').first().textContent()).includes('chờ đồng bộ')));
 results.push({case:'Mất mạng: máy chủ giữ đề, kết nối lại lưu nháp và bỏ cảnh báo tự động',passed:true});

 await context.setOffline(true);
 await rename('Nháp cục bộ khi xung đột');await waitDraft();
 const newer=await state();
 current(newer).title='Bản mới trên máy chủ';
 const savedElsewhere=await context.request.put(base+'/api/kv',{
  headers:{Origin:base,'If-Match':String(newer.revision)},data:{key:'state',value:newer.value},
 });
 assert(savedElsewhere.ok(),await savedElsewhere.text());
 const rejected=waitPut(409);
 await context.setOffline(false);
 assert.equal((await (await rejected).json()).code,'stale_snapshot');
 const backupButton=page.getByRole('button',{name:'Tải bản nháp',exact:true});
 await backupButton.waitFor();
 assert.match(await page.locator('[data-save-message]').textContent(),/Xung đột lưu/);
 assert.equal(current(await state()).title,'Bản mới trên máy chủ');
 assert.equal(await page.locator('.header-title').inputValue(),'Nháp cục bộ khi xung đột');
 const draftDownload=page.waitForEvent('download');await backupButton.click();
 const draftFile=await draftDownload;
 await draftFile.saveAs(path.join(out,'nhap-khi-xung-dot.json'));
 const recoveredDraft=JSON.parse(await fs.readFile(path.join(out,'nhap-khi-xung-dot.json')));
 assert.equal(current({value:recoveredDraft.state}).title,'Nháp cục bộ khi xung đột');
 assert.equal(current(await state()).title,'Bản mới trên máy chủ');
 results.push({case:'Mất mạng và xung đột: giữ bản máy chủ, nút tải xuất đúng nháp cục bộ',passed:true});
 await verifyBatchAudio(backup.state.exams[0]);
 results.push({case:'Kho đề tải JSON kèm audio và tệp hoàn tác. Ghép tệp trùng ID, reload khi API KV mất kết nối vẫn phát đúng audio của cả hai đề',passed:true});
 assert.deepEqual(errors,[]);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({results,pageErrors:errors,fixture:true,realAI:false},null,2));
 console.log(JSON.stringify({results,pageErrors:errors}));
}finally{await browser.close();}
