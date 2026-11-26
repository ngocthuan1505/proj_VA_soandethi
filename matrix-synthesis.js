import {richTextHTML,diffContentHTML} from './math-content.js';
import {esc, LEVELS, QUESTION_TYPES} from './core.js';
import * as db from './storage.js';
import {selectedDocumentPages,sourcePageLabel} from './assistant-sources.js';
import {citationContextHTML} from './citation-context.js';

let cachedAutoPilot=null;

export const AUTO_CREATE_STEPS=[
 {phase:'plan',label:'Lập kế hoạch & ma trận'},
 {phase:'swarm',label:'Sinh song song nhiều lô'},
 {phase:'goal',label:'Kiểm định & tự sửa'},
 {phase:'apply',label:'Áp lên trang A4'},
];

export function setAutoPilotEnabled(value){
 cachedAutoPilot=Boolean(value);
 try{globalThis.localStorage?.setItem('mach:autoPilot',String(cachedAutoPilot));}catch{}
 return cachedAutoPilot;
}

export function isAutoPilotEnabled(configOrFlag){
 if(typeof cachedAutoPilot==='boolean')return cachedAutoPilot;
 if(typeof globalThis.__machAutoPilot==='boolean')return globalThis.__machAutoPilot;
 try{
  const stored=globalThis.localStorage?.getItem('mach:autoPilot');
  if(stored==='false')return false;
  if(stored==='true')return true;
 }catch{}
 if(typeof configOrFlag==='boolean')return configOrFlag;
 if(configOrFlag&&typeof configOrFlag==='object'){
  if(typeof configOrFlag.fixedRouter?.autoPilot==='boolean')return configOrFlag.fixedRouter.autoPilot;
  if(typeof configOrFlag.autoPilot==='boolean')return configOrFlag.autoPilot;
 }
 return true;
}

export function parseAutoCreateSse(chunkBuffer){
 const records=[];
 let buffer=String(chunkBuffer||'').replace(/\r\n/g,'\n');
 let end;
 while((end=buffer.indexOf('\n\n'))>=0){
  const raw=buffer.slice(0,end);
  buffer=buffer.slice(end+2);
  const type=raw.match(/^event:\s*(.+)$/m)?.[1]?.trim()||'message';
  const dataLines=raw.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trim());
  if(!dataLines.length)continue;
  try{records.push({type,data:JSON.parse(dataLines.join('\n'))});}catch{}
 }
 return {records,rest:buffer};
}

 export function describeActiveEngine(status){
  const cfg=status?.config||{};
  const fr=cfg.fixedRouter||{};
  const hasDs=Boolean(cfg.deepseek?.hasKey||cfg.deepseek?.configured);
  const hasGem=Boolean((cfg.gemini?.hasKey&&cfg.gemini?.freeTierConfirmed)||cfg.gemini?.configured);
  const fallbackProvider=status?.aiProvider||'ollama';
  const fallbackModel=status?.model||'';
  if(!status?.fixture&&fr.enabled!==false&&(fr.agyAvailable||hasDs||hasGem)){
   if(fr.agyAvailable){
    const genModel=fr.agyModel||'gemini-pro-orchestrator-neon';
    const revModel=hasDs?(cfg.deepseek?.reasonerModel||cfg.deepseek?.model||genModel):(fr.agyFastModel||genModel);
    const dest=hasDs?'AGY CLI và DeepSeek API':(hasGem?'AGY CLI và Gemini API':'AGY CLI');
    return {destination:dest,genModel,revModel};
   }
   if(hasDs){
    return {destination:'DeepSeek API',genModel:cfg.deepseek?.model||'deepseek-chat',revModel:cfg.deepseek?.reasonerModel||cfg.deepseek?.model||'deepseek-reasoner'};
   }
   if(hasGem){
    return {destination:'Gemini API của Google',genModel:cfg.gemini?.model||fallbackModel,revModel:cfg.gemini?.checkModel||cfg.gemini?.model||fallbackModel};
   }
  }
  const mapLabel=p=>{
   const k=String(p||'').toLowerCase();
   if(k.startsWith('agy'))return 'AGY CLI';
   if(k.startsWith('deepseek'))return 'DeepSeek API';
   if(k==='gemini'||k.startsWith('gemini'))return 'Gemini API của Google';
   return 'Ollama trên máy';
  };
  const destinations=[fallbackProvider,status?.reviewer?.provider||fallbackProvider];
  return {destination:[...new Set(destinations)].map(mapLabel).join(' và '),genModel:fallbackModel,revModel:status?.reviewer?.model||fallbackModel};
 }

 export function renderAutoCreateCardHTML(state){
  const phases=state?.phases||{};
  const stepsHTML=AUTO_CREATE_STEPS.map((step,idx)=>{
   const st=phases[step.phase]||'pending';
   const cls=st==='done'?'is-done':st==='running'?'is-active':st==='error'?'is-error':'';
   return `<li class="auto-create-step ${cls}" data-phase="${step.phase}"><span class="auto-create-step-num">${st==='done'?'✓':idx+1}</span><span>${esc(step.label)}</span></li>`;
  }).join('');
  const batchMeta=state?.totalBatches
   ?`<p class="auto-create-batch-meta">Tiến độ lô: ${state.completedBatches||0}/${state.totalBatches} lô · ${state.completedCount||0}/${state.totalSlots||0} câu${state.lastModel?` · Mô hình: <code>${esc(state.lastModel)}</code>`:''}</p>`
   :'';
  const doneCount=state?.complete?.questions?.length??state?.complete?.totalQuestions??state?.totalSlots??0;
  const donePts=state?.complete?.totalPoints??10;
  const summaryHTML=state?.complete
   ?`<p class="auto-create-summary">Đã áp ${doneCount} câu (${donePts} điểm) lên trang A4.</p>`
   :'';
  const consentHTML=state?.needsConsent
   ?`<div class="auto-create-consent"><p role="alert">${esc(state.error||'Cần xác nhận cho phép gửi nội dung tới AI trước khi tự động soạn đề.')}</p><label class="consent"><input type="checkbox" data-auto-save-consent> Ghi nhớ cho toàn không gian làm việc</label><div class="auto-create-actions"><button type="button" class="primary" data-action="auto-create-consent-retry">✓ Cho phép &amp; Tự động soạn ngay</button></div></div>`
   :'';
  const errHTML=!state?.needsConsent&&state?.error
   ?`<p class="auto-create-error" role="alert">${esc(state.error)}</p>`
   :'';
  const closeBtn=!state?.running?'<button type="button" class="auto-create-dismiss" data-action="auto-create-dismiss" title="Đóng thẻ tiến độ" aria-label="Đóng thẻ tiến độ">✕</button>':'';
  const controlsHTML=`<div class="auto-create-actions">${state?.running?'<button type="button" data-action="auto-create-cancel">Dừng</button>':''}<button type="button" class="ghost" data-action="open-manual-matrix">Mở bảng ma trận chi tiết</button></div>`;
  return `<div class="auto-create-card" data-status="${esc(state?.status||'running')}" role="region" aria-label="Tự động soạn đề"><div class="auto-create-head"><b>Tự động soạn đề</b><div class="auto-create-head-right"><span class="auto-create-status">${esc(state?.statusText||'Đang khởi chạy…')}</span>${closeBtn}</div></div><ol class="auto-create-steps" aria-live="polite">${stepsHTML}</ol>${batchMeta}${summaryHTML}${consentHTML}${errHTML}${controlsHTML}</div>`;
 }

