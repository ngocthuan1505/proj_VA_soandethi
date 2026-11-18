import test from'node:test';import assert from'node:assert/strict';import{intentOf}from'../subject-profiles.js';import{richPositionMap,richSelection,documentPlain}from'../rich-document.js';import{blank,uid,clone}from'../core.js';import{ensureBlocks,requestScopes,questionScope,refreshScope,contextForScopes,validateEdits,applyEdits}from'../blocks.js';
const exam=()=>{const e=blank('Ngữ văn');e.questions=Array.from({length:3},(_,i)=>({id:uid(),v:1,type:'essay',points:2,stem:`Đề bài ${i+1}: Đọc đoạn văn và trả lời.`,explanation:'Lời giải. Giữ phần này.',options:[],rubric:[{text:'Nhận biết hình ảnh.',points:1},{text:'Phân tích tác dụng.',points:1}]}));return ensureBlocks(e);};
const partial=(q,field,start,end,index)=>({id:q.id,version:q.v,field,...(Number.isInteger(index)?{index}:{}),start,end,text:(field==='rubric'?q.rubric[index].text:q[field]).slice(start,end)});

test('Ràng buộc giữ nguyên và chữ trích dẫn không chuyển vùng sửa sang lời giải hoặc barem',()=>{
 const e=exam();e.questions.push({...clone(e.questions[0]),id:uid()});ensureBlocks(e);
 const q=e.questions[3],scope=questionScope(q);
 const request='Chỉ sửa đề bài Câu 4: thay cụm “dung dịch muối nồng độ cao” bằng “dung dịch chứa chất tan không phân li có nồng độ cao hơn dịch tế bào”. Giữ nguyên các giả định còn lại, phương án, đáp án, lời giải, điểm, chủ đề, mức nhận thức và ba câu khác.';
 const afterReload='Chỉ sửa đề bài Câu 4: thay cụm “(chất tan không phân li, không qua màng;” bằng “(không qua màng;” để bỏ chữ lặp. Giữ nguyên các giả định còn lại, phương án, đáp án, lời giải, điểm, chủ đề, mức nhận thức và ba câu khác.';
 for(const text of [request,afterReload,'Sửa đề bài câu 4, giữ nguyên lời giải và barem.','Sửa đoạn đang chọn. Không sửa lời giải câu 1 và câu 2.','Thay “lời giải câu 1” bằng “barem câu 2” trong đoạn đang chọn.']){
  const selected=requestScopes(e,text,{scopes:[scope]});
  assert.equal(selected.length,1,text);assert.equal(selected[0].id,q.id,text);
  assert.equal(selected[0].field,'stem',text);assert.equal(selected[0].allowFields,undefined,text);
 }
 const selected=partial(q,'stem',0,3);
 assert.deepEqual(requestScopes(e,'Sửa đoạn này. Giữ nguyên lời giải và barem.',{scopes:[selected]})[0],{...refreshScope(e,selected),permission:'edit'});
 assert.equal(requestScopes(e,'Giữ nguyên đề bài; sửa lời giải câu 2.',{scopes:[scope]})[0].field,'explanation');
 const moved=requestScopes(e,'Giữ nguyên lời giải và barem, chỉ sửa đề bài câu 2.',{scopes:[scope]});
 assert.equal(moved[0].id,e.questions[1].id);assert.equal(moved[0].field,'stem');
 assert.equal(requestScopes(e,'Sửa lời giải và barem câu 2',{scopes:[scope]})[0].field,'rubric');
 assert.equal(requestScopes(e,request,{scopes:[scope],intent:'verify'})[0].field,'explanation');
});
test('Ý định sửa không bị biến thành tạo đề/hỏi thường, kể cả chưa chọn vùng',()=>{for(const text of ['Viết lại đề bài 2 cho rõ hơn','Sửa câu 2 giúp tôi','Rút gọn đoạn đang chọn','Soạn lại đề hiện tại','Đổi số thành 9','Tại sao sai? Sửa giúp tui'])assert.equal(intentOf(text,[]),'edit',text);for(const text of ['Tạo đề Toán lớp 9','Soạn cho tui một đề mới','Viết một bài kiểm tra'])assert.equal(intentOf(text,[]),'create',text);for(const text of ['Chỉ giải thích, đừng sửa đề','Có nên sửa câu này không?'])assert.equal(intentOf(text,[{id:'x'}]),'explain',text);assert.equal(intentOf('Kiểm tra đáp án bài 2'),'verify');});
test('Ánh xạ đúng từ lặp, công thức nguyên tử, xuống dòng và ô bảng',()=>{const d={type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'abc abc '},{type:'mathInline',attrs:{latex:'x+1',display:false}},{type:'text',text:' abc'}]},{type:'paragraph',content:[{type:'text',text:'abc'}]}]};assert.equal(richSelection(d,5,8).start,4);assert.deepEqual(richSelection(d,9,10),{start:8,end:13,text:'$x+1$'});assert.deepEqual(richSelection(d,16,19),{start:18,end:21,text:'abc'});const table={type:'doc',content:[{type:'table',content:[{type:'tableRow',content:[{type:'tableCell',content:[{type:'paragraph',content:[{type:'text',text:'Ô một'}]}]},{type:'tableCell',content:[{type:'paragraph',content:[{type:'text',text:'Ô hai'}]}]}]}]}]};assert.equal(richPositionMap(table).text,documentPlain(table));const unit=richPositionMap(table).units.find(u=>u.start===documentPlain(table).indexOf('Ô hai'));assert.equal(richSelection(table,unit.from,unit.to).text,'Ô hai');});
test('Tên bài trong chat ưu tiên hơn vùng cũ; hỗ trợ danh sách và khoảng',()=>{const e=exam(),old=questionScope(e.questions[0]);assert.equal(requestScopes(e,'Sửa bài 2',{scopes:[old]})[0].id,e.questions[1].id);assert.deepEqual(requestScopes(e,'Sửa câu 1, 2 và 3',{}).map(s=>s.id),e.questions.map(q=>q.id));assert.equal(requestScopes(e,'Sửa bài 1 đến 3',{}).length,3);assert.throws(()=>requestScopes(e,'Sửa bài 8',{}),/không có/);});
test('Bỏ ngữ cảnh không dùng lại ngầm câu cũ; kiểm tra chỉ mở phần đáp án',()=>{const e=exam(),fallback=questionScope(e.questions[0]);assert.throws(()=>requestScopes(e,'Sửa giúp tui',{muted:true,fallback}),/Bôi đen/);assert.equal(requestScopes(e,'Sửa bài 2',{muted:true,fallback})[0].id,e.questions[1].id);const verified=requestScopes(e,'Kiểm tra cả đề',{intent:'verify'});assert.equal(verified.length,3);assert.ok(verified.every(s=>s.field==='explanation'&&s.permission==='verify'));});
test('Vùng bôi đen cũ chỉ cập nhật phiên bản khi chữ còn khớp; không ngầm mở rộng',()=>{const e=exam(),q=e.questions[0],s=partial(q,'stem',0,6);q.v++;assert.equal(refreshScope(e,s).version,q.v);q.stem='Mới '+q.stem;assert.throws(()=>refreshScope(e,s),/Bôi đen lại/);assert.equal(refreshScope(e,questionScope(q)).text,q.stem);});
test('Context hỏi đáp chứa đủ đề hiện tại và nhãn phần đã chọn',()=>{const e=exam(),q=e.questions[1],s=partial(q,'rubric',0,5,1),context=contextForScopes(e,[s])[0];assert.equal(context.questionNumber,2);assert.equal(context.fieldLabel,'Barem');assert.equal(context.question.stem,q.stem);assert.equal(context.index,1);});

