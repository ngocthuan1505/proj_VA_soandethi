import {test} from 'node:test';
import assert from 'node:assert/strict';
import {connectionSettings,connectionFormData,refreshPocConnections} from '../connections.js';

test('PoC only shows supported connections and never embeds a saved key',()=>{
 const html=connectionSettings({localPoC:true,ollama:{model:'qwen2.5:3b'},gemini:{hasKey:true,key:'secret-must-not-render',freeTierConfirmed:true},routes:{generate:'gemini'}});
 assert.ok(html.includes('id="connections-form"'));
 assert.ok(html.includes('name="gemini-free-tier" checked'));
 assert.ok(html.includes('value="gemini" selected'));
 assert.ok(html.includes('Đã có khóa trong phiên'));
 assert.ok(!html.includes('secret-must-not-render'));
 assert.ok(!html.includes('value="gpt"'));
 assert.ok(html.includes('Ngữ liệu sẽ được gửi đến Google'));
 assert.match(html,/data-poc-provider="ollama" hidden/);
 assert.ok(!connectionSettings({}).includes('name="poc-connection"'));
 const saved=connectionSettings({localPoC:true,saveLocally:true,persistence:{available:true,saved:true},gemini:{hasKey:true,key:'secret-must-not-render'}});
 assert.ok(saved.includes('name="poc-save-local" checked'));
 assert.ok(saved.includes('Đã lưu mã hóa trên máy'));
 assert.ok(!saved.includes('secret-must-not-render'));
 const pool=connectionSettings({localPoC:true,gemini:{hasBackupKey:true,backupKey:'backup-secret-must-not-render'}});
 assert.ok(pool.includes('name="gemini-backup-key" type="password"'));
 assert.ok(pool.includes('Đã có key dự phòng'));
 assert.ok(pool.includes('name="gemini-clear-backup-key"'));
 assert.ok(!pool.includes('backup-secret-must-not-render'));
});

test('Đổi dịch vụ chỉ hiện cấu hình đang dùng, không xóa giá trị form',()=>{
 const values={'poc-connection':{value:'1'},'route-generate':{value:'ollama'},'route-check':{value:'ollama'},'gemini-key':{value:'fixture-key'}};
 const nodes=['ollama','gemini','gemini'].map(name=>({dataset:{pocProvider:name},hidden:false}));
 const form={elements:{namedItem:name=>values[name]},querySelectorAll:()=>nodes};
 refreshPocConnections(form);assert.deepEqual(nodes.map(n=>n.hidden),[false,true,true]);
 values['route-generate'].value='gemini';refreshPocConnections(form);assert.deepEqual(nodes.map(n=>n.hidden),[false,false,false]);
 values['route-check'].value='gemini';refreshPocConnections(form);assert.deepEqual(nodes.map(n=>n.hidden),[true,false,false]);
 assert.equal(values['gemini-key'].value,'fixture-key');assert.doesNotThrow(()=>refreshPocConnections(null));
});

test('PoC hiển thị đủ 4 preset thời gian (120s/300s/1200s/3600s, max 7200) và che kín multi-key Gemini + DeepSeek',()=>{
 const html=connectionSettings({
  localPoC:true,
  fixedRouter:{timePreset:'deep',timeoutSeconds:1200,agyAvailable:true},
  gemini:{
   hasKey:true,
   hasBackupKey:true,
   totalKeysCount:4,
   extraKeysCount:2,
   key:'gemini-secret-1',
   backupKey:'gemini-secret-2',
   extraKeys:['gemini-secret-3','gemini-secret-4'],
  },
  deepseek:{
   hasKey:true,
   key:'sk-deepseek-secret-must-not-leak',
   sessionLimitUsd:0.75,
   totalLimitUsd:6.5,
  },
  ollama:{model:'qwen3:4b'},
 });
 assert.ok(html.includes('120s'));
 assert.ok(html.includes('300s'));
 assert.ok(html.includes('1200s'));
 assert.ok(html.includes('3600s'));
 assert.ok(html.includes('name="fixed-timeout-seconds" min="30" max="7200" value="1200"'));
 assert.ok(html.includes('name="fixed-time-preset" value="deep" checked'));
 assert.ok(html.includes('Sẵn sàng (Ưu tiên việc khó & chat sâu)'));
 assert.ok(html.includes('4 khóa xoay vòng'));
 assert.ok(html.includes('Đã nạp khóa · Trần $0.75/phiên · $6.5/tổng'));
 assert.ok(html.includes('name="gemini-extra-keys"'));
 assert.ok(html.includes('name="gemini-clear-extra-keys"'));
 assert.ok(html.includes('name="deepseek-key"'));
 assert.ok(html.includes('name="deepseek-clear-key"'));
 assert.ok(html.includes('name="deepseek-session-limit"'));
 assert.ok(html.includes('name="deepseek-total-limit"'));
 assert.ok(html.includes('name="agy-custom-path"'));
 assert.ok(!html.includes('gemini-secret-1'));
 assert.ok(!html.includes('gemini-secret-2'));
 assert.ok(!html.includes('gemini-secret-3'));
 assert.ok(!html.includes('gemini-secret-4'));
 assert.ok(!html.includes('sk-deepseek-secret-must-not-leak'));
});

test('connectionFormData trích xuất đúng fixedRouter, deepseek và gemini.extraKeys',()=>{
 const parsed=connectionFormData({
  'poc-connection':'1',
  'route-generate':'gemini',
  'route-check':'ollama',
  'gemini-url':'https://generativelanguage.googleapis.com/v1beta',
  'gemini-model':'gemini-3.6-flash',
  'gemini-check-model':'gemini-3.8-flash',
  'gemini-key':'key-1',
  'gemini-backup-key':'key-2',
  'gemini-extra-keys':'  key-3 \n\n key-4 \r\n ',
  'gemini-clear-extra-keys':'on',
  'gemini-free-tier':'on',
  'gemini-auto-fallback':'on',
  'ollama-url':'http://127.0.0.1:11434',
  'ollama-model':'qwen3:4b',
  'ollama-check-model':'qwen3:4b',
  'deepseek-key':'sk-ds-test',
  'deepseek-clear-key':'on',
  'deepseek-session-limit':'0.85',
  'deepseek-total-limit':'7.5',
  'fixed-time-preset':'extended',
  'fixed-timeout-seconds':'7200',
  'agy-custom-path':'C:\\tools\\agy.exe',
  'poc-save-local':'on',
  'max-model-calls':'40',
  'run-timeout':'900',
 });
 assert.deepEqual(parsed.gemini.extraKeys,['key-3','key-4']);
 assert.equal(parsed.gemini.clearExtraKeys,true);
 assert.deepEqual(parsed.deepseek,{
  url:'https://api.deepseek.com/v1',
  key:'sk-ds-test',
  clearKey:true,
  sessionLimitUsd:0.85,
  totalLimitUsd:7.5,
 });
 assert.deepEqual(parsed.fixedRouter,{
  enabled:true,
  timePreset:'extended',
  timeoutSeconds:7200,
  agyCustomPath:'C:\\tools\\agy.exe',
 });
});
