import {esc,uid} from './core.js';
import {mergeAssistantSourceDraft} from './reference.js';

function linkRow(item){
 return '<article class="shared-link-row"><div><b>Bản '+item.revision+' · '+(item.answers?'Có đáp án':'Bản học sinh')+(item.community?' · Kho cộng đồng':'')+'</b><small>'+esc(new Date(item.created).toLocaleString('vi-VN'))+'</small></div>'+
 '<input readonly aria-label="Liên kết bản '+item.revision+'" value="'+esc(item.url)+'"><div class="row">'+
 '<button type="button" data-action="copy-share" data-url="'+esc(item.url)+'">Sao chép</button>'+
 '<a href="'+esc(item.url)+'" target="_blank" rel="noopener noreferrer">Mở bản chỉ xem</a>'+
 '<button type="button" class="danger" data-action="revoke-share" data-token="'+esc(item.token)+'">Thu hồi</button></div></article>';
}

export async function openSharing(c,api,{localPoC=false,sharedSnapshots=false}={}){
 if(localPoC&&!sharedSnapshots){
  c.modal('Chia sẻ đề','<p>Bản đang chạy chưa có chia sẻ snapshot. Dùng Xuất đề để gửi Word/PDF, hoặc nạp bản app mới.</p>');return;
 }
 const exam=c.exam(),result=sharedSnapshots?await api('/api/share?examId='+encodeURIComponent(exam.id)):{shares:[]};
 c.modal('Chia sẻ bản đề đã lưu',
  '<p>Ai có liên kết đều xem được bản được chọn. Sửa đề gốc không đổi bản chia sẻ. Liên kết hoạt động khi máy chạy app; đây chưa phải hosting Internet.</p>'+
  '<form id="share-form" data-exam="'+esc(exam.id)+'" data-revision="'+exam.revision+'">'+
  '<p><b>'+esc(exam.title)+'</b> · Bản '+exam.revision+' · '+exam.questions.length+' câu</p>'+
  '<label class="source-choice"><input name="answers" type="checkbox"> Kèm đáp án, lời giải và barem</label>'+
  '<label class="source-choice"><input name="allowCopy" type="checkbox" checked> Cho phép tạo bản sao để chỉnh sửa</label>'+
  (sharedSnapshots?'<label class="source-choice"><input name="community" type="checkbox"> Công bố bản học sinh trong kho cộng đồng</label><p class="hint">Người dùng cùng bản app có thể tìm và mở đề công bố. Chỉ công bố tài liệu được phép chia sẻ.</p><div data-community-fields hidden><label class="source-choice"><input name="consentPublic" type="checkbox"> Đồng ý công bố công khai trên kho cộng đồng (chỉ bản học sinh)</label><div class="grid2"><label>Bộ sách (tùy chọn)<input name="series" maxlength="150" value="'+esc(exam.series||'')+'"></label><label>Chương (tùy chọn)<input name="chapter" maxlength="200" value="'+esc(exam.chapter||'')+'"></label></div></div>':'')+
  '<div class="modal-foot"><button class="primary" type="submit">Tạo liên kết chỉ xem</button></div></form>'+
  (sharedSnapshots?'<button type="button" data-action="community-exams">Mở kho đề cộng đồng</button>':'')+
  (result.shares.length?'<section class="shared-links"><h3>Liên kết đang mở</h3><p class="hint">Thu hồi ngăn truy cập tiếp; không xóa nội dung người khác đã xem hoặc tải.</p>'+result.shares.map(linkRow).join('')+'</section>':''));
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
  const community=data.has('community');
  const series=String(data.get('series')||'').trim();
  const chapter=String(data.get('chapter')||'').trim();
  const result=await api('/api/share',{examId:form.dataset.exam,baseRevision:Number(form.dataset.revision),answers:data.has('answers'),allowCopy:data.has('allowCopy'),...(community?{community:true,consentPublic:data.has('consentPublic'),...(series?{series}:{}),...(chapter?{chapter}:{})}:{})});
  if(!form.isConnected||!document.querySelector('#dialog').open){
   c.toast('Đã tạo liên kết. Mở Chia sẻ để lấy hoặc thu hồi.');return;
  }
  c.modal(result.community?'Đề đã có trong kho cộng đồng':'Liên kết chia sẻ đã tạo',
   (result.community?'<p>Người dùng có thể tìm bản học sinh trong kho cộng đồng. Mở Chia sẻ để thu hồi.</p>':'<p>Đây là bản cố định tại thời điểm tạo. Chỉ gửi liên kết cho người được phép xem.</p>')+
   '<label>Liên kết chỉ xem<input id="share-url" value="'+esc(result.url)+'" readonly></label>'+
   '<div class="modal-foot"><button type="button" data-action="copy-share" class="primary">Sao chép liên kết</button>'+
   '<a href="'+esc(result.url)+'" target="_blank" rel="noopener noreferrer">Mở bản chỉ xem</a>'+
   '<button type="button" data-action="share">Quản lý liên kết</button></div>');
 }finally{
  form.dataset.creating='';submit.disabled=false;submit.textContent=form.elements.community?.checked?'Công bố bản học sinh':'Tạo liên kết chỉ xem';
 }
}

