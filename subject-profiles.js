export const SUBJECT_PROFILES={
 'Toán':{topics:['Biểu thức và phương trình','Hàm số và đồ thị','Bài toán thực tế','Hình học phẳng','Xác suất và thống kê'],guidance:'Bám chương trình GDPT 2018 theo lớp. Chỉ dùng kiến thức đúng cấp học. Viết phương trình trong $...$ và nêu rõ nghiệm trong lời giải để bộ tính tại máy tự đọc và kiểm tra. Bài hình cần figure spec có tọa độ/ràng buộc kiểm được. Không tự vẽ SVG.'},
 'Vật lí':{topics:['Động học','Năng lượng','Điện học','Quang học','Ứng dụng'],guidance:'Ghi rõ đơn vị SI, giả thiết, số liệu thực tế hợp lý, điều kiện áp dụng công thức; kiểm thứ nguyên.'},
 'Hoá học':{topics:['Chất và cấu tạo','Phản ứng hóa học','Tính toán hóa học','Dung dịch','Ứng dụng'],guidance:'Cân bằng phương trình; công thức hóa học đặt trong $\\ce{...}$. Ghi điều kiện phản ứng và đơn vị.'},
 'Sinh học':{topics:['Tế bào','Di truyền','Sinh thái','Cơ thể sống','Ứng dụng'],guidance:'Dùng thuật ngữ đúng theo cấp/lớp; nêu điều kiện và giới hạn của kết luận.'},
 'Ngữ văn':{topics:['Đọc hiểu','Tiếng Việt','Nghị luận xã hội','Nghị luận văn học','Viết'],guidance:'Dùng ngữ liệu người dùng cung cấp hoặc văn bản tự sáng tác có ghi nhãn. Không bịa trích dẫn, tác giả hoặc dẫn nguồn sách.'},
 'Tiếng Anh':{topics:['Ngữ âm','Từ vựng','Ngữ pháp','Đọc hiểu','Viết'],guidance:'Chọn cấp độ phù hợp lớp; ngữ cảnh rõ, chỉ một đáp án đúng nếu trắc nghiệm; đoạn đọc tự soạn.'}
};
export function profileFor(subject){return SUBJECT_PROFILES[subject]||{topics:['Kiến thức nền tảng','Hiểu và vận dụng','Bài tập tổng hợp'],guidance:'Bám chương trình theo cấp học đã nêu, không tự khẳng định nguồn khi chưa có tài liệu.'};}
const plain=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/gi,'d').toLowerCase();
export function intentOf(text,scopes=[]){const s=plain(text).trim();
 const explain=/(?:giai thich|tai sao|vi sao|huong dan cach|co nen|nhan xet|danh gia)/.test(s),edit=/(?:sua|doi|thay|them|xoa|chinh|viet lai|soan lai|rut gon|ngan hon|ngan lai|de hon|kho hon|kho cao hon|nang (?:do kho|cap)|don gian hoa|bo bot|chuyen thanh|sang trac nghiem)/.test(s);
 const greeting=/^(?:hello|hi|hey|chao(?:\s+(?:ban|thay|co|tro ly|ai))?|xin chao(?:\s+(?:ban|thay|co|tro ly|ai))?|ban la ai)[!?.,\s]*$/.test(s);
 const addQuestions=/(?:them|tao them|goi y(?:\s+them)?|bo sung(?:\s+them)?|cho them)\s+(?:(?:cho (?:toi|tui|minh)|giup (?:toi|tui|minh))\s+)?\d*\s*(?:cau|bai)\b/.test(s);
 if(greeting)return 'chat';
 if(/(?:chi giai thich|dung (?:sua|chinh)|khong chinh sua|khong sua (?:gi|noi dung))/.test(s)||explain&&!/(?:hay|giup|chi) (?:sua|doi|viet lai)|(?:sua|doi|viet lai) (?:giup|cho)/.test(s))return 'explain';
 if(addQuestions&&!/(?:viet|soan) lai/.test(s)&&!/(?:sua|doi|thay|xoa|chinh)\s+(?:cau|bai)\s*\d/.test(s))return 'chat';
 if(/(?:viet|soan) lai/.test(s)||/(?:de|bai) (?:hien tai|dang mo)/.test(s)&&edit)return 'edit';
 if(/(?:soan|tao|viet)\s+(?:(?:cho (?:toi|tui|minh)|giup (?:toi|tui|minh)|mot|1|bo)\s+)*(?:de(?:\s|$)|bai kiem tra)|(?:tao|soan|lam)\s+de moi/.test(s))return 'create';
 if(/(?:check|kiem tra|ra soat|giai lai|giai de|sua dap an)/.test(s))return 'verify';
 if(/\?\s*$/.test(s)&&!edit)return 'chat';
 if(edit||/(?:ap dung|dua vao|chen vao|dung (?:cau|bai|de xuat) (?:do|nay|vua))/.test(s)||scopes.length&&/(?:cho|tao|lam)\s+(?:(?:tui|toi|minh)\s+)?(?:1|mot)?\s*(?:cau|bai)(?: hoi)?\s+(?:moi|khac)/.test(s))return 'edit';return 'chat';}
