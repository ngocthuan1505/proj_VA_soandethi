import test from 'node:test';
import assert from 'node:assert/strict';
import {
 essaySample,
 referenceCompose,
 tableCellHTML,
 questionTablesHTML,
 ASSISTANT_DROP_EXTENSIONS,
 MAX_ASSISTANT_DROP_BYTES,
 validateDroppedSourceFile,
 filterDroppedSourceFiles,
 hasDraggedFiles,
 extractDroppedFiles,
 duplicateQuestionInExam,
 moveQuestionInExam,
 toggleQuestionApprovalInExam,
 questionQuickActionsHTML,
 inferAssistantContextState,
 buildContextualAssistantSuggestions,
 contextualSuggestionsHTML,
} from '../reference.js';
import {approveQuestion,isApproved,check,clone,exportHTML,commit,undo,blank} from '../core.js';
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

test('Ô bảng trên canvas giữ ảnh data:image và chú thích, chặn URL nguy hiểm và không in [object Object]',()=>{
 const png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
 const cellHtml=tableCellHTML({data:png,caption:'Hình "A" <script>alert(1)</script>'});
 assert.ok(cellHtml.includes('<img class="cell-image" src="'+png+'"'));
 assert.ok(cellHtml.includes('<small class="cell-caption">Hình &quot;A&quot; &lt;script&gt;alert(1)&lt;/script&gt;</small>'));
 assert.ok(!cellHtml.includes('[object Object]'));
 const badSvg=tableCellHTML({data:'data:image/svg+xml;base64,PHN2Zz4=',caption:'SVG'});
 assert.ok(!badSvg.includes('<img'));
 const badProto=tableCellHTML({data:'javascript:alert(1)',caption:'JS'});
 assert.ok(!badProto.includes('<img'));
 const richCell=tableCellHTML({type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'Đậm',marks:[{type:'bold'}]}]}]});
 assert.ok(richCell.includes('<strong>Đậm</strong>'));
 assert.equal(tableCellHTML('<plain>'), '&lt;plain&gt;');
 const full=questionTablesHTML({id:'q1',tables:[{id:'t1',rows:[['Cột 1','Cột 2'],[{data:png,caption:'Bảng ảnh'},'40 km/h']]}]});
 assert.ok(full.includes('<img class="cell-image"'));
 assert.ok(full.includes('<small class="cell-caption">Bảng ảnh</small>'));
 assert.ok(full.includes('<td>40 km/h</td>'));
 assert.ok(!full.includes('[object Object]'));
});

test('Bộ lọc kéo-thả nguồn chấp nhận đủ định dạng hợp lệ và chặn tệp lạ/quá 15MB/rỗng',()=>{
 for(const ext of ASSISTANT_DROP_EXTENSIONS){
  const res=validateDroppedSourceFile({name:`nguon.${ext}`,size:1024});
  assert.equal(res.ok,true,ext);
  assert.equal(res.ext,ext);
 }
 assert.equal(validateDroppedSourceFile({name:'script.exe',size:128}).ok,false);
 assert.equal(validateDroppedSourceFile({name:'khongduoitep',size:128}).ok,false);
 assert.equal(validateDroppedSourceFile({name:'trong.txt',size:0}).ok,false);
 assert.equal(validateDroppedSourceFile({name:'lon.pdf',size:MAX_ASSISTANT_DROP_BYTES+1}).ok,false);

 const batch=filterDroppedSourceFiles([
  {name:'de.docx',size:400},
  {name:'malware.bat',size:20},
  {name:'anh.webp',size:800},
 ]);
 assert.deepEqual(batch.accepted.map(f=>f.name),['de.docx','anh.webp']);
 assert.equal(batch.rejected.length,1);
 assert.match(batch.rejected[0].error,/Định dạng chưa hỗ trợ/);

 assert.equal(hasDraggedFiles({types:['text/plain']}),false);
 assert.equal(hasDraggedFiles({types:['Files']}),true);
 const fileObj={name:'a.pdf',size:10};
 assert.deepEqual(extractDroppedFiles({items:[{kind:'file',getAsFile:()=>fileObj},{kind:'string'}]}),[fileObj]);
});

