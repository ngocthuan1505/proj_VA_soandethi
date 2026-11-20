import {answerLabel,selectedCheckSources} from '../question-check.js';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {questionAnswer,dataChartSVG,duplicateExam,recordCheck,approveQuestion,isApproved,sample,blank,clone,commit,undo,redo,touch,check,derive,updateData,matrix,exportHTML,snapshot} from '../core.js';

test('Đề trống dùng lời dặn chung, đề minh họa giữ lời dặn riêng',()=>{
 const exam=blank('Toán');
 assert.equal(exam.instructions,'Đọc kỹ và làm theo yêu cầu của từng câu.');
 assert.match(sample('Toán').instructions,/Chọn một phương án đúng/u);
});

test('Giá trị dữ kiện giữ nguyên không làm mất duyệt hoặc tăng phiên bản câu',()=>{
 const e=sample();approveQuestion(e.questions[0]);const before=clone(e);
 updateData(e,1,e.data[1].value);
 assert.deepEqual(e,before);
});

test('Câu hỏi B nhiều hơn A cần rà lại nếu B thấp hơn hoặc bằng A',()=>{
 const e=sample(),q=e.questions[1];
 for(const value of [90,120]){
  e.data[1].value=value;
  assert.match(derive(e,q).error,/tiền đề|không nhiều hơn/i);
  assert.equal(derive(e,q).result,undefined);
  assert.equal(check(e,q).status,'review');
 }
});

