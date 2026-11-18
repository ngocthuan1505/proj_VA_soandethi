// Fixture giao diện/nhập/xuất, không dùng làm bằng chứng AI sinh câu thật.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {blank,uid} from '../core.js';

const url=process.env.POC_URL||'http://127.0.0.1:4182';
const output=path.resolve(process.argv[2]||'outputs/local-demo/ui-export');
await fs.mkdir(output,{recursive:true});
async function request(route,options={}){
 const response=await fetch(url+route,{...options,headers:{Origin:url,'Content-Type':'application/json',...options.headers}});
 assert(response.ok,await response.clone().text());return response.json();
}
const prior=await request('/api/kv?key=state'),exam=blank('Ngữ văn',[]);
exam.title='Kiểm UI local · câu soạn sẵn tách AI';exam.grade='6';exam.fullExam=true;
exam.quote.text='Nguồn giả lập kiểm xuất. Mai báo với cô Loan về cửa sổ bị hỏng.';
exam.questions=[{id:uid(),v:1,type:'mcq',stem:'Mai báo với ai?',options:['Nam','Cô Loan','Hà','Lan'],answer:1,explanation:'Chi tiết chỉ dành cho giáo viên.',topic:'Chi tiết',level:0,points:10,source:null,check:null}];
const state=prior.value||{exams:[],prefs:[]};state.exams.push(exam);state.current=exam.id;
await request('/api/kv',{method:'PUT',headers:{'If-Match':String(prior.revision)},body:JSON.stringify({key:'state',value:state})});
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}});page.setDefaultTimeout(60000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);await page.waitForLoadState('networkidle');
 await page.locator('.paper').getByText('Mai báo với ai?',{exact:true}).first().waitFor({state:'visible'});
 await page.screenshot({path:path.join(output,'01-de-kiem-ui.png'),fullPage:true});
 const exports=[];
 for(const [format,teacher] of [['html',false],['html',true],['docx',false],['pdf',false]]){
  await page.locator('[data-action="export"]').first().click();
  await page.locator(`[data-action="export-file"][data-format="${format}"][data-teacher="${teacher}"]`).click();
  const link=page.locator('.saved-export-link');await link.waitFor();
  const href=await link.getAttribute('href'),response=await fetch(url+href);
  assert(response.ok);const bytes=Buffer.from(await response.arrayBuffer());
  if(format==='html'){
   const text=bytes.toString('utf8');assert(text.includes('Nguồn giả lập kiểm xuất'));
   assert.equal(text.includes('Chi tiết chỉ dành cho giáo viên.'),teacher);
  }else assert(bytes.subarray(0,format==='pdf'?5:2).equals(Buffer.from(format==='pdf'?'%PDF-':'PK')));
  await fs.writeFile(path.join(output,(teacher?'giao-vien':'hoc-sinh')+'.'+format),bytes);
  exports.push({format,teacher,bytes:bytes.length});
  await page.locator('#dialog [data-action="close"]').click();
 }
 await page.locator('[data-action="import-doc"]').first().click();
 await page.locator('#mvp-file').setInputFiles({name:'nguon-test.txt',mimeType:'text/plain',buffer:Buffer.from('Văn bản nguồn nhập từ tệp, không tự gửi tới AI.')});
 await page.locator('#dialog').getByText('Văn bản nguồn nhập từ tệp, không tự gửi tới AI.',{exact:false}).first().waitFor();
 await page.locator('#dialog [data-action="close"]').click();
 await page.reload();await page.waitForLoadState('networkidle');
 const current=await request('/api/kv?key=state');
 const saved=current.value.exams.find(e=>e.id===exam.id);
 assert(saved.docs.some(d=>d.name==='nguon-test.txt'&&d.text.includes('không tự gửi')));
 assert.equal(saved.questions[0].stem,'Mai báo với ai?');
 assert.deepEqual(errors,[]);
 await fs.writeFile(path.join(output,'result.json'),JSON.stringify({mode:'ui_fixture_no_ai',examId:exam.id,exports,importSaved:true,reloadPreserved:true,pageErrors:errors},null,2));
 console.log(JSON.stringify({mode:'ui_fixture_no_ai',exports,importSaved:true,reloadPreserved:true}));
}finally{await browser.close();}
