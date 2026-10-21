export const CLOUD_PROVIDERS=['gemini','claude','gpt'];
export const PROVIDER_INFO={
 ollama:{label:'Ollama / server môn học',url:'http://127.0.0.1:11434'},
 api:{label:'Máy chủ cục bộ / API tương thích',url:'https://api.openai.com/v1'},
 greennode:{label:'GreenNode · AI riêng',url:'',keyOptional:true},
 gemini:{label:'Gemini · Google',url:'https://generativelanguage.googleapis.com/v1beta',keyURL:'https://aistudio.google.com/api-keys'},
 claude:{label:'Claude · Anthropic',url:'https://api.anthropic.com/v1',keyURL:'https://platform.claude.com/settings/keys'},
 gpt:{label:'GPT · OpenAI',url:'https://api.openai.com/v1',keyURL:'https://platform.openai.com/api-keys'}
};
export const AI_PROVIDERS=Object.keys(PROVIDER_INFO);

// Add actionable context when the server intentionally returns a generic AI error.
// Do not infer an upstream status/quota error or include raw provider payloads/keys.
export function describeAIError(message,config,path){
 const text=String(message||'Mình chưa hoàn tất được tác vụ.');
 if(!/^Mình chưa (?:hoàn tất|thực hiện) được tác vụ/.test(text)||!/^\/api\/(?:ai|assistant)\//.test(path))return text;
 const task=/\/(?:check)$/.test(path)?'check':/\/(?:chat|patch)$/.test(path)?'patch':'generate';
 const describe=key=>{const provider=config?.routes?.[key],entry=config?.[provider];return provider&&entry?.model?`${PROVIDER_INFO[provider]?.label||provider} · ${String(entry.model).replace(/[\r\n]/g,' ').slice(0,90)}`:'';};
 const current=path.endsWith('/stream')?[describe('generate'),describe('check')].filter(Boolean).join(' / '):describe(task);
 return `Tác vụ AI chưa trả kết quả hợp lệ.${current?' Cấu hình đang dùng: '+current+'.':''} Mở Kết nối AI để kiểm tra model, quyền truy cập và hạn mức. Lấy được danh sách model chưa xác nhận rằng model đó sinh được nội dung. Thông báo từ server hiện chưa cho biết nguyên nhân chi tiết.`;
}
export async function aiRequestError(path,message,readStatus=async()=>{const r=await fetch('/api/status');if(!r.ok)throw Error('Status unavailable');return r.json();}){
 const text=String(message||'Mình chưa hoàn tất được tác vụ.');
 if(!/^Mình chưa (?:hoàn tất|thực hiện) được tác vụ/.test(text)||!/^\/api\/(?:ai|assistant)\//.test(path))return Error(text);
 try{const status=await readStatus();return Error(describeAIError(text,status.config,path));}catch{return Error(describeAIError(text,null,path));}
}
