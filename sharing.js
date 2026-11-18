import {esc} from './core.js';

function linkRow(item){
 return '<article class="shared-link-row"><div><b>Bản '+item.revision+' · '+(item.answers?'Có đáp án':'Bản học sinh')+'</b><small>'+esc(new Date(item.created).toLocaleString('vi-VN'))+'</small></div>'+
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
  '<div class="modal-foot"><button class="primary" type="submit">Tạo liên kết chỉ xem</button></div></form>'+
  (result.shares.length?'<section class="shared-links"><h3>Liên kết đang mở</h3><p class="hint">Thu hồi ngăn truy cập tiếp; không xóa nội dung người khác đã xem hoặc tải.</p>'+result.shares.map(linkRow).join('')+'</section>':''));
}

export async function createSharing(c,api,form){
 if(form.dataset.creating)return;
 form.dataset.creating='true';
 const submit=form.querySelector('[type=submit]');submit.disabled=true;submit.textContent='Đang tạo bản chia sẻ…';
 try{
  await c.persist();
  const data=new FormData(form);
  const result=await api('/api/share',{examId:form.dataset.exam,baseRevision:Number(form.dataset.revision),answers:data.has('answers'),allowCopy:data.has('allowCopy')});
  if(!form.isConnected||!document.querySelector('#dialog').open){
   c.toast('Đã tạo liên kết. Mở Chia sẻ để lấy hoặc thu hồi.');return;
  }
  c.modal('Liên kết chia sẻ đã tạo',
   '<p>Đây là bản cố định tại thời điểm tạo. Chỉ gửi liên kết cho người được phép xem.</p>'+
   '<label>Liên kết chỉ xem<input id="share-url" value="'+esc(result.url)+'" readonly></label>'+
   '<div class="modal-foot"><button type="button" data-action="copy-share" class="primary">Sao chép liên kết</button>'+
   '<a href="'+esc(result.url)+'" target="_blank" rel="noopener noreferrer">Mở bản chỉ xem</a>'+
   '<button type="button" data-action="share">Quản lý liên kết</button></div>');
 }finally{
  form.dataset.creating='';submit.disabled=false;submit.textContent='Tạo liên kết chỉ xem';
 }
}
