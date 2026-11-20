const contexts=new Map();
function contextFor(id){
 if(!contexts.has(id))contexts.set(id,{id,revision:0,stateConflict:false,pending:new Map(),inflight:new WeakMap(),disk:Promise.resolve(),remote:Promise.resolve()});
 return contexts.get(id);
}
let active=contextFor('local');
export const setIdentity=id=>{active=contextFor(id||'local');};
const dbp=new Promise((resolve,reject)=>{
 const request=indexedDB.open('tro-ly-soan-de-v1',1);
 request.onupgradeneeded=()=>request.result.createObjectStore('kv');
 request.onsuccess=()=>resolve(request.result);
 request.onerror=()=>reject(request.error);
});
async function localGet(ctx,key){
 const db=await dbp;
 return new Promise((resolve,reject)=>{
  const request=db.transaction('kv').objectStore('kv').get(ctx.id+':'+key);
  request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
 });
}
async function localPut(ctx,key,value){
 const db=await dbp;
 return new Promise((resolve,reject)=>{
  const tx=db.transaction('kv','readwrite');tx.objectStore('kv').put(value,ctx.id+':'+key);
  tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('Không lưu được bản tạm.'));
 });
}
async function updatePending(ctx,key,record,next){
 const db=await dbp;
 return new Promise((resolve,reject)=>{
  const tx=db.transaction('kv','readwrite'),store=tx.objectStore('kv'),name=ctx.id+':__pending:'+key;
  const request=store.get(name);
  request.onsuccess=()=>{
   if(!request.result||request.result.id!==record.id){resolve();return;}
   store.put(next,name);
  };
  tx.oncomplete=()=>resolve();
  tx.onerror=()=>reject(tx.error);
  tx.onabort=()=>reject(tx.error||Error('Không lưu được bản tạm.'));
 });
}
function disk(ctx,work){const operation=ctx.disk.then(work);ctx.disk=operation.catch(()=>{});return operation;}
function sameIdentity(ctx){if(ctx!==active)throw Error('Tài khoản đã đổi. Bản nháp được giữ riêng; đăng nhập lại đúng tài khoản để đồng bộ.');}
export function workspaceHeaders(ctx=active){return ctx.id.startsWith('team:')?{'X-Workspace-Context':ctx.id}:{};}
function send(ctx,key,record,saved=Promise.resolve()){
 if(ctx.inflight.has(record))return ctx.inflight.get(record);
 const operation=ctx.remote.then(async()=>{
  await saved;sameIdentity(ctx);
  const response=await fetch('/api/kv',{method:'PUT',headers:{...workspaceHeaders(ctx),'Content-Type':'application/json',...(key==='state'?{'If-Match':String(record.base)}:{})},body:JSON.stringify({key,value:record.value})});
  let result;try{result=await response.json();}catch{throw Error('Máy chủ chưa trả kết quả lưu hợp lệ. Bản tạm vẫn được giữ.');}
  if(!response.ok){
   if(key==='state'&&response.status===409&&result.code==='stale_snapshot')ctx.stateConflict=true;
   throw Error(result.error||'Không lưu được dữ liệu trên máy chủ. Bản tạm vẫn được giữ.');
  }
  if(key==='state'){ctx.revision=result.revision;ctx.stateConflict=false;}
  await disk(ctx,async()=>{
   const latest=ctx.pending.get(key);
   if(latest===record){ctx.pending.delete(key);await updatePending(ctx,key,record,null);}
   else if(latest){
    // Lần lưu cũ chỉ được cập nhật base, không xóa nháp mới hơn đang chờ.
    if(key==='state')latest.base=result.revision;
    await updatePending(ctx,key,latest,latest);
   }
  });
 });
 ctx.inflight.set(record,operation);
 operation.then(()=>ctx.inflight.delete(record),()=>ctx.inflight.delete(record));
 ctx.remote=operation.catch(()=>{});return operation;
}
export function hasStateConflict(){return active.stateConflict;}
export function hasPendingWrites(){return active.pending.size>0;}
export async function retryPendingWrites(){
 const ctx=active;
 for(const [key,record] of [...ctx.pending]){
  sameIdentity(ctx);if(ctx.pending.get(key)===record)await send(ctx,key,record);
 }
}
export async function get(key,{requireRemote=false}={}){
 const ctx=active;await ctx.remote;await ctx.disk;
 const queued=ctx.pending.get(key)||await localGet(ctx,'__pending:'+key);
 if(queued?.value!==undefined){
  ctx.pending.set(key,queued);if(key==='state'&&!ctx.revision)ctx.revision=queued.base||0;
  if(requireRemote)throw Error('Còn thay đổi chờ đồng bộ. Kết nối lại và đồng bộ bản nháp trước khi tiếp tục.');
 }
 try{
  sameIdentity(ctx);
  const response=await fetch('/api/kv?key='+encodeURIComponent(key),{headers:workspaceHeaders(ctx)});
  if(response.status===401||response.status===403){const error=Error('Phiên đăng nhập đã hết hoặc không có quyền. Đăng nhập lại để mở dữ liệu.');error.auth=true;throw error;}
  if(response.status===409){const error=Error('Tài khoản đã đổi ở tab khác. Tải lại trang để mở đúng kho.');error.auth=true;throw error;}
  if(!response.ok)throw Error('Máy chủ chưa sẵn sàng.');
  const result=await response.json();sameIdentity(ctx);const latest=ctx.pending.get(key);
  if(latest){
   if(key==='state')ctx.stateConflict=result.revision!==(latest.base||0);
   if(result.revision===(latest.base||0))try{await send(ctx,key,latest);}catch{}
   return latest.value;
  }
  if(key==='state'&&result.revision<ctx.revision)return localGet(ctx,key);
  if(key==='state'){ctx.revision=result.revision;ctx.stateConflict=false;}
  if(result.value!==null){await disk(ctx,()=>localPut(ctx,key,result.value));return result.value;}
  const legacy=await localGet(ctx,key);
  if(legacy!==undefined&&key.startsWith('file:')){sameIdentity(ctx);await put(key,legacy);}
  return legacy;
 }catch(error){
  if(requireRemote||error.auth||ctx!==active)throw error;
  if(key==='state')console.warn('Dùng bản lưu trong trình duyệt:',error.message);
 }
 return ctx.pending.get(key)?.value??localGet(ctx,key);
}
export function put(key,value){
 const ctx=active,record={id:crypto.randomUUID(),value:structuredClone(value),base:key==='state'?ctx.revision:0};
 if(ctx.restoring)return Promise.reject(Error('Đang khôi phục kho. Chờ hoàn tất trước khi sửa.'));
 ctx.pending.set(key,record);
 const saved=disk(ctx,async()=>{await localPut(ctx,key,record.value);await localPut(ctx,'__pending:'+key,record);});
 return send(ctx,key,record,saved);
}
export async function allFiles(ids){const ctx=active,files={};for(const id of ids){sameIdentity(ctx);const value=await get('file:'+id);sameIdentity(ctx);if(value)files[id]=value;}return files;}

