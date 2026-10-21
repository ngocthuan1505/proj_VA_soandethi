// Uses the existing Jupyter access and only this project's transient queue.
// No new public port, terminal execution API, or access to other project folders.
import {randomUUID} from 'node:crypto';
const ROOT='network-volume/ProJ_VA/soande_ai';
class ProjectClient{
 constructor(config){const u=new URL(config.url);u.pathname='/';u.search='';u.hash='';this.base=u.origin;this.key=config.key;this.cookies='';this.xsrf='';}
 async initialize(){const response=await fetch(this.base+'/lab',{redirect:'error',headers:this.key?{Authorization:'token '+this.key}:{},signal:AbortSignal.timeout(12000)});if(!response.ok)throw Error('Không truy cập được JupyterLab. Kiểm tra địa chỉ hoặc token.');const cookies=response.headers.getSetCookie().map(c=>c.split(';')[0]);this.cookies=cookies.join('; ');this.xsrf=cookies.find(c=>c.startsWith('_xsrf='))?.slice(6)||'';await response.arrayBuffer();}
 async contents(file,method='GET',content){
  if(!/^(status\.json|jobs\/[qr]-[a-f0-9-]{36}\.json)$/.test(file))throw Error('Chỉ được dùng hàng đợi AI trong ProJ_VA.');
  const response=await fetch(this.base+'/api/contents/'+ROOT+'/'+file+(method==='GET'?'?content=1&format=text':''),{method,redirect:'error',headers:{...(this.key?{Authorization:'token '+this.key}:{}),...(this.cookies?{Cookie:this.cookies}:{}),...(this.xsrf?{'X-XSRFToken':this.xsrf}:{}),...(content?{'Content-Type':'application/json'}:{})},...(content?{body:JSON.stringify({type:'file',format:'text',content:JSON.stringify(content)})}:{}),signal:AbortSignal.timeout(15000)});
  if(response.status===404)return null;
  if(!response.ok)throw Error(`GreenNode trả HTTP ${response.status}. Kiểm tra kết nối Jupyter và quyền vào ProJ_VA.`);
  if(method==='DELETE')return true;
  const data=await response.json();return method==='GET'?JSON.parse(data.content):data;
 }
}
export async function greenStatus(config){const client=new ProjectClient(config);await client.initialize();const status=await client.contents('status.json');if(!status||!status.ready||Date.now()/1000-status.updated>600)throw Error('AI GreenNode chưa sẵn sàng. Khởi động worker trong ProJ_VA.');return status;}
export async function greenComplete(config,system,prompt,task){
 const client=new ProjectClient(config);await client.initialize();const status=await client.contents('status.json');if(!status?.ready||Date.now()/1000-status.updated>600)throw Error('AI GreenNode chưa sẵn sàng. Kiểm tra worker trong ProJ_VA.');if(status.model!==config.model)throw Error('Mô hình chọn khác mô hình đang chạy trên GreenNode. Kiểm tra kết nối để xem tên.');
 const id=randomUUID(),request='jobs/q-'+id+'.json',response='jobs/r-'+id+'.json';
 const raw='<|im_start|>system\n'+system+'<|im_end|>\n<|im_start|>user\n'+prompt+'<|im_end|>\n<|im_start|>assistant\n<think>\n</think>\n\n';
 try{await client.contents(request,'PUT',{id,task,model:config.model,prompt:raw,created:Date.now()/1000});const deadline=Date.now()+270000;while(Date.now()<deadline){const result=await client.contents(response);if(result){if(result.id!==id||!result.error&&result.model!==config.model)throw Error('Kết quả không khớp tác vụ.');if(result.error)throw Error(result.error);return result.text;}await new Promise(resolve=>setTimeout(resolve,1000));}throw Error('AI GreenNode chưa trả lời trong thời hạn. Chọn ít câu hơn hoặc kiểm tra worker.');}
 finally{await Promise.allSettled([client.contents(request,'DELETE'),client.contents(response,'DELETE')]);}
}