test('Sửa đáp án chọn đúng trường theo loại câu, không chuyển nhầm sang đề bài',()=>{
 const e=exam();for(const [index,type]of ['short','truefalse','mcq'].entries())e.questions[index].type=type;
 assert.equal(requestScopes(e,'Chỉ sửa đáp án câu 1')[0].field,'answerText');
 assert.equal(requestScopes(e,'Sửa lại đáp án câu 2')[0].field,'truthValues');
 assert.equal(requestScopes(e,'Sửa đáp án câu 3')[0].field,'answer');
 assert.equal(requestScopes(e,'Chỉ đổi phương án câu 2')[0].field,'options');
});

test('Áp dụng đáp án typed giữ UUID, phần khác và đánh dấu có đáp án kể cả nội dung không đổi',()=>{
 for(const type of ['short','truefalse']){
  const e=exam(),q=e.questions[0],other=clone(e.questions[1]);q.type=type;q.answerKnown=false;
  const field=type==='short'?'answerText':'truthValues';q[field]=type==='short'?'30':[true,false,false,true];
  const before=clone(q),scope=questionScope(q,field),proposal={edits:[{blockId:q.blockIds[field],op:'replace',content:clone(q[field])}]};
  const result=validateEdits(e,proposal,[scope]);applyEdits(e,result.edits);
  assert(q.answerKnown);assert.equal(q.id,before.id);assert.equal(q.v,before.v+1);assert.equal(q.stem,before.stem);assert.deepEqual(e.questions[1],other);
  const wrong={edits:[{blockId:q.blockIds.answer,op:'replace',content:1}]};assert.throws(()=>validateEdits(e,wrong,[questionScope(q)]),/dạng câu/);
 }
});
test('Sửa đoạn trong barem không chạm bước khác, điểm hoặc chữ ngoài vùng',()=>{const e=exam(),q=e.questions[0],s=partial(q,'rubric',0,4,1),rows=clone(q.rubric);rows[1].text='Nêu '+rows[1].text.slice(4);const edit=()=>({edits:[{op:'replace',blockId:q.blockIds.rubric,content:rows}]});assert.ok(validateEdits(e,edit(),[s]));rows[0].text='Đổi bước khác';assert.throws(()=>validateEdits(e,edit(),[s]),/ngoài/);rows[0]=clone(q.rubric[0]);rows[1].text='Viết lại toàn dòng';assert.throws(()=>validateEdits(e,edit(),[s]),/ngoài/);});
test('Kiểm tra đáp án không cho thay stem/options; sửa explanation không đổi đề',()=>{const e=exam(),q=e.questions[0],s={...questionScope(q,'explanation'),permission:'verify'};assert.throws(()=>validateEdits(e,{edits:[{op:'replace',blockId:q.blockIds.stem,content:'Đề mới'}]},[s]),/đề bài|đề xuất|đề/);const partialScope=partial(q,'explanation',0,8);assert.throws(()=>validateEdits(e,{edits:[{op:'replace',blockId:q.blockIds.explanation,content:'Đổi toàn lời giải'}]},[partialScope]),/ngoài/);});
test('Áp dụng nhiều thay đổi là một giao dịch nguyên vẹn khi giữ định dạng bị lỗi',()=>{const e=exam(),before=clone(e),a=e.questions[0],b=e.questions[1];a.richDoc={type:'doc',content:[]};b.richDoc={type:'doc',content:[]};const initial=clone(e);let calls=0;assert.throws(()=>applyEdits(e,[{questionId:a.id,field:'stem',op:'replace',content:'Mới 1'},{questionId:b.id,field:'stem',op:'replace',content:'Mới 2'}],{richTransform:()=>{if(++calls===2)throw Error('Cannot preserve structure');return null;}}));assert.deepEqual(e,initial);const version=a.v;applyEdits(e,[{questionId:a.id,field:'stem',op:'replace',content:a.stem}]);assert.equal(a.v,version);});

