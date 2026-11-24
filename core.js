import {renderRichDocument,documentPlain} from './rich-document.js';
import {richTextHTML} from './math-content.js';
export const LEVELS=['Nhận biết','Thông hiểu','Vận dụng','Vận dụng cao'];
export const QUESTION_TYPES={mcq:'Nhiều lựa chọn',truefalse:'Đúng–sai',short:'Trả lời ngắn',essay:'Tự luận'};
export function validateMatrixRows(rows){
 if(!Array.isArray(rows)||!rows.length||rows.length>30)throw Error('Ma trận cần 1–30 dòng.');
 const usesExtended=rows.some(r=>r?.points!=null||r?.pointsByLevel!=null||r?.choiceGroup);
 if(!usesExtended){
  const keys=new Set();let count=0,fixed=0,automatic=0;
  for(const row of rows){
   const type=row.type||'mcq',topic=row.topic?.trim(),key=topic?.toLocaleLowerCase()+'|'+type;
   if(!topic||!QUESTION_TYPES[type]||keys.has(key)||!Array.isArray(row.targets)||![3,4].includes(row.targets.length)||row.targets.some(n=>!Number.isInteger(n)||n<0||n>30))throw Error('Chủ đề/loại câu cần riêng biệt, các mức có số câu nguyên 0..30.');
   keys.add(key);const total=row.targets.reduce((n,x)=>n+x,0);count+=total;
   const perLevel=row.pointsByLevelQ4;
   if(perLevel&&(!Array.isArray(perLevel)||perLevel.length!==4||row.pointsQ4!=null))throw Error('Chọn điểm chung hoặc điểm theo mức.');
   row.targets.forEach((n,i)=>{const points=perLevel?perLevel[i]:row.pointsQ4;if(points==null)automatic+=n;else{if(!Number.isInteger(points)||points<1||points>40)throw Error('Điểm mỗi câu theo bước 0,25, từ 0,25 đến 10.');fixed+=n*points;}});
  }
  if(count<1||count>30)throw Error('Nhận tổng 1–30 câu.');
  if((automatic&&40-fixed<automatic)||(!automatic&&fixed!==40))throw Error('Tổng điểm cần đúng 10; mỗi câu ít nhất 0,25.');
  return rows;
 }
 const keys=new Set();let commonQ=0,commonFixed=0,commonAuto=0;
 const trackQ=new Map(),trackFixed=new Map(),trackAuto=new Map();
 for(const row of rows){
  const type=row.type||'mcq',topic=row.topic?.trim(),grp=(row.choiceGroup||'').trim();
  const key=topic?.toLocaleLowerCase()+'|'+type+'|'+grp.toLocaleLowerCase();
  if(!topic||!QUESTION_TYPES[type]||keys.has(key)||!Array.isArray(row.targets)||![3,4].includes(row.targets.length)||row.targets.some(n=>!Number.isInteger(n)||n<0||n>30))throw Error('Chủ đề/loại câu/nhóm chọn cần riêng biệt, số câu nguyên 0..30.');
  keys.add(key);
  const perLevelQ4=row.pointsByLevelQ4,perLevelDec=row.pointsByLevel;
  if([row.pointsQ4!=null,perLevelQ4!=null,row.points!=null,perLevelDec!=null].filter(Boolean).length>1)throw Error('Chỉ chọn một cách ghi điểm trên mỗi dòng.');
  row.targets.forEach((n,i)=>{
   let p100=null;
   if(perLevelQ4)p100=perLevelQ4[i]==null?null:perLevelQ4[i]*25;
   else if(perLevelDec)p100=perLevelDec[i]==null?null:Math.round(Number(perLevelDec[i])*100);
   else if(row.pointsQ4!=null)p100=row.pointsQ4*25;
   else if(row.points!=null)p100=Math.round(Number(row.points)*100);
   if(p100!=null&&(!Number.isFinite(p100)||p100<5||p100>1000))throw Error('Điểm mỗi câu từ 0,05 đến 10.');
   if(grp){
    trackQ.set(grp,(trackQ.get(grp)||0)+n);
    if(p100==null)trackAuto.set(grp,(trackAuto.get(grp)||0)+n);
    else trackFixed.set(grp,(trackFixed.get(grp)||0)+n*p100);
   }else{
    commonQ+=n;
    if(p100==null)commonAuto+=n;else commonFixed+=n*p100;
   }
  });
 }
 const activeCount=commonQ+(trackQ.size?Math.max(...trackQ.values()):0);
 if(activeCount<1||activeCount>30)throw Error('Nhận tổng hiệu lực 1–30 câu.');
 const tracks=trackQ.size?[...trackQ.keys()]:[''];
 for(const grp of tracks){
  const fixed=commonFixed+(grp?trackFixed.get(grp)||0:0);
  const auto=commonAuto+(grp?trackAuto.get(grp)||0:0);
  const rem=1000-fixed;
  if((auto&&rem<auto*5)||(!auto&&rem!==0))throw Error('Tổng điểm hiệu lực phải đúng 10,00 điểm.');
 }
 return rows;
}
export function rebalanceMatrixRowsToTen(rows){
 if(!Array.isArray(rows)||!rows.length)throw Error('Ma trận cần ít nhất 1 dòng.');
 const next=clone(rows);
 const rowCount=r=>Array.isArray(r?.targets)?r.targets.reduce((a,b)=>a+Math.max(0,Number(b)||0),0):0;
 const existingUnit=r=>{
  if(r?.points!=null&&r.points!=='')return Number(r.points);
  if(r?.pointsQ4!=null)return Number(r.pointsQ4)/4;
  return 1;
 };
 const commonRows=next.filter(r=>!(r.choiceGroup||'').trim()&&rowCount(r)>0);
 const groups=[...new Set(next.map(r=>(r.choiceGroup||'').trim()).filter(Boolean))];
 const trackMaxQ=groups.length?Math.max(...groups.map(g=>next.filter(r=>(r.choiceGroup||'').trim()===g).reduce((s,r)=>s+rowCount(r),0))):0;
 const commonQ=commonRows.reduce((s,r)=>s+rowCount(r),0);
 const effTotal=commonQ+trackMaxQ;
 if(effTotal<1||effTotal>30)throw Error('Cần tổng hiệu lực từ 1 đến 30 câu để phân bổ 10,00 điểm.');
 const allocateSubset=(subset,targetUnits,{allowAuto=true}={})=>{
  const active=subset.filter(r=>rowCount(r)>0);
  if(!active.length)return 0;
  const weights=active.map(r=>rowCount(r)*Math.max(0.05,existingUnit(r)));
  const sumW=weights.reduce((a,b)=>a+b,0)||1;
  const counts=active.map(rowCount);
  const perQUnits=active.map((r,i)=>Math.max(1,Math.round((targetUnits*weights[i]/sumW)/counts[i])));
  let used=perQUnits.reduce((s,u,i)=>s+u*counts[i],0);
  let diff=targetUnits-used;
  let guard=0;
  while(diff!==0&&guard++<400){
   let progressed=false;
   for(let i=active.length-1;i>=0&&diff!==0;i--){
    const c=counts[i];
    if(diff>0&&diff>=c){perQUnits[i]++;diff-=c;progressed=true;}
    else if(diff<0&&-diff>=c&&perQUnits[i]>1){perQUnits[i]--;diff+=c;progressed=true;}
   }
   if(!progressed)break;
  }
  active.forEach((r,i)=>{
   delete r.pointsQ4;delete r.pointsByLevelQ4;delete r.pointsByLevel;
   r.points=Number((perQUnits[i]*0.05).toFixed(2));
  });
  if(diff!==0){
   const targetRow=active.find(r=>counts[active.indexOf(r)]===1)||active[active.length-1];
   const activeIdx=active.indexOf(targetRow);
   const othersUnits=perQUnits.reduce((s,u,idx)=>s+(idx===activeIdx?0:u*counts[idx]),0);
   const remUnits=targetUnits-othersUnits;
   const cnt=counts[activeIdx];
   if(remUnits>=cnt){
    const lvls=(targetRow.targets||[]).map((n,l)=>({n:Math.max(0,Number(n)||0),l})).filter(x=>x.n>0);
    if(remUnits%cnt===0){
     targetRow.points=Number(((remUnits/cnt)*0.05).toFixed(2));
    }else if(lvls.length>1){
     const baseU=Math.floor(remUnits/cnt);
     let extra=remUnits-baseU*cnt;
     const arr=[null,null,null,null].slice(0,targetRow.targets.length);
     for(const {n,l}of lvls){
      if(extra===0){arr[l]=Number((baseU*0.05).toFixed(2));}
      else if(extra>=n){arr[l]=Number(((baseU+1)*0.05).toFixed(2));extra-=n;}
      else if(n===1){arr[l]=Number(((baseU+1)*0.05).toFixed(2));extra--;}
      else{arr[l]=null;}
     }
     if(arr.some(x=>x==null)){if(allowAuto){delete targetRow.points;delete targetRow.pointsByLevel;}}
     else{delete targetRow.points;targetRow.pointsByLevel=arr;}
    }else if(allowAuto){
     delete targetRow.points;
    }
   }else if(!allowAuto&&remUnits<cnt){
    let totalNow=active.reduce((s,r,i)=>s+(perQUnits[i]*counts[i]),0);
    for(let i=0;i<active.length&&totalNow>targetUnits;i++){
     while(perQUnits[i]>1&&totalNow-counts[i]>=targetUnits){perQUnits[i]--;totalNow-=counts[i];}
     active[i].points=Number((perQUnits[i]*0.05).toFixed(2));
    }
   }
  }
  return active.reduce((s,r)=>s+(r.points!=null?Math.round(r.points*20)*rowCount(r):0),0);
 };
 for(const r of next)if(rowCount(r)===0){delete r.points;delete r.pointsQ4;delete r.pointsByLevel;delete r.pointsByLevelQ4;}
 if(!groups.length){
  allocateSubset(commonRows,200);
 }else{
  const commonWeightSum=commonRows.reduce((s,r)=>s+rowCount(r)*Math.max(0.05,existingUnit(r)),0);
  const trackWeightMax=Math.max(...groups.map(g=>next.filter(r=>(r.choiceGroup||'').trim()===g).reduce((s,r)=>s+rowCount(r)*Math.max(0.05,existingUnit(r)),0)),0.05);
  const maxCommonBudget=Math.max(commonQ,200-trackMaxQ);
  const commonShare=Math.min(maxCommonBudget,Math.max(commonQ,Math.round(200*(commonWeightSum/(commonWeightSum+trackWeightMax)))));
  const actualCommonFixed=allocateSubset(commonRows,commonShare,{allowAuto:false});
  const trackShare=Math.max(1,200-actualCommonFixed);
  for(const g of groups){
   allocateSubset(next.filter(r=>(r.choiceGroup||'').trim()===g),trackShare);
  }
 }
 return next;
}
export const separateMarking=e=>!!e.fullExam&&e.questions.length>0&&e.questions.every(q=>q.type==='essay');
export const clone=o=>structuredClone(o);
export const uid=()=>globalThis.crypto.randomUUID();
export const questionAnswer=q=>q.answerKnown===false||q.type==='essay'?null:q.type==='short'?(q.answerText||q.answer):q.type==='truefalse'?(q.truthValues?.length?q.truthValues:q.answer):q.answer;
export function dataChartSVG(data){
 if(!Array.isArray(data)||!data.length||data.length>100||data.some(d=>typeof d.label!=='string'||typeof d.value!=='number'||!Number.isFinite(d.value)||d.value<0||d.value>1e12))throw Error('Dữ kiện biểu đồ chưa hợp lệ.');
 const width=Math.max(240,data.length*80+32),height=220,max=Math.max(...data.map(d=>d.value),1);
 return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Biểu đồ dữ kiện Bảng 1"><path d="M12 178h'+(width-24)+'" stroke="#bccdc3"/>'+
 data.map((d,i)=>{
  const h=d.value/max*130,x=36+i*80,label=d.label.replace('Khu vực ','KV ');
  return '<g><title>'+esc(d.label)+': '+d.value+'</title><rect x="'+x+'" y="'+(178-h)+'" width="36" height="'+h+'" fill="#3b7860"/>'+
  '<text x="'+(x+18)+'" y="'+(170-h)+'" text-anchor="middle" font-size="14">'+d.value+'</text>'+
  '<text x="'+(x+18)+'" y="202" text-anchor="middle" font-size="13">'+esc(label.length>12?label.slice(0,11)+'…':label)+'</text></g>';
 }).join('')+'</svg>';
}
export function duplicateExam(original){
 if(!original?.id||!Array.isArray(original.questions))throw Error('Đề cần nhân bản không còn tồn tại.');
 const copy=clone(original);
 copy.id=uid();copy.title+=' — Bản sao';copy.updated=Date.now();copy.revision=1;copy.workflowStatus='draft';
 copy.chat=[];copy.history=[];copy.undo=[];copy.redo=[];
 for(const key of ['blockIds','activeAIJob','aiPlan','aiClarification','aiPendingPatch'])delete copy[key];
 for(const q of copy.questions){
  q.id=uid();q.v=1;q.check=null;
  delete q.blockIds;delete q.approval;delete q.verification;
 }
 return copy;
}
export const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const isConfirmedPreference=pref=>Number.isSafeInteger(pref?.confirmedAt)&&pref.confirmedAt>0;
const normScope=s=>String(s??'').trim().toLocaleLowerCase('vi-VN').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/\s+/g,' ');
const subjectScopeKey=s=>{const k=normScope(s);return (k==='tieng viet'||k==='ngu van')?'ngu van':k;};
export function prefMatchesExamScope(pref,subject='',grade=''){
 if(!isConfirmedPreference(pref))return false;
 const scope=pref?.scopeType||'all';
 if(scope==='all')return true;
 const pSubject=pref?.subject?.trim()||'';
 if(scope==='subject'||scope==='subject_grade'){
  if(pSubject&&subject&&subjectScopeKey(pSubject)!==subjectScopeKey(subject))return false;
  if(scope==='subject')return true;
  const pGrade=normScope(pref?.grade||''),eGrade=normScope(grade);
  return !pGrade||!eGrade||pGrade===eGrade;
 }
 return true;
}
export function filterPrefsForExam(prefs=[],subject='',grade=''){
 return (Array.isArray(prefs)?prefs:[]).filter(pref=>prefMatchesExamScope(pref,subject,grade));
}
export function sample(subject='Địa lí',prefs=[]){
 if(subject==='Toán')return mathSample(prefs);
 const geo=subject==='Địa lí',grade=geo?'10':'9';
 const doc={id:uid(),name:geo?'Tư liệu đô thị • Nhóm tự soạn':'Một buổi sáng ở thư viện • Nhóm tự soạn',kind:'text',sample:true,text:geo?'TƯ LIỆU MINH HỌA — KHÔNG PHẢI SỐ LIỆU THỐNG KÊ THỰC\n\n[Đoạn 1] Đô thị hóa là quá trình gia tăng tỉ lệ dân thành thị và phổ biến lối sống đô thị.\n\n[Đoạn 2] Phát triển giao thông công cộng góp phần giảm áp lực giao thông trong đô thị.\n\n[Bảng 1] Số người sử dụng thư viện tại ba khu vực A, B, C là dữ liệu tự tạo để luyện đọc biểu đồ. Bảng và biểu đồ trong đề lấy từ dữ kiện đang chỉnh sửa.':'NGỮ LIỆU MINH HỌA DO NHÓM TỰ SOẠN\n\n[Đoạn 1 • Bản A]\nBuổi sáng, nắng khẽ chạm vào ô cửa thư viện. Mai mở cuốn sách cũ, nghe tiếng giấy xào xạc như lời chào của một người bạn. Ngoài sân, cây bàng đứng yên trong gió nhẹ.\n\n[Đoạn 2 • Bản B, biên tập minh họa]\nBuổi sáng nắng khẽ chạm ô cửa thư viện. Mai mở cuốn sách cũ, nghe tiếng giấy xào xạc như lời chào của một người bạn. Ngoài sân, cây bàng khẽ lay trong gió nhẹ.'};
 const q=(stem,options,answer,topic,level,extra={})=>({id:uid(),v:1,stem,options,answer,explanation:'Thầy cô đối chiếu tư liệu và duyệt lại trước khi dùng.',topic,level,source:{docId:doc.id,location:'Đoạn 1'},check:null,...extra});
 const questions=geo?[
 q('Theo bảng số liệu, khu vực nào có số người sử dụng thư viện cao nhất?',['Khu vực A','Khu vực B','Khu vực C','Ba khu vực bằng nhau'],1,'Đọc biểu đồ',0,{rule:'max',source:{docId:doc.id,location:'Bảng 1'},explanation:'Khu vực B có 240 người, lớn nhất trong ba khu vực.'}),
 q('Số người sử dụng thư viện ở khu vực B nhiều hơn khu vực A bao nhiêu người?',['60 người','80 người','120 người','240 người'],1,'Đọc biểu đồ',2,{rule:'difference',source:{docId:doc.id,location:'Bảng 1'},explanation:'240 − 120 = 120 người. Đáp án lưu B đang lệch với phép tính; đây là ca thử có chủ đích.'}),
 q('Đô thị hóa gắn với sự thay đổi nào sau đây?',['Giảm tỉ lệ dân thành thị','Tăng tỉ lệ dân thành thị','Xóa bỏ giao thông công cộng','Giảm mọi hoạt động dịch vụ'],1,'Đô thị hóa',0),
 q('Theo tư liệu, giải pháp nào góp phần giảm áp lực giao thông đô thị?',['Tăng xe cá nhân','Thu hẹp đường đi bộ','Phát triển giao thông công cộng','Giảm phương tiện công cộng'],2,'Đô thị hóa',1,{source:{docId:doc.id,location:'Đoạn 2'}})
 ]:[
 q('Ngữ liệu lấy bối cảnh ở đâu?',['Thư viện','Bến xe','Lớp học','Sân vận động'],0,'Đọc hiểu',0,{quote:true}),
 q('Cụm từ “như lời chào của một người bạn” dùng biện pháp tu từ nào?',['Hoán dụ','So sánh','Nói quá','Liệt kê'],1,'Tiếng Việt',1,{quote:true}),
 q('Chi tiết nào gợi sự gắn bó của Mai với sách?',['Mai đóng cửa','Mai rời sân','Tiếng giấy như lời chào của bạn','Không có chi tiết nào'],2,'Đọc hiểu',1,{quote:true})];
 const quoteA=geo?'Phát triển giao thông công cộng góp phần giảm áp lực giao thông trong đô thị.':doc.text.split('[Đoạn 1 • Bản A]\n')[1].split('\n\n')[0];
 const quoteB=geo?'Phát triển giao thông công cộng có thể giảm áp lực giao thông đô thị.':doc.text.split('[Đoạn 2 • Bản B, biên tập minh họa]\n')[1];
 const topics=[...new Set(questions.map(x=>x.topic))];
 return {id:uid(),title:geo?'Kiểm tra giữa kì I — Địa lí 10':'Đọc hiểu — Ngữ văn 9',subject,grade,minutes:45,school:'TRƯỜNG THPT • BẢN DEMO',department:'',workflowStatus:'draft',instructions:'Chọn một phương án đúng cho mỗi câu hỏi.',sample:true,questions,docs:[doc],data:[{label:'Khu vực A',value:120},{label:'Khu vực B',value:240},{label:'Khu vực C',value:180}],matrix:topics.map(topic=>({topic,targets:LEVELS.map((_,l)=>questions.filter(q=>q.topic===topic&&q.level===l).length)})),matrixConfirmed:false,quote:{text:quoteA,chosen:null,versions:[{id:uid(),label:'Bản A • ngữ liệu gốc minh họa',text:quoteA,docId:doc.id,location:geo?'Đoạn 2':'Đoạn 1 • Bản A'},{id:uid(),label:'Bản B • biên tập minh họa',text:quoteB,docId:geo?null:doc.id,location:geo?'Bản đối chiếu tự soạn (không có trong tư liệu gốc)':'Đoạn 2 • Bản B'}]},appliedPrefs:clone(filterPrefsForExam(prefs,subject,grade)),chat:[{role:'assistant',text:'Thầy cô đang mở ví dụ mẫu. Có thể sửa ngay trên trang đề, chọn một câu để xem căn cứ hoặc thử đổi dữ kiện. AI, rút trích scan và tìm web chưa kết nối.'}],history:[],undo:[],redo:[],revision:1,updated:Date.now()};
}
export function mathSample(prefs=[]){
 const doc={id:uid(),name:'Ôn tập Toán 9 • Nhóm tự soạn',kind:'text',sample:true,text:'TƯ LIỆU TOÁN 9 — VÍ DỤ DO NHÓM TỰ SOẠN\n\n[Mục 1 • Phương trình]\nTrên ℝ, x² = c có hai nghiệm −√c và √c khi c > 0; một nghiệm 0 khi c = 0; vô nghiệm khi c < 0.\nVới a ≠ 0, phương trình ax + b = c có nghiệm x = (c − b)/a.\n\n[Mục 2 • Hàm số]\nGiá trị của hàm số y = ax + b tại x = t được tính bằng at + b.\n\n[Mục 3 • Tam giác vuông]\nBình phương cạnh huyền bằng tổng bình phương hai cạnh góc vuông.\n\n[Mục 4 • Xác suất]\nKhi gieo một xúc xắc cân đối sáu mặt, sáu kết quả là đồng khả năng. Xác suất một biến cố bằng số kết quả thuận lợi chia cho 6.\n\nTài liệu minh họa này không trích từ sách giáo khoa hoặc đề thi có thật.'};
 const q=(stem,options,answer,topic,level,rule,location,explanation)=>({id:uid(),v:1,stem,options,answer,topic,level,rule,source:{docId:doc.id,location},explanation,check:null});
 const questions=[
 q('Trên ℝ, tập nghiệm của phương trình x² = 9 là?',['{−3; 3}','{3}','{−3}','∅'],1,'Phương trình',0,'math-square','Mục 1 • Phương trình','Đáp án B được cố ý lưu thiếu nghiệm âm để thử rà soát. Với x² = 9, tập nghiệm là {−3; 3}.'),
 q('Giải phương trình 2x + 3 = 11 trên ℝ.',['x = 2','x = 3','x = 4','x = 5'],2,'Phương trình',1,'math-linear','Mục 1 • Phương trình','2x = 11 − 3 = 8 nên x = 4.'),
 q('Cho hàm số y = 2x + 1. Khi x = 3, giá trị của y bằng bao nhiêu?',['5','6','7','8'],2,'Hàm số',1,'math-function','Mục 2 • Hàm số','Thay x = 3 vào y = 2x + 1: y = 2 × 3 + 1 = 7.'),
 q('Một tam giác vuông có hai cạnh góc vuông dài 3 cm và 4 cm. Độ dài cạnh huyền là bao nhiêu?',['5 cm','7 cm','12 cm','25 cm'],0,'Hình học',2,'math-pythagoras','Mục 3 • Tam giác vuông','Cạnh huyền có độ dài √(3² + 4²) = 5 cm.'),
 q('Gieo một xúc xắc cân đối sáu mặt một lần. Xác suất xuất hiện mặt có số chấm chẵn là bao nhiêu?',['1/6','1/3','1/2','2/3'],2,'Xác suất',0,null,'Mục 4 • Xác suất','Có ba kết quả thuận lợi {2; 4; 6} trong sáu kết quả đồng khả năng nên xác suất là 3/6 = 1/2. Chưa có bộ giải tự động cho câu này.')];
 const topics=[...new Set(questions.map(q=>q.topic))];
 return {id:uid(),title:'Ôn tập giữa kì — Toán 9',subject:'Toán',grade:'9',minutes:45,school:'TRƯỜNG THCS • BẢN DEMO',department:'',workflowStatus:'draft',instructions:'Chọn một phương án đúng cho mỗi câu hỏi. Các phương trình được xét trên tập số thực ℝ.',sample:true,questions,docs:[doc],data:[],matrix:topics.map(topic=>({topic,targets:LEVELS.map((_,l)=>questions.filter(q=>q.topic===topic&&q.level===l).length)})),matrixConfirmed:false,quote:{text:'',chosen:null,versions:[]},appliedPrefs:clone(filterPrefsForExam(prefs,'Toán','9')),chat:[{role:'assistant',text:'Đây là ví dụ Toán 9 do nhóm tự soạn. Câu 1 cố ý lưu đáp án thiếu nghiệm để thử kiểm tra. Thầy cô có thể sửa x² = 9 thành x² = −9, xem phép kiểm đổi theo nội dung, duyệt đề xuất và hoàn tác. Các phép kiểm hỗ trợ bốn dạng mẫu trong đề; câu xác suất cần giải lại bằng AI hoặc giáo viên. Mở Kết nối AI để xem đường xử lý.'}],history:[],undo:[],redo:[],revision:1,updated:Date.now()};
}
export const usesTable=q=>['max','difference'].includes(q.rule)||q.dataLinked===true;
const mathKey=s=>String(s).replace(/−/g,'-').replace(/\s/g,'').replace(/^x=/,'').replace(/^\{(.+)\}$/,(_,body)=>body.split(';').sort().join(';'));
export function deriveMath(q){
 const stem=q.stem.replace(/−/g,'-').trim();let m,result,explanation;
 if(q.rule==='math-square'&&(m=stem.match(/^Trên ℝ, tập nghiệm của phương trình x²\s*=\s*(-?\d{1,6}) là\?$/u))){const c=Number(m[1]),root=Math.sqrt(c);result=c<0?'∅':c===0?'{0}':Number.isInteger(root)?`{−${root}; ${root}}`:`{−√${c}; √${c}}`;explanation=c<0?`Vì x² ≥ 0 với mọi x ∈ ℝ, x² = ${c} vô nghiệm trên ℝ. Tập nghiệm S = ∅.`:c===0?'x² = 0 ⇔ x = 0. Tập nghiệm S = {0}.':`x² = ${c} ⇔ x = ±√${c}. Tập nghiệm S = ${result}.`;}
 else if(q.rule==='math-linear'&&(m=stem.match(/^Giải phương trình (-?\d{1,5})x\s*([+-])\s*(\d{1,5})\s*=\s*(-?\d{1,5}) trên ℝ\.$/u))){const a=Number(m[1]),b=Number(m[3])*(m[2]==='-'?-1:1),c=Number(m[4]);if(a===0)return null;const value=(c-b)/a;if(!Number.isInteger(value))return null;result=`x = ${value}`;explanation=`${a}x = ${c} − (${b}) = ${c-b}, nên x = ${value}.`;}
 else if(q.rule==='math-function'&&(m=stem.match(/^Cho hàm số y = (-?\d{1,5})x\s*([+-])\s*(\d{1,5})\. Khi x = (-?\d{1,5}), giá trị của y bằng bao nhiêu\?$/u))){const a=Number(m[1]),b=Number(m[3])*(m[2]==='-'?-1:1),x=Number(m[4]);result=String(a*x+b);explanation=`Thay x = ${x}: y = ${a} × (${x}) + (${b}) = ${result}.`;}
 else if(q.rule==='math-pythagoras'&&(m=stem.match(/^Một tam giác vuông có hai cạnh góc vuông dài (\d{1,5}) cm và (\d{1,5}) cm\. Độ dài cạnh huyền là bao nhiêu\?$/u))){const a=Number(m[1]),b=Number(m[2]),c=Math.sqrt(a*a+b*b);if(a<=0||b<=0||!Number.isInteger(c))return null;result=`${c} cm`;explanation=`Theo định lí Pythagore: cạnh huyền = √(${a}² + ${b}²) = ${c} cm.`;}
 else return null;
 const matches=q.options.map((o,i)=>mathKey(o)===mathKey(result)?i:-1).filter(i=>i>=0);
 return {answer:matches.length===1?matches[0]:null,result,replacement:result,explanation,error:matches.length===1?null:'Phương án chưa chứa duy nhất một kết quả đúng.'};
}
export function blank(subject,prefs=[],profile=null){
 const e=sample(subject,prefs);
 e.title='Đề thi mới';
 e.instructions='Đọc kỹ và làm theo yêu cầu của từng câu.';
 if(profile?.grade)e.grade=String(profile.grade);
 if(profile?.school)e.school=profile.school;
 e.department=profile?.department||'';
 if(profile?.layout&&typeof profile.layout==='object')e.layout=clone(profile.layout);
 e.workflowStatus='draft';
 e.appliedPrefs=clone(filterPrefsForExam(prefs,subject,e.grade));
 e.sample=false;
 e.questions=[];
 e.docs=[];
 e.matrix=[{topic:'Chủ đề mới',targets:[2,1,1]}];
 e.quote={text:'',chosen:null,versions:[]};
 e.chat=[{role:'assistant',text:'Đề mới đã áp dụng các yêu cầu thầy cô xác nhận. Thầy cô có thể thêm câu thủ công, nhập tư liệu hoặc mở bộ ví dụ. Sinh câu từ tài liệu cần kết nối AI.'}];
 return e;
}
export function snapshot(e){const {history,undo,redo,...content}=e;return clone(content);}
export function commit(e,label,fn){const before=snapshot(e);const revision=Math.max(e.revision,...e.history.map(x=>x.revision))+1;fn(e);e.undo.push({label,state:before});if(e.undo.length>60)e.undo.shift();e.redo=[];e.revision=revision;e.updated=Date.now();e.history.push({id:uid(),label,at:e.updated,revision:e.revision,state:snapshot(e)});if(e.history.length>100)e.history.shift();return e;}
export function undo(e){if(!e.undo.length)return false;const previous=e.undo.pop();e.redo.push({label:previous.label,state:snapshot(e)});const {history,undo,redo}=e;Object.assign(e,clone(previous.state),{history,undo,redo});e.revision=Math.max(...history.map(x=>x.revision),e.revision)+1;e.history.push({id:uid(),label:'Hoàn tác: '+previous.label,at:Date.now(),revision:e.revision,state:snapshot(e)});return true;}
export function redo(e){if(!e.redo.length)return false;const next=e.redo.pop();e.undo.push({label:next.label,state:snapshot(e)});const {history,undo,redo}=e;Object.assign(e,clone(next.state),{history,undo,redo});e.revision=Math.max(...history.map(x=>x.revision),e.revision)+1;e.history.push({id:uid(),label:'Làm lại: '+next.label,at:Date.now(),revision:e.revision,state:snapshot(e)});return true;}
export function touch(q){q.v++;q.check=null;q.approval=null;}
export function isApproved(q){return q.approval?.version===q.v&&q.approval.status==='approved'||q.check?.version===q.v&&q.check.status==='approved';}
export function approveQuestion(q,at=Date.now()){q.approval={version:q.v,status:'approved',at,method:'Giáo viên duyệt thủ công'};}
export function recordCheck(q,result){if(q.check?.version===q.v&&q.check.status==='approved'&&!q.approval)approveQuestion(q,q.check.at);q.check=result;return result;}
export function derive(e,q){if(q.rule?.startsWith('math-'))return deriveMath(q);if(q.rule==='max'){const max=Math.max(...e.data.map(x=>x.value));const matches=e.data.map((x,i)=>x.value===max?i:-1).filter(i=>i>=0);if(matches.length!==1)return {error:'Có nhiều khu vực cùng giá trị lớn nhất. Cần sửa phương án để có đáp án duy nhất.'};const label=e.data[matches[0]].label;const opts=q.options.map((o,i)=>o.trim().toLocaleLowerCase()===label.toLocaleLowerCase()?i:-1).filter(i=>i>=0);return {answer:opts.length===1?opts[0]:null,explanation:`${label} có ${max} người, lớn nhất trong bảng.`,error:opts.length!==1?'Không có duy nhất phương án đúng với tên khu vực lớn nhất.':null};}if(q.rule==='difference'){const a=e.data[0],b=e.data[1];if(!a||!b)return {error:'Bảng thiếu dữ kiện của hai khu vực cần so sánh.'};const result=b.value-a.value;if(result<=0)return {error:'Khu vực B không nhiều hơn khu vực A. Sửa tiền đề trong thân câu trước khi duyệt.'};const matches=q.options.map((x,i)=>/^\s*-?\d+\s*(người)?\s*$/iu.test(x)&&Number(x.replace(/[^\d-]/g,''))===result?i:-1).filter(i=>i>=0);return {answer:matches.length===1?matches[0]:null,result,explanation:`${e.data[1].value} − ${e.data[0].value} = ${result} người.`,error:matches.length!==1?'Phương án chưa chứa duy nhất một kết quả đúng.':null};}return null;}
export function check(e,q){const doc=e.docs.find(d=>d.id===q.source?.docId);const d=derive(e,q);const problems=[];if(q.type!=='essay'&&q.answerKnown===false)problems.push('Chưa nhập hoặc xác nhận đáp án sau khi rút trích.');if(!['essay','short'].includes(q.type)&&(q.options.length!==4||q.options.some(x=>!x.trim())))problems.push('Cần đủ bốn phương án có nội dung.');if(!['essay','short'].includes(q.type)&&new Set(q.options.map(s=>s.trim().toLocaleLowerCase())).size!==q.options.length)problems.push('Có phương án trùng nhau.');if(q.type==='essay'&&q.rubric?.length&&Math.abs(q.rubric.reduce((n,r)=>n+Number(r.points),0)-Number(q.points))>0.001)problems.push('Tổng thang điểm chưa bằng điểm của bài.');if(!doc)problems.push('Chưa gắn tài liệu nguồn.');if(!q.stem.trim())problems.push('Câu hỏi còn trống.');for(const pref of e.appliedPrefs||[]){if(isConfirmedPreference(pref)&&pref.kind==='short'){const words=q.stem.trim().split(/\s+/u).filter(Boolean).length;if(words>(pref.maxWords||30))problems.push(`Thân câu có ${words} từ, vượt ${pref.maxWords||30} từ theo yêu cầu thầy cô đã xác nhận.`);}}if(d?.error)problems.push(d.error);if(d&&d.answer!==null&&d.answer!==undefined&&d.answer!==q.answer)problems.push(`Bất đồng: đáp án lưu ${String.fromCharCode(65+q.answer)}, phép tính cho ${String.fromCharCode(65+d.answer)}.`);recordCheck(q,{version:q.v,status:problems.length?'review':d?'consistent':'unverified',problems,evidence:d?.explanation||'Đã kiểm tra cấu trúc và liên kết nguồn. Chưa giải lại nội dung bằng AI.',at:Date.now(),method:d?(q.rule?.startsWith('math-')?'Phép tính theo dạng toán hỗ trợ, không đọc đáp án lưu để giải':'Phép tính từ bảng dữ kiện, không đọc đáp án lưu để giải'):'Rà soát cấu trúc tại máy'});return q.check;}
export function planDataUpdate(exam,values){
 if(values.length!==exam.data.length||values.some(value=>!Number.isSafeInteger(value)||value<0||value>1e6)){
  throw Error('Dữ kiện cần là số nguyên từ 0 đến 1.000.000 trong mỗi ô.');
 }
 if(values.every((value,index)=>value===exam.data[index].value))return null;
 const data=exam.data.map((row,index)=>({...row,value:values[index]}));
 const view={...exam,data};
 const questions=exam.questions.map(question=>{
  if(!usesTable(question))return question;
  const revised=clone(question);
  touch(revised);
  check(view,revised);
  return revised;
 });
 return {data,questions};
}
export function updateData(exam,index,value){
 const values=exam.data.map(row=>row.value);
 if(!Number.isInteger(index)||index<0||index>=values.length)throw Error('Không tìm thấy ô dữ kiện.');
 values[index]=value;
 const update=planDataUpdate(exam,values);
 if(update)Object.assign(exam,update);
}
export function matrix(e){return e.matrix.map(row=>({...row,cells:LEVELS.map((_,l)=>({actual:e.questions.filter(q=>q.topic===row.topic&&q.level===l&&(!row.type||q.type===row.type)).length,target:row.targets[l]||0}))}));}
const fieldHTML=(text,doc)=>doc&&documentPlain(doc)===text?renderRichDocument(doc):richTextHTML(text);
export function exportHTML(e,teacher=false){return `<!doctype html><html lang="vi"><meta charset="utf-8"><title>${esc(e.title)}${teacher?' — Giáo viên':''}</title><style>body{max-width:780px;margin:36px auto;font:16px/1.6 Georgia,serif;color:#111}h1{text-align:center;font-size:23px}header{text-align:center}section{break-inside:avoid;margin:24px 0}table{border-collapse:collapse;width:100%}td,th{border:1px solid #888;padding:7px}.options{display:grid;grid-template-columns:1fr 1fr;gap:8px}aside{background:#f4f4f4;padding:12px}svg{max-width:100%}@media print{body{margin:0}button{display:none}}.chart{display:flex;align-items:end;height:140px;gap:20px;margin:10px 0 50px}.bar{background:#536f66;text-align:center;width:100px;position:relative}.bar span{position:absolute;top:100%;left:0;width:100%;font-size:12px}</style><body><header>${esc(e.school)}<h1>${esc(e.title)}</h1><p>Môn ${esc(e.subject)} · Lớp ${esc(e.grade)} · ${esc(e.minutes)} phút</p><p>${teacher?'BẢN GIÁO VIÊN • ĐÁP ÁN VÀ GIẢI THÍCH':'Họ và tên: ........................................ Lớp: ............'}</p></header><p>${esc(e.instructions)}</p>${teacher&&e.appliedPrefs.length?'<p>Yêu cầu áp dụng: '+e.appliedPrefs.map(p=>esc(p.text)).join(' · ')+'</p>':''}${(e.subject==='Ngữ văn'||e.quote.chosen)&&e.quote.text?`<aside><p>${esc(e.quote.text).replace(/\n/g,'<br>')}</p><small>${e.quote.chosen?'Ngữ liệu đã được giáo viên chọn':'Ngữ liệu chưa duyệt'}${e.sample?' • Ngữ liệu tự soạn minh họa':''}</small></aside>`:''}${e.questions.some(usesTable)?`<p><b>Bảng 1. Số người sử dụng thư viện (người)</b> — dữ liệu minh họa tự tạo</p><table><tr>${e.data.map(d=>`<th>${esc(d.label)}</th>`).join('')}</tr><tr>${e.data.map(d=>`<td>${d.value}</td>`).join('')}</tr></table><div class="chart">${e.data.map(d=>`<div class="bar" style="height:${d.value/Math.max(...e.data.map(x=>x.value),1)*130}px"><span>${esc(d.label)}<br>${d.value}</span></div>`).join('')}</div>`:''}${e.questions.map((q,i)=>`<section><b>${q.type==='essay'?'Bài':'Câu'} ${i+1}${q.points?' ('+q.points+' điểm)':''}.</b> ${esc(q.stem).replace(/\n/g,'<br>')}<div class="options">${q.options.map((o,j)=>`<div>${String.fromCharCode(65+j)}. ${fieldHTML(o,q.optionDocs?.[j])}</div>`).join('')}</div>${teacher&&!e.fullExam?`<aside><b>${q.type==='essay'?'Hướng dẫn giải':q.answerKnown===false?'Chưa nhập đáp án':'Đáp án lưu: '+String.fromCharCode(65+q.answer)}</b><p>${fieldHTML(q.explanation,q.explanationDoc)}</p>${q.type==='essay'&&q.rubric?.length?`<table><tr><th>Nội dung</th><th>Điểm</th></tr>${q.rubric.map(r=>`<tr><td>${fieldHTML(r.text,r.richDoc)}</td><td>${r.points}</td></tr>`).join('')}</table>`:''}<small>${esc(q.check?.version===q.v?q.check.status==='approved'?'Giáo viên đã duyệt':q.check.problems.join(' ')||q.check.evidence:'Chưa kiểm tra bản hiện tại')} · Câu v${q.v}</small><p>Nguồn: ${esc(e.docs.find(d=>d.id===q.source?.docId)?.name||'Chưa có')} · ${esc(q.source?.location||'')}</p></aside>`:''}</section>`).join('')}${teacher&&e.fullExam?`<section style="break-before:page"><h1>HƯỚNG DẪN CHẤM VÀ BIỂU ĐIỂM</h1><h2>A. HƯỚNG DẪN CHUNG</h2><p>${esc(e.markingGuidance||'Học sinh có cách giải khác đúng được điểm tương ứng. Chấm theo từng bước, đơn vị điểm 0,25.')}</p><h2>B. ĐÁP ÁN VÀ THANG ĐIỂM</h2><table><tr><th>Bài</th><th>Nội dung / lời giải</th><th>Điểm</th></tr>${e.questions.map((q,i)=>`<tr><td>Bài ${i+1} (${q.points} điểm)</td><td>${fieldHTML(q.explanation,q.explanationDoc)}</td><td></td></tr>${(q.rubric||[]).map(r=>`<tr><td></td><td>${fieldHTML(r.text,r.richDoc)}</td><td>${r.points}</td></tr>`).join('')}`).join('')}</table></section>`:''}<footer>— Hết —${e.sample?' · Đề mẫu dùng để trải nghiệm':''}</footer><button onclick="window.print()">In / Lưu PDF</button></body></html>`;}

const typingGroups=new WeakMap();
export function commitTyping(e,label,fn,key){const previous=typingGroups.get(e),now=Date.now();if(previous?.key===key&&now-previous.at<2000&&previous.revision===e.revision&&e.undo.length){fn(e);e.revision++;e.updated=now;e.redo=[];const history=e.history.at(-1);if(history){history.revision=e.revision;history.at=now;history.state=snapshot(e);}typingGroups.set(e,{key,at:now,revision:e.revision});return e;}commit(e,label,fn);typingGroups.set(e,{key,at:now,revision:e.revision});return e;}
