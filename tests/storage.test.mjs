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

test('Nháp offline phát hiện lệch revision khi online lại vẫn giữ trạng thái xung đột sau khi tải lại offline',async()=>{
 const h=await harness();try{
  let serverRev=1;
  globalThis.fetch=async(url,options)=>{
   if(!options?.body)return {ok:true,status:200,json:async()=>({value:{title:'Ban đầu'},revision:serverRev})};
   return {ok:false,status:503,json:async()=>({error:'Mất mạng'})};
  };
  await h.storage.get('state');
  await assert.rejects(h.storage.put('state',{title:'Nháp sửa offline'}));
  assert.equal(h.storage.hasStateConflict(),false);

  // Tab khác đẩy revision trên máy chủ lên 2; tab này tải lại khi có mạng -> ghi nhận conflict vào IndexedDB.
  serverRev=2;
  const onlineReload=await h.open(h.session);
  const loaded=await onlineReload.storage.get('state');
  assert.deepEqual(loaded,{title:'Nháp sửa offline'});
  assert.equal(onlineReload.storage.hasStateConflict(),true);
  assert.equal(h.data.get(h.pendingKey()).conflict,true);

  // Tải lại tiếp khi ngoại tuyến: vẫn giữ nháp và cờ conflict để người dùng không vô tình ghi đè.
  globalThis.fetch=async()=>{throw Error('Mất mạng');};
  const offlineReload=await h.open(h.session);
  const offlineState=await offlineReload.storage.get('state');
  assert.deepEqual(offlineState,{title:'Nháp sửa offline'});
  assert.equal(offlineReload.storage.hasStateConflict(),true);
 }finally{h.restore();}
});

test('retryPendingWrites không bỏ sót file audio đang chờ khi state gặp HTTP 409',async()=>{
 const h=await harness();try{
  await h.storage.get('state');
  h.responses.push(()=>{throw Error('Mất mạng');});
  await assert.rejects(h.storage.put('state',{title:'Nháp lệch revision'}));
  h.responses.push(()=>{throw Error('Mất mạng');});
  await assert.rejects(h.storage.put('file:aud_1','data:audio/wav;base64,UklGRg=='));

  globalThis.fetch=async(url,options)=>{
   const body=JSON.parse(options.body);
   h.writes.push({body,headers:options.headers});
   if(body.key==='state')return {ok:false,status:409,json:async()=>({error:'Đề đã đổi ở nơi khác.',code:'stale_snapshot'})};
   return {ok:true,status:200,json:async()=>({revision:5})};
  };
  await assert.rejects(h.storage.retryPendingWrites(),/đã đổi/);
  assert.ok(h.writes.some(w=>w.body.key==='file:aud_1'&&w.body.value==='data:audio/wav;base64,UklGRg=='));
  assert.equal(h.data.has(h.pendingKey('local','file:aud_1')),false);
  assert.equal(h.data.get(h.pendingKey()).conflict,true);
 }finally{h.restore();}
});

test('Web Locks bị từ chối sau HTTP 409 vẫn giữ nguyên tabId và mở nháp IndexedDB khi reload',async()=>{
 const h=await harness();
 const prevWindow=globalThis.window;
 try{
  let serverRev=1,serverState={title:'Bản máy chủ mới'};
  globalThis.fetch=async(url,options)=>{
   if(!options?.body)return {ok:true,status:200,json:async()=>({value:structuredClone(serverState),revision:serverRev})};
   return {ok:false,status:409,json:async()=>({error:'Đề trên máy chủ đã đổi.',code:'stale_snapshot'})};
  };
  globalThis.window={navigator:{locks:{request:()=>Promise.reject(Error('Lock rejected'))}}};
  h.session.set('mach-storage-tab','tab-409-id');
  const tab=await h.open(h.session);
  await tab.storage.get('state');
  const draft={title:'Nháp 409 cần giữ'};
  await assert.rejects(tab.storage.put('state',draft),/đã đổi/);
  assert.equal(h.session.get('mach-storage-tab'),'tab-409-id');
  assert.equal(h.data.get(tab.pendingKey()).conflict,true);

  serverRev=2;
  serverState={title:'Bản máy chủ sau reload'};
  const reloaded=await h.open(h.session);
  const loaded=await reloaded.storage.get('state');
  assert.equal(h.session.get('mach-storage-tab'),'tab-409-id');
  assert.deepEqual(loaded,draft);
  assert.equal(reloaded.storage.hasStateConflict(),true);
  assert.equal(reloaded.storage.hasPendingWrites(),true);
 }finally{
  if(prevWindow===undefined)delete globalThis.window;else globalThis.window=prevWindow;
  h.restore();
 }
});