function formatsFor(text,count,type){const found=[...text.matchAll(/(\d{1,2})\s*(?:(?:cau|bai)\s*)?(trac nghiem|dung(?:-|\s*)sai|tra loi ngan|tu luan)/g)];const toType=name=>name.startsWith('trac')?'mcq':name.startsWith('dung')?'truefalse':name.startsWith('tra loi')?'short':'essay';if(found.length>1)return found.flatMap(m=>Array(Number(m[1])).fill(toType(m[2])));if(/trac nghiem/.test(text)&&/tu luan/.test(text))return Array.from({length:count},(_,i)=>i<Math.ceil(count*.6)?'mcq':'essay');return Array(count).fill(type);}
function allocatePlanPoints(types){const n=types.length;if(n<1||n>30)throw Error('Mỗi lần soạn từ 1 đến 30 câu/bài. Chia ma trận lớn thành nhiều phần nhé.');if(new Set(types).size===1)return types.map((_,i)=>(Math.floor(40/n)+(i<40%n?1:0))/4);const weights=types.map(t=>t==='essay'?4:t==='truefalse'?2:1),total=weights.reduce((a,b)=>a+b,0),shares=weights.map(w=>(40-n)*w/total),units=shares.map(v=>Math.floor(v)+1);const order=shares.map((v,i)=>({i,f:v-Math.floor(v)})).sort((a,b)=>b.f-a.f||a.i-b.i);for(let spare=40-units.reduce((a,b)=>a+b,0),j=0;j<spare;j++)units[order[j].i]++;return units.map(x=>x/4);}
export function makePlan(text,exam={},pending=null){
 const primary=plain(text),s=primary+' '+plain(pending?.request||''),aliases=[[/\bvat li\b|\b(?:mon|de|soan)\s+ly\b|^ly\b/,'Vật lí'],[/\bhoa hoc\b|\b(?:mon|de|soan)\s+hoa\b|^hoa\b/,'Hoá học'],[/\bsinh hoc\b|\b(?:mon|de|soan)\s+sinh\b|^sinh\b/,'Sinh học'],[/\b(?:mon|de|soan)\s+anh\b|^anh\b/,'Tiếng Anh'],[/\b(?:mon|de|soan)\s+van\b|^van\b/,'Ngữ văn']];
 const subject=Object.keys(SUBJECT_PROFILES).find(n=>primary.includes(plain(n)))||aliases.find(([re])=>re.test(primary))?.[1]||Object.keys(SUBJECT_PROFILES).find(n=>s.includes(plain(n)))||exam.subject||'Toán';
 const grade=(s.match(/lop\s*(\d{1,2})/)||[])[1]||(s.match(/toan\s*(\d{1,2})/)||[])[1]||exam.grade||'9',periodText=/tuyen sinh|vao lop|giua|cuoi|hk/.test(primary)?primary:s;
 const period=/tuyen sinh|vao lop 10/.test(periodText)?'Tuyển sinh vào lớp 10':/giua/.test(periodText)?'Giữa kỳ':/hk\s*1|hoc ky\s*i\b|cuoi ky\s*1/.test(periodText)?'Cuối học kỳ I':/cuoi|hk\s*2/.test(periodText)?'Cuối học kỳ II':null;
 if(!period&&!pending)return {kind:'clarify',request:text,message:'Bạn muốn đề giữa kỳ, cuối kỳ hay tuyển sinh? Có thể cho biết thêm dạng câu hỏi và thời gian làm bài; phần chưa nêu mình sẽ chọn mặc định phù hợp.'};
 const count=Math.max(1,Number((s.match(/(\d{1,2})\s*(?:bai|cau)/)||[])[1])||5),minutes=Math.min(300,Math.max(15,Number((s.match(/(\d{2,3})\s*phut/)||[])[1])||(/tuyen sinh/.test(periodText)?120:90))),formatText=/trac nghiem|dung(?:-|\s*)sai|tra loi ngan|tu luan/.test(primary)?primary:s;
 const type=/dung(?:-|\s*)sai/.test(formatText)?'truefalse':/tra loi ngan/.test(formatText)?'short':/trac nghiem/.test(formatText)&&!/tu luan/.test(formatText)?'mcq':'essay',types=formatsFor(formatText,count,type),points=allocatePlanPoints(types),profile=profileFor(subject);
 const slots=types.map((type,i)=>({id:crypto.randomUUID(),index:i+1,type,points:points[i],topic:profile.topics[i%profile.topics.length],level:i<2?0:i<types.length-1?1:2,figure:subject==='Toán'&&types.length>=4&&profile.topics[i%profile.topics.length]==='Hình học phẳng'}));
 const names={essay:'tự luận',mcq:'trắc nghiệm',truefalse:'đúng–sai',short:'trả lời ngắn'},summary=[...new Set(types)].map(t=>types.filter(v=>v===t).length+' '+names[t]).join(', ');
 return {kind:'plan',id:crypto.randomUUID(),subject,grade,period:period||'Tuyển sinh vào lớp 10',minutes,title:'Đề '+(period||'tuyển sinh vào lớp 10')+' — '+subject+' '+grade,slots,totalPoints:10,request:(pending?.request||'')+' '+text,message:'Mình đề xuất '+summary+', tổng 10 điểm, '+minutes+' phút. Bạn đồng ý để mình viết trực tiếp vào đề chứ?'};
}

export function examRequestDefaults(text,exam){
 text=text.normalize('NFC');
 const grade=text.match(/lớp\s*(1[0-2]|[1-9])(?!\d)/iu)?.[1]||exam.grade;
 const subject=['Toán','Vật lí','Vật lý','Hóa học','Hoá học','Sinh học','Ngữ văn','Tiếng Anh','Lịch sử','Địa lí','Tin học'].find(name=>text.toLocaleLowerCase().includes(name.toLocaleLowerCase()))||exam.subject;
 const types=/(?:chỉ|toàn bộ|100%)\s*(?:câu\s*)?tự luận/iu.test(text)?'essay':/(?:chỉ|toàn bộ|100%)\s*(?:câu\s*)?trắc nghiệm/iu.test(text)?'mcq':'';
 return {grade,subject,term:/k[ìỳ]\s*(?:ii|2)(?!\w)/iu.test(text)?'cuối học kì II':/k[ìỳ]\s*(?:i|1)(?!\w)/iu.test(text)?'cuối học kì I':'cuối kì (chưa nêu học kì)',count:text.match(/(\d+)\s*(?:câu|bài)/iu)?.[1]||'',minutes:text.match(/(\d+)\s*phút/iu)?.[1]||'',types};
}
