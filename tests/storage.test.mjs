import test from 'node:test';
import assert from 'node:assert/strict';

// Mô phỏng callback/transaction IndexedDB, không thay logic storage cần kiểm.
async function harness(){
 const data=new Map(),previous={indexedDB:globalThis.indexedDB,fetch:globalThis.fetch};
 globalThis.indexedDB={open(){const request={};queueMicrotask(()=>{request.result={transaction(){const tx={objectStore(){return {get(key){const r={};queueMicrotask(()=>{r.result=structuredClone(data.get(key));r.onsuccess?.();});return r;},put(value,key){data.set(key,structuredClone(value));queueMicrotask(()=>tx.oncomplete?.());}};}};return tx;}};request.onsuccess?.();});return request;}};
 const responses=[],writes=[];
 globalThis.fetch=async(url,options)=>{
  if(!options?.body)return {ok:true,status:200,json:async()=>({value:{title:'Ban đầu'},revision:1})};
  const body=JSON.parse(options.body);writes.push({body,headers:options.headers});
  if(responses.length)return responses.shift()(body,options);
  return {ok:true,status:200,json:async()=>({revision:writes.length+1})};
 };
 const storage=await import('../storage.js?test='+crypto.randomUUID());
 return {storage,data,responses,writes,restore(){globalThis.indexedDB=previous.indexedDB;globalThis.fetch=previous.fetch;}};
}

test('Đổi tài khoản không đồng bộ nháp offline của người trước sang tài khoản mới',async()=>{
 const h=await harness();try{
  h.storage.setIdentity('nguoi-a');await h.storage.get('state');
  h.responses.push(()=>{throw Error('Mất mạng');});
  await assert.rejects(h.storage.put('state',{title:'Nháp riêng của A'}));
  assert(h.storage.hasPendingWrites());h.storage.setIdentity('nguoi-b');
  assert.equal(h.storage.hasPendingWrites(),false);
  await h.storage.retryPendingWrites();assert.equal(h.writes.length,1);
  h.storage.setIdentity('nguoi-a');assert(h.storage.hasPendingWrites());
  await h.storage.retryPendingWrites();assert.equal(h.writes.length,2);
 }finally{h.restore();}
});