test('Web Locks báo khóa đang bận (nhân bản tab) phải cấp tabId mới và không đọc nhầm nháp tab nguồn',async()=>{
 const h=await harness();
 const prevWindow=globalThis.window;
 try{
  const held=new Set(['mach-storage-tab:source-tab-id']);
  globalThis.window={navigator:{locks:{request:(name,_opts,cb)=>{
   if(held.has(name))return Promise.resolve(cb(null));
   held.add(name);
   return Promise.resolve(cb({name}));
  }}}};
  h.data.set('local:__pending:source-tab-id:state',{id:crypto.randomUUID(),base:1,conflict:true,value:{title:'Nháp tab nguồn'}});
  h.session.set('mach-storage-tab','source-tab-id');
  const duplicated=await h.open(h.session);
  const loaded=await duplicated.storage.get('state');
  assert.notEqual(h.session.get('mach-storage-tab'),'source-tab-id');
  assert.deepEqual(loaded,{title:'Ban đầu'});
  assert.equal(duplicated.storage.hasPendingWrites(),false);
 }finally{
  if(prevWindow===undefined)delete globalThis.window;else globalThis.window=prevWindow;
  h.restore();
 }
});

test('allQuestionBank tiếp tục phân trang khi total là null hoặc rỗng và hasMore=true',async()=>{
 const h=await harness();try{
  const pages=[
   {items:[{id:'q1',owner_id:'u1',stem:'Câu 1'}],total:null,hasMore:true},
   {items:[{id:'q2',owner_id:'u1',stem:'Câu 2'}],total:'',hasMore:true},
   {items:[{id:'q3',owner_id:'u1',stem:'Câu 3'}],hasMore:false},
  ];
  let idx=0;
  globalThis.fetch=async()=>({ok:true,status:200,json:async()=>pages[idx++]});
  const items=await h.storage.allQuestionBank();
  assert.deepEqual(items,[{id:'q1',stem:'Câu 1'},{id:'q2',stem:'Câu 2'},{id:'q3',stem:'Câu 3'}]);
 }finally{h.restore();}
});