export async function streamAutoCreateExam(examId,payload,{fetchImpl=fetch,signal,headers={},onEvent}={}){
 const response=await fetchImpl(`/api/exams/${encodeURIComponent(examId)}/agent/auto-create`,{
  method:'POST',
  signal,
  headers:{...db.workspaceHeaders(),...headers,'Content-Type':'application/json'},
  body:JSON.stringify(payload),
 });
 const ct=String(response.headers?.get?.('content-type')||'');
 if(!response.ok){
  let errBody={};
  try{errBody=await response.json();}catch{}
  const err=new Error(errBody.error||errBody.detail?.message||'Chưa bắt đầu được luồng tự động soạn đề.');
  err.code=errBody.code||errBody.detail?.code||(response.status===409?'stale_snapshot':'auto_create_error');
  err.status=response.status;
  throw err;
 }
 if(!ct.includes('text/event-stream')||!response.body?.getReader){
  const jsonRes=await response.json();
  onEvent?.('complete',jsonRes);
  return jsonRes;
 }
 const reader=response.body.getReader(),decoder=new TextDecoder();
 let buffer='',completeData=null;
 const handleRecords=records=>{
  for(const rec of records){
   onEvent?.(rec.type,rec.data);
   if(rec.type==='error'){
    const err=new Error(rec.data?.error||'Lỗi trong quá trình tự động soạn đề.');
    err.code=rec.data?.code||'auto_create_error';
    err.status=rec.data?.status||500;
    throw err;
   }
   if(rec.type==='complete')completeData=rec.data;
  }
 };
 while(true){
  const {value,done}=await reader.read();
  if(done)break;
  buffer+=decoder.decode(value,{stream:true});
  const parsed=parseAutoCreateSse(buffer);
  buffer=parsed.rest;
  handleRecords(parsed.records);
 }
 if(buffer.trim()){
  const parsed=parseAutoCreateSse(buffer+'\n\n');
  handleRecords(parsed.records);
 }
 if(!completeData)throw new Error('Kết nối bị ngắt trước khi hoàn tất bộ đề.');
 return completeData;
}

