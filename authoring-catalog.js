import {EXTRA_SUBJECTS,CURRICULUM_CATALOG,CATALOG_SOURCES} from './curriculum-catalog.js';
import {NOTATION_CATALOG} from './notation-catalog.js';
export {CATALOG_SOURCES};
export const SUBJECTS=[{id:'math',name:'Toán',symbol:'ƒ',hint:'Biểu thức, hệ và hình học'},{id:'physics',name:'Vật lí',symbol:'Ω',hint:'Đại lượng, đơn vị, công thức'},{id:'chemistry',name:'Hoá học',symbol:'H₂',hint:'Chất, ion và phản ứng'},{id:'biology',name:'Sinh học',symbol:'Aa',hint:'Di truyền và tế bào'},{id:'literature',name:'Ngữ văn',symbol:'“',hint:'Ngữ liệu, câu hỏi và dẫn nguồn'},{id:'english',name:'Tiếng Anh',symbol:'En',hint:'Đoạn đọc và bài điền từ'},...EXTRA_SUBJECTS];
const t=(id,subject,title,latex,tags=[],builder=null,fields=[])=>({id,subject,title,latex,tags,builder,fields});
export const CATALOG=[
 t('fraction','math','Phân số','\\frac{x+1}{2}',['tử số','mẫu số','chia'],'fraction',[['numerator','Tử số','x+1'],['denominator','Mẫu số','2']]),
 t('root','math','Căn bậc hai','\\sqrt{x+1}',['căn','sqrt'],'root',[['radicand','Biểu thức dưới căn','x+1']]),
 t('nth-root','math','Căn bậc n','\\sqrt[3]{8}',['căn bậc ba'],'nth-root',[['degree','Bậc của căn','3'],['radicand','Biểu thức dưới căn','8']]),
 t('power','math','Lũy thừa','x^{2}',['mũ','bình phương'],'power',[['base','Cơ số','x'],['exponent','Số mũ','2']]),
 t('system','math','Hệ phương trình','\\begin{cases}x+y=5\\\\xy=6\\end{cases}',['hai phương trình','cases','hệ'],'system',[['row1','Phương trình 1','x+y=5'],['row2','Phương trình 2','xy=6']]),
 t('quadratic','math','Nghiệm phương trình bậc hai','x=\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}',['delta','nghiệm']),
 t('sum','math','Tổng hữu hạn','\\sum_{i=1}^{n}a_i',['sigma','dãy số']),
 t('integral','math','Tích phân','\\int_a^b f(x)\\,dx',['nguyên hàm']),
 t('vector','math','Vectơ','\\overrightarrow{AB}',['hình học']),
 t('probability','math','Xác suất','P(A)=\\frac{n(A)}{n(\\Omega)}',['biến cố']),
 t('speed','physics','Vận tốc','v=\\frac{s}{t}',['chuyển động','m/s']),
 t('newton','physics','Định luật II Newton','\\vec{F}=m\\vec{a}',['lực','gia tốc','N']),
 t('ohm','physics','Định luật Ohm','I=\\frac{U}{R}',['điện','ampe','vôn','ôm']),
 t('power-electric','physics','Công suất điện','P=UI=I^2R',['oát','W']),
 t('kinetic','physics','Động năng','W_{\\mathrm{đ}}=\\frac{1}{2}mv^2',['năng lượng','J']),
 t('waves','physics','Bước sóng','\\lambda=\\frac{v}{f}',['dao động','sóng','Hz']),
 t('reaction','chemistry','Phương trình phản ứng','\\ce{2H2 + O2 -> 2H2O}',['phản ứng','cân bằng'],'reaction',[['reactants','Chất tham gia','2H2 + O2'],['products','Sản phẩm','2H2O'],['condition','Điều kiện (tùy chọn)','']]),
 t('substance','chemistry','Chất và ion','\\ce{SO4^2-}',['chỉ số','điện tích','công thức'],'substance',[['substance','Gõ chất hoặc ion như H2SO4, Ca^2+','SO4^2-']]),
 t('equilibrium','chemistry','Phản ứng thuận nghịch','\\ce{N2 + 3H2 <=> 2NH3}',['cân bằng','amoniac'],'equilibrium',[['reactants','Chất tham gia','N2 + 3H2'],['products','Sản phẩm','2NH3'],['condition','Điều kiện (tùy chọn)','']]),
 t('moles','chemistry','Số mol','n=\\frac{m}{M}',['khối lượng','mol']),
 t('concentration','chemistry','Nồng độ mol','C_M=\\frac{n}{V}',['dung dịch','mol/l']),
 t('dna','biology','Chiều dài ADN','L=\\frac{N}{2}\\times 0.34\\,\\mathrm{nm}',['nucleotit','di truyền']),
 t('mitosis','biology','Số tế bào sau nguyên phân','N=N_0\\times 2^k',['phân bào']),
 t('cross','biology','Phép lai một cặp tính trạng','\\mathrm{Aa}\\times\\mathrm{Aa}',['di truyền','Mendel']),
 {id:'punnett',subject:'biology',title:'Bảng lai Punnett',tags:['lai','bảng','di truyền'],kind:'table'},
 {id:'passage',subject:'literature',title:'Ngữ liệu đọc hiểu',tags:['đoạn trích','tác giả','nguồn'],kind:'passage'},
 {id:'poem',subject:'literature',title:'Thơ / văn bản nhiều dòng',tags:['thơ','xuống dòng','ngữ liệu'],kind:'poem'},
 {id:'reading',subject:'literature',title:'Bộ câu hỏi đọc hiểu',tags:['nhận biết','thông hiểu','vận dụng'],kind:'reading'},
 {id:'essay-outline',subject:'literature',title:'Dàn ý nghị luận',tags:['mở bài','thân bài','kết bài'],kind:'outline'},
 {id:'cloze',subject:'english',title:'Đoạn văn điền từ',tags:['cloze','điền từ','ngữ pháp'],kind:'cloze'},
 {id:'english-reading',subject:'english',title:'Đọc hiểu tiếng Anh',tags:['reading','comprehension'],kind:'english-reading'}
];
export const normalize=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/gi,'d').toLowerCase();
export function subjectId(name){const p=normalize(name).trim();const exact=SUBJECTS.find(s=>normalize(s.id)===p||normalize(s.name)===p);if(exact)return exact.id;const aliases=[['science',/khoa hoc|khtn|tu nhien/],['geography',/dia li|dia ly|geography/],['informatics',/tin hoc|informatics/],['technology',/cong nghe|technology/],['economics',/kinh te|tai chinh|ktpl|economics/],['history',/lich su|history/],['civics',/dao duc|gdcd|cong dan/],['music',/am nhac|music/],['art',/mi thuat|my thuat|art/],['pe',/the chat|the duc/],['defence',/quoc phong|gdqp|an ninh/],['experience',/trai nghiem|huong nghiep/],['languages',/ngoai ngu|tieng phap|tieng trung|tieng nhat|tieng han|tieng duc|tieng nga/],['chemistry',/hoa/],['physics',/vat|physics/],['biology',/sinh|biology/],['literature',/van|tieng viet|literature/],['english',/anh|english/]];return aliases.find(([,re])=>re.test(p))?.[0]||'math';}
export function gradeLabel(t){if(t.gradeBasis==='tool')return 'Công cụ mọi lớp';const g=t.grades||[];const runs=[];for(let i=0;i<g.length;i++){const start=g[i];while(g[i+1]===g[i]+1)i++;runs.push(g[i]>start?`${start}–${g[i]}`:String(start));}return 'Lớp '+runs.join(', ');}
export function searchCatalog(subject,query='',filters={}){const words=normalize(query).trim().split(/\s+/).filter(Boolean),members=SUBJECTS.find(s=>s.id===subject)?.members||[subject],grade=Number(filters.grade);return CATALOG.filter(t=>(!subject||members.includes(t.subject))&&(!grade||t.grades.some(g=>filters.includeEarlier?g<=grade:g===grade))&&(!filters.topic||t.topic===filters.topic)&&(!filters.type||t.type===filters.type)&&words.every(w=>normalize([t.title,...t.tags,t.latex||'',t.note,t.topic,SUBJECTS.find(s=>s.id===t.subject)?.name].join(' ')).includes(w)));}
export function buildLatex(kind,v,pattern=''){const x=k=>String(v[k]??'').trim();switch(kind){case 'pattern':return pattern.replace(/\[\[(\w+)\]\]/g,(_,key)=>x(key));case 'fraction':return `\\frac{${x('numerator')}}{${x('denominator')}}`;case 'root':return `\\sqrt{${x('radicand')}}`;case 'nth-root':return `\\sqrt[${x('degree')}]{${x('radicand')}}`;case 'power':return `{${x('base')}}^{${x('exponent')}}`;case 'system':return '\\begin{cases}'+[x('row1'),x('row2'),x('row3')].filter(Boolean).join('\\\\')+'\\end{cases}';case 'reaction':case 'equilibrium':return '\\ce{'+x('reactants')+(kind==='reaction'?' ->':' <=>')+(x('condition')?'['+x('condition')+']':'')+' '+x('products')+'}';case 'substance':return '\\ce{'+x('substance')+'}';default:return '';}}
// Only infer builders when the entire expression has a recognized structure. Advanced content remains intact.
export function inferBuilder(latex){const system=String(latex).match(/^\\begin\{cases\}([\s\S]*)\\end\{cases\}$/);if(system){const rows=system[1].split(/\\\\/).map(s=>s.replace(/&/g,'').trim());if(rows.length<=3)return {id:'system',values:Object.fromEntries(rows.map((r,i)=>['row'+(i+1),r]))};}const chem=String(latex).match(/^\\ce\{([^{}]*)\}$/);if(chem){const m=chem[1].match(/^(.*?)\s*(->|<=>)(?:\[([^\]]*)\])?\s*(.*?)$/);return m?{id:m[2]==='->'?'reaction':'equilibrium',values:{reactants:m[1],products:m[4],condition:m[3]||''}}:{id:'substance',values:{substance:chem[1]}};}return null;}
export function reactionBalance(reactants,products){function side(value){const total={};for(const term of value.split(/\s*\+\s*/)){const m=term.trim().match(/^(\d*)\s*([A-Z][A-Za-z0-9]*)$/);if(!m)return null;const coefficient=Number(m[1]||1),formula=m[2],atoms=[...formula.matchAll(/([A-Z][a-z]?)(\d*)/g)];if(atoms.map(m=>m[0]).join('')!==formula)return null;for(const a of atoms)total[a[1]]=(total[a[1]]||0)+coefficient*Number(a[2]||1);}return total;}const a=side(reactants),b=side(products);if(!a||!b)return null;return [...new Set([...Object.keys(a),...Object.keys(b)])].every(k=>a[k]===b[k]);}
export const TEMPLATE_NOTES={speed:'v: vận tốc (m/s) · s: quãng đường (m) · t: thời gian (s). Dùng cho vận tốc trung bình.',newton:'F: hợp lực (N) · m: khối lượng (kg) · a: gia tốc (m/s²). Áp dụng trong hệ quy chiếu quán tính.',ohm:'I: cường độ dòng điện (A) · U: hiệu điện thế (V) · R: điện trở (Ω). Kiểm tra điều kiện áp dụng định luật Ohm.', 'power-electric':'P: công suất (W) · U: hiệu điện thế (V) · I: cường độ dòng điện (A).',kinetic:'Wđ: động năng (J) · m: khối lượng (kg) · v: vận tốc (m/s).',waves:'λ: bước sóng (m) · v: tốc độ truyền sóng (m/s) · f: tần số (Hz).',moles:'n: lượng chất (mol) · m: khối lượng (g) · M: khối lượng mol (g/mol).',concentration:'CM: nồng độ mol (mol/L) · n: lượng chất (mol) · V: thể tích dung dịch (L).',dna:'Mẫu ADN dạng B: khoảng cách giữa hai cặp base liên tiếp xấp xỉ 0,34 nm. N là tổng số nucleotide hai mạch.',mitosis:'N₀: số tế bào ban đầu · k: số lần nguyên phân. Mẫu giả sử các tế bào đều phân chia đủ k lần.',cross:'Mẫu phép lai Aa × Aa. Cần nêu quy luật di truyền và giả thiết của bài toán.',punnett:'Mẫu minh họa Aa × Aa. Bảng có thể sửa từng ô sau khi chèn.',reading:'Câu hỏi là khung gợi ý. Điều chỉnh để phù hợp ngữ liệu và mức độ của học sinh.'};

