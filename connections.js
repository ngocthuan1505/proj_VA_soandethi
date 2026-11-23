import {AI_PROVIDERS,CLOUD_PROVIDERS,PROVIDER_INFO} from './ai-providers.js';
import {esc} from './core.js';
export function connectionSettings(config){
 if(config.localPoC)return pocConnectionSettings(config);
 const providerCard=p=>{const x=config[p]||{},info=PROVIDER_INFO[p];return `<section class="settings-section provider-card" data-provider-card="${p}"><h3>${esc(info.label)}</h3><label>${p==='greennode'?'Địa chỉ JupyterLab':'Địa chỉ API'}<input name="${p}-url" value="${esc(x.url||info.url)}" spellcheck="false"></label><label>Tên mô hình<input name="${p}-model" value="${esc(x.model||'')}" list="${p}-models" placeholder="Kiểm tra kết nối rồi chọn ID mô hình" spellcheck="false"><datalist id="${p}-models"></datalist></label>${p!=='ollama'?`<label>${p==='greennode'?'Token Jupyter (nếu máy chủ yêu cầu)':'API key'}<input name="${p}-key" type="password" autocomplete="off" placeholder="${x.hasKey?'Đã có khóa trong phiên — để trống để giữ':p==='greennode'?'Để trống nếu Jupyter không yêu cầu token':'Chưa nhập khóa'}"></label><label class="consent"><input type="checkbox" name="${p}-clear-key"> Xóa khóa khỏi phiên</label>`:''}${p==='gemini'?'<p class="hint">Gợi ý cho kiểm tra đề: <b>gemini-3.8-flash</b> (phiên bản ổn định). Flash-Lite phù hợp yêu cầu nhẹ. Cần thử sinh nội dung thật với khóa đang dùng; tên trong danh sách chưa xác nhận quyền gọi.</p>':''}${info.keyURL?`<a href="${info.keyURL}" target="_blank" rel="noopener noreferrer">Mở trang tạo API key</a>`:''}<button type="button" data-action="test-provider" data-provider="${p}">Kiểm tra & xem mô hình</button><div id="${p}-result" class="hint" role="status"></div></section>`;};
 return `<p class="hint">Ba API có cấu hình và khóa riêng. Khóa chỉ giữ trong bộ nhớ máy chủ app; không ghi vào đề, bản sao hoặc trình duyệt. Khởi động lại server cần nhập lại khóa dịch vụ ngoài.</p><form id="connections-form"><h3>API AI</h3><div class="grid3 cloud-provider-grid">${CLOUD_PROVIDERS.map(providerCard).join('')}</div><details class="local-connection-settings" open><summary>AI cục bộ & máy chủ môn học</summary><p class="hint">Phạm vi làm việc GreenNode: /network-volume/ProJ_VA. Thẻ GreenNode dùng địa chỉ JupyterLab để nối bộ chạy riêng trong ProJ_VA; Ollama và máy chủ API dùng endpoint suy luận tương ứng.</p><div class="grid2">${['ollama','api','greennode'].map(providerCard).join('')}</div></details><h3 class="section-heading">Phân việc cho mô hình</h3><div class="grid3">${[['generate','Sinh đề'],['patch','Sửa vùng chọn'],['check','Giải lại / kiểm tra']].map(([task,label])=>`<label>${label}<select name="route-${task}">${AI_PROVIDERS.map(p=>`<option value="${p}" ${config.routes?.[task]===p?'selected':''}>${esc(PROVIDER_INFO[p].label)}</option>`).join('')}</select></label>`).join('')}</div><p class="hint">Mỗi tác vụ gọi đúng một dịch vụ đã chọn. App không tự chuyển sang API khác khi lỗi. Có thể dùng một dịch vụ sinh và dịch vụ khác giải lại.</p><h3 class="section-heading">Tìm nguồn trên web</h3><label>Dịch vụ tìm kiếm<select name="search-provider">${[['none','Chưa bật'],['bing','Bing RSS — không cần khóa'],['brave','Brave Search API'],['searxng','Máy chủ SearXNG']].map(([id,label])=>`<option value="${id}" ${config.search?.provider===id?'selected':''}>${label}</option>`).join('')}</select></label><div class="grid2"><label>Địa chỉ SearXNG<input name="search-url" value="${esc(config.search?.url||'')}"></label><label>Khóa Brave<input type="password" name="search-key" autocomplete="off" placeholder="${config.search?.hasKey?'Đã có khóa trong phiên':'Chưa nhập'}"></label></div><div class="alert">Kiểm tra kết nối chỉ xác nhận truy cập danh sách mô hình, chưa bảo đảm quyền sinh nội dung hoặc số dư. Các lượt sinh/sửa/kiểm tra qua API có thể tính phí và cần đồng ý trước khi gửi nội dung ra ngoài.</div><div class="modal-foot"><button class="primary" type="submit">Lưu cấu hình</button></div></form>`;
}
function readFormData(form){
 if(form&&typeof form.get==='function'&&typeof form.has==='function')return form;
 try{return new FormData(form);}catch{
  const lookup=name=>{
   if(!form)return undefined;
   if(typeof form.elements?.namedItem==='function'){
    const el=form.elements.namedItem(name);
    if(!el)return undefined;
    if(el.type==='checkbox')return el.checked?el.value||'on':undefined;
    return el.value;
   }
   return form[name];
  };
  return {
   get:name=>{const v=lookup(name);return v===undefined||v===false?null:String(v);},
   has:name=>{const v=lookup(name);return v!==undefined&&v!==null&&v!==false;},
  };
 }
}
export function connectionFormData(form){
 const fd=readFormData(form);
 const providers=Object.fromEntries(AI_PROVIDERS.map(p=>[p,{url:fd.get(p+'-url'),model:fd.get(p+'-model'),...(p!=='ollama'?{key:fd.get(p+'-key'),clearKey:fd.has(p+'-clear-key')}:{})}]));
 const poc=fd.has('poc-connection');
 if(poc){
  providers.gemini.freeTierConfirmed=fd.has('gemini-free-tier');
  providers.gemini.autoFallback=fd.has('gemini-auto-fallback');
  providers.gemini.checkModel=fd.get('gemini-check-model');
  providers.gemini.backupKey=fd.get('gemini-backup-key');
  providers.gemini.clearBackupKey=fd.has('gemini-clear-backup-key');
  providers.gemini.extraKeys=String(fd.get('gemini-extra-keys')||'').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  providers.gemini.clearExtraKeys=fd.has('gemini-clear-extra-keys');
  providers.ollama.checkModel=fd.get('ollama-check-model');
 }
 const deepseekUrl=String(fd.get('deepseek-url')||'').trim()||'https://api.deepseek.com/v1';
 const deepseekModel=String(fd.get('deepseek-model')||'').trim();
 const deepseekReasonerModel=String(fd.get('deepseek-reasoner-model')||'').trim();
 const deepseekCrossModel=String(fd.get('deepseek-cross-model')||'').trim();
 return {
  ...providers,
  routes:Object.fromEntries(['generate','patch','check'].map(t=>[t,fd.get('route-'+t)])),
  ...(poc?{
   saveLocally:fd.has('poc-save-local'),
   runBudget:{maxModelCalls:Number(fd.get('max-model-calls')),timeoutSeconds:Number(fd.get('run-timeout'))},
   deepseek:{
    url:deepseekUrl,
    ...(deepseekModel?{model:deepseekModel}:{}),
    ...(deepseekReasonerModel?{reasonerModel:deepseekReasonerModel}:{}),
    ...(deepseekCrossModel?{crossModel:deepseekCrossModel}:{}),
    key:fd.get('deepseek-key')||'',
    clearKey:fd.has('deepseek-clear-key'),
    sessionLimitUsd:Number(fd.get('deepseek-session-limit')||0.5),
    totalLimitUsd:Number(fd.get('deepseek-total-limit')||5.0),
   },
   fixedRouter:{
    enabled:true,
    timePreset:fd.get('fixed-time-preset')||'standard',
    timeoutSeconds:Number(fd.get('fixed-timeout-seconds')||300),
    agyCustomPath:fd.get('agy-custom-path')||'',
   },
  }:{}),
  search:{provider:fd.get('search-provider'),url:fd.get('search-url'),key:fd.get('search-key')},
 };
}

