import {AI_PROVIDERS,CLOUD_PROVIDERS,PROVIDER_INFO} from './ai-providers.js';
import {esc} from './core.js';

export const DEFAULT_AGY_ORCHESTRATOR_MODEL='gemini-pro-orchestrator-neon';
export const DEFAULT_AGY_FAST_MODEL='gemini-3.8-flash-medium';
export const AGY_RECOMMENDED_MODELS=[
 'gemini-pro-orchestrator-neon',
 'gemini-3.8-flash-medium',
 'gemini-4-neon-medium',
 'gemini-4-hydrogen-medium',
];
const AGY_EFFORT_OPTIONS=[
 ['low','Thấp (nhanh, tiết kiệm token)'],
 ['medium','Trung bình (cân bằng — mặc định)'],
 ['high','Cao (suy luận sâu & tự sửa)'],
 ['xhigh','Rất cao (đề chuyên sâu)'],
 ['max','Tối đa'],
];

export function connectionSettings(config){
 if(config.localPoC)return pocConnectionSettings(config);
 const providerCard=p=>{const x=config[p]||{},info=PROVIDER_INFO[p];return `<section class="settings-section provider-card" data-provider-card="${p}"><h3>${esc(info.label)}</h3><label>${p==='greennode'?'Địa chỉ máy chủ JupyterLab':'Địa chỉ API'}<input name="${p}-url" value="${esc(x.url||info.url)}" spellcheck="false"></label><label>Tên mô hình<input name="${p}-model" value="${esc(x.model||'')}" list="${p}-models" placeholder="Kiểm tra kết nối rồi chọn mã mô hình" spellcheck="false"><datalist id="${p}-models"></datalist></label>${p!=='ollama'?`<label>${p==='greennode'?'Mã truy cập (nếu máy chủ yêu cầu)':'Khóa API'}<input name="${p}-key" type="password" autocomplete="off" placeholder="${x.hasKey?'Đã có khóa trong phiên — để trống để giữ':p==='greennode'?'Để trống nếu máy chủ không yêu cầu':'Chưa nhập khóa'}"></label><label class="consent"><input type="checkbox" name="${p}-clear-key"> Xóa khóa khỏi phiên</label>`:''}${p==='gemini'?'<p class="hint">Gợi ý cho kiểm tra đề: <b>gemini-3.8-flash</b> (bản ổn định). Cần thử sinh nội dung thật với khóa đang dùng.</p>':''}${info.keyURL?`<a href="${info.keyURL}" target="_blank" rel="noopener noreferrer">Mở trang lấy khóa API</a>`:''}<button type="button" data-action="test-provider" data-provider="${p}">Kiểm tra &amp; xem mô hình</button><div id="${p}-result" class="hint" role="status"></div></section>`;};
 return `<p class="hint">Mỗi dịch vụ AI giữ cấu hình và khóa riêng trong bộ nhớ phiên. Khóa không ghi vào đề thi hoặc bản sao JSON.</p><form id="connections-form"><h3>Dịch vụ AI đám mây</h3><div class="grid3 cloud-provider-grid">${CLOUD_PROVIDERS.map(providerCard).join('')}</div><details class="local-connection-settings" open><summary>AI chạy tại máy &amp; máy chủ riêng</summary><div class="grid2">${['ollama','api','greennode'].map(providerCard).join('')}</div></details><h3 class="section-heading">Phân công mô hình theo tác vụ</h3><div class="grid3">${[['generate','Sinh đề'],['patch','Sửa vùng chọn'],['check','Giải lại / kiểm tra']].map(([task,label])=>`<label>${label}<select name="route-${task}">${AI_PROVIDERS.map(p=>`<option value="${p}" ${config.routes?.[task]===p?'selected':''}>${esc(PROVIDER_INFO[p].label)}</option>`).join('')}</select></label>`).join('')}</div><h3 class="section-heading">Tìm nguồn tham khảo trên web</h3><label>Dịch vụ tìm kiếm<select name="search-provider">${[['none','Chưa bật'],['bing','Bing RSS — không cần khóa'],['brave','Brave Search'],['searxng','Máy chủ SearXNG']].map(([id,label])=>`<option value="${id}" ${config.search?.provider===id?'selected':''}>${label}</option>`).join('')}</select></label><div class="grid2"><label>Địa chỉ SearXNG<input name="search-url" value="${esc(config.search?.url||'')}"></label><label>Khóa Brave<input type="password" name="search-key" autocomplete="off" placeholder="${config.search?.hasKey?'Đã có khóa trong phiên':'Chưa nhập'}"></label></div><div class="modal-foot"><button class="primary" type="submit">Lưu cấu hình</button></div></form>`;
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
 const agyModel=String(fd.get('agy-model')||'').trim();
 const agyFastModel=String(fd.get('agy-fast-model')||'').trim();
 const agyEffort=String(fd.get('agy-effort')||'').trim();
 const hasAutoPilot=fd.has('auto-pilot-field')||fd.has('auto-pilot');
 const hasWorkspaceConsent=fd.has('workspace-ai-consent-field')||fd.has('workspace-ai-consent');
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
    ...(agyModel?{agyModel}:{}),
    ...(agyFastModel?{agyFastModel}:{}),
    ...(agyEffort?{agyEffort}:{}),
    ...(hasAutoPilot?{autoPilot:fd.has('auto-pilot')}:{}),
    ...(hasWorkspaceConsent?{workspaceAiConsent:fd.has('workspace-ai-consent')}:{}),
   },
  }:{}),
  search:{provider:fd.get('search-provider'),url:fd.get('search-url'),key:fd.get('search-key')},
 };
}