export async function runAutoCreateExam(ctx,promptText,opts={}){
 const prompt=String(promptText||'').trim();
 if(!prompt)throw new Error('Vui lòng nhập yêu cầu đề cần soạn.');
 const exam=ctx.exam();
 if(!exam?.id)throw new Error('Chưa có đề đang mở để tự động soạn.');
 const examId=opts.examId||exam.id;
 const fetchImpl=opts.fetchImpl||globalThis.fetch;
 const doc=typeof document!=='undefined'?document:null;
 if(doc){
  doc.querySelector('.workspace')?.classList.remove('chat-hidden','focus-mode');
  doc.querySelector('.assistant')?.classList.add('open');
 }
 const host=opts.host||doc?.querySelector('.assistant-body')||null;
 let container=null;
 if(host&&doc){
  host.querySelectorAll('.auto-create-session').forEach(node=>{
   const st=node.querySelector('.auto-create-card')?.dataset.status;
   if(st&&st!=='running')node.remove();
  });
  container=doc.createElement('section');
  container.className='auto-create-session';
  host.append(container);
 }
 const controller=new AbortController();
 const onAbort=()=>controller.abort();
 opts.signal?.addEventListener?.('abort',onAbort,{once:true});

 const state={
  status:'running',
  running:true,
  statusText:'Đang lập kế hoạch & ma trận…',
  phases:{plan:'running',swarm:'pending',goal:'pending',apply:'pending'},
  totalBatches:0,
  completedBatches:0,
  completedCount:0,
  totalSlots:0,
  lastModel:'',
  complete:null,
  needsConsent:false,
  error:'',
 };

 const paint=()=>{
  if(!container)return;
  const liveHost=doc?.querySelector('.assistant-body');
  if(liveHost&&!liveHost.contains(container))liveHost.append(container);
  container.innerHTML=renderAutoCreateCardHTML(state);
  const cancelBtn=container.querySelector('[data-action="auto-create-cancel"]');
  if(cancelBtn)cancelBtn.onclick=()=>{controller.abort();};
  const manualBtn=container.querySelector('[data-action="open-manual-matrix"]');
  if(manualBtn)manualBtn.onclick=()=>{
   if(state.running)controller.abort();
   opts.onOpenManualMatrix?.(ctx,prompt);
  };
  const consentBtn=container.querySelector('[data-action="auto-create-consent-retry"]');
  if(consentBtn)consentBtn.onclick=()=>{
   const saveWs=Boolean(container.querySelector('[data-auto-save-consent]')?.checked);
   exam.aiConsent=true;
   container.remove();
   void runAutoCreateExam(ctx,prompt,{...opts,consentGiven:true,saveWorkspaceConsent:saveWs});
  };
  const dismissBtn=container.querySelector('[data-action="auto-create-dismiss"]');
  if(dismissBtn)dismissBtn.onclick=()=>{container.remove();};
  const activeHost=liveHost||host;
  if(activeHost&&typeof activeHost.scrollTop==='number')activeHost.scrollTop=activeHost.scrollHeight;
 };
 paint();

 const currentDocs=Array.isArray(exam.assistantSources)
  ?(exam.docs||[]).filter(d=>exam.assistantSources.includes(d.id))
  :(exam.docs||[]);
 const attachedSources=opts.sources||currentDocs.flatMap(d=>selectedDocumentPages(exam,d)
  .filter(p=>p?.text?.trim())
  .map(p=>({
   docId:d.id,
   name:d.name,
   page:p.number,
   location:d.name+' · '+sourcePageLabel(d,p.number),
   text:p.text,
  })));

 const requestPayload={
  prompt,
  subject:opts.subject??exam.subject??null,
  grade:opts.grade??exam.grade??null,
  durationMinutes:opts.durationMinutes??exam.minutes??null,
  expectedRevision:exam.revision??null,
  sourceIds:opts.sourceIds??(exam.assistantSources||[]),
  sources:attachedSources,
  consentGiven:opts.consentGiven!==undefined?Boolean(opts.consentGiven):Boolean(exam.aiConsent),
  saveWorkspaceConsent:Boolean(opts.saveWorkspaceConsent),
  campaignId:opts.campaignId??null,
  persistToStore:opts.persistToStore===true,
 };

 try{
  const complete=await streamAutoCreateExam(examId,requestPayload,{
   fetchImpl,
   signal:controller.signal,
   onEvent:(type,data)=>{
    if(type==='step'&&data?.phase){
     state.phases[data.phase]=data.status||'running';
     if(data.totalBatches)state.totalBatches=data.totalBatches;
     if(data.totalQuestions||data.totalSlots)state.totalSlots=data.totalQuestions||data.totalSlots;
     if(data.message)state.statusText=data.message;
     else if(data.phase==='plan'&&data.status==='done')state.statusText=`Đã lập ma trận ${data.totalQuestions||''} câu · ${data.subject||''} ${data.grade||''}`.trim();
     else if(data.phase==='swarm'&&data.status==='done')state.statusText=`Đã sinh xong ${data.completedCount||0} câu từ ${data.totalBatches||0} lô song song`;
     else if(data.phase==='goal'&&data.status==='done')state.statusText=`Đã kiểm định đạt 10 điểm (${data.repairRounds||0} vòng tự sửa)`;
     else if(data.phase==='apply'&&data.status==='done')state.statusText='Đang nạp lên trang A4…';
     paint();
    }else if(type==='batch'&&data){
     state.completedBatches+=1;
     if(data.totalBatches)state.totalBatches=data.totalBatches;
     if(data.completedCount!=null)state.completedCount=data.completedCount;
     if(data.totalSlots)state.totalSlots=data.totalSlots;
     if(data.model)state.lastModel=data.model;
     state.statusText=`Đã xong lô ${state.completedBatches}/${state.totalBatches||state.completedBatches} (${state.completedCount}/${state.totalSlots||state.completedCount} câu)`;
     paint();
    }else if(type==='verify'&&data){
     state.statusText=data.repairing
      ?`Đang tự sửa vòng ${data.round||1} (${data.issueCount||0} mục cần chuẩn hóa)…`
      :`Kiểm định đạt: ${data.totalQuestions||0} câu · ${data.totalPoints??10} điểm`;
     paint();
    }
   },
  });

  if(ctx.exam()?.id!==examId)throw new Error('Đã chuyển sang đề khác trong lúc AI đang soạn.');
  const applyChange=arg=>{
   const target=arg||ctx.exam();
   target.questions=Array.isArray(complete.questions)?complete.questions:[];
   if(Array.isArray(complete.matrix)&&complete.matrix.length){
    target.matrix=complete.matrix;
    target.matrixConfirmed=true;
   }
   if(complete.title)target.title=complete.title;
   if(complete.subject)target.subject=complete.subject;
   if(complete.grade!=null)target.grade=String(complete.grade);
   if(complete.minutes)target.minutes=Number(complete.minutes);
   target.sample=false;
   target.fullExam=true;
  };
  ctx.change('AI tự động soạn đề',applyChange);
  const updatedExam=ctx.exam();
  const undoRevision=updatedExam.revision;
  const modelsText=Array.isArray(complete.stats?.modelsUsed)&&complete.stats.modelsUsed.length
   ?` · Mô hình: ${complete.stats.modelsUsed.join(', ')}`
   :'';
  const chatSummary=complete.message||`Đã tự động soạn xong ${complete.questions?.length||0} câu hỏi bản nháp (tổng ${complete.totalPoints??10} điểm)${modelsText}. Có thể bấm Hoàn tác để về bản trước.`;
  updatedExam.chat=Array.isArray(updatedExam.chat)?updatedExam.chat:[];
  updatedExam.chat.push({
   role:'assistant',
   text:chatSummary,
   at:Date.now(),
   undoRevision,
   modelUsed:complete.stats?.modelsUsed?.[0]||complete.stats?.orchestratorModel||'',
   autoCreateStats:complete.stats||null,
  });
  await ctx.persist?.();
  ctx.render?.();
  if(requestPayload.consentGiven&&requestPayload.saveWorkspaceConsent){
   try{globalThis.window?.dispatchEvent?.(new CustomEvent('mach:workspace-consent-saved'));}catch{}
  }

  if(opts.campaignId){
   try{
    await fetchImpl(`/api/campaigns/${encodeURIComponent(opts.campaignId)}/link-exam`,{
     method:'POST',
     headers:{...db.workspaceHeaders(),'Content-Type':'application/json'},
     body:JSON.stringify({examId:updatedExam.id}),
    });
   }catch{}
   try{
    globalThis.window?.dispatchEvent?.(new CustomEvent('mach:campaign-updated',{
     detail:{campaignId:opts.campaignId,examId:updatedExam.id},
    }));
   }catch{}
  }

  state.running=false;
  state.status='complete';
  state.phases={plan:'done',swarm:'done',goal:'done',apply:'done'};
  state.complete=complete;
  state.statusText='Hoàn tất · Đã áp lên trang A4';
  paint();
  ctx.toast?.('Đã tự động soạn đề xong. Mọi câu ở trạng thái bản nháp · bấm Hoàn tác nếu muốn quay lại.');
  return {ok:true,undoRevision,complete};
 }catch(error){
  state.running=false;
  if(error?.code==='consent_required'){
   state.status='consent_required';
   state.needsConsent=true;
   state.statusText='Cần xác nhận cho phép AI';
   state.error=error.message;
   paint();
   return {ok:false,code:'consent_required',error:error.message};
  }
  const aborted=error?.name==='AbortError';
  state.status=aborted?'cancelled':'error';
  state.statusText=aborted?'Đã dừng tự động soạn đề':'Chưa hoàn tất tự động soạn đề';
  state.error=aborted?'Đã dừng theo yêu cầu. Nội dung đề cũ được giữ nguyên.':(error?.message||'Đã xảy ra lỗi khi tự động soạn đề.');
  const activePhase=AUTO_CREATE_STEPS.find(s=>state.phases[s.phase]==='running')?.phase;
  if(activePhase)state.phases[activePhase]='error';
  paint();
  if(opts.rethrow)throw error;
  return {ok:false,code:error?.code||(aborted?'cancelled':'auto_create_error'),error:state.error};
 }finally{
  opts.signal?.removeEventListener?.('abort',onAbort);
 }
}

