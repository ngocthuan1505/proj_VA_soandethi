"""Ngữ liệu tự biên soạn cho thư viện học liệu, theo từng bài."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def _catalog_sha256(
    subject: str, grade: str, book: str, volume: str, lessons: list[tuple[str, str, str, str]]
) -> str:
    payload = {
        "grade": grade,
        "subject": subject,
        "book": book,
        "volume": volume,
        "lessons": [
            {"number": i, "chapter": ch, "title": t, "outcome": o, "text": txt}
            for i, (ch, t, o, txt) in enumerate(lessons, 1)
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def normalize_nfd_text(value: str) -> str:
    """Chuẩn hóa NFD, bỏ dấu thanh/dấu mũ tiếng Việt (kể cả đ -> d) để tìm kiếm không dấu."""
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    folded = stripped.replace("đ", "d").replace("Đ", "d").casefold()
    return " ".join(folded.split())


def lesson_catalog() -> list[dict[str, Any]]:
    """Trả về danh mục bộ học liệu tự biên soạn đa môn có licenseStatus='allowed'."""
    collections = [
        (
            "toan-9-dai-so-1",
            "Toán",
            "9",
            "Đại số THCS",
            "Tập 1",
            [
                (
                    "Phương trình và hệ phương trình",
                    "Phương trình bậc nhất hai ẩn",
                    "Nhận ra nghiệm dưới dạng một cặp số và kiểm tra bằng phép thế.",
                    "Một nghiệm của phương trình bậc nhất hai ẩn là cặp số làm hai vế "
                    "bằng nhau. Chẳng hạn, cặp (2; 1) thỏa mãn 2x + y = 5 do "
                    "2 nhân 2 cộng 1 bằng 5. Một phương trình có thể có nhiều cặp nghiệm.",
                ),
                (
                    "Phương trình và hệ phương trình",
                    "Giải hệ bằng phép thế",
                    "Biểu diễn một ẩn theo ẩn còn lại, giải hệ rồi thử lại.",
                    "Với hệ x + y = 7 và x − y = 1, từ phương trình đầu suy ra "
                    "y = 7 − x. Thế vào phương trình sau được 2x = 8. Cặp (4; 3) "
                    "thỏa mãn đồng thời cả hai phương trình.",
                ),
                (
                    "Phương trình và hệ phương trình",
                    "Lập hệ từ bài toán thực tế",
                    "Đặt hai ẩn, chọn điều kiện và giải thích kết quả theo ngữ cảnh.",
                    "Một nhóm mua tổng cộng 8 quyển vở và bút. Vở giá 6 nghìn đồng, "
                    "bút giá 4 nghìn đồng, tổng giá 40 nghìn đồng. Gọi x là số vở "
                    "và y là số bút, ta lập x + y = 8 và 6x + 4y = 40. "
                    "Kết quả 4 quyển vở và 4 cây bút phù hợp với điều kiện.",
                ),
                (
                    "Bất phương trình",
                    "Giải bất phương trình đơn giản",
                    "Giải bất phương trình và đổi chiều khi chia cho số âm.",
                    "Khi nhân hoặc chia hai vế của bất phương trình cho một số âm, "
                    "phải đổi chiều so sánh. Chẳng hạn, từ −2x < 6 suy ra x > −3.",
                ),
            ],
        ),
        (
            "toan-9-dai-so-2",
            "Toán",
            "9",
            "Đại số THCS",
            "Tập 2",
            [
                (
                    "Hàm số và phương trình bậc hai",
                    "Đồ thị của y = ax²",
                    "Dùng bảng giá trị để xác định các điểm và nhận ra trục đối xứng.",
                    "Đồ thị y = ax² với a khác 0 đi qua gốc tọa độ và đối xứng qua "
                    "trục tung. Với y = 2x², các điểm có hoành độ −1 và 1 đều có tung độ 2.",
                ),
                (
                    "Hàm số và phương trình bậc hai",
                    "Phương trình bậc hai và biệt thức",
                    "Tính biệt thức để phân biệt hai nghiệm, nghiệm kép và vô nghiệm thực.",
                    "Với ax² + bx + c = 0, a khác 0, biệt thức là b² − 4ac. "
                    "Phương trình x² − 5x + 6 = 0 có biệt thức 1 và hai nghiệm 2, 3.",
                ),
            ],
        ),
        (
            "toan-5-so-do",
            "Toán",
            "5",
            "Số và đo lường",
            "Tập 1",
            [
                (
                    "Số thập phân",
                    "So sánh số thập phân",
                    "So sánh từ phần nguyên tới từng hàng của phần thập phân.",
                    "Để so sánh 3,08 và 3,8, có thể viết 3,8 thành 3,80. "
                    "Hai phần nguyên đều bằng 3, nhưng hàng phần mười của 3,08 nhỏ hơn.",
                ),
            ],
        ),
        (
            "vat-li-10-chuyen-dong",
            "Vật lí",
            "10",
            "Cơ học nhập môn",
            "Tập 1",
            [
                (
                    "Động học",
                    "Tốc độ trung bình",
                    "Dùng tổng quãng đường và tổng thời gian để tính tốc độ trung bình.",
                    "Một học sinh đi 120 mét trong 30 giây rồi 60 mét trong 30 giây. "
                    "Tổng quãng đường là 180 mét, tổng thời gian là 60 giây. "
                    "Tốc độ trung bình của toàn chặng là 3 mét trên giây.",
                ),
            ],
        ),
        (
            "toan-9-hinh-hoc-1",
            "Toán",
            "9",
            "Hình học THCS",
            "Tập 1",
            [
                (
                    "Hệ thức lượng trong tam giác vuông",
                    "Tỉ số lượng giác và bài toán đo chiều cao",
                    "Vận dụng sin, cos, tan góc nhọn để giải tam giác vuông.",
                    "Trong tam giác vuông $ABC$ vuông tại $A$ có $\\alpha = \\widehat{B}$, "
                    "cạnh đối $b = AC$, cạnh kề $c = AB$ và cạnh huyền $a = BC$, ta có "
                    "$\\sin \\alpha = \\frac{b}{a}$, $\\cos \\alpha = \\frac{c}{a}$, "
                    "$\\tan \\alpha = \\frac{b}{c}$. Ví dụ: đứng cách cột cờ $20\\text{ m}$ "
                    "đo góc nâng $38^\\circ$ với mắt cao $1{,}5\\text{ m}$, chiều cao cột là "
                    "$$h = 1{,}5 + 20 \\cdot \\tan 38^\\circ \\approx 17{,}1\\text{ m}.$$",
                ),
                (
                    "Đường tròn và tứ giác nội tiếp",
                    "Đường cao, trực tâm và đường tròn ngoại tiếp",
                    "Chứng minh tứ giác nội tiếp, tam giác đồng dạng và hệ thức đường kính.",
                    "Cho tam giác nhọn $ABC$ ($AB < AC$) nội tiếp đường tròn tâm $O$. "
                    "Các đường cao $AD, BE, CF$ đồng quy tại trực tâm $H$; kẻ đường kính "
                    "$AK$ và gọi $M$ là trung điểm $BC$. Vì "
                    "$\\widehat{BEC} = \\widehat{BFC} = 90^\\circ$ nên $B, C, E, F$ cùng "
                    "thuộc đường tròn đường kính $BC$. Hai tam giác $ABD$ và $AKC$ có "
                    "$\\widehat{ADB} = \\widehat{ACK} = 90^\\circ$ và "
                    "$\\widehat{ABD} = \\widehat{AKC}$ nên $\\triangle ABD \\sim \\triangle AKC$, "
                    "suy ra $AB \\cdot AC = AD \\cdot AK$. Tứ giác $BHCK$ là hình bình hành "
                    "nên $H, M, K$ thẳng hàng và $AH = 2OM$.",
                ),
                (
                    "Bài toán thực tế và hệ phương trình",
                    "Lập hệ từ bảng định mức vận chuyển",
                    "Đọc bảng số liệu, lập hệ phương trình bậc nhất hai ẩn và thử lại.",
                    "Hai đội xe nhỏ và lớn vận chuyển vật tư theo bảng số liệu sau:\n"
                    "| Loại xe | Số chuyến mỗi xe | Sức chở (thùng/chuyến) |\n"
                    "|---|---|---|\n"
                    "| Xe cỡ nhỏ ($x$ xe) | $1$ | $15$ |\n"
                    "| Xe cỡ lớn ($y$ xe) | $1$ | $20$ |\n"
                    "Tổng số xe điều động là $22$ chiếc và tổng số thùng chở đúng $380$. "
                    "Ta lập hệ phương trình:\n"
                    "$$\\begin{cases} x + y = 22 \\\\ 15x + 20y = 380 \\end{cases}$$\n"
                    "Giải hệ được $x = 12$ xe nhỏ và $y = 10$ xe lớn. "
                    "Thử lại: $12 + 10 = 22$ và $15 \\cdot 12 + 20 \\cdot 10 = 380$.",
                ),
            ],
        ),
        (
            "toan-10-dai-so-hinh-1",
            "Toán",
            "10",
            "Đại số và Hình học THPT",
            "Tập 1",
            [
                (
                    "Hệ bất phương trình bậc nhất hai ẩn",
                    "Bài toán tối ưu tuyến tính từ bảng nguyên liệu",
                    "Biểu diễn miền nghiệm của hệ bất phương trình và tìm cực trị.",
                    "Một xưởng thủ công làm mẫu A ($x$ chiếc) và mẫu B ($y$ chiếc) "
                    "theo bảng định mức:\n"
                    "| Nguồn lực | Mẫu A | Mẫu B | Tối đa hiện có |\n"
                    "|---|---|---|---|\n"
                    "| Gỗ thông (kg) | $1$ | $2$ | $14$ |\n"
                    "| Giờ hoàn thiện (giờ) | $3$ | $1$ | $18$ |\n"
                    "| Lợi nhuận (nghìn đồng/sp) | $40$ | $50$ | — |\n"
                    "Hệ điều kiện là $x \\ge 0, y \\ge 0$, $x + 2y \\le 14$, "
                    "$3x + y \\le 18$ có các đỉnh $(0;0), (6;0), (4;5), (0;7)$. "
                    "Hàm mục tiêu $L(x, y) = 40x + 50y$ đạt lớn nhất tại $(4; 5)$ với "
                    "$L(4, 5) = 40 \\cdot 4 + 50 \\cdot 5 = 410$ nghìn đồng.",
                ),
                (
                    "Phương pháp tọa độ trong mặt phẳng",
                    "Tích vô hướng và khoảng cách từ điểm đến đường thẳng",
                    "Tính tích vô hướng hai vectơ, kiểm tra vuông góc và khoảng cách.",
                    "Trong mặt phẳng $Oxy$, tích vô hướng của $\\vec{u} = (x_1; y_1)$ và "
                    "$\\vec{v} = (x_2; y_2)$ là $\\vec{u} \\cdot \\vec{v} = x_1 x_2 + y_1 y_2$. "
                    "Khoảng cách từ $M(x_0; y_0)$ tới đường thẳng $\\Delta: ax + by + c = 0$ "
                    "là $$d(M, \\Delta) = \\frac{|ax_0 + by_0 + c|}{\\sqrt{a^2 + b^2}}.$$ "
                    "Ví dụ: $A(1; 1), B(5; 1), C(1; 4)$ có $\\overrightarrow{AB} = (4; 0)$ "
                    "và $\\overrightarrow{AC} = (0; 3)$ nên "
                    "$\\overrightarrow{AB} \\cdot \\overrightarrow{AC} = 0$, vuông tại $A$, "
                    "$AB = 4, AC = 3, BC = 5$ và diện tích $S = 6$.",
                ),
            ],
        ),
        (
            "toan-12-giai-tich-1",
            "Toán",
            "12",
            "Giải tích và Thống kê THPT",
            "Tập 1",
            [
                (
                    "Ứng dụng đạo hàm",
                    "Khảo sát cực trị hàm số bậc ba và bảng giá trị",
                    "Tìm điểm cực trị bằng đạo hàm cấp một và lập bảng xét dấu.",
                    "Xét hàm số $y = x^3 - 3x^2 + 2$ trên $\\mathbb{R}$. "
                    "Đạo hàm $y' = 3x^2 - 6x = 3x(x - 2)$ bằng $0$ tại $x = 0$ và $x = 2$. "
                    "Bảng giá trị tham chiếu:\n"
                    "| $x$ | $-1$ | $0$ | $1$ | $2$ | $3$ |\n"
                    "|---|---|---|---|---|---|\n"
                    "| $y$ | $-2$ | $2$ | $0$ | $-2$ | $2$ |\n"
                    "Hàm số đạt cực đại tại $x = 0$ ($y_{\\text{CĐ}} = 2$) và đạt cực tiểu "
                    "tại $x = 2$ ($y_{\\text{CT}} = -2$).",
                ),
                (
                    "Nguyên hàm và Tích phân",
                    "Diện tích hình phẳng giới hạn bởi hai đường cong",
                    "Thiết lập tích phân xác định và tính chính xác diện tích hình phẳng.",
                    "Diện tích hình phẳng giới hạn bởi $y = f(x)$, $y = g(x)$ liên tục "
                    "trên $[a; b]$ và $x = a, x = b$ là "
                    "$$S = \\int_a^b |f(x) - g(x)|\\,dx.$$ "
                    "Ví dụ: hai đường $y = 2x$ và $y = x^2$ cắt nhau tại $x = 0$ và $x = 2$. "
                    "Trên $[0; 2]$ có $2x \\ge x^2$, nên "
                    "$$S = \\int_0^2 (2x - x^2)\\,dx = "
                    "\\left[x^2 - \\frac{x^3}{3}\\right]_0^2 = 4 - \\frac{8}{3} = \\frac{4}{3}.$$",
                ),
            ],
        ),
        (
            "ngu-van-9-doc-hieu-1",
            "Ngữ văn",
            "9",
            "Ngữ liệu Đọc hiểu THCS",
            "Tập 1",
            [
                (
                    "Đọc hiểu văn bản tự sự",
                    "Ngữ liệu: Chiếc đèn dầu và cuốn sổ tay trạm khí tượng",
                    "Đọc hiểu chi tiết tiêu biểu, biện pháp tu từ và thông điệp.",
                    "[Đoạn 1] Chập tối, gió mùa thổi ràn rạt qua hàng phi lao quanh trạm "
                    "khí tượng ven đồi. Ngoài sân, thùng đo mưa đặt cách hàng rào tre mười "
                    "bước chân cứ rung lên bần bật. Minh — cậu thực tập sinh vừa về trạm "
                    "tuần trước — nhìn qua ô cửa kính mờ hơi nước, băn khoăn tự hỏi có "
                    "cần ra sân đọc vạch đo đúng giờ mười chín giờ hay chờ ngớt gió.\n"
                    "[Đoạn 2] Ông Hòa, người trực trạm hai mươi năm, lặng lẽ thắp chiếc "
                    "đèn dầu có chụp kính chắn gió rồi đặt cuốn sổ tay bìa vải nâu lên bàn "
                    "gỗ. Ông bảo: 'Số liệu thời tiết giống như nhịp tim của bầu trời; bỏ "
                    "sót một giờ là chuỗi quan trắc cả tháng mất đi độ tin cậy.' Ánh đèn "
                    "vàng hắt lên trang giấy kẻ ô ngay ngắn, nơi từng con số lượng mưa "
                    "được ghi bằng mực xanh kèm dấu kiểm chéo cẩn thận.\n"
                    "[Đoạn 3] Hai chú cháu khoác áo mưa đi ra sân, nương theo ánh đèn để "
                    "đọc đúng mức nước đến từng phần mười mi-li-mét. Trở vào phòng, Minh "
                    "tự tay ghi giờ quan trắc vào sổ và nhận ra sự chính xác không đến "
                    "từ lời hứa suông mà từ những bước chân bền bỉ giữa đêm gió.",
                ),
                (
                    "Đọc hiểu văn bản nghị luận",
                    "Ngữ liệu: Giá trị của việc tự kiểm chứng thông tin",
                    "Nhận diện luận điểm, lí lẽ, bằng chứng và viết đoạn nghị luận ngắn.",
                    "[Đoạn 1] Trong nhịp sống số hóa, mỗi người có thể tiếp nhận hàng trăm "
                    "tin tức chỉ trong vài phút. Tuy vậy, tốc độ lan truyền nhanh không đồng "
                    "nghĩa với độ tin cậy cao; một chi tiết bị cắt xén ngữ cảnh có thể dẫn "
                    "đến hiểu lầm dây chuyền.\n"
                    "[Đoạn 2] Tự kiểm chứng thông tin là thói quen đối chiếu nguồn gốc, "
                    "kiểm tra số liệu ban đầu và phân biệt rõ giữa dữ kiện quan sát được "
                    "với suy đoán chủ quan. Khi làm bài thực hành, việc ghi rõ nguồn trích "
                    "và kiểm tra lại phép tính giúp tránh lặp lại sai sót.\n"
                    "[Đoạn 3] Rèn luyện tinh thần kiểm chứng không làm chậm bước tiến của "
                    "tri thức mà tạo nền tảng vững chắc để mỗi kết luận đưa ra đều minh bạch.",
                ),
            ],
        ),
        (
            "ngu-van-11-doc-hieu-1",
            "Ngữ văn",
            "11",
            "Ngữ liệu Đọc hiểu THPT",
            "Tập 1",
            [
                (
                    "Văn bản thông tin tổng hợp",
                    "Ngữ liệu: Bảo tồn tri thức nghề gốm ven sông",
                    "Phân tích cách trình bày thông tin, số liệu quy trình và ý nghĩa.",
                    "[Đoạn 1] Ở xóm lò gốm ven sông Thu, đất sét trắng được lấy từ bãi bồi "
                    "tầng sâu, phơi nắng ba ngày rồi ngâm ủ trong bể nước mưa để loại bỏ "
                    "tạp chất. Người thợ gọi đó là bước 'làm sạch trí nhớ của đất' trước "
                    "khi đưa lên bàn xoay.\n"
                    "[Đoạn 2] Khâu khó nhất là theo dõi nhiệt độ lò nung qua ba giai đoạn: "
                    "sấy ẩm ở khoảng 200 độ C, nung chuyển màu quanh 900 độ C và giữ nhiệt "
                    "ổn định trên 1.150 độ C suốt sáu giờ liên tiếp. Trước đây, kinh nghiệm "
                    "nhìn màu lửa chỉ truyền miệng; gần đây, các nghệ nhân trẻ đã lập bảng "
                    "ghi chép kết hợp cảm biến nhiệt để người mới học dễ đối chiếu.\n"
                    "[Đoạn 3] Nhờ ghép nối tay nghề truyền thống với sổ đo hiện đại, tỉ lệ "
                    "sản phẩm nứt vỡ giảm rõ rệt mà nét men mộc vẫn được giữ trọn vẹn.",
                ),
                (
                    "Đọc hiểu thơ tự do",
                    "Ngữ liệu thơ: Đêm trực ở trạm bơm đầu nguồn",
                    "Phân tích hình ảnh thơ, nhịp điệu và biện pháp tu từ trong thơ tự do.",
                    "Khổ 1:\n"
                    "Đèn trạm bơm soi mặt kênh lặng lẽ\n"
                    "Tiếng máy đều như nhịp thở cánh đồng xa\n"
                    "Giọt sương khuya đậu trên bảng đồng hồ cũ\n"
                    "Giữ giùm mùa lúa mới một bình minh.\n"
                    "Khổ 2:\n"
                    "Người thợ trẻ ghi từng vạch mực nước\n"
                    "Ngoài bờ đê gió bấc thổi qua cầu\n"
                    "Cửa cống mở, dòng phù sa thức dậy\n"
                    "Chảy âm thầm vào từng thửa ruộng sâu.",
                ),
            ],
        ),
        (
            "tieng-anh-9-doc-hieu-1",
            "Tiếng Anh",
            "9",
            "Ngữ liệu Tiếng Anh THCS",
            "Tập 1",
            [
                (
                    "Reading Comprehension",
                    "School Rooftop Herb Garden",
                    "Đọc hiểu ý chính, chi tiết cụ thể và từ vựng theo ngữ cảnh.",
                    "[Paragraph 1] Last autumn, a group of ninth-grade students at Binh Minh "
                    "Secondary School turned an unused concrete rooftop into a compact herb "
                    "garden. Instead of buying expensive plastic planters, the club reused "
                    "wooden crates lined with breathable cloth and collected rainwater in "
                    "two covered barrels beside the staircase.\n"
                    "[Paragraph 2] Each week, teams measured soil moisture, recorded plant "
                    "height in a shared notebook, and harvested mint and lemongrass for the "
                    "school canteen. Teachers noticed that the green layer lowered the "
                    "afternoon ceiling temperature of the rooms below by nearly two degrees "
                    "Celsius. The project showed how simple daily habits can link science "
                    "lessons with practical care for the local environment.",
                ),
                (
                    "Grammar and Vocabulary",
                    "Conditionals, Relative Clauses and Collocations",
                    "Phân biệt câu điều kiện loại 1–2, mệnh đề quan hệ và cụm động từ.",
                    "[Notes] 1. First conditional describes real future possibilities: "
                    "'If students collect rainwater, the garden will stay green during "
                    "dry weeks.'\n"
                    "2. Second conditional expresses imaginary present situations: "
                    "'If our school had a larger yard, we would plant more shade trees.'\n"
                    "3. Relative clauses connect facts clearly: 'The wooden crates which "
                    "were repaired by volunteers now hold twenty rows of herbs.' Use 'who' "
                    "for people, 'which' for things, and 'where' for places.\n"
                    "4. Key collocations: take part in (tham gia), cut down on (cắt giảm), "
                    "carry out (tiến hành), keep track of (theo dõi).",
                ),
            ],
        ),
        (
            "tieng-anh-11-doc-hieu-1",
            "Tiếng Anh",
            "11",
            "Ngữ liệu Tiếng Anh THPT",
            "Tập 1",
            [
                (
                    "Reading Comprehension",
                    "Neighborhood Repair Cafes",
                    "Phân tích quan điểm, thông tin suy luận và từ vựng học thuật THPT.",
                    "[Paragraph 1] Every second Saturday morning, a community hall in Da "
                    "Nang hosts a volunteer repair cafe where residents bring broken fans, "
                    "torn backpacks, and slow bicycles instead of throwing them away. "
                    "Retired technicians sit beside university engineering students, sharing "
                    "diagnostic tools and explaining how simple circuits or joints work.\n"
                    "[Paragraph 2] Visitors are encouraged to watch and assist rather than "
                    "drop items off passively. According to the organizers' six-month log, "
                    "roughly seventy percent of the brought-in items returned to service "
                    "after basic soldering, cleaning, or part replacement. Beyond reducing "
                    "household waste, these gatherings build mutual trust across generations.",
                ),
                (
                    "Grammar and Discourse",
                    "Participle Clauses and Concessive Linking",
                    "Sử dụng mệnh đề phân từ rút gọn và cấu trúc nhượng bộ.",
                    "[Notes] 1. Participle clauses condense actions with the same subject: "
                    "'Equipped with basic meters, the volunteers quickly located the loose "
                    "wire.' (passive) / 'Working side by side, students and seniors fixed "
                    "twelve lamps in one morning.' (active).\n"
                    "2. Concessive structures: 'Although + clause' contrasts with "
                    "'Despite / In spite of + noun phrase/V-ing'. Example: 'Although the "
                    "toaster looked old, it worked safely after the cord was replaced.' -> "
                    "'Despite looking old, it worked safely after the cord was replaced.'",
                ),
            ],
        ),
        (
            "khtn-9-thuc-hanh-1",
            "Khoa học tự nhiên",
            "9",
            "Thực hành Khoa học tự nhiên THCS",
            "Tập 1",
            [
                (
                    "Điện học thực nghiệm",
                    "Thí nghiệm kiểm chứng định luật Ôm với bảng đo",
                    "Đọc bảng số liệu U – I và tính điện trở, công suất tỏa nhiệt.",
                    "Mục đích: khảo sát sự phụ thuộc của cường độ dòng điện $I$ vào hiệu "
                    "điện thế $U$ hai đầu điện trở mẫu. Mắc nối tiếp ampe kế và song song "
                    "vôn kế qua điện trở, thu được bảng kết quả:\n"
                    "| Lần đo | Hiệu điện thế $U$ (V) | Cường độ dòng điện $I$ (A) |\n"
                    "|---|---|---|\n"
                    "| 1 | $1{,}5$ | $0{,}15$ |\n"
                    "| 2 | $3{,}0$ | $0{,}30$ |\n"
                    "| 3 | $4{,}5$ | $0{,}45$ |\n"
                    "| 4 | $6{,}0$ | $0{,}60$ |\n"
                    "Theo định luật Ôm, $I = \\frac{U}{R}$, suy ra điện trở không đổi bằng "
                    "$R = \\frac{U}{I} = 10\\,\\Omega$. Khi $U = 6{,}0\\text{ V}$, công suất "
                    "tỏa nhiệt là $P = U I = I^2 R = 6{,}0 \\cdot 0{,}60 = 3{,}6\\text{ W}$.",
                ),
                (
                    "Chất và sự biến đổi chất",
                    "Thực hành phản ứng trung hòa và tính nồng độ",
                    "Viết phương trình hóa học dạng $\\ce{...}$ và tính nồng độ mol.",
                    "Thí nghiệm: cho $25\\text{ mL}$ dung dịch $\\ce{HCl}$ $0{,}2\\text{ M}$ "
                    "tác dụng vừa đủ với $25\\text{ mL}$ dung dịch $\\ce{NaOH}$ có nhỏ vài "
                    "giọt phenolphtalein. Phương trình hóa học:\n"
                    "$$\\ce{HCl + NaOH -> NaCl + H2O}$$\n"
                    "Số mol $\\ce{HCl}$ là $n = C_M \\cdot V = 0{,}2 \\cdot 0{,}025 = "
                    "0{,}005\\text{ mol}$. Theo tỉ lệ $1:1$, số mol $\\ce{NaOH}$ và muối "
                    "$\\ce{NaCl}$ tạo thành đều bằng $0{,}005\\text{ mol}$; nồng độ "
                    "dung dịch $\\ce{NaOH}$ là $C_M(\\ce{NaOH}) = "
                    "\\frac{0{,}005}{0{,}025} = 0{,}2\\text{ M}$.",
                ),
            ],
        ),
        (
            "vat-li-11-dien-song-1",
            "Vật lí",
            "11",
            "Vật lí thực nghiệm THPT",
            "Tập 1",
            [
                (
                    "Dòng điện không đổi",
                    "Thí nghiệm xác định suất điện động và điện trở trong",
                    "Áp dụng định luật Ôm toàn mạch để tìm $\\mathcal{E}$ và $r$.",
                    "Mắc nguồn điện có suất điện động $\\mathcal{E}$ và điện trở trong $r$ "
                    "với biến trở ngoài $R_N$. Đo được hai cặp giá trị ổn định:\n"
                    "| Phép đo | Điện trở ngoài $R_N$ ($\\Omega$) | Cường độ $I$ (A) |\n"
                    "|---|---|---|\n"
                    "| 1 | $4{,}0$ | $1{,}0$ |\n"
                    "| 2 | $9{,}0$ | $0{,}5$ |\n"
                    "Áp dụng định luật Ôm toàn mạch $$I = \\frac{\\mathcal{E}}{R_N + r}$$ "
                    "và $U_N = \\mathcal{E} - I r$, ta có $\\mathcal{E} = 1{,}0(4{,}0 + r)$ "
                    "và $\\mathcal{E} = 0{,}5(9{,}0 + r)$. Giải ra điện trở trong "
                    "$r = 1{,}0\\,\\Omega$ và suất điện động $\\mathcal{E} = 5{,}0\\text{ V}$.",
                ),
                (
                    "Sóng và giao thoa",
                    "Thí nghiệm giao thoa ánh sáng và đo bước sóng",
                    "Tính khoảng vân, bước sóng và xác định vị trí vân sáng bậc k.",
                    "Trong thí nghiệm giao thoa qua hai khe hẹp cách nhau "
                    "$a = 1{,}0\\text{ mm}$, màn quan sát cách hai khe $D = 2{,}0\\text{ m}$. "
                    "Khoảng cách giữa $6$ vân sáng liên tiếp là $6{,}0\\text{ mm}$, nên "
                    "khoảng vân $i = \\frac{6{,}0}{5} = 1{,}2\\text{ mm}$. Áp dụng "
                    "$\\lambda = \\frac{a \\cdot i}{D}$, ta tính được bước sóng "
                    "$$\\lambda = \\frac{1{,}0 \\cdot 10^{-3} \\cdot 1{,}2 \\cdot 10^{-3}}"
                    "{2{,}0} = 0{,}6\\,\\mu\\text{m}.$$",
                ),
            ],
        ),
        (
            "hoa-hoc-10-phan-ung-1",
            "Hoá học",
            "10",
            "Hóa học THPT Thực nghiệm",
            "Tập 1",
            [
                (
                    "Phản ứng oxi hóa – khử",
                    "Thực hành kim loại tác dụng với dung dịch axit",
                    "Cân bằng phản ứng oxi hóa – khử và tính thể tích khí sinh ra.",
                    "Thí nghiệm 1: Cho $6{,}5\\text{ g}$ kẽm ($\\ce{Zn}$, "
                    "$M = 65\\text{ g/mol}$) tác dụng hoàn toàn với $\\ce{HCl}$ dư: "
                    "$$\\ce{Zn + 2HCl -> ZnCl2 + H2 ^}$$\n"
                    "Số mol $\\ce{Zn}$ là $n_{\\ce{Zn}} = \\frac{6{,}5}{65} = 0{,}1\\text{ mol}$, "
                    "nhường $2e$ tạo $n_{\\ce{H2}} = 0{,}1\\text{ mol}$, thể tích "
                    "$V = 0{,}1 \\cdot 24{,}79 = 2{,}479\\text{ L}$ ở "
                    "$25^\\circ\\text{C}, 1\\text{ bar}$.\n"
                    "Thí nghiệm 2 minh họa phản ứng oxi hóa mạnh: "
                    "$$\\ce{Cu + 4HNO3(đặc) -> Cu(NO3)2 + 2NO2 ^ + 2H2O}.$$",
                ),
                (
                    "Tốc độ phản ứng hóa học",
                    "Thí nghiệm ảnh hưởng của nồng độ đến tốc độ phản ứng",
                    "Phân tích bảng thời gian và tính tốc độ trung bình.",
                    "Khảo sát $$\\ce{Na2S2O3 + H2SO4 -> Na2SO4 + SO2 ^ + S v + H2O}$$ "
                    "ở $25^\\circ\\text{C}$ bằng cách đo thời gian kết tủa lưu huỳnh:\n"
                    "| Thí nghiệm | Nồng độ $\\ce{Na2S2O3}$ (M) | Thời gian $\\Delta t$ (giây) |\n"
                    "|---|---|---|\n"
                    "| A | $0{,}10$ | $64$ |\n"
                    "| B | $0{,}20$ | $32$ |\n"
                    "| C | $0{,}40$ | $16$ |\n"
                    "Khi nồng độ tăng gấp đôi, thời gian giảm một nửa, chứng tỏ tốc độ "
                    "trung bình $v = -\\frac{\\Delta C}{\\Delta t}$ tỉ lệ thuận với nồng độ.",
                ),
            ],
        ),
        (
            "sinh-hoc-10-thuc-hanh-1",
            "Sinh học",
            "10",
            "Sinh học tế bào THPT",
            "Tập 1",
            [
                (
                    "Trao đổi chất qua màng tế bào",
                    "Thực hành quan sát co nguyên sinh ở tế bào biểu bì",
                    "Giải thích co nguyên sinh và phản co nguyên sinh theo thẩm thấu.",
                    "Đặt lớp biểu bì lá thài lài tía lần lượt vào ba môi trường cùng nhiệt độ:\n"
                    "| Môi trường | Tính chất | Trạng thái tế bào quan sát |\n"
                    "|---|---|---|\n"
                    "| Nước cất | Nhược trương | Tế bào hút nước, trương căng áp sát thành |\n"
                    "| Muối $0{,}9\\%$ | Gần đẳng trương | Nước vào ra cân bằng, giữ hình dạng |\n"
                    "| Muối $10\\%$ | Ưu trương | Mất nước, màng tách thành (co nguyên sinh) |\n"
                    "Nhỏ lại nước cất kịp thời giúp tế bào nhận nước và hồi phục sức trương.",
                ),
                (
                    "Enzim và chuyển hóa năng lượng",
                    "Thí nghiệm ảnh hưởng của nhiệt độ đến hoạt tính enzim",
                    "Nhận xét tốc độ phản ứng xúc tác của enzim theo nhiệt độ.",
                    "Đo tốc độ giải phóng bọt khí $\\ce{O2}$ từ "
                    "$\\ce{2H2O2 -> 2H2O + O2 ^}$ nhờ enzim catalaza ở $\\text{pH} = 7$:\n"
                    "| Nhiệt độ ($^\\circ\\text{C}$) | $0$ | $25$ | $37$ | $75$ |\n"
                    "|---|---|---|---|---|\n"
                    "| Mức độ sủi bọt khí | Rất ít | Mạnh | Rất mạnh | Không sủi bọt |\n"
                    "Ở $0^\\circ\\text{C}$ phân tử chuyển động chậm; quanh $37^\\circ\\text{C}$ "
                    "enzim hoạt động mạnh; ở $75^\\circ\\text{C}$ protein enzim biến tính.",
                ),
            ],
        ),
    ]
    return [
        {
            "id": str(uuid5(NAMESPACE_URL, f"soan-de-thi/hoc-lieu/{key}/1")),
            "version": 1,
            "subject": subject,
            "grade": grade,
            "book": book,
            "volume": volume,
            "name": f"{subject} {grade} · {book} · {volume}",
            "licenseStatus": "allowed",
            "licenseNote": "Ngữ liệu tự biên soạn thuộc dự án",
            "sourceOrigin": "lesson_catalog",
            "sha256": _catalog_sha256(subject, grade, book, volume, lessons),
            "lessons": [
                {
                    "number": index,
                    "chapter": chapter,
                    "title": title,
                    "outcome": outcome,
                    "text": text,
                }
                for index, (chapter, title, outcome, text) in enumerate(lessons, 1)
            ],
        }
        for key, subject, grade, book, volume, lessons in collections
    ]


def search_lesson_catalog(
    query: str = "",
    *,
    subject: str | None = None,
    grade: str | int | None = None,
    book: str | None = None,
    volume: str | None = None,
) -> list[dict[str, Any]]:
    """Lọc danh mục học liệu mẫu theo lớp/môn/bộ sách/tập và từ khóa không dấu NFD."""
    needle = normalize_nfd_text(query)
    grade_str = str(grade).strip() if grade is not None else ""
    subject_norm = normalize_nfd_text(subject) if subject else ""
    book_norm = normalize_nfd_text(book) if book else ""
    volume_norm = normalize_nfd_text(volume) if volume else ""

    matched: list[dict[str, Any]] = []
    for collection in lesson_catalog():
        if grade_str and collection["grade"] != grade_str:
            continue
        if subject_norm and normalize_nfd_text(collection["subject"]) != subject_norm:
            continue
        if book_norm and normalize_nfd_text(collection["book"]) != book_norm:
            continue
        if volume_norm and normalize_nfd_text(collection["volume"]) != volume_norm:
            continue

        lessons = collection["lessons"]
        if needle:
            lessons = [
                lesson
                for lesson in lessons
                if needle
                in normalize_nfd_text(
                    " ".join(
                        [
                            collection["subject"],
                            collection["book"],
                            collection["volume"],
                            lesson["chapter"],
                            lesson["title"],
                            lesson["outcome"],
                            lesson["text"],
                        ]
                    )
                )
            ]
        if lessons:
            matched.append({**collection, "lessons": list(lessons)})
    return matched


def to_curriculum_source_payload(
    collection: Mapping[str, Any], lesson_number: int = 1
) -> dict[str, Any]:
    """Chuyển một bài trong lesson_catalog() thành payload tương thích CurriculumSourceCreate."""
    lesson = next(
        (item for item in collection["lessons"] if item["number"] == lesson_number),
        None,
    )
    if lesson is None:
        raise ValueError(f"Không tìm thấy bài số {lesson_number} trong bộ {collection.get('id')}.")
    return {
        "grade": int(collection["grade"]),
        "subject": collection["subject"],
        "series": collection["book"],
        "volume": collection["volume"],
        "chapter": lesson["chapter"],
        "lesson": f"Bài {lesson['number']}: {lesson['title']}",
        "title": lesson["title"],
        "license_status": collection["licenseStatus"],
        "license_note": collection["licenseNote"],
        "source_origin": collection["sourceOrigin"],
        "locator": f"Bài {lesson['number']} · {lesson['chapter']}",
        "content_excerpt": (
            f"Bài {lesson['number']}. {lesson['title']}\n"
            f"{lesson['text']}\n"
            f"Mục tiêu: {lesson['outcome']}"
        ),
    }
