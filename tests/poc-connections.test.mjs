import {test} from 'node:test';
import assert from 'node:assert/strict';
import {connectionSettings,refreshPocConnections} from '../connections.js';

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