test('restoreBackup giữ UUID, công thức, richDoc, audio và không ghi đè state thành undefined ở chế độ ghép lô',async()=>{
 const h=await harness();try{
  const examUuid='7c1d6d46-9b34-4c86-a47d-1234567890ab';
  const richDoc={type:'doc',attrs:{id:'doc-1'},content:[{type:'math_inline',attrs:{latex:'\\frac{a}{b}'}}]};
  const fullState={
   current:examUuid,
   exams:[{
    id:examUuid,
    title:'Đề khôi phục đầy đủ',
    audio:{fileId:'aud_exam',filename:'nghe.wav',mimeType:'audio/wav'},
    questions:[{id:'q-1',stem:'Tính $\\frac{1}{2}$',richDoc,formulas:['\\frac{1}{2}'],audio:{fileId:'aud_q1',mimeType:'audio/mpeg'}}],
   }],
  };
  const files={aud_exam:'data:audio/wav;base64,UklGRg==',aud_q1:'data:audio/mpeg;base64,SUQzAw=='};
  globalThis.fetch=async(url,options)=>{
   if(String(url)==='/api/workspace/restore')return {ok:true,status:200,json:async()=>({revision:3,restoredExams:1})};
   if(String(url).startsWith('/api/kv?key=state')){
    if(options?.body)return {ok:true,status:200,json:async()=>({revision:1})};
    return {ok:true,status:200,json:async()=>({value:{current:examUuid,exams:[]},revision:1})};
   }
   return {ok:true,status:200,json:async()=>({value:null,revision:0})};
  };
  await h.storage.get('state');
  const fullRes=await h.storage.restoreBackup({format:'tro-ly-soan-de-backup',state:fullState,files},1);
  assert.equal(fullRes.revision,3);
  assert.equal(h.data.get('local:state').current,examUuid);
  assert.deepEqual(h.data.get('local:state').exams[0].questions[0].richDoc,richDoc);
  assert.equal(h.data.get('local:file:aud_exam'),files.aud_exam);
  assert.equal(h.data.get('local:file:aud_q1'),files.aud_q1);

  // Batch restore (format tro-ly-soan-de-batch) không có backup.state -> lấy state đã ghép từ server, không ghi undefined vào cache.
  const incomingExam={id:'8a2e1111-1111-4111-8111-111111111111',title:'Đề ghép thêm',audio:fullState.exams[0].audio};
  const remapped='aud_exam-moi';
  const mergedExam={...incomingExam,audio:{...incomingExam.audio,fileId:remapped}};
  const mergedServerState={...fullState,exams:[...fullState.exams,mergedExam]};
  globalThis.fetch=async(url)=>{
   if(String(url)==='/api/workspace/restore')return {ok:true,status:200,json:async()=>({revision:4,state:mergedServerState,importedExams:1,fileRemap:{aud_exam:remapped},normalizedFileTypes:{aud_exam:'audio/wav'}})};
   throw Error('Mất mạng sau khi ghép đề');
  };
  const batchRes=await h.storage.restoreBackup({format:'tro-ly-soan-de-batch',exams:[incomingExam],files:{aud_exam:'data:application/octet-stream;base64,UklG RgE='}},3);
  assert.equal(batchRes.revision,4);
  assert.equal(batchRes.cacheWarning,undefined);
  globalThis.fetch=async()=>{throw Error('Mất mạng');};
  const {storage:reloaded}=await h.open(h.session);
  assert.deepEqual(await reloaded.get('state'),mergedServerState);
  assert.equal(await reloaded.get('file:aud_exam'),files.aud_exam);
  assert.equal(await reloaded.get('file:'+remapped),'data:audio/wav;base64,UklGRgE=');
 }finally{h.restore();}
});

test('restoreBackup toàn kho chuẩn hóa MIME WAV từ normalizedFileTypes vào IndexedDB để đọc ngoại tuyến sau reload',async()=>{
 const h=await harness();try{
  const examUuid='9b2f7d10-4c21-4f3a-9d55-1234567890cd';
  const fullState={
   current:examUuid,
   exams:[{
    id:examUuid,
    title:'Đề khôi phục toàn kho có WAV MIME chung',
    audio:{fileId:'aud_full',filename:'nghe.wav',mimeType:'audio/wav'},
    questions:[],
   }],
   prefs:[],
  };
  const rawGenericWav='data:application/octet-stream;base64,UklG RgE=';
  globalThis.fetch=async(url)=>{
   if(String(url)==='/api/workspace/restore'){
    return {ok:true,status:200,json:async()=>({revision:2,restored:true,normalizedFileTypes:{aud_full:'audio/wav'}})};
   }
   return {ok:true,status:200,json:async()=>({value:{current:null,exams:[],prefs:[]},revision:1})};
  };
  await h.storage.get('state');
  const res=await h.storage.restoreBackup({format:'tro-ly-soan-de',version:1,state:fullState,files:{aud_full:rawGenericWav}},1);
  assert.equal(res.revision,2);
  assert.equal(res.cacheWarning,undefined);
  globalThis.fetch=async()=>{throw Error('Mất mạng');};
  const {storage:reloaded}=await h.open(h.session);
  const cachedWav=await reloaded.get('file:aud_full');
  assert.equal(cachedWav,'data:audio/wav;base64,UklGRgE=');
  assert.ok(cachedWav.startsWith('data:audio/'));
 }finally{h.restore();}
});

