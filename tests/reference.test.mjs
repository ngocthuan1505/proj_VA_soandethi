import test from 'node:test';
import assert from 'node:assert/strict';
import {essaySample,referenceCompose} from '../reference.js';
import {check,clone,exportHTML,commit,undo} from '../core.js';
import {validateGenerated} from '../ai.mjs';
import {makeDocx,formattedHTML} from '../exports.mjs';
import {dependency} from '../runtime.mjs';
test('Tự luận: năm bài, tổng 10 điểm, kiểm tra barem và hoàn tác',()=>{const e=essaySample();assert.equal(e.questions.length,5);assert.equal(e.questions.reduce((n,q)=>n+q.points,0),10);for(const q of e.questions){assert.equal(q.options.length,0);assert.ok(!check(e,q).problems.some(x=>/phương án/.test(x)));}const q=e.questions[0];commit(e,'Đổi thang điểm',()=>{q.rubric[0].points=0.25;});assert.ok(check(e,q).problems.some(x=>/Tổng thang điểm/.test(x)));undo(e);assert.equal(e.questions[0].rubric[0].points,1);});
test('Sinh tự luận chỉ nhận barem khớp điểm, ma trận và nguồn thật',()=>{const sources=[{docId:'s',page:1,location:'Trang 1',text:'Phương trình bậc nhất có dạng ax + b = 0.'}],matrix=[{topic:'Đại số',targets:[0,1,0]}];const data={questions:[{type:'essay',stem:'Giải 2x + 3 = 11.',options:[],answer:0,points:2,rubric:[{text:'Chuyển vế',points:1},{text:'Tìm x = 4',points:1}],explanation:'2x = 8 nên x = 4.',topic:'Đại số',level:1,source:{docId:'s',page:1,quote:'Phương trình bậc nhất'}}]};assert.equal(validateGenerated(clone(data),sources,matrix,'essay')[0].type,'essay');const broken=clone(data);broken.questions[0].rubric[0].points=0.5;assert.throws(()=>validateGenerated(broken,sources,matrix,'essay'),/Thang điểm/);const invented=clone(data);invented.questions[0].source.quote='trích dẫn không có trong tài liệu';assert.throws(()=>validateGenerated(invented,sources,matrix,'essay'),/đoạn trích/);});
test('Xuất tự luận: học sinh không lộ lời giải; giáo viên có bảng điểm Word thật',async()=>{const e=essaySample(),text=e.questions[0].rubric[0].text;assert.ok(!exportHTML(e,false).includes(text));assert.ok(exportHTML(e,true).includes(text));const zip=await dependency('jszip').loadAsync(await makeDocx(e,true));const xml=await zip.file('word/document.xml').async('string');assert.ok(xml.includes(text));assert.ok(xml.includes('Bài 1 (2 điểm)'));assert.ok(xml.includes('w:tbl'));assert.ok(!(await formattedHTML(e,false)).includes(text));});

test('Lát B1: referenceCompose dựng chip 4 kênh [SGK]/[ĐỀ]/[CỘNG ĐỒNG]/[TỆP] kèm nút detach đúng data-doc',()=>{
 const html=referenceCompose({
  docs:[
   {id:'d-sgk',name:'Toán 10 · Bài 1',catalog:{series:'KNTT'}},
   {id:'d-exam',name:'Đề ngắn 109B',sourceExamId:'ex-1'},
   {id:'d-comm',name:'Đề cộng đồng',communityToken:'tok-1'},
   {id:'d-file',name:'De_cu.docx'},
  ],
  assistantSources:['d-sgk','d-exam','d-comm','d-file'],
  questions:[],
  aiEffort:1,
 },null);
 for(const badge of ['[SGK]','>SGK<','>ĐỀ<','>CỘNG ĐỒNG<','>TỆP<'].slice(1))assert.ok(html.includes(badge),badge);
 for(const id of ['d-sgk','d-exam','d-comm','d-file']){
  assert.ok(html.includes(`data-action="detach-source"`));
  assert.ok(html.includes(`data-doc="${id}"`),id);
 }
});
