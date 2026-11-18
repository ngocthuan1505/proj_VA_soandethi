import {esc,clone,touch,check,recordCheck,questionAnswer} from './core.js';
import {reconcileEditorRich} from './editor.js';
import {richTextHTML} from './math-content.js';

export const answerLabel=(type,answer)=>answer===null||answer===undefined?'Chưa kết luận':type==='mcq'?'ABCD'[answer]:type==='truefalse'?answer.map((v,i)=>`${i+1}. ${v?'Đúng':'Sai'}`).join(' · '):String(answer);
export function selectedCheckSources(exam,q){
 const chosen=new Set(exam.assistantSources||[]);if(q.source?.docId)chosen.add(q.source.docId);
 return exam.docs.filter(d=>chosen.has(d.id)).flatMap(d=>(d.pages?.length?d.pages:[{number:1,text:d.text||''}]).filter(p=>p.text?.trim()).map(p=>({sourceId:d.id,sourceVersion:d.version||1,locator:{kind:'page',index:p.number},label:`${d.name} · trang ${p.number}`,length:p.text.length})));
}
const errorMessage=result=>result.error||result.detail?.message||(typeof result.detail==='string'?result.detail:'Chưa kiểm được câu. Hãy mở lại và thử lại.');
export async function openQuestionCheck(c,workspaceHeaders){
 const exam=c.exam(),q=c.qget(c.getSelected());if(!q)throw Error('Chọn một câu trước khi giải lại.');
 const identity={examId:exam.id,questionId:q.id,version:q.v,revision:exam.revision};
 await c.persist();const response=await fetch('/api/status',{headers:workspaceHeaders}),status=await response.json();if(!response.ok)throw Error(errorMessage(status));
 const current=()=>c.exam().id===identity.examId&&c.qget(identity.questionId)?.v===identity.version;
 if(!current()||c.exam().revision!==identity.revision)throw Error('Đề đã đổi; mở lại câu cần kiểm.');
 const sources=selectedCheckSources(exam,q),reviewer=status.reviewer||{provider:status.aiProvider,model:status.model};
 c.modal('Giải lại & đối chiếu',`<div class="scope"><small>Câu v${q.v}</small><div>${richTextHTML(q.stem)}</div></div><p class="hint">Bộ giải chỉ nhận đề bài, phương án và nguồn được chọn. Đáp án, lời giải và barem đang lưu được giữ lại để so sánh. Không tự sửa đề hoặc duyệt câu.</p><form id="question-check-form"><fieldset><legend>Nguồn đối chiếu</legend>${sources.length?sources.map((s,i)=>`<label class="consent"><input type="checkbox" name="check-source" value="${i}" checked> ${esc(s.label)} · ${s.length.toLocaleString('vi-VN')} ký tự</label>`).join(''):'<p class="hint">Chưa chọn nguồn. Có thể giải từ đề bài; kết quả sẽ ghi rõ chưa có căn cứ nguồn.</p>'}</fieldset><p class="hint">Đường kiểm: ${esc(reviewer.provider)} · ${esc(reviewer.model)}. Một số mẫu phép tính đơn giản được kiểm tại máy.</p><label class="consent"><input type="checkbox" id="question-check-consent" required> Cho phép gửi câu và các trang nguồn đã chọn tới kết nối kiểm này.</label><p data-check-error role="alert"></p><div class="modal-foot"><button type="button" data-action="close">Để sau</button><button type="submit" class="primary">Giải lại & đối chiếu</button></div></form>`);
 const form=document.querySelector('#question-check-form');let running=false,busyMessage=null;
 form.onsubmit=async event=>{
  event.preventDefault();event.stopPropagation();if(running)return;
  const error=form.querySelector('[data-check-error]');error.textContent='';
  try{
   if(!current()||c.exam().revision!==identity.revision)throw Error('Đề hoặc câu đã đổi; mở lại trước khi kiểm.');
   if(!form.querySelector('#question-check-consent').checked)throw Error('Cần xác nhận kết nối trước khi gửi.');
   const selected=[...form.querySelectorAll('[name=check-source]:checked')].map(n=>sources[Number(n.value)]);
   if(selected.length>12||selected.reduce((n,s)=>n+s.length,0)>12000)throw Error('Chọn tối đa 12 trang và 12.000 ký tự nguồn trong lượt kiểm này.');
   running=true;form.querySelector('[type=submit]').disabled=true;
   c.modal('Đang giải lại','<p role="status" data-check-running>Đang giải độc lập, chưa gửi đáp án hoặc lời giải đang lưu…</p><p class="hint">Đóng hộp này không tự hủy yêu cầu đang chạy. Kết quả không đổi nội dung câu.</p>');
   busyMessage=document.querySelector('[data-check-running]');
   const reply=await fetch(`/api/exams/${identity.examId}/questions/${identity.questionId}/check`,{method:'POST',headers:{...workspaceHeaders,'Content-Type':'application/json','X-PoC-Config':status.config.fingerprint},body:JSON.stringify({baseRevision:identity.revision,questionVersion:identity.version,consent:true,requireEvidence:selected.length>0,sources:selected.map(({sourceId,sourceVersion,locator})=>({sourceId,sourceVersion,locator}))})});
   const result=await reply.json();if(!reply.ok)throw Error(errorMessage(result));
   if(!current()||c.exam().revision!==identity.revision)throw Error('Câu hoặc đề đã đổi trong lúc giải; chưa lưu kết quả cũ.');
   const problems=[];
   if(result.comparison==='disagrees')problems.push(`Bất đồng: đáp án lưu ${answerLabel(q.type,questionAnswer(q))}, giải lại ${answerLabel(q.type,result.answer)}.`);
   if(result.uncertain)problems.push('Bộ giải chưa đủ chắc chắn; cần rà soát, không dùng tự động.');
   if(result.comparison==='needs_review'&&!result.uncertain)problems.push('Chưa kết luận tương đương đáp án/lời giải/barem; giáo viên cần đối chiếu.');
   if(!result.evidence.length&&result.method!=='local_arithmetic')problems.push('Chưa có trích dẫn khớp nguồn để đối chiếu.');
   const method=result.method==='local_arithmetic'?'Phép tính độc lập tại máy':`AI giải độc lập · ${reviewer.provider} · ${reviewer.model}`;
   c.change('Giải lại câu '+(exam.questions.indexOf(q)+1),()=>{recordCheck(q,{version:q.v,status:problems.length?'review':'consistent',problems,evidence:result.explanation,at:Date.now(),method,solver:result});},{renderPage:false});
   await c.persist();c.refreshInline();
   const reviewRevision=c.exam().revision,before=clone({answer:questionAnswer(q),explanation:q.explanation});
   if(!busyMessage.isConnected||!document.querySelector('#dialog').open){c.toast('Đã lưu kết quả giải lại cho câu đã chọn. Mở Rà soát để xem.');return;}
   const canApply=!result.uncertain&&result.answer!==null&&q.type!=='essay';
   c.modal('Kết quả giải lại',`<p role="status" class="alert ${problems.length?'':'success'}">${esc(problems.join(' ')||'Chưa thấy bất đồng trong lần kiểm này. Kết quả AI vẫn cần giáo viên xem lại.')}</p><p class="hint">${esc(method)} · Câu v${q.v}. Không đánh giá đầy đủ mức nhận thức hoặc mọi khía cạnh kiến thức.</p><div class="diff question-check-comparison ${result.uncertain?'uncertain':''}"><del><b>Đang lưu · ${esc(answerLabel(q.type,questionAnswer(q)))}</b><br>${richTextHTML(q.explanation||'Chưa có lời giải')}</del><ins><b>Giải lại · ${esc(answerLabel(q.type,result.answer))}</b><br>${richTextHTML(result.explanation)}</ins></div>${result.evidence.map(e=>`<blockquote>${esc(e.quote)}<br><small>Khớp chữ · trang ${e.locator.index} · nguồn v${e.sourceVersion}</small><br><button type="button" data-action="source" data-doc="${esc(e.sourceId)}" data-page="${e.locator.index}">Mở nguồn để đối chiếu</button></blockquote>`).join('')}${q.type==='essay'?'<p class="hint">Lời giải và barem tự luận giữ nguyên. Có thể nhờ chat sửa đồng bộ sau khi đối chiếu.</p>':''}<div class="modal-foot"><button type="button" data-action="close">Đóng</button>${canApply?'<button type="button" data-use-checked-answer>Dùng đáp án & lời giải này</button>':''}<button type="button" data-action="approve-question" data-id="${q.id}" data-version="${q.v}" class="primary">Tôi đã rà soát · duyệt câu hiện tại</button></div>`);
   document.querySelector('[data-use-checked-answer]')?.addEventListener('click',async event=>{
    const button=event.currentTarget;button.disabled=true;
    try{
     if(!current()||c.exam().revision!==reviewRevision||JSON.stringify(questionAnswer(q))!==JSON.stringify(before.answer)||q.explanation!==before.explanation)throw Error('Câu đã đổi; giải lại trước khi áp dụng.');
     const explanationDoc=reconcileEditorRich(q.explanationDoc,q.explanation||'',result.explanation);
     c.change('Dùng kết quả giải lại sau đối chiếu',()=>{
      if(q.type==='short')q.answerText=result.answer;
      else if(q.type==='truefalse')q.truthValues=clone(result.answer);
      else q.answer=result.answer;
      q.answerKnown=true;
      q.explanation=result.explanation;
      q.explanationDoc=explanationDoc;
      touch(q);
      check(exam,q);
     });
     await c.persist();document.querySelector('#dialog').close();c.toast('Đã dùng kết quả; bản mới cần rà soát và duyệt lại. Có thể hoàn tác.');
    }catch(e){button.disabled=false;c.toast(e.message);}
   });
  }catch(e){running=false;if(form.isConnected){error.textContent=e.message;form.querySelector('[type=submit]').disabled=false;}else if(busyMessage&&!document.querySelector('#dialog').open)c.toast(e.message);else c.modal('Chưa hoàn tất kiểm câu',`<p role="alert">${esc(e.message)}</p><p class="hint">Chưa dùng đáp án hoặc lời giải mới. Mở lại kiểm câu để thử tiếp.</p>`);}
 };
}
