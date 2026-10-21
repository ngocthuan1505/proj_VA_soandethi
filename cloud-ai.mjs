// Native REST adapters. Keys stay on the app server and are sent in headers only.
export function authHeaders(provider,key){
 if(provider==='gemini')return {'x-goog-api-key':key};
 if(provider==='claude')return {'x-api-key':key,'anthropic-version':'2023-06-01'};
 return {Authorization:`Bearer ${key}`};
}
async function request(url,provider,c,body){
 if(!c.key)throw Error('Chưa nhập API key cho '+provider+'. Nhập khóa trực tiếp trong Kết nối AI.');
 const response=await fetch(url,{redirect:'error',...(body?{method:'POST'}:{}),headers:{...authHeaders(provider,c.key),...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(body?180000:12000)});
 if(!response.ok){const hint=response.status===401||response.status===403?'Kiểm tra API key và quyền truy cập.':response.status===429?'Kiểm tra hạn mức hoặc số dư dịch vụ.':'Kiểm tra mô hình và cấu hình dịch vụ.';throw Error(`${provider} trả HTTP ${response.status}. ${hint}`);}
 return response.json();
}
export async function cloudModels(provider,c){
 const result=await request(c.url+'/models',provider,c);
 return provider==='gemini'?(result.models||[]).filter(m=>!m.supportedGenerationMethods||m.supportedGenerationMethods.includes('generateContent')).map(m=>m.name.replace(/^models\//,'')):(result.data||[]).map(m=>m.id);
}
export async function cloudComplete(provider,c,system,prompt){
 if(provider==='gpt'){
  const data=await request(c.url+'/responses',provider,c,{model:c.model,instructions:system,input:prompt,text:{format:{type:'json_object'}},max_output_tokens:6000,store:false});
  if(data.status==='incomplete'||data.status==='failed'||data.error)throw Error('GPT chưa hoàn thành phản hồi. Thử ít câu hoặc ít nguồn hơn.');
  const content=(data.output||[]).filter(x=>x.type==='message').flatMap(x=>x.content||[]);
  if(content.some(x=>x.type==='refusal'))throw Error('GPT từ chối yêu cầu. Chưa áp dụng thay đổi.');
  return content.filter(x=>x.type==='output_text').map(x=>x.text).join('');
 }
 if(provider==='gemini'){
  const model=encodeURIComponent(c.model.replace(/^models\//,''));
  const data=await request(c.url+'/models/'+model+':generateContent',provider,c,{systemInstruction:{parts:[{text:system}]},contents:[{role:'user',parts:[{text:prompt}]}],generationConfig:{responseMimeType:'application/json',maxOutputTokens:6000}});
  const candidate=data.candidates?.[0];
  if(!candidate||candidate.finishReason&&candidate.finishReason!=='STOP')throw Error('Gemini chưa hoàn thành nội dung hoặc đã chặn yêu cầu. Thử ít câu hoặc kiểm tra nội dung nguồn.');
  return (candidate.content?.parts||[]).filter(x=>!x.thought&&typeof x.text==='string').map(x=>x.text).join('');
 }
 const data=await request(c.url+'/messages',provider,c,{model:c.model,max_tokens:6000,system,messages:[{role:'user',content:prompt}]});
 if(['max_tokens','refusal','pause_turn'].includes(data.stop_reason))throw Error('Claude chưa hoàn thành phản hồi. Chưa áp dụng; thử ít câu hoặc ít nguồn hơn.');
 return (data.content||[]).filter(x=>x.type==='text').map(x=>x.text).join('');
}