test('Thao tác nhanh trên câu: nhân bản đổi UUID & xóa duyệt cũ, di chuyển vị trí và duyệt/bỏ duyệt',()=>{
 const e=essaySample();
 const q0=e.questions[0];
 q0.blockIds={stem:'old-stem-block'};
 q0.richDoc={type:'doc',content:[{type:'paragraph',attrs:{id:'node-1'},content:[{type:'text',text:'Câu 1'}]}]};
 q0.formulas=[{id:'f-1',latex:'x^2'}];
 q0.tables=[{id:'t-1',rows:[['A','B']]}];
 q0.images=[{id:'i-1',data:'data:image/png;base64,AA==',caption:'Hình'}];
 approveQuestion(q0);

 const copy=duplicateQuestionInExam(e,q0.id);
 assert.ok(copy);
 assert.equal(e.questions.length,6);
 assert.equal(e.questions[1].id,copy.id);
 assert.notEqual(copy.id,q0.id);
 assert.equal(copy.blockIds,undefined);
 assert.equal(copy.approval,undefined);
 assert.equal(copy.check,null);
 assert.notEqual(copy.richDoc.content[0].attrs.id,'node-1');
 assert.notEqual(copy.formulas[0].id,'f-1');
 assert.notEqual(copy.tables[0].id,'t-1');
 assert.notEqual(copy.images[0].id,'i-1');
 assert.equal(isApproved(copy),false);

 assert.equal(moveQuestionInExam(e,q0.id,-1),false);
 assert.equal(moveQuestionInExam(e,q0.id,1),true);
 assert.equal(e.questions[0].id,copy.id);
 assert.equal(e.questions[1].id,q0.id);

 assert.equal(toggleQuestionApprovalInExam(e,q0),false);
 assert.equal(isApproved(q0),false);
 assert.equal(toggleQuestionApprovalInExam(e,q0),true);
 assert.equal(isApproved(q0),true);

 const bar=questionQuickActionsHTML(q0,1,e.questions.length);
 assert.ok(bar.includes('data-action="select"'));
 assert.ok(bar.includes('data-action="quick-formula"'));
 assert.ok(!bar.includes('data-action="subject-library"'));
 assert.ok(bar.includes('data-action="quick-image"'));
 assert.ok(bar.includes('data-action="quick-table"'));
 assert.ok(bar.includes('data-action="quick-figure"'));
 assert.ok(bar.includes('data-action="toggle-approve-question"'));
 assert.ok(bar.includes('data-action="duplicate-question"'));
 assert.ok(bar.includes('data-action="quick-move-up"'));
 assert.ok(bar.includes('data-action="quick-move-down"'));
});

test('Gợi ý Trợ lý AI đổi linh hoạt theo đủ 5 trạng thái ngữ cảnh của đề',()=>{
 const eEmpty=blank('Sinh học');
 const pEmpty=buildContextualAssistantSuggestions(eEmpty);
 assert.equal(pEmpty.mode,'empty');
 assert.ok(pEmpty.actions.some(a=>a.action==='import-doc'));

 const eSrc=blank('Toán');
 eSrc.docs=[{id:'d1',name:'Tai-lieu.txt',pages:[{number:1,text:'Nội dung nguồn đủ dài'}]}];
 eSrc.assistantSources=['d1'];
 const pSrc=buildContextualAssistantSuggestions(eSrc);
 assert.equal(pSrc.mode,'has-sources');
 assert.ok(pSrc.actions.some(a=>a.action==='local-matrix'));
 assert.ok(pSrc.actions.some(a=>a.action==='parse-first-doc'));

 const pMatrix=buildContextualAssistantSuggestions(eSrc,{matrixOpen:true,matrixPhase:'review'});
 assert.equal(pMatrix.mode,'matrix-open');
 assert.match(pMatrix.summary,/Chấp nhận/);

 const eReview=essaySample();
 check(eReview,eReview.questions[0]);
 const pReview=buildContextualAssistantSuggestions(eReview);
 assert.equal(pReview.mode,'needs-review');
 assert.ok(pReview.actions.some(a=>a.action==='jump-first-review'));

 const pSel=buildContextualAssistantSuggestions(eReview,{selectedId:eReview.questions[2].id});
 assert.equal(pSel.mode,'selected-question');
 const {buttons}=contextualSuggestionsHTML(eReview,{selectedId:eReview.questions[2].id});
 assert.ok(buttons.includes('Câu 3'));
 assert.ok(buttons.includes('data-action="quick-formula"'));

 eReview.questions.forEach(q=>approveQuestion(q));
 assert.equal(inferAssistantContextState(eReview).mode,'ready');
});