export async function allPersonalLessons(){
 const ctx=active;
 const response=await fetch('/api/lesson-catalog/sources',{headers:workspaceHeaders(ctx)}).catch(()=>null);
 sameIdentity(ctx);
 if(!response||response.status===404)return null;
 if(!response.ok)throw Error('Chưa đọc được kho học liệu cá nhân để sao lưu.');
 const {sources}=await response.json();
 sameIdentity(ctx);
 if(!Array.isArray(sources))throw Error('Kho học liệu cá nhân trả dữ liệu không hợp lệ.');
 return sources.map(({owner_id,...source})=>source);
}

export async function previewRestore(backup){
 const ctx=active;await ctx.remote;await ctx.disk;sameIdentity(ctx);
 if(ctx.pending.size)throw Error('Còn bản nháp chưa đồng bộ. Tải bản sao hiện tại và xử lý đồng bộ trước khi khôi phục.');
 const body=JSON.stringify(backup);
 let response,result;
 try{
  response=await fetch('/api/workspace/restore/preview',{method:'POST',headers:{...workspaceHeaders(ctx),'Content-Type':'application/json'},body});
  result=await response.json();
 }catch{
  sameIdentity(ctx);
  throw Error('Chưa nhận được phản hồi hợp lệ khi kiểm bản sao. Kiểm tra kết nối rồi thử lại. Bản nháp vẫn được giữ.');
 }
 sameIdentity(ctx);
 if(!response.ok)throw Error(result?.error||'Chưa kiểm được bản sao.');
 if(result.revision!==ctx.revision)throw Error('Kho đã đổi ở cửa sổ khác. Tải lại trước khi khôi phục.');
 return result;
}

export async function restoreBackup(backup,revision){
 const ctx=active;if(ctx.restoring)throw Error('Đang khôi phục kho.');ctx.restoring=true;
 try{
  await ctx.remote;await ctx.disk;sameIdentity(ctx);
  if(ctx.pending.size||ctx.revision!==revision)throw Error('Bản nháp/kho đã đổi sau khi xem trước. Đồng bộ và mở lại bản sao.');
  let response,result;
  try{
   response=await fetch('/api/workspace/restore',{method:'POST',headers:{...workspaceHeaders(ctx),'Content-Type':'application/json','If-Match':String(revision)},body:JSON.stringify(backup)});
   result=await response.json();
  }catch{
   sameIdentity(ctx);
   throw Error('Chưa xác định được kết quả khôi phục. Khi có mạng, tải lại trang và kiểm tra kho trước khi thử lại.');
  }
  sameIdentity(ctx);
  if(!response.ok)throw Error(result.error||'Chưa khôi phục được dữ liệu.');
  ctx.revision=result.revision;
  try{
   await disk(ctx,async()=>{
    const database=await dbp;
    await new Promise((resolve,reject)=>{
     const tx=database.transaction('kv','readwrite'),store=tx.objectStore('kv');
     for(const [key,value]of [['state',backup.state],...Object.entries(backup.files||{}).map(([id,value])=>['file:'+id,value])]){
      store.put(value,ctx.id+':'+key);store.put(null,ctx.id+':__pending:'+key);
     }
     tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('Chưa lưu được cache.'));
    });
   });
  }catch{result.cacheWarning='Kho đã khôi phục trên máy chủ; tải lại khi còn kết nối để cập nhật bộ nhớ trình duyệt.';}
  return result;
 }finally{ctx.restoring=false;}
}
