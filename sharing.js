import {esc,uid} from './core.js';
import {mergeAssistantSourceDraft} from './reference.js';
import {put as putStorage} from './storage.js';

const SHARE_LINK_STYLE='display:inline-flex;align-items:center;justify-content:center;min-height:40px;min-width:64px;padding:6px 12px;border:1px solid var(--line,#cbd5e1);border-radius:8px;white-space:nowrap;text-decoration:none;font-weight:500';
const CLONE_ARRAY_FIELDS=['docs','matrix','history','undo','redo','chat','data','appliedPrefs','questions','passages'];

function linkButton(href,label,blank=true){
 return '<a href="'+esc(href)+'"'+(blank?' target="_blank" rel="noopener noreferrer"':'')+' style="'+SHARE_LINK_STYLE+'">'+esc(label)+'</a>';
}

function sanitizeClonedExam(cloned,answersIncluded){
 cloned.updated||=Date.now();
 cloned.workflowStatus||='draft';
 if(!cloned.quote||typeof cloned.quote!=='object')cloned.quote={text:'',source:''};
 for(const key of CLONE_ARRAY_FIELDS){if(!Array.isArray(cloned[key]))cloned[key]=[];}
 if(answersIncluded===true)return cloned;
 for(const q of cloned.questions){
  if(!q||typeof q!=='object')continue;
  if(q.answerKnown===false||answersIncluded===false||q.answer==null){
   if(q.type==='choice'||q.answerKnown===false||answersIncluded===false)q.answer=null;
   q.answerKnown=false;
  }
 }
 return cloned;
}

function linkRow(item){
 return '<article class="shared-link-row"><div><b>Bản '+item.revision+' · '+(item.answers?'Có đáp án':'Bản học sinh')+(item.community?' · Kho cộng đồng':'')+'</b><small>'+esc(new Date(item.created).toLocaleString('vi-VN'))+'</small></div>'+
 '<input readonly aria-label="Liên kết bản '+item.revision+'" value="'+esc(item.url)+'"><div class="row" style="flex-wrap:wrap;gap:8px">'+
 '<button type="button" data-action="copy-share" data-url="'+esc(item.url)+'">Sao chép</button>'+
 linkButton(item.url,'Mở bản chỉ xem')+
 '<button type="button" class="danger" data-action="revoke-share" data-token="'+esc(item.token)+'">Thu hồi</button></div></article>';
}