test('sharing.js ẩn đáp án khi sao cộng đồng, bảo toàn render khi HTTP 409 và chuẩn nút cảm ứng mobile',async()=>{
 const h=await harness();
 const prevDoc=globalThis.document;
 try{
  const modals=[];
  let viewMode='home',rendered=0;
  const formMock={querySelector:()=>({}),elements:{}};
  const prevBtn={disabled:false},nextBtn={disabled:false};
  const statusEl={textContent:''},resultsEl={innerHTML:'',textContent:''};
  const filterForm={
   isConnected:true,
   dataset:{},
   elements:{},
   addEventListener(){},
   querySelector(sel){
    if(sel==='[data-community-results]')return resultsEl;
    if(sel==='[data-community-status]')return statusEl;
    if(sel==='[data-community-page=prev]')return prevBtn;
    if(sel==='[data-community-page=next]')return nextBtn;
    return formMock;
   },
  };
  const dialog={
   open:true,
   close(){this.open=false;},
   querySelector(sel){
    if(sel==='#assistant-source-form')return null;
    if(sel==='#community-filter')return filterForm;
    if(sel==='#share-form')return filterForm;
    return null;
   },
  };
  globalThis.document={
   documentElement:{style:{}},
   body:{style:{}},
   createElement:()=>({style:{},setAttribute(){},appendChild(){},addEventListener(){}}),
   querySelector(sel){
    if(sel==='#dialog')return dialog;
    if(sel==='#share-form')return filterForm;
    return null;
   },
  };
  const prevFormData=globalThis.FormData;
  globalThis.FormData=class{entries(){return [];}[Symbol.iterator](){return [][Symbol.iterator]();}};
  try{
   const {openSharing,openCommunity,cloneCommunityExam}=await import('../sharing.js?test='+crypto.randomUUID());
   const state={exams:[{id:'old-1',title:'Đề gốc',revision:2,questions:[]}],current:'old-1'};
   const ctx={
    exam:()=>state.exams.find(e=>e.id===state.current),
    getState:()=>state,
    getViewMode:()=>viewMode,
    setViewMode:m=>{viewMode=m;},
    modal:(title,body)=>{modals.push({title,body});},
    persist:async()=>{throw Error('HTTP 409 Conflict');},
    render:()=>{rendered+=1;},
    toast:()=>{},
   };
   await openSharing(ctx,async()=>({shares:[{revision:2,answers:false,community:false,created:Date.now(),url:'http://localhost/s/abc',token:'abc'}]}),{sharedSnapshots:true});
   assert.ok(modals[0].body.includes('min-height:40px'));
   assert.ok(modals[0].body.includes('flex-wrap:wrap'));

   let communityCalls=0;
   await openCommunity(ctx,async()=>{
    communityCalls+=1;
    if(communityCalls===1)return {page:2,hasMore:false,exams:[{token:'tok1',title:'Đề cộng đồng',subject:'Toán',grade:'6',questions:2,allowCopy:true}]};
    throw Error('Mất kết nối');
   });
   assert.ok(resultsEl.innerHTML.includes('min-height:40px'));
   assert.ok(resultsEl.innerHTML.includes('Xem đề'));
   assert.ok(resultsEl.innerHTML.includes('Sao về kho của tôi'));
   await nextBtn.onclick();
   assert.equal(statusEl.textContent,'Mất kết nối');
   assert.equal(prevBtn.disabled,false);

   const btn={dataset:{token:'tok1'},disabled:false};
   await assert.rejects(cloneCommunityExam(ctx,async()=>({
    answersIncluded:false,
    clonedExam:{id:'new-uuid-2',title:'Đề đã sao',questions:[{id:'q1',type:'choice',stem:'1+1=?',options:['1','2'],answer:1,answerKnown:true}]},
   }),btn),/409/);
   assert.equal(btn.disabled,false);
   assert.equal(viewMode,'workspace');
   assert.equal(rendered,1);
   const cloned=state.exams.find(e=>e.id==='new-uuid-2');
   assert.equal(cloned.questions[0].answer,null);
   assert.equal(cloned.questions[0].answerKnown,false);
  }finally{
   globalThis.FormData=prevFormData;
  }
 }finally{
  if(prevDoc===undefined)delete globalThis.document;else globalThis.document=prevDoc;
  h.restore();
 }
});
