import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from 'playwright-core';
import {sample,approveQuestion,check} from '../core.js';
import {ensureBlocks} from '../blocks.js';

const base='http://127.0.0.1:4183',out='outputs/mvp-18-11/linked-data';
async function api(route,{body,method,revision}={}){
 const response=await fetch(base+route,{
  method:method||'GET',
  ...(body?{headers:{Origin:base,'Content-Type':'application/json',...(revision===undefined?{}:{'If-Match':String(revision)})},body:JSON.stringify(body)}:{})
 });
 assert(response.ok,await response.clone().text());
 return response;
}
assert((await(await api('/api/status')).json()).fixture);
const exam=sample('Địa lí');
ensureBlocks(exam);
exam.questions.forEach(question=>{check(exam,question);approveQuestion(question,1);});
await api('/api/kv',{method:'PUT',body:{key:'state',value:{version:1,current:exam.id,exams:[exam],prefs:[]}}});
const saved=async()=>(await api('/api/kv?key=state')).json();
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1366,height:830}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base);await page.waitForLoadState('networkidle');
 const before=await saved(),dialog=page.locator('#dialog');
 const open=()=>page.getByRole('button',{name:'Sửa dữ kiện',exact:true}).click();
 const value=()=>dialog.locator('[data-data-index="1"]');
 const preview=()=>dialog.getByRole('button',{name:'Xem ảnh hưởng',exact:true}).click();
 const confirm=()=>dialog.getByRole('button',{name:'Xác nhận cập nhật',exact:true}).click();
 const write=code=>page.waitForResponse(response=>response.url()===base+'/api/kv'&&response.request().method()==='PUT'&&response.status()===code);
 const chart=page.locator('.data-card svg').getByText(/Khu vực B:/);
 await open();await preview();
 await dialog.getByText('Dữ kiện chưa thay đổi.',{exact:true}).waitFor();
 assert.deepEqual(await saved(),before);
 await page.keyboard.press('Escape');
 await open();await value().fill('90');await preview();
 await dialog.getByText(/Khu vực B không nhiều hơn khu vực A/).waitFor();
 assert.deepEqual(await saved(),before);
 await page.keyboard.press('Escape');assert.deepEqual(await saved(),before);
 await open();await value().fill('300');await preview();
 await dialog.getByText(/180 người/).waitFor();
 assert.deepEqual(await saved(),before);
 await Promise.all([write(200),confirm()]);
 const after=(await saved()).value.exams[0];
 assert.deepEqual(after.data.map(row=>row.value),[120,300,180]);
 assert.deepEqual(after.questions.slice(2),before.value.exams[0].questions.slice(2));
 for(const [i,q] of after.questions.slice(0,2).entries()){
  const old=before.value.exams[0].questions[i];
  assert.equal(q.id,old.id);assert.equal(q.v,old.v+1);assert.equal(q.approval,null);
  assert.equal(q.answer,old.answer);assert.equal(q.check.version,q.v);
 }
 await page.locator('.data-card td').getByText('300',{exact:true}).waitFor();
 assert.match(await chart.textContent(),/300/);
 const exported=await(await api('/api/save-export',{method:'POST',body:{type:'exam',exam:after,format:'html',teacher:false}})).json();
 const html=await(await api(exported.url)).text();
 assert.match(html,/<td>300<\/td>/);assert.match(html,/Khu vực B: 300/);
 await page.reload();await page.waitForLoadState('networkidle');
 assert.match(await chart.textContent(),/300/);
 await page.screenshot({path:out+'/applied.png'});
 await Promise.all([write(200),page.getByRole('button',{name:'Hoàn tác',exact:true}).click()]);
 const undone=(await saved()).value.exams[0];
 assert.deepEqual(undone.data,before.value.exams[0].data);
 assert.deepEqual(undone.questions,before.value.exams[0].questions);
 assert.match(await chart.textContent(),/240/);
 await open();await value().fill('310');await preview();
 const other=await saved();other.value.exams[0].title+=' (đã sửa ở phiên khác)';
 await api('/api/kv',{method:'PUT',revision:other.revision,body:{key:'state',value:other.value}});
 await Promise.all([write(409),confirm()]);
 const server=await saved();
 assert.deepEqual(server.value,other.value);assert.equal(server.revision,other.revision+1);
 await dialog.getByText(/Chưa đồng bộ dữ kiện/).waitFor();
 assert.deepEqual(errors,[]);
 await fs.writeFile(out+'/result.json',JSON.stringify({noOp:true,reversedPremise:true,previewIsolated:true,tableAndChart:true,exportStudent:true,reload:true,undo:true,staleWriteRejected:true,fixture:true},null,2));
 console.log('Dữ kiện, bảng, biểu đồ, xuất, hoàn tác và xung đột đều đạt.');
}finally{await browser.close();}
