const form=document.querySelector('#team-login'),feedback=document.querySelector('#login-feedback');
let mode='login';
function select(value){
 mode=value;feedback.textContent='';
 document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===mode)));
 document.querySelectorAll('[data-registration]').forEach(label=>{label.hidden=mode!=='register';label.querySelector('input').disabled=mode!=='register';});
 form.elements.password.autocomplete=mode==='register'?'new-password':'current-password';
 form.querySelector('[type=submit]').textContent=mode==='register'?'Tạo tài khoản từ lời mời':'Đăng nhập';
}
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>select(button.dataset.mode)));
function acceptInvite(){
 const invite=new URLSearchParams(location.hash.slice(1)).get('invite');
 if(invite){select('register');form.elements.inviteCode.value=invite;history.replaceState(null,'',location.pathname+location.search);}
}
acceptInvite();window.addEventListener('hashchange',acceptInvite);
form.addEventListener('submit',async event=>{
 event.preventDefault();const submit=form.querySelector('[type=submit]');submit.disabled=true;form.setAttribute('aria-busy','true');document.querySelectorAll('[data-mode]').forEach(button=>button.disabled=true);feedback.textContent='';
 try{
  const response=await fetch('/api/account/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Chưa đăng nhập được. Kiểm tra thông tin rồi thử lại.');
  form.reset();const copy=new URLSearchParams(location.search).get('copy');location.replace(copy&&/^[A-Za-z0-9_-]{43}$/.test(copy)?'/?copy='+encodeURIComponent(copy):'/');
 }catch(error){feedback.textContent=error.message||'Không kết nối được app. Thử lại khi máy chủ sẵn sàng.';}
 finally{submit.disabled=false;form.removeAttribute('aria-busy');document.querySelectorAll('[data-mode]').forEach(button=>button.disabled=false);}
});