test('Lỗi rà câu liên kết giữa chừng giữ cả câu đã rà và bảng cũ',()=>{
 const e=sample();approveQuestion(e.questions[0]);e.questions[1].options=null;
 const before=clone(e);
 assert.throws(()=>updateData(e,1,300));
 assert.deepEqual(e,before);
});
test('Sửa đúng một câu, hết hiệu lực duyệt cũ, hoàn tác cả trạng thái',()=>{const e=sample();check(e,e.questions[0]);const previous=clone(e.questions);commit(e,'Sửa vùng chọn',()=>{e.questions[0].stem='Câu đã chỉnh';e.questions[0].rule=null;touch(e.questions[0]);});assert.deepEqual(e.questions.slice(1),previous.slice(1));assert.equal(e.questions[0].check,null);assert.equal(e.questions[0].v,2);assert.ok(undo(e));assert.deepEqual(e.questions,previous);assert.ok(redo(e));assert.equal(e.questions[0].stem,'Câu đã chỉnh');assert.equal(e.history.length,3);});
test('Tính lại không dùng đáp án cũ, nhận ra đáp án mẫu lệch và sửa theo phiên bản',()=>{const e=sample(),q=e.questions[1];const a=derive(e,q);q.answer=0;assert.equal(derive(e,q).answer,a.answer);assert.equal(check(e,q).status,'review');commit(e,'Sửa đáp án',()=>{q.answer=a.answer;q.explanation=a.explanation;touch(q);check(e,q);});assert.equal(q.check.status,'consistent');assert.equal(q.check.version,q.v);});
test('Dữ kiện–bảng–phép tính đổi cùng nhau; hoàn tác phục hồi đầy đủ',()=>{const e=sample();e.questions.forEach(q=>check(e,q));const before=snapshot(e);commit(e,'Đổi dữ kiện',()=>updateData(e,1,300));assert.equal(e.data[1].value,300);assert.equal(e.questions[1].check.status,'review');assert.equal(derive(e,e.questions[1]).result,180);assert.deepEqual(e.questions.slice(2),before.questions.slice(2));undo(e);assert.deepEqual(e.data,before.data);assert.deepEqual(e.questions,before.questions);});
test('Phát hiện trường hợp đồng hạng, phương án thiếu hoặc trùng; không tự gắn xanh',()=>{const e=sample();e.data[0].value=240;assert.equal(check(e,e.questions[0]).status,'review');e.data[0].value=120;e.questions[0].options[1]='Không có';assert.equal(check(e,e.questions[0]).status,'review');e.questions[1].options[0]='120 người';assert.equal(check(e,e.questions[1]).status,'review');});
test('Ma trận đếm từ dữ liệu thật sau thêm, đổi mức và xóa',()=>{const e=sample();assert.equal(matrix(e)[0].cells[0].actual,1);e.questions[0].level=1;assert.equal(matrix(e)[0].cells[0].actual,0);assert.equal(matrix(e)[0].cells[1].actual,1);e.questions.push({...clone(e.questions[0]),id:'another'});assert.equal(matrix(e)[0].cells[1].actual,2);e.questions.splice(0,1);assert.equal(matrix(e)[0].cells[1].actual,1);});
test('Yêu cầu xác nhận được sao chép độc lập qua hai đề, không tự sửa câu mẫu',()=>{const prefs=[{id:'p',text:'Tránh phủ định kép',confirmedAt:1},{id:'nhap',text:'Quy tắc nháp'}];const a=sample('Địa lí',prefs),b=blank('Lịch sử',prefs);assert.deepEqual(a.appliedPrefs,b.appliedPrefs);assert.deepEqual(a.appliedPrefs.map(p=>p.id),['p']);assert.notEqual(a.id,b.id);prefs[0].text='Quy tắc mới';assert.equal(a.appliedPrefs[0].text,'Tránh phủ định kép');});
test('Bản học sinh không chứa đáp án, giải thích, nguồn kiểm tra hoặc chat',()=>{const e=sample();e.questions[0].explanation='SECRET_EXPLANATION';e.chat.push({text:'SECRET_CHAT'});const s=exportHTML(e,false),t=exportHTML(e,true);assert.ok(!s.includes('SECRET_EXPLANATION'));assert.ok(!s.includes('Đáp án lưu'));assert.ok(!s.includes('SECRET_CHAT'));assert.ok(t.includes('SECRET_EXPLANATION'));assert.ok(t.includes('Đáp án lưu'));e.data[0].value=999;assert.ok(exportHTML(e).includes('999'));});
test('Ngữ liệu đã chọn không đổi khi sửa câu liên quan; undo/restore giữ phiên bản đề tăng',()=>{const e=sample('Ngữ văn');e.quote.chosen=e.quote.versions[0].id;const quote=clone(e.quote);commit(e,'Sửa câu',()=>{e.questions[0].stem='Nội dung mới';touch(e.questions[0]);});assert.deepEqual(e.quote,quote);const old=snapshot(e);commit(e,'Đổi tiêu đề',()=>e.title='Tên mới');const r=e.revision;commit(e,'Khôi phục',()=>Object.assign(e,old));assert.equal(e.revision,r+1);undo(e);assert.equal(e.title,'Tên mới');});
test('Xuất HTML thoát nội dung nhập tay, không chạy mã',()=>{const e=sample();e.questions[0].stem='<img src=x onerror=alert(1)>';const out=exportHTML(e);assert.ok(out.includes('&lt;img'));assert.ok(!out.includes('<img src=x'));});
test('Quy tắc độ dài đã xác nhận được thực thi qua đề mới',()=>{const pref={id:'short',text:'Câu ngắn',kind:'short',maxWords:30,confirmedAt:1};const a=sample('Địa lí',[pref]),b=sample('Ngữ văn',[pref]);for(const e of [a,b]){e.questions[0].stem=Array(31).fill('từ').join(' ');e.questions[0].rule=null;const result=check(e,e.questions[0]);assert.equal(result.status,'review');assert.ok(result.problems.some(p=>p.includes('vượt 30 từ')));}});
test('Bản xuất giữ bảng khi thân câu đã đổi và không đưa ghi chú biên soạn vào đề học sinh',()=>{const e=sample('Địa lí',[{text:'GHI_CHU_CUA_THAY_CO',confirmedAt:1}]);for(const q of e.questions.filter(q=>q.rule)){q.rule=null;q.dataLinked=true;}const s=exportHTML(e);assert.ok(s.includes('Bảng 1. Số người sử dụng thư viện'));assert.ok(!s.includes('GHI_CHU_CUA_THAY_CO'));assert.ok(exportHTML(e,true).includes('GHI_CHU_CUA_THAY_CO'));});
test('Ví dụ Toán có nguồn, ma trận và bốn phép kiểm độc lập đáp án lưu',()=>{const e=sample('Toán');assert.equal(e.subject,'Toán');assert.equal(e.questions.length,5);assert.equal(check(e,e.questions[0]).status,'review');for(const q of e.questions.slice(1,4))assert.equal(check(e,q).status,'consistent');assert.equal(check(e,e.questions[4]).status,'unverified');assert.ok(e.docs[0].text.includes('Phương trình'));assert.equal(matrix(e).flatMap(r=>r.cells).reduce((s,c)=>s+c.actual,0),5);assert.ok(!exportHTML(e).includes('Số người sử dụng thư viện'));});
test('Sửa x² = 9 thành x² = −9 tính lại ∅; sửa và undo đúng phiên bản',()=>{const e=sample('Toán'),q=e.questions[0],before=clone(e.questions);commit(e,'Đổi số',()=>{q.stem=q.stem.replace('= 9','= −9');touch(q);check(e,q);});assert.equal(derive(e,q).answer,3);assert.equal(q.check.version,2);assert.equal(q.check.status,'review');commit(e,'Sửa đáp án',()=>{const d=derive(e,q);q.answer=d.answer;q.explanation=d.explanation;touch(q);check(e,q);});assert.equal(q.check.status,'consistent');assert.deepEqual(e.questions.slice(1),before.slice(1));undo(e);assert.equal(e.questions[0].answer,1);undo(e);assert.deepEqual(e.questions,before);});
test('Phép kiểm Toán xử lý thiếu phương án và không khẳng định dạng chưa hỗ trợ',()=>{const e=sample('Toán'),q=e.questions[0];q.stem=q.stem.replace('= 9','= 2');const d=derive(e,q);assert.equal(d.answer,null);assert.equal(d.replacement,'{−√2; √2}');q.options[0]=d.replacement;assert.equal(derive(e,q).answer,0);q.stem='Hãy chứng minh một định lí bất kỳ.';assert.equal(derive(e,q),null);assert.equal(check(e,q).status,'unverified');});