// Original familiar shortcuts remain first; every entry shares filterable metadata.
const baseGrades={quadratic:[9,10],sum:[11],integral:[12],vector:[10,12],probability:[9,10,11,12],speed:[5,7,10],newton:[10],ohm:[9,11], 'power-electric':[9,11],kinetic:[9,10],waves:[11],moles:[8,9,10,11,12],concentration:[8,9,11],dna:[9,12],mitosis:[9,10],cross:[9,12],punnett:[9,12]};
for(const t of CATALOG){t.type=t.kind?'content':t.builder?'structure':'formula';t.grades=baseGrades[t.id]||Array.from({length:12},(_,i)=>i+1);t.gradeBasis=t.type==='structure'?'tool':'indicative';t.topic=t.kind?'Mẫu nội dung':t.type==='structure'?'Công cụ ký hiệu':'Công thức thường dùng';t.note=TEMPLATE_NOTES[t.id]||(t.kind?'Khung nội dung tham khảo. Điều chỉnh ngữ liệu và yêu cầu theo lớp đang dạy.':t.type==='structure'?'Công cụ nhập ký hiệu; thầy cô lựa chọn nội dung phù hợp từng lớp.':'Kiểm tra giả thiết và phạm vi áp dụng trong bài học trước khi sử dụng.');t.sourceIds=t.type==='structure'?[]:['curriculum'];}
CATALOG.push(...NOTATION_CATALOG,...CURRICULUM_CATALOG);

Object.assign(CATALOG.find(t=>t.id==='quadratic'),{note:'Cho ax²+bx+c=0 với a≠0 và Δ=b²−4ac≥0 để có nghiệm thực.'});
Object.assign(CATALOG.find(t=>t.id==='probability'),{note:'Không gian mẫu hữu hạn có các kết quả đồng khả năng; n(Ω)>0. Không áp dụng trực tiếp cho các kết quả không đồng khả năng.'});
Object.assign(CATALOG.find(t=>t.id==='speed'),{title:'Tốc độ trung bình',tags:['chuyển động','vận tốc','m/s'],note:'v: tốc độ trung bình (m/s) · s: tổng quãng đường (m) · t: tổng thời gian (s), t>0. Vận tốc trung bình dùng độ dịch chuyển thay cho quãng đường.'});
Object.assign(CATALOG.find(t=>t.id==='power-electric'),{note:'P: công suất (W) · U: hiệu điện thế (V) · I: cường độ dòng điện (A). Mẫu cho dòng điện không đổi; dạng I²R dùng cho điện trở thuần tuân theo Ohm.'});
