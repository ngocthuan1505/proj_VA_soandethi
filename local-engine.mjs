import {mkdir,readFile,writeFile,open} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('.',import.meta.url));
export async function localEngineConfig(){const file=path.join(root,'.data/local-engine.json');try{return JSON.parse(await readFile(file,'utf8'));}catch{return null;}}
export async function prepareLocalConfig(){await mkdir(path.join(root,'.data'),{recursive:true});let config=await localEngineConfig();if(!config){config={url:'http://127.0.0.1:11435/v1',model:'qwen3:4b',engine:'llamacpp',key:randomBytes(24).toString('hex')};await writeFile(path.join(root,'.data/local-engine.json'),JSON.stringify(config,null,2));}if(config.engine!=='llamacpp'){config.engine='llamacpp';await writeFile(path.join(root,'.data/local-engine.json'),JSON.stringify(config,null,2));}return config;}
export async function startLocalEngine(appPort=4173){const exe=path.join(root,'.runtime/ollama/lib/ollama/llama-server.exe'),model=path.join(root,'.data/models/qwen3-4b.gguf');if(!existsSync(exe)||!existsSync(model))return null;const config=await prepareLocalConfig();try{const r=await fetch(config.url+'/models',{headers:{Authorization:`Bearer ${config.key}`},signal:AbortSignal.timeout(2000)});if(r.ok)return {config,child:null};}catch{}
 await writeFile(path.join(root,'.runtime/qwen-json.jinja'),`{% for message in messages %}<|im_start|>{{ message['role'] }}
{{ message['content'] }}<|im_end|>
{% endfor %}<|im_start|>assistant
<think>
</think>

`);const keyFile=path.join(root,'.data/local-engine.key');await writeFile(keyFile,config.key+'\n');const logfile=await open(path.join(root,'.data/local-engine.log'),'a');const child=spawn(exe,['--model',model,'--alias',config.model,'--host','127.0.0.1','--port','11435','--ctx-size','4096','--batch-size','256','--ubatch-size','64','--parallel','1','--threads','4','--threads-batch','6','--reasoning','off','--reasoning-format','none','--chat-template-file',path.join(root,'.runtime/qwen-json.jinja'),'--skip-chat-parsing','--api-key-file',keyFile,'--cors-origins',`http://127.0.0.1:${appPort}`,'-lv','2'],{cwd:root,windowsHide:true,stdio:['ignore',logfile.fd,logfile.fd]});child.on('exit',()=>logfile.close().catch(()=>{}));child.on('error',()=>logfile.close().catch(()=>{}));return {config,child};}
