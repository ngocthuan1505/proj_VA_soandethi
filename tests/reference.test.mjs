import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
 essaySample,
 referenceChat,
 referenceCompose,
 CHAT_TIME_PRESETS,
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
 pickDetachFocusTarget,
 formatProviderName,
 formatLatencyLabel,
 chatMetaBadgeText,
 sourceBadge,
 sourceChannelKey,
 emptyCanvasHTML,
} from '../reference.js';
import {normalizeLessonSearch,expandLessonSearchVariants,lessonMatchesSearch} from '../lesson-picker.js';
import {assistantText,latexToReadableUnicode,formatOutlineTitleUnicode} from '../studio.js';
import {intentOf} from '../subject-profiles.js';
import {approveQuestion,isApproved,check,clone,exportHTML,commit,undo,blank} from '../core.js';
import {validateGenerated} from '../ai.mjs';
import {makeDocx,formattedHTML} from '../exports.mjs';
import {dependency} from '../runtime.mjs';
test('Tự luận: năm bài, tổng 10 điểm, kiểm tra barem và hoàn tác',()=>{const e=essaySample();assert.equal(e.questions.length,5);assert.equal(e.questions.reduce((n,q)=>n+q.points,0),10);for(const q of e.questions){assert.equal(q.options.length,0);assert.ok(!check(e,q).problems.some(x=>/phương án/.test(x)));}const q=e.questions[0];commit(e,'Đổi thang điểm',()=>{q.rubric[0].points=0.25;});assert.ok(check(e,q).problems.some(x=>/Tổng thang điểm/.test(x)));undo(e);assert.equal(e.questions[0].rubric[0].points,1);});
test('Sinh tự luận chỉ nhận barem khớp điểm, ma trận và nguồn thật',()=>{const sources=[{docId:'s',page:1,location:'Trang 1',text:'Phương trình bậc nhất có dạng ax + b = 0.'}],matrix=[{topic:'Đại số',targets:[0,1,0]}];const data={questions:[{type:'essay',stem:'Giải 2x + 3 = 11.',options:[],answer:0,points:2,rubric:[{text:'Chuyển vế',points:1},{text:'Tìm x = 4',points:1}],explanation:'2x = 8 nên x = 4.',topic:'Đại số',level:1,source:{docId:'s',page:1,quote:'Phương trình bậc nhất'}}]};assert.equal(validateGenerated(clone(data),sources,matrix,'essay')[0].type,'essay');const broken=clone(data);broken.questions[0].rubric[0].points=0.5;assert.throws(()=>validateGenerated(broken,sources,matrix,'essay'),/Thang điểm/);const invented=clone(data);invented.questions[0].source.quote='trích dẫn không có trong tài liệu';assert.throws(()=>validateGenerated(invented,sources,matrix,'essay'),/đoạn trích/);});
test('Xuất tự luận: học sinh không lộ lời giải; giáo viên có bảng điểm Word thật',async()=>{const e=essaySample(),text=e.questions[0].rubric[0].text;assert.ok(!exportHTML(e,false).includes(text));assert.ok(exportHTML(e,true).includes(text));const zip=await dependency('jszip').loadAsync(await makeDocx(e,true));const xml=await zip.file('word/document.xml').async('string');assert.ok(xml.includes(text));assert.ok(xml.includes('Bài 1 (2 điểm)'));assert.ok(xml.includes('w:tbl'));assert.ok(!(await formattedHTML(e,false)).includes(text));});