async function api(url, body, headers={}){
 const response=await fetch(url,{
  headers:{...db.workspaceHeaders(),...headers,...(body===undefined?{}:{'Content-Type':'application/json'})},
  ...(body===undefined?{}:{method:'POST',body:JSON.stringify(body)}),
 });
 const result=await response.json();
 if(!response.ok)throw Error(result.error||result.detail?.message||JSON.stringify(result.detail||result));
 return result;
}

export async function openMatrixSynthesis(c, options={}){
 const inline=!!options.host;
 const examId=options.examId||c.exam().id;
 const status=await api('/api/status');
 const engine=describeActiveEngine(status);
 const destination=engine.destination;
 const checkNames={validate_schema:'Cấu trúc',check_matrix_and_scoring:'Ma trận và điểm',retrieve_evidence:'Đoạn nguồn',check_evidence:'Căn cứ nguồn',solve_blind:'Giải lại',verify_options:'Bốn phương án',review_level:'Mức nhận thức',check_duplicates:'Trùng ý',check_explanation:'Lời giải',aggregate_checks:'Tổng hợp'};
 const budget=status.runBudget||{maxModelCalls:24,timeoutSeconds:900};
 if(!status.matrixPython){c.toast('Mở bản Python cục bộ để dùng luồng sinh theo ma trận.');return;}
 await c.persist();
 if(c.exam().id!==examId)throw Error('Đã chuyển đề trong lúc mở tác vụ. Mở lại ở đúng đề cần soạn.');
 const exam=c.exam(),baseRevision=exam.revision;
 if(!exam.matrixConfirmed){c.toast('Lưu và xác nhận ma trận trước khi sinh.');return;}
 const rows=exam.matrix||[],count=rows.flatMap(r=>r.targets).reduce((n,x)=>n+x,0);
 const currentDocs=exam.docs.filter(d=>exam.assistantSources?.includes(d.id));
 const pendingPages=currentDocs.flatMap(d=>selectedDocumentPages(exam,d)
  .filter(p=>p.needsOCR||(p.needsReview??(d.needsReview||p.uncertain===true||p.uncertain?.length)))
  .map(p=>d.name+' · trang '+p.number));
 const attachedPages=currentDocs.flatMap(doc=>selectedDocumentPages(exam,doc)
  .filter(page=>page.text?.trim()).map(page=>({doc,page})));
 const sourceRefs=attachedPages.map(({doc,page})=>({
  sourceId:doc.id,sourceVersion:doc.version||1,locator:{kind:'page',index:page.number},
 }));
 const attachedPreview=attachedPages.map(({doc,page})=>doc.name+' · '+sourcePageLabel(doc,page.number)+'\n'+page.text).join('\n\n');
 let source=attachedPreview;
 let job=null,lastCandidate=null,approval=null,closed=false,reviews={},polling=false,deciding=false;
 const errorNames={incomplete_response:'AI bị ngắt trước khi trả đủ bộ câu; bản đề giữ nguyên. Có thể giảm số câu hoặc thử lại; tải log để xem chi tiết',duplicate_question:'Câu hỏi bị trùng',invalid_options:'Phương án chưa hợp lệ',answer_disagreement:'Đáp án chưa khớp lượt giải lại',level_disagreement:'Mức thực tế chưa khớp ma trận',explanation_disagreement:'Lời giải chưa khớp',uncertain_answer:'Lượt giải chưa đủ chắc chắn',unsupported_answer:'Chưa đủ căn cứ',topic_disagreement:'Chưa đúng chủ đề',invalid_review:'Lượt rà trả dữ liệu chưa hợp lệ',attempt_limit:'Đã hết giới hạn của lượt thử cũ',call_budget:'Đã hết ngân sách gọi AI',timeout:'Hết thời gian xử lý — thử giảm số câu, đổi chế độ thời gian dài hơn hoặc bấm Thử lại',provider_http_error:'Dịch vụ AI đang trả lỗi',provider_quota:'Đã hết hạn mức dịch vụ AI',provider_auth:'Khóa Gemini chưa hợp lệ; mở Kết nối để thay khóa',provider_timeout:'Dịch vụ AI quá thời gian chờ; bản đề giữ nguyên',check_not_completed:'Một số phép kiểm chưa hoàn tất',option_verdicts_failed:'Có nhiều đáp án đúng hoặc phương án chưa rõ',semantic_duplicate:'Câu hỏi trùng ý',uncertain_duplicate:'Chưa kết luận được trùng ý',interrupted:'App đã khởi động lại khi tác vụ chưa hoàn tất',stale_snapshot:'Đề hoặc nguồn đã thay đổi',provider_unavailable:'Chưa kết nối được AI đã chọn'};
 const errorText=e=>(e.ordinal!==undefined?'Câu '+(e.ordinal+1)+': ':'')+(errorNames[e.code]||e.code)+(e.reason?' — '+e.reason:'')+(e.details?.length?' · '+e.details.map(d=>d.message).join('; '):'');
 const markup=`${inline?'<p>Trợ lý soạn, tự kiểm và sửa bộ câu. Xem lại trên trang đề rồi chọn chấp nhận hoặc bỏ.</p><details><summary>Kết nối và giới hạn</summary>':''}<p>Sinh bằng <b>${esc(engine.genModel)}</b> · kiểm bằng <b>${esc(engine.revModel)}</b>. Nguồn được gửi tới ${esc(destination)}. ${status.matrixAgent?`Trợ lý tự soạn, gọi công cụ kiểm và sửa theo lỗi trong ngân sách ${budget.maxModelCalls} lần gọi AI, tối đa ${budget.timeoutSeconds} giây. Thầy cô không cần xử lý từng vòng.`:'Bản thử cũ sinh từng ô, mỗi ô có giới hạn lượt riêng.'} Chỉ trả bản cuối đã qua bộ kiểm; thầy cô xem lại trước khi xác nhận lưu.</p>${inline?'</details>':''}
 <details class="matrix-chat-summary"><summary>Ma trận đã xác nhận · ${count} câu</summary><table class="matrix-full"><thead><tr><th>Chủ đề / loại câu</th>${LEVELS.map(x=>'<th>'+x+'</th>').join('')}</tr></thead><tbody>${rows.map(r=>'<tr><td>'+esc(r.topic)+' · '+esc(QUESTION_TYPES[r.type||'mcq'])+'</td>'+r.targets.map(n=>'<td>'+n+'</td>').join('')+'</tr>').join('')}</tbody></table></details>
 ${inline?'<button type="button" id="matrix-edit-plan">Chỉnh / tải file ma trận</button>':''}<p>${count} / tối đa 30 câu, bốn dạng · tổng 10 điểm. Chia điểm theo bước 0,25; phần dư phân theo thứ tự ô.</p>
 <label>Cách soạn<select id="matrix-source-mode">${sourceRefs.length?'<option value="attached" selected>Theo trang đã chọn trong kho</option>':''}<option value="provided">Theo ngữ liệu dán</option><option value="general" ${source?'':'selected'}>Theo kiến thức môn/lớp · không có tài liệu đối chiếu</option></select></label><p class="hint" id="matrix-general-note">Soạn không nguồn vẫn giải lại và rà lời giải, nhưng chưa xác minh với SGK/tài liệu. Giáo viên cần kiểm tra kiến thức và phạm vi.</p><details id="matrix-inputs" ${source?'open':''}><summary>Thêm tài liệu nguồn (tùy chọn)</summary><label>Tên nguồn<input id="matrix-source-name" maxlength="200" value="${esc(currentDocs.map(d=>d.name).join('; ').slice(0,200))}" placeholder="Ghi đúng tên hoặc ghi ngữ liệu tự viết"></label>
 <label>Nội dung nguồn cho lượt sinh<textarea id="matrix-source-text" rows="4" maxlength="12000" placeholder="Dán ngữ liệu cần ra câu hỏi. Không tự coi đây là trích SGK nếu chưa có nguồn.">${esc(source)}</textarea></label>
 ${pendingPages.length?`<p id="matrix-source-warning" class="hint">Trang chưa đọc hoặc chưa đối chiếu: ${esc(pendingPages.slice(0,6).join('; '))}${pendingPages.length>6?' và '+(pendingPages.length-6)+' trang nữa':''}. Rà lại phần văn bản trước khi sinh.</p>`:''}
 <label><input type="checkbox" id="matrix-consent" style="width:auto"> Cho phép gửi yêu cầu và tài liệu đã chọn tới ${esc(destination)} để sinh và tự kiểm đề.</label></details>
 <div class="toolbar-row"><button type="button" id="matrix-start" class="primary">${inline?"Bắt đầu soạn":"Duyệt yêu cầu và sinh"}</button><button type="button" id="matrix-stop" disabled>Dừng tác vụ</button><button type="button" id="matrix-download" disabled>Tải log</button><button type="button" id="matrix-review-pack" disabled>Phiếu rà độc lập</button></div>
 <ol id="matrix-live-steps" class="matrix-live-steps" aria-live="polite" hidden></ol>
 <p id="matrix-status" role="status">Chưa chạy. Bản đề hiện có ${exam.questions.length} câu.</p><button type="button" id="matrix-poll-retry" hidden>Tải lại trạng thái</button><p id="matrix-metrics" class="hint"></p>
 <label id="matrix-reviewer-field" hidden>Người rà (không bắt buộc)<input id="matrix-reviewer" maxlength="120" placeholder="Ghi đúng người rà nếu muốn lưu góp ý từng câu"></label>
 <details id="matrix-progress"><summary>Nhật ký tự kiểm và sửa</summary><div id="matrix-trace" aria-live="polite"></div></details><div id="matrix-audit" class="hint"></div><div id="matrix-checks"></div><div id="matrix-preview"></div>
 <p id="matrix-review-summary" role="status"></p><label ${inline?'hidden':''}><input type="checkbox" id="matrix-final-check" style="width:auto"> Tôi đã xem lại kết quả cuối và đồng ý thay bộ câu trong đề.</label>
 ${inline?'<button type="button" id="matrix-view-proposal" hidden>Xem đề xuất trên trang</button><div class="matrix-decisions">':''}<button type="button" id="matrix-confirm-save" class="primary" disabled>${inline?"✓ Chấp nhận":"Xác nhận thay bộ câu trong đề"}</button>${inline?'<button type="button" id="matrix-discard" class="matrix-discard">✕ Bỏ đề xuất</button></div>':''}
 <p class="hint">Nhãn trong ma trận là yêu cầu. Đọc từng câu, đáp án và đoạn trích trước khi ghi mức thực tế. Qua kiểm cấu trúc không có nghĩa đã đúng kiến thức hoặc đúng mức.</p>`;
 if(inline)options.host.innerHTML='<div class="matrix-session-head"><h3>Soạn theo ma trận</h3><button type="button" class="matrix-close-x" title="Đóng thẻ ma trận" aria-label="Đóng thẻ soạn theo ma trận">✕</button></div>'+markup;else c.modal('Sinh bộ câu theo ma trận',markup);
 const dialog=options.host||document.querySelector('#dialog'),$=id=>dialog.querySelector('#'+id)||options.find?.(id);
 if(inline){
  const headWrap=dialog.querySelector('.matrix-session-head'),intro=headWrap.nextElementSibling,connection=intro.nextElementSibling;
  intro.remove();
  const request=document.createElement('details');request.id='matrix-request-settings';request.open=true;
  request.innerHTML='<summary>Yêu cầu soạn đề · '+count+' câu</summary>';
  const matrix=dialog.querySelector('.matrix-chat-summary'),edit=$('matrix-edit-plan'),score=edit.nextElementSibling;
  request.append(matrix,edit,score,$('matrix-source-mode').closest('label'),$('matrix-general-note'),$('matrix-inputs'),$('matrix-consent').closest('label'));headWrap.after(request);
  const startActions=document.createElement('div');startActions.className='matrix-start-actions';
  startActions.append($('matrix-start'));request.append(startActions);
  const later=document.createElement('button');later.type='button';later.textContent='Để sau';later.id='matrix-dismiss';startActions.append(later);
  headWrap.querySelector('.matrix-close-x').onclick=()=>later.click();
  const details=document.createElement('details');details.id='matrix-result-details';details.innerHTML='<summary>Chi tiết kỹ thuật</summary>';
  const retry=document.createElement('button');retry.type='button';retry.id='matrix-retry';retry.className='primary';retry.textContent='Thử lại';retry.hidden=true;
  const errClose=document.createElement('button');errClose.type='button';errClose.className='matrix-error-close';errClose.textContent='Đóng';errClose.hidden=true;
  const errActions=document.createElement('div');errActions.className='matrix-error-actions';errActions.hidden=true;
  errActions.append(retry,errClose);
  retry.onclick=()=>{$('matrix-request-settings').open=true;$('matrix-inputs').open=true;$('matrix-start').focus();};
  errClose.onclick=()=>later.click();
  $('matrix-status').after(errActions);
  const utilities=document.createElement('div');utilities.className='matrix-utilities';utilities.append($('matrix-download'),$('matrix-review-pack'));
  details.append(connection,$('matrix-metrics'),$('matrix-reviewer-field'),$('matrix-progress'),$('matrix-audit'),$('matrix-checks'),utilities,dialog.querySelector(':scope>p.hint:last-child'));
  errActions.after(details);
  const decisions=dialog.querySelector('.matrix-decisions');decisions.setAttribute('aria-label','Duyệt đề xuất');
  const label=document.createElement('b');label.className='matrix-decision-title';label.textContent=count+' câu chờ duyệt';
  decisions.prepend(label,$('matrix-view-proposal'));decisions.append($('matrix-review-summary'));
  const stop=$('matrix-stop');stop.hidden=true;dialog.append(stop);dialog.querySelector('.toolbar-row').remove();
 }
 const sameExam=()=>c.exam().id===exam.id&&c.exam().revision===baseRevision;
 const setStatus=text=>{$('matrix-status').textContent=text;};
 let preparing=false,lastTrace=[];
 function renderLiveSteps(trace=lastTrace){
  const el=$('matrix-live-steps');if(!el)return;
  lastTrace=Array.isArray(trace)?trace:[];
  const steps=['Chuẩn bị ma trận & nguồn','Sinh bộ câu hỏi','Tự kiểm & giải độc lập','Chờ giáo viên duyệt'];
  const activeRun=preparing||job?.status==='running';
  const complete=job?.status==='complete';
  const failed=!!job&&!activeRun&&!complete;
  const hidden=inline?(dialog.dataset.phase==='setup'&&!preparing):(!activeRun&&!complete&&!failed);
  el.hidden=hidden;if(hidden)return;
  let active=0;
  if(complete)active=3;
  else if(lastTrace.some(t=>['structure_check','blind_content_check','level_recheck','candidate_check','generation_result'].includes(t.event)))active=2;
  else if(lastTrace.some(t=>['run_start','model_start','model_call_start','tool_call'].includes(t.event))||job?.status==='running')active=1;
  el.innerHTML=steps.map((label,idx)=>{
   const cls=idx<active||(complete&&idx<3)?'is-done':idx===active?(failed?'is-error':complete?'is-done':'is-active'):'';
   return `<li class="matrix-step ${cls}"><span class="matrix-step-num">${idx+1}</span><span>${esc(label)}</span></li>`;
  }).join('');
 }
 function syncPhase(){
  if(!inline){renderLiveSteps();return;}
  const phase=job?.status==='running'||preparing?'running':job?.status==='complete'&&!job.saved&&lastCandidate?.jobId===job.jobId&&$('matrix-poll-retry').hidden?'review':job?'error':'setup';
  const changed=dialog.dataset.phase!==phase;dialog.dataset.phase=phase;
  if(changed){$('matrix-request-settings').open=phase==='setup';$('matrix-result-details').open=false;$('matrix-progress').open=false;}
  $('matrix-result-details').hidden=phase==='setup';$('matrix-status').hidden=phase==='setup'&&!$('matrix-status').dataset.error;
  const showRetry=phase==='error'&&$('matrix-poll-retry').hidden;
  const errActions=dialog.querySelector('.matrix-error-actions'),errClose=dialog.querySelector('.matrix-error-close'),closeX=dialog.querySelector('.matrix-close-x');
  if(errActions)errActions.hidden=!showRetry;
  if(errClose)errClose.hidden=!showRetry;
  $('matrix-retry').hidden=!showRetry;
  if(closeX)closeX.hidden=phase==='running';
  renderLiveSteps();
  options.phase?.({phase,cancellable:!$('matrix-stop').disabled,decisions:dialog.querySelector('.matrix-decisions')||options.find?.('matrix-confirm-save')?.parentElement,stop:()=>{$('matrix-stop').click();}});
 }
 const guard=fn=>async event=>{event?.preventDefault();event?.stopPropagation();try{await fn();}catch(error){preparing=false;$('matrix-status').dataset.error='true';setStatus(error.message);$('matrix-start').disabled=job?.status==='running';syncPhase();}};
 const lockSources=locked=>{for(const id of ['matrix-source-name','matrix-source-text','matrix-consent','matrix-source-mode'])$(id).disabled=locked;};
 const sourceInput=$('matrix-source-text');
 sourceInput.readOnly=sourceRefs.length>0;
 let pastedSource='';
 $('matrix-source-mode').addEventListener('change',()=>{
  if(!sourceInput.readOnly)pastedSource=sourceInput.value;
  sourceInput.readOnly=$('matrix-source-mode').value==='attached';
  sourceInput.value=sourceInput.readOnly?attachedPreview:pastedSource;
 });
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
 function evidenceHTML(e){
  const currentDocs=(c.exam()?.id===exam.id?c.exam().docs:exam.docs)||[];
  return citationContextHTML(e,currentDocs,{
   pastedText:source,
   pastedName:$('matrix-source-name').value,
   pastedRefs:approval?.sources,
  });
 }
 function showProposal(){
  lastCandidate=job;
  $('matrix-reviewer-field').hidden=false;
  reviews=job.reviews||{};
  if(!$('matrix-reviewer').value) $('matrix-reviewer').value=Object.values(reviews)[0]?.reviewer||'';
  $('matrix-preview').innerHTML='<h3>Bản xem trước · chưa ghi vào đề</h3>'+job.proposal.questions.map((q,i)=>`<section class="matrix-review-question" style="border:1px solid #c7d8d1;border-radius:8px;padding:16px;margin:16px 0" data-matrix-question="${i}">
   <p><b>Câu ${i+1} · ${esc(q.topic)} · Yêu cầu: ${LEVELS[q.level]} · ${q.points??(q.pointsQ4/4)} điểm</b></p>
   <p>${richTextHTML(q.stem)}</p><ol type="A">${q.options.map(x=>'<li>'+richTextHTML(x)+'</li>').join('')}</ol>
   <p>Đáp án AI đề xuất: <b>${q.type==='essay'?'Tự luận':diffContentHTML(q.type==='mcq'?'answer':q.type==='truefalse'?'truthValues':'answerText',q.answer)}</b>. ${richTextHTML(q.explanation)}</p>
   ${q.rubric?.length?'<div class="matrix-rubric"><b>Hướng dẫn chấm</b>'+diffContentHTML('rubric',q.rubric.map(r=>({...r,points:r.points??(r.pointsQ4/4)})))+'</div>':''}
   ${q.evidence.map(evidenceHTML).join('')}
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
   renderLiveSteps(trace);
   const latestCheck=trace.findLast(t=>t.event==='generation_result');if(latestCheck)showChecks(latestCheck);
   $('matrix-trace').innerHTML=trace.map(t=>t.event?'<p>'+esc({run_start:'Trợ lý bắt đầu',provider_model_switch:'Hết quota: chuyển từ '+(t.fromModel||'')+' sang '+(t.toModel||''),provider_key_switch:'Đổi sang key dự phòng (ẩn khóa)',provider_retry:'Thử lại sau lỗi dịch vụ tạm thời',model_start:'Đang gọi '+(t.model||''),model_end:(t.ok?'Đã nhận kết quả từ ':'Lượt gọi chưa đạt: ')+(t.model||''),model_call_start:({agent:'AI đang soạn hoặc sửa bộ câu',repair_stem:'AI đang đặt lại thân câu',level_recheck:'AI đang rà riêng câu có mức mâu thuẫn',blind_content_check:'AI đang giải lại và rà mức',explanation_check:'AI đang đối chiếu lời giải'}[t.purpose]||'Đang gọi AI'),model_call_end:'AI đã trả kết quả lượt xử lý',tool_call:'Trợ lý gọi công cụ '+(t.tool||''),structure_check:'Kiểm cấu trúc',blind_content_check:'Giải lại, rà mức và căn cứ',level_recheck:'Đã rà riêng mức của câu '+(t.ordinal+1),candidate_check:'Tổng hợp kiểm nội dung',generation_result:'Kết quả lần nộp '+t.generationAttempt+(t.reusedFromAttempt?' · Trùng lần '+t.reusedFromAttempt+', chờ sửa bộ câu':''),run_end:'Kết thúc: '+t.status}[t.event]||t.event)+(typeof t.ok==='boolean'?' · '+(t.ok?'Qua bộ kiểm':'Còn vấn đề'):'')+(t.errors?.length?' · '+esc(t.errors.map(errorText).join(' · ')):'')+(t.seconds!==undefined?' · '+Number(t.seconds).toFixed(2)+' giây':'')+'</p>':'<p>Câu '+t.question+' · lượt '+t.attempt+' · '+esc(t.status)+(t.message?' · '+esc(t.message):'')+'</p>').join('');
   const last=trace.at(-1);if(job.status==='running'&&last)setStatus('Đang '+({model_call_start:({agent:'soạn hoặc sửa bộ câu',repair_stem:'đặt lại thân câu',level_recheck:'rà riêng câu có mức mâu thuẫn',blind_content_check:'giải độc lập và rà mức',explanation_check:'đối chiếu lời giải'}[last.purpose]||'gọi model'),model_call_end:'đã nhận kết quả lượt AI',generation_result:last.reusedFromAttempt?'chờ AI sửa bộ câu bị nộp trùng':'xử lý kết quả lần nộp '+last.generationAttempt}[last.event]||'kiểm tra và chờ kết quả AI')+'…');
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
  const mode=$('matrix-source-mode').value,useSource=mode!=='general';
  if(mode==='provided'&&(!$('matrix-source-name').value.trim()||sourceInput.value.trim().length<20))throw Error('Điền tên nguồn và ít nhất 20 ký tự nội dung nguồn.');
  if(mode==='attached'&&pendingPages.length)throw Error('Đối chiếu các trang nguồn đã chọn hoặc chọn lại trang trước khi sinh.');
  if(!$('matrix-consent').checked)throw Error('Cần cho phép gửi nguồn tới '+destination+' trước khi sinh.');
  preparing=true;delete $('matrix-status').dataset.error;setStatus('Đang chuẩn bị yêu cầu…');syncPhase();
  $('matrix-start').disabled=true;$('matrix-confirm-save').disabled=true;$('matrix-progress').open=true;
  $('matrix-final-check').checked=false;reviews={};
  if(!sameExam())throw Error('Đề đã đổi. Đóng tác vụ này rồi mở lại để dùng phiên bản mới.');
  await c.persist();
  options.clearPreview?.();
  job=null;
  source=mode==='provided'?sourceInput.value.trim():'';
  approval=await api('/api/exams/'+exam.id+'/matrix/approve',{baseRevision,sourceText:source,sourceName:useSource?$('matrix-source-name').value.trim()||'Trang đã chọn trong kho':'Kiến thức chung · không có nguồn đối chiếu',sourceMode:useSource?'provided':'general',...(mode==='attached'?{sources:sourceRefs}:{})});
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
  const response=await fetch(base()+'/review-pack',{headers:db.workspaceHeaders()});
  if(!response.ok){const error=await response.json();throw Error(error.error||'Chưa tạo được phiếu rà.');}
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
  link.href=url;link.download='Phieu_ra_'+job.jobId+'.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
 syncPhase();
 const latest=await api('/api/exams/'+exam.id+'/proposals/latest');
 if(latest&&latest.baseRevision===baseRevision&&!latest.saved&&!latest.discarded){job=latest;if(latest.input){source=latest.input.sourceText||'';$('matrix-source-text').value=source;$('matrix-source-name').value=latest.input.sourceName||'';approval=latest.input.approval;$('matrix-source-mode').value=approval?.sources?.some(s=>s.locator.kind==='page')&&sourceRefs.length?'attached':approval?.sources?.length?'provided':'general';sourceInput.readOnly=$('matrix-source-mode').value==='attached';if(sourceInput.readOnly)sourceInput.value=attachedPreview;}lockSources(job.status==='running');$('matrix-start').disabled=job.status==='running';$('matrix-stop').disabled=job.status!=='running';syncPhase();await poll();}
 return {refresh:updateConfirm};
}