export async function openCommunity(c,api){
 const layer1=document.querySelector('#dialog');
 const useLayer2=Boolean(layer1?.open&&layer1.querySelector('#assistant-source-form')&&document.querySelector('#dialog-layer2'));
 const dlg=useLayer2?document.querySelector('#dialog-layer2'):layer1;
 c.modal('Kho đề cộng đồng',`<form id="community-filter" data-layer2="${useLayer2?'1':'0'}"><label>Tìm kiếm (không dấu · tiêu đề &amp; thân câu)<input name="q" type="search" maxlength="120" placeholder="Ví dụ: giua hoc ki, phan so..."></label><label class="source-choice"><input name="scope" type="checkbox" value="content" checked> Tìm cả trong nội dung câu hỏi &amp; phương án</label><div class="grid2"><label>Môn<input name="subject" maxlength="80" placeholder="Ví dụ: Toán"></label><label>Lớp<select name="grade"><option value="">Tất cả</option>${Array.from({length:12},(_,i)=>`<option>${i+1}</option>`).join('')}</select></label><label>Bộ sách<input name="series" maxlength="150" placeholder="Kết nối tri thức"></label><label>Chương<input name="chapter" maxlength="200"></label></div><button type="submit">Tìm đề</button><p data-community-status role="status"></p><div data-community-results></div><div class="row"><button type="button" data-community-page="prev">Trang trước</button><button type="button" data-community-page="next">Trang sau</button></div></form>`,'',{layer:useLayer2?2:1});
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
   page=data.page;
   status.textContent=data.exams.length?`Trang ${page} · ${data.exams.length} đề`:'Chưa có đề phù hợp.';
   results.innerHTML=data.exams.map(item=>{
    const token=encodeURIComponent(item.token);
    const meta=[item.subject,item.grade?'Lớp '+item.grade:'',item.series,item.chapter,item.questions+' câu'].filter(Boolean).join(' · ');
    return `<article class="small-card"><h3>${esc(item.title)}</h3><p>${esc(meta)}</p><div class="row"><a href="/s/${token}" target="_blank" rel="noopener noreferrer">Xem đề</a>${item.allowCopy?`<button type="button" data-action="community-clone" data-token="${token}">Sao bản độc lập (UUID mới)</button><a href="/?copy=${token}">Sao về kho của tôi</a><button type="button" data-action="community-source" data-token="${token}">Dùng làm nguồn</button>`:''}</div></article>`;
   }).join('');
   prev.disabled=page===1;next.disabled=!data.hasMore;
  }catch(error){
   if(sequence===request&&form.isConnected)status.textContent=error.message;
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
 const token=button.dataset.token;
 const result=await api('/api/community-exams/'+encodeURIComponent(token)+'/clone',{});
 const cloned=result?.clonedExam;
 if(!cloned?.id)throw Error('Không tạo được bản sao độc lập.');
 c.getState().exams.push(cloned);
 c.getState().current=cloned.id;
 document.querySelector('#dialog-layer2')?.close();
 document.querySelector('#dialog')?.close();
 await c.persist();
 c.render();
 c.toast('Đã tạo bản sao độc lập với UUID mới.');
}

export async function attachCommunitySource(c,api,button){
 const form=button.closest('#community-filter'),examId=c.exam().id;
 const dlg=form?.closest('dialog')||document.querySelector('#dialog');
 const isLayer2=dlg?.id==='dialog-layer2';
 const token=button.dataset.token;
 const result=await api('/api/share/read/'+encodeURIComponent(token));
 if(!result.allowCopy||!result.exam)throw Error('Đề hiện chỉ cho xem hoặc đã thu hồi.');
 if(!form?.isConnected||!dlg?.open||c.exam().id!==examId)return;
 const exam=result.exam;
 const text=[exam.quote?.text,...exam.questions.map((q,i)=>
  ['Câu '+(i+1)+'. '+q.stem,...q.options.map((option,j)=>String.fromCharCode(65+j)+'. '+option)].join('\n')
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
 if(isLayer2)await c.act('assistant-sources');
 c.toast('Đã gắn đề cộng đồng làm nguồn.');
}