test('Lát B1: referenceCompose tách badge TÀI LIỆU CÁ NHÂN / HỌC LIỆU MẪU / ĐỀ / CỘNG ĐỒNG / TỆP kèm nút detach',()=>{
 const personalDoc={id:'d-personal',name:'Bài giảng riêng',personalLesson:true};
 const sampleDoc={id:'d-sgk',name:'Toán 10 · Bài 1',catalog:{series:'KNTT'}};
 const originSampleDoc={id:'d-origin',name:'Học liệu gốc',sourceOrigin:'lesson_catalog'};
 assert.equal(sourceBadge(personalDoc),'TÀI LIỆU CÁ NHÂN');
 assert.equal(sourceChannelKey(personalDoc),'personal');
 assert.equal(sourceBadge(sampleDoc),'HỌC LIỆU MẪU');
 assert.equal(sourceChannelKey(sampleDoc),'sample');
 assert.equal(sourceBadge(originSampleDoc),'HỌC LIỆU MẪU');
 assert.equal(sourceChannelKey(originSampleDoc),'sample');
 const html=referenceCompose({
  docs:[
   personalDoc,
   sampleDoc,
   {id:'d-exam',name:'Đề ngắn 109B',sourceExamId:'ex-1'},
   {id:'d-comm',name:'Đề cộng đồng',communityToken:'tok-1'},
   {id:'d-file',name:'De_cu.docx'},
  ],
  assistantSources:['d-personal','d-sgk','d-exam','d-comm','d-file'],
  questions:[],
  aiEffort:1,
 },null);
 for(const badge of ['>TÀI LIỆU CÁ NHÂN<','>HỌC LIỆU MẪU<','>ĐỀ<','>CỘNG ĐỒNG<','>TỆP<'])assert.ok(html.includes(badge),badge);
 for(const id of ['d-personal','d-sgk','d-exam','d-comm','d-file']){
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

test('BUG-6: tableCellHTML render công thức KaTeX trong ô chuỗi và {text}, vẫn thoát XSS an toàn',()=>{
 const mathHtml=tableCellHTML('$a^2+b^2=c^2$');
 assert.ok(mathHtml.includes('class="katex"'),mathHtml);
 assert.ok(!mathHtml.includes('$a^2+b^2=c^2$'));
 const objHtml=tableCellHTML({text:'Giá trị $\\frac{1}{2}$ <script>alert(1)</script>'});
 assert.ok(objHtml.includes('class="katex"'));
 assert.ok(objHtml.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
 assert.ok(!objHtml.includes('<script>'));
});

test('BUG-5: pickDetachFocusTarget giữ focus hợp lý sau khi gỡ nguồn, bỏ qua vùng hidden',()=>{
 const btn2={id:'detach-2',hidden:false,disabled:false};
 const hiddenAdd={id:'hidden-add',hidden:true,closest:()=>({hidden:true})};
 const attachBtn={id:'attach-btn',hidden:false,disabled:false,closest:()=>null};
 const mockDocRemain={querySelectorAll:sel=>sel==='.assistant-sources .source-detach'?[btn2]:[]};
 assert.equal(pickDetachFocusTarget(0,mockDocRemain),btn2);

 const mockDocEmpty={querySelectorAll:sel=>sel==='.assistant-sources .add-source'?[hiddenAdd]:sel==='[data-ux-action="attach"]'?[attachBtn]:[]};
 assert.equal(pickDetachFocusTarget(0,mockDocEmpty),attachBtn);
});

test('Cột phải Trợ lý AI tách rõ ctx-badge/ctx-summary (không dính Tự luậnSửa), có thanh nguồn 1 dòng và 1 dropdown #chat-time-preset',()=>{
 const e=essaySample();
 const selectedId=e.questions[0].id;
 const {plan,buttons,contextHeaderHTML}=contextualSuggestionsHTML(e,{selectedId});
 assert.equal(plan.mode,'selected-question');
 assert.ok(contextHeaderHTML.includes('<span class="ctx-badge assistant-context-badge"'));
 assert.ok(contextHeaderHTML.includes('<p class="ctx-summary"'));
 assert.ok(contextHeaderHTML.includes('Đang chọn Câu 1 · Tự luận'));
 assert.ok(contextHeaderHTML.includes('Sửa đúng Câu 1 hoặc kiểm tra độc lập trước khi duyệt.'));
 assert.ok(!contextHeaderHTML.includes('Tự luậnSửa'));
 const chatHtml=referenceChat(e,{selectedId});
 assert.ok(chatHtml.includes('<span class="ctx-badge assistant-context-badge"'));
 assert.ok(chatHtml.includes('<p class="ctx-summary"'));
 assert.ok(!chatHtml.includes('Tự luậnSửa'));
 assert.equal((buttons.match(/class="suggestion-card/g)||[]).length,3);

 const composeHtml=referenceCompose({...e,aiTimePreset:'deep'},null);
 assert.ok(composeHtml.includes('NGUỒN CHO TRỢ LÝ'));
 assert.ok(composeHtml.includes('data-action="import-doc"'));
 assert.ok(composeHtml.includes('+ Kho tài liệu'));
 assert.match(composeHtml,/data-action="lesson-sources"[^>]*>Bài SGK</);
 assert.ok(composeHtml.includes('data-action="assistant-sources"'));
 assert.ok(composeHtml.includes('data-action="community-exams"'));
 assert.ok(composeHtml.includes('Đề cộng đồng'));
 assert.ok(composeHtml.includes('<select id="chat-time-preset" name="chat-time-preset" class="chat-time-select" aria-label="Thời gian chạy AI"'));
 for(const [id,label] of CHAT_TIME_PRESETS){
  assert.ok(composeHtml.includes(`value="${id}"`),id);
  assert.ok(composeHtml.includes(label),label);
 }
 assert.ok(composeHtml.includes('<option value="deep" selected>Thời gian: Kỹ sâu (20p · AGY)</option>'));
 assert.ok(!composeHtml.includes('effort-toggle'));
 assert.ok(!composeHtml.includes('Mức: Trung bình'));
 assert.ok(!composeHtml.includes('time-preset-pill'));
 assert.ok(!composeHtml.includes('time-preset-bar'));

 const referenceSrc=readFileSync(new URL('../reference.js',import.meta.url),'utf8');
 assert.ok(referenceSrc.includes('<span>Trợ lý AI soạn đề</span>'));
 assert.ok(referenceSrc.includes('assistant-memory-btn'));
 assert.ok(referenceSrc.includes("'memory','· Trí nhớ'"));

 const workbenchSrc=readFileSync(new URL('../workbench.js',import.meta.url),'utf8');
 assert.ok(!workbenchSrc.includes('function paintTimePresets'));
 assert.ok(!workbenchSrc.includes('time-preset-pill'));
 assert.ok(!workbenchSrc.includes('assistant-context-bar'));
 assert.ok(!workbenchSrc.includes('contextStripHTML'));
 assert.ok(workbenchSrc.includes("ev.target.id==='chat-time-preset'"));
 assert.ok(workbenchSrc.includes("kind:'exam-questions-summary'"));
 assert.ok(workbenchSrc.includes('result.providerUsed'));
 assert.ok(workbenchSrc.includes('result.latencyMs'));
 assert.ok(workbenchSrc.includes('chat-consent-card'));
 assert.ok(workbenchSrc.includes('✓ Cho phép và gửi ngay'));
 assert.ok(workbenchSrc.includes('is-attention'));
 assert.ok(workbenchSrc.includes('Bấm "Cho phép và gửi ngay" phía trên để bật AI cho đề này.'));
 assert.ok(workbenchSrc.includes('ai-stage-timer'));
 assert.ok(workbenchSrc.includes('Đang trả lời AI…'));
 assert.ok(workbenchSrc.includes('copy-chat-msg'));
 assert.ok(workbenchSrc.includes('chat-msg-tools'));
});

test('intentOf phân loại câu chào, câu hỏi ngắn và yêu cầu thêm câu mới sang chat; giữ nguyên create/edit/verify',()=>{
 const scope={id:'q-1',field:'stem',start:0,end:10,text:'Câu hỏi 1'};
 for(const chatText of [
  'hello',
  'hi',
  'chào',
  'xin chào',
  'bạn là ai',
  'bạn là ai?',
  'thêm 2 câu trắc nghiệm Toán 9',
  'thêm 2 câu trắc nghiệm',
  'tạo thêm 3 bài tự luận',
  'gợi ý 2 câu vận dụng',
  'bổ sung thêm 1 câu hỏi',
  'cho thêm 2 câu đúng sai',
  'Câu này thuộc mức độ nào?',
 ]){
  assert.equal(intentOf(chatText,[scope]),'chat',chatText);
  assert.equal(intentOf(chatText,[]),'chat',chatText);
 }
 assert.equal(intentOf('soạn đề Toán lớp 9 giữa kỳ',[scope]),'create');
 assert.equal(intentOf('sửa câu 1 rõ hơn',[scope]),'edit');
 assert.equal(intentOf('viết lại bài 2 cho ngắn gọn',[scope]),'edit');
 assert.equal(intentOf('đổi thành: Giải phương trình 2x + 4 = 0',[scope]),'edit');
 assert.equal(intentOf('check đáp án câu 1',[scope]),'verify');
 assert.equal(intentOf('Tại sao có hai nghiệm?',[scope]),'explain');
});

test('Huy hiệu nguồn và tốc độ chat hiển thị chuẩn DeepSeek · 2,4s / Gemini · 3,1s',()=>{
 assert.equal(formatProviderName('deepseek'),'DeepSeek');
 assert.equal(formatProviderName('deepseek-v4.1-flash'),'DeepSeek');
 assert.equal(formatProviderName('gemini'),'Gemini');
 assert.equal(formatProviderName('agy_cli'),'AGY CLI');
 assert.equal(formatLatencyLabel(2400),'2,4s');
 assert.equal(formatLatencyLabel(3100),'3,1s');
 assert.equal(formatLatencyLabel(50),'0,1s');
 assert.equal(formatLatencyLabel(0),'');
 assert.equal(chatMetaBadgeText({providerUsed:'deepseek',latencyMs:2400}),'DeepSeek · 2,4s');
 assert.equal(chatMetaBadgeText({providerUsed:'gemini',latencyMs:3100}),'Gemini · 3,1s');
 assert.equal(chatMetaBadgeText({providerUsed:'ollama',latencyMs:0}),'Ollama');
 assert.equal(chatMetaBadgeText({providerUsed:'',latencyMs:1200}),'1,2s');
 assert.equal(chatMetaBadgeText({providerUsed:'deepseek',fallbackFrom:'agy_cli',latencyMs:2400}),'DeepSeek (dự phòng từ AGY CLI) · 2,4s');
 assert.equal(chatMetaBadgeText({providerUsed:'agy_cli',latencyMs:14200}),'AGY CLI · 14,2s');
});

test('Blue Whale additions: chatMetaBadgeText modelUsed, emptyCanvasHTML, lesson-picker ty so/giai he, studio Unicode & list',()=>{
 assert.equal(chatMetaBadgeText({providerUsed:'agy',modelUsed:'agy-cli',latencyMs:59900}),'AGY CLI · agy-cli · 59,9s');
 assert.equal(chatMetaBadgeText({providerUsed:'deepseek',fallbackFrom:'agy',modelUsed:'deepseek-chat',latencyMs:2400}),'DeepSeek (dự phòng từ AGY CLI) · deepseek-chat · 2,4s');

 const emptyHtml=emptyCanvasHTML({subject:'Toán',grade:'9'});
 assert.ok(emptyHtml.includes('class="empty-paper-canvas'));
 assert.ok(emptyHtml.includes('class="empty-whale-art"'));
 assert.ok(emptyHtml.includes('<svg'));

 assert.equal(normalizeLessonSearch('Tỉ số lượng giác'), 'ti so luong giac');
 assert.ok(expandLessonSearchVariants('ty so').includes('ti so'));
 assert.equal(lessonMatchesSearch({name:'Toán 9',subject:'Toán'},{chapter:'Hệ thức lượng',title:'Tỉ số lượng giác của góc nhọn',outcome:'',text:''},'ty so'),true);
 assert.equal(lessonMatchesSearch({name:'Toán 9',subject:'Toán'},{chapter:'Hệ phương trình',title:'Giải hệ hai phương trình bậc nhất hai ẩn',outcome:'',text:''},'giai he phuong trinh'),true);
 assert.equal(lessonMatchesSearch({name:'Toán 9',subject:'Toán'},{chapter:'Hệ phương trình',title:'Giải hệ phương trình bằng phương pháp thế',outcome:'',text:''},'giai he bang phep the'),true);
 assert.equal(lessonMatchesSearch({name:'Toán 11',subject:'Toán'},{chapter:'Đạo hàm',title:'Đạo hàm',outcome:'Quy tắc tính đạo hàm',text:''},'dao ham'),true);
 assert.equal(lessonMatchesSearch({name:'Toán 12',subject:'Toán'},{chapter:'Nguyên hàm',title:'Nguyên hàm của hàm số',outcome:'',text:'Nội dung nguyên hàm'}),true);
 assert.equal(lessonMatchesSearch({name:'Toán 9',subject:'Toán'},{chapter:'Chương 1',title:'Quy tắc đếm',outcome:'',text:''},'qui tac'),true);

 const uni=latexToReadableUnicode('\\frac{a}{b}+\\sqrt{x}\\ge \\pi, \\triangle ABC, x\\in\\mathbb{R}, y\\le \\infty, z\\neq 0');
 assert.ok(uni.includes('a/b'));
 assert.ok(uni.includes('√(x)'));
 assert.ok(uni.includes('≥'));
 assert.ok(uni.includes('π'));
 assert.ok(uni.includes('△ABC'));
 assert.ok(uni.includes('ℝ'));
 assert.ok(uni.includes('≤'));
 assert.ok(uni.includes('∞'));
 assert.ok(uni.includes('≠'));
 assert.equal(formatOutlineTitleUnicode('Tính $\\frac{1}{2} + \\sqrt{9}$'),'Tính 1/2 + √(9)');

 const richMsg=assistantText('### Tiêu đề `x_1`\n1. Bước một **đậm**\n2. Bước hai `code`');
 assert.ok(richMsg.includes('<h4>Tiêu đề <code>x_1</code></h4>'));
 assert.ok(richMsg.includes('chat-list-ordered'));
 assert.ok(!richMsg.includes('</h4><br>'));
});
