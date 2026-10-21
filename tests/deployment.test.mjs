import test from 'node:test';import assert from 'node:assert/strict';import http from 'node:http';import {spawn} from 'node:child_process';import {DatabaseSync} from 'node:sqlite';import {once} from 'node:events';import {mkdtemp,readFile,writeFile,mkdir} from 'node:fs/promises';import path from 'node:path';import os from 'node:os';import {fileURLToPath} from 'node:url';
import {deploymentSettings} from '../deployment.mjs';import {accountService} from '../accounts.mjs';import {openStore} from '../backend-store.mjs';import {blank,uid} from '../core.js';
const invite='fixture-invite-only-24-characters',adminEmail='owner@example.test';

test('Exclusive store prevents a second connection and persists revisions without a WAL sidecar',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'mach-exclusive-')),file=path.join(dir,'workspace.sqlite');let store=openStore(dir,{exclusive:true});
 try{assert.equal(store.put('state',{title:'Bản lưu thử'},0),1);const other=new DatabaseSync(file);try{assert.throws(()=>other.prepare('SELECT * FROM kv').all(),/locked/);}finally{other.close();}assert.throws(()=>store.put('state',{title:'stale'},0),/cửa sổ khác/);}finally{store.close();}
 store=openStore(dir,{exclusive:true});try{assert.deepEqual(store.get('state').value,{title:'Bản lưu thử'});assert.equal(store.put('state',{title:'Bản tiếp theo'},1),2);}finally{store.close();}
 const inspect=new DatabaseSync(file);try{assert.equal(inspect.prepare('PRAGMA journal_mode').get().journal_mode,'delete');assert.equal(inspect.prepare('PRAGMA integrity_check').get().integrity_check,'ok');}finally{inspect.close();}
 await assert.rejects(readFile(file+'-wal'),{code:'ENOENT'});
});
test('Local mode remains loopback; online requires HTTPS, admin and a long invitation code',()=>{
 const local=deploymentSettings({PORT:'4173'});assert.equal(local.host,'127.0.0.1');assert.equal(local.online,false);assert.ok(local.allowedOrigins.has('http://localhost:4173'));
 assert.throws(()=>deploymentSettings({HOST:'0.0.0.0'}),/APP_PUBLIC_URL/);assert.throws(()=>deploymentSettings({PORT:'NaN'}),/PORT/);
 const valid={APP_PUBLIC_URL:'https://mach.example.test',APP_ADMIN_EMAIL:adminEmail,APP_SIGNUP_CODE:invite,APP_DATA_DIR:'/persistent/mach'};
 for(const value of ['http://mach.example.test','https://user:pass@mach.example.test','https://mach.example.test/path','https://mach.example.test/?key=x'])assert.throws(()=>deploymentSettings({...valid,APP_PUBLIC_URL:value}));
 assert.throws(()=>deploymentSettings({...valid,APP_ADMIN_EMAIL:''}),/APP_ADMIN_EMAIL/);assert.throws(()=>deploymentSettings({...valid,APP_SIGNUP_CODE:'short'}),/APP_SIGNUP_CODE/);
 assert.throws(()=>deploymentSettings({...valid,APP_DATA_DIR:''}),/APP_DATA_DIR/);
 const online=deploymentSettings(valid);assert.equal(online.host,'0.0.0.0');assert.equal(online.online,true);assert.deepEqual([...online.allowedOrigins],['https://mach.example.test']);
});
test('Invite-only accounts: first member is not admin, no local data is adopted, cookies secure and logout revokes the old token',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'mach-accounts-online-')),store=openStore(dir);try{
 store.put('state',{private:'LOCAL_OWNER_CONTENT'});const account=accountService(store,{online:true,adminEmail,signupCode:invite}),headers={},res={setHeader(k,v){headers[k]=v;}};
 assert.throws(()=>account.register(res,{email:'teacher@example.test',name:'Teacher',password:'fixture-password'}),/Mã mời/);
 const member=account.register(res,{email:'teacher@example.test',name:'Teacher',password:'fixture-password',inviteCode:invite});const memberReq={headers:{cookie:headers['Set-Cookie'].split(';')[0]}};
 assert.ok(headers['Set-Cookie'].includes('; Secure'));assert.equal(account.isAdmin(memberReq),false);assert.equal(store.get(account.scope(member.id,'state')),null);assert.equal(store.get('local-owner'),null);
 account.register(res,{email:adminEmail,name:'Owner',password:'fixture-password',inviteCode:invite});const adminReq={headers:{cookie:headers['Set-Cookie'].split(';')[0]}};assert.equal(account.isAdmin(adminReq),true);
 account.logout(res,memberReq);assert.equal(account.owner(memberReq),'local');assert.ok(headers['Set-Cookie'].includes('Max-Age=0; Secure'));assert.notEqual(account.owner(adminReq),'local');
 }finally{store.close();}
});
test('Online HTTP contracts: authentication, CSRF, admin config, private exports, shares, and persistence after restart',async()=>{
 const probe=http.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const dir=await mkdtemp(path.join(os.tmpdir(),'mach-online-')),root=fileURLToPath(new URL('../',import.meta.url)),publicOrigin='https://mach.example.test',base='http://127.0.0.1:'+port;
 const env={...process.env,PORT:String(port),HOST:'127.0.0.1',APP_PUBLIC_URL:publicOrigin,APP_ADMIN_EMAIL:adminEmail,APP_SIGNUP_CODE:invite,APP_DATA_DIR:dir,APP_AI_CONFIG:JSON.stringify({gemini:{model:'fixture-model',key:'server-only-fixture-secret'}})};let child,logs='';
 const request=(route,{method='GET',data,cookie,origin=publicOrigin,host='mach.example.test'}={})=>new Promise((resolve,reject)=>{const req=http.request(base+route,{method,headers:{Host:host,...(!['GET','HEAD'].includes(method)?{Origin:origin,'Content-Type':'application/json'}:{}),...(cookie?{Cookie:cookie}:{})}},res=>{const chunks=[];res.on('data',c=>chunks.push(c));res.on('end',()=>resolve(new Response(Buffer.concat(chunks),{status:res.statusCode,headers:res.headers})));});req.on('error',reject);req.end(data?JSON.stringify(data):undefined);});
 const start=async()=>{child=spawn(process.execPath,[path.join(root,'server.mjs')],{env,stdio:['ignore','pipe','pipe'],windowsHide:true});child.stdout.on('data',s=>logs+=s);child.stderr.on('data',s=>logs+=s);for(let i=0;i<100;i++){if(child.exitCode!==null)throw Error(logs);try{if((await request('/api/health')).ok)return;}catch{}await new Promise(r=>setTimeout(r,100));}throw Error('Server timeout: '+logs);};
 const stop=async()=>{if(child&&child.exitCode===null){const done=once(child,'exit');child.kill('SIGTERM');await done;}};
 try{await start();assert.equal((await request('/')).status,302);assert.equal((await request('/login')).status,200);assert.match(await(await request('/login')).text(),/registration-fields/);
 for(const route of ['/api/kv?key=state','/api/status','/api/config','/exports/anything.json'])assert.equal((await request(route)).status,401,route);
 const guest=await(await request('/api/account')).json();assert.equal(guest.user,null);assert.equal(guest.online,true);assert.equal(guest.credits,null);
 assert.equal((await request('/api/health',{host:'attacker.example'})).status,403);
 assert.equal((await request('/api/account/register',{method:'POST',origin:'https://attacker.example',data:{}})).status,403);
 const register=async(email)=>{const response=await request('/api/account/register',{method:'POST',data:{email,name:'Test teacher',password:'fixture-password',inviteCode:invite}});assert.equal(response.status,200);assert.match(response.headers.get('set-cookie'),/Secure/);return response.headers.get('set-cookie').split(';')[0];};
 const member=await register('teacher@example.test'),admin=await register(adminEmail);
 assert.equal((await request('/api/config',{method:'POST',data:{},cookie:member})).status,403);assert.equal((await request('/api/test-provider',{method:'POST',data:{provider:'api'},cookie:member})).status,403);
 const status=await(await request('/api/status',{cookie:member})).json();assert.equal(status.admin,false);assert.equal(status.config.gemini.url,'');assert.equal(status.config.gemini.hasKey,false);assert.ok(!JSON.stringify(status).includes('server-only-fixture-secret'));
 const adminStatus=await(await request('/api/status',{cookie:admin})).json();assert.equal(adminStatus.config.gemini.hasKey,true);assert.ok(!JSON.stringify(adminStatus).includes('server-only-fixture-secret'));
 assert.equal((await request('/api/config',{method:'POST',cookie:admin,data:{gemini:{model:'updated-fixture'}}})).status,200);
 const e=blank('Toán');e.questions=[{id:uid(),v:1,type:'essay',stem:'Giải phương trình $x+1=2$.',points:1,options:[],answer:0,explanation:'PRIVATE_TEACHER_SOLUTION',rubric:[{text:'Kết luận $x=1$.',points:1}]}];
 assert.equal((await request('/api/kv',{method:'PUT',cookie:member,data:{key:'state',value:{version:1,current:e.id,exams:[e],prefs:[]}}})).status,200);
 assert.equal((await(await request('/api/kv?key=state',{cookie:admin})).json()).value,null);
 const exported=await(await request('/api/save-export',{method:'POST',cookie:member,data:{type:'backup',backup:{format:'tro-ly-soan-de',content:'MEMBER_PRIVATE_EXPORT'}}})).json();assert.ok(exported.url);assert.equal((await request(exported.url,{cookie:admin})).status,403);assert.equal((await request(exported.url)).status,401);assert.match(await(await request(exported.url,{cookie:member})).text(),/MEMBER_PRIVATE_EXPORT/);assert.ok((await readFile(path.join(dir,'exports',exported.filename),'utf8')).includes('MEMBER_PRIVATE_EXPORT'));
 await mkdir(path.join(dir,'exports'),{recursive:true});await writeFile(path.join(dir,'exports','orphan.txt'),'ORPHAN_PRIVATE');assert.equal((await request('/exports/orphan.txt',{cookie:member})).status,403);
 const share=await(await request('/api/share',{method:'POST',cookie:member,data:{examId:e.id,answers:false,allowCopy:true}})).json();assert.ok(share.url.startsWith(publicOrigin+'/s/'));assert.equal(share.localOnly,false);const shared=await request(new URL(share.url).pathname);assert.equal(shared.status,200);assert.ok(!(await shared.text()).includes('PRIVATE_TEACHER_SOLUTION'));
 const redirected=await request('/?copy='+share.token);assert.ok(redirected.headers.get('location').startsWith('/login?next='));
 await stop();await start();assert.ok((await(await request('/api/kv?key=state',{cookie:member})).json()).value.exams[0].id===e.id);assert.equal((await request(exported.url,{cookie:member})).status,200);assert.equal((await(await request('/api/status',{cookie:admin})).json()).config.gemini.hasKey,true);
 assert.equal((await request('/api/account/logout',{method:'POST',cookie:member,data:{}})).status,200);assert.equal((await request('/api/kv?key=state',{cookie:member})).status,401);
 }finally{await stop();}
});
