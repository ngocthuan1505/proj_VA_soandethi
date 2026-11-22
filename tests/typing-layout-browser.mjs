// Regression: long stems wrap to the left margin; typing preserves page/editor/sidebar nodes.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {blank,uid} from '../core.js';
import {dependency,chromePath} from '../runtime.mjs';
const root=fileURLToPath(new URL('../',import.meta.url)),base='http://127.0.0.1:4297';
const dir=await mkdtemp(path.join(os.tmpdir(),'typing-layout-'));
const server=spawn(process.execPath,[path.join(root,'server.mjs')],{env:{...process.env,PORT:'4297',APP_DATA_DIR:dir},windowsHide:true,stdio:'ignore'});
let browser;
try{
 for(let i=0;i<100;i++){try{if((await fetch(base+'/api/status')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 const e=blank('Sinh học');e.fullExam=true;e.autoUpdate=false;
 e.questions=Array.from({length:12},()=>({id:uid(),v:1,type:'mcq',points:2.5,stem:'Một tế bào thực vật có nồng độ chất tan nội bào tương đương dung dịch NaCl 0,9%. Nếu đặt tế bào này vào cốc chứa dung dịch NaCl 2,0% (môi trường có nồng độ chất tan cao hơn), chiều di chuyển ròng của nước và trạng thái tế bào sẽ như thế nào?',options:['Nước di chuyển từ trong ra ngoài.','Tế bào trương nước.','Không có dòng nước ròng.','Tế bào giữ nguyên.'],answer:0,explanation:'',rubric:[],topic:'Thẩm thấu',level:0}));
 // A previously edited question can retain its own centered paragraph in richDoc.
 e.questions[0].richDoc={type:'doc',content:[{type:'paragraph',attrs:{textAlign:'center'},content:[{type:'text',text:e.questions[0].stem}]}]};
 await fetch(base+'/api/kv',{method:'PUT',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({key:'state',value:{version:1,current:e.id,exams:[e],prefs:[]}})});
 browser=await dependency('playwright-core').chromium.launch({headless:true,executablePath:chromePath()});
 const page=await browser.newPage({viewport:{width:1740,height:1100}});
 await page.goto(base);await page.locator('.document-page').first().waitFor();await page.waitForTimeout(800);
 await page.screenshot({path:path.join(dir,'question-layout.png')});console.log('SCREENSHOT',path.join(dir,'question-layout.png'));
 const geometry=await page.locator('.stem-editor .ProseMirror').first().evaluate(el=>{
  const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT),lines=new Map();let n;
  while(n=walker.nextNode())for(let i=0;i<n.length;i++){const r=document.createRange();r.setStart(n,i);r.setEnd(n,i+1);const b=r.getBoundingClientRect(),y=Math.round(b.top);if(b.width)lines.set(y,Math.min(lines.get(y)??Infinity,b.left));}
  return {left:el.getBoundingClientRect().left,lines:[...lines.values()]};
 });
 console.log('WRAP',geometry);
 assert.ok(Math.abs(geometry.lines[1]-geometry.left)<3,'Dòng thứ hai phải bắt đầu ở lề trái');
 assert.ok(geometry.lines.slice(1).every(left=>Math.abs(left-geometry.left)<3),'Mọi dòng tiếp theo của câu cũ căn giữa phải sát lề trái');
 const editor=page.locator('.stem-editor .ProseMirror').nth(3);await editor.click();await page.keyboard.press('Home');
 await page.evaluate(()=>{window.typingStats={detached:0,replaced:0,scroll:[]};const paper=document.querySelector('.paper'),side=document.querySelector('.side-content');window.typingEditor=document.activeElement;window.typingSide=side.querySelector('.outline-item');window.typingPage=typingEditor.closest('.document-page');new MutationObserver(records=>{for(const r of records)for(const n of r.removedNodes)if(n===typingPage||n.contains?.(typingEditor))typingStats.detached++;}).observe(paper,{childList:true,subtree:true});document.querySelector('.paper-scroll').addEventListener('scroll',()=>typingStats.scroll.push(document.querySelector('.paper-scroll').scrollTop));});
 const top=await page.locator('.paper-scroll').evaluate(n=>n.scrollTop);
 for(let i=0;i<4;i++){for(let j=0;j<5;j++)await page.keyboard.press(i%2?'Delete':'Space');await page.waitForTimeout(750);}
 const result=await page.evaluate(()=>({...typingStats,top:document.querySelector('.paper-scroll').scrollTop,sameEditor:document.activeElement===typingEditor,sameSide:document.querySelector('.side-content .outline-item')===typingSide}));
 console.log('TYPING',result);
 assert.equal(result.detached,0,'Không tháo editor khi kích thước trang không đổi');
 assert.equal(result.sameEditor,true);assert.equal(result.sameSide,true,'Không dựng lại mục lục khi nhập');
 assert.ok(Math.abs(result.top-top)<3,'Vị trí cuộn phải ổn định');
 console.log('PASS: xuống dòng sát lề; Space/Delete giữ editor, trang, mục lục và vị trí cuộn');
}finally{await browser?.close();server.kill();}