export function translateProviderErrorMessage(provider,raw){
 const msg=String(raw||'').trim();
 if(!msg)return '';
 if(provider==='ollama'&&/All connection attempts failed|Connection refused|ECONNREFUSED|WinError 10061/i.test(msg)){
  return 'Chưa bật dịch vụ Ollama tại máy (127.0.0.1:11434)';
 }
 if(/All connection attempts failed|ECONNREFUSED/i.test(msg)){
  return 'Chưa kết nối được tới dịch vụ tại máy (127.0.0.1:11434)';
 }
 return msg;
}

export function renderProvidersHealthHTML(health,fallback={config:{}}){
 if(!health||typeof health!=='object'){
  return '<p class="hint">Đang kiểm tra trạng thái các kênh AI trực tiếp…</p>';
 }
 const agy=health.agy||{},gem=health.gemini||{},ds=health.deepseek||{},oll=health.ollama||{};
 const cards=[
  {
   id:'agy',
   title:'AGY Orchestrator Neon',
   ok:Boolean(agy.available||agy.detected),
   status:agy.available?`Sẵn sàng${agy.version?' · '+agy.version:''}`:(translateProviderErrorMessage('agy',agy.error)||'Chưa phát hiện trên máy'),
   detail:`Chính: ${agy.agyModel||DEFAULT_AGY_ORCHESTRATOR_MODEL} · Nhanh: ${agy.agyFastModel||DEFAULT_AGY_FAST_MODEL}`,
  },
  {
   id:'gemini',
   title:'Gemini (Google)',
   ok:Boolean(gem.configured&&(gem.activeKeys>0||gem.validKeys>0||gem.freeTierConfirmed)),
   status:gem.configured?`${gem.activeKeys??gem.validKeys??0} khóa hoạt động${gem.cooldownCount?` · ${gem.cooldownCount} tạm nghỉ`:''}`:'Chưa nạp khóa',
   detail:gem.model?`Mặc định: ${gem.model}${gem.vertexExpressKeys?` · ${gem.vertexExpressKeys} khóa Express`:''}`:'Hỗ trợ xoay vòng nhiều khóa miễn phí',
  },
  {
   id:'deepseek',
   title:'DeepSeek / Cổng API riêng',
   ok:Boolean(ds.configured&&(ds.reachable!==false||ds.ok)),
   status:ds.ok?'Kết nối ổn định':ds.configured?(translateProviderErrorMessage('deepseek',ds.message)||'Đã nạp khóa · sẵn sàng'):'Chưa nạp khóa',
   detail:ds.model?`${ds.model}${Number.isFinite(Number(ds.spentSessionUsd))?` · Đã dùng $${Number(ds.spentSessionUsd).toFixed(2)}`:''}`:'Tương thích chuẩn OpenAI',
  },
  {
   id:'ollama',
   title:'Ollama ngoại tuyến',
   ok:Boolean(oll.reachable),
   status:oll.reachable?`Đang chạy (${(oll.models||[]).length} mô hình)`:(translateProviderErrorMessage('ollama',oll.error)||'Chưa bật dịch vụ Ollama tại máy (127.0.0.1:11434)'),
   detail:(oll.chatModels||[]).length?`Gợi ý: ${oll.chatModels.slice(0,3).join(', ')}`:`Dự phòng (${fallback?.config?.ollama?.model||'qwen3:4b'})`,
  },
 ];
 return cards.map(item=>`<div class="router-tier-badge" data-health-card="${esc(item.id)}"><div class="router-tier-head"><b>${esc(item.title)}</b><span class="pill ${item.ok?'ok':'warn'}">${item.ok?'Hoạt động':'Chờ bật'}</span></div><span>${esc(item.status)}</span><small class="hint" style="margin:0">${esc(item.detail)}</small><div class="buttons" style="margin-top:4px"><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="${esc(item.id)}">Thử kênh</button><span id="provider-test-status-${esc(item.id)}" class="hint" role="status" style="margin:0"></span></div></div>`).join('');
}

