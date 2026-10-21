// Curated teaching reference: grade tags are indicative, not a textbook pacing certificate.
export const CATALOG_SOURCES=[{id:'curriculum',title:'Danh mục chương trình GDPT 2018 – Bộ GD&ĐT, cổng trường công lập',url:'https://thcsminhduc.hcm.edu.vn/thong-tin-tu-bo-gddt/bo-gddt-cong-bo-chuong-trinh-giao-duc-pho-thong-moi/ctmb/91870/476970'},{id:'math-program',title:'Chương trình môn Toán 2018 – bản lưu Đại học Cần Thơ',url:'https://se.ctu.edu.vn/images/upload/thongbao/TT32.pdf'},{id:'physics',title:'OpenStax Physics – thuật ngữ và công thức nền tảng',url:'https://openstax.org/books/physics/pages/index'},{id:'physics12',title:'Hội thảo Vật lí 12 CT2018 – THCS/THPT Nguyễn Khuyến, 2024',url:'https://filethpt.hcm.edu.vn/data/doc/2024/thcs-thptnguyenkhuyen/2024_9/20/to-li-kh-hoi-thao-ngay-07092024-full_209202414.pdf'},{id:'chemistry',title:'OpenStax Chemistry 2e – tài liệu tham chiếu',url:'https://openstax.org/books/chemistry-2e/pages/1-introduction'},{id:'biology',title:'OpenStax Biology 2e – di truyền quần thể',url:'https://openstax.org/books/biology-2e/pages/19-1-population-evolution'}];
export const EXTRA_SUBJECTS=[{id:'science',name:'Khoa học / KHTN',symbol:'⚛',hint:'Khoa học tiểu học, Lý – Hóa – Sinh tích hợp',members:['physics','chemistry','biology','science']},{id:'geography',name:'Địa lí',symbol:'◎',hint:'Bản đồ, dân số, khí hậu và số liệu'},{id:'informatics',name:'Tin học',symbol:'01',hint:'Dữ liệu, bảng tính và thuật toán'},{id:'technology',name:'Công nghệ',symbol:'⚙',hint:'Kĩ thuật, điện và trồng trọt'},{id:'economics',name:'Kinh tế & tài chính',symbol:'₫',hint:'Ngân sách, lãi suất và hiệu quả'},{id:'history',name:'Lịch sử',symbol:'↔',hint:'Niên biểu và phân tích tư liệu'},{id:'civics',name:'Đạo đức / GDCD',symbol:'◇',hint:'Tình huống, quyền và trách nhiệm'},{id:'music',name:'Âm nhạc',symbol:'♪',hint:'Nhịp, trường độ và tiết tấu'},{id:'art',name:'Mĩ thuật',symbol:'◩',hint:'Tỉ lệ, bố cục và phân tích tác phẩm'},{id:'pe',name:'Giáo dục thể chất',symbol:'↗',hint:'Thời gian, tốc độ và kết quả vận động'},{id:'defence',name:'GDQP & an ninh',symbol:'▣',hint:'Khung câu hỏi nhận thức và an toàn'},{id:'languages',name:'Ngoại ngữ khác',symbol:'文',hint:'Mẫu từ vựng, hội thoại và cấu trúc ngôn ngữ'},{id:'experience',name:'Trải nghiệm / hướng nghiệp',symbol:'✧',hint:'Kế hoạch, khảo sát và tự đánh giá'}];
export function gradesOf(s){return [...new Set(String(s).split(',').flatMap(x=>{const [a,b]=x.split('-').map(Number);return b?Array.from({length:b-a+1},(_,i)=>a+i):[a];}))].sort((a,b)=>a-b);}
function rows(subject,source,body){return body.trim().split('\n').filter(s=>s.trim()&&!s.startsWith('//')).map(line=>{const [id,grade,topic,title,latex,note]=line.split('|');return {id:'f-'+id,subject,grades:gradesOf(grade),topic,title,latex,note,tags:[topic,title],sourceIds:[source],gradeBasis:'indicative',type:'formula'};});}
const M=String.raw;
export const CURRICULUM_CATALOG=[
...rows('math','math-program',M`
add|1-3|Số và phép tính|Phép cộng|a+b=c|a, b là các số hạng; c là tổng.
subtract|1-3|Số và phép tính|Phép trừ|a-b=c|a là số bị trừ; b là số trừ; c là hiệu.
compare|1-3|Số và phép tính|So sánh hai số|a<b,\quad a=b,\quad a>b|Chọn dấu phù hợp với hai số.
number-line|1-3|Số và phép tính|Số liền trước và liền sau|n-1,\quad n,\quad n+1|n là số tự nhiên; số liền trước chỉ xét khi n≥1.
missing-addend|1-4|Số và phép tính|Tìm số hạng chưa biết|x+a=b\Rightarrow x=b-a|Dùng cùng một đơn vị khi giải bài toán có lời văn.
missing-minuend|2-4|Số và phép tính|Tìm số bị trừ|x-a=b\Rightarrow x=b+a|Các số trong phạm vi học sinh đã học.
missing-subtrahend|2-4|Số và phép tính|Tìm số trừ|a-x=b\Rightarrow x=a-b|Trong số tự nhiên cần a≥b.
multiply|2-4|Số và phép tính|Phép nhân và tổng lặp|a\times n=\underbrace{a+\cdots+a}_{n\text{ lần}}|n là số tự nhiên dương; giải thích bằng nhóm đồ vật ở lớp nhỏ.
divide|2-4|Số và phép tính|Phép chia|a:b=c\Leftrightarrow a=b\times c|b≠0; dấu : là phép chia.
remainder|3-6|Số và phép tính|Chia có dư|a=bq+r,\quad 0\le r<b|a là số bị chia; b>0; q là thương; r là số dư.
commute|2-6|Số và phép tính|Tính chất giao hoán|a+b=b+a,\quad ab=ba|Áp dụng trong các tập số đã học.
associate|3-6|Số và phép tính|Tính chất kết hợp|(a+b)+c=a+(b+c)|Phép nhân có tính chất kết hợp tương tự.
distribute|4-8|Số và phép tính|Nhân phân phối đối với cộng|a(b+c)=ab+ac|Dùng để tính thuận tiện hoặc khai triển biểu thức.
find-factor|3-5|Số và phép tính|Tìm thừa số chưa biết|ax=b\Rightarrow x=b:a|a≠0.
find-dividend|3-5|Số và phép tính|Tìm số bị chia|x:a=b\Rightarrow x=ab|a≠0.
find-divisor|3-5|Số và phép tính|Tìm số chia|a:x=b\Rightarrow x=a:b|x≠0 và b≠0; kiểm tra lại phép chia.
sum-difference|4-5|Bài toán có lời văn|Tìm hai số biết tổng và hiệu|a=\frac{S+D}{2},\quad b=\frac{S-D}{2}|S là tổng, D≥0 là hiệu, a≥b; kết quả phải đúng phạm vi bài toán.
sum-ratio|4-6|Tỉ số và phần trăm|Tìm hai số biết tổng và tỉ số|a=\frac{mS}{m+n},\quad b=\frac{nS}{m+n}|a:b=m:n với m,n>0.
difference-ratio|4-6|Tỉ số và phần trăm|Tìm hai số biết hiệu và tỉ số|a=\frac{mD}{m-n},\quad b=\frac{nD}{m-n}|a:b=m:n, m>n>0, D=a−b.
mean-primary|4-7|Thống kê|Trung bình cộng|\bar{x}=\frac{x_1+\cdots+x_n}{n}|n>0; các giá trị phải cùng loại và cùng đơn vị.
fraction-equal|4-6|Phân số và số thập phân|Hai phân số bằng nhau|\frac ab=\frac cd\Leftrightarrow ad=bc|b,d≠0.
fraction-add|4-6|Phân số và số thập phân|Cộng phân số|\frac ab+\frac cd=\frac{ad+bc}{bd}|b,d≠0; có thể quy đồng theo mẫu chung nhỏ hơn bd.
fraction-subtract|4-6|Phân số và số thập phân|Trừ phân số|\frac ab-\frac cd=\frac{ad-bc}{bd}|b,d≠0.
fraction-multiply|4-6|Phân số và số thập phân|Nhân phân số|\frac ab\cdot\frac cd=\frac{ac}{bd}|b,d≠0; rút gọn kết quả khi cần.
fraction-divide|4-6|Phân số và số thập phân|Chia phân số|\frac ab:\frac cd=\frac{ad}{bc}|b,c,d≠0.
percent|5-9|Tỉ số và phần trăm|Tỉ số phần trăm|p=\frac ab\times100\%|b≠0; a,b cùng đơn vị.
percent-part|5-9|Tỉ số và phần trăm|Tìm phần trăm của một số|A=B\frac{p}{100}|p là số phần trăm, ví dụ nhập 15 khi tính 15%.
percent-original|5-9|Tỉ số và phần trăm|Tìm số gốc khi biết phần trăm|B=\frac{100A}{p}|p≠0; A bằng p% của B.
rectangle-perimeter|3-6|Hình học tiểu học|Chu vi hình chữ nhật|P=2(a+b)|a,b là chiều dài, chiều rộng; cùng đơn vị độ dài.
rectangle-area|3-6|Hình học tiểu học|Diện tích hình chữ nhật|S=ab|a,b cùng đơn vị; S dùng đơn vị diện tích.
square-perimeter|3-6|Hình học tiểu học|Chu vi hình vuông|P=4a|a>0 là cạnh hình vuông.
square-area|3-6|Hình học tiểu học|Diện tích hình vuông|S=a^2|a>0; đơn vị diện tích là bình phương đơn vị cạnh.
triangle-area|5-8|Hình học phẳng|Diện tích tam giác theo đáy và chiều cao|S=\frac12 ah|h là chiều cao ứng với đáy a.
parallelogram-area|4-8|Hình học phẳng|Diện tích hình bình hành|S=ah|h vuông góc với đáy a.
rhombus-area|4-8|Hình học phẳng|Diện tích hình thoi|S=\frac12 d_1d_2|d₁,d₂ là hai đường chéo.
trapezoid-area|5-8|Hình học phẳng|Diện tích hình thang|S=\frac{(a+b)h}{2}|a,b là hai đáy song song, h là khoảng cách giữa hai đáy.
circle-length|5-9|Đường tròn|Chu vi đường tròn|C=2\pi r=\pi d|d=2r; π là hằng số, dùng độ chính xác theo đề.
circle-area|5-9|Đường tròn|Diện tích hình tròn|S=\pi r^2|r>0 là bán kính.
box-volume|5-8|Hình không gian|Thể tích hình hộp chữ nhật|V=abc|Ba kích thước cùng đơn vị.
box-surface|5-8|Hình không gian|Diện tích toàn phần hình hộp chữ nhật|S=2(ab+bc+ca)|a,b,c là ba kích thước của hình hộp chữ nhật.
cube-volume|5-8|Hình không gian|Thể tích hình lập phương|V=a^3|a>0 là cạnh.
cube-surface|5-8|Hình không gian|Diện tích toàn phần hình lập phương|S=6a^2|a>0; có sáu mặt vuông bằng nhau.
unit-length|2-6|Đo lường và đơn vị|Đổi đơn vị độ dài|1\,\mathrm{km}=1000\,\mathrm{m},\quad1\,\mathrm{m}=100\,\mathrm{cm}|Hai đơn vị liền kề trong dãy km,hm,dam,m,dm,cm,mm hơn kém 10 lần.
unit-area|4-6|Đo lường và đơn vị|Đổi đơn vị diện tích|1\,\mathrm{m}^2=100\,\mathrm{dm}^2=10000\,\mathrm{cm}^2|Hai đơn vị diện tích liền kề hơn kém 100 lần.
unit-volume|5-7|Đo lường và đơn vị|Đổi đơn vị thể tích và dung tích|1\,\mathrm{m}^3=1000\,\mathrm{dm}^3,\quad1\,\mathrm{L}=1\,\mathrm{dm}^3|1 mL=1 cm³; phân biệt thể tích với diện tích.
unit-time|2-6|Đo lường và đơn vị|Đổi giờ, phút và giây|1\,\mathrm{h}=60\,\mathrm{min}=3600\,\mathrm{s}|Đơn vị thời gian không đổi theo cơ số 10.
unit-mass|2-6|Đo lường và đơn vị|Đổi đơn vị khối lượng|1\,\mathrm{t}=1000\,\mathrm{kg},\quad1\,\mathrm{kg}=1000\,\mathrm{g}|t là tấn; kiểm tra cách dùng kí hiệu trong đề.
distance|5-7|Chuyển động|Quãng đường trong chuyển động đều|s=vt|v không đổi; s,v,t dùng đơn vị tương thích.
meeting|5-7|Chuyển động|Hai vật chuyển động ngược chiều gặp nhau|t=\frac{s}{v_1+v_2}|Khởi hành đồng thời, khoảng cách đầu s, tốc độ dương và không đổi.
catchup|5-7|Chuyển động|Hai vật cùng chiều đuổi kịp|t=\frac{s}{v_1-v_2}|Vật sau nhanh hơn: v₁>v₂; s là khoảng cách ban đầu.
work-rate|5-9|Bài toán có lời văn|Làm chung một công việc|\frac1T=\frac1{t_1}+\frac1{t_2}|Hai bên cùng làm với năng suất không đổi, công việc được chuẩn hóa bằng 1.
integer-sign|6-7|Số và phép tính|Tích và thương các số cùng dấu, khác dấu|(-a)(-b)=ab,\quad(-a)b=-(ab)|Dùng để giải thích quy tắc dấu; a,b>0 khi minh họa.
absolute|6-9|Số và phép tính|Giá trị tuyệt đối|\lvert x\rvert=\begin{cases}x&x\ge0\\-x&x<0\end{cases}|Khoảng cách từ x đến 0 trên trục số.
power-product|6-9|Lũy thừa và căn|Nhân hai lũy thừa cùng cơ số|a^ma^n=a^{m+n}|m,n là số tự nhiên; các điều kiện mở rộng tùy tập số.
power-quotient|6-9|Lũy thừa và căn|Chia hai lũy thừa cùng cơ số|\frac{a^m}{a^n}=a^{m-n}|a≠0; với số mũ tự nhiên thường xét m≥n.
power-power|6-9|Lũy thừa và căn|Lũy thừa của lũy thừa|(a^m)^n=a^{mn}|Mẫu số mũ nguyên; số mũ thực cần thêm điều kiện cơ số.
proportion|6-8|Tỉ lệ thức|Tính chất tỉ lệ thức|\frac ab=\frac cd\Rightarrow ad=bc|b,d≠0.
direct|7-9|Tỉ lệ thức|Hai đại lượng tỉ lệ thuận|y=kx|k≠0; giữ đơn vị và hệ số tỉ lệ nhất quán.
inverse|7-9|Tỉ lệ thức|Hai đại lượng tỉ lệ nghịch|xy=k\quad\Leftrightarrow\quad y=\frac{k}{x}|k≠0, x≠0.
triangle-angles|7-9|Hình học phẳng|Tổng ba góc tam giác|A+B+C=180^\circ|A,B,C là số đo ba góc trong của tam giác phẳng.
exterior-angle|7-9|Hình học phẳng|Góc ngoài tam giác|A_{\text{ngoài}}=B+C|Góc ngoài tại đỉnh A không kề với hai góc B,C.
pythagoras|8-10|Hình học phẳng|Định lí Pythagore|a^2+b^2=c^2|Chỉ dùng khi tam giác vuông, c là cạnh huyền.
identity-square-sum|8-10|Hằng đẳng thức|(a+b) bình phương|(a+b)^2=a^2+2ab+b^2|Đúng với các số thực a,b.
identity-square-diff|8-10|Hằng đẳng thức|(a−b) bình phương|(a-b)^2=a^2-2ab+b^2|Đúng với các số thực a,b.
identity-diff-squares|8-10|Hằng đẳng thức|Hiệu hai bình phương|a^2-b^2=(a-b)(a+b)|Ứng dụng phân tích thành nhân tử.
identity-cube-sum|8-10|Hằng đẳng thức|(a+b) lập phương|(a+b)^3=a^3+3a^2b+3ab^2+b^3|Có thể dùng Pascal để nhớ hệ số.
identity-cube-diff|8-10|Hằng đẳng thức|(a−b) lập phương|(a-b)^3=a^3-3a^2b+3ab^2-b^3|Kiểm tra dấu các hạng tử.
identity-sum-cubes|8-10|Hằng đẳng thức|Tổng hai lập phương|a^3+b^3=(a+b)(a^2-ab+b^2)|Đúng với các số thực a,b.
identity-diff-cubes|8-10|Hằng đẳng thức|Hiệu hai lập phương|a^3-b^3=(a-b)(a^2+ab+b^2)|Đúng với các số thực a,b.
linear-equation|8-10|Phương trình|Phương trình bậc nhất một ẩn|ax+b=0\Rightarrow x=-\frac ba|a≠0; nếu a=0 phải xét riêng b.
linear-function|9-10|Hàm số|Hàm số bậc nhất|y=ax+b|a≠0; a là hệ số góc.
roots|9-10|Lũy thừa và căn|Căn bậc hai của bình phương|\sqrt{a^2}=\lvert a\rvert|Không thay bằng a khi chưa biết dấu a.
root-product|9-10|Lũy thừa và căn|Căn của một tích|\sqrt{ab}=\sqrt a\sqrt b|Trong số thực, a,b≥0.
root-quotient|9-10|Lũy thừa và căn|Căn của một thương|\sqrt{\frac ab}=\frac{\sqrt a}{\sqrt b}|a≥0, b>0.
rationalize|9-10|Lũy thừa và căn|Trục căn thức ở mẫu|\frac1{\sqrt a+\sqrt b}=\frac{\sqrt a-\sqrt b}{a-b}|a,b≥0 và a≠b; trường hợp a=b phải xử lí riêng.
quadratic-discriminant|9-10|Phương trình|Biệt thức phương trình bậc hai|\Delta=b^2-4ac|a≠0; Δ>0 hai nghiệm thực, Δ=0 nghiệm kép, Δ<0 không có nghiệm thực.
vieta|9-10|Phương trình|Hệ thức Viète|x_1+x_2=-\frac ba,\quad x_1x_2=\frac ca|a≠0; x₁,x₂ là hai nghiệm kể cả nghiệm kép khi tồn tại.
trig-right|9-10|Lượng giác|Tỉ số lượng giác trong tam giác vuông|\sin\alpha=\frac{a}{c},\quad\cos\alpha=\frac{b}{c},\quad\tan\alpha=\frac ab|a đối diện góc α, b kề góc α, c cạnh huyền; α nhọn.
trig-pythag|9-11|Lượng giác|Hệ thức lượng giác cơ bản|\sin^2x+\cos^2x=1|x là góc/số thực với đơn vị góc nhất quán.
inscribed-angle|9-10|Đường tròn|Góc nội tiếp và góc ở tâm|\widehat{AOB}=2\widehat{ACB}|Hai góc cùng chắn cung AB; C nằm trên cung còn lại.
arc-length|9-10|Đường tròn|Độ dài cung tròn|l=\frac{\pi rn}{180}|n là số đo góc ở tâm tính bằng độ.
sector-area|9-10|Đường tròn|Diện tích hình quạt|S=\frac{\pi r^2n}{360}|n tính bằng độ, 0≤n≤360.
cylinder|9-12|Hình không gian|Hình trụ: thể tích và diện tích xung quanh|V=\pi r^2h,\quad S_{xq}=2\pi rh|Hình trụ tròn xoay; h là chiều cao.
cone|9-12|Hình không gian|Hình nón: thể tích và diện tích xung quanh|V=\frac13\pi r^2h,\quad S_{xq}=\pi rl|l là đường sinh; hình nón tròn xoay l²=r²+h².
sphere|9-12|Hình không gian|Hình cầu: diện tích và thể tích|S=4\pi r^2,\quad V=\frac43\pi r^3|r>0; S là diện tích mặt cầu.
sine-rule|10-11|Tam giác và vectơ|Định lí sin|\frac a{\sin A}=\frac b{\sin B}=\frac c{\sin C}=2R|a,b,c đối diện các góc A,B,C; R là bán kính đường tròn ngoại tiếp.
cosine-rule|10-11|Tam giác và vectơ|Định lí cosin|a^2=b^2+c^2-2bc\cos A|A là góc xen giữa hai cạnh b,c.
triangle-trig-area|10-11|Tam giác và vectơ|Diện tích tam giác theo hai cạnh và góc|S=\frac12bc\sin A|A là góc xen giữa b,c.
heron|10-11|Tam giác và vectơ|Công thức Heron|S=\sqrt{p(p-a)(p-b)(p-c)},\quad p=\frac{a+b+c}{2}|a,b,c thỏa bất đẳng thức tam giác.
triangle-inradius|10-11|Tam giác và vectơ|Diện tích tam giác theo bán kính nội tiếp|S=pr|p là nửa chu vi, r là bán kính nội tiếp.
vector-coordinates|10-12|Tọa độ|Tọa độ vectơ trong mặt phẳng|\overrightarrow{AB}=(x_B-x_A;y_B-y_A)|Trong hệ tọa độ Oxy.
vector-dot|10-12|Tọa độ|Tích vô hướng vectơ|\vec a\cdot\vec b=a_1b_1+a_2b_2|Trong hệ trục trực chuẩn; 3D thêm a₃b₃.
vector-angle|10-12|Tọa độ|Góc giữa hai vectơ|\cos\theta=\frac{\vec a\cdot\vec b}{\lVert\vec a\rVert\lVert\vec b\rVert}|Hai vectơ đều khác vectơ không.
point-distance|10-12|Tọa độ|Khoảng cách hai điểm trong Oxy|AB=\sqrt{(x_B-x_A)^2+(y_B-y_A)^2}|Trong hệ trục trực chuẩn.
midpoint|10-12|Tọa độ|Tọa độ trung điểm|M\left(\frac{x_A+x_B}{2};\frac{y_A+y_B}{2}\right)|M là trung điểm của đoạn AB.
line-plane|10-12|Tọa độ|Phương trình đường thẳng tổng quát|ax+by+c=0|a²+b²>0; (a,b) là vectơ pháp tuyến.
point-line|10-12|Tọa độ|Khoảng cách từ điểm đến đường thẳng|d=\frac{\lvert ax_0+by_0+c\rvert}{\sqrt{a^2+b^2}}|a²+b²>0, điểm M(x₀,y₀).
circle-coordinate|10-12|Tọa độ|Phương trình đường tròn|(x-a)^2+(y-b)^2=R^2|Tâm I(a,b), bán kính R>0.
parabola|10-11|Ba đường conic|Parabol chính tắc|y^2=2px|p>0; tiêu điểm F(p/2,0).
ellipse|10-11|Ba đường conic|Elip chính tắc|\frac{x^2}{a^2}+\frac{y^2}{b^2}=1|a>b>0; c²=a²−b².
hyperbola|10-11|Ba đường conic|Hyperbol chính tắc|\frac{x^2}{a^2}-\frac{y^2}{b^2}=1|a,b>0; c²=a²+b².
permutation|10-12|Tổ hợp và xác suất|Hoán vị|P_n=n!|n là số nguyên không âm; 0!=1.
arrangement|10-12|Tổ hợp và xác suất|Chỉnh hợp|A_n^k=\frac{n!}{(n-k)!}|0≤k≤n; có xét thứ tự, không lặp.
combination|10-12|Tổ hợp và xác suất|Tổ hợp|C_n^k=\binom nk=\frac{n!}{k!(n-k)!}|0≤k≤n; không xét thứ tự, không lặp.
binomial|10-12|Tổ hợp và xác suất|Nhị thức Newton|(a+b)^n=\sum_{k=0}^{n}\binom nk a^{n-k}b^k|n là số nguyên không âm.
prob-add|10-12|Tổ hợp và xác suất|Xác suất của hợp hai biến cố|P(A\cup B)=P(A)+P(B)-P(A\cap B)|Không bỏ phần giao nếu hai biến cố không xung khắc.
prob-complement|10-12|Tổ hợp và xác suất|Biến cố đối|P(\overline A)=1-P(A)|A và biến cố đối phân hoạch không gian mẫu.
arithmetic-term|11-12|Dãy số|Số hạng cấp số cộng|u_n=u_1+(n-1)d|n≥1, d là công sai.
arithmetic-sum|11-12|Dãy số|Tổng cấp số cộng|S_n=\frac n2(u_1+u_n)|n≥1.
geometric-term|11-12|Dãy số|Số hạng cấp số nhân|u_n=u_1q^{n-1}|n≥1, q là công bội.
geometric-sum|11-12|Dãy số|Tổng cấp số nhân hữu hạn|S_n=u_1\frac{1-q^n}{1-q}|q≠1; nếu q=1 thì Sₙ=nu₁.
infinite-geometric|11-12|Giới hạn|Tổng cấp số nhân lùi vô hạn|S=\frac{u_1}{1-q}|Chỉ khi giá trị tuyệt đối của q nhỏ hơn 1.
trig-add|11-12|Lượng giác|Sin và cos của tổng|\sin(a+b)=\sin a\cos b+\cos a\sin b|cos(a+b)=cos a cos b−sin a sin b; dùng nhất quán đơn vị góc.
trig-double|11-12|Lượng giác|Công thức góc nhân đôi|\sin2x=2\sin x\cos x,\quad\cos2x=1-2\sin^2x|Có các dạng tương đương cos²x−sin²x hoặc 2cos²x−1.
trig-sum-product|11-12|Lượng giác|Biến đổi tổng thành tích|\sin a+\sin b=2\sin\frac{a+b}{2}\cos\frac{a-b}{2}|Đúng với mọi a,b thực.
trig-equation-sin|11-12|Phương trình lượng giác|Nghiệm sin x = sin α|x=\alpha+2k\pi\quad\text{hoặc}\quad x=\pi-\alpha+2k\pi|k∈ℤ; mẫu dùng radian.
trig-equation-cos|11-12|Phương trình lượng giác|Nghiệm cos x = cos α|x=\pm\alpha+2k\pi|k∈ℤ; mẫu dùng radian.
trig-equation-tan|11-12|Phương trình lượng giác|Nghiệm tan x = tan α|x=\alpha+k\pi|k∈ℤ; tan α phải xác định.
exp-rules|11-12|Mũ và logarit|Lũy thừa với số mũ thực|a^xa^y=a^{x+y},\quad(a^x)^y=a^{xy}|a>0.
log-definition|11-12|Mũ và logarit|Định nghĩa logarit|\log_a b=c\Leftrightarrow a^c=b|a>0, a≠1, b>0.
log-product|11-12|Mũ và logarit|Logarit tích và thương|\log_a(xy)=\log_a x+\log_a y|a>0, a≠1; x,y>0. Thương dùng hiệu logarit.
log-power|11-12|Mũ và logarit|Logarit của lũy thừa|\log_a(x^r)=r\log_a x|a>0, a≠1, x>0.
log-base|11-12|Mũ và logarit|Đổi cơ số logarit|\log_a b=\frac{\log_c b}{\log_c a}|a,c>0; a,c≠1; b>0.
limit-derivative|11-12|Đạo hàm|Định nghĩa đạo hàm|f'(x)=\lim_{h\to0}\frac{f(x+h)-f(x)}h|Giới hạn phải tồn tại hữu hạn.
derivative-power|11-12|Đạo hàm|Đạo hàm hàm lũy thừa|(x^n)'=nx^{n-1}|Xét miền xác định và số mũ phù hợp.
derivative-product|11-12|Đạo hàm|Đạo hàm tích|(uv)'=u'v+uv'|u,v khả vi tại điểm đang xét.
derivative-quotient|11-12|Đạo hàm|Đạo hàm thương|\left(\frac uv\right)'=\frac{u'v-uv'}{v^2}|v≠0; u,v khả vi.
derivative-chain|11-12|Đạo hàm|Đạo hàm hàm hợp|[f(u(x))]'=f'(u(x))u'(x)|Các hàm thành phần khả vi.
derivative-trig|11-12|Đạo hàm|Đạo hàm sin, cos, tan|(\sin x)'=\cos x,\quad(\cos x)'=-\sin x,\quad(\tan x)'=\frac1{\cos^2x}|x tính bằng radian; công thức tan cần cos x≠0.
derivative-exp|11-12|Đạo hàm|Đạo hàm hàm mũ và logarit|(e^x)'=e^x,\quad(a^x)'=a^x\ln a,\quad(\ln x)'=\frac1x|a>0; công thức ln x dùng x>0.
tangent|11-12|Đạo hàm|Phương trình tiếp tuyến đồ thị|y=f'(x_0)(x-x_0)+f(x_0)|Hàm khả vi tại x₀.
prism|11-12|Hình không gian|Thể tích lăng trụ|V=Bh|B là diện tích đáy, h là khoảng cách giữa hai mặt đáy.
pyramid|11-12|Hình không gian|Thể tích khối chóp|V=\frac13Bh|B là diện tích đáy; h vuông góc với mặt đáy.
integral-power|12|Nguyên hàm và tích phân|Nguyên hàm lũy thừa|\int x^n\,dx=\frac{x^{n+1}}{n+1}+C|n≠−1; xét trên một khoảng thuộc miền xác định.
integral-log|12|Nguyên hàm và tích phân|Nguyên hàm 1/x|\int\frac1x\,dx=\ln\lvert x\rvert+C|x≠0; xét trên khoảng không chứa 0.
integral-elementary|12|Nguyên hàm và tích phân|Nguyên hàm sin, cos, hàm mũ|\int\sin x\,dx=-\cos x+C,\quad\int\cos x\,dx=\sin x+C|x dùng radian; ∫eˣdx=eˣ+C.
newton-leibniz|12|Nguyên hàm và tích phân|Newton–Leibniz|\int_a^b f(x)\,dx=F(b)-F(a)|F là nguyên hàm của f liên tục trên [a,b].
area-integral|12|Nguyên hàm và tích phân|Diện tích giữa hai đồ thị|S=\int_a^b\lvert f(x)-g(x)\rvert\,dx|f,g liên tục; xác định đúng các điểm giao và khoảng tích phân.
revolution-volume|12|Nguyên hàm và tích phân|Thể tích tròn xoay quanh Ox|V=\pi\int_a^b[f(x)]^2\,dx|Miền giới hạn bởi y=f(x), Ox, x=a, x=b quay quanh Ox.
point-distance3|12|Tọa độ không gian|Khoảng cách hai điểm Oxyz|AB=\sqrt{(x_B-x_A)^2+(y_B-y_A)^2+(z_B-z_A)^2}|Hệ trục trực chuẩn; các tọa độ cùng đơn vị.
plane3|12|Tọa độ không gian|Phương trình mặt phẳng|Ax+By+Cz+D=0|A²+B²+C²>0; (A,B,C) là vectơ pháp tuyến.
point-plane3|12|Tọa độ không gian|Khoảng cách điểm đến mặt phẳng|d=\frac{\lvert Ax_0+By_0+Cz_0+D\rvert}{\sqrt{A^2+B^2+C^2}}|M(x₀,y₀,z₀); pháp tuyến khác không.
line3|12|Tọa độ không gian|Phương trình tham số đường thẳng|\begin{cases}x=x_0+at\\y=y_0+bt\\z=z_0+ct\end{cases}|Vectơ chỉ phương (a,b,c) khác không; t∈ℝ.
sphere3|12|Tọa độ không gian|Phương trình mặt cầu|(x-a)^2+(y-b)^2+(z-c)^2=R^2|Tâm (a,b,c), R>0.
conditional|12|Xác suất có điều kiện|Định nghĩa xác suất có điều kiện|P(A\mid B)=\frac{P(A\cap B)}{P(B)}|P(B)>0.
total-prob|12|Xác suất có điều kiện|Công thức xác suất toàn phần|P(A)=P(A\mid B)P(B)+P(A\mid\overline B)P(\overline B)|0<P(B)<1; B và biến cố đối tạo thành phân hoạch.
bayes|12|Xác suất có điều kiện|Công thức Bayes|P(B\mid A)=\frac{P(A\mid B)P(B)}{P(A)}|P(A)>0; các xác suất có điều kiện sử dụng phải xác định.
variance|10-12|Thống kê|Phương sai mẫu số liệu|s^2=\frac1n\sum_{i=1}^n(x_i-\bar x)^2|Quy ước phương sai mô tả phổ thông chia n; không nhầm ước lượng chia n−1.
stddev|10-12|Thống kê|Độ lệch chuẩn|s=\sqrt{s^2}|Cùng đơn vị với dữ liệu gốc, khác đơn vị của phương sai.
weighted-mean|10-12|Thống kê|Trung bình có tần số|\bar x=\frac{\sum n_ix_i}{\sum n_i}|Với số liệu ghép nhóm, xᵢ là giá trị đại diện nhóm, chỉ là gần đúng.
quartile-iqr|10-12|Thống kê|Khoảng tứ phân vị|\Delta_Q=Q_3-Q_1|Tứ phân vị được xác định theo quy ước của chương trình/bộ sách.
`),
];
CURRICULUM_CATALOG.push(...rows('physics','physics',M`
p-speedavg|7,10|Chuyển động|Tốc độ trung bình|v_{tb}=\frac{s_{\text{tổng}}}{t_{\text{tổng}}}|s là tổng quãng đường, t là tổng thời gian; không lấy trung bình cộng tốc độ tùy tiện.
p-velocityavg|10|Chuyển động|Vận tốc trung bình|\vec v_{tb}=\frac{\Delta\vec r}{\Delta t}|Dùng độ dịch chuyển, khác tổng quãng đường; đơn vị m/s.
p-accel|10|Chuyển động|Gia tốc trung bình|\vec a_{tb}=\frac{\Delta\vec v}{\Delta t}|Δt>0; đơn vị m/s².
p-uniform|10|Chuyển động|Phương trình chuyển động thẳng đều|x=x_0+vt|Chọn gốc thời gian, gốc tọa độ và chiều dương.
p-vconsta|10|Chuyển động|Vận tốc trong chuyển động gia tốc không đổi|v=v_0+at|Các đại lượng là thành phần đại số trên trục đã chọn.
p-xconsta|10|Chuyển động|Độ dịch chuyển khi gia tốc không đổi|s=v_0t+\frac12at^2|s là độ dịch chuyển đại số; a không đổi.
p-consta-identity|10|Chuyển động|Hệ thức độc lập thời gian|v^2-v_0^2=2as|Chuyển động thẳng có gia tốc không đổi.
p-freefall|10|Chuyển động|Rơi tự do từ trạng thái nghỉ|v=gt,\quad h=\frac12gt^2|Bỏ sức cản, g không đổi; chiều dương hướng xuống.
p-horizontal|10|Chuyển động|Ném ngang: thời gian rơi và tầm xa|t=\sqrt{\frac{2h}{g}},\quad L=v_0\sqrt{\frac{2h}{g}}|Vật được ném ngang ở độ cao h, bỏ sức cản.
p-relative|10|Chuyển động|Cộng vận tốc|\vec v_{13}=\vec v_{12}+\vec v_{23}|Các vận tốc được quy về cùng thời điểm và hệ quy chiếu tương ứng.
p-circular|10|Chuyển động tròn|Tốc độ góc và chu kì|\omega=\frac{2\pi}{T}=2\pi f|T tính bằng s, f bằng Hz, ω bằng rad/s.
p-circle-speed|10|Chuyển động tròn|Tốc độ dài và gia tốc hướng tâm|v=\omega r,\quad a_{ht}=\frac{v^2}{r}=\omega^2r|Chuyển động tròn đều, r>0.
p-weight|6,8,10|Lực và cân bằng|Trọng lực gần mặt đất|P=mg|m (kg), g (m/s²), P (N); g theo đề, không luôn lấy 10.
p-friction|10|Lực và cân bằng|Lực ma sát trượt|F_{mst}=\mu_tN|N là phản lực pháp tuyến; không đồng nhất N=mg trong mọi trường hợp.
p-hooke|10|Lực và cân bằng|Định luật Hooke|F=k\lvert\Delta l\rvert|Trong giới hạn đàn hồi; k (N/m), Δl (m).
p-centripetal|10|Lực và cân bằng|Hợp lực hướng tâm|F_{ht}=m\frac{v^2}{r}|Đây là hợp lực hướng tâm, không nhất thiết là một lực riêng biệt.
p-moment|8,10|Lực và cân bằng|Moment lực|M=Fd|d là khoảng cách vuông góc từ trục quay đến giá của lực; đơn vị N·m.
p-lever|8,10|Lực và cân bằng|Cân bằng đòn bẩy|F_1d_1=F_2d_2|Hai moment ngược chiều; điều kiện cân bằng tĩnh và các lực khác đã xét đủ.
p-density|6,8|Chất và áp suất|Khối lượng riêng|\rho=\frac mV|m (kg), V (m³), ρ (kg/m³); V>0.
p-pressure|8|Chất và áp suất|Áp suất|p=\frac FS|F là áp lực vuông góc lên diện tích S; p (Pa).
p-fluid|8|Chất và áp suất|Áp suất chất lỏng|p=p_0+\rho gh|Chất lỏng đứng yên, ρ và g gần như không đổi; phân biệt áp suất tổng và phần tăng ρgh.
p-buoyancy|8|Chất và áp suất|Lực đẩy Archimedes|F_A=\rho_{\text{lỏng}}gV_{\text{chìm}}|V chìm là thể tích phần chất lỏng bị chiếm chỗ.
p-work|9-10|Công và năng lượng|Công của lực không đổi|A=Fs\cos\alpha|α là góc giữa lực và độ dịch chuyển; A (J).
p-power|9-10|Công và năng lượng|Công suất trung bình|\mathcal P=\frac At|A (J), t (s), công suất (W); t>0.
p-gravenergy|9-10|Công và năng lượng|Thế năng trọng trường|W_t=mgh|Mốc thế năng do người giải chọn; gần mặt đất, g không đổi.
p-springenergy|10-11|Công và năng lượng|Thế năng đàn hồi|W_t=\frac12k(\Delta l)^2|Lò xo tuân theo Hooke; Δl tính từ vị trí không biến dạng.
p-mechanical|10-11|Công và năng lượng|Cơ năng và bảo toàn|W=W_{\text{đ}}+W_t=\text{hằng số}|Chỉ bảo toàn khi chỉ có lực thế sinh công hoặc công lực không thế bằng 0.
p-work-energy|10|Công và năng lượng|Định lí động năng|A_{\text{hợp lực}}=\Delta W_{\text{đ}}|Tổng công các lực bằng độ biến thiên động năng.
p-efficiency|9-10|Công và năng lượng|Hiệu suất|H=\frac{E_{\text{ích}}}{E_{\text{vào}}}\times100\%|E vào>0; dùng cùng loại năng lượng và cùng đơn vị.
p-momentum|10|Động lượng|Động lượng|\vec p=m\vec v|m (kg), v (m/s); động lượng có hướng.
p-impulse|10|Động lượng|Xung lượng và biến thiên động lượng|\Delta\vec p=\vec F_{tb}\Delta t|Ftb là lực trung bình trong khoảng thời gian.
p-conserve-momentum|10|Động lượng|Bảo toàn động lượng|\sum\vec p_{\text{trước}}=\sum\vec p_{\text{sau}}|Hệ cô lập hoặc tổng xung lượng ngoại lực không đáng kể.
p-shm|11|Dao động|Li độ dao động điều hòa|x=A\cos(\omega t+\varphi)|A≥0; x đo từ vị trí cân bằng, pha tính bằng radian.
p-shm-v|11|Dao động|Vận tốc dao động điều hòa|v=-A\omega\sin(\omega t+\varphi)|Cùng quy ước pha với x=A cos(ωt+φ).
p-shm-a|11|Dao động|Gia tốc dao động điều hòa|a=-\omega^2x|Gia tốc luôn hướng về vị trí cân bằng.
p-spring-period|11|Dao động|Chu kì con lắc lò xo|T=2\pi\sqrt{\frac mk}|Lò xo lí tưởng, ma sát bỏ qua; m (kg), k (N/m).
p-pendulum-period|11|Dao động|Chu kì con lắc đơn góc nhỏ|T=2\pi\sqrt{\frac lg}|Chỉ với góc nhỏ, bỏ ma sát, g không đổi.
p-shm-energy|11|Dao động|Cơ năng dao động điều hòa|E=\frac12m\omega^2A^2|Dao động không tắt dần, khối lượng không đổi.
p-wave-phase|11|Sóng|Độ lệch pha trên phương truyền sóng|\Delta\varphi=\frac{2\pi d}{\lambda}|Hai điểm cách nhau d theo phương truyền của sóng điều hòa.
p-wave-equation|11|Sóng|Phương trình sóng truyền theo chiều dương|u=A\cos\left(\omega t-\frac{2\pi x}{\lambda}+\varphi\right)|Mô hình sóng điều hòa không suy giảm; xác định rõ chiều truyền.
p-interference|11|Sóng|Giao thoa hai nguồn cùng pha|\Delta d=k\lambda\quad\text{(cực đại)}|Cực tiểu: Δd=(k+1/2)λ; hai nguồn kết hợp cùng pha.
p-standing|11|Sóng|Sóng dừng trên dây hai đầu cố định|l=k\frac{\lambda}{2}|k=1,2,…; hai đầu đều là nút.
p-standing-open|11|Sóng|Dây một đầu nút, một đầu bụng|l=(2k+1)\frac{\lambda}{4}|k=0,1,…; mô hình biên lí tưởng.
p-young|11|Sóng ánh sáng|Giao thoa khe Young|i=\frac{\lambda D}{a}|Ánh sáng đơn sắc; D≫a, góc nhỏ; cùng đơn vị độ dài.
p-soundlevel|11|Sóng|Mức cường độ âm|L=10\log_{10}\frac I{I_0}|L (dB), I₀ là cường độ chuẩn; không cộng trực tiếp mức dB như năng lượng.
p-coulomb|11|Điện trường|Lực Coulomb|F=k\frac{\lvert q_1q_2\rvert}{r^2}|Điện tích điểm đứng yên trong chân không; k≈8,99×10⁹ N·m²/C².
p-electricfield|11|Điện trường|Cường độ điện trường|\vec E=\frac{\vec F}{q}|q≠0 là điện tích thử; E (N/C hoặc V/m).
p-pointfield|11|Điện trường|Điện trường điện tích điểm|E=k\frac{\lvert Q\rvert}{r^2}|Chân không; xác định chiều theo dấu Q.
p-potential|11|Điện trường|Hiệu điện thế và công|U_{AB}=\frac{A_{AB}}q|Công của lực điện khi điện tích q đi từ A đến B; q≠0.
p-uniformfield|11|Điện trường|Điện trường đều giữa hai bản|E=\frac Ud|U là độ lớn hiệu điện thế, d khoảng cách; bỏ hiệu ứng mép.
p-capacitance|11|Tụ điện|Điện dung|C=\frac QU|Q là độ lớn điện tích một bản; U≠0; C (F).
p-cap-energy|11|Tụ điện|Năng lượng điện trường tụ điện|W=\frac12CU^2=\frac{Q^2}{2C}|Tụ tuyến tính, C>0.
p-current|8-9,11|Dòng điện|Cường độ dòng điện trung bình|I=\frac{\Delta q}{\Delta t}|Δq là điện lượng qua tiết diện; I (A), Δt>0.
p-resistance|9,11|Dòng điện|Điện trở dây dẫn|R=\rho\frac lS|Dây đồng chất, tiết diện đều; ρ là điện trở suất (Ω·m), phụ thuộc nhiệt độ.
p-series|9,11|Dòng điện|Điện trở nối tiếp|R_{td}=R_1+R_2+\cdots+R_n|Cùng dòng điện đi qua các điện trở.
p-parallel|9,11|Dòng điện|Điện trở song song|\frac1{R_{td}}=\frac1{R_1}+\frac1{R_2}+\cdots+\frac1{R_n}|Các điện trở có cùng hiệu điện thế; Ri>0.
p-electric-energy|9,11|Dòng điện|Điện năng tiêu thụ|A=UIt=Pt|U,I không đổi; 1 kWh=3,6×10⁶ J.
p-joule|9,11|Dòng điện|Nhiệt Joule–Lenz|Q=I^2Rt|Điện trở thuần, dòng điện không đổi, bỏ thay đổi R do nhiệt nếu đề cho phép.
p-source|11|Dòng điện|Nguồn điện có điện trở trong|I=\frac{\mathcal E}{R+r}|Mạch kín đơn giản nguồn suất điện động ℰ, điện trở ngoài R và trong r.
p-terminal|11|Dòng điện|Hiệu điện thế hai cực nguồn phát điện|U=\mathcal E-Ir|Nguồn đang phát điện, chiều dòng điện theo quy ước.
p-temperature|12|Vật lí nhiệt|Đổi Celsius và Kelvin|T=t+273.15|T (K), t (°C); trong bài làm tròn có thể dùng 273 theo đề.
p-specificheat|8,12|Vật lí nhiệt|Nhiệt lượng khi đổi nhiệt độ|Q=mc\Delta T|Không chuyển thể; c coi không đổi; c (J/(kg·K)).
p-latent|12|Vật lí nhiệt|Nhiệt lượng chuyển thể|Q=mL|L (J/kg) là nhiệt nóng chảy hoặc hóa hơi riêng tại điều kiện đang xét.
p-first-law|12|Vật lí nhiệt|Nguyên lí I nhiệt động lực học|\Delta U=Q+A_{\text{nhận}}|Quy ước Q>0 khi hệ nhận nhiệt, A nhận>0 khi ngoại lực thực hiện công lên hệ.
p-boyles|12|Khí lí tưởng|Định luật Boyle|pV=\text{hằng số}|Một lượng khí lí tưởng cố định, nhiệt độ tuyệt đối không đổi.
p-charles|12|Khí lí tưởng|Định luật Charles|\frac VT=\text{hằng số}|Một lượng khí lí tưởng cố định, áp suất không đổi; T (K).
p-gasstate|12|Khí lí tưởng|Phương trình trạng thái khí lí tưởng|pV=nRT|SI: p (Pa), V (m³), T (K), n (mol), R≈8,314 J/(mol·K).
p-gas-kinetic|12|Khí lí tưởng|Áp suất theo mô hình động học|p=\frac13\frac NVm\overline{v^2}|m là khối lượng một phân tử, N số phân tử, V thể tích.
p-kinetic-temp|12|Khí lí tưởng|Động năng tịnh tiến trung bình phân tử|\overline E_k=\frac32k_BT|Khí lí tưởng đơn nguyên tử hoặc phần chuyển động tịnh tiến; T (K).
p-laplace|12|Từ trường|Lực từ lên đoạn dây|F=BIl\sin\alpha|Đoạn dây thẳng trong từ trường đều, α là góc dây với B.
p-lorentz|12|Từ trường|Lực từ lên điện tích chuyển động|F=\lvert q\rvert vB\sin\alpha|Chỉ thành phần lực từ; α giữa v và B, lực vuông góc vận tốc.
p-flux|12|Cảm ứng điện từ|Từ thông|\Phi=BS\cos\alpha|B đều; α là góc giữa B và pháp tuyến mặt phẳng khung.
p-faraday|12|Cảm ứng điện từ|Suất điện động cảm ứng trung bình|\mathcal E_c=-N\frac{\Delta\Phi}{\Delta t}|Φ là từ thông qua một vòng; dấu trừ thể hiện quy tắc Lenz.
p-emwave|11-12|Sóng điện từ|Liên hệ tần số và bước sóng điện từ|c=\lambda f|Trong chân không c≈3,00×10⁸ m/s; trong môi trường dùng tốc độ truyền tương ứng.
p-rms|12|Dòng điện xoay chiều|Giá trị hiệu dụng của dòng hình sin|I=\frac{I_0}{\sqrt2},\quad U=\frac{U_0}{\sqrt2}|Chỉ áp dụng sóng hình sin; mức độ dạy theo chương trình/chuyên đề.
p-transformer|12|Cảm ứng điện từ|Máy biến áp lí tưởng|\frac{U_1}{U_2}=\frac{N_1}{N_2}|Bỏ mọi hao phí; không áp dụng trực tiếp cho nguồn điện một chiều ổn định.
p-reflection|7,9|Quang học|Định luật phản xạ|i=r|Các góc đo với pháp tuyến.
p-refraction|9,11|Quang học|Định luật khúc xạ|n_1\sin i=n_2\sin r|Hai môi trường trong suốt; góc đo với pháp tuyến.
p-index|9,11|Quang học|Chiết suất tuyệt đối|n=\frac cv|c là tốc độ ánh sáng chân không, v trong môi trường.
p-critical|9,11|Quang học|Góc giới hạn phản xạ toàn phần|\sin i_{gh}=\frac{n_2}{n_1}|Chỉ khi n₁>n₂; ánh sáng truyền từ môi trường 1 sang 2.
p-lens|9,11|Quang học|Thấu kính mỏng|\frac1f=\frac1d+\frac1{d'}|Quy ước dấu: vật thật d>0, ảnh thật d′>0, hội tụ f>0; đổi dấu cho ảnh ảo/phân kì.
p-magnification|9,11|Quang học|Độ phóng đại ảnh thấu kính|k=\frac{h'}h=-\frac{d'}d|Dùng độ cao ảnh có dấu; k<0 ảnh ngược chiều.
p-nuclide|12|Hạt nhân|Số khối, proton và neutron|A=Z+N|Z số proton, N neutron; A số khối, không phải khối lượng nguyên tử chính xác.
p-mass-defect|12|Hạt nhân|Độ hụt khối và năng lượng liên kết|\Delta m=Zm_p+Nm_n-m_{hn},\quad E_{lk}=\Delta mc^2|Các khối lượng hạt nhân và nucleon cùng đơn vị; không trộn khối lượng nguyên tử nếu chưa hiệu chỉnh electron.
p-decay|12|Hạt nhân|Định luật phóng xạ|N=N_0e^{-\lambda t}=N_0\,2^{-t/T}|T là chu kì bán rã; λ=ln2/T; lượng hạt ban đầu N₀.
p-activity|12|Hạt nhân|Độ phóng xạ|H=\lambda N|H (Bq=s⁻¹); λ phải tính bằng s⁻¹ nếu muốn H ra Bq.
`));
CURRICULUM_CATALOG.push(...rows('chemistry','chemistry',M`
c-atoms|7-8,10|Nguyên tử|Số khối nguyên tử|A=Z+N|Z proton, N neutron. A không đồng nhất nguyên tử khối trung bình.
c-neutral|7-8,10|Nguyên tử|Nguyên tử trung hòa điện|N_e=Z|Ion dương ít electron hơn Z, ion âm nhiều electron hơn Z.
c-average|10|Nguyên tử|Nguyên tử khối trung bình|\overline A=\sum_i x_iA_i|xᵢ là phần số nguyên tử đồng vị, tổng xᵢ=1; không dùng phần trăm chưa chia 100.
c-shell|10|Cấu tạo electron|Số electron tối đa của lớp|N_{e,\max}=2n^2|n=1,2,…; đây là sức chứa tối đa của lớp, không phải thứ tự phân bố electron.
c-orbital|10|Cấu tạo electron|Sức chứa phân lớp s, p, d, f|s^2,\quad p^6,\quad d^{10},\quad f^{14}|Mỗi orbital tối đa 2 electron; không phải cấu hình của một nguyên tử cụ thể.
c-valence|7-8|Hóa trị và công thức|Quy tắc hóa trị|x\,a=y\,b|Trong AₓBᵧ, a và b là hóa trị các thành phần trong phạm vi quy tắc hóa trị phổ thông.
c-mol-particles|8-12|Mol và khí|Số hạt và số mol|N=nN_A|Nₐ≈6,02214076×10²³ mol⁻¹; xác định rõ hạt là nguyên tử, phân tử hay ion.
c-gas25|8-12|Mol và khí|Thể tích mol khí ở 25 °C, 1 bar|V\approx24.79n\;(\mathrm{L})|Khí coi lí tưởng, T=298,15 K, p=100 kPa. Không dùng cho mọi điều kiện khí.
c-gas0|8-12|Mol và khí|Thể tích mol khí ở 0 °C, 1 atm|V\approx22.414n\;(\mathrm{L})|Khí lí tưởng, T=273,15 K, p=101,325 kPa. Phân biệt với điều kiện 25 °C, 1 bar.
c-gasgeneral|10-12|Mol và khí|Khí lí tưởng ở điều kiện bất kì|n=\frac{pV}{RT}|Đơn vị p,V,R phải tương thích; nhiệt độ dùng K.
c-gasrelative|8-12|Mol và khí|Tỉ khối hai khí|d_{A/B}=\frac{M_A}{M_B}|Cùng nhiệt độ và áp suất, khí gần lí tưởng.
c-gasair|8-12|Mol và khí|Tỉ khối khí so với không khí|d_{A/kk}\approx\frac{M_A}{29}|M tính g/mol, lấy khối lượng mol không khí gần đúng 29 g/mol.
c-conserve|8-12|Phản ứng và bảo toàn|Bảo toàn khối lượng|\sum m_{\text{trước}}=\sum m_{\text{sau}}|Hệ kín; tính cả chất khí thoát ra hoặc hấp thụ.
c-stoichiometry|8-12|Phản ứng và bảo toàn|Tỉ lệ mol theo hệ số phương trình|\frac{n_A}{a}=\frac{n_B}{b}=\frac{n_C}{c}|Cho phương trình đã cân bằng aA+bB→cC; các n là lượng đã phản ứng/được tạo thành.
c-yield|8-12|Phản ứng và bảo toàn|Hiệu suất phản ứng theo sản phẩm|H=\frac{n_{\text{thực}}}{n_{\text{lí thuyết}}}\times100\%|So sánh cùng sản phẩm; dùng khối lượng cũng được nếu đúng chất và đơn vị.
c-masspercent|8-12|Dung dịch|Nồng độ phần trăm khối lượng|C\%=\frac{m_{ct}}{m_{dd}}\times100\%|mdd=mct+mdung môi; không nhầm phần trăm thể tích.
c-solutionmass|8-12|Dung dịch|Khối lượng dung dịch từ khối lượng riêng|m_{dd}=DV|D (g/mL), V (mL) thì m (g); chọn đúng đơn vị.
c-dilution|8-12|Dung dịch|Pha loãng giữ số mol chất tan|C_1V_1=C_2V_2|Không có phản ứng và lượng chất tan được bảo toàn; V cùng đơn vị.
c-solubility|8-11|Dung dịch|Độ tan theo khối lượng dung môi|S=\frac{m_{ct}}{m_{dm}}\times100|Dung dịch bão hòa tại nhiệt độ xác định; S là g chất tan/100 g dung môi.
c-elementpercent|8-12|Công thức phân tử|Phần trăm khối lượng nguyên tố|w_A=\frac{xM_A}{M_{A_xB_y}}\times100\%|M_A là nguyên tử khối theo đơn vị mol tương ứng; tính đủ số nguyên tử.
c-empirical|11-12|Hữu cơ đại cương|Tỉ lệ nguyên tử từ phần trăm khối lượng|x:y:z=\frac{w_C}{12}:\frac{w_H}{1}:\frac{w_O}{16}|Mẫu chất chỉ gồm C,H,O; w có cùng cơ sở phần trăm hoặc phần số.
c-molecular|11-12|Hữu cơ đại cương|Từ công thức đơn giản đến công thức phân tử|M=kM_{\text{đơn giản}},\quad k\in\mathbb N^*|Biết khối lượng mol và công thức đơn giản; k là số nguyên dương.
c-dbe|11-12|Hữu cơ đại cương|Độ bất bão hòa|k=\frac{2C+2+N-H-X}{2}|Hợp chất trung hòa thông thường gồm C,H,N,halogen X và O; không áp dụng máy móc cho ion/kim loại.
c-alkane|9,11|Hydrocarbon|Công thức chung alkane mạch hở|\ce{C_nH_{2n+2}}|n≥1; hợp chất no, mạch hở.
c-alkene|9,11|Hydrocarbon|Công thức chung alkene đơn chức mạch hở|\ce{C_nH_{2n}}|n≥2, đúng một liên kết đôi, mạch hở; công thức này cũng có thể thuộc cycloalkane.
c-alkyne|11|Hydrocarbon|Công thức chung alkyne mạch hở|\ce{C_nH_{2n-2}}|n≥2, một liên kết ba, mạch hở.
c-alcohol|9,11|Dẫn xuất hữu cơ|Alcohol no đơn chức mạch hở|\ce{C_nH_{2n+1}OH}|n≥1; không dùng làm công thức chung mọi alcohol.
c-acid|9,11-12|Dẫn xuất hữu cơ|Acid carboxylic no đơn chức mạch hở|\ce{C_nH_{2n}O2}|n≥1; xác định nhóm −COOH từ cấu tạo.
c-ester|12|Dẫn xuất hữu cơ|Ester no đơn chức mạch hở|\ce{C_nH_{2n}O2}|n≥2; cùng công thức phân tử có thể là acid carboxylic.
c-neutralization|8-12|Phản ứng vô cơ|Trung hòa acid–base|\ce{H+ + OH- -> H2O}|Phương trình ion rút gọn cho acid mạnh và base mạnh trong dung dịch loãng.
c-carbonate|8-12|Phản ứng vô cơ|Carbonate tác dụng acid|\ce{CO3^2- + 2H+ -> CO2 + H2O}|Phương trình ion rút gọn; cần đủ acid.
c-oxidation|10-12|Oxi hóa–khử|Bảo toàn electron|\sum n_e(\text{nhường})=\sum n_e(\text{nhận})|Tính electron trao đổi theo sự thay đổi số oxi hóa và số mol.
c-enthalpy|10-12|Năng lượng hóa học|Enthalpy phản ứng từ enthalpy tạo thành|\Delta_rH^\circ=\sum\nu\Delta_fH^\circ_{sp}-\sum\nu\Delta_fH^\circ_{cđ}|Dùng hệ số phương trình đã cân bằng và cùng trạng thái vật chất; kJ cho lượng phản ứng đã viết.
c-bondenergy|10|Năng lượng hóa học|Ước tính nhiệt phản ứng từ năng lượng liên kết|\Delta H\approx\sum E_{\text{phá}}-\sum E_{\text{tạo}}|Thường dùng năng lượng liên kết trung bình pha khí, chỉ là gần đúng.
c-rate|10-11|Tốc độ phản ứng|Tốc độ trung bình theo nồng độ|v_{tb}=-\frac1a\frac{\Delta C_A}{\Delta t}|a là hệ số chất phản ứng A; với sản phẩm dùng dấu cộng và chia hệ số.
c-vant-hoff|10|Tốc độ phản ứng|Hệ số nhiệt độ tốc độ phản ứng|\frac{v_2}{v_1}=\gamma^{(T_2-T_1)/10}|Mô hình thực nghiệm trong khoảng nhiệt độ cho phép; γ được đề cho.
c-equilibrium|11|Cân bằng hóa học|Hằng số cân bằng theo nồng độ|K_c=\frac{[C]^c[D]^d}{[A]^a[B]^b}|Cho aA+bB⇌cC+dD; bỏ chất rắn và chất lỏng tinh khiết trong mô hình phổ thông.
c-ph|11-12|Acid–base|pH dung dịch|\mathrm{pH}=-\log_{10}[\ce{H+}]|Dung dịch loãng, dùng xấp xỉ nồng độ thay hoạt độ; [H⁺] theo mol/L.
c-water|11-12|Acid–base|Tích số ion của nước|[\ce{H+}][\ce{OH-}]\approx10^{-14}|Dung dịch loãng ở 25 °C; giá trị thay đổi theo nhiệt độ.
c-ph-poh|11-12|Acid–base|Liên hệ pH và pOH|\mathrm{pH}+\mathrm{pOH}\approx14|Ở 25 °C, dung dịch loãng. Không dùng 14 cho mọi nhiệt độ.
c-ka|11-12|Acid–base|Hằng số phân li acid yếu|K_a=\frac{[\ce{H+}][\ce{A-}]}{[\ce{HA}]}|Cho acid đơn chức HA, trạng thái cân bằng; dung dịch đủ loãng để dùng nồng độ.
c-esterification|11-12|Dẫn xuất hữu cơ|Ester hóa|\ce{RCOOH + R'OH <=> RCOOR' + H2O}|Cần điều kiện xúc tác/nhiệt theo chất cụ thể; đây là khung phản ứng.
c-saponification|12|Dẫn xuất hữu cơ|Thủy phân ester trong kiềm|\ce{RCOOR' + NaOH -> RCOONa + R'OH}|Ester đơn chức thông thường; lượng base phụ thuộc số nhóm ester.
c-glucose|9,12|Carbohydrate|Quang hợp: phương trình tổng quát|\ce{6CO2 + 6H2O -> C6H12O6 + 6O2}|Khung cân bằng tổng quát, có ánh sáng và sắc tố quang hợp; không mô tả từng cơ chế.
c-ferment|9,12|Carbohydrate|Lên men glucose thành ethanol|\ce{C6H12O6 -> 2C2H5OH + 2CO2}|Điều kiện lên men phù hợp; không mặc định hiệu suất 100%.
c-starch|12|Carbohydrate|Thủy phân polysaccharide|\ce{(C6H10O5)_n + nH2O -> nC6H12O6}|Mẫu tinh bột/cellulose, cần acid hoặc enzyme thích hợp.
c-polymer|12|Polymer|Hệ số trùng hợp trung bình|\bar n=\frac{\overline M_{polymer}}{M_{\text{mắt xích}}}|Phân biệt mắt xích và monomer nếu có mất phân tử nhỏ.
c-faraday|12|Điện hóa|Khối lượng chất tạo ở điện cực|m=\frac{MIt}{zF}|Hiệu suất dòng 100%; z số electron trao đổi mỗi tiểu phân, F≈96485 C/mol.
c-cell|12|Điện hóa|Suất điện động pin chuẩn|E^\circ_{pin}=E^\circ_{cathode}-E^\circ_{anode}|Dùng các thế điện cực chuẩn cùng quy ước thế khử; V.
`));
CURRICULUM_CATALOG.push(...rows('biology','biology',M`
b-basepair|9,12|ADN và gene|Nguyên tắc bổ sung ADN|A=T,\quad G=C,\quad A+G=\frac N2|ADN hai mạch; A,T,G,C là số nucleotide tính trên toàn phân tử.
b-hydrogen|9,12|ADN và gene|Liên kết hydrogen trong ADN|H=2A+3G|ADN hai mạch với cặp A–T và G–C; A,G là số cặp tương ứng.
b-basepercent|9,12|ADN và gene|Tỉ lệ nucleotide của ADN|\%A+\%G=50\%|ADN hai mạch; %A=%T và %G=%C.
b-dna-copy|9,12|ADN và gene|Số ADN sau nhân đôi|N_{ADN}=N_0\,2^k|Mỗi phân tử hoàn tất k lần nhân đôi, không phân hủy.
b-dna-material|9,12|ADN và gene|Nucleotide môi trường cho nhân đôi|N_{mt}=N(2^k-1)|N là tổng nucleotide của một ADN hai mạch ban đầu, nhân đôi k lần hoàn toàn.
b-dna-helix|9,12|ADN và gene|Số vòng xoắn mô hình ADN dạng B|C=\frac N{20}|Mô hình phổ thông 10 cặp nucleotide/vòng, 0,34 nm/cặp; giá trị thật có thể biến thiên.
b-mrna|9,12|Biểu hiện gene|Độ dài đoạn RNA phiên mã từ gene|N_{RNA}=\frac{N_{ADN,\text{đoạn phiên mã}}}{2}|Chỉ cùng đoạn được phiên mã; mRNA trưởng thành có thể ngắn hơn nếu cắt intron.
b-codon|9,12|Biểu hiện gene|Số bộ ba trên vùng mã hóa|n_{codon}=\frac{N_{nt,\text{vùng mã hóa}}}{3}|Vùng mã hóa liên tục, đúng khung đọc; phân biệt stop codon với bộ ba mã hóa amino acid.
b-amino|9,12|Biểu hiện gene|Số amino acid trước biến đổi sau dịch mã|n_{aa}=n_{codon}-1|Vùng mã hóa có đúng một bộ ba kết thúc, đã gồm codon khởi đầu; chưa loại methionine đầu hoặc biến đổi sau dịch mã.
b-peptide|10,12|Protein|Liên kết peptide trong một chuỗi|n_{lk}=n_{aa}-1|Một chuỗi polypeptide mạch hở với n amino acid, n≥1.
b-dihybrid|9,12|Di truyền Mendel|Tỉ lệ kiểu hình lai hai cặp gene|9:3:3:1|AaBb×AaBb, phân li độc lập, trội hoàn toàn, không tương tác/lệch sống sót.
b-gametes|9,12|Di truyền Mendel|Số loại giao tử do phân li độc lập|n_{gt}=2^k|k là số cặp gene dị hợp, nằm trên các cặp NST khác nhau trong mô hình độc lập.
b-genotypes|9,12|Di truyền Mendel|Số kiểu gene và kiểu hình độc lập|n_{kg}=3^k,\quad n_{kh}=2^k|Lai các cá thể dị hợp k cặp gene phân li độc lập, trội hoàn toàn; không áp dụng mọi phép lai.
b-allele|12|Di truyền quần thể|Tần số allele từ số kiểu gene|p=\frac{2N_{AA}+N_{Aa}}{2N},\quad q=1-p|Quần thể lưỡng bội, locus hai allele trên NST thường, N cá thể.
b-hardy|12|Di truyền quần thể|Cân bằng Hardy–Weinberg|p^2+2pq+q^2=1|Giao phối ngẫu nhiên, quần thể lớn, không đột biến/chọn lọc/di nhập gene đáng kể; p+q=1.
b-selfing|12|Di truyền quần thể|Dị hợp sau các thế hệ tự thụ phấn|H_n=H_0\left(\frac12\right)^n|Tự thụ hoàn toàn, không chọn lọc/đột biến; H là tần số dị hợp.
b-crossing|12|Liên kết và hoán vị gene|Tần số hoán vị gene|f=\frac{N_{\text{tái tổ hợp}}}{N_{\text{con}}}\times100\%|Phép lai phân tích đúng giả thiết; f≤50%; ở vùng ngắn khoảng cách bản đồ xấp xỉ f cM.
b-chromosomes|9-10,12|Phân bào|Số NST và chromatid ở kì giữa nguyên phân|N_{NST}=2n,\quad N_{chromatid}=4n|Đếm NST theo tâm động, kì giữa trước tách chromatid; phân biệt kì sau.
b-meiosis|9-10,12|Phân bào|Giảm phân và số NST giao tử|2n\longrightarrow n|Mô hình giảm phân bình thường; không nhầm mức bội với lượng ADN.
b-gamete-count|9-10,12|Phân bào|Sản phẩm giảm phân ở phát sinh giao tử|1\text{ tế bào sinh tinh}\to4\text{ tinh trùng}|Mô hình sinh tinh bình thường; phát sinh trứng không tạo 4 trứng chức năng.
b-cellgrow|10|Vi sinh vật|Tăng số tế bào theo thế hệ|N=N_0\,2^{t/g}|g là thời gian thế hệ; điều kiện phân đôi đồng đều trong pha lũy thừa, cùng đơn vị t,g.
b-logistic|12|Sinh thái quần thể|Tăng trưởng logistic liên tục|\frac{dN}{dt}=rN\left(1-\frac NK\right)|Mở rộng mô hình: r tốc độ tăng nội tại, K sức chứa, không coi mọi quần thể tuân đúng mô hình.
b-popdensity|9,12|Sinh thái quần thể|Mật độ cá thể|D=\frac NS|S là diện tích hoặc thay bằng thể tích khi thích hợp; đơn vị cá thể/m² hoặc cá thể/m³.
b-popchange|9,12|Sinh thái quần thể|Biến động số lượng quần thể|\Delta N=B-D+I-E|B sinh, D tử, I nhập cư, E xuất cư trong cùng khoảng thời gian.
b-eco-eff|9,12|Sinh thái hệ sinh thái|Hiệu suất sinh thái|H=\frac{E_{n+1}}{E_n}\times100\%|Năng lượng hai bậc dinh dưỡng liên tiếp trong cùng thời gian và cùng cơ sở đo.
b-primary-production|12|Sinh thái hệ sinh thái|Năng suất sơ cấp thực|NPP=GPP-R|GPP sản xuất sơ cấp tổng, R hô hấp của sinh vật sản xuất; cùng đơn vị/thời gian.
b-respiration|10-11|Trao đổi chất|Phương trình tổng quát hô hấp hiếu khí|\ce{C6H12O6 + 6O2 -> 6CO2 + 6H2O}|Giải phóng năng lượng, một phần tích lũy trong ATP; không ấn định số ATP cho mọi tế bào.
b-waterbalance|11|Trao đổi chất|Cân bằng nước ở thực vật|\Delta W=W_{\text{hấp thu}}-W_{\text{mất}}|Tính trong cùng khoảng thời gian; còn có biến động tích trữ.
`));
CURRICULUM_CATALOG.push(...rows('geography','curriculum',M`
g-scale|6-12|Bản đồ|Tỉ lệ bản đồ|\frac1M=\frac{d_{\text{bản đồ}}}{d_{\text{thực}}}|Hai khoảng cách cùng đơn vị, M là mẫu số tỉ lệ; xét biến dạng bản đồ nếu cần chính xác cao.
g-real-distance|4-12|Bản đồ|Khoảng cách thực từ tỉ lệ|D=dM|Đổi đơn vị sau khi nhân; d là khoảng cách trên bản đồ tỉ lệ 1:M.
g-density|6-12|Dân cư|Mật độ dân số|D=\frac PS|P là số dân, S diện tích; người/km² nếu S dùng km².
g-birth|10-12|Dân cư|Tỉ suất sinh thô|CBR=\frac BP\times1000|B số trẻ sinh sống, P dân số trung bình cùng năm; đơn vị ‰.
g-death|10-12|Dân cư|Tỉ suất tử thô|CDR=\frac DP\times1000|D số người chết, P dân số trung bình; đơn vị ‰.
g-natural-growth|10-12|Dân cư|Gia tăng tự nhiên|r_{\%}=\frac{CBR-CDR}{10}|CBR,CDR cùng dùng ‰; chia 10 để đổi kết quả ra %.
g-pop-projection|10-12|Dân cư|Dự báo dân số theo tốc độ cố định|P_t=P_0(1+r)^t|r dùng phần số/năm; mô hình giả định tốc độ không đổi, không phải dự báo chắc chắn.
g-urban|10-12|Dân cư|Tỉ lệ dân thành thị|U=\frac{P_{\text{thành thị}}}{P_{\text{tổng}}}\times100\%|Cùng mốc thời gian và đơn vị dân số.
g-agri-productivity|7-12|Kinh tế và số liệu|Năng suất cây trồng|Y=\frac QS|Q sản lượng, S diện tích; đổi tấn/ha sang tạ/ha bằng nhân 10.
g-percapita-food|7-12|Kinh tế và số liệu|Sản lượng bình quân đầu người|q=\frac QP|Nếu Q là tấn và P là người, q là tấn/người; đổi kg khi cần.
g-share|6-12|Kinh tế và số liệu|Tỉ trọng trong cơ cấu|w_i=\frac{x_i}{\sum_jx_j}\times100\%|Tổng phải khác 0; các bộ phận cùng phạm vi và đơn vị.
g-growth-index|7-12|Kinh tế và số liệu|Chỉ số phát triển, năm gốc 100|I=\frac{x_t}{x_0}\times100|x₀≠0; không nhầm chỉ số 120 với mức tăng 20%.
g-growth-rate|7-12|Kinh tế và số liệu|Tốc độ tăng trưởng so với năm gốc|g=\frac{x_t-x_0}{x_0}\times100\%|x₀≠0; ghi rõ năm gốc.
g-gdp-person|10-12|Kinh tế và số liệu|GDP bình quân đầu người|GDP_{pc}=\frac{GDP}{P}|GDP và P cùng thời kì; giá hiện hành/giá so sánh phải được nêu rõ.
g-tradebalance|11-12|Thương mại|Cán cân xuất nhập khẩu|B=X-M|B>0 xuất siêu, B<0 nhập siêu; X,M cùng đơn vị tiền và cùng thời kì.
g-tradetotal|11-12|Thương mại|Tổng kim ngạch xuất nhập khẩu|T=X+M|Không trừ nhập khẩu khi tính tổng kim ngạch.
g-export-ratio|11-12|Thương mại|Tỉ lệ xuất khẩu so với nhập khẩu|R=\frac XM\times100\%|M>0; khác tỉ trọng xuất khẩu trong tổng kim ngạch.
g-rainfall|6-12|Khí hậu|Tổng lượng mưa năm|R_{\text{năm}}=\sum_{m=1}^{12}R_m|Rm là lượng mưa tháng (mm), không lấy trung bình khi hỏi tổng năm.
g-temperature|6-12|Khí hậu|Nhiệt độ trung bình từ các lần đo|\bar T=\frac1n\sum_{i=1}^{n}T_i|Các lần đo có trọng số tương đương; không thay dữ liệu bình quân đã có trọng số.
g-temp-range|6-12|Khí hậu|Biên độ nhiệt|A=T_{\max}-T_{\min}|Cùng chuỗi thời gian, dùng °C; biên độ năm thường dựa nhiệt độ trung bình tháng.
g-lapse|6-12|Địa hình và khí hậu|Ước tính nhiệt độ theo độ cao|\Delta T\approx0.6\frac{\Delta h}{100}|Quy ước bài tập: giảm khoảng 0,6 °C/100 m; không coi là hằng số khí quyển mọi nơi.
g-solar-time|6,10|Bản đồ|Giờ Mặt Trời địa phương theo kinh độ|\Delta t=\frac{\Delta\lambda}{15^\circ}\;(\mathrm{h})|Kinh độ Đông nhanh hơn; giờ hành chính theo múi giờ không hoàn toàn trùng giờ Mặt Trời.
g-transport-distance|10-12|Giao thông vận tải|Cự li vận chuyển trung bình|L=\frac{Q_{\text{luân chuyển}}}{Q_{\text{vận chuyển}}}|Ví dụ tấn·km chia tấn cho km; thống nhất hệ số nghìn/triệu.
`));
CURRICULUM_CATALOG.push(...rows('informatics','curriculum',M`
i-byte|3-12|Thông tin và dữ liệu|Byte và bit|1\,\mathrm{B}=8\,\mathrm{bit}|B viết hoa là byte, b viết thường thường là bit.
i-binary-unit|6-12|Thông tin và dữ liệu|Đơn vị nhị phân KiB, MiB, GiB|1\,\mathrm{KiB}=1024\,\mathrm{B},\quad1\,\mathrm{MiB}=1024\,\mathrm{KiB}|Phân biệt KB theo hệ thập phân 1000 B với KiB=1024 B.
i-binary-number|6,10|Biểu diễn số|Giá trị số nhị phân|N=\sum_{i=0}^{k}b_i2^i|bi∈{0,1}, i tính từ bit thấp nhất bên phải.
i-image-size|6,10-12|Thông tin và dữ liệu|Dung lượng ảnh bitmap chưa nén|S=\frac{W H b}{8}\;(\mathrm{byte})|W,H số pixel, b bit/pixel; bỏ header, metadata và nén.
i-audio-size|10-12|Thông tin và dữ liệu|Dung lượng âm thanh PCM chưa nén|S=\frac{f_sbtC}{8}\;(\mathrm{byte})|fs mẫu/s, b bit/mẫu/kênh, C số kênh, t giây; bỏ header.
i-transfer-time|6,10-12|Mạng và dữ liệu|Thời gian truyền lí tưởng|t=\frac{S_{bit}}{R_{bit/s}}|Tốc độ hữu hiệu có thể nhỏ hơn danh định do giao thức và đường truyền.
i-remainder|8-12|Lập trình|Chia nguyên và phần dư|a=bq+r,\quad0\le r<b|Mẫu số nguyên không âm và b>0; quy ước số âm khác nhau giữa các ngôn ngữ.
i-loop-count|8-12|Lập trình|Số bước trong dãy tăng đều|N=\left\lfloor\frac{b-a}{h}\right\rfloor+1|h>0, a≤b, có lấy mốc đầu a và điều kiện không vượt b; không đồng nhất mọi hàm range.
i-sum-integers|8-12|Thuật toán|Tổng n số tự nhiên dương đầu tiên|S=\frac{n(n+1)}2|n nguyên không âm; hữu ích để đối chiếu thuật toán lặp.
i-average|7-12|Bảng tính|Trung bình một dãy số|\bar x=\frac{\sum x_i}{n}|Bảng tính dùng AVERAGE trên ô số; cách xử lí ô trống/văn bản theo phần mềm.
i-percent|7-12|Bảng tính|Tỉ lệ phần trăm trong bảng tính|p=\frac{\text{phần}}{\text{tổng}}|Khi ô đã định dạng %, không nhân 100 lần nữa nếu muốn hiển thị đúng.
i-complexity|10-12|Thuật toán|Tìm kiếm nhị phân: số bước xấp xỉ|k\approx\log_2n|Mở rộng: dữ liệu có thứ tự; số so sánh nguyên phụ thuộc triển khai.
`));
CURRICULUM_CATALOG.push(...rows('technology','curriculum',M`
t-scale|8-11|Bản vẽ kĩ thuật|Tỉ lệ bản vẽ|k=\frac{l_{\text{vẽ}}}{l_{\text{thật}}}|k=1 nguyên hình, k<1 thu nhỏ, k>1 phóng to; cùng đơn vị.
t-gear|8,11|Truyền động cơ khí|Tỉ số truyền bánh răng|i=\frac{n_1}{n_2}=\frac{z_2}{z_1}|Bánh 1 chủ động, 2 bị động; n tốc độ quay, z số răng; không trượt.
t-belt|8,11|Truyền động cơ khí|Truyền động đai không trượt|\frac{n_1}{n_2}=\frac{D_2}{D_1}|D là đường kính puly; quy ước tỉ số truyền có thể khác sách, cần ghi rõ.
t-rpm|8,11|Truyền động cơ khí|Vận tốc góc từ vòng/phút|\omega=\frac{2\pi n}{60}|n vòng/phút, ω rad/s.
t-electricbill|8-9,12|Kĩ thuật điện|Điện năng theo công suất và thời gian|E=Pt|P (kW), t (h) thì E (kWh); tiền điện còn phụ thuộc biểu giá và các khoản khác.
t-efficiency|8-12|Kĩ thuật điện|Hiệu suất thiết bị|\eta=\frac{P_{ra}}{P_{vào}}\times100\%|Công suất cùng đơn vị; xác định ranh giới hệ thống.
t-singlephase|12|Kĩ thuật điện|Công suất tác dụng một pha hình sin|P=UI\cos\varphi|U,I là giá trị hiệu dụng, φ góc lệch pha; đơn vị W.
t-threephase|12|Kĩ thuật điện|Công suất ba pha cân bằng|P=\sqrt3 U_dI_d\cos\varphi|Mạch ba pha cân bằng, điện áp/dòng dây hiệu dụng.
t-transformer|9,12|Kĩ thuật điện|Tỉ số vòng dây máy biến áp lí tưởng|\frac{U_1}{U_2}=\frac{N_1}{N_2}|Nguồn xoay chiều; bỏ mọi tổn hao.
t-plantdensity|7,10|Trồng trọt|Số cây ước tính theo khoảng cách trồng|N=\frac{S}{ab}|Mô hình lưới chữ nhật, S là tổng diện tích; a,b tính theo m nếu S tính theo m²; không trừ lối đi thì chỉ là ước tính.
t-germination|7,10|Trồng trọt|Tỉ lệ nảy mầm|G=\frac{n_{\text{nảy mầm}}}{n_{\text{gieo thử}}}\times100\%|Mẫu thử có kích thước dương, cùng điều kiện thử.
t-feedratio|7,11|Chăn nuôi|Hệ số chuyển hóa thức ăn|FCR=\frac{m_{\text{thức ăn}}}{\Delta m_{\text{vật nuôi}}}|Cùng kì theo dõi; Δm>0; không đồng nhất các định nghĩa hiệu quả thức ăn khác.
`));
CURRICULUM_CATALOG.push(...rows('economics','math-program',M`
e-budget|6-12|Ngân sách cá nhân|Cân đối thu và chi|S=I-C|I thu, C chi, S phần dư; cùng thời kì, không phải khuyến nghị chi tiêu cá nhân.
e-saving|6-12|Ngân sách cá nhân|Tỉ lệ tiết kiệm|r=\frac SI\times100\%|I>0; ghi rõ phần S là tiết kiệm thực tế hay kế hoạch.
e-simple|9-12|Lãi suất và phần trăm|Lãi đơn|A=P(1+nr)|Lãi tính trên vốn gốc, r phần số mỗi kì, n số kì; không gồm phí/thuế.
e-compound|11-12|Lãi suất và phần trăm|Lãi kép|A=P(1+r)^n|r là lãi suất phần số mỗi kì ghép lãi; mô hình cố định, không có dòng tiền khác.
e-discount|5-12|Lãi suất và phần trăm|Giá sau giảm giá|P_1=P_0\left(1-\frac p{100}\right)|p nhập theo số phần trăm; giảm liên tiếp phải nhân từng hệ số.
e-increase|5-12|Lãi suất và phần trăm|Giá sau tăng phần trăm|P_1=P_0\left(1+\frac p{100}\right)|p là phần trăm tăng so với giá gốc P₀.
e-revenue|10-12|Chi phí và hiệu quả|Doanh thu một loại sản phẩm|R=pq|p đơn giá, q số lượng, cùng thời kì; không nhầm doanh thu với lợi nhuận.
e-profit|10-12|Chi phí và hiệu quả|Lợi nhuận giản lược|\Pi=R-C|C phải bao gồm các chi phí theo giả thiết; đây là mô hình bài tập.
e-break-even|10-12|Chi phí và hiệu quả|Sản lượng hòa vốn giản lược|q^*=\frac F{p-v}|F chi phí cố định, v chi phí biến đổi/đơn vị, p>v; điều kiện tuyến tính.
e-margin|10-12|Chi phí và hiệu quả|Biên lợi nhuận theo doanh thu|m=\frac{\Pi}{R}\times100\%|R>0; không nhầm với tỉ suất lợi nhuận tính trên chi phí.
e-unitcost|10-12|Chi phí và hiệu quả|Chi phí bình quân đơn vị|c=\frac Cq|q>0; chi phí, sản lượng cùng phạm vi.
e-realindex|11-12|Lãi suất và phần trăm|Sức mua điều chỉnh chỉ số giá|V_{thực}=\frac{V_{danh\ nghĩa}}{CPI/100}|CPI theo năm gốc 100; chỉ là phép quy đổi sức mua trong mô hình.
`));
CURRICULUM_CATALOG.push(...rows('history','curriculum',M`
h-timeline|6-12|Niên đại|Khoảng cách hai mốc cùng Công nguyên|\Delta t=t_2-t_1|Năm dương lịch, t₂≥t₁; xét ngày/tháng nếu cần thời gian chính xác.
h-bce-ce|6-12|Niên đại|Khoảng cách mốc TCN và CN|\Delta t=a+b-1|Từ cùng ngày của năm a TCN đến năm b CN; lịch sử không có năm 0. Không dùng cho cách đánh số năm thiên văn.
`));
CURRICULUM_CATALOG.push(...rows('music','curriculum',M`
mu-whole|1-12|Trường độ và nhịp|Quan hệ trường độ nốt cơ bản|1=2\times\frac12=4\times\frac14=8\times\frac18|Các phân số ở đây là phần của nốt tròn, không ấn định số giây.
mu-dotted|3-12|Trường độ và nhịp|Trường độ nốt chấm dôi|T_{\text{chấm dôi}}=\frac32T|Một chấm dôi cộng nửa trường độ nốt gốc; hai chấm dôi có quy tắc khác.
mu-meter|3-12|Trường độ và nhịp|Tổng trường độ ô nhịp đơn|\sum_i d_i=\frac nd|Số chỉ nhịp n/d, d chỉ loại nốt theo phần nốt tròn; các trường độ cộng đủ một ô nhịp.
mu-tempo|6-12|Tiết tấu và tốc độ|Thời gian một phách|t=\frac{60}{BPM}\;(\mathrm{s})|BPM gắn với loại nốt được ghi làm phách; không mặc định luôn là nốt đen.
`));
CURRICULUM_CATALOG.push(...rows('art','curriculum',M`
a-aspect|3-12|Tỉ lệ và bố cục|Tỉ lệ khung hình|r=\frac{W}{H}|W,H cùng đơn vị; khung 16:9 không có nghĩa là kích thước cố định.
a-scale|4-12|Tỉ lệ và bố cục|Phóng to, thu nhỏ đồng dạng|W'=kW,\quad H'=kH|Dùng cùng một hệ số k>0 để giữ tỉ lệ.
a-grid|5-12|Tỉ lệ và bố cục|Chia khung thành lưới đều|w=\frac Wn,\quad h=\frac Hm|n cột, m hàng, đều là số nguyên dương; dùng làm khung bố cục chứ không áp đặt thẩm mĩ.
`));
CURRICULUM_CATALOG.push(...rows('pe','curriculum',M`
pe-pace|6-12|Đo kết quả vận động|Tốc độ trung bình trong bài chạy|v=\frac st|s (m), t (s); là đo kết quả, không phải chỉ định cường độ tập luyện.
pe-accuracy|4-12|Đo kết quả vận động|Tỉ lệ thực hiện thành công|R=\frac{n_{\text{đạt}}}{n_{\text{thử}}}\times100\%|Số lần thử>0; tiêu chí đạt cần xác định trước.
pe-change|6-12|Đo kết quả vận động|Mức thay đổi kết quả thời gian|r=\frac{t_0-t_1}{t_0}\times100\%|t₀>0, cùng cự li và điều kiện; r dương nghĩa thời gian giảm.
`));
const guide=(id,subject,grade,topic,title,fields,note='')=>({id:'g-'+id,subject,grades:gradesOf(grade),topic,title,kind:'guided',type:'content',formFields:fields,note,tags:[topic,title],sourceIds:['curriculum'],gradeBasis:'indicative'});
const F=(key,label,value='',multiline=true)=>[key,label,value,multiline];
CURRICULUM_CATALOG.push(
 guide('viet-syllables','literature','1-2','Tiếng Việt tiểu học','Âm, vần, tiếng và từ',[F('task','Yêu cầu','Đọc các tiếng, từ sau và tìm tiếng có vần giống nhau.'),F('words','Tiếng / từ do giáo viên chọn','')]),
 guide('viet-sentence','literature','1-3','Tiếng Việt tiểu học','Sắp xếp từ thành câu',[F('words','Các từ cần sắp xếp',''),F('task','Yêu cầu','Sắp xếp các từ thành câu có nghĩa. Viết hoa đầu câu và dùng dấu kết thúc phù hợp.')]),
 guide('viet-paragraph','literature','2-5','Tiếng Việt tiểu học','Viết đoạn văn theo gợi ý',[F('topic','Đề bài','Viết một đoạn văn về một sự việc hoặc nhân vật em yêu thích.'),F('hints','Gợi ý','Đối tượng / sự việc là gì?\nCó đặc điểm nào nổi bật?\nEm có cảm nghĩ như thế nào?')]),
 guide('viet-description','literature','4-5','Viết','Dàn ý miêu tả',[F('outline','Khung dàn ý','Mở bài: Giới thiệu đối tượng.\nThân bài: Đặc điểm khái quát và chi tiết tiêu biểu.\nKết bài: Cảm nghĩ hoặc nhận xét.')]),
 guide('viet-narrative','literature','3-7','Viết','Dàn ý kể chuyện',[F('outline','Khung dàn ý','Mở đầu: Bối cảnh và nhân vật.\nDiễn biến: Các sự việc theo trình tự hợp lí.\nKết thúc: Kết quả và điều rút ra.')]),
 guide('viet-rhetoric','literature','4-12','Tiếng Việt và đọc hiểu','Phân tích biện pháp tu từ',[F('quote','Câu / đoạn cần phân tích',''),F('questions','Câu hỏi','Xác định biện pháp tu từ.\nChỉ ra từ ngữ hoặc hình ảnh làm căn cứ.\nPhân tích tác dụng trong ngữ cảnh cụ thể.')]),
 guide('viet-evidence','literature','6-12','Đọc hiểu','Luận điểm – lí lẽ – bằng chứng',[F('claim','Luận điểm',''),F('reason','Lí lẽ',''),F('evidence','Bằng chứng và nguồn',''),F('analysis','Phân tích mối liên hệ','')]),
 guide('viet-poetry','literature','6-12','Đọc hiểu','Phân tích thơ theo yếu tố',[F('text','Ngữ liệu do giáo viên cung cấp',''),F('task','Gợi ý phân tích','Chủ thể trữ tình và cảm xúc.\nHình ảnh, ngôn ngữ, nhịp và giọng điệu.\nMối liên hệ giữa hình thức và nội dung.\nCăn cứ từ văn bản.')]),
 guide('viet-argument','literature','6-12','Nghị luận','Nghị luận về một vấn đề',[F('issue','Vấn đề cần nghị luận',''),F('structure','Khung lập luận','Nêu quan điểm.\nTriển khai luận điểm và bằng chứng.\nXem xét ý kiến khác.\nKhẳng định hoặc điều chỉnh kết luận.')]),
 guide('viet-compare','literature','10-12','Nghị luận','So sánh hai tác phẩm',[F('works','Hai văn bản / tác phẩm và nguồn',''),F('criteria','Tiêu chí so sánh','Đề tài, chủ đề, điểm nhìn, hình tượng và nghệ thuật.'),F('task','Yêu cầu','Phân tích tương đồng và khác biệt bằng dẫn chứng; lí giải có căn cứ.')]),
 guide('viet-report','literature','8-12','Viết','Báo cáo nghiên cứu nhỏ',[F('outline','Các phần báo cáo','Vấn đề và câu hỏi nghiên cứu.\nCách thu thập thông tin.\nKết quả và phân tích.\nKết luận, giới hạn và tài liệu tham khảo.')]),
 guide('en-introduce','english','1-5','Giao tiếp cơ bản','Giới thiệu bản thân',[F('pattern','Mẫu câu','My name is ___.\nI am ___ years old.\nI like ___.')],'Chọn lượng thông tin phù hợp lứa tuổi; lớp 1–2 là ngoại ngữ làm quen tùy chương trình.'),
 guide('en-be','english','3-6','Ngữ pháp nền tảng','Động từ be hiện tại',[F('pattern','Cấu trúc','I am ...\nHe / She / It is ...\nYou / We / They are ...\nAm / Is / Are + subject + ...?')]),
 guide('en-present-simple','english','4-8','Các thì cơ bản','Hiện tại đơn',[F('pattern','Cấu trúc','Affirmative: S + V(s/es).\nNegative: S + do/does not + base verb.\nQuestion: Do/Does + S + base verb?'),F('use','Ngữ cảnh','Thói quen, sự thật hoặc trạng thái phù hợp; động từ be có dạng riêng.')]),
 guide('en-present-progressive','english','4-8','Các thì cơ bản','Hiện tại tiếp diễn',[F('pattern','Cấu trúc','S + am/is/are + V-ing.\nAm/Is/Are + S + V-ing?'),F('use','Ngữ cảnh','Hành động đang diễn ra hoặc tình huống tạm thời; lưu ý động từ trạng thái.')]),
 guide('en-past-simple','english','5-9','Các thì cơ bản','Quá khứ đơn',[F('pattern','Cấu trúc','S + V2 / V-ed.\nS + did not + base verb.\nDid + S + base verb?'),F('use','Lưu ý','Động từ be dùng was/were; kiểm tra động từ bất quy tắc.')]),
 guide('en-future','english','5-9','Các thì cơ bản','Tương lai và dự định',[F('pattern','Cấu trúc','S + will + base verb.\nS + am/is/are going to + base verb.'),F('context','Ngữ cảnh sử dụng','Chọn theo dự đoán, quyết định tại thời điểm nói hoặc kế hoạch/dấu hiệu có sẵn.')]),
 guide('en-perfect','english','7-12','Các thì mở rộng','Hiện tại hoàn thành',[F('pattern','Cấu trúc','S + have/has + past participle.\nHave/Has + S + past participle?'),F('context','Ngữ cảnh','Trải nghiệm hoặc sự việc có liên hệ hiện tại; không dùng máy móc với thời điểm quá khứ đã kết thúc.')]),
 guide('en-past-progressive','english','8-12','Các thì mở rộng','Quá khứ tiếp diễn',[F('pattern','Cấu trúc','S + was/were + V-ing.'),F('context','Ngữ cảnh','Hoạt động đang diễn ra tại một thời điểm quá khứ; phối hợp với quá khứ đơn theo nghĩa.')]),
 guide('en-past-perfect','english','9-12','Các thì mở rộng','Quá khứ hoàn thành',[F('pattern','Cấu trúc','S + had + past participle.'),F('context','Ngữ cảnh','Sự việc xảy ra trước một mốc/sự việc khác trong quá khứ.')]),
 guide('en-comparative','english','5-12','So sánh','So sánh hơn và nhất',[F('pattern','Cấu trúc','Short adjective: adj-er / the adj-est.\nLong adjective: more adj / the most adj.\nEquality: as + adjective/adverb + as.'),F('exceptions','Ngoại lệ / ví dụ do giáo viên chọn','')]),
 guide('en-passive','english','8-12','Cấu trúc câu','Câu bị động',[F('pattern','Cấu trúc khái quát','S (receiver) + be (correct tense) + past participle (+ by agent).'),F('context','Giới hạn','Thường với động từ có tân ngữ; giữ thì/thể và ngữ cảnh, không đổi mọi câu sang bị động được.')]),
 guide('en-conditionals','english','8-12','Cấu trúc câu','Câu điều kiện',[F('pattern','Các mẫu phổ biến','Zero: If + present, present.\nFirst: If + present, will/can/may + base verb.\nSecond: If + past, would/could + base verb.\nThird: If + past perfect, would/could have + past participle.'),F('context','Ngữ cảnh / điều chỉnh','Chọn mẫu theo ý nghĩa thực, giả định hoặc trái thực; có biến thể và câu điều kiện hỗn hợp.')]),
 guide('en-relative','english','8-12','Cấu trúc câu','Mệnh đề quan hệ',[F('pattern','Mẫu khái quát','Noun + who/which/that/whose/... + relative clause.'),F('context','Lưu ý','Phân biệt xác định/không xác định, dấu phẩy và khả năng lược bỏ đại từ quan hệ.')]),
 guide('en-reported','english','8-12','Cấu trúc câu','Tường thuật lời nói',[F('pattern','Mẫu khái quát','Statement: said (that) + clause.\nQuestion: asked + if/whether/wh-word + clause.\nRequest: asked + object + to-infinitive.'),F('context','Lưu ý','Lùi thì, đại từ và trạng từ theo ngữ cảnh; không lùi thì máy móc khi nội dung vẫn đúng.')]),
 guide('en-gerund','english','7-12','Từ và cụm từ','Gerund và infinitive',[F('pattern','Khung ghi nhớ theo từ','Verb / expression: ___.\nFollowing form: V-ing / to V / bare V.\nMeaning in context: ___.\nExample: ___.')]),
 guide('en-modal','english','6-12','Từ và cụm từ','Động từ khuyết thiếu',[F('pattern','Mẫu khái quát','S + can/could/may/might/must/should/... + base verb.'),F('context','Ý nghĩa trong câu','Khả năng, cho phép, nghĩa vụ hoặc suy đoán tùy ngữ cảnh.')]),
 guide('en-writing','english','6-12','Kĩ năng viết','Topic sentence – support – conclusion',[F('pattern','Khung đoạn văn','Topic sentence: ___.\nSupporting point and example: ___.\nSupporting point and example: ___.\nConcluding sentence: ___.')]),
 guide('science-observe','science','1-5','Quan sát và đo lường','Phiếu quan sát tự nhiên',[F('question','Câu hỏi quan sát',''),F('record','Ghi chép','Đối tượng: ___.\nThời gian / nơi quan sát: ___.\nĐặc điểm nhìn thấy: ___.\nĐiều còn cần tìm hiểu: ___.')]),
 guide('science-experiment','science','4-9','Thực hành khoa học','Khung thí nghiệm có đối chứng',[F('question','Câu hỏi / dự đoán',''),F('design','Thiết kế','Yếu tố thay đổi: ___.\nYếu tố giữ nguyên: ___.\nĐại lượng đo và đơn vị: ___.\nSố lần lặp lại: ___.')],'Hoạt động cụ thể cần giáo viên chọn và kiểm tra an toàn; mẫu này không cung cấp quy trình thí nghiệm nguy hiểm.'),
 guide('science-classify','science','1-7','Phân loại và mô hình','Phân loại theo tiêu chí',[F('objects','Các đối tượng',''),F('criteria','Tiêu chí phân loại',''),F('task','Yêu cầu','Chia nhóm theo tiêu chí và giải thích bằng đặc điểm quan sát được.')]),
 guide('science-cycle','science','3-7','Phân loại và mô hình','Sơ đồ chu trình',[F('stages','Các giai đoạn','Giai đoạn 1 → Giai đoạn 2 → Giai đoạn 3 → ...'),F('task','Yêu cầu','Mô tả mối liên hệ giữa các giai đoạn, phân biệt mô hình với quá trình thực tế.')]),
 guide('history-table','history','4-12','Tư liệu và niên biểu','Niên biểu sự kiện',[F('events','Các mốc và sự kiện do giáo viên cung cấp','Năm / thời gian — Sự kiện — Ý nghĩa — Nguồn.'),F('task','Yêu cầu','Sắp xếp theo thời gian và chỉ ra mối liên hệ có căn cứ.')]),
 guide('history-source','history','6-12','Tư liệu và niên biểu','Phân tích nguồn sử liệu',[F('source','Nguồn / đoạn tư liệu',''),F('questions','Câu hỏi','Tác giả, thời điểm và mục đích tạo tư liệu là gì?\nTư liệu phản ánh điều gì?\nĐộ tin cậy và giới hạn?\nCó thể đối chiếu với nguồn nào?')]),
 guide('history-cause','history','6-12','Phân tích lịch sử','Nguyên nhân – diễn biến – kết quả',[F('event','Sự kiện / quá trình',''),F('outline','Khung phân tích','Bối cảnh.\nNguyên nhân và điều kiện.\nDiễn biến chính.\nKết quả, tác động và giới hạn của kết luận.')]),
 guide('civic-situation','civics','1-12','Tình huống và ứng xử','Phân tích tình huống',[F('situation','Tình huống do giáo viên nhập',''),F('task','Câu hỏi','Ai có liên quan?\nHành vi nào cần xem xét?\nCác lựa chọn và hệ quả có thể có?\nLựa chọn phù hợp và lí do?')]),
 guide('civic-rights','civics','6-12','Quyền và trách nhiệm','Quyền – nghĩa vụ – căn cứ',[F('situation','Vấn đề / tình huống',''),F('framework','Khung trả lời','Quyền và nghĩa vụ liên quan.\nHành vi và căn cứ.\nCách xử lí phù hợp.\nNguồn pháp luật và thời điểm hiệu lực cần kiểm tra.')],'Không tự điền hoặc khẳng định quy định pháp luật hiện hành khi chưa đối chiếu nguồn.'),
 guide('music-rhythm','music','1-12','Trường độ và nhịp','Mẫu luyện tiết tấu',[F('meter','Số chỉ nhịp / tốc độ',''),F('rhythm','Chuỗi trường độ do giáo viên nhập',''),F('task','Yêu cầu','Đếm phách, xác định trọng âm và thực hiện tiết tấu theo hướng dẫn.')]),
 guide('music-listen','music','3-12','Nghe và cảm thụ','Phiếu nghe nhạc',[F('work','Tác phẩm / nguồn do giáo viên cung cấp',''),F('criteria','Tiêu chí','Nhịp độ — Sắc thái — Âm sắc — Hình thức — Cảm nhận có căn cứ.')]),
 guide('art-analysis','art','1-12','Cảm thụ và thực hành','Phân tích tác phẩm mĩ thuật',[F('work','Tác phẩm / hình ảnh / nguồn',''),F('criteria','Gợi ý','Đường nét, hình, màu, sắc độ, không gian.\nBố cục và điểm nhấn.\nThông điệp hoặc cách cảm nhận có căn cứ.')]),
 guide('art-project','art','3-12','Cảm thụ và thực hành','Lập kế hoạch sản phẩm mĩ thuật',[F('brief','Yêu cầu sản phẩm',''),F('plan','Kế hoạch','Ý tưởng — Chất liệu — Kích thước — Các bước — Tiêu chí tự đánh giá.')]),
 guide('pe-record','pe','1-12','Đo kết quả vận động','Phiếu ghi kết quả vận động',[F('activity','Nội dung do giáo viên chọn',''),F('record','Mẫu ghi','Lần thực hiện: ___.\nKết quả và đơn vị: ___.\nĐiều kiện thực hiện: ___.\nNhận xét theo tiêu chí đã hướng dẫn: ___.')],'Không tự tạo yêu cầu vận động hoặc đánh giá sức khỏe cá nhân.'),
 guide('defence-awareness','defence','10-12','Nhận thức và an toàn','Khung câu hỏi nhận thức',[F('topic','Chủ đề theo tài liệu được duyệt',''),F('task','Câu hỏi','Trình bày nội dung chính.\nPhân tích ý nghĩa và trách nhiệm công dân.\nVận dụng vào tình huống an toàn do giáo viên cung cấp.')],'Mẫu nội dung học tập, không hướng dẫn sử dụng vũ khí hay thao tác nguy hiểm.'),
 guide('language-vocab','languages','1-12','Từ vựng và giao tiếp','Thẻ từ vựng ngoại ngữ',[F('language','Ngôn ngữ',''),F('word','Từ / cách đọc / nghĩa',''),F('example','Ví dụ và ngữ cảnh do giáo viên cung cấp','')]),
 guide('language-dialogue','languages','1-12','Từ vựng và giao tiếp','Khung hội thoại ngoại ngữ',[F('language','Ngôn ngữ và trình độ',''),F('context','Bối cảnh / mục đích',''),F('dialogue','Lượt lời','A: ...\nB: ...\nA: ...\nB: ...')]),
 guide('language-structure','languages','3-12','Cấu trúc ngôn ngữ','Mẫu cấu trúc ngữ pháp',[F('language','Ngôn ngữ',''),F('pattern','Cấu trúc do giáo viên nhập',''),F('use','Điều kiện và ngoại lệ',''),F('example','Ví dụ','')]),
 guide('experience-plan','experience','1-12','Kế hoạch và tự đánh giá','Kế hoạch hoạt động',[F('goal','Mục tiêu',''),F('plan','Khung kế hoạch','Việc cần làm — Người phụ trách — Thời gian — Nguồn lực — Tiêu chí kết quả.')]),
 guide('experience-survey','experience','4-12','Kế hoạch và tự đánh giá','Mẫu khảo sát nhỏ',[F('question','Câu hỏi khảo sát',''),F('plan','Cách tiến hành','Đối tượng và cách chọn mẫu.\nCâu hỏi không dẫn dắt.\nCách tổng hợp dữ liệu.\nGiới hạn và bảo vệ thông tin cá nhân.')]),
 guide('experience-career','experience','8-12','Hướng nghiệp','Hồ sơ tìm hiểu nghề',[F('career','Nghề / nhóm nghề',''),F('criteria','Nội dung cần tìm hiểu','Công việc — Năng lực — Điều kiện đào tạo — Nguồn thông tin — Điều phù hợp cần tự đánh giá.')])
);