test('Yêu cầu câu khác hoặc áp dụng gợi ý được chuyển sang sửa đúng phạm vi',()=>{for(const text of ['Cho 1 câu khác có độ khó cao hơn đi','Tạo câu hỏi khác khó hơn đi','Áp dụng vào bài đi','Ok sửa vào đi','Đưa vào đề giúp tui'])assert.equal(intentOf(text,[{id:'x'}]),'edit',text);});

test('Lời giải giữ chữ và công thức ngoài đoạn chọn theo fixture chung với Python', async () => {
 const {readFile}=await import('node:fs/promises');
 const fixture=JSON.parse(await readFile(new URL('./fixtures/ai-patch-local.json',import.meta.url),'utf8'));
 const e=exam(),q=e.questions[0];
 q.id=fixture.questionId;
 q.blockIds.explanation=fixture.blockId;
 q.explanation=fixture.text;
 const start=q.explanation.indexOf(fixture.selectionText);
 const scope=partial(q,'explanation',start,start+fixture.selectionText.length);
 for(const item of fixture.cases){
  const run=()=>validateEdits(e,{edits:[{op:'replace',blockId:fixture.blockId,content:item.content}]},[scope]);
  if(item.accepted)assert.equal(run().edits[0].content,item.content,item.id);
  else assert.throws(run,/ngoài/,item.id);
 }
});