export async function openSharing(c,api,{localPoC=false,sharedSnapshots=false}={}){
 if(localPoC&&!sharedSnapshots){
  c.modal('Chia sẻ đề','<p>Bản đang chạy chưa có chia sẻ bản chụp đề. Dùng Xuất đề để gửi Word/PDF, hoặc cập nhật phiên bản ứng dụng mới.</p>');return;
 }
 const initialExam=c.exam();
 if(!initialExam?.id)throw Error('Chưa có đề đang mở để chia sẻ.');
 const result=sharedSnapshots?await api('/api/share?examId='+encodeURIComponent(initialExam.id)):{shares:[]};
 const latestExam=c.exam();
 if(latestExam&&latestExam.id!==initialExam.id)return;
 const exam=latestExam?.id===initialExam.id?latestExam:initialExam;
 const rev=exam.revision??0;
 const qCount=Array.isArray(exam.questions)?exam.questions.length:0;
 const shares=Array.isArray(result?.shares)?result.shares:[];
 c.modal('Chia sẻ bản đề đã lưu',
  '<p>Ai có liên kết đều xem được bản được chọn. Sửa đề gốc không đổi bản chia sẻ. Liên kết hoạt động khi máy đang chạy ứng dụng; đây chưa phải máy chủ Internet.</p>'+
  '<form id="share-form" data-exam="'+esc(exam.id)+'" data-revision="'+rev+'">'+
  '<p><b>'+esc(exam.title)+'</b> · Bản '+rev+' · '+qCount+' câu</p>'+
  '<label class="source-choice"><input name="answers" type="checkbox"> Kèm đáp án, lời giải và barem</label>'+
  '<label class="source-choice"><input name="allowCopy" type="checkbox" checked> Cho phép tạo bản sao để chỉnh sửa</label>'+
  (sharedSnapshots?'<label class="source-choice"><input name="community" type="checkbox"> Công bố bản học sinh trong kho cộng đồng</label><p class="hint">Người dùng cùng phiên bản ứng dụng có thể tìm và mở đề công bố. Chỉ công bố tài liệu được phép chia sẻ.</p><div data-community-fields hidden><label class="source-choice"><input name="consentPublic" type="checkbox"> Đồng ý công bố công khai trên kho cộng đồng (chỉ bản học sinh)</label><div class="grid2"><label>Bộ sách (tùy chọn)<input name="series" maxlength="150" value="'+esc(exam.series||'')+'"></label><label>Chương (tùy chọn)<input name="chapter" maxlength="200" value="'+esc(exam.chapter||'')+'"></label></div></div>':'')+
  '<div class="modal-foot" style="flex-wrap:wrap;gap:8px"><button class="primary" type="submit">Tạo liên kết chỉ xem</button></div></form>'+
  (sharedSnapshots?'<button type="button" data-action="community-exams">Mở kho đề cộng đồng</button>':'')+
  (shares.length?'<section class="shared-links"><h3>Liên kết đang mở</h3><p class="hint">Thu hồi ngăn truy cập tiếp; không xóa nội dung người khác đã xem hoặc tải.</p>'+shares.map(linkRow).join('')+'</section>':''));
 const form=document.querySelector('#share-form');
 const communityFields=form.querySelector('[data-community-fields]');
 form.elements.community?.addEventListener('change',()=>{
  const publish=form.elements.community.checked;
  form.elements.answers.disabled=publish;
  if(publish)form.elements.answers.checked=false;
  if(communityFields)communityFields.hidden=!publish;
  if(form.elements.consentPublic)form.elements.consentPublic.checked=publish;
  form.querySelector('[type=submit]').textContent=publish?'Công bố bản học sinh':'Tạo liên kết chỉ xem';
 });
}

export async function createSharing(c,api,form){
 if(form.dataset.creating)return;
 const data=new FormData(form);
 form.dataset.creating='true';
 const submit=form.querySelector('[type=submit]');submit.disabled=true;submit.textContent='Đang tạo bản chia sẻ…';
 try{
  await c.persist();
  if(!form.isConnected||!document.querySelector('#dialog').open)return;
  const latestExam=c.exam?.();
  const baseRevision=latestExam?.id===form.dataset.exam&&latestExam.revision!=null?Number(latestExam.revision):Number(form.dataset.revision);
  const community=data.has('community');
  const series=String(data.get('series')||'').trim();
  const chapter=String(data.get('chapter')||'').trim();
  const result=await api('/api/share',{examId:form.dataset.exam,baseRevision,answers:data.has('answers'),allowCopy:data.has('allowCopy'),...(community?{community:true,consentPublic:data.has('consentPublic'),...(series?{series}:{}),...(chapter?{chapter}:{})}:{})});
  if(!form.isConnected||!document.querySelector('#dialog').open){
   c.toast('Đã tạo liên kết. Mở Chia sẻ để lấy hoặc thu hồi.');return;
  }
  c.modal(result.community?'Đề đã có trong kho cộng đồng':'Liên kết chia sẻ đã tạo',
   (result.community?'<p>Người dùng có thể tìm bản học sinh trong kho cộng đồng. Mở Chia sẻ để thu hồi.</p>':'<p>Đây là bản cố định tại thời điểm tạo. Chỉ gửi liên kết cho người được phép xem.</p>')+
   '<label>Liên kết chỉ xem<input id="share-url" value="'+esc(result.url)+'" readonly></label>'+
   '<div class="modal-foot" style="flex-wrap:wrap;gap:8px"><button type="button" data-action="copy-share" class="primary">Sao chép liên kết</button>'+
   linkButton(result.url,'Mở bản chỉ xem')+
   '<button type="button" data-action="share">Quản lý liên kết</button></div>');
 }finally{
  form.dataset.creating='';submit.disabled=false;submit.textContent=form.elements.community?.checked?'Công bố bản học sinh':'Tạo liên kết chỉ xem';
 }
}

