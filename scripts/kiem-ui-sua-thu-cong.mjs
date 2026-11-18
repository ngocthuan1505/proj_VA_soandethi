import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from 'playwright-core';
import {blank,uid} from '../core.js';
import {documentPlain} from '../rich-document.js';
import {ensureBlocks} from '../blocks.js';

const base='http://127.0.0.1:4183',out='outputs/mvp-18-11/manual';
async function api(route,body){
 const response=await fetch(base+route,body?{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
 assert(response.ok,await response.clone().text());
 return response.json();
}
assert((await api('/api/status')).fixture);
const stem=String.raw`Một xe chạy với thời gian $\frac{x}{40}$. Giữ dữ kiện cuối.`;
const exam=blank('Toán'),q={
 id:uid(),v:1,type:'mcq',stem,options:['A','B','C','D'],answer:1,explanation:'Lời giải cũ.',level:0,topic:'Vận tốc',points:5,
 richDoc:{type:'doc',content:[{type:'paragraph',attrs:{id:uid()},content:[
  {type:'text',text:'Một xe chạy',marks:[{type:'bold'}]},
  {type:'text',text:' với thời gian '},
  {type:'mathInline',attrs:{id:uid(),latex:String.raw`\frac{x}{40}`,display:false}},
  {type:'text',text:'. Giữ dữ kiện cuối.',marks:[{type:'italic'}]}
 ]}]}
};
assert.equal(documentPlain(q.richDoc),stem);
exam.questions=[q,{...q,id:uid(),stem:'Câu độc lập.',richDoc:null}];
ensureBlocks(exam);
await api('/api/kv',{key:'state',value:{version:1,exams:[exam],prefs:[],current:exam.id}});
const saved=async()=>(await api('/api/kv?key=state')).value.exams[0];
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1366,height:768}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base);await page.waitForLoadState('networkidle');
 const edit=async()=>{
  const outline=page.locator('.outline-item').filter({hasText:'Một xe chạy'});
  if(await outline.isVisible())await outline.click();
  else await page.locator('.stem-editor').filter({hasText:'Một xe chạy'}).click();
  await page.getByRole('button',{name:'Chỉnh sửa',exact:true}).click();
  await page.locator('[data-action=replace]:visible').click();
 };
 const preview=async(value)=>{await page.locator('#replacement').fill(value);await page.getByRole('button',{name:'Xem thay đổi',exact:true}).click();};
 const waitForSave=()=>page.waitForResponse(response=>response.url()===base+'/api/kv'&&response.request().method()==='PUT'&&response.ok());
 await edit();
 const next=stem.replace('40','50');
 await preview(next);
 await page.locator('#dialog del .katex').waitFor({timeout:3000});
 await page.locator('#dialog ins .katex').waitFor();
 assert.deepEqual((await saved()).questions,exam.questions);
 await page.keyboard.press('Escape');
 assert.deepEqual((await saved()).questions,exam.questions);
 await edit();await preview(stem.replace('40}', '40'));
 await page.getByText(/Công thức chưa hợp lệ/).waitFor();
 assert.deepEqual((await saved()).questions,exam.questions);
 await page.keyboard.press('Escape');
 await edit();await preview(next);
 await Promise.all([waitForSave(),page.getByRole('button',{name:'Xác nhận thay đổi',exact:true}).click()]);
 if(await page.locator('#dialog').isVisible())throw Error(await page.locator('#dialog [data-dialog-feedback]').textContent({timeout:2000}));
 const applied=(await saved()).questions;
 assert.equal(applied[0].stem,next);assert.equal(applied[0].v,2);assert.equal(applied[0].id,q.id);
 assert.equal(documentPlain(applied[0].richDoc),next);
 assert.deepEqual(applied[0].richDoc.content[0].content.at(-1),q.richDoc.content[0].content.at(-1));
 assert.deepEqual(applied[0].richDoc.content[0].content[0],q.richDoc.content[0].content[0]);
 assert.deepEqual(applied[1],exam.questions[1]);assert.equal(applied[0].explanation,q.explanation);
 await Promise.all([waitForSave(),page.getByRole('button',{name:'Hoàn tác',exact:true}).click()]);
 assert.deepEqual((await saved()).questions,exam.questions);
 const phrase='với thời gian',replacement='trong thời gian';
 const editor=page.locator('.stem-editor').filter({hasText:'Một xe chạy'}).locator('.tiptap');
 await editor.evaluate((node,phrase)=>{
  const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);
  for(let part=walker.nextNode();part;part=walker.nextNode()){
   const start=part.textContent.indexOf(phrase);
   if(start<0)continue;
   node.focus();
   const range=document.createRange();range.setStart(part,start);range.setEnd(part,start+phrase.length);
   const selection=getSelection();selection.removeAllRanges();selection.addRange(range);return;
  }
  throw Error('Thiếu đoạn hay dùng để thử vùng bôi đen.');
 },phrase);
 await page.evaluate(async()=>{(await import('/editor.js')).captureDOMSelection();});
 await page.getByRole('button',{name:'Chỉnh sửa',exact:true}).click();
 await page.locator('[data-action=replace]:visible').click();
 assert.equal(await page.locator('#replacement').inputValue(),phrase);
 await preview(replacement);
 await Promise.all([waitForSave(),page.getByRole('button',{name:'Xác nhận thay đổi',exact:true}).click()]);
 const scoped=(await saved()).questions;
 assert.equal(scoped[0].stem,stem.replace(phrase,replacement));
 assert.deepEqual(scoped[0].richDoc.content[0].content.find(node=>node.type==='mathInline'),q.richDoc.content[0].content[2]);
 assert.deepEqual(scoped[1],exam.questions[1]);
 await Promise.all([waitForSave(),page.getByRole('button',{name:'Hoàn tác',exact:true}).click()]);
 assert.deepEqual((await saved()).questions,exam.questions);
 await page.setViewportSize({width:390,height:844});
 await edit();await preview(stem+String.raw` $$\frac{${'x+'.repeat(50)}1}{50}$$ <nhan-thu>`);
 const modal=page.locator('#dialog');
 const long=modal.locator('ins .katex-display');
 assert(await long.evaluate(el=>el.scrollWidth>el.clientWidth));
 assert.equal(await modal.locator('nhan-thu').count(),0);
 assert((await modal.locator('ins').innerText()).includes('<nhan-thu>'));
 const confirm=modal.getByRole('button',{name:'Xác nhận thay đổi',exact:true});
 await confirm.focus();assert(await confirm.evaluate(el=>el===document.activeElement));
 await page.screenshot({path:out+'/mobile-diff.png'});
 await page.keyboard.press('Escape');assert.deepEqual((await saved()).questions,exam.questions);
 assert.deepEqual(errors,[]);
 await fs.writeFile(out+'/result.json',JSON.stringify({desktop:true,mobile:true,previewUnchanged:true,richUndo:true,scopedText:true,escapedText:true,invalidMath:true,pageErrors:errors},null,2));
 console.log('So sánh công thức, giữ định dạng, hoàn tác, lỗi cú pháp và mobile đạt.');
}finally{await browser.close();}
