import test from 'node:test';
import assert from 'node:assert/strict';

// Mô phỏng callback/transaction IndexedDB, không thay logic storage cần kiểm.
function testBrowser(){
 const data=new Map(),previous={indexedDB:globalThis.indexedDB,fetch:globalThis.fetch,sessionStorage:globalThis.sessionStorage};
 function transaction(){
  let remaining=0;
  const enqueue=callback=>{
   remaining++;
   queueMicrotask(()=>{callback();if(--remaining===0)tx.oncomplete?.();});
  };
  const store={
   get(key){const r={};enqueue(()=>{r.result=structuredClone(data.get(key));r.onsuccess?.();});return r;},
   put(value,key){const copy=structuredClone(value);enqueue(()=>data.set(key,copy));},
   delete(key){enqueue(()=>data.delete(key));},
  };
  const tx={objectStore:()=>store};
  return tx;
 }
 globalThis.indexedDB={open(){const request={};queueMicrotask(()=>{request.result={transaction};request.onsuccess?.();});return request;}};
 async function open(session=new Map()){
  globalThis.sessionStorage={getItem:key=>session.get(key),setItem:(key,value)=>session.set(key,value)};
  const storage=await import('../storage.js?test='+crypto.randomUUID());
  return {storage,session,pendingKey:(id='local',key='state')=>id+':__pending:'+session.get('mach-storage-tab')+':'+key};
 }
 return {data,open,restore(){Object.assign(globalThis,previous);}};
}
async function harness(){
 const browser=testBrowser(),tab=await browser.open();
 const responses=[],writes=[];
 globalThis.fetch=async(url,options)=>{
  if(!options?.body)return {ok:true,status:200,json:async()=>({value:{title:'Ban đầu'},revision:1})};
  const body=JSON.parse(options.body);writes.push({body,headers:options.headers});
  if(responses.length)return responses.shift()(body,options);
  return {ok:true,status:200,json:async()=>({revision:writes.length+1})};
 };
 return {...browser,...tab,responses,writes};
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

test('Các lần lưu chồng nhau phải tuần tự, dùng revision mới và không mất bản mới nhất',async()=>{
 const h=await harness();try{
  await h.storage.get('state');let release;
  h.responses.push(()=>new Promise(resolve=>{release=()=>resolve({ok:true,status:200,json:async()=>({revision:2})});}));
  const first=h.storage.put('state',{title:'Bản A'});
  await new Promise(resolve=>setImmediate(resolve));
  const second=h.storage.put('state',{title:'Bản B'});
  const third=h.storage.put('state',{title:'Bản C'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(h.writes.length,1);
  assert.deepEqual(h.data.get(h.pendingKey()).value,{title:'Bản C'});
  release();await Promise.all([first,second,third]);
  assert.deepEqual(h.writes.map(write=>write.headers['If-Match']),['1','2','3']);
  assert.equal(h.storage.hasPendingWrites(),false);
  assert.deepEqual(h.data.get('local:state'),{title:'Bản C'});
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
  assert.equal(h.data.get(h.pendingKey('team:nguoi-a')).value.title,'Nháp A');
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
  assert.deepEqual(h.data.get(h.pendingKey()).value,{title:'Bản cần khôi phục'});
 }finally{h.restore();}
});

test('Đọc bản nháp IndexedDB từ phiên bản cũ và giữ lại khi tải lại tab',async()=>{
 const h=await harness();try{
  const legacy={id:crypto.randomUUID(),base:1,conflict:true,value:{title:'Bản nháp cũ'}};
  h.data.set('local:__pending:state',legacy);
  globalThis.fetch=async()=>{throw Error('Mất mạng');};
  assert.deepEqual(await h.storage.get('state'),legacy.value);
  assert.equal(h.storage.hasStateConflict(),true);
  assert.deepEqual(h.data.get(h.pendingKey()),legacy);
  assert.equal(h.data.has('local:__pending:state'),false);
  const reloaded=await h.open(h.session);
  assert.deepEqual(await reloaded.storage.get('state'),legacy.value);
  assert.equal(reloaded.storage.hasStateConflict(),true);
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
   assert.deepEqual(h.data.get(h.pendingKey()).value,draft);
   assert.equal(h.data.get(h.pendingKey()).base,1);
   assert.deepEqual(h.data.get('local:state'),{title:'Ban đầu'});
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
  assert.deepEqual(h.data.get(h.pendingKey()).value,draft);
  assert.equal(h.data.get(h.pendingKey()).base,1);
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

test('Hai tab lưu chồng: B giữ nháp 409 khi chưa có phản hồi của A và sau khi cả hai tải lại',async()=>{
 const browser=testBrowser(),{data}=browser;
 let serverRev=10,serverState={title:'Gốc'};
 let receiveA,releaseA;
 const acceptedA=new Promise(resolve=>{receiveA=resolve;});
 globalThis.fetch=async(url,options)=>{
  if(!options?.body)return {ok:true,status:200,json:async()=>({value:structuredClone(serverState),revision:serverRev})};
  const body=JSON.parse(options.body);
  const ifMatch=Number(options.headers['If-Match']);
  if(ifMatch!==serverRev){
   return {ok:false,status:409,json:async()=>({error:'Đề trên máy chủ đã đổi.',code:'stale_snapshot'})};
  }
  serverRev+=1;
  serverState=structuredClone(body.value);
  const revision=serverRev;
  if(body.value.title==='A lưu 1')await new Promise(resolve=>{releaseA=resolve;receiveA();});
  return {ok:true,status:200,json:async()=>({revision})};
 };
 try{
  const a=await browser.open();
  await a.storage.get('state');
  const b=await browser.open();
  await b.storage.get('state');
  const savingA=a.storage.put('state',{title:'A lưu 1'});
  await acceptedA;
  assert.equal(serverRev,11);
  const draftB={title:'Nháp B'};
  await assert.rejects(b.storage.put('state',draftB),/đã đổi/);
  assert.equal(b.storage.hasStateConflict(),true);
  assert.deepEqual(data.get(b.pendingKey()).value,draftB);
  assert.equal(data.get(b.pendingKey()).conflict,true);
  releaseA();await savingA;
  await a.storage.put('state',{title:'A lưu 2'});
  assert.equal(serverRev,12);
  assert.equal(data.has(a.pendingKey()),false);
  assert.deepEqual(data.get(b.pendingKey()).value,draftB);
  const reloadedA=await browser.open(a.session);
  assert.deepEqual(await reloadedA.storage.get('state'),{title:'A lưu 2'});
  assert.equal(reloadedA.storage.hasPendingWrites(),false);
  const reloadedB=await browser.open(b.session);
  assert.deepEqual(await reloadedB.storage.get('state'),draftB);
  assert.equal(reloadedB.storage.hasStateConflict(),true);
  assert.equal(reloadedB.storage.hasPendingWrites(),true);
 }finally{
  releaseA?.();
  browser.restore();
 }
});

test('Phản hồi lưu đến muộn không hạ phiên bản cache của tab khác',async()=>{
 const h=await harness();try{
  await h.storage.get('state');
  let release;
  const accepted=new Promise(resolve=>{
   h.responses.push(()=>new Promise(respond=>{
    release=()=>respond({ok:true,status:200,json:async()=>({revision:2})});
    resolve();
   }));
  });
  const saving=h.storage.put('state',{title:'A đã lưu'});
  await accepted;
  const b=await h.open(),fetchWrites=globalThis.fetch;
  globalThis.fetch=(url,options)=>options?.body?fetchWrites(url,options):
   Promise.resolve({ok:true,status:200,json:async()=>({value:{title:'A đã lưu'},revision:2})});
  await b.storage.get('state');
  await b.storage.put('state',{title:'B đã lưu sau A'});
  release();await saving;
  assert.deepEqual(h.data.get('local:state'),{title:'B đã lưu sau A'});
 }finally{h.restore();}
});