export async function openCommunity(c,api){
 const layer1=document.querySelector('#dialog');
 const useLayer2=Boolean(layer1?.open&&layer1.querySelector('#assistant-source-form')&&document.querySelector('#dialog-layer2'));
 const dlg=useLayer2?document.querySelector('#dialog-layer2'):layer1;
 c.modal('Kho đề cộng đồng',`<form id="community-filter" data-layer2="${useLayer2?'1':'0'}"><label>Tìm kiếm (không dấu · tiêu đề &amp; thân câu)<input name="q" type="search" maxlength="120" placeholder="Ví dụ: giua hoc ki, phan so..."></label><label class="source-choice"><input name="scope" type="checkbox" value="content" checked> Tìm cả trong nội dung câu hỏi &amp; phương án</label><div class="grid2"><label>Môn<input name="subject" maxlength="80" placeholder="Ví dụ: Toán"></label><label>Lớp<select name="grade"><option value="">Tất cả</option>${Array.from({length:12},(_,i)=>`<option>${i+1}</option>`).join('')}</select></label><label>Bộ sách<input name="series" maxlength="150" placeholder="Kết nối tri thức"></label><label>Chương<input name="chapter" maxlength="200"></label></div><button type="submit">Tìm đề</button><p data-community-status role="status"></p><div data-community-results></div><div class="row" style="flex-wrap:wrap;gap:8px"><button type="button" data-community-page="prev">Trang trước</button><button type="button" data-community-page="next">Trang sau</button></div></form>`,'',{layer:useLayer2?2:1});
 const form=dlg.querySelector('#community-filter'),results=form.querySelector('[data-community-results]');
 const status=form.querySelector('[data-community-status]');
 const prev=form.querySelector('[data-community-page=prev]'),next=form.querySelector('[data-community-page=next]');
 let page=1, request=0, filters=new URLSearchParams(new FormData(form));
 async function load(number){
  const sequence=++request;
  prev.disabled=next.disabled=true;
  status.textContent='Đang tìm đề…';
  results.textContent='';
  try{
   const query=new URLSearchParams(filters);
   if(!query.get('scope'))query.set('scope','title');
   query.set('page',String(number));
   const data=await api('/api/community-exams?'+query);
   if(sequence!==request||!form.isConnected)return;
   page=Number(data?.page)||1;
   const exams=Array.isArray(data?.exams)?data.exams:[];
   status.textContent=exams.length?`Trang ${page} · ${exams.length} đề`:'Chưa có đề phù hợp.';
   results.innerHTML=exams.map(item=>{
    const rawToken=String(item.token||''),urlToken=encodeURIComponent(rawToken),dataToken=esc(rawToken);
    const meta=[item.subject,item.grade?'Lớp '+item.grade:'',item.series,item.chapter,(item.questions??0)+' câu'].filter(Boolean).join(' · ');
    return `<article class="small-card"><h3>${esc(item.title)}</h3><p>${esc(meta)}</p><div class="row" style="flex-wrap:wrap;gap:8px">${linkButton('/s/'+urlToken,'Xem đề')}${item.allowCopy?`<button type="button" data-action="community-clone" data-token="${dataToken}">Sao bản độc lập (UUID mới)</button>${linkButton('/?copy='+urlToken,'Sao về kho của tôi',false)}<button type="button" data-action="community-source" data-token="${dataToken}">Dùng làm nguồn</button>`:''}</div></article>`;
   }).join('');
   prev.disabled=page<=1;next.disabled=!data?.hasMore;
  }catch(error){
   if(sequence===request&&form.isConnected){
    status.textContent=error.message;
    prev.disabled=page<=1;
    next.disabled=true;
   }
  }
 }
 form.addEventListener('submit',event=>{
  event.preventDefault();event.stopPropagation();
  filters=new URLSearchParams(new FormData(form));void load(1);
 });
 prev.onclick=()=>load(page-1);next.onclick=()=>load(page+1);
 await load(1);
}

