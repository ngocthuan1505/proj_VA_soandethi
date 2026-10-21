// Reusable notation tools. Grade labels describe availability in the editor, not syllabus requirements.
const p=(id,title,pattern,fields,tags=[],subject='math')=>({id:'tool-'+id,subject,title,pattern,builder:'pattern',fields:fields.map(([k,l,v])=>[k,l,v]),latex:pattern.replace(/\[\[(\w+)\]\]/g,(_,key)=>fields.find(f=>f[0]===key)?.[2]||''),tags,grades:Array.from({length:12},(_,i)=>i+1),topic:'Công cụ ký hiệu',type:'structure',note:'Công cụ soạn ký hiệu dùng ở mọi lớp. Nội dung và mức độ do thầy cô lựa chọn.',sourceIds:[],gradeBasis:'tool'});
export const NOTATION_CATALOG=[
 p('matrix2','Ma trận 2 × 2',String.raw`\begin{pmatrix}[[a]]&[[b]]\\[[c]]&[[d]]\end{pmatrix}`,[['a','Ô hàng 1, cột 1','1'],['b','Ô hàng 1, cột 2','2'],['c','Ô hàng 2, cột 1','3'],['d','Ô hàng 2, cột 2','4']],['ma tran','bảng số']),
 p('matrix3','Ma trận 3 × 3',String.raw`\begin{pmatrix}[[a]]&[[b]]&[[c]]\\[[d]]&[[e]]&[[f]]\\[[g]]&[[h]]&[[i]]\end{pmatrix}`,Array.from({length:9},(_,i)=>[String.fromCharCode(97+i),`Ô hàng ${Math.floor(i/3)+1}, cột ${i%3+1}`,String(i%4===0?1:0)]),['ma tran']),
 p('determinant','Định thức 2 × 2',String.raw`\begin{vmatrix}[[a]]&[[b]]\\[[c]]&[[d]]\end{vmatrix}`,[['a','Ô 1,1','a'],['b','Ô 1,2','b'],['c','Ô 2,1','c'],['d','Ô 2,2','d']],['định thức']),
 p('piecewise','Hàm cho bởi từng khoảng',String.raw`f(x)=\begin{cases}[[a]]&[[condition1]]\\[[b]]&[[condition2]]\end{cases}`,[['a','Biểu thức thứ nhất','x^2'],['condition1','Điều kiện thứ nhất',String.raw`x\ge 0`],['b','Biểu thức thứ hai','-x'],['condition2','Điều kiện thứ hai','x<0']],['hàm từng đoạn','cases']),
 p('binomial','Tổ hợp / hệ số nhị thức',String.raw`\binom{[[n]]}{[[k]]}`,[['n','Số phần tử','n'],['k','Số phần tử chọn','k']],['tổ hợp']),
 p('limit','Giới hạn',String.raw`\lim_{[[variable]]\to [[target]]}[[expression]]`,[['variable','Biến','x'],['target','Giá trị tiến tới','0'],['expression','Biểu thức',String.raw`\frac{\sin x}{x}`]],['lim','giới hạn']),
 p('derivative','Đạo hàm',String.raw`\frac{d}{d[[variable]]}\left([[expression]]\right)`,[['variable','Biến','x'],['expression','Biểu thức','x^2']],['đạo hàm']),
 p('integral','Tích phân có cận',String.raw`\int_{[[lower]]}^{[[upper]]}[[expression]]\,d[[variable]]`,[['lower','Cận dưới','0'],['upper','Cận trên','1'],['expression','Hàm dưới dấu tích phân','x^2'],['variable','Biến','x']],['tích phân']),
 p('sum','Tổng có chỉ số',String.raw`\sum_{[[lower]]}^{[[upper]]}[[expression]]`,[['lower','Chỉ số đầu','i=1'],['upper','Chỉ số cuối','n'],['expression','Số hạng','a_i']],['sigma','tổng']),
 p('product','Tích có chỉ số',String.raw`\prod_{[[lower]]}^{[[upper]]}[[expression]]`,[['lower','Chỉ số đầu','i=1'],['upper','Chỉ số cuối','n'],['expression','Thừa số','a_i']],['tích']),
 p('vector','Ký hiệu vectơ',String.raw`\overrightarrow{[[name]]}`,[['name','Tên vectơ','AB']],['vectơ']),
 p('absolute','Giá trị tuyệt đối',String.raw`\left\lvert [[expression]]\right\rvert`,[['expression','Biểu thức','x-1']],['trị tuyệt đối']),
 p('indexed','Chỉ số dưới và số mũ',String.raw`{[[base]]}_{[[index]]}^{[[power]]}`,[['base','Ký hiệu','a'],['index','Chỉ số dưới','n'],['power','Số mũ','2']],['chỉ số','mũ']),
 p('scientific','Dạng khoa học',String.raw`[[coefficient]]\times 10^{[[power]]}`,[['coefficient','Hệ số','6.02'],['power','Số mũ của 10','23']],['khoa học','lũy thừa mười']),
 p('interval','Khoảng và đoạn',String.raw`[[left]][[a]];[[b]][[right]]`,[['left','Dấu đầu: ( hoặc [','['],['a','Đầu trái','a'],['b','Đầu phải','b'],['right','Dấu cuối: ) hoặc ]',']']],['khoảng','đoạn']),
 p('set','Tập hợp theo điều kiện',String.raw`\left\{[[variable]]\mid [[condition]]\right\}`,[['variable','Phần tử','x'],['condition','Điều kiện','x>0']],['tập hợp']),
 p('angle','Ký hiệu góc',String.raw`\widehat{[[name]]}=[[value]]^{\circ}`,[['name','Tên góc','ABC'],['value','Số đo (độ)','60']],['góc']),
 p('aligned','Các bước biến đổi',String.raw`\begin{aligned}[[row1]]\\[[row2]]\\[[row3]]\end{aligned}`,[['row1','Dòng 1','A=2(x+1)'],['row2','Dòng 2','=2x+2'],['row3','Dòng 3','=6']],['biến đổi','nhiều dòng']),
 p('nuclide','Ký hiệu nguyên tử / đồng vị',String.raw`{}_{[[Z]]}^{[[A]]}\mathrm{[[symbol]]}`,[['Z','Số hiệu nguyên tử Z','6'],['A','Số khối A','14'],['symbol','Ký hiệu nguyên tố','C']],['nguyên tử','đồng vị'],'chemistry'),
 p('unit','Đại lượng kèm đơn vị',String.raw`[[symbol]]=[[value]]\,\mathrm{[[unit]]}`,[['symbol','Đại lượng','v'],['value','Giá trị','10'],['unit','Đơn vị','m/s']],['đơn vị','SI'],'physics')
];