test('Duyệt thủ công giữ nguyên bằng chứng kiểm, sửa câu bỏ duyệt, undo khôi phục cả hai',()=>{
 const e=sample(),q=e.questions[0];check(e,q);const proof=clone(q.check);
 commit(e,'Duyệt',()=>approveQuestion(q));assert(isApproved(q));assert.deepEqual(q.check,proof);
 commit(e,'Đổi câu',()=>{q.stem+=' Mới';touch(q);});assert(!isApproved(q));assert.equal(q.check,null);
 undo(e);assert(isApproved(e.questions[0]));assert.deepEqual(e.questions[0].check,proof);
 check(e,e.questions[0]);assert(isApproved(e.questions[0]));
 const legacy={v:2,check:{version:2,status:'approved'}};assert(isApproved(legacy));touch(legacy);assert(!isApproved(legacy));
});

test('Kiểm câu chỉ chọn đúng trang nguồn có ID/version, nhãn đáp án đa dạng',()=>{
 const e=blank('Sinh học'),q={source:{docId:'B'}};e.assistantSources=['A'];
 e.docs=[{id:'A',version:3,name:'A',text:'Nguồn A'}, {id:'B',name:'B',pages:[{number:2,text:'Nguồn B2'},{number:3,text:''}]},{id:'C',text:'Không được chọn'}];
 const before=clone(e);const sources=selectedCheckSources(e,q);assert.deepEqual(sources.map(s=>[s.sourceId,s.sourceVersion,s.locator.index]),[['A',3,1],['B',1,2]]);assert.deepEqual(e,before);
 assert.equal(answerLabel('mcq',2),'C');assert.equal(answerLabel('essay',null),'Chưa kết luận');assert.equal(answerLabel('short','42'),'42');assert.equal(answerLabel('truefalse',[true,false,true,false]),'1. Đúng · 2. Sai · 3. Đúng · 4. Sai');
});

test('Kiểm mới kế thừa duyệt thủ công dữ liệu cũ mà không giả là AI đã đồng ý',()=>{
 const q={v:3,check:{version:3,status:'approved',at:123}};recordCheck(q,{version:3,status:'review',problems:['AI bất đồng']});assert(isApproved(q));assert.equal(q.approval.at,123);assert.equal(q.check.status,'review');
});