function pocConnectionSettings(config){
 const selected=config.routes?.generate||'ollama',g=config.gemini||{},d=config.deepseek||{},fr=config.fixedRouter||{},check=config.routes?.check||selected;
 const timePreset=fr.timePreset||'standard',timeoutSeconds=Number(fr.timeoutSeconds||300);
 const extraCount=Array.isArray(g.extraKeys)?g.extraKeys.length:Number(g.extraKeysCount||0);
 const totalGeminiKeys=g.totalKeysCount||((g.hasKey?1:0)+(g.hasBackupKey?1:0)+extraCount);
 const providers=value=>['ollama','gemini'].map(p=>`<option value="${p}" ${value===p?'selected':''}>${p==='ollama'?'Ollama trên máy':'Gemini API · Google'}</option>`).join('');
 const models=value=>(g.models||['gemini-3.6-flash']).map(m=>`<option value="${esc(m)}" ${value===m?'selected':''}>${esc(m)}</option>`).join('');
 const presets=[
  ['fast','Nhanh · 2 phút (120s · 12 lượt)','Chat linh hoạt, sửa 1 câu, tạo 1–5 câu'],
  ['standard','Tiêu chuẩn · 5 phút (300s · 30 lượt)','Đề 6–15 câu, giải mù chéo họ model'],
  ['deep','Kỹ sâu · 20 phút (1200s · 80 lượt)','Đề 15–30 câu Toán/KHTN, tự sửa phẫu thuật'],
  ['extended','Chuyên sâu · 60 phút (3600s · 200 lượt)','Đề lớn 30–60 câu, nhiều chương, lưu checkpoint từng lô'],
 ];
 return `<form id="connections-form" class="poc-connections"><input type="hidden" name="poc-connection" value="1">
 <section class="settings-section poc-time-router-section">
  <h3>Chế độ Thời gian &amp; Độ kỹ (Hệ thống tự động điều phối 11 đầu việc M01–M11)</h3>
  <p class="poc-intro">Hệ thống tự động phân việc cố định cho AGY CLI, cụm 3–4+ khóa Gemini Pro, DeepSeek và Ollama kèm 7 lớp bọc an toàn &amp; giải mù chéo model. Bạn chỉ cần chọn thời gian chạy.</p>
  <div class="time-preset-grid" role="radiogroup" aria-label="Chế độ thời gian và độ kỹ">${presets.map(([id,title,desc])=>`<label class="time-preset-card ${timePreset===id?'is-active':''}"><input type="radio" name="fixed-time-preset" value="${id}" ${timePreset===id?'checked':''}><div><b>${esc(title)}</b><small>${esc(desc)}</small></div></label>`).join('')}</div>
  <label class="fixed-timeout-label">Thời gian chạy tùy chỉnh (giây · tối đa 2 tiếng = 7200s)<input type="number" name="fixed-timeout-seconds" min="30" max="7200" value="${timeoutSeconds}"></label>
  <div class="fixed-router-status-strip" role="status" aria-label="Trạng thái 4 tầng tài nguyên AI">
   <div class="router-tier-badge"><b>AGY CLI Local</b><span>${fr.agyAvailable?'Sẵn sàng (Ưu tiên việc khó & chat sâu)':'Tự động bật khi có AGY CLI'}</span></div>
   <div class="router-tier-badge"><b>Gemini Pro Pool</b><span>${totalGeminiKeys} khóa xoay vòng</span></div>
   <div class="router-tier-badge"><b>DeepSeek ($30 Guardrail)</b><span>${d.hasKey?'Đã nạp khóa':'Chưa nạp khóa'} · Trần $${d.sessionLimitUsd??0.50}/phiên · $${d.totalLimitUsd??5.00}/tổng</span></div>
   <div class="router-tier-badge"><b>Ollama + Python</b><span>Dự phòng Offline (${esc(config.ollama?.model||'qwen3:4b')})</span></div>
  </div>
 </section>
 <details class="poc-key-vault" ${fr.vaultCollapsed?'':'open'}><summary>Quản trị khóa &amp; Nguồn lực dự phòng (Cài 1 lần · Mã hóa Windows DPAPI)</summary>
  <p class="hint">Chọn AI để soạn và kiểm đề. Chỉ phần kết nối đang dùng được hiển thị bên dưới.</p>
  <div class="grid2 poc-routes"><label>Soạn và sửa đề<select name="route-generate">${providers(selected)}</select></label><label>Kiểm đề<select name="route-check">${providers(check)}</select></label></div>
  <section class="settings-section" data-poc-provider="ollama" ${selected!=='ollama'&&check!=='ollama'?'hidden':''}><h3>Ollama trên máy</h3><p class="hint">Dùng model đã tải sẵn. Nội dung được xử lý tại máy.</p><input type="hidden" name="ollama-url" value="http://127.0.0.1:11434"><div class="grid2"><label>Model soạn đề<input name="ollama-model" value="${esc(config.ollama?.model||'')}" spellcheck="false" autocomplete="off"></label><label>Model kiểm đề<input name="ollama-check-model" value="${esc(config.ollama?.checkModel||config.ollama?.model||'')}" spellcheck="false" autocomplete="off"></label></div></section>
  <section class="settings-section" data-poc-provider="gemini" ${selected!=='gemini'&&check!=='gemini'?'hidden':''}><h3>Gemini API</h3><p class="hint">Ngữ liệu sẽ được gửi đến Google. Chọn nguồn tự viết hoặc tài liệu được phép chia sẻ.</p><input type="hidden" name="gemini-url" value="https://generativelanguage.googleapis.com/v1beta">
  <div class="grid2"><label>Model soạn đề<select name="gemini-model">${models(g.model)}</select></label><label>Model kiểm đề<select name="gemini-check-model">${models(g.checkModel||g.model)}</select></label></div>
  <label>API key Gemini (AI Studio AIza... hoặc Vertex AI Express AQ....)<input name="gemini-key" type="password" autocomplete="off" placeholder="${g.hasKey?(config.persistence?.saved?'Đã lưu mã hóa trên máy — để trống để giữ':'Đã có khóa trong phiên — để trống để giữ'):'Nhập khóa Google AI Studio (AIza...) hoặc Vertex Express (AQ....)…'}"></label>
  <details class="poc-backup" ${g.hasBackupKey||extraCount?'open':''}><summary>${g.hasBackupKey?'Key dự phòng đã kết nối':'Thêm API key dự phòng'} <span>Không bắt buộc</span></summary><label>API key của project khác<input name="gemini-backup-key" type="password" autocomplete="off" placeholder="${g.hasBackupKey?'Đã có key dự phòng — để trống để giữ':'Nhập key của project thứ hai…'}"></label><label>Cụm 6–8 khóa Gemini bổ sung (AIza... hoặc Vertex AI Express AQ...., dán nguyên dòng ten_acc : AQ....)<textarea name="gemini-extra-keys" rows="3" spellcheck="false" autocomplete="off" placeholder="${extraCount?`Đã có ${extraCount} khóa bổ sung — để trống để giữ`:'Dán thêm 6–8 khóa Vertex AI Express (AQ.... hoặc ten_acc : AQ....) hoặc Google AI Studio (AIza...), mỗi dòng 1 khóa'}"></textarea></label><label class="consent"><input type="checkbox" name="gemini-clear-extra-keys"> Xóa các khóa Gemini bổ sung</label><p class="hint">Hỗ trợ cả 6–8 khóa Vertex AI Express (<code>AQ....</code>, dán nguyên dòng <code>ten_acc : AQ....</code>) lẫn khóa Google AI Studio (<code>AIza...</code>). Hai key cùng project dùng chung quota; app luân phiên các khóa được phép và không tự bật trả phí.</p></details>
  <label class="consent"><input type="checkbox" name="gemini-auto-fallback" ${g.autoFallback!==false?'checked':''}> Tự đổi model khi hết quota</label><p class="hint">Thử các key được phép trên model đang chọn trước, sau đó chuyển giữa Flash3.6, Flash3.8 và Hydrogen4. Không dùng Flash Lite. Mọi lần thử tính vào ngân sách và ghi model thực tế trong log. Có thể tắt khi cần so sánh cố định một model.</p><label class="consent"><input type="checkbox" name="gemini-free-tier" ${g.freeTierConfirmed?'checked':''}> Tôi xác nhận các project đang ở Free tier và có quyền sử dụng.</label>
  <a class="poc-key-link" href="https://aistudio.google.com/api-keys" target="_blank" rel="noopener noreferrer">Lấy key tại Google AI Studio</a></section>
  <section class="settings-section poc-deepseek-agy-section">
   <h3>Cổng API / DeepSeek (OpenAI-compatible) &amp; AGY CLI Local</h3>
   <div class="grid2">
    <label>Base URL cổng API (HTTPS · OpenAI-compatible)<input type="url" name="deepseek-url" value="${esc(d.url||'https://api.deepseek.com/v1')}" spellcheck="false" autocomplete="off" placeholder="https://api.deepseek.com/v1"></label>
    <label>API key Cổng / DeepSeek<input type="password" name="deepseek-key" autocomplete="off" placeholder="${d.hasKey?'Đã có khóa DeepSeek — để trống để giữ':'Nhập khóa cổng API / DeepSeek…'}"></label>
   </div>
   <div class="grid2">
    <label>Model chính (soạn / nhanh)<input name="deepseek-model" value="${esc(d.model||'deepseek-v4.1-flash')}" spellcheck="false" autocomplete="off" placeholder="deepseek-v4.1-flash / deepseek-chat"></label>
    <label>Model suy luận (Reasoner)<input name="deepseek-reasoner-model" value="${esc(d.reasonerModel||'deepseek-v4-pro')}" spellcheck="false" autocomplete="off" placeholder="deepseek-v4-pro / deepseek-reasoner"></label>
   </div>
   <div class="grid2">
    <label>Model đối chiếu chéo (Cross-model)<input name="deepseek-cross-model" value="${esc(d.crossModel||'qwen3.8-max')}" spellcheck="false" autocomplete="off" placeholder="qwen3.8-max"></label>
    <label>Đường dẫn AGY CLI (tùy chọn)<input name="agy-custom-path" value="${esc(fr.agyCustomPath||'')}" spellcheck="false" autocomplete="off" placeholder="Tự động tìm agy trên máy"></label>
   </div>
   <div class="grid2">
    <label>Trần chi phí mỗi phiên ($ USD)<input type="number" step="0.05" min="0.05" max="30" name="deepseek-session-limit" value="${d.sessionLimitUsd??0.5}"></label>
    <label>Trần chi phí tổng ($ USD)<input type="number" step="0.5" min="0.1" max="30" name="deepseek-total-limit" value="${d.totalLimitUsd??5.0}"></label>
   </div>
   <label class="consent"><input type="checkbox" name="deepseek-clear-key"> Xóa khóa DeepSeek</label>
  </section>
 </details>
 <label class="consent poc-remember"><input type="checkbox" name="poc-save-local" ${config.saveLocally?'checked':''} ${config.persistence?.available?'':'disabled'}> Nhớ kết nối trên máy này</label><p class="hint">${config.persistence?.available?'Windows mã hóa kết nối cho tài khoản này. Bỏ chọn để chỉ dùng trong phiên.':'Máy này chưa hỗ trợ kho mã hóa Windows; khóa chỉ giữ trong phiên.'} Khóa không nằm trong đề hoặc mã nguồn.</p>${config.persistence?.warning?`<p role="alert">${esc(config.persistence.warning)}</p>`:''}
 <details class="poc-advanced"><summary>Cài đặt nâng cao</summary><div class="grid2"><label>Tối đa lần gọi AI<input type="number" name="max-model-calls" min="4" max="64" required value="${config.runBudget?.maxModelCalls||24}"></label><label>Thời gian tối đa (giây)<input type="number" name="run-timeout" min="30" max="900" required value="${config.runBudget?.timeoutSeconds||900}"></label></div><p class="hint">Gồm cả sinh và kiểm. Hết ngân sách thì dừng, giữ nguyên đề cũ. Giữ cố định model kiểm khi so sánh model sinh.</p><div data-poc-provider="gemini" ${selected!=='gemini'&&check!=='gemini'?'hidden':''}><label class="consent"><input type="checkbox" name="gemini-clear-backup-key"> Xóa key dự phòng</label><label class="consent"><input type="checkbox" name="gemini-clear-key"> Xóa key chính (xóa key dự phòng trước hoặc cùng lúc)</label></div></details>
 <div class="modal-foot"><span class="poc-save-note">Lưu kết nối chưa xác nhận model gọi được.</span><button class="primary" type="submit">Lưu kết nối</button></div></form>`;
}

export function refreshPocConnections(form){
 if(!form?.elements.namedItem('poc-connection'))return;
 const used=['route-generate','route-check'].map(name=>form.elements.namedItem(name).value);
 form.querySelectorAll('[data-poc-provider]').forEach(section=>section.hidden=!used.includes(section.dataset.pocProvider));
}