export async function cloneCommunityExam(c,api,button){
 if(button?.disabled)return;
 const token=button?.dataset?.token;
 if(!token)throw Error('Thiếu mã bản chia sẻ.');
 if(button)button.disabled=true;
 try{
  const result=await api('/api/community-exams/'+encodeURIComponent(token)+'/clone',{});
  const cloned=result?.clonedExam;
  if(!cloned?.id)throw Error('Không tạo được bản sao độc lập.');
  sanitizeClonedExam(cloned,result?.answersIncluded);
  if(result?.files&&typeof result.files==='object'){
   for(const [fid,dataUri] of Object.entries(result.files)){
    if(typeof dataUri==='string'&&dataUri)await putStorage('file:'+fid,dataUri);
   }
  }
  const state=c.getState();
  if(!Array.isArray(state.exams))state.exams=[];
  if(!state.exams.some(item=>item?.id===cloned.id))state.exams.push(cloned);
  state.current=cloned.id;
  document.querySelector('#dialog-layer2')?.close();
  document.querySelector('#dialog')?.close();
  if(c.getViewMode?.()==='home'&&typeof c.setViewMode==='function')c.setViewMode('workspace');
  try{
   await c.persist();
  }finally{
   c.render();
  }
  c.toast('Đã tạo bản sao độc lập với UUID mới.');
 }finally{
  if(button)button.disabled=false;
 }
}

export async function attachCommunitySource(c,api,button){
 if(button?.disabled)return;
 const token=button?.dataset?.token;
 if(!token)throw Error('Thiếu mã bản chia sẻ.');
 const form=button.closest?.('#community-filter'),examId=c.exam()?.id;
 const dlg=form?.closest?.('dialog')||document.querySelector('#dialog');
 const isLayer2=dlg?.id==='dialog-layer2';
 if(button)button.disabled=true;
 try{
  const result=await api('/api/share/read/'+encodeURIComponent(token));
  if(!result.allowCopy||!result.exam)throw Error('Đề hiện chỉ cho xem hoặc đã thu hồi.');
  if(!form?.isConnected||!dlg?.open||c.exam()?.id!==examId)return;
  const exam=result.exam;
  const passages=Array.isArray(exam.passages)?exam.passages.map(p=>p?.text||p?.content).filter(t=>typeof t==='string'&&t.trim()):[];
  const head=[];
  for(const part of [exam.quote?.text,...passages]){if(part&&!head.includes(part))head.push(part);}
  const text=[...head,...(exam.questions||[]).map((q,i)=>
   ['Câu '+(i+1)+'. '+(q.stem||''),...(q.options||[]).map((option,j)=>String.fromCharCode(65+j)+'. '+option)].join('\n')
  )].filter(Boolean).join('\n\n');
  if(!text.trim()||text.length>12000)throw Error('Nguồn trống hoặc vượt 12.000 ký tự.');
  let addedDocId=null;
  c.change('Gắn đề cộng đồng làm nguồn',current=>{
   const existing=current.docs.find(doc=>doc.communityToken===token);
   const id=existing?.id||uid();
   addedDocId=id;
   if(!existing)current.docs.push({id,kind:'text',name:exam.title+' · Đề cộng đồng',
    version:1,text,pages:[{number:1,text}],communityToken:token});
   current.assistantSources=[...new Set([...(current.assistantSources||[]),id])];
   (current.assistantSourcePages??={})[id]=[1];
  });
  if(addedDocId)mergeAssistantSourceDraft(examId,[addedDocId],{[addedDocId]:[1]});
  dlg.close();
  if(isLayer2)await c.act?.('assistant-sources');
  c.toast('Đã gắn đề cộng đồng làm nguồn.');
 }finally{
  if(button)button.disabled=false;
 }
}