test('Hai lần lưu chồng nhau phải tuần tự, dùng revision mới và không mất bản mới nhất',async()=>{
 const h=await harness();try{
  await h.storage.get('state');let release;
  h.responses.push(()=>new Promise(resolve=>{release=()=>resolve({ok:true,status:200,json:async()=>({revision:2})});}));
  const first=h.storage.put('state',{title:'Bản A'});
  await new Promise(resolve=>setImmediate(resolve));
  const second=h.storage.put('state',{title:'Bản B'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(h.writes.length,1);
  assert.deepEqual(h.data.get('local:__pending:state').value,{title:'Bản B'});
  release();await first;await second;
  assert.equal(h.writes[1].headers['If-Match'],'2');
  assert.equal(h.storage.hasPendingWrites(),false);
  assert.deepEqual(h.data.get('local:state'),{title:'Bản B'});
 }finally{h.restore();}
});

test('Hết phiên rõ ràng 401 không được coi là mất mạng để mở cache riêng',async()=>{
 const h=await harness();try{
  h.storage.setIdentity('nguoi-a');await h.storage.get('state');
  globalThis.fetch=async()=>({ok:false,status:401,json:async()=>({error:'Phiên hết hạn'})});
  await assert.rejects(h.storage.get('state'),/đăng nhập|phiên/i);
 }finally{h.restore();}
});

test('Tab kho nhóm ràng buộc các yêu cầu với tài khoản đã mở và giữ nháp khi phiên đổi',async()=>{
 const h=await harness();try{
  h.storage.setIdentity('team:nguoi-a');
  const fetchDefault=globalThis.fetch, requests=[];
  globalThis.fetch=async(url,options)=>{requests.push({url,headers:options.headers});return fetchDefault(url,options);};
  await h.storage.get('state');
  const backup={state:{title:'Bản sao A'}};
  h.responses.push(()=>({ok:true,status:200,json:async()=>({revision:1})}));
  await h.storage.previewRestore(backup);
  await h.storage.restoreBackup(backup,1);
  h.responses.push(()=>({ok:false,status:409,json:async()=>({error:'Tài khoản đã đổi ở tab khác.'})}));
  await assert.rejects(h.storage.put('state',{title:'Nháp A'}),/Tài khoản đã đổi/);
  assert.deepEqual(requests.map(({url})=>url),['/api/kv?key=state','/api/workspace/restore/preview','/api/workspace/restore','/api/kv']);
  assert(requests.every(({headers})=>headers['X-Workspace-Context']==='team:nguoi-a'));
  assert.equal(h.data.get('team:nguoi-a:__pending:state').value.title,'Nháp A');
 }finally{h.restore();}
});

test('Conflict giữ bản mới offline và không ghi đè server khi tự retry',async()=>{
 const h=await harness();try{
  await h.storage.get('state');
  const conflict=()=>({ok:false,status:409,json:async()=>({error:'Đề đã đổi ở cửa sổ khác',code:'stale_snapshot'})});
  h.responses.push(conflict,conflict);
  await assert.rejects(h.storage.put('state',{title:'Bản cần khôi phục'}),/cửa sổ khác/);
  await assert.rejects(h.storage.retryPendingWrites(),/cửa sổ khác/);
  assert(h.storage.hasPendingWrites());
  assert.equal(h.writes[1].headers['If-Match'],'1');
  assert(h.storage.hasStateConflict());
  assert.deepEqual(h.data.get('local:__pending:state').value,{title:'Bản cần khôi phục'});
 }finally{h.restore();}
});

test('Lượt lưu cũ đã xong không xóa bản nháp mới ghi từ tab khác',async()=>{
 const h=await harness();try{
  await h.storage.get('state');
  let release;
  h.responses.push(()=>new Promise(resolve=>{release=()=>resolve({ok:true,status:200,json:async()=>({revision:2})});}));
  const oldSave=h.storage.put('state',{title:'Bản lưu cũ'});
  await new Promise(resolve=>setImmediate(resolve));
  const newer={id:crypto.randomUUID(),base:1,value:{title:'Bản nháp ở tab khác'}};
  h.data.set('local:__pending:state',newer);
  release();
  await oldSave;
  assert.deepEqual(h.data.get('local:__pending:state'),newer);
 }finally{h.restore();}
});

test('Hai sự kiện kết nối lại không gửi lặp cùng bản nháp đang chờ xác nhận',async()=>{
 const h=await harness();try{
  await h.storage.get('state');let release;
  h.responses.push(()=>new Promise(resolve=>{release=()=>resolve({ok:true,status:200,json:async()=>({revision:2})});}));
  const save=h.storage.put('state',{title:'Nháp'});
  await new Promise(resolve=>setImmediate(resolve));
  const retry1=h.storage.retryPendingWrites(),retry2=h.storage.retryPendingWrites();
  release();await Promise.all([save,retry1,retry2]);
  assert.equal(h.writes.length,1);assert(!h.storage.hasPendingWrites());
 }finally{h.restore();}
});

test('Đổi tài khoản khi đang đọc không trả dữ liệu tài khoản trước vào màn hình mới',async()=>{
 const h=await harness();try{
  let release;h.storage.setIdentity('nguoi-a');
  globalThis.fetch=()=>new Promise(resolve=>{release=()=>resolve({ok:true,status:200,json:async()=>({value:{secret:'A'},revision:1})});});
  const reading=h.storage.get('state');
  await new Promise(resolve=>setImmediate(resolve));h.storage.setIdentity('nguoi-b');release();
  await assert.rejects(reading,/Tài khoản đã đổi/);
  assert(!h.data.has('nguoi-b:state'));
 }finally{h.restore();}
});

for(const [scenario,failPreview] of [
 ['Mất phản hồi mạng',()=>{throw Error('Failed to fetch');}],
 ['JSON lỗi',()=>({ok:false,status:502,json:async()=>{throw new SyntaxError('Invalid JSON');}})],
]){
 test(`${scenario} khi xem trước báo lỗi rõ ràng và giữ nháp phát sinh trong lúc chờ`,async()=>{
  const h=await harness();try{
   await h.storage.get('state');
   const backup={state:{title:'Bản sao thử'}},draft={title:'Nháp mới'};
   let finishPreview;
   const previewStarted=new Promise(resolve=>{
    h.responses.push(()=>new Promise((respond,reject)=>{
     finishPreview=()=>Promise.resolve().then(failPreview).then(respond,reject);
     resolve();
    }));
   });
   const preview=assert.rejects(h.storage.previewRestore(backup),/Chưa nhận được phản hồi hợp lệ khi kiểm bản sao.*Kiểm tra kết nối.*Bản nháp vẫn được giữ/);
   await previewStarted;
   h.responses.push(()=>{throw Error('Chưa lưu được nháp');});
   await assert.rejects(h.storage.put('state',draft),/Chưa lưu được nháp/);
   finishPreview();
   await preview;
   assert(h.storage.hasPendingWrites());
   assert.deepEqual(h.data.get('local:__pending:state').value,draft);
  assert.equal(h.data.get('local:__pending:state').base,1);
   assert.deepEqual(h.data.get('local:state'),draft);
   assert.equal(h.writes.length,2);
   await h.storage.retryPendingWrites();
   assert.equal(h.writes.length,3);
   assert.deepEqual(h.writes[2].body,{key:'state',value:draft});
   assert.equal(h.writes[2].headers['If-Match'],'1');
   assert.equal(h.storage.hasPendingWrites(),false);
  }finally{h.restore();}
 });
}

test('Nháp đang chờ đồng bộ chặn yêu cầu xem trước và vẫn còn trong hàng đợi',async()=>{
 const h=await harness();try{
  await h.storage.get('state');
  const draft={title:'Nháp chưa đồng bộ'};
  h.responses.push(()=>{throw Error('Mất mạng');});
  await assert.rejects(h.storage.put('state',draft),/Mất mạng/);
  await assert.rejects(h.storage.previewRestore({state:{title:'Bản sao thử'}}),/Còn bản nháp chưa đồng bộ/);
  assert.equal(h.writes.length,1);
  assert(h.storage.hasPendingWrites());
  assert.deepEqual(h.data.get('local:__pending:state').value,draft);
  assert.equal(h.data.get('local:__pending:state').base,1);
 }finally{h.restore();}
});

test('Xem trước báo riêng khi revision của kho đã thay đổi',async()=>{
 const h=await harness();try{
  await h.storage.get('state');
  h.responses.push(()=>({ok:true,status:200,json:async()=>({revision:2})}));
  await assert.rejects(h.storage.previewRestore({state:{title:'Bản sao thử'}}),{
   message:'Kho đã đổi ở cửa sổ khác. Tải lại trước khi khôi phục.',
  });
 }finally{h.restore();}
});

test('Xem trước giữ thông báo lỗi kiểm bản sao của API',async()=>{
 const h=await harness();try{
  await h.storage.get('state');
  h.responses.push(()=>({ok:false,status:422,json:async()=>({error:'Bản sao thiếu dữ liệu.',revision:2})}));
  await assert.rejects(h.storage.previewRestore({}),{message:'Bản sao thiếu dữ liệu.'});
 }finally{h.restore();}
});

test('Mất phản hồi lúc khôi phục yêu cầu kiểm kho, giữ cache và không tự gửi lại',async()=>{
 const h=await harness();try{
  await h.storage.get('state');
  h.responses.push(()=>{throw Error('Mất phản hồi');});
  await assert.rejects(h.storage.restoreBackup({state:{title:'Bản sao thử'}},1),/Chưa xác định.*tải lại trang/);
  assert.equal(h.writes.length,1);
  assert.deepEqual(h.data.get('local:state'),{title:'Ban đầu'});
  await h.storage.retryPendingWrites();
  assert.equal(h.writes.length,1);
 }finally{h.restore();}
});

test('allQuestionBank phân trang tới hết total và trả null khi máy chủ chưa có route (404)',async()=>{
 const h=await harness();try{
  const urls=[];
  globalThis.fetch=async(url)=>{
   urls.push(url);
   if(url.includes('offset=0'))return {ok:true,status:200,json:async()=>({items:[{id:'q1',owner_id:'u1',topic:'Toán'}],total:2,hasMore:true})};
   return {ok:true,status:200,json:async()=>({items:[{id:'q2',owner_id:'u1',topic:'Văn'}],total:2,hasMore:false})};
  };
  const all=await h.storage.allQuestionBank();
  assert.deepEqual(urls,['/api/question-bank?limit=500&offset=0','/api/question-bank?limit=500&offset=1']);
  assert.equal(all.length,2);
  assert.equal(all[0].owner_id,undefined);
  globalThis.fetch=async()=>({ok:false,status:404,json:async()=>({})});
  assert.equal(await h.storage.allQuestionBank(),null);
 }finally{h.restore();}
});

test('Hai tab cùng IndexedDB: tab B gặp 409 rồi tab A lưu tiếp không làm mất nháp B khi B tải lại',async()=>{
 const data=new Map(),previous={indexedDB:globalThis.indexedDB,fetch:globalThis.fetch};
 globalThis.indexedDB={open(){const request={};queueMicrotask(()=>{request.result={transaction(){const tx={objectStore(){return {get(key){const r={};queueMicrotask(()=>{r.result=structuredClone(data.get(key));r.onsuccess?.();});return r;},put(value,key){data.set(key,structuredClone(value));queueMicrotask(()=>tx.oncomplete?.());}};}};return tx;}};request.onsuccess?.();});return request;}};
 let serverRev=10,serverState={title:'Gốc'};
 globalThis.fetch=async(url,options)=>{
  if(!options?.body)return {ok:true,status:200,json:async()=>({value:structuredClone(serverState),revision:serverRev})};
  const body=JSON.parse(options.body);
  const ifMatch=Number(options.headers['If-Match']);
  if(ifMatch!==serverRev){
   return {ok:false,status:409,json:async()=>({error:'Đề trên máy chủ đã đổi.',code:'stale_snapshot'})};
  }
  serverRev+=1;
  serverState=structuredClone(body.value);
  return {ok:true,status:200,json:async()=>({revision:serverRev})};
 };
 try{
  const tabA=await import('../storage.js?tabA='+crypto.randomUUID());
  const tabB=await import('../storage.js?tabB='+crypto.randomUUID());
  await tabA.get('state');
  await tabB.get('state');

  // 1. Tab A lưu lần 1 (rev 10 -> 11)
  await tabA.put('state',{title:'QA TAB A LUU 1'});
  assert.equal(serverRev,11);

  // 2. Tab B (base=10) lưu -> 409 stale_snapshot, nháp B lưu trong IndexedDB
  await assert.rejects(tabB.put('state',{title:'QA TAB B NHAP CHUA LUU'}),/đã đổi/);
  assert.equal(tabB.hasStateConflict(),true);
  assert.equal(data.get('local:__pending:state').value.title,'QA TAB B NHAP CHUA LUU');
  assert.equal(data.get('local:__pending:state').conflict,true);

  // 3. Tab A lưu lần 2 (rev 11 -> 12) -> KHÔNG được xóa/ghi đè nháp 409 của tab B
  await tabA.put('state',{title:'QA TAB A LUU 2'});
  assert.equal(serverRev,12);
  assert.equal(data.get('local:__pending:state').value.title,'QA TAB B NHAP CHUA LUU');
  assert.equal(data.get('local:state').title,'QA TAB B NHAP CHUA LUU');

  // 4. Tab B tải lại (context mới đọc từ IndexedDB) -> vẫn khôi phục nháp B và cờ xung đột 409
  const tabBReloaded=await import('../storage.js?tabBReload='+crypto.randomUUID());
  const loaded=await tabBReloaded.get('state');
  assert.equal(loaded.title,'QA TAB B NHAP CHUA LUU');
  assert.equal(tabBReloaded.hasStateConflict(),true);
  assert.equal(tabBReloaded.hasPendingWrites(),true);
 }finally{
  globalThis.indexedDB=previous.indexedDB;
  globalThis.fetch=previous.fetch;
 }
});
