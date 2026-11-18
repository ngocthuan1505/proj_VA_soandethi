import {richTextHTML,diffContentHTML} from './math-content.js';
import {esc, LEVELS, QUESTION_TYPES} from './core.js';
import * as db from './storage.js';

async function api(url, body, headers={}){
 const response=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)});
 const result=await response.json();
 if(!response.ok)throw Error(result.error||result.detail?.message||JSON.stringify(result.detail||result));
 return result;
}

export async function openMatrixSynthesis(c, options={}){
 const inline=!!options.host;
 const examId=options.examId||c.exam().id;
 const status=await api('/api/status');
 const destinations=[status.aiProvider,status.reviewer?.provider||status.aiProvider];
 const destination=[...new Set(destinations)].map(p=>p==='gemini'?'Gemini API của Google':'Ollama trên máy').join(' và ');
 const checkNames={validate_schema:'Cấu trúc',check_matrix_and_scoring:'Ma trận và điểm',retrieve_evidence:'Đoạn nguồn',check_evidence:'Căn cứ nguồn',solve_blind:'Giải lại',verify_options:'Bốn phương án',review_level:'Mức nhận thức',check_duplicates:'Trùng ý',check_explanation:'Lời giải',aggregate_checks:'Tổng hợp'};
 const budget=status.runBudget||{maxModelCalls:24,timeoutSeconds:900};
 if(!status.matrixPython){c.toast('Mở bản Python cục bộ để dùng luồng sinh theo ma trận.');return;}
 await c.persist();
 if(c.exam().id!==examId)throw Error('Đã chuyển đề trong lúc mở tác vụ. Mở lại ở đúng đề cần soạn.');
 const exam=c.exam(),baseRevision=exam.revision;
 if(!exam.matrixConfirmed){c.toast('Lưu và xác nhận ma trận trước khi sinh.');return;}
 const rows=exam.matrix||[],count=rows.flatMap(r=>r.targets).reduce((n,x)=>n+x,0);
 const currentDocs=exam.docs.filter(d=>exam.assistantSources?.includes(d.id));
 const pendingPages=currentDocs.flatMap(d=>(d.pages?.length?d.pages:[{number:1}])
  .filter(p=>p.needsOCR||(p.needsReview??(d.needsReview||p.uncertain===true||p.uncertain?.length)))
  .map(p=>d.name+' · trang '+p.number));
 let source=currentDocs.map(d=>d.text||d.pages?.map(p=>p.text).join('\n')).filter(Boolean).join('\n\n');
 let job=null,lastCandidate=null,approval=null,closed=false,reviews={},polling=false,deciding=false;
 const errorNames={incomplete_response:'AI bị ngắt trước khi trả đủ bộ câu; bản đề giữ nguyên. Có thể giảm số câu hoặc thử lại; tải log để xem chi tiết',duplicate_question:'Câu hỏi bị trùng',invalid_options:'Phương án chưa hợp lệ',answer_disagreement:'Đáp án chưa khớp lượt giải lại',level_disagreement:'Mức thực tế chưa khớp ma trận',explanation_disagreement:'Lời giải chưa khớp',uncertain_answer:'Lượt giải chưa đủ chắc chắn',unsupported_answer:'Chưa đủ căn cứ',topic_disagreement:'Chưa đúng chủ đề',invalid_review:'Lượt rà trả dữ liệu chưa hợp lệ',attempt_limit:'Đã hết giới hạn của lượt thử cũ',call_budget:'Đã hết ngân sách gọi AI',timeout:'Đã hết thời gian tự xử lý',provider_http_error:'Dịch vụ AI đang trả lỗi',provider_quota:'Đã hết hạn mức dịch vụ AI',provider_auth:'Khóa Gemini chưa hợp lệ; mở Kết nối để thay khóa',provider_timeout:'Dịch vụ AI quá thời gian chờ; bản đề giữ nguyên',check_not_completed:'Một số phép kiểm chưa hoàn tất',option_verdicts_failed:'Có nhiều đáp án đúng hoặc phương án chưa rõ',semantic_duplicate:'Câu hỏi trùng ý',uncertain_duplicate:'Chưa kết luận được trùng ý',interrupted:'App đã khởi động lại khi tác vụ chưa hoàn tất',stale_snapshot:'Đề hoặc nguồn đã thay đổi',provider_unavailable:'Chưa kết nối được AI đã chọn'};
 const errorText=e=>(e.ordinal!==undefined?'Câu '+(e.ordinal+1)+': ':'')+(errorNames[e.code]||e.code)+(e.reason?' — '+e.reason:'')+(e.details?.length?' · '+e.details.map(d=>d.message).join('; '):'');
 const markup=`${inline?'<p>Trợ lý soạn, tự kiểm và sửa bộ câu. Xem lại trên trang đề rồi chọn chấp nhận hoặc bỏ.</p><details><summary>Kết nối và giới hạn</summary>':''}<p>Sinh bằng <b>${esc(status.model)}</b> · kiểm bằng <b>${esc(status.reviewer?.model||status.model)}</b>. Nguồn được gửi tới ${esc(destination)}. ${status.matrixAgent?`Trợ lý tự soạn, gọi công cụ kiểm và sửa theo lỗi trong ngân sách ${budget.maxModelCalls} lần gọi AI, tối đa ${budget.timeoutSeconds} giây. Thầy cô không cần xử lý từng vòng.`:'Bản thử cũ sinh từng ô, mỗi ô có giới hạn lượt riêng.'} Chỉ trả bản cuối đã qua bộ kiểm; thầy cô xem lại trước khi xác nhận lưu.</p>${inline?'</details>':''}
 <details class="matrix-chat-summary"><summary>Ma trận đã xác nhận · ${count} câu</summary><table class="matrix-full"><thead><tr><th>Chủ đề / loại câu</th>${LEVELS.map(x=>'<th>'+x+'</th>').join('')}</tr></thead><tbody>${rows.map(r=>'<tr><td>'+esc(r.topic)+' · '+esc(QUESTION_TYPES[r.type||'mcq'])+'</td>'+r.targets.map(n=>'<td>'+n+'</td>').join('')+'</tr>').join('')}</tbody></table></details>
 ${inline?'<button type="button" id="matrix-edit-plan">Chỉnh / tải file ma trận</button>':''}<p>${count} / tối đa 30 câu, bốn dạng · tổng 10 điểm. Chia điểm theo bước 0,25; phần dư phân theo thứ tự ô.</p>
 <label>Cách soạn<select id="matrix-source-mode"><option value="provided" ${source?'selected':''}>Theo tài liệu nguồn</option><option value="general" ${source?'':'selected'}>Theo kiến thức môn/lớp · không có tài liệu đối chiếu</option></select></label><p class="hint" id="matrix-general-note">Soạn không nguồn vẫn giải lại và rà lời giải, nhưng chưa xác minh với SGK/tài liệu. Giáo viên cần kiểm tra kiến thức và phạm vi.</p><details id="matrix-inputs" ${source?'open':''}><summary>Thêm tài liệu nguồn (tùy chọn)</summary><label>Tên nguồn<input id="matrix-source-name" maxlength="200" value="${esc(currentDocs.map(d=>d.name).join('; '))}" placeholder="Ghi đúng tên hoặc ghi ngữ liệu tự viết"></label>
 <label>Nội dung nguồn cho lượt sinh<textarea id="matrix-source-text" rows="4" maxlength="12000" placeholder="Dán ngữ liệu cần ra câu hỏi. Không tự coi đây là trích SGK nếu chưa có nguồn.">${esc(source)}</textarea></label>
 ${pendingPages.length?`<p id="matrix-source-warning" class="hint">Trang chưa đọc hoặc chưa đối chiếu: ${esc(pendingPages.slice(0,6).join('; '))}${pendingPages.length>6?' và '+(pendingPages.length-6)+' trang nữa':''}. Rà lại phần văn bản trước khi sinh.</p>`:''}
 <label><input type="checkbox" id="matrix-consent" style="width:auto"> Cho phép gửi yêu cầu và tài liệu đã chọn tới ${esc(destination)} để sinh và tự kiểm đề.</label></details>
 <div class="toolbar-row"><button type="button" id="matrix-start" class="primary">${inline?"Bắt đầu soạn":"Duyệt yêu cầu và sinh"}</button><button type="button" id="matrix-stop" disabled>Dừng tác vụ</button><button type="button" id="matrix-download" disabled>Tải log</button><button type="button" id="matrix-review-pack" disabled>Phiếu rà độc lập</button></div>
 <p id="matrix-status" role="status">Chưa chạy. Bản đề hiện có ${exam.questions.length} câu.</p><button type="button" id="matrix-poll-retry" hidden>Tải lại trạng thái</button><p id="matrix-metrics" class="hint"></p>
 <label id="matrix-reviewer-field" hidden>Người rà (không bắt buộc)<input id="matrix-reviewer" maxlength="120" placeholder="Ghi đúng người rà nếu muốn lưu góp ý từng câu"></label>
 <details id="matrix-progress"><summary>Nhật ký tự kiểm và sửa</summary><div id="matrix-trace" aria-live="polite"></div></details><div id="matrix-audit" class="hint"></div><div id="matrix-checks"></div><div id="matrix-preview"></div>
 <p id="matrix-review-summary" role="status"></p><label ${inline?'hidden':''}><input type="checkbox" id="matrix-final-check" style="width:auto"> Tôi đã xem lại kết quả cuối và đồng ý thay bộ câu trong đề.</label>
 ${inline?'<button type="button" id="matrix-view-proposal" hidden>Xem đề xuất trên trang</button><div class="matrix-decisions">':''}<button type="button" id="matrix-confirm-save" class="primary" disabled>${inline?"✓ Chấp nhận":"Xác nhận thay bộ câu trong đề"}</button>${inline?'<button type="button" id="matrix-discard" class="matrix-discard">✕ Bỏ đề xuất</button></div>':''}
 <p class="hint">Nhãn trong ma trận là yêu cầu. Đọc từng câu, đáp án và đoạn trích trước khi ghi mức thực tế. Qua kiểm cấu trúc không có nghĩa đã đúng kiến thức hoặc đúng mức.</p>`;
 if(inline)options.host.innerHTML='<h3>Soạn theo ma trận</h3>'+markup;else c.modal('Sinh bộ câu theo ma trận',markup);
 const dialog=options.host||document.querySelector('#dialog'),$=id=>dialog.querySelector('#'+id)||options.find?.(id);
 if(inline){
  const heading=dialog.querySelector('h3'),intro=heading.nextElementSibling,connection=intro.nextElementSibling;
  intro.remove();
  const request=document.createElement('details');request.id='matrix-request-settings';request.open=true;
  request.innerHTML='<summary>Yêu cầu soạn đề · '+count+' câu</summary>';
  const matrix=dialog.querySelector('.matrix-chat-summary'),edit=$('matrix-edit-plan'),score=edit.nextElementSibling;
  request.append(matrix,edit,score,$('matrix-source-mode').closest('label'),$('matrix-general-note'),$('matrix-inputs'),$('matrix-consent').closest('label'));heading.after(request);
  const startActions=document.createElement('div');startActions.className='matrix-start-actions';
  startActions.append($('matrix-start'));request.append(startActions);
  const later=document.createElement('button');later.type='button';later.textContent='Để sau';later.id='matrix-dismiss';startActions.append(later);
  const details=document.createElement('details');details.id='matrix-result-details';details.innerHTML='<summary>Chi tiết lượt xử lý</summary>';
  const retry=document.createElement('button');retry.type='button';retry.id='matrix-retry';retry.textContent='Xem yêu cầu và thử lại';retry.hidden=true;
  retry.onclick=()=>{$('matrix-request-settings').open=true;$('matrix-inputs').open=true;$('matrix-start').focus();};
  $('matrix-status').after(retry);
  const utilities=document.createElement('div');utilities.className='matrix-utilities';utilities.append($('matrix-download'),$('matrix-review-pack'));
  details.append(connection,$('matrix-metrics'),$('matrix-reviewer-field'),$('matrix-progress'),$('matrix-audit'),$('matrix-checks'),utilities,dialog.querySelector(':scope>p.hint:last-child'));
  $('matrix-status').after(details);
  const decisions=dialog.querySelector('.matrix-decisions');decisions.setAttribute('aria-label','Duyệt đề xuất');
  const label=document.createElement('b');label.className='matrix-decision-title';label.textContent=count+' câu chờ duyệt';
  decisions.prepend(label,$('matrix-view-proposal'));decisions.append($('matrix-review-summary'));
  const stop=$('matrix-stop');stop.hidden=true;dialog.append(stop);dialog.querySelector('.toolbar-row').remove();
 }
 const sameExam=()=>c.exam().id===exam.id&&c.exam().revision===baseRevision;
 const setStatus=text=>{$('matrix-status').textContent=text;};
 let preparing=false;
 function syncPhase(){
  if(!inline)return;
  const phase=job?.status==='running'||preparing?'running':job?.status==='complete'&&!job.saved&&lastCandidate?.jobId===job.jobId&&$('matrix-poll-retry').hidden?'review':job?'error':'setup';
  const changed=dialog.dataset.phase!==phase;dialog.dataset.phase=phase;
  if(changed){$('matrix-request-settings').open=phase==='setup';$('matrix-result-details').open=false;$('matrix-progress').open=false;}
  $('matrix-result-details').hidden=phase==='setup';$('matrix-status').hidden=phase==='setup'&&!$('matrix-status').dataset.error;
  $('matrix-retry').hidden=phase!=='error'||!$('matrix-poll-retry').hidden;
  options.phase?.({phase,cancellable:!$('matrix-stop').disabled,decisions:dialog.querySelector('.matrix-decisions')||options.find?.('matrix-confirm-save')?.parentElement,stop:()=>{$('matrix-stop').click();}});
 }
 const guard=fn=>async event=>{event?.preventDefault();event?.stopPropagation();try{await fn();}catch(error){preparing=false;$('matrix-status').dataset.error='true';setStatus(error.message);$('matrix-start').disabled=job?.status==='running';syncPhase();}};
 const lockSources=locked=>{for(const id of ['matrix-source-name','matrix-source-text','matrix-consent','matrix-source-mode'])$(id).disabled=locked;};
 const decide=fn=>guard(async()=>{if(deciding)return;deciding=true;lockSources(true);for(const id of ['matrix-confirm-save','matrix-discard','matrix-start'])if($(id))$(id).disabled=true;try{await fn();}finally{deciding=false;if(dialog.isConnected){lockSources(job?.status==='running');if($('matrix-discard'))$('matrix-discard').disabled=false;$('matrix-start').disabled=job?.status==='running';updateConfirm();}}});
 const discardCandidate=async()=>{const candidate=job?.status==='complete'?job:lastCandidate;if(candidate){await api('/api/exams/'+exam.id+'/proposals/'+candidate.jobId+'/discard',{});lastCandidate=null;}};
 for(const id of ['matrix-source-name','matrix-source-text','matrix-source-mode'])$(id).addEventListener('input',()=>{if(job?.status==='running')return;job=null;reviews={};$('matrix-review-pack').disabled=true;$('matrix-audit').textContent='';$('matrix-download').disabled=true;options.clearPreview?.();$('matrix-preview').innerHTML='';$('matrix-checks').innerHTML='';$('matrix-metrics').textContent='';$('matrix-final-check').checked=false;updateConfirm();setStatus('Nguồn đã đổi. Bấm sinh để tạo và kiểm bộ câu theo nguồn mới.');});
 const cancel=async()=>{if(job?.status==='running'){job=await api(base()+'/cancel',{});setStatus(job.status==='cancelled'?'Đã dừng. Bản đề đang lưu được giữ nguyên.':'Tác vụ đã hoàn tất trước khi yêu cầu dừng tới nơi. Hãy xem kết quả trước khi lưu.');}};
 if(!inline)dialog.addEventListener('close',()=>{closed=true;cancel().catch(()=>{});},{once:true});
 if(inline)$('matrix-discard').onclick=decide(async()=>{await cancel();await discardCandidate();closed=true;await options.finish('discarded');});
 if(inline)$('matrix-dismiss').onclick=$('matrix-discard').onclick;
 if(inline)$('matrix-view-proposal').onclick=options.viewPreview;
 if(inline)$('matrix-edit-plan').onclick=guard(async()=>{if(job?.status==='running')throw Error('Dừng tác vụ trước khi chỉnh ma trận.');await discardCandidate();closed=true;options.clearPreview();options.editMatrix();});
 function base(){return '/api/exams/'+exam.id+'/proposals/'+job.jobId;}
 function updateConfirm(){
  const questions=job?.proposal?.questions||[];
  const unresolved=status.matrixAgent?Object.entries(reviews).some(([i,r])=>r.observed!==questions[Number(i)]?.level||!r.contentOk):questions.some((q,i)=>reviews[String(i)]?.observed!==q.level||!reviews[String(i)]?.contentOk);
  $('matrix-review-summary').textContent=unresolved?'Còn góp ý chưa được xử lý. Mở “Góp ý câu này” ở các câu có nhận xét trước khi xác nhận lưu.':'';
  $('matrix-confirm-save').disabled=deciding||!sameExam()||job?.saved||lastCandidate?.jobId!==job?.jobId||!$('matrix-poll-retry').hidden||!questions.length||unresolved||(!inline&&!$('matrix-final-check').checked);
  if(!sameExam()&&questions.length)$('matrix-review-summary').textContent='Đề đã thay đổi. Giữ bản vừa sửa và tạo lượt sinh mới trước khi chấp nhận.';
  syncPhase();
 }
 $('matrix-final-check').onchange=updateConfirm;
 $('matrix-reviewer').oninput=()=>{$('matrix-preview').querySelectorAll('[name=reviewer]').forEach(input=>input.value=$('matrix-reviewer').value);};
 function showChecks(report){
  if(!report.checks?.length)return;
  const open=$('matrix-checks').querySelector('details')?.open;
  const counts=Object.fromEntries(['PASS','FAIL','UNKNOWN'].map(s=>[s,report.checks.filter(r=>r.status===s).length]));
  $('matrix-checks').innerHTML=`<details ${open?'open':''}><summary>Báo cáo kiểm · lần nộp ${report.generationAttempt}: ${counts.PASS} đạt, ${counts.FAIL} lỗi, ${counts.UNKNOWN} chưa kết luận</summary><p class="hint">Mã bản: <code style="overflow-wrap:anywhere">${esc(report.candidateHash)}</code>. Các bước rà dùng chung một lượt AI có thời gian chồng nhau; không cộng các hàng để đo thời gian chờ.</p><table class="matrix-full"><thead><tr><th>Phép kiểm</th><th>Kết quả</th></tr></thead><tbody>${report.checks.map(r=>`<tr><td>${esc(checkNames[r.toolName]||r.toolName)}</td><td>${esc({PASS:'Đạt kiểm',FAIL:'Có lỗi',UNKNOWN:'Chưa kết luận'}[r.status]||r.status)}</td></tr>`).join('')}</tbody></table></details>`;
  const m=report.summary;
  if(m)$('matrix-metrics').textContent=`Lượt này: ${m.modelCalls||0}/${m.budget?.maxModelCalls||budget.maxModelCalls} lần gọi AI · ${Number(m.elapsedSeconds||0).toFixed(2)} giây · Sinh: ${m.generator?.model||'—'} · Kiểm: ${m.reviewer?.model||'—'}`;
 }
 function showProposal(){
  lastCandidate=job;
  $('matrix-reviewer-field').hidden=false;
  reviews=job.reviews||{};
  if(!$('matrix-reviewer').value) $('matrix-reviewer').value=Object.values(reviews)[0]?.reviewer||'';
  $('matrix-preview').innerHTML='<h3>Bản xem trước · chưa ghi vào đề</h3>'+job.proposal.questions.map((q,i)=>`<section class="matrix-review-question" style="border:1px solid #c7d8d1;border-radius:8px;padding:16px;margin:16px 0" data-matrix-question="${i}">
   <p><b>Câu ${i+1} · ${esc(q.topic)} · Yêu cầu: ${LEVELS[q.level]} · ${q.pointsQ4/4} điểm</b></p>
   <p>${richTextHTML(q.stem)}</p><ol type="A">${q.options.map(x=>'<li>'+richTextHTML(x)+'</li>').join('')}</ol>
   <p>Đáp án AI đề xuất: <b>${q.type==='essay'?'Tự luận':diffContentHTML(q.type==='mcq'?'answer':q.type==='truefalse'?'truthValues':'answerText',q.answer)}</b>. ${richTextHTML(q.explanation)}</p>
   ${q.rubric?.length?'<div class="matrix-rubric"><b>Hướng dẫn chấm</b>'+diffContentHTML('rubric',q.rubric.map(r=>({...r,points:r.pointsQ4/4})))+'</div>':''}
   ${q.evidence.map(e=>'<blockquote>“'+esc(e.quote)+'”<br><small title="'+esc(e.sourceId)+'">'+esc($('matrix-source-name').value||'Nguồn đã chọn')+' · bản '+e.sourceVersion+' · đoạn '+e.locator.index+'</small></blockquote>').join('')}
   <details><summary>Góp ý câu này nếu còn vấn đề</summary><form data-matrix-review="${i}"><label>Người rà<input name="reviewer" required maxlength="120" value="${esc($('matrix-reviewer').value)}" placeholder="Tên người ghi nhận xét…"></label><label>Mức thực tế theo người rà<select name="observed" required><option value="">Chọn sau khi đọc câu</option>${LEVELS.map((l,n)=>'<option value="'+n+'">'+l+'</option>').join('')}<option value="-1">Chưa đủ căn cứ</option></select></label><label>Lý do (học sinh cần làm gì; đáp án/căn cứ có vấn đề gì?)<input name="reason" required minlength="4" maxlength="600"></label><label><input type="checkbox" name="contentOk" style="width:auto"> Đã đối chiếu và thấy đáp án, giải thích, căn cứ phù hợp</label><button type="submit">Ghi nhận đánh giá</button><output></output></form></details></section>`).join('');
  for(const form of $('matrix-preview').querySelectorAll('[data-matrix-review]')){const previous=reviews[form.dataset.matrixReview];if(previous){form.elements.reviewer.value=previous.reviewer||'';form.elements.observed.value=String(previous.observed);form.elements.reason.value=previous.reason;form.elements.contentOk.checked=previous.contentOk;form.querySelector('output').textContent='Đã có nhận xét của '+previous.reviewer;}}
  for(const form of $('matrix-preview').querySelectorAll('[data-matrix-review]'))form.onsubmit=guard(async()=>{
   const data=new FormData(form),ordinal=Number(form.dataset.matrixReview);
   reviews=await api(base()+'/review',{ordinal,observed:Number(data.get('observed')),reason:data.get('reason'),contentOk:data.has('contentOk'),reviewer:String(data.get('reviewer')||$('matrix-reviewer').value).trim()});
   const matched=reviews[String(ordinal)].observed===job.proposal.questions[ordinal].level&&reviews[String(ordinal)].contentOk;
   form.querySelector('output').textContent=matched?' Đã ghi nhận.':' Mức chưa phù hợp. Điều chỉnh yêu cầu hoặc sinh lại trước khi lưu.';
   updateConfirm();
  });
  if(inline){$('matrix-view-proposal').hidden=false;options.preview($('matrix-preview'));}
  updateConfirm();
 }
 async function poll(){
  if(polling)return;polling=true;
  const retry=$('matrix-poll-retry');
  retry.hidden=true;
  try{while(!closed){
   const savedReviews=job.reviews;job=await api(base()+'/status');if(savedReviews)job.reviews=savedReviews;
   const trace=await api(base()+'/trace');
   const latestCheck=trace.findLast(t=>t.event==='generation_result');if(latestCheck)showChecks(latestCheck);
   $('matrix-trace').innerHTML=trace.map(t=>t.event?'<p>'+esc({run_start:'Trợ lý bắt đầu',provider_model_switch:'Hết quota: chuyển từ '+(t.fromModel||'')+' sang '+(t.toModel||''),provider_key_switch:'Đổi sang key dự phòng (ẩn khóa)',provider_retry:'Thử lại sau lỗi dịch vụ tạm thời',model_start:'Đang gọi '+(t.model||''),model_end:(t.ok?'Đã nhận kết quả từ ':'Lượt gọi chưa đạt: ')+(t.model||''),model_call_start:({agent:'AI đang soạn hoặc sửa bộ câu',blind_content_check:'AI đang giải lại và rà mức',explanation_check:'AI đang đối chiếu lời giải'}[t.purpose]||'Đang gọi AI'),model_call_end:'AI đã trả kết quả lượt xử lý',tool_call:'Trợ lý gọi công cụ '+(t.tool||''),structure_check:'Kiểm cấu trúc',blind_content_check:'Giải lại, rà mức và căn cứ',candidate_check:'Tổng hợp kiểm nội dung',generation_result:'Kết quả lần nộp '+t.generationAttempt,run_end:'Kết thúc: '+t.status}[t.event]||t.event)+(typeof t.ok==='boolean'?' · '+(t.ok?'Qua bộ kiểm':'Còn vấn đề'):'')+(t.errors?.length?' · '+esc(t.errors.map(errorText).join(' · ')):'')+(t.seconds!==undefined?' · '+Number(t.seconds).toFixed(2)+' giây':'')+'</p>':'<p>Câu '+t.question+' · lượt '+t.attempt+' · '+esc(t.status)+(t.message?' · '+esc(t.message):'')+'</p>').join('');
   const last=trace.at(-1);if(job.status==='running'&&last)setStatus('Đang '+({model_call_start:({agent:'soạn hoặc sửa bộ câu',blind_content_check:'giải độc lập và rà mức',explanation_check:'đối chiếu lời giải'}[last.purpose]||'gọi model'),model_call_end:'đã nhận kết quả lượt AI',generation_result:'đã kiểm lần nộp '+last.generationAttempt}[last.event]||'kiểm tra và chờ kết quả AI')+'…');
   if(job.status!=='running')break;
   await new Promise(resolve=>setTimeout(resolve,1000));
  }
  if(closed)return;
  $('matrix-stop').disabled=true;
  if(status.matrixAgent)showChecks(await api(base()+'/report'));
  if(status.matrixAgent){const audit=await api(base()+'/audit');$('matrix-audit').textContent=audit.traceVerified?'Đã đối chiếu lời gọi công cụ với log thô'+(audit.successfulRepairObserved?' · có nhận lỗi, đổi nội dung và kiểm lại.':'.'):'Chưa xác minh đầy đủ log thô của lượt này.';}
  lockSources(false);$('matrix-start').disabled=false;$('matrix-download').disabled=false;
  $('matrix-review-pack').disabled=job.status!=='complete'||!status.matrixAgent;
  if(job.status==='complete'){setStatus('Đã soạn '+job.proposal.questions.length+' câu và tự kiểm. Đề xuất đang ở trên trang; chưa thay đề đã lưu.');showProposal();}
  else {setStatus(job.status==='cancelled'?'Đã dừng. Đề được giữ nguyên.':'Chưa hoàn tất. '+(errorNames[job.errorCode]||job.errorCode)+'. Đề được giữ nguyên.');syncPhase();}
  }catch{
   if(!closed){
    $('matrix-start').disabled=true;
    retry.hidden=false;
    setStatus('Chưa tải được trạng thái tác vụ. Bấm “Tải lại trạng thái” để tiếp tục theo dõi lượt này.');
    updateConfirm();
   }
  }finally{polling=false;}
 }
 $('matrix-poll-retry').onclick=()=>poll();
 $('matrix-start').onclick=guard(async()=>{
  if(job?.saved)throw Error('Bộ câu đã lưu. Tải lại trang để đồng bộ trước khi soạn tiếp.');
  if(job?.status==='running')return;
  if(count<1||count>30)throw Error('Nhận từ1đến30câu theo ma trận. Hãy chỉnh ma trận.');
  const useSource=$('matrix-source-mode').value==='provided';
  if(useSource&&(!$('matrix-source-name').value.trim()||$('matrix-source-text').value.trim().length<20))throw Error('Điền tên nguồn và ít nhất 20 ký tự nội dung nguồn.');
  if(!$('matrix-consent').checked)throw Error('Cần cho phép gửi nguồn tới '+destination+' trước khi sinh.');
  preparing=true;delete $('matrix-status').dataset.error;setStatus('Đang chuẩn bị yêu cầu…');syncPhase();
  $('matrix-start').disabled=true;$('matrix-confirm-save').disabled=true;$('matrix-progress').open=true;
  $('matrix-final-check').checked=false;reviews={};
  if(!sameExam())throw Error('Đề đã đổi. Đóng tác vụ này rồi mở lại để dùng phiên bản mới.');
  await c.persist();
  options.clearPreview?.();
  job=null;
  source=useSource?$('matrix-source-text').value.trim():'';
  approval=await api('/api/exams/'+exam.id+'/matrix/approve',{baseRevision,sourceText:source,sourceName:useSource?$('matrix-source-name').value.trim():'Kiến thức chung · không có nguồn đối chiếu',sourceMode:useSource?'provided':'general'});
  setStatus('Trợ lý đang tự sinh và kiểm. Chưa thay câu nào trong đề.');
  $('matrix-preview').innerHTML='';$('matrix-checks').innerHTML='';$('matrix-metrics').textContent='';$('matrix-audit').textContent='';$('matrix-review-pack').disabled=true;
  job=await api('/api/exams/'+exam.id+'/proposals/generate',{requestId:crypto.randomUUID(),baseRevision,consent:true,requireEvidence:useSource,plan:approval.plan,sources:approval.sources},{'X-PoC-Config':status.config?.fingerprint||'legacy'});
  preparing=false;lockSources(true);$('matrix-inputs').open=false;$('matrix-stop').disabled=false;syncPhase();await poll();
 });
 $('matrix-stop').onclick=guard(async()=>{await cancel();await poll();});
 $('matrix-confirm-save').onclick=decide(async()=>{
  if(!sameExam())throw Error('Đề đã thay đổi. Chưa chấp nhận đề xuất cũ.');
  const nodes=[document.querySelector('#app'),dialog],wasInert=nodes.map(n=>n.inert),focus=document.activeElement;
  const blockShortcut=event=>{if(event.ctrlKey||event.metaKey){event.preventDefault();event.stopImmediatePropagation();}};
  nodes.forEach(n=>n.inert=true);document.addEventListener('keydown',blockShortcut,true);
  setStatus('Đang lưu bộ câu. Chờ đồng bộ xong trước khi sửa tiếp.');
  try{
   await c.persist();
   await api(base()+'/confirm',{baseRevision,teacherConfirmation:inline||$('matrix-final-check').checked});
   job.saved=true;
   let fresh;
   try{fresh=await db.get('state',{requireRemote:true});}
   catch{
    const recovery=document.createElement('dialog');
    recovery.setAttribute('aria-labelledby','matrix-sync-title');
    recovery.innerHTML='<div class="modal-head"><h2 id="matrix-sync-title">Bộ câu đã lưu</h2></div><div class="modal-body"><p role="status">Chưa tải lại được dữ liệu từ máy chủ. Kết nối lại rồi thử đồng bộ để tiếp tục sửa; không cần chấp nhận lần nữa.</p><button type="button" class="primary">Thử đồng bộ</button></div>';
    recovery.addEventListener('cancel',event=>event.preventDefault());document.body.append(recovery);recovery.showModal();
    fresh=await new Promise(resolve=>{recovery.querySelector('button').onclick=async()=>{
     const button=recovery.querySelector('button');button.disabled=true;
     try{resolve(await db.get('state',{requireRemote:true}));}
     catch{recovery.querySelector('[role=status]').textContent='Chưa kết nối được. Bộ câu đã lưu vẫn giữ nguyên trên máy chủ. Thử đồng bộ khi mạng ổn định.';}
     finally{button.disabled=false;}
    };});
    recovery.close();recovery.remove();
   }
   Object.assign(c.getState(),fresh);
   if(inline)await options.finish('saved');else{dialog.close();c.render();}c.toast('Đã lưu bộ câu theo ma trận. Có thể hoàn tác; câu mới vẫn chờ giáo viên duyệt.');
  }finally{
   nodes.forEach((n,i)=>n.inert=wasInert[i]);document.removeEventListener('keydown',blockShortcut,true);
   if(focus?.isConnected)focus.focus();else document.querySelector('.header-title')?.focus();
  }
 });
 $('matrix-download').onclick=guard(async()=>{
  const trace=await api(base()+'/trace');
  const report=await api(base()+'/report');
  const audit=status.matrixAgent?await api(base()+'/audit'):null;
  const payload={at:new Date().toISOString(),provider:status.aiProvider||'ollama',model:status.model,modelSelection:'preferred',actualModels:[...new Set((report.summary?.calls||[]).map(call=>call.model).filter(Boolean))],reviewer:status.reviewer,budget,source,approval,job,trace,reviews,report,audit,note:'Log tác vụ; xem mode trong run_start để phân biệt fixture và AI thật. Nhận xét người rà cần khai đúng người thực hiện.'};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='Sinh_ma_tran_'+job.jobId+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
 $('matrix-review-pack').onclick=guard(async()=>{
  const response=await fetch(base()+'/review-pack');
  if(!response.ok){const error=await response.json();throw Error(error.error||'Chưa tạo được phiếu rà.');}
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download='Phieu_ra_'+job.jobId+'.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
 syncPhase();
 const latest=await api('/api/exams/'+exam.id+'/proposals/latest');
 if(latest&&latest.baseRevision===baseRevision&&!latest.saved&&!latest.discarded){job=latest;if(latest.input){source=latest.input.sourceText||'';$('matrix-source-text').value=source;$('matrix-source-name').value=latest.input.sourceName||'';approval=latest.input.approval;$('matrix-source-mode').value=approval?.sources?.length?'provided':'general';}lockSources(job.status==='running');$('matrix-start').disabled=job.status==='running';$('matrix-stop').disabled=job.status!=='running';syncPhase();await poll();}
 return {refresh:updateConfirm};
}