test('Nhân bản đề cấp ID mới và bỏ job/duyệt cũ, giữ nguyên bản gốc và nội dung',()=>{
 const original=sample('Toán');original.activeAIJob=crypto.randomUUID();original.aiPlan={pending:true};
 original.blockIds={heading:crypto.randomUUID()};
 const q=original.questions[0];q.blockIds={stem:crypto.randomUUID()};q.approval={version:q.v,status:'approved'};
 const before=clone(original),copy=duplicateExam(original);
 assert.notEqual(copy.id,original.id);assert.equal(copy.revision,1);
 for(let i=0;i<original.questions.length;i++){
  assert.notEqual(copy.questions[i].id,original.questions[i].id);assert.equal(copy.questions[i].stem,original.questions[i].stem);
  assert.equal(copy.questions[i].v,1);assert.equal(copy.questions[i].check,null);assert.equal(copy.questions[i].approval,undefined);
  assert.equal(copy.questions[i].blockIds,undefined);
 }
 assert.equal(copy.activeAIJob,undefined);assert.equal(copy.aiPlan,undefined);assert.equal(copy.blockIds,undefined);
 assert.deepEqual(copy.chat,[]);assert.deepEqual(copy.history,[]);assert.deepEqual(original,before);
});


test('Biểu đồ dùng đúng dữ kiện, thoát nhãn và chặn số không hợp lệ',()=>{
 const svg=dataChartSVG([{label:'<script>tự viết</script>',value:0},{label:'B',value:240}]);
 assert(svg.includes('viewBox=')&&svg.includes('240'));assert(svg.includes('&lt;script&gt;'));assert(!svg.includes('<script>'));
 for(const value of [NaN,Infinity,-1,'240'])assert.throws(()=>dataChartSVG([{label:'A',value}]),/Dữ kiện/);
});


test('Đọc đáp án đúng trường, không nhầm đáp án ngắn/đúng-sai thành A',()=>{
 assert.equal(questionAnswer({type:'short',answer:0,answerText:'42'}),'42');
 assert.deepEqual(questionAnswer({type:'truefalse',answer:0,truthValues:[true,false,true,false]}),[true,false,true,false]);
 assert.equal(questionAnswer({type:'mcq',answer:2}),2);
 assert.equal(questionAnswer({type:'short',answerText:'42',answerKnown:false}),null);
 assert.equal(questionAnswer({type:'essay',answer:0}),null);
 assert.equal(questionAnswer({type:'short',answer:'bản cũ'}),'bản cũ');
});


import {validateMatrixRows} from '../core.js';
test('Ma trận bốn mức giữ điểm khác nhau theo mức và vẫn đọc ma trận ba mức cũ',()=>{
 const rows=[{topic:'A',type:'essay',targets:[4,5,2,2],pointsByLevelQ4:[2,4,3,3]}];
 assert.equal(validateMatrixRows(rows),rows);
 for(const bad of [
  [{...rows[0],pointsQ4:2}],
  [{...rows[0],pointsByLevelQ4:[2,4,3]}],
  [{...rows[0],pointsByLevelQ4:[2,4,3,0]}],
  [{...rows[0],pointsByLevelQ4:[2,4,3,4]}],
 ])assert.throws(()=>validateMatrixRows(bad));
 assert.doesNotThrow(()=>validateMatrixRows([{topic:'Cũ',targets:[2,1,1]}]));
});
test('Ma trận30câu và nhiều loại giữ đúng cơ cấu, chặn thiếu/thừa điểm trước sinh',()=>{
 assert.doesNotThrow(()=>validateMatrixRows([{topic:'A',targets:[28,1,1]}]));
 const rows=[{topic:'A',type:'mcq',targets:[2,0,0],pointsQ4:2},{topic:'A',type:'essay',targets:[0,1,0]}];
 assert.equal(validateMatrixRows(rows),rows);
 for(const bad of [[{topic:'A',targets:[29,1,1]}],[{topic:'A',type:'unknown',targets:[1,0,0]}],[{topic:'A',targets:[1,0,0],pointsQ4:39}],[{topic:'A',targets:[2,0,0],pointsQ4:20},{topic:'B',targets:[1,0,0]}]])assert.throws(()=>validateMatrixRows(bad));
});
