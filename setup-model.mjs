// Downloads the official Ollama Qwen3:4b GGUF layer; no account or API key needed.
import {mkdir,readFile,rename,stat,writeFile} from 'node:fs/promises';
import {createReadStream,createWriteStream} from 'node:fs';
import {createHash} from 'node:crypto';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {fileURLToPath} from 'node:url';
const directory=new URL('./.data/models/',import.meta.url);await mkdir(directory,{recursive:true});
const response=await fetch('https://registry.ollama.ai/v2/library/qwen3/manifests/4b');if(!response.ok)throw Error('Không đọc được manifest mô hình.');
const manifest=await response.json(),layer=manifest.layers.find(x=>x.mediaType==='application/vnd.ollama.image.model');
if(!/^sha256:[a-f0-9]{64}$/.test(layer?.digest||''))throw Error('Manifest mô hình không hợp lệ.');
const destination=fileURLToPath(new URL('qwen3-4b.gguf',directory)),partial=destination+'.part';
async function digest(file){const hash=createHash('sha256');for await(const chunk of createReadStream(file))hash.update(chunk);return hash.digest('hex');}
const expected=layer.digest.slice(7);
try{if((await stat(destination)).size===layer.size&&await digest(destination)===expected){console.log('Mô hình đã sẵn sàng, SHA-256 khớp.');process.exit(0);}}catch{}
let offset=0;try{offset=(await stat(partial)).size;}catch{}
if(offset>layer.size)throw Error('Tệp tải dở lớn hơn mô hình. Hãy đổi tên tệp .part rồi thử lại.');
if(offset<layer.size){const download=await fetch('https://registry.ollama.ai/v2/library/qwen3/blobs/'+layer.digest,{headers:offset?{Range:`bytes=${offset}-`}:{}});if(!download.ok)throw Error('Không tải được mô hình.');if(offset&&download.status!==206)offset=0;console.log(`Tải mô hình khoảng ${(layer.size/1e9).toFixed(2)} GB; có thể tiếp tục nếu bị ngắt.`);await pipeline(Readable.fromWeb(download.body),createWriteStream(partial,{flags:offset?'a':'w'}));}
if((await stat(partial)).size!==layer.size||await digest(partial)!==expected)throw Error('SHA-256 mô hình không khớp; chưa kích hoạt.');
await rename(partial,destination);await writeFile(new URL('qwen3-4b.manifest.json',directory),JSON.stringify(manifest,null,2));console.log('Mô hình sẵn sàng. Mở lại app để khởi động AI cục bộ.');
