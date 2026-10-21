import {DatabaseSync} from 'node:sqlite';
import {mkdirSync} from 'node:fs';
import path from 'node:path';
export function openStore(root,{exclusive=false}={}){
 mkdirSync(root,{recursive:true});const db=new DatabaseSync(path.join(root,'workspace.sqlite'));
 // shortcut: the network-volume deployment allows one process only; validate storage and backups before broader use.
 db.exec((exclusive?'PRAGMA locking_mode=EXCLUSIVE; PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL;':'PRAGMA journal_mode=WAL;')+' CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, rev INTEGER NOT NULL DEFAULT 1, updated INTEGER NOT NULL)');
 return {entries(prefix){return db.prepare('SELECT key,value FROM kv WHERE key LIKE ?').all(prefix+'%').map(r=>({key:r.key,value:JSON.parse(r.value)}));},get(key){const r=db.prepare('SELECT value,rev,updated FROM kv WHERE key=?').get(key);return r?{value:JSON.parse(r.value),revision:r.rev,updated:r.updated}:null;},put(key,value,base){const prev=db.prepare('SELECT rev FROM kv WHERE key=?').get(key);if(base!==undefined&&Number(base)!==(prev?.rev||0)){const e=new Error('Dữ liệu đã được thay đổi ở cửa sổ khác. Hãy tải lại trước khi tiếp tục.');e.status=409;throw e;}const rev=(prev?.rev||0)+1;db.prepare('INSERT INTO kv(key,value,rev,updated) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,rev=excluded.rev,updated=excluded.updated').run(key,JSON.stringify(value),rev,Date.now());return rev;},close(){db.close();}};
}