export function formatProviderTestResultHTML(provider,result){
 const ok=Boolean(result?.ok||result?.reachable||result?.available);
 const rawMsg=String(result?.message||result?.error||(ok?'Kết nối thành công':'Chưa kết nối được'));
 const msg=ok?rawMsg:(translateProviderErrorMessage(provider,rawMsg)||rawMsg);
 const models=Array.isArray(result?.models)?result.models.map(m=>typeof m==='string'?m:m?.name).filter(Boolean):(Array.isArray(result?.chatModels)?result.chatModels:[]);
 const modelNote=models.length?` · Tìm thấy ${models.length} mô hình`:'';
 return {ok,text:`${ok?'✓':'⚠'} ${msg}${modelNote}`,models};
}

function pocConnectionSettings(config){
 const selected=config.routes?.generate||'ollama',g=config.gemini||{},d=config.deepseek||{},fr=config.fixedRouter||{},check=config.routes?.check||selected;
 const timePreset=fr.timePreset||'standard',timeoutSeconds=Number(fr.timeoutSeconds||300);
 const agyModel=fr.agyModel||DEFAULT_AGY_ORCHESTRATOR_MODEL;
 const agyFastModel=fr.agyFastModel||DEFAULT_AGY_FAST_MODEL;
 const agyEffort=fr.agyEffort||'medium';
 const autoPilot=fr.autoPilot!==false;
 const workspaceAiConsent=fr.workspaceAiConsent===true;
 const agyList=Array.isArray(fr.agyRecommendedModels)&&fr.agyRecommendedModels.length?fr.agyRecommendedModels:AGY_RECOMMENDED_MODELS;
 const extraCount=Array.isArray(g.extraKeys)?g.extraKeys.length:Number(g.extraKeysCount||0);
 const totalGeminiKeys=g.totalKeysCount||((g.hasKey?1:0)+(g.hasBackupKey?1:0)+extraCount);
 const providers=value=>['ollama','gemini'].map(p=>`<option value="${p}" ${value===p?'selected':''}>${p==='ollama'?'Ollama trên máy':'Gemini · Google'}</option>`).join('');
 const models=value=>(g.models||['gemini-3.6-flash']).map(m=>`<option value="${esc(m)}" ${value===m?'selected':''}>${esc(m)}</option>`).join('');
 const presets=[
  ['fast','Nhanh · 2 phút (120s · 12 lượt)','Hỏi đáp nhanh, sửa 1 câu, tạo 1–5 câu'],
  ['standard','Tiêu chuẩn · 5 phút (300s · 30 lượt)','Đề 6–15 câu, đối chiếu chéo hai mô hình độc lập'],
  ['deep','Kỹ sâu · 20 phút (1200s · 80 lượt)','Đề 15–30 câu Toán/KHTN, kiểm tra điều kiện chi tiết'],
  ['extended','Chuyên sâu · 60 phút (3600s · 200 lượt)','Đề lớn 30–60 câu, nhiều chương, lưu tiến độ từng phần'],
 ];
 return `<form id="connections-form" class="poc-connections"><input type="hidden" name="poc-connection" value="1">
 <section class="settings-section poc-time-router-section">
  <div class="row space"><h3>Tầng 1 · Thời gian xử lý &amp; Trạng thái các kênh AI</h3><button type="button" class="tiny-btn" data-action="refresh-providers-health">Kiểm tra nhanh</button></div>
  <p class="poc-intro hint">Hệ thống tự động chọn đường xử lý phù hợp cho từng yêu cầu và đối chiếu chéo để tăng độ tin cậy. Thầy cô chỉ cần chọn thời lượng xử lý.</p>
  <div class="auto-pilot-banner">
   <input type="hidden" name="auto-pilot-field" value="1">
   <label class="consent"><input type="checkbox" name="auto-pilot" ${autoPilot?'checked':''}> <b>Tự động hoàn toàn (Plan → Swarm → Goal)</b> — Tự lập ma trận, sinh song song nhiều lô và kiểm định lên trang A4</label>
   <input type="hidden" name="workspace-ai-consent-field" value="1">
   <label class="consent"><input type="checkbox" name="workspace-ai-consent" ${workspaceAiConsent?'checked':''}> Cho phép gửi nội dung tới AI cho toàn không gian làm việc (không hỏi lặp từng đề)</label>
  </div>
  <div class="time-preset-grid" role="radiogroup" aria-label="Chế độ thời gian và độ kỹ">${presets.map(([id,title,desc])=>`<label class="time-preset-card ${timePreset===id?'is-active':''}"><input type="radio" name="fixed-time-preset" value="${id}" ${timePreset===id?'checked':''}><div><b>${esc(title)}</b><small>${esc(desc)}</small></div></label>`).join('')}</div>
  <label class="fixed-timeout-label">Thời gian chờ tối đa (giây · tối đa 7200s)<input type="number" name="fixed-timeout-seconds" min="30" max="7200" value="${timeoutSeconds}"></label>
  <div id="providers-health-strip" class="fixed-router-status-strip" role="status" aria-label="Trạng thái 4 kênh AI">
   <div class="router-tier-badge" data-agy-neon-card="1"><b>AGY Orchestrator Neon</b><span>${fr.agyAvailable?'Sẵn sàng (Ưu tiên việc khó & chat sâu)':'Tự động bật khi có AGY CLI'}</span><small class="hint" style="margin:0">Điều phối: <code>${esc(agyModel)}</code> · Nhanh: <code>${esc(agyFastModel)}</code> (${esc(agyEffort)})</small><div class="buttons"><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="agy">Thử kênh</button><span id="provider-test-status-agy" class="hint"></span></div></div>
   <div class="router-tier-badge"><b>Gemini xoay vòng</b><span>${totalGeminiKeys} khóa xoay vòng</span><div class="buttons"><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="gemini">Thử kênh</button><span id="provider-test-status-gemini" class="hint"></span></div></div>
   <div class="router-tier-badge"><b>DeepSeek / Cổng API riêng</b><span>${d.hasKey?'Đã nạp khóa':'Chưa nạp khóa'} · Trần $${d.sessionLimitUsd??0.50}/phiên · $${d.totalLimitUsd??5.00}/tổng</span><div class="buttons"><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="deepseek">Thử kênh</button><span id="provider-test-status-deepseek" class="hint"></span></div></div>
   <div class="router-tier-badge"><b>Ollama trên máy</b><span>Dự phòng ngoại tuyến (${esc(config.ollama?.model||'qwen3:4b')})</span><div class="buttons"><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="ollama">Khám phá &amp; thử</button><span id="provider-test-status-ollama" class="hint"></span></div></div>
  </div>
 </section>
 <details class="poc-key-vault" ${fr.vaultOpen?'open':''}><summary>Tầng 2 · Quản lý khóa xoay vòng, Cổng riêng, AGY CLI &amp; Ollama</summary>
  <p class="hint">Cài một lần, mã hóa an toàn trên Windows. Thầy cô có thể chọn kênh ưu tiên và thử từng kết nối riêng biệt.</p>
  <div class="grid2 poc-routes"><label>Kênh soạn và sửa đề<select name="route-generate">${providers(selected)}</select></label><label>Kênh kiểm tra lại<select name="route-check">${providers(check)}</select></label></div>
  <section class="settings-section" data-poc-provider="ollama" ${selected!=='ollama'&&check!=='ollama'?'hidden':''}><div class="row space"><h3>Ollama trên máy (tự khám phá mô hình)</h3><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="ollama">Tự khám phá mô hình</button></div><p class="hint">Dùng mô hình chạy ngoại tuyến tại máy. Dữ liệu không rời khỏi máy tính.</p><input type="hidden" name="ollama-url" value="http://127.0.0.1:11434"><div class="grid2"><label>Mô hình soạn đề<input name="ollama-model" list="ollama-models-list" value="${esc(config.ollama?.model||'')}" spellcheck="false" autocomplete="off"></label><label>Mô hình kiểm đề<input name="ollama-check-model" list="ollama-models-list" value="${esc(config.ollama?.checkModel||config.ollama?.model||'')}" spellcheck="false" autocomplete="off"></label></div><datalist id="ollama-models-list"></datalist><div id="ollama-discovered-models" class="buttons" style="margin-top:6px"></div></section>
  <section class="settings-section" data-poc-provider="gemini" ${selected!=='gemini'&&check!=='gemini'?'hidden':''}><div class="row space"><h3>Gemini API · Cụm khóa xoay vòng</h3><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="gemini">Thử kênh Gemini</button></div><p class="hint">Ngữ liệu sẽ được gửi đến Google. Chọn nguồn tự soạn hoặc tài liệu được phép chia sẻ.</p><input type="hidden" name="gemini-url" value="https://generativelanguage.googleapis.com/v1beta">
  <div class="grid2"><label>Mô hình soạn đề<select name="gemini-model">${models(g.model)}</select></label><label>Mô hình kiểm đề<select name="gemini-check-model">${models(g.checkModel||g.model)}</select></label></div>
  <label>Khóa Gemini chính (AI Studio AIza... hoặc Vertex AI Express AQ....)<input name="gemini-key" type="password" autocomplete="off" placeholder="${g.hasKey?(config.persistence?.saved?'Đã lưu mã hóa trên máy — để trống để giữ':'Đã có khóa trong phiên — để trống để giữ'):'Nhập khóa Google AI Studio (AIza...) hoặc Vertex Express (AQ....)…'}"></label>
  <details class="poc-backup" ${g.hasBackupKey||extraCount?'open':''}><summary>${g.hasBackupKey?'Khóa dự phòng đã kết nối':'Thêm khóa API dự phòng &amp; cụm khóa xoay vòng'} <span>Không bắt buộc</span></summary><label>Khóa API dự phòng<input name="gemini-backup-key" type="password" autocomplete="off" placeholder="${g.hasBackupKey?'Đã có key dự phòng — để trống để giữ':'Nhập khóa của dự án thứ hai…'}"></label><label>Cụm khóa Gemini xoay vòng bổ sung (AIza... hoặc Vertex AI Express AQ...., mỗi dòng: ten_acc : AQ....)<textarea name="gemini-extra-keys" rows="3" spellcheck="false" autocomplete="off" placeholder="${extraCount?`Đã có ${extraCount} khóa bổ sung — để trống để giữ`:'Dán thêm khóa Vertex AI Express (AQ.... hoặc ten_acc : AQ....) hoặc Google AI Studio (AIza...), mỗi dòng 1 khóa'}"></textarea></label><label class="consent"><input type="checkbox" name="gemini-clear-extra-keys"> Xóa các khóa Gemini bổ sung</label><p class="hint">Hỗ trợ nhiều khóa Vertex AI Express (<code>AQ....</code>, dạng <code>ten_acc : AQ....</code>) và Google AI Studio (<code>AIza...</code>). Hệ thống tự luân phiên khóa còn hạn mức.</p></details>
  <label class="consent"><input type="checkbox" name="gemini-auto-fallback" ${g.autoFallback!==false?'checked':''}> Tự đổi mô hình khi hết hạn mức</label><label class="consent"><input type="checkbox" name="gemini-free-tier" ${g.freeTierConfirmed?'checked':''}> Tôi xác nhận các khóa đang dùng ở mức miễn phí hợp lệ.</label>
  <a class="poc-key-link" href="https://aistudio.google.com/api-keys" target="_blank" rel="noopener noreferrer">Lấy khóa tại Google AI Studio</a></section>
  <section class="settings-section poc-deepseek-agy-section">
   <div class="row space"><h3>DeepSeek / Cổng API riêng &amp; AGY Orchestrator Neon</h3><div class="buttons"><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="deepseek">Thử Cổng riêng</button><button type="button" class="tiny-btn" data-action="test-single-provider" data-provider="agy">Thử AGY CLI</button></div></div>
   <div class="grid2">
    <label>Mô hình AGY điều phối chính (Neon)<input name="agy-model" list="agy-models-list" value="${esc(agyModel)}" spellcheck="false" autocomplete="off" placeholder="${DEFAULT_AGY_ORCHESTRATOR_MODEL}"></label>
    <label>Mô hình AGY tầng nhanh (tiết kiệm token)<input name="agy-fast-model" list="agy-models-list" value="${esc(agyFastModel)}" spellcheck="false" autocomplete="off" placeholder="${DEFAULT_AGY_FAST_MODEL}"></label>
   </div>
   <datalist id="agy-models-list">${agyList.map(m=>`<option value="${esc(m)}"></option>`).join('')}</datalist>
   <div class="grid2">
    <label>Mức độ suy luận AGY<select name="agy-effort">${AGY_EFFORT_OPTIONS.map(([val,lbl])=>`<option value="${val}" ${agyEffort===val?'selected':''}>${esc(lbl)}</option>`).join('')}</select></label>
    <label>Đường dẫn AGY CLI (tùy chọn)<input name="agy-custom-path" value="${esc(fr.agyCustomPath||'')}" spellcheck="false" autocomplete="off" placeholder="Tự động tìm agy trên máy"></label>
   </div>
   <div class="grid2">
    <label>Địa chỉ cổng API (HTTPS · chuẩn OpenAI)<input type="url" name="deepseek-url" value="${esc(d.url||'https://api.deepseek.com/v1')}" spellcheck="false" autocomplete="off" placeholder="https://api.deepseek.com/v1"></label>
    <label>Khóa API Cổng / DeepSeek<input type="password" name="deepseek-key" autocomplete="off" placeholder="${d.hasKey?'Đã có khóa DeepSeek — để trống để giữ':'Nhập khóa cổng API / DeepSeek…'}"></label>
   </div>
   <div class="grid2">
    <label>Mô hình chính (soạn / nhanh)<input name="deepseek-model" value="${esc(d.model||'deepseek-v4.1-flash')}" spellcheck="false" autocomplete="off" placeholder="deepseek-v4.1-flash / deepseek-chat"></label>
    <label>Mô hình suy luận<input name="deepseek-reasoner-model" value="${esc(d.reasonerModel||'deepseek-v4-pro')}" spellcheck="false" autocomplete="off" placeholder="deepseek-v4-pro / deepseek-reasoner"></label>
   </div>
   <div class="grid2">
    <label>Mô hình đối chiếu chéo<input name="deepseek-cross-model" value="${esc(d.crossModel||'qwen3.8-max')}" spellcheck="false" autocomplete="off" placeholder="qwen3.8-max"></label>
    <label>Giới hạn chi phí mỗi phiên ($ USD)<input type="number" step="0.05" min="0.05" max="30" name="deepseek-session-limit" value="${d.sessionLimitUsd??0.5}"></label>
   </div>
   <div class="grid2">
    <label>Giới hạn chi phí tổng ($ USD)<input type="number" step="0.5" min="0.1" max="30" name="deepseek-total-limit" value="${d.totalLimitUsd??5.0}"></label>
    <label class="consent"><input type="checkbox" name="deepseek-clear-key"> Xóa khóa DeepSeek / Cổng riêng</label>
   </div>
  </section>
  <details class="poc-advanced"><summary>Giới hạn lượt gọi &amp; Xóa khóa nhanh</summary><div class="grid2"><label>Số lượt gọi tối đa<input type="number" name="max-model-calls" min="4" max="64" required value="${config.runBudget?.maxModelCalls||24}"></label><label>Thời gian tối đa (giây)<input type="number" name="run-timeout" min="30" max="900" required value="${config.runBudget?.timeoutSeconds||900}"></label></div><div data-poc-provider="gemini" ${selected!=='gemini'&&check!=='gemini'?'hidden':''}><label class="consent"><input type="checkbox" name="gemini-clear-backup-key"> Xóa khóa dự phòng</label><label class="consent"><input type="checkbox" name="gemini-clear-key"> Xóa khóa chính</label></div></details>
 </details>
 <label class="consent poc-remember"><input type="checkbox" name="poc-save-local" ${config.saveLocally?'checked':''} ${config.persistence?.available?'':'disabled'}> Ghi nhớ cấu hình mã hóa trên máy này</label><p class="hint">${config.persistence?.available?'Windows mã hóa an toàn cho tài khoản hiện tại. Khóa không nằm trong đề thi hoặc tệp sao lưu.':'Máy chưa bật kho mã hóa; khóa chỉ giữ trong phiên làm việc hiện tại.'}</p>${config.persistence?.warning?`<p role="alert">${esc(config.persistence.warning)}</p>`:''}
 <div class="modal-foot"><span class="poc-save-note">Lưu xong có thể bấm Thử kênh để kiểm tra kết nối thật.</span><button class="primary" type="submit">Lưu kết nối</button></div></form>`;
}

export function refreshPocConnections(form){
 if(!form?.elements.namedItem('poc-connection'))return;
 const used=['route-generate','route-check'].map(name=>form.elements.namedItem(name).value);
 form.querySelectorAll('[data-poc-provider]').forEach(section=>section.hidden=!used.includes(section.dataset.pocProvider));
}
