import {mkdir,writeFile,readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {dependency} from './runtime.mjs';
const root=fileURLToPath(new URL('.',import.meta.url));
await mkdir(path.join(root,'assets/tessdata'),{recursive:true});
for(const lang of ['vie','eng']){const url=`https://tessdata.projectnaptha.com/4.0.0/${lang}.traineddata.gz`;console.log('Tải dữ liệu nhận dạng',lang);const r=await fetch(url);if(!r.ok)throw Error('Không tải được '+lang);await writeFile(path.join(root,'assets/tessdata',`${lang}.traineddata.gz`),Buffer.from(await r.arrayBuffer()));}
const r=await fetch('https://registry.npmjs.org/katex/0.16.22');if(!r.ok)throw Error('Không tải được thư viện công thức.');const meta=await r.json();const tar=Buffer.from(await(await fetch(meta.dist.tarball)).arrayBuffer());const raw=dependency('node:zlib').gunzipSync(tar);const target=path.join(root,'assets/katex');await mkdir(target,{recursive:true});let count=0;
for(let off=0;off+512<raw.length;){const name=raw.subarray(off,off+100).toString().split('\0')[0];const size=parseInt(raw.subarray(off+124,off+136).toString().replace(/\0/g,'').trim(),8)||0;const type=raw[off+156];off+=512;if(name.startsWith('package/dist/')&&type!==53){const rel=name.slice('package/dist/'.length);const dest=path.resolve(target,rel);if(!dest.startsWith(target+path.sep))throw Error('Đường dẫn tài nguyên không hợp lệ.');await mkdir(path.dirname(dest),{recursive:true});await writeFile(dest,raw.subarray(off,off+size));count++;}off+=Math.ceil(size/512)*512;}
const mhchem=path.join(target,'contrib/mhchem.mjs');await writeFile(mhchem,(await readFile(mhchem,'utf8')).replace(/from ['"]katex['"]/g,"from '../katex.mjs'"));
console.log('Sẵn sàng: OCR Việt/Anh và',count,'tệp KaTeX cục bộ.');
