import {deploymentSettings} from './deployment.mjs';
import {accountService} from './accounts.mjs';
import {workbenchRoutes,friendlyError} from './workbench-server.mjs';
import {startLocalEngine} from './local-engine.mjs';
import {AI_PROVIDERS} from './ai-providers.js';
import http from 'node:http';
import {readFile,writeFile,mkdir,stat} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {formattedHTML,makeDocx,makePDF} from './exports.mjs';
import {openStore} from './backend-store.mjs';
import {extractFile,recognize,renderPdfPage,parseQuestions} from './importers.mjs';
import {defaultConfig,publicConfig,mergeConfig,testProvider,generate,patch,solve,readMatrix} from './ai.mjs';
import {searchWeb,readWeb} from './web-sources.mjs';
const root=fileURLToPath(new URL('.',import.meta.url)),deployment=deploymentSettings(),{port,origin,host,online}=deployment;
const dataRoot=process.env.APP_DATA_DIR||path.join(root,'.data'),exportRoot=online?path.join(dataRoot,'exports'):path.join(root,'exports');
await mkdir(path.join(root,'.data/ocr-cache'),{recursive:true});
const store=openStore(dataRoot,{exclusive:process.env.APP_SQLITE_EXCLUSIVE==='1'});
let config=structuredClone(defaultConfig);const saved=store.get('config')?.value;if(saved){for(const key of [...AI_PROVIDERS,'routes','search'])Object.assign(config[key],saved[key]||{});for(const key of [...AI_PROVIDERS.filter(p=>p!=='ollama'),'search'])config[key].key='';}
let localEngine=null;if(!online&&!process.env.APP_DATA_DIR){localEngine=await startLocalEngine(port);if(localEngine&&config.api.url===localEngine.config.url&&config.api.engine==='llamacpp')config.api.key=localEngine.config.key;if(localEngine&&!config.ollama.model&&!config.api.model){Object.assign(config.api,localEngine.config);config.routes={generate:'api',patch:'api',check:'api'};config.search.provider='bing';}}
if(process.env.APP_AI_CONFIG)config=mergeConfig(config,JSON.parse(process.env.APP_AI_CONFIG));
const account=accountService(store,deployment);
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.woff':'font/woff','.woff2':'font/woff2','.ttf':'font/ttf','.gz':'application/gzip','.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'};
const send=(res,data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
const workbench=workbenchRoutes({store,account,getConfig:()=>config,body,send,origin,online});
async function body(req){let size=0,chunks=[];for await(const chunk of req){size+=chunk.length;if(size>150*1024*1024)throw Error('Dữ liệu quá lớn.');chunks.push(chunk);}return JSON.parse(Buffer.concat(chunks).toString('utf8')||'{}');}
function fileBuffer(id,owner='local'){const value=store.get(account.scope(owner,'file:'+id))?.value;if(typeof value!=='string'||!/^data:[^;,]+;base64,/.test(value))throw Error('Chưa tìm thấy tệp gốc trên máy chủ.');const buffer=Buffer.from(value.split(',')[1],'base64');if(buffer.length>20*1024*1024)throw Error('Tệp vượt giới hạn 20 MB.');return buffer;}
function validateExam(e){if(!e||!Array.isArray(e.questions)||e.questions.length>1000||!Array.isArray(e.docs)||!Array.isArray(e.data)||!e.quote||!Array.isArray(e.appliedPrefs))throw Error('Dữ liệu đề không hợp lệ.');for(const q of e.questions)if(typeof q.stem!=='string'||!Array.isArray(q.options)||(['essay','short'].includes(q.type)?q.options.length!==0:q.options.length!==4)||q.options.some(x=>typeof x!=='string'))throw Error('Câu hỏi không hợp lệ.');}
const server=http.createServer(async(req,res)=>{try{
 const u=new URL(req.url,origin),p=decodeURIComponent(u.pathname),currentOwner=account.owner(req);
 if(!deployment.allowedHosts.has(String(req.headers.host||'').toLowerCase()))return send(res,{error:'Host không hợp lệ'},403);
 if(!['GET','HEAD','OPTIONS'].includes(req.method)&&!deployment.allowedOrigins.has(req.headers.origin))return send(res,{error:'Chỉ nhận yêu cầu từ đúng địa chỉ ứng dụng.'},403);
 if(p==='/api/health'&&req.method==='GET'){store.get('config');return send(res,{ok:true});}
 if(online&&currentOwner==='local'){if(p==='/'||p==='/index.html'){res.writeHead(302,{Location:'/login'+(u.search?'?next='+encodeURIComponent('/'+u.search):''),'Cache-Control':'no-store'});return res.end();}if(p.startsWith('/exports/'))return send(res,{error:'Đăng nhập để mở bản xuất.'},401);if(p.startsWith('/api/')&&!['/api/account','/api/account/login','/api/account/register'].includes(p))return send(res,{error:'Đăng nhập để tiếp tục.'},401);}
 if(online&&['/api/config','/api/test-provider'].includes(p)&&!account.isAdmin(req))return send(res,{error:'Chỉ người quản lý được thay đổi kết nối AI.'},403);
 if(online&&p==='/login'&&['GET','HEAD'].includes(req.method)){const html=await readFile(path.join(root,'assets/online-login.html'));res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"});return res.end(req.method==='HEAD'?undefined:html);}
 if(await workbench(req,res,u))return;
 if(p.startsWith('/s/')&&req.method==='GET'){const token=p.slice(3),share=store.get('share:'+account.hash(token))?.value;if(!share||share.revoked)return send(res,{error:'Liên kết không còn hiệu lực.'},404);let html=await formattedHTML(share.exam,share.answers,origin);html=html.replace('<body>',`<body><div style="font:14px Segoe UI;padding:15px;background:#eef4ff;margin-bottom:20px">Bản chia sẻ chỉ xem · ${share.allowCopy?'<a href="/?copy='+encodeURIComponent(token)+'">Sao chép vào kho đề của tôi</a>':'Không cho phép sao chép qua ứng dụng'}</div>`);res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});return res.end(html);}
 if(p==='/api/status'&&req.method==='GET')return send(res,{version:'6.0.0',storage:'sqlite',ocr:existsSync(path.join(root,'assets/tessdata/vie.traineddata.gz')),pdf:true,docx:true,online,admin:account.isAdmin(req),config:account.isAdmin(req)?publicConfig(config):{routes:config.routes,...Object.fromEntries(AI_PROVIDERS.map(p=>[p,{model:config[p]?.model||'',url:'',hasKey:false}])),search:{provider:'none',url:'',hasKey:false}}});
 if(p==='/api/kv'&&req.method==='GET'){const key=u.searchParams.get('key');if(key!=='state'&&!/^file:[\w-]+$/.test(key||''))throw Error('Khóa không hợp lệ.');return send(res,store.get(account.scope(currentOwner,key))||{value:null,revision:0});}
 if(p==='/api/kv'&&req.method==='PUT'){const {key,value}=await body(req);if(key!=='state'&&!/^file:[\w-]+$/.test(key||''))throw Error('Khóa không hợp lệ.');if(key==='state'&&(!Array.isArray(value?.exams)||!Array.isArray(value?.prefs)))throw Error('Dữ liệu workspace không hợp lệ.');const revision=store.put(account.scope(currentOwner,key),value,req.headers['if-match']===undefined?undefined:Number(req.headers['if-match']));return send(res,{revision});}
 if(p==='/api/config'&&req.method==='POST'){config=mergeConfig(config,await body(req));store.put('config',publicConfig(config));return send(res,publicConfig(config));}
 if(p==='/api/test-provider'&&req.method==='POST'){const {provider}=await body(req);return send(res,await testProvider(config,provider));}
 if(p==='/api/extract'&&req.method==='POST'){const {fileId,name}=await body(req);return send(res,await extractFile(name,fileBuffer(fileId,currentOwner)));}
 if(p==='/api/ocr'&&req.method==='POST'){const {fileId,name,page=1}=await body(req);const original=fileBuffer(fileId,currentOwner);const image=name.toLowerCase().endsWith('.pdf')?await renderPdfPage(original,Number(page)):original;return send(res,await recognize(image));}
 if(p==='/api/parse-questions'&&req.method==='POST'){const {text,images=[]}=await body(req);if(typeof text!=='string'||text.length>1000000)throw Error('Văn bản không hợp lệ.');return send(res,{questions:parseQuestions(text,images)});}
 if(p==='/api/page-image'&&req.method==='GET'){const data=await renderPdfPage(fileBuffer(u.searchParams.get('file'),currentOwner),Number(u.searchParams.get('page')||1));res.writeHead(200,{'Content-Type':'image/png'});return res.end(data);}
 if(p==='/api/ai/matrix'&&req.method==='POST')return send(res,await readMatrix(config,await body(req)));
 if(p==='/api/ai/generate'&&req.method==='POST')return send(res,await generate(config,await body(req)));
 if(p==='/api/ai/patch'&&req.method==='POST')return send(res,await patch(config,await body(req)));
 if(p==='/api/ai/check'&&req.method==='POST')return send(res,await solve(config,await body(req)));
 if(p==='/api/search'&&req.method==='POST'){const b=await body(req);return send(res,await searchWeb(config,b.query,b.consent));}
 if(p==='/api/read-web'&&req.method==='POST'){const b=await body(req);return send(res,await readWeb(b.url,b.consent));}
 if(p==='/api/save-export'&&req.method==='POST'){
  const payload=await body(req);let content,ext,label;if(payload.type==='exam'){validateExam(payload.exam);ext=['docx','pdf','html'].includes(payload.format)?payload.format:'html';label=payload.teacher?'Giao-vien':'Hoc-sinh';content=ext==='docx'?await makeDocx(payload.exam,payload.teacher===true):ext==='pdf'?await makePDF(payload.exam,payload.teacher===true,origin):await formattedHTML(payload.exam,payload.teacher===true,origin);}
  else if(payload.type==='backup'&&payload.backup?.format==='tro-ly-soan-de'){content=JSON.stringify(payload.backup,null,2);ext='json';label='Ban-sao';}else throw Error('Bản xuất không hợp lệ.');
  const filename=`${label}-${new Date().toISOString().replace(/[:.]/g,'-')}-${crypto.randomUUID().slice(0,6)}.${ext}`;await mkdir(exportRoot,{recursive:true});await writeFile(path.join(exportRoot,filename),content);store.put('export-owner:'+filename,currentOwner);return send(res,{filename,url:'/exports/'+filename,bytes:Buffer.byteLength(content)});
 }
 if(p.startsWith('/api/'))return send(res,{error:'Không có tác vụ này.'},404);
 const rel=p==='/'?'index.html':p.slice(1);const allowed=['index.html', 'citation-context.js', 'sketch-board.js', 'lesson-picker.js' , 'assistant-sources.js','bootstrap.js','app.js','matrix-chat.js','matrix-chat.css','matrix-synthesis.js','question-check.js','sharing.js','core.js','storage.js','style.css','mvp.css','mvp.js','editor.js','ai-providers.js','connections.js','client-services.js','reference.js','reference.css','workbench.js','workbench.css','geometry.js','blocks.js','math-content.js','subject-profiles.js','rich-document.js','studio.js','studio.css','pages.js','composer.js','composer.css','authoring-catalog.js','curriculum-catalog.js','notation-catalog.js','design.js','design.css'];if(!allowed.includes(rel)&&!rel.startsWith('assets/')&&!rel.startsWith('exports/'))return send(res,{error:'Không tìm thấy tài nguyên.'},404);
 if(rel.startsWith('exports/')){const fileOwner=store.get('export-owner:'+rel.slice(8))?.value;if((online&&!fileOwner)||(fileOwner&&fileOwner!==currentOwner))return send(res,{error:'Bạn không có quyền mở bản xuất này.'},403);}
 const file=rel.startsWith('exports/')?path.resolve(exportRoot,rel.slice(8)):path.resolve(root,rel),canonical=(rel.startsWith('exports/')?'exports/':'')+path.relative(rel.startsWith('exports/')?exportRoot:root,file).split(path.sep).join('/');if(canonical!==rel||!['GET','HEAD'].includes(req.method))return send(res,{error:'Không được phép.'},403);const info=await stat(file);if(!info.isFile())throw Error('Không có tệp.');const data=await readFile(file);res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(req.method==='HEAD'?undefined:data);
 }catch(error){if(res.headersSent){res.end();return;}send(res,{error:friendlyError(error)},error.status||400);}});
server.requestTimeout=300000;
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{localEngine?.child?.kill();server.close(()=>{store.close();process.exit(0);});setTimeout(()=>process.exit(1),15000).unref();});
server.listen(port,host,()=>console.log(`MVP đang chạy: ${origin} • Dữ liệu tại .data/workspace.sqlite`));
