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


_SUBJECT_ALIASES: dict[str, frozenset[str]] = {
    "tieng viet": frozenset({"tieng viet", "ngu van"}),
    "ngu van": frozenset({"ngu van", "tieng viet"}),
}


def _grade_level(grade: str | int) -> str:
    grade_num = int(grade)
    if grade_num <= 5:
        return "Tiểu học"
    if grade_num <= 9:
        return "THCS"
    return "THPT"


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
        (
            "toan-1-so-hinh-1",
            "Toán",
            "1",
            "Số học và Hình phẳng Tiểu học",
            "Tập 1",
            [
                (
                    "Các số và phép tính trong phạm vi 100",
                    "Phép cộng và phép trừ không nhớ trong phạm vi 100",
                    "Thực hiện được phép cộng, phép trừ số có hai chữ số không nhớ.",
                    "Số có hai chữ số gồm hàng chục và hàng đơn vị, ví dụ $34 = 30 + 4$. "
                    "Khi cộng hoặc trừ không nhớ, ta tính hàng đơn vị với hàng đơn vị, "
                    "hàng chục với hàng chục:\n"
                    "| Phép tính | Tách chục và đơn vị | Kết quả |\n"
                    "|---|---|---|\n"
                    "| $23 + 15$ | $(20 + 10) + (3 + 5)$ | $38$ |\n"
                    "| $47 - 12$ | $(40 - 10) + (7 - 2)$ | $35$ |\n"
                    "Ví dụ: Tổ Một xếp được $24$ ngôi sao giấy, Tổ Hai xếp thêm $15$ ngôi sao. "
                    "Cả hai tổ có $24 + 15 = 39$ ngôi sao giấy.",
                ),
                (
                    "Hình học trực quan và đo độ dài",
                    "Nhận biết hình vuông, hình tròn, hình tam giác và đo xăng-ti-mét",
                    "Nhận dạng hình phẳng cơ bản và đọc số đo độ dài theo đơn vị cm.",
                    "Hình vuông có $4$ cạnh bằng nhau; hình tam giác có $3$ cạnh và $3$ đỉnh; "
                    "hình tròn có đường viền cong khép kín. Khi đo băng giấy bằng thước có vạch "
                    "xăng-ti-mét ($\\text{cm}$), đặt vạch $0$ trùng một đầu băng giấy. "
                    "Nếu đầu kia trùng vạch $12$ thì băng giấy dài $12\\text{ cm}$. "
                    "Ghép hai đoạn thẳng $5\\text{ cm}$ và $4\\text{ cm}$ thẳng hàng được "
                    "đoạn dài $5 + 4 = 9\\text{ cm}$.",
                ),
            ],
        ),
        (
            "tieng-viet-1-doc-viet-1",
            "Tiếng Việt",
            "1",
            "Ngữ liệu Đọc viết Tiểu học",
            "Tập 1",
            [
                (
                    "Đọc hiểu câu và đoạn ngắn",
                    "Ngữ liệu: Khu vườn nhỏ bên hiên lớp",
                    "Đọc trơn đoạn văn ngắn, tìm đúng chi tiết về sự vật trong đoạn.",
                    "[Đoạn 1] Bên hiên lớp Một A có ba chậu cây nhỏ đặt trên kệ gỗ. "
                    "Chậu đầu tiên trồng cây trầu bà lá xanh bóng. Chậu ở giữa trồng "
                    "cây hoa mười giờ nở bông hồng tươi mỗi buổi sáng nắng ấm.\n"
                    "[Đoạn 2] Giờ ra chơi, Lan và Nam dùng bình tưới nhỏ giọt nước mát "
                    "lên từng gốc cây. Nhờ được chăm sóc đều đặn, mầm non vươn lên "
                    "xanh mát cả góc hành lang.",
                ),
                (
                    "Từ ngữ và câu kể đơn giản",
                    "Từ chỉ sự vật xung quanh và câu giới thiệu",
                    "Nhận biết từ chỉ đồ vật, cây cối và đặt câu theo mẫu Ai là gì.",
                    "Từ chỉ sự vật dùng để gọi tên người, đồ vật, con vật, cây cối như: "
                    "bảng đen, viên phấn, chim sẻ, chậu hoa. Khi viết câu kể ngắn giới thiệu "
                    "sự vật, chữ cái đầu câu viết hoa và cuối câu đặt dấu chấm. "
                    "Ví dụ: 'Chiếc cặp sách là người bạn thân của em mỗi ngày đến trường.'",
                ),
            ],
        ),
        (
            "toan-2-phep-tinh-do-luong-1",
            "Toán",
            "2",
            "Phép tính và Đo lường Tiểu học",
            "Tập 1",
            [
                (
                    "Phép cộng, trừ có nhớ và bảng nhân 2, 5",
                    "Cộng trừ có nhớ trong phạm vi 100 và phép nhân, phép chia",
                    "Tính đúng phép cộng, trừ có nhớ và vận dụng bảng nhân 2, 5.",
                    "Khi cộng $38 + 25$, ta lấy $8 + 5 = 13$ viết $3$ nhớ $1$, rồi "
                    "$3 + 2 + 1 = 6$, được $63$. Phép nhân là tổng các số hạng bằng nhau:\n"
                    "| Biểu thức tổng | Phép nhân | Phép chia tương ứng |\n"
                    "|---|---|---|\n"
                    "| $2 + 2 + 2 + 2$ | $2 \\times 4 = 8$ | $8 : 2 = 4$ |\n"
                    "| $5 + 5 + 5$ | $5 \\times 3 = 15$ | $15 : 5 = 3$ |\n"
                    "Nếu xếp đều $20$ quyển truyện vào $5$ ngăn kệ thì mỗi ngăn có "
                    "$20 : 5 = 4$ quyển truyện.",
                ),
                (
                    "Đo độ dài, khối lượng và dung tích",
                    "Đổi đơn vị đề-xi-mét, mét và bài toán ki-lô-gam, lít",
                    "Quy đổi giữa m, dm, cm và giải bài toán có đơn vị kg, l.",
                    "Quan hệ giữa các đơn vị đo độ dài: $1\\text{ m} = 10\\text{ dm} = "
                    "100\\text{ cm}$, $1\\text{ dm} = 10\\text{ cm}$. Một sợi dây dài "
                    "$2\\text{ m } 4\\text{ dm}$ tức là dài $24\\text{ dm}$. "
                    "Trong đo khối lượng và dung tích: can thứ nhất đựng $12\\text{ l}$ nước, "
                    "can thứ hai đựng nhiều hơn can thứ nhất $5\\text{ l}$ nên can thứ hai "
                    "có $12 + 5 = 17\\text{ l}$ nước.",
                ),
            ],
        ),
        (
            "tieng-viet-2-doc-hieu-1",
            "Tiếng Việt",
            "2",
            "Ngữ liệu Đọc hiểu Tiểu học",
            "Tập 1",
            [
                (
                    "Đọc hiểu văn bản kể chuyện",
                    "Ngữ liệu: Chiếc đồng hồ gỗ của ông nội",
                    "Hiểu trình tự sự việc và tình cảm gia đình qua chi tiết câu chuyện.",
                    "[Đoạn 1] Trên tường phòng khách nhà Hà có treo chiếc đồng hồ vỏ gỗ "
                    "màu cánh gián. Mỗi sáng Chủ nhật, ông nội lại lấy khăn mềm lau mặt kính "
                    "và chỉnh lại kim phút cho thật chuẩn.\n"
                    "[Đoạn 2] Ông bảo tiếng tích tắc nhắc mọi người quý trọng từng phút giây "
                    "học tập và làm việc. Nghe lời ông, Hà lập bảng giờ học buổi tối và "
                    "luôn chuẩn bị sách vở gọn gàng trước khi kim ngắn chỉ chín giờ.",
                ),
                (
                    "Luyện từ và câu",
                    "Từ chỉ hoạt động, đặc điểm và dấu chấm, dấu chấm hỏi",
                    "Phân biệt từ chỉ hoạt động với từ chỉ đặc điểm; dùng đúng dấu cuối câu.",
                    "Từ chỉ hoạt động nêu việc làm như: lau kính, đọc sách, sắp xếp. "
                    "Từ chỉ đặc điểm nêu màu sắc, tính chất như: gọn gàng, ấm áp, ngay ngắn. "
                    "Cuối câu kể dùng dấu chấm (.); cuối câu hỏi dùng dấu chấm hỏi (?); "
                    "cuối câu bộc lộ cảm xúc dùng dấu chấm than (!).",
                ),
            ],
        ),
        (
            "toan-3-nhan-chia-chu-vi-1",
            "Toán",
            "3",
            "Số học và Chu vi diện tích Tiểu học",
            "Tập 1",
            [
                (
                    "Phép tính trong phạm vi 10.000",
                    "Giá trị biểu thức có dấu ngoặc và phép chia có dư",
                    "Tính đúng giá trị biểu thức số và kiểm tra số dư trong phép chia.",
                    "Trong biểu thức có dấu ngoặc, ta thực hiện phép tính trong ngoặc trước:\n"
                    "$$120 + (45 - 15) \\times 3 = 120 + 30 \\times 3 = 120 + 90 = 210.$$\n"
                    "Trong phép chia có dư $a = b \\times q + r$, số dư $r$ luôn thỏa mãn "
                    "$0 \\le r < b$. Ví dụ: $47 : 5 = 9$ (dư $2$) vì $5 \\times 9 + 2 = 47$ "
                    "và $2 < 5$.",
                ),
                (
                    "Hình học và đo diện tích",
                    "Chu vi và diện tích hình chữ nhật, hình vuông",
                    "Vận dụng công thức tính chu vi, diện tích hình chữ nhật và hình vuông.",
                    "Với hình chữ nhật có chiều dài $a$, chiều rộng $b$ (cùng đơn vị đo), "
                    "chu vi là $P = (a + b) \\times 2$ và diện tích là $S = a \\times b$. "
                    "Với hình vuông cạnh $a$, chu vi là $P = 4a$ và diện tích là $S = a^2$:\n"
                    "| Hình phẳng | Kích thước | Chu vi (cm) | Diện tích ($\\text{cm}^2$) |\n"
                    "|---|---|---|---|\n"
                    "| Hình chữ nhật | $a = 12\\text{ cm}, b = 5\\text{ cm}$ | $34$ | $60$ |\n"
                    "| Hình vuông | $a = 8\\text{ cm}$ | $32$ | $64$ |",
                ),
            ],
        ),
        (
            "tieng-viet-3-doc-hieu-1",
            "Tiếng Việt",
            "3",
            "Ngữ liệu Đọc hiểu Tiểu học",
            "Tập 1",
            [
                (
                    "Đọc hiểu văn bản miêu tả",
                    "Ngữ liệu: Buổi sáng ở trạm gác rừng thông",
                    "Nhận biết hình ảnh miêu tả thiên nhiên và ý nghĩa công việc bảo vệ rừng.",
                    "[Đoạn 1] Khi sương sớm còn vương trên những tán lá kim, chú kiểm lâm "
                    "đã mở sổ trực và kiểm tra la bàn cùng ống nhòm. Từ chòi canh cao, "
                    "cả đồi thông trải rộng như tấm thảm xanh rì nối tiếp nhau.\n"
                    "[Đoạn 2] Dọc lối mòn, các tấm biển gỗ nhắc khách đi rừng giữ vệ sinh "
                    "và phòng chống cháy. Những giọt nhựa thông trong veo tỏa hương dịu nhẹ "
                    "giữa nắng mai tinh khiết.",
                ),
                (
                    "Câu khiến, câu cảm và biện pháp so sánh",
                    "Nhận diện hình ảnh so sánh và dấu câu trong đoạn văn",
                    "Chỉ ra hai sự vật được so sánh và chuyển đổi câu kể thành câu cảm.",
                    "Biện pháp so sánh đối chiếu hai sự vật có nét tương đồng qua các từ "
                    "'như', 'tựa như', 'giống như'. Trong câu 'Đồi thông trải rộng như tấm "
                    "thảm xanh rì', đồi thông được so sánh với tấm thảm xanh. "
                    "Câu khiến dùng để nêu yêu cầu, đề nghị; câu cảm dùng để bộc lộ cảm xúc.",
                ),
            ],
        ),
        (
            "toan-4-phan-so-thong-ke-1",
            "Toán",
            "4",
            "Phân số và Hình học Tiểu học",
            "Tập 1",
            [
                (
                    "Phân số và các phép tính phân số",
                    "Rút gọn phân số, quy đồng mẫu số và cộng trừ phân số",
                    "Rút gọn được phân số tối giản và cộng, trừ hai phân số khác mẫu số.",
                    "Khi chia cả tử số và mẫu số của $\\frac{18}{24}$ cho $6$, ta được phân số "
                    "tối giản $\\frac{3}{4}$. Muốn cộng hoặc trừ hai phân số khác mẫu, ta quy "
                    "đồng mẫu số rồi cộng hoặc trừ tử số:\n"
                    "$$\\frac{2}{3} + \\frac{1}{6} = \\frac{4}{6} + \\frac{1}{6} = \\frac{5}{6}, "
                    "\\quad \\frac{7}{8} - \\frac{1}{4} = \\frac{7}{8} - \\frac{2}{8} = "
                    "\\frac{5}{8}.$$",
                ),
                (
                    "Số trung bình cộng và hình học phẳng",
                    "Trung bình cộng, bảng số liệu và góc nhọn, góc tù, góc bẹt",
                    "Tính số trung bình cộng từ bảng số liệu và phân loại các góc.",
                    "Số trung bình cộng của $n$ số bằng tổng của chúng chia cho $n$. "
                    "Bảng lượng sách quyên góp của bốn tổ lớp 4A:\n"
                    "| Tổ | Tổ 1 | Tổ 2 | Tổ 3 | Tổ 4 |\n"
                    "|---|---|---|---|---|\n"
                    "| Số quyển sách | $26$ | $30$ | $28$ | $36$ |\n"
                    "Trung bình mỗi tổ góp $(26 + 30 + 28 + 36) : 4 = 30$ quyển. "
                    "Về góc: góc vuông bằng $90^\\circ$, góc nhọn nhỏ hơn $90^\\circ$, "
                    "góc tù lớn hơn $90^\\circ$ và nhỏ hơn $180^\\circ$, "
                    "góc bẹt bằng $180^\\circ$.",
                ),
            ],
        ),
        (
            "tieng-viet-4-doc-hieu-1",
            "Tiếng Việt",
            "4",
            "Ngữ liệu Đọc hiểu Tiểu học",
            "Tập 1",
            [
                (
                    "Đọc hiểu văn bản tự sự – miêu tả",
                    "Ngữ liệu: Giỏ tre đan của làng nghề ven đê",
                    "Tìm ý chính của từng đoạn và hiểu vẻ đẹp của lao động thủ công.",
                    "[Đoạn 1] Từ những cây tre bánh tẻ thẳng đều, bác thợ chẻ từng nan mỏng "
                    "và chuốt nhẵn cạnh bằng lưỡi dao nhỏ. Nan tre được phơi qua hai nắng "
                    "để giữ độ dẻo dai và màu vàng óng tự nhiên.\n"
                    "[Đoạn 2] Dưới bàn tay khéo léo, các nan dọc nan ngang đan cài thành "
                    "chiếc giỏ đựng nông sản bền chắc. Mỗi chiếc giỏ tre thay thế hàng chục "
                    "túi ni-lông dùng một lần, góp phần giữ chợ quê sạch đẹp.",
                ),
                (
                    "Cấu tạo câu và biện pháp nhân hóa",
                    "Chủ ngữ, vị ngữ, trạng ngữ và nhân hóa trong câu văn",
                    "Xác định thành phần chính, trạng ngữ của câu và tác dụng của nhân hóa.",
                    "Trong câu 'Dưới hiên nhà, các nan tre trò chuyện rì rào theo nhịp tay "
                    "người thợ', cụm 'Dưới hiên nhà' là trạng ngữ chỉ nơi chốn; 'các nan tre' "
                    "là chủ ngữ; phần còn lại là vị ngữ. Biện pháp nhân hóa dùng từ chỉ hoạt "
                    "động của người ('trò chuyện') cho vật giúp câu văn sinh động, gần gũi.",
                ),
            ],
        ),
        (
            "toan-5-hinh-hoc-chuyen-dong-2",
            "Toán",
            "5",
            "Hình học và Chuyển động đều",
            "Tập 2",
            [
                (
                    "Diện tích và thể tích hình khối",
                    "Diện tích hình thang, hình tròn và thể tích hình hộp chữ nhật",
                    "Tính đúng diện tích hình thang, hình tròn và thể tích hình hộp chữ nhật.",
                    "Hình thang có đáy lớn $a$, đáy bé $b$, chiều cao $h$ có diện tích "
                    "$$S = \\frac{(a + b) \\times h}{2}.$$ "
                    "Hình tròn bán kính $r$ có chu vi $C = 2 \\times 3{,}14 \\times r$ và "
                    "diện tích $S = 3{,}14 \\times r^2$. Hình hộp chữ nhật kích thước "
                    "$a, b, c$ có thể tích $V = a \\times b \\times c$. Ví dụ: bể cá dài "
                    "$8\\text{ dm}$, rộng $5\\text{ dm}$, cao $6\\text{ dm}$ có thể tích "
                    "$V = 8 \\times 5 \\times 6 = 240\\text{ dm}^3 = 240\\text{ lít}$.",
                ),
                (
                    "Số đo thời gian và chuyển động đều",
                    "Quan hệ giữa vận tốc, quãng đường và thời gian",
                    "Giải bài toán chuyển động đều một xe và hai xe đi ngược chiều.",
                    "Trong chuyển động đều với vận tốc $v$, thời gian $t$ và quãng đường $s$, "
                    "ta có $s = v \\times t$, $v = \\frac{s}{t}$, $t = \\frac{s}{v}$:\n"
                    "| Phương tiện | Quãng đường $s$ (km) | Thời gian $t$ (giờ) "
                    "| Vận tốc $v$ (km/h) |\n"
                    "|---|---|---|---|\n"
                    "| Xe đạp | $27$ | $1{,}5$ | $18$ |\n"
                    "| Ô tô | $135$ | $2{,}5$ | $54$ |\n"
                    "Nếu hai xe khởi hành cùng lúc từ hai bến cách nhau $144\\text{ km}$ và đi "
                    "ngược chiều nhau thì thời gian gặp nhau là "
                    "$t = \\frac{144}{18 + 54} = 2$ giờ.",
                ),
            ],
        ),
        (
            "tieng-viet-5-doc-hieu-1",
            "Tiếng Việt",
            "5",
            "Ngữ liệu Đọc hiểu Tiểu học",
            "Tập 1",
            [
                (
                    "Đọc hiểu văn bản tự sự – biểu cảm",
                    "Ngữ liệu: Cây cầu gỗ qua suối đá",
                    "Phân tích ý nghĩa chi tiết và rút ra thông điệp về tinh thần vì cộng đồng.",
                    "[Đoạn 1] Con suối nhỏ ngăn cách xóm Bản Mới với trường tiểu học thường "
                    "dâng nước cao mỗi khi mưa đầu hạ. Trước mùa tựu trường, các bác thợ mộc "
                    "và thanh niên trong xóm cùng nhau dựng một cây cầu gỗ chắc chắn có lan "
                    "can sơn màu cam nổi bật.\n"
                    "[Đoạn 2] Trên trụ cầu, tấm bảng nhỏ ghi rõ tải trọng và lời dặn đi chậm "
                    "khi trời mưa ướt. Từ ngày có cầu mới, tiếng cười nói của học trò vang "
                    "lên rộn rã mỗi sớm mai, nối gần khoảng cách giữa bản làng với trang sách.",
                ),
                (
                    "Từ vựng và liên kết câu trong đoạn văn",
                    "Từ đồng nghĩa, từ đa nghĩa và liên kết câu bằng phép lặp, phép thế",
                    "Phân biệt nghĩa gốc với nghĩa chuyển; nhận diện phép liên kết câu.",
                    "Từ đa nghĩa có một nghĩa gốc và một hoặc nhiều nghĩa chuyển; ví dụ từ "
                    "'chân' trong 'chân người' (nghĩa gốc) và 'chân cầu', 'chân núi' (nghĩa "
                    "chuyển). Các câu trong đoạn văn liên kết với nhau bằng phép lặp từ ngữ, "
                    "phép thế đại từ hoặc dùng từ ngữ nối ('tuy nhiên', 'nhờ đó', 'vì vậy').",
                ),
            ],
        ),
        (
            "toan-6-so-hoc-hinh-1",
            "Toán",
            "6",
            "Số học và Hình học trực quan THCS",
            "Tập 1",
            [
                (
                    "Số tự nhiên và số nguyên",
                    "Ước chung lớn nhất, bội chung nhỏ nhất và phép tính số nguyên",
                    "Tìm ƯCLN, BCNN bằng phân tích thừa số nguyên tố và tính toán số nguyên.",
                    "Phân tích ra thừa số nguyên tố: $36 = 2^2 \\cdot 3^2$ và $48 = 2^4 \\cdot 3$. "
                    "Suy ra $\\text{ƯCLN}(36, 48) = 2^2 \\cdot 3 = 12$ và "
                    "$\\text{BCNN}(36, 48) = 2^4 \\cdot 3^2 = 144$. "
                    "Trên tập số nguyên $\\mathbb{Z}$, quy tắc nhân hai số nguyên âm cho kết quả "
                    "dương: $(-4) \\cdot (-7) + (-10) = 28 - 10 = 18$.",
                ),
                (
                    "Hình học trực quan và tính đối xứng",
                    "Hình bình hành, hình thoi và trục đối xứng, tâm đối xứng",
                    "Tính chu vi, diện tích hình bình hành, hình thoi và nhận biết đối xứng.",
                    "Hình bình hành cạnh $a, b$ và chiều cao $h$ ứng với cạnh $a$ có chu vi "
                    "$P = 2(a + b)$ và diện tích $S = a \\cdot h$. Hình thoi có hai đường chéo "
                    "$d_1, d_2$ có diện tích $S = \\frac{1}{2} d_1 d_2$:\n"
                    "| Hình | Số trục đối xứng | Có tâm đối xứng | Công thức diện tích |\n"
                    "|---|---|---|---|\n"
                    "| Hình chữ nhật | $2$ | Có | $S = a \\cdot b$ |\n"
                    "| Hình thoi | $2$ | Có | $S = \\frac{1}{2} d_1 d_2$ |\n"
                    "| Tam giác đều | $3$ | Không | $S = \\frac{1}{2} a \\cdot h$ |",
                ),
            ],
        ),
        (
            "ngu-van-6-doc-hieu-1",
            "Ngữ văn",
            "6",
            "Ngữ liệu Đọc hiểu THCS",
            "Tập 1",
            [
                (
                    "Đọc hiểu truyện kể ngôi thứ nhất",
                    "Ngữ liệu: Con đường gạch đỏ sau cơn mưa đầu mùa",
                    "Nhận biết ngôi kể, chi tiết miêu tả thiên nhiên và cảm xúc nhân vật.",
                    "[Đoạn 1] Cơn mưa đầu mùa vừa tạnh, con đường lát gạch đỏ dẫn vào thư "
                    "viện xã như được gội sạch bụi đất. Tôi dừng xe đạp dưới tán bàng non, "
                    "ngắm những giọt nước trong vắt đọng trên kẽ lá lấp lánh dưới nắng chiều.\n"
                    "[Đoạn 2] Bác thủ thư mở rộng cửa sổ gỗ để gió mát ùa vào gian phòng đầy "
                    "mùi giấy mới. Tôi chọn một cuốn sách viết về các loài cây bản địa, lắng "
                    "nghe tiếng chim sẻ ríu rít ngoài hiên và thấy lòng bình yên lạ thường.",
                ),
                (
                    "Thơ lục bát và thực hành tiếng Việt",
                    "Ngữ liệu thơ lục bát: Bến sông quê và từ ghép, từ láy",
                    "Nhận diện vần, nhịp thơ lục bát và phân biệt từ ghép với từ láy.",
                    "Đoạn thơ lục bát tự biên soạn:\n"
                    "Con đò neo bến sông chiều\n"
                    "Gió đưa hương lúa dập dìu bờ đê\n"
                    "Trăng lên soi bóng hàng tre\n"
                    "Nhịp chèo khua nhẹ vỗ về sóng xô.\n"
                    "Thơ lục bát gieo vần chân và vần lưng ('chiều' – 'dìu', 'đê' – 'tre' – 'về'). "
                    "Từ ghép có các tiếng đều có nghĩa ('bến sông', 'hàng tre'); từ láy có sự "
                    "hòa phối âm thanh giữa các tiếng ('dập dìu', 'lấp lánh').",
                ),
            ],
        ),
        (
            "khtn-6-thuc-hanh-1",
            "Khoa học tự nhiên",
            "6",
            "Khoa học tự nhiên THCS",
            "Tập 1",
            [
                (
                    "Các phép đo và các thể của chất",
                    "Đo chiều dài, khối lượng, nhiệt độ và sự chuyển thể",
                    "Đọc đúng giới hạn đo, độ chia nhỏ nhất và phân biệt các quá trình chuyển thể.",
                    "Khi dùng dụng cụ đo, cần xác định giới hạn đo (GHĐ) và độ chia nhỏ nhất "
                    "(ĐCNN). Bảng theo dõi nhiệt độ đun nóng băng phiến theo thời gian:\n"
                    "| Thời gian (phút) | $0$ | $2$ | $4$ | $6$ | $8$ |\n"
                    "|---|---|---|---|---|---|\n"
                    "| Nhiệt độ ($^\\circ\\text{C}$) | $60$ | $75$ | $80$ | $80$ | $86$ |\n"
                    "Trong suốt thời gian nóng chảy ở $80^\\circ\\text{C}$ (từ phút thứ $4$ đến "
                    "phút thứ $6$), nhiệt độ của chất rắn kết tinh giữ không đổi.",
                ),
                (
                    "Tế bào và lực trong đời sống",
                    "Cấu tạo tế bào thực vật, trọng lượng và lực ma sát",
                    "So sánh tế bào nhân sơ với nhân thực; tính trọng lượng từ khối lượng.",
                    "Mọi cơ thể sống đều cấu tạo từ tế bào; tế bào thực vật có thành tế bào "
                    "và lục lạp giúp thực hiện quang hợp. Trong cơ học, trọng lượng của vật "
                    "khối lượng $m$ (kg) gần bằng $P = 10m$ (N). Một vật có khối lượng "
                    "$m = 2{,}5\\text{ kg}$ chịu trọng lực $P = 10 \\cdot 2{,}5 = 25\\text{ N}$.",
                ),
            ],
        ),
        (
            "tieng-anh-6-doc-hieu-1",
            "Tiếng Anh",
            "6",
            "Ngữ liệu Tiếng Anh THCS",
            "Tập 1",
            [
                (
                    "Reading Comprehension",
                    "Morning Routine at a Riverside Boarding School",
                    "Đọc hiểu lịch sinh hoạt hằng ngày và từ vựng chủ đề trường học.",
                    "[Paragraph 1] At Hoa Binh Boarding School, students start their day at "
                    "six o'clock with twenty minutes of morning exercise in the courtyard. "
                    "After breakfast in the dining hall, they walk past a row of mango trees "
                    "to their classrooms on the second floor.\n"
                    "[Paragraph 2] Every Tuesday afternoon, the science club meets in the "
                    "laboratory to observe plant leaves under microscopes. Students enjoy "
                    "keeping their study corners tidy and helping one another with homework.",
                ),
                (
                    "Grammar and Vocabulary",
                    "Present Simple, Present Continuous and Prepositions of Place",
                    "Chia đúng thì hiện tại đơn, hiện tại tiếp diễn và giới từ chỉ vị trí.",
                    "[Notes] 1. Present Simple describes daily habits and timetables: "
                    "'The library opens at seven thirty every weekday.'\n"
                    "2. Present Continuous describes actions happening right now: "
                    "'Listen! The students are practicing a folk song in the music room.'\n"
                    "3. Prepositions of place: between (ở giữa hai vật), opposite (đối diện), "
                    "next to (bên cạnh), in front of (phía trước).",
                ),
            ],
        ),
        (
            "toan-7-dai-so-hinh-1",
            "Toán",
            "7",
            "Số hữu tỉ và Hình học phẳng THCS",
            "Tập 1",
            [
                (
                    "Số hữu tỉ và tỉ lệ thức",
                    "Tính chất dãy tỉ số bằng nhau và bài toán chia tỉ lệ",
                    "Áp dụng tính chất dãy tỉ số bằng nhau để giải bài toán thực tế.",
                    "Từ dãy tỉ số bằng nhau $\\frac{x}{a} = \\frac{y}{b} = \\frac{z}{c}$, ta có:\n"
                    "$$\\frac{x}{a} = \\frac{y}{b} = \\frac{z}{c} = "
                    "\\frac{x + y + z}{a + b + c}.$$\n"
                    "Ví dụ: Ba lớp 7A, 7B, 7C trồng tổng cộng $120$ cây xanh tỉ lệ với $3; 4; 5$. "
                    "Áp dụng dãy tỉ số bằng nhau với $3 + 4 + 5 = 12$, hệ số tỉ lệ bằng "
                    "$\\frac{120}{12} = 10$, suy ra số cây ba lớp lần lượt là $30, 40, 50$ cây.",
                ),
                (
                    "Tam giác và các đường đồng quy",
                    "Tổng ba góc của tam giác và các trường hợp bằng nhau",
                    "Chứng minh hai tam giác bằng nhau và tính chất đường trung trực, phân giác.",
                    "Trong $\\triangle ABC$, tổng ba góc luôn bằng "
                    "$\\widehat{A} + \\widehat{B} + \\widehat{C} = 180^\\circ$. "
                    "Nếu $\\triangle ABC$ cân tại $A$ có $\\widehat{A} = 40^\\circ$ thì "
                    "$\\widehat{B} = \\widehat{C} = "
                    "\\frac{180^\\circ - 40^\\circ}{2} = 70^\\circ$. "
                    "Ba đường trung tuyến của tam giác đồng quy tại trọng tâm $G$, cách mỗi "
                    "đỉnh một khoảng bằng $\\frac{2}{3}$ độ dài đường trung tuyến đi qua đỉnh đó.",
                ),
            ],
        ),
        (
            "ngu-van-7-doc-hieu-1",
            "Ngữ văn",
            "7",
            "Ngữ liệu Đọc hiểu THCS",
            "Tập 1",
            [
                (
                    "Đọc hiểu tản văn và tùy bút",
                    "Ngữ liệu: Mùi khói bếp chiều đông ở bản cao",
                    "Phân tích chất trữ tình, cái tôi tác giả và ngôn ngữ giàu hình ảnh.",
                    "[Đoạn 1] Chiều tháng Mười một, sương mù từ sườn núi tràn xuống ôm lấy "
                    "những mái nhà sàn lợp ngói âm dương. Từ từng gian bếp nhỏ, làn khói lam "
                    "mỏng mảnh bay lên, quyện với mùi củi thông khô và hương gạo nếp mới.\n"
                    "[Đoạn 2] Bên bếp lửa hồng, tiếng củi nổ lách tách hòa cùng lời kể trầm "
                    "ấm của bà về mùa gặt năm xưa. Làn khói bếp không chỉ sưởi ấm đôi bàn tay "
                    "lạnh cóng mà còn giữ lại nhịp sum vầy bền chặt của mỗi nếp nhà.",
                ),
                (
                    "Đọc hiểu nghị luận và tiếng Việt",
                    "Ngữ liệu: Thói quen ghi chép sổ tay và mở rộng thành phần câu bằng cụm từ",
                    "Nhận biết ý kiến, lí lẽ, bằng chứng và tác dụng của việc mở rộng câu.",
                    "[Đoạn 1] Ghi chép sổ tay giúp người học lưu giữ ngay những ý tưởng bất "
                    "chợt và hệ thống hóa kiến thức theo sơ đồ riêng. Khi tự tay tóm tắt một "
                    "bài đọc thành ba ý cốt lõi, trí nhớ làm việc sâu hơn so với chỉ đọc lướt.\n"
                    "[Đoạn 2] Trong ngữ pháp tiếng Việt, có thể mở rộng thành phần chính hoặc "
                    "trạng ngữ bằng cụm danh từ, cụm động từ, cụm tính từ để làm rõ số lượng, "
                    "đặc điểm và hoàn cảnh của sự việc.",
                ),
            ],
        ),
        (
            "khtn-7-thuc-hanh-1",
            "Khoa học tự nhiên",
            "7",
            "Khoa học tự nhiên THCS",
            "Tập 1",
            [
                (
                    "Nguyên tử và tốc độ chuyển động",
                    "Cấu tạo nguyên tử, bảng tuần hoàn và đồ thị quãng đường – thời gian",
                    "Xác định số proton, electron và tính tốc độ từ bảng quãng đường – thời gian.",
                    "Nguyên tử trung hòa về điện có số proton trong hạt nhân bằng số electron "
                    "ở vỏ ($Z = p = e$). Trong phần chuyển động, bảng ghi quãng đường của một "
                    "xe tự hành trong phòng thí nghiệm:\n"
                    "| Thời gian $t$ (s) | $0$ | $5$ | $10$ | $15$ |\n"
                    "|---|---|---|---|---|\n"
                    "| Quãng đường $s$ (m) | $0$ | $10$ | $20$ | $30$ |\n"
                    "Tốc độ của xe không đổi và bằng $v = \\frac{s}{t} = \\frac{30}{15} = "
                    "2{,}0\\text{ m/s} = 7{,}2\\text{ km/h}$.",
                ),
                (
                    "Trao đổi chất ở sinh vật và quang – âm học",
                    "Quang hợp, hô hấp tế bào và định luật phản xạ ánh sáng",
                    "Viết sơ đồ quang hợp, hô hấp tế bào và tính góc phản xạ ánh sáng.",
                    "Quang hợp ở lục lạp tổng hợp chất hữu cơ và giải phóng khí $\\ce{O2}$: "
                    "$$\\ce{6CO2 + 6H2O ->[ánh sáng][diệp lục] C6H12O6 + 6O2}.$$\n"
                    "Trong quang học, tia phản xạ nằm trong mặt phẳng chứa tia tới và pháp "
                    "tuyến, góc phản xạ luôn bằng góc tới ($i' = i$). Nếu tia sáng hợp với "
                    "mặt gương phẳng một góc $35^\\circ$ thì góc tới là "
                    "$i = 90^\\circ - 35^\\circ = 55^\\circ$.",
                ),
            ],
        ),
        (
            "tieng-anh-7-doc-hieu-1",
            "Tiếng Anh",
            "7",
            "Ngữ liệu Tiếng Anh THCS",
            "Tập 1",
            [
                (
                    "Reading Comprehension",
                    "Community Book-Sharing Cabinets",
                    "Đọc hiểu hoạt động cộng đồng và xác định thông tin đúng/sai trong bài.",
                    "[Paragraph 1] Two months ago, youth volunteers in Hue placed three wooden "
                    "book cabinets in neighborhood parks. Each cabinet has glass doors to keep "
                    "rain out and two shelves for children's stories and science magazines.\n"
                    "[Paragraph 2] Readers can borrow any book for free and leave another book "
                    "in its place. Every Sunday evening, a student team checks the shelves, "
                    "repairs torn covers, and updates the catalog list on a noticeboard.",
                ),
                (
                    "Grammar and Vocabulary",
                    "Past Simple, Comparisons and Quantifiers",
                    "Sử dụng thì quá khứ đơn, cấu trúc so sánh bằng và lượng từ.",
                    "[Notes] 1. Past Simple with finished time expressions (last month, two "
                    "days ago): 'Volunteers built three wooden cabinets two months ago.'\n"
                    "2. Comparisons with 'as ... as' and 'different from': 'Reading printed "
                    "books is as enjoyable as listening to audio stories.'\n"
                    "3. Quantifiers: use 'some / a lot of' in affirmative sentences, 'any' in "
                    "negatives and questions, 'much' with uncountable nouns, and 'many' with "
                    "plural countable nouns.",
                ),
            ],
        ),
        (
            "toan-8-dai-so-hinh-1",
            "Toán",
            "8",
            "Đa thức và Định lí Thalès THCS",
            "Tập 1",
            [
                (
                    "Đa thức, phân thức và hàm số bậc nhất",
                    "Hằng đẳng thức đáng nhớ, rút gọn phân thức và đồ thị y = ax + b",
                    "Phân tích đa thức thành nhân tử, rút gọn phân thức và tìm hệ số góc.",
                    "Với $x \\ne \\pm 2$, áp dụng hằng đẳng thức $x^2 - 4 = (x - 2)(x + 2)$ và "
                    "$(x + 2)^2 = x^2 + 4x + 4$, ta rút gọn phân thức:\n"
                    "$$P = \\frac{x^2 + 4x + 4}{x^2 - 4} = \\frac{(x + 2)^2}{(x - 2)(x + 2)} = "
                    "\\frac{x + 2}{x - 2}.$$\n"
                    "Tại $x = 4$, giá trị phân thức là $P = \\frac{4 + 2}{4 - 2} = 3$. "
                    "Đường thẳng $y = 2x - 3$ có hệ số góc $a = 2$ và cắt trục tung tại $(0; -3)$.",
                ),
                (
                    "Định lí Thalès và tam giác đồng dạng",
                    "Đường trung bình, tính chất phân giác và tam giác đồng dạng",
                    "Vận dụng định lí Thalès và tỉ số đồng dạng để tính độ dài đoạn thẳng.",
                    "Trong $\\triangle ABC$, nếu $MN \\parallel BC$ ($M \\in AB, N \\in AC$) thì "
                    "theo định lí Thalès và hệ quả:\n"
                    "$$\\frac{AM}{AB} = \\frac{AN}{AC} = \\frac{MN}{BC}.$$\n"
                    "Bảng số đo thực hành đo bóng nắng cùng thời điểm:\n"
                    "| Vật đo | Chiều cao thật (m) | Chiều dài bóng trên sân (m) |\n"
                    "|---|---|---|\n"
                    "| Cọc tiêu thẳng đứng | $1{,}6$ | $2{,}0$ |\n"
                    "| Cây phượng sân trường | $h$ | $11{,}5$ |\n"
                    "Vì hai tam giác vuông đồng dạng nên "
                    "$\\frac{h}{1{,}6} = \\frac{11{,}5}{2{,}0}$, "
                    "suy ra $h = 9{,}2\\text{ m}$.",
                ),
            ],
        ),
        (
            "ngu-van-8-doc-hieu-1",
            "Ngữ văn",
            "8",
            "Ngữ liệu Đọc hiểu THCS",
            "Tập 1",
            [
                (
                    "Đọc hiểu truyện ngắn hiện đại",
                    "Ngữ liệu: Người thợ sửa đàn bên phố cổ",
                    "Phân tích cốt truyện, tâm lí nhân vật và chủ đề trân trọng nghệ thuật.",
                    "[Đoạn 1] Căn gác nhỏ cuối phố Hàng Đàn quanh năm thơm mùi gỗ thông và "
                    "vec-ni. Ông Lâm ngồi bên bàn đèn, kiên nhẫn lắng nghe từng âm vực của "
                    "cây đàn ghi-ta cũ mà một cậu học trò vừa mang tới sửa trước ngày hội "
                    "diễn văn nghệ trường.\n"
                    "[Đoạn 2] Ông không chỉ thay dây mới mà còn căn chỉnh lại ngựa đàn đến "
                    "từng mi-li-mét để tiếng ngân tròn và ấm nhất. Khi trao lại cây đàn mà chỉ "
                    "nhận tiền dây, ông mỉm cười: 'Tiếng đàn trong trẻo của cháu trên sân khấu "
                    "đã là phần công quý nhất cho người thợ rồi.'",
                ),
                (
                    "Văn bản thông tin và thực hành tiếng Việt",
                    "Ngữ liệu: Bản đồ gió mùa và trợ từ, thán từ, câu hỏi tu từ",
                    "Phân tích cách triển khai thông tin và nhận diện trợ từ, thán từ.",
                    "[Đoạn 1] Các bản ghi chép khí hậu ven biển cho thấy hướng gió mùa đông "
                    "bắc và gió mùa tây nam quyết định lịch ra khơi cũng như mùa vụ nông "
                    "nghiệp. Việc kết hợp quan sát mây tầng thấp với bản đồ khí áp số giúp "
                    "ngư dân chủ động phòng tránh áp thấp nhiệt đới.\n"
                    "[Đoạn 2] Trong tiếng Việt, trợ từ ('chính', 'ngay', 'những') dùng để nhấn "
                    "mạnh sự vật được nói đến; thán từ ('a', 'ôi', 'vâng') dùng để bộc lộ cảm "
                    "xúc hoặc gọi đáp.",
                ),
            ],
        ),
        (
            "khtn-8-thuc-hanh-1",
            "Khoa học tự nhiên",
            "8",
            "Khoa học tự nhiên THCS",
            "Tập 1",
            [
                (
                    "Phản ứng hóa học và tính theo phương trình",
                    "Mol, tỉ khối chất khí và định luật bảo toàn khối lượng",
                    "Tính số mol, khối lượng chất tham gia – sản phẩm và hiệu suất phản ứng.",
                    "Theo định luật bảo toàn khối lượng, trong phản ứng nung đá vôi "
                    "$$\\ce{CaCO3 ->[t^\\circ] CaO + CO2 ^}$$\n"
                    "ta có $m_{\\ce{CaCO3}} = m_{\\ce{CaO}} + m_{\\ce{CO2}}$. Nung hoàn toàn "
                    "$20\\text{ g}$ $\\ce{CaCO3}$ ($M = 100\\text{ g/mol}$, "
                    "tức $n = 0{,}2\\text{ mol}$) "
                    "thu được $0{,}2 \\cdot 56 = 11{,}2\\text{ g}$ $\\ce{CaO}$ và "
                    "$0{,}2 \\cdot 44 = 8{,}8\\text{ g}$ khí $\\ce{CO2}$ (thể tích ở đkc là "
                    "$V = 0{,}2 \\cdot 24{,}79 = 4{,}958\\text{ L}$).",
                ),
                (
                    "Khối lượng riêng, áp suất và lực đẩy Archimedes",
                    "Thí nghiệm đo lực đẩy Archimedes và áp suất trên bề mặt",
                    "Tính khối lượng riêng $D = m/V$, áp suất $p = F/S$ và lực đẩy $F_A = dV$.",
                    "Nhúng chìm hoàn toàn một vật thể tích $V = 200\\text{ cm}^3 = "
                    "2 \\cdot 10^{-4}\\text{ m}^3$ vào nước có trọng lượng riêng "
                    "$d = 10.000\\text{ N/m}^3$. Lực đẩy Archimedes tác dụng lên vật là:\n"
                    "$$F_A = d \\cdot V = 10.000 \\cdot 2 \\cdot 10^{-4} = 2{,}0\\text{ N}.$$\n"
                    "| Trạng thái đo lực kế | Số chỉ lực kế (N) | Ý nghĩa vật lí |\n"
                    "|---|---|---|\n"
                    "| Treo vật ngoài không khí | $P = 5{,}4\\text{ N}$ "
                    "| Trọng lượng thật của vật |\n"
                    "| Nhúng chìm vật trong nước | $F = 3{,}4\\text{ N}$ "
                    "| $F_A = P - F = 2{,}0\\text{ N}$ |",
                ),
            ],
        ),
        (
            "tieng-anh-8-doc-hieu-1",
            "Tiếng Anh",
            "8",
            "Ngữ liệu Tiếng Anh THCS",
            "Tập 1",
            [
                (
                    "Reading Comprehension",
                    "Traditional Bamboo Weaving Workshop",
                    "Đọc hiểu quy trình làng nghề truyền thống và từ vựng văn hóa.",
                    "[Paragraph 1] During a weekend field trip, eighth-grade students visited "
                    "a bamboo weaving village in Thai Binh. While the master artisan was "
                    "splitting bamboo poles into thin strips, he explained how natural drying "
                    "prevents insects and keeps baskets durable for years.\n"
                    "[Paragraph 2] Students tried weaving small coasters using dyed strips in "
                    "red and natural beige. The trip helped them appreciate the patience and "
                    "geometric precision behind everyday handmade crafts.",
                ),
                (
                    "Grammar and Vocabulary",
                    "Past Continuous, Reported Speech and Phrasal Verbs",
                    "Kết hợp quá khứ tiếp diễn với quá khứ đơn và chuyển câu tường thuật.",
                    "[Notes] 1. Past Continuous vs. Past Simple: 'While the artisan was "
                    "weaving a basket, the students took notes in their journals.'\n"
                    "2. Reported speech shifts tense back one step: Direct: 'We export these "
                    "baskets to five countries,' the craftsman said. -> Indirect: The craftsman "
                    "said that they exported those baskets to five countries.\n"
                    "3. Phrasal verbs: pass down (truyền lại), set up (thành lập), look forward "
                    "to + V-ing (mong đợi).",
                ),
            ],
        ),
        (
            "lich-su-dia-li-9-1",
            "Lịch sử và Địa lí",
            "9",
            "Lịch sử và Địa lí THCS",
            "Tập 1",
            [
                (
                    "Lịch sử Việt Nam hiện đại",
                    "Công cuộc Đổi mới từ năm 1986 và tiến trình hội nhập quốc tế",
                    "Trình bày nội dung cơ bản và thành tựu của đường lối Đổi mới đất nước.",
                    "Từ cuối năm 1986, công cuộc Đổi mới ở Việt Nam tập trung chuyển đổi sang "
                    "nền kinh tế hàng hóa nhiều thành phần vận hành theo cơ chế thị trường có "
                    "sự quản lý của Nhà nước, đồng thời mở rộng quan hệ đối ngoại:\n"
                    "| Giai đoạn tiêu biểu | Trọng tâm phát triển | Dấu mốc hội nhập |\n"
                    "|---|---|---|\n"
                    "| 1986 – 1995 | Ổn định kinh tế – xã hội, đảm bảo lương thực "
                    "| Gia nhập ASEAN (1995) |\n"
                    "| 1996 – 2007 | Đẩy mạnh công nghiệp hóa, hiện đại hóa "
                    "| Gia nhập WTO (2007) |\n"
                    "| Từ 2008 đến nay | Chuyển đổi số, tăng trưởng xanh, bền vững "
                    "| Ký kết nhiều FTA thế hệ mới |",
                ),
                (
                    "Địa lí các vùng kinh tế Việt Nam",
                    "Cơ cấu kinh tế vùng và phát triển bền vững đồng bằng ven biển",
                    "Phân tích bảng cơ cấu GDP và giải pháp thích ứng biến đổi khí hậu.",
                    "Phân tích cơ cấu GRDP giả định của một vùng kinh tế trọng điểm ven biển:\n"
                    "| Khu vực kinh tế | Nông – Lâm – Thủy sản | Công nghiệp – Xây dựng "
                    "| Dịch vụ |\n"
                    "|---|---|---|---|\n"
                    "| Tỉ trọng (%) | $14{,}5\\%$ | $43{,}0\\%$ | $42{,}5\\%$ |\n"
                    "Giải pháp phát triển bền vững đồng bằng ven biển gồm: bảo vệ rừng ngập "
                    "mặn chắn sóng, chuyển đổi cơ cấu cây trồng chịu mặn và phát triển năng "
                    "lượng tái tạo kết hợp kinh tế biển xanh.",
                ),
            ],
        ),
        (
            "tin-hoc-9-thuat-toan-1",
            "Tin học",
            "9",
            "Thuật toán và Bảng tính THCS",
            "Tập 1",
            [
                (
                    "Giải quyết vấn đề với máy tính",
                    "Sơ đồ khối thuật toán, cấu trúc rẽ nhánh và cấu trúc lặp",
                    "Mô tả thuật toán bằng sơ đồ khối/mã giả và theo dõi bảng giá trị biến.",
                    "Xét thuật toán tính tổng các số chẵn từ $2$ đến $2n$ với $n = 4$: "
                    "khởi tạo $S \\leftarrow 0$, cho $i$ chạy từ $1$ đến $4$, mỗi bước cập nhật "
                    "$S \\leftarrow S + 2i$. Bảng theo dõi từng vòng lặp:\n"
                    "| Bước lặp $i$ | Giá trị cộng thêm $2i$ | Tổng tích lũy $S$ |\n"
                    "|---|---|---|\n"
                    "| $1$ | $2$ | $2$ |\n"
                    "| $2$ | $4$ | $6$ |\n"
                    "| $3$ | $6$ | $12$ |\n"
                    "| $4$ | $8$ | $20$ |\n"
                    "Khi kết thúc vòng lặp, thuật toán đưa ra kết quả $S = n(n + 1) = 20$.",
                ),
                (
                    "Bảng tính điện tử và trực quan hóa dữ liệu",
                    "Hàm điều kiện IF, hàm thống kê COUNTIF, SUMIF và biểu đồ",
                    "Viết đúng công thức bảng tính có địa chỉ tương đối, tuyệt đối và thống kê.",
                    "Trong bảng tính theo dõi điểm thực hành, địa chỉ tuyệt đối `$C$2` giữ cố "
                    "định ô hệ số khi sao chép công thức, còn địa chỉ tương đối `B4` tự động "
                    'thay đổi theo hàng. Hàm `=IF(D4>=8; "Đạt tốt"; "Cần cố gắng")` kiểm tra '
                    'điều kiện điểm; hàm `=COUNTIF(D4:D23; ">=8")` đếm số học sinh đạt từ '
                    "$8$ điểm trở lên.",
                ),
            ],
        ),
        (
            "khtn-9-quang-sinh-2",
            "Khoa học tự nhiên",
            "9",
            "Quang học và Di truyền THCS",
            "Tập 2",
            [
                (
                    "Ánh sáng và năng lượng cơ học",
                    "Khúc xạ ánh sáng, thấu kính hội tụ và định luật bảo toàn cơ năng",
                    "Tính tiêu cự, vị trí ảnh qua thấu kính hội tụ và động năng, thế năng.",
                    "Khi tia sáng truyền từ môi trường chiết suất $n_1$ sang môi trường chiết "
                    "suất $n_2$, định luật khúc xạ ánh sáng cho $n_1 \\sin i = n_2 \\sin r$. "
                    "Với vật khối lượng $m = 0{,}5\\text{ kg}$ chuyển động ở độ cao "
                    "$h = 4\\text{ m}$ với tốc độ $v = 6\\text{ m/s}$ ($g = 10\\text{ m/s}^2$), "
                    "động năng là $W_{\\text{đ}} = \\frac{1}{2}mv^2 = 9\\text{ J}$ và thế năng "
                    "trọng trường là $W_{\\text{t}} = mgh = 20\\text{ J}$, "
                    "tổng cơ năng $W = 29\\text{ J}$.",
                ),
                (
                    "Di truyền học Mendel và phân tử sinh học",
                    "Phép lai một cặp tính trạng và cấu trúc ADN, ARN",
                    "Xác định tỉ lệ kiểu gen, kiểu hình ở F2 và tính số nuclêôtit của ADN.",
                    "Trong phép lai một cặp tính trạng trội hoàn toàn $P: AA \\times aa$, đời "
                    "$F_1$ có $100\\%$ kiểu gen $Aa$; khi $F_1 \\times F_1$ ($Aa \\times Aa$), "
                    "đời $F_2$ phân li theo tỉ lệ kiểu gen $1AA : 2Aa : 1aa$ và tỉ lệ kiểu "
                    "hình $3$ trội : $1$ lặn. Trên phân tử ADN mạch kép, theo nguyên tắc bổ "
                    "sung luôn có $A = T$, $G = X$ và tổng số nuclêôtit $N = 2(A + G)$.",
                ),
            ],
        ),
        (
            "vat-li-9-dien-tu-quang-1",
            "Vật lí",
            "9",
            "Điện từ và Năng lượng THCS",
            "Tập 1",
            [
                (
                    "Điện học và công suất điện",
                    "Đoạn mạch nối tiếp, song song và điện năng tiêu thụ",
                    "Tính điện trở tương đương, công suất định mức và điện năng tiêu thụ.",
                    "Với hai điện trở $R_1 = 6\\,\\Omega$ và $R_2 = 12\\,\\Omega$: khi mắc nối "
                    "tiếp thì $R_{\\text{nt}} = R_1 + R_2 = 18\\,\\Omega$; khi mắc song song thì "
                    "$$R_{\\text{ss}} = \\frac{R_1 R_2}{R_1 + R_2} = \\frac{6 \\cdot 12}{18} = "
                    "4\\,\\Omega.$$ "
                    "Điện năng tiêu thụ trong thời gian $t$ là $A = P \\cdot t = U I t$.",
                ),
                (
                    "Cảm ứng điện từ và truyền tải điện năng",
                    "Máy biến thế và giảm hao phí trên đường dây truyền tải",
                    "Vận dụng tỉ số máy biến thế và công thức công suất hao phí tỏa nhiệt.",
                    "Trên máy biến thế có số vòng cuộn sơ cấp $N_1$ và thứ cấp $N_2$, tỉ số điện "
                    "áp hiệu dụng là $\\frac{U_1}{U_2} = \\frac{N_1}{N_2}$. Công suất hao phí do "
                    "tỏa nhiệt trên dây dẫn điện trở $R$ khi truyền công suất $P$ ở điện áp $U$ là "
                    "$$P_{\\text{hp}} = \\frac{P^2 R}{U^2},$$ nên khi tăng điện áp $U$ lên $10$ "
                    "lần thì công suất hao phí giảm đi $100$ lần.",
                ),
            ],
        ),
        (
            "ngu-van-10-doc-hieu-1",
            "Ngữ văn",
            "10",
            "Ngữ liệu Đọc hiểu THPT",
            "Tập 1",
            [
                (
                    "Đọc hiểu tự sự dân gian và sử thi",
                    "Ngữ liệu: Giếng đá cổ dưới chân núi mờ sương",
                    "Phân tích không gian nghệ thuật, hình tượng nhân vật và biểu tượng cộng đồng.",
                    "[Đoạn 1] Dưới chân dãy núi Đá Trắng có một giếng nước cổ kè bằng những "
                    "phiến đá xanh ghép khít không cần vữa. Theo lời kể của các bậc cao niên, "
                    "những người mở đất đầu tiên đã cùng nhau đào giếng suốt một mùa khô hạn "
                    "để tìm mạch nước ngầm mát lành nuôi sống cả bản làng.\n"
                    "[Đoạn 2] Quanh thành giếng, vết dây gầu năm tháng hằn sâu như những dòng "
                    "ký ức khắc vào đá. Mỗi dịp đầu xuân, dân làng lại cùng khơi trong lòng "
                    "giếng, nhắc con cháu nhớ rằng mạch nguồn chỉ bền lâu khi mọi người biết "
                    "chung tay gìn giữ.",
                ),
                (
                    "Đọc hiểu nghị luận xã hội THPT",
                    "Ngữ liệu: Bản lĩnh lắng nghe trong đối thoại học thuật",
                    "Xác định luận đề, hệ thống luận điểm và thao tác lập luận bác bỏ, so sánh.",
                    "[Đoạn 1] Trong thảo luận khoa học, nhiều người thường chuẩn bị thật kỹ "
                    "lí lẽ để bảo vệ ý kiến cá nhân nhưng lại thiếu kiên nhẫn khi nghe góc "
                    "nhìn phản biện. Một cuộc trao đổi chỉ thực sự có chiều sâu khi mỗi bên "
                    "lắng nghe để hiểu đúng luận cứ của người đối diện.\n"
                    "[Đoạn 2] Lắng nghe có bản lĩnh không phải là xuôi chiều theo số đông, mà "
                    "là sẵn sàng điều chỉnh nhận thức trước bằng chứng xác thực và giữ thái độ "
                    "tôn trọng sự thật khách quan.",
                ),
            ],
        ),
        (
            "tieng-anh-10-doc-hieu-1",
            "Tiếng Anh",
            "10",
            "Ngữ liệu Tiếng Anh THPT",
            "Tập 1",
            [
                (
                    "Reading Comprehension",
                    "Solar-Powered Irrigation in Highland Farms",
                    "Đọc hiểu văn bản công nghệ xanh, tìm từ đồng nghĩa và thông tin chi tiết.",
                    "[Paragraph 1] Smallholder farmers in a highland valley have recently "
                    "replaced diesel water pumps with solar-powered drip irrigation systems. "
                    "Panels mounted above the storage reservoir generate clean electricity "
                    "during sunny hours and fill an elevated tank.\n"
                    "[Paragraph 2] From the tank, narrow pipes deliver water directly to plant "
                    "roots, cutting water loss from evaporation by nearly forty percent. "
                    "Farmers also receive mobile alerts when soil moisture drops below optimal "
                    "levels, saving both fuel costs and manual labor.",
                ),
                (
                    "Grammar and Vocabulary",
                    "Passive Voice, Defining Relative Clauses and Word Formation",
                    "Chuyển đổi câu bị động, dùng mệnh đề quan hệ xác định và hậu tố từ loại.",
                    "[Notes] 1. Passive Voice emphasizes the action or object: "
                    "'Clean electricity is generated by solar panels during sunny hours.'\n"
                    "2. Defining relative clauses identify essential nouns: "
                    "'Farmers who use drip irrigation save up to forty percent of water.'\n"
                    "3. Word formation suffixes: evaporate (v) -> evaporation (n); "
                    "sustain (v) -> sustainable (adj) -> sustainability (n).",
                ),
            ],
        ),
        (
            "tin-hoc-10-lap-trinh-1",
            "Tin học",
            "10",
            "Khoa học máy tính và Python THPT",
            "Tập 1",
            [
                (
                    "Biểu diễn dữ liệu và mạng máy tính",
                    "Hệ nhị phân, phép toán logic mệnh đề và an toàn thông tin",
                    "Chuyển đổi số nguyên giữa hệ thập phân và hệ nhị phân; lập bảng chân trị.",
                    "Số tự nhiên trong hệ nhị phân dùng hai chữ số $0$ và $1$ theo lũy thừa cơ "
                    "số $2$: ví dụ $13_{10} = 1 \\cdot 2^3 + 1 \\cdot 2^2 + 0 \\cdot 2^1 + "
                    "1 \\cdot 2^0 = 1101_2$. Bảng phép toán logic cơ bản:\n"
                    "| $p$ | $q$ | $p \\land q$ (AND) | $p \\lor q$ (OR) | $\\neg p$ (NOT) |\n"
                    "|---|---|---|---|---|\n"
                    "| Đúng | Đúng | Đúng | Đúng | Sai |\n"
                    "| Đúng | Sai | Sai | Đúng | Sai |\n"
                    "| Sai | Sai | Sai | Sai | Đúng |",
                ),
                (
                    "Lập trình Python cơ bản",
                    "Vòng lặp for, kiểu danh sách list và hàm tự định nghĩa",
                    "Đọc hiểu đoạn mã Python xử lý danh sách và tính kết quả đầu ra.",
                    "Trong Python, danh sách `a = [3, 6, 9, 12]` có chỉ số từ `0` đến `3` và "
                    "`len(a) == 4`. Hàm tính tổng các phần tử chia hết cho $6$:\n"
                    "`def tong_chia_het_6(ds): return sum(x for x in ds if x % 6 == 0)`\n"
                    "Khi gọi `tong_chia_het_6([3, 6, 9, 12])`, các phần tử thỏa mãn điều kiện "
                    "`x % 6 == 0` là `6` và `12`, nên hàm trả về giá trị $18$.",
                ),
            ],
        ),
        (
            "toan-11-luong-giac-day-so-1",
            "Toán",
            "11",
            "Lượng giác và Dãy số THPT",
            "Tập 1",
            [
                (
                    "Hàm số lượng giác và phương trình lượng giác",
                    "Công thức lượng giác, tập giá trị và phương trình lượng giác cơ bản",
                    "Tìm giá trị lớn nhất, nhỏ nhất của hàm lượng giác và giải phương trình.",
                    "Với mọi góc $\\alpha$, ta có $\\sin^2 \\alpha + \\cos^2 \\alpha = 1$ và "
                    "$\\sin 2\\alpha = 2\\sin\\alpha\\cos\\alpha$. Hàm số $y = 2\\sin x + 3$ có "
                    "$-1 \\le \\sin x \\le 1$ nên đạt giá trị nhỏ nhất $y_{\\min} = 1$ và giá trị "
                    "lớn nhất $y_{\\max} = 5$. Phương trình $\\cos x = \\frac{1}{2} = "
                    "\\cos\\frac{\\pi}{3}$ có nghiệm:\n"
                    "$$x = \\pm\\frac{\\pi}{3} + k2\\pi \\quad (k \\in \\mathbb{Z}).$$",
                ),
                (
                    "Dãy số, cấp số cộng và cấp số nhân",
                    "Số hạng tổng quát và tổng n số hạng đầu của cấp số cộng, cấp số nhân",
                    "Tính số hạng tổng quát, tổng cấp số cộng và giới hạn dãy số.",
                    "Cấp số cộng $(u_n)$ có số hạng đầu $u_1$, công sai $d$ thì "
                    "$u_n = u_1 + (n - 1)d$ và tổng $n$ số hạng đầu là:\n"
                    "$$S_n = \\frac{n(u_1 + u_n)}{2} = \\frac{n[2u_1 + (n - 1)d]}{2}.$$\n"
                    "| Đại lượng | Cấp số cộng ($u_1 = 3, d = 4$) "
                    "| Cấp số nhân ($v_1 = 2, q = 3$) |\n"
                    "|---|---|---|\n"
                    "| Số hạng thứ $4$ | $u_4 = 3 + 3 \\cdot 4 = 15$ "
                    "| $v_4 = 2 \\cdot 3^3 = 54$ |\n"
                    "| Tổng $4$ số hạng đầu | $S_4 = \\frac{4(3 + 15)}{2} = 36$ "
                    "| $S_4 = 2 \\cdot \\frac{3^4 - 1}{3 - 1} = 80$ |",
                ),
            ],
        ),
        (
            "hoa-hoc-11-can-bang-huu-co-1",
            "Hoá học",
            "11",
            "Cân bằng hóa học và Hữu cơ THPT",
            "Tập 1",
            [
                (
                    "Cân bằng hóa học trong dung dịch",
                    "Hằng số cân bằng, pH của dung dịch và nguyên lí Le Chatelier",
                    "Tính pH dung dịch axit mạnh/bazơ mạnh và xác định chiều chuyển dịch cân bằng.",
                    "Xét cân bằng tổng hợp amoniac: "
                    "$$\\ce{N2(g) + 3H2(g) <=> 2NH3(g)} \\quad (\\Delta_r H^\\circ_{298} < 0).$$\n"
                    "Khi tăng áp suất chung hoặc giảm nhiệt độ, cân bằng chuyển dịch theo chiều "
                    "thuận tạo $\\ce{NH3}$. Với dung dịch $\\ce{HCl}$ $0{,}01\\text{ M}$, nồng độ "
                    "$[\\ce{H+}] = 10^{-2}\\text{ M}$ nên $\\text{pH} = -\\log(10^{-2}) = 2{,}0$.",
                ),
                (
                    "Đại cương hóa học hữu cơ và hiđrocacbon",
                    "Đồng đẳng, đồng phân và phản ứng của ankan, anken, ancol",
                    "Xác định công thức phân tử và tính toán phản ứng của chất hữu cơ.",
                    "Anken mạch hở có công thức chung $\\ce{C_nH_{2n}}$ ($n \\ge 2$) làm mất màu "
                    "dung dịch nước brom theo tỉ lệ mol $1:1$. Đốt cháy hoàn toàn "
                    "$0{,}1\\text{ mol}$ ancol etylic ($\\ce{C2H5OH}$):\n"
                    "$$\\ce{C2H5OH + 3O2 ->[t^\\circ] 2CO2 + 3H2O}$$\n"
                    "thu được $0{,}2\\text{ mol}$ $\\ce{CO2}$ ($8{,}8\\text{ g}$) và "
                    "$0{,}3\\text{ mol}$ $\\ce{H2O}$ ($5{,}4\\text{ g}$).",
                ),
            ],
        ),
        (
            "sinh-hoc-11-trao-doi-chat-1",
            "Sinh học",
            "11",
            "Sinh học cơ thể THPT",
            "Tập 1",
            [
                (
                    "Trao đổi chất và chuyển hóa năng lượng ở thực vật",
                    "Hấp thụ nước – khoáng ở rễ và quang hợp ở thực vật C3, C4, CAM",
                    "So sánh pha sáng, pha tối và đặc điểm thích nghi của thực vật C3, C4, CAM.",
                    "Rễ cây hấp thụ nước theo cơ chế thẩm thấu từ nơi có thế nước cao (đất) "
                    "đến nơi có thế nước thấp (tế bào lông hút). Bảng đối chiếu ba nhóm thực vật:\n"
                    "| Nhóm thực vật | Chất nhận $\\ce{CO2}$ đầu tiên | Thời điểm mở khí khổng |\n"
                    "|---|---|---|\n"
                    "| Thực vật $C_3$ (lúa, đậu) "
                    "| Hợp chất $5$ cacbon (Ribulôzơ-1,5-điphotphat) | Ban ngày |\n"
                    "| Thực vật $C_4$ (ngô, mía) "
                    "| Photphoanol piruvat ($\\text{PEP}$) | Ban ngày |\n"
                    "| Thực vật $\\text{CAM}$ (dứa, xương rồng) "
                    "| $\\text{PEP}$ (cố định $\\ce{CO2}$ ban đêm) | Ban đêm |",
                ),
                (
                    "Tuần hoàn, hô hấp và cân bằng nội môi ở động vật",
                    "Hoạt động của hệ tuần hoàn, huyết áp và điều hòa đường huyết",
                    "Giải thích biến đổi huyết áp, vận tốc máu và cơ chế insulin – glucagon.",
                    "Trong hệ mạch, huyết áp giảm dần từ động mạch chủ qua mao mạch đến tĩnh "
                    "mạch chủ, còn vận tốc máu chậm nhất ở mao mạch do tổng tiết diện mao mạch "
                    "lớn nhất. Khi nồng độ glucôzơ máu tăng sau bữa ăn, tuyến tụy tiết insulin "
                    "chuyển glucôzơ thành glicôgen dự trữ ở gan và cơ.",
                ),
            ],
        ),
        (
            "tin-hoc-11-csdl-thuat-toan-1",
            "Tin học",
            "11",
            "Cơ sở dữ liệu và Thuật toán THPT",
            "Tập 1",
            [
                (
                    "Cơ sở dữ liệu quan hệ và ngôn ngữ SQL",
                    "Khóa chính, khóa ngoại và câu lệnh truy vấn SELECT – JOIN",
                    "Xác định khóa chính, khóa ngoại và viết truy vấn SQL lọc, kết nối bảng.",
                    "Trong cơ sở dữ liệu thư viện, bảng `SACH(MaSach, TenSach, MaTheLoai)` có "
                    "khóa chính là `MaSach` và khóa ngoại `MaTheLoai` tham chiếu tới bảng "
                    "`THE_LOAI(MaTheLoai, TenTheLoai)`. Câu lệnh SQL lấy tên sách và thể loại:\n"
                    "`SELECT S.TenSach, T.TenTheLoai FROM SACH S INNER JOIN THE_LOAI T "
                    "ON S.MaTheLoai = T.MaTheLoai WHERE S.MaTheLoai = 'TH';`",
                ),
                (
                    "Kĩ thuật lập trình và thiết kế thuật toán",
                    "Tìm kiếm nhị phân, sắp xếp và độ phức tạp thời gian",
                    "Tính số bước so sánh của tìm kiếm nhị phân trên mảng đã sắp xếp.",
                    "Trên dãy đã sắp xếp tăng dần $A = [4, 9, 15, 22, 28, 35, 41]$ có $n = 7$ "
                    "phần tử (chỉ số $0..6$), tìm kiếm nhị phân giá trị $x = 28$ thực hiện:\n"
                    "| Bước | Đoạn tìm `[left..right]` | Chỉ số giữa `mid` | Giá trị `A[mid]` |\n"
                    "|---|---|---|---|\n"
                    "| $1$ | `[0..6]` | $3$ | $A[3] = 22 < 28$ |\n"
                    "| $2$ | `[4..6]` | $5$ | $A[5] = 35 > 28$ |\n"
                    "| $3$ | `[4..4]` | $4$ | $A[4] = 28$ (Tìm thấy) |\n"
                    "Độ phức tạp thời gian của tìm kiếm nhị phân là $O(\\log_2 n)$.",
                ),
            ],
        ),
        (
            "ngu-van-12-doc-hieu-1",
            "Ngữ văn",
            "12",
            "Ngữ liệu Đọc hiểu THPT",
            "Tập 1",
            [
                (
                    "Đọc hiểu phóng sự, nhật kí và hồi kí",
                    "Ngữ liệu: Những trang sổ đo thủy văn mùa lũ lớn",
                    "Phân tích tính xác thực của tư liệu phi hư cấu kết hợp cảm hứng nhân văn.",
                    "[Đoạn 1] Ngày 14 tháng 10, mực nước tại cột mốc cầu Bến Giang dâng thêm "
                    "bốn mươi xăng-ti-mét chỉ sau ba giờ mưa lớn. Trong căn buồng trực nhỏ ở "
                    "đầu đập, kỹ sư Trực vẫn đều đặn đối chiếu số liệu từ cảm biến tự động với "
                    "thước đo cơ học ngoài bờ kè để gửi bản tin cảnh báo sớm về hạ lưu.\n"
                    "[Đoạn 2] Giữa tiếng nước xiết dưới chân kè đá, từng dòng nhật kí ca trực "
                    "ghi ngắn gọn giờ mở tràn, lưu lượng xả và danh sách các thôn ven bãi đã "
                    "sơ tán an toàn. Chính những con số khô khan ấy lại chứa đựng trách nhiệm "
                    "âm thầm bảo vệ sự bình yên của hàng nghìn mái nhà.",
                ),
                (
                    "Nghị luận văn học và phong cách ngôn ngữ",
                    "Ngữ liệu: Chiều sâu nhân bản của chi tiết nghệ thuật",
                    "Phân tích vai trò của chi tiết tiêu biểu và lập luận trong văn nghị luận.",
                    "[Đoạn 1] Trong tác phẩm văn học đích thực, một chi tiết nhỏ được đặt đúng "
                    "điểm rơi tâm lí có thể soi sáng toàn bộ tính cách nhân vật và tư tưởng "
                    "của nhà văn. Chi tiết nghệ thuật cô đọng như giọt sương chứa cả sắc trời "
                    "buổi sớm.\n"
                    "[Đoạn 2] Khi phân tích văn bản, người đọc cần đặt chi tiết trong chỉnh thể "
                    "cốt truyện, giọng điệu và bối cảnh lịch sử – văn hóa để tránh suy diễn "
                    "rời rạc hoặc áp đặt khuôn mẫu có sẵn.",
                ),
            ],
        ),
        (
            "vat-li-12-nhiet-hat-nhan-1",
            "Vật lí",
            "12",
            "Vật lí nhiệt, Từ trường và Hạt nhân THPT",
            "Tập 1",
            [
                (
                    "Vật lí nhiệt và khí lí tưởng",
                    "Định luật I nhiệt động lực học và phương trình trạng thái khí lí tưởng",
                    "Vận dụng $\\Delta U = A + Q$ và phương trình $pV/T = \\text{const}$.",
                    "Theo định luật I nhiệt động lực học, độ biến thiên nội năng của hệ là "
                    "$\\Delta U = A + Q$. Với một lượng khí lí tưởng xác định chuyển từ trạng "
                    "thái $(p_1, V_1, T_1)$ sang $(p_2, V_2, T_2)$:\n"
                    "$$\\frac{p_1 V_1}{T_1} = \\frac{p_2 V_2}{T_2}.$$\n"
                    "Ví dụ: nén đẳng nhiệt ($T_1 = T_2 = 300\\text{ K}$) $6{,}0\\text{ L}$ khí ở "
                    "áp suất $p_1 = 1{,}0\\text{ bar}$ xuống thể tích $V_2 = 2{,}0\\text{ L}$ "
                    "thì áp suất tăng lên $p_2 = \\frac{p_1 V_1}{V_2} = 3{,}0\\text{ bar}$.",
                ),
                (
                    "Từ trường và vật lí hạt nhân",
                    "Suất điện động cảm ứng, lực từ và độ hụt khối hạt nhân",
                    "Tính lực từ $F = BIl\\sin\\theta$, từ thông và năng lượng liên kết hạt nhân.",
                    "Đoạn dây dẫn dài $l = 0{,}20\\text{ m}$ mang dòng điện $I = 5{,}0\\text{ A}$ "
                    "đặt vuông góc với từ trường đều $B = 0{,}40\\text{ T}$ chịu lực từ "
                    "$F = B I l \\sin 90^\\circ = 0{,}40\\text{ N}$. Trong vật lí hạt nhân, hạt "
                    "nhân $_Z^A X$ có độ hụt khối $\\Delta m = Z m_p + (A - Z) m_n - m_X$ và "
                    "năng lượng liên kết:\n"
                    "$$W_{\\text{lk}} = \\Delta m \\cdot c^2.$$",
                ),
            ],
        ),
        (
            "hoa-hoc-12-este-dien-hoa-1",
            "Hoá học",
            "12",
            "Hóa hữu cơ và Điện hóa THPT",
            "Tập 1",
            [
                (
                    "Este – lipit, cacbohiđrat và hợp chất chứa nitơ",
                    "Phản ứng xà phòng hóa este và tính chất của glucozơ, amino axit",
                    "Viết phương trình thủy phân este trong kiềm và tính khối lượng muối.",
                    "Đun nóng $0{,}15\\text{ mol}$ etyl axetat ($\\ce{CH3COOC2H5}$, "
                    "$M = 88\\text{ g/mol}$) với dung dịch $\\ce{NaOH}$ vừa đủ:\n"
                    "$$\\ce{CH3COOC2H5 + NaOH ->[t^\\circ] CH3COONa + C2H5OH}.$$\n"
                    "Khối lượng muối natri axetat ($M = 82\\text{ g/mol}$) thu được là "
                    "$m = 0{,}15 \\cdot 82 = 12{,}3\\text{ g}$. Amino axit có nhóm "
                    "$\\ce{-NH2}$ và $\\ce{-COOH}$ nên thể hiện tính chất lưỡng tính.",
                ),
                (
                    "Đại cương kim loại và điện hóa học",
                    "Suất điện động chuẩn của pin Galvani và định luật Faraday",
                    "Tính suất điện động chuẩn $E^\\circ_{\\text{pin}}$ và khối lượng điện phân.",
                    "Cho thế điện cực chuẩn $E^\\circ_{\\ce{Zn^2+/Zn}} = -0{,}76\\text{ V}$ và "
                    "$E^\\circ_{\\ce{Cu^2+/Cu}} = +0{,}34\\text{ V}$. Pin Galvani $\\ce{Zn - Cu}$ "
                    "có suất điện động chuẩn:\n"
                    "$$E^\\circ_{\\text{pin}} = E^\\circ_{\\text{catot}} - "
                    "E^\\circ_{\\text{anot}} = 0{,}34 - (-0{,}76) = 1{,}10\\text{ V}.$$\n"
                    "| Điện cực | Bán phản ứng | Vai trò trong pin Galvani |\n"
                    "|---|---|---|\n"
                    "| Điện cực $\\ce{Zn}$ | $\\ce{Zn -> Zn^2+ + 2e}$ "
                    "| Anot (cực âm, sự oxi hóa) |\n"
                    "| Điện cực $\\ce{Cu}$ | $\\ce{Cu^2+ + 2e -> Cu}$ "
                    "| Catot (cực dương, sự khử) |",
                ),
            ],
        ),
        (
            "sinh-hoc-12-di-truyen-sinh-thai-1",
            "Sinh học",
            "12",
            "Di truyền và Sinh thái học THPT",
            "Tập 1",
            [
                (
                    "Cơ chế di truyền và di truyền học quần thể",
                    "Phiên mã, dịch mã và cân bằng di truyền Hardy – Weinberg",
                    "Tính tần số alen, tần số kiểu gen trong quần thể ngẫu phối đạt cân bằng.",
                    "Quần thể ngẫu phối đạt trạng thái cân bằng Hardy – Weinberg với hai alen "
                    "$A$ (tần số $p$) và $a$ (tần số $q$, $p + q = 1$) có cấu trúc di truyền:\n"
                    "$$p^2 AA + 2pq Aa + q^2 aa = 1.$$\n"
                    "Ví dụ: nếu tần số kiểu hình lặn $aa$ bằng $q^2 = 0{,}16$ thì $q = 0{,}4$, "
                    "suy ra $p = 1 - 0{,}4 = 0{,}6$ và tỉ lệ dị hợp tử $Aa$ là "
                    "$2pq = 2 \\cdot 0{,}6 \\cdot 0{,}4 = 0{,}48$ ($48\\%$).",
                ),
                (
                    "Tiến hóa và sinh thái học",
                    "Các nhân tố tiến hóa, chuỗi thức ăn và hiệu suất sinh thái",
                    "Phân tích nhân tố tiến hóa và tính hiệu suất sinh thái giữa các bậc.",
                    "Bảng năng lượng tích lũy qua một chuỗi thức ăn đồng cỏ:\n"
                    "| Bậc dinh dưỡng | Sinh vật đại diện | Năng lượng tích lũy (kcal) |\n"
                    "|---|---|---|\n"
                    "| Bậc $1$ (Sinh vật sản xuất) | Cỏ xanh | $1{,}0 \\cdot 10^6$ |\n"
                    "| Bậc $2$ (Tiêu thụ bậc $1$) | Châu chấu | $1{,}0 \\cdot 10^5$ |\n"
                    "| Bậc $3$ (Tiêu thụ bậc $2$) | Chim sẻ | $1{,}2 \\cdot 10^4$ |\n"
                    "Hiệu suất sinh thái từ bậc $2$ sang bậc $3$ là "
                    "$H = \\frac{1{,}2 \\cdot 10^4}{1{,}0 \\cdot 10^5} \\cdot 100\\% = 12\\%$.",
                ),
            ],
        ),
        (
            "tieng-anh-12-doc-hieu-1",
            "Tiếng Anh",
            "12",
            "Ngữ liệu Tiếng Anh THPT",
            "Tập 1",
            [
                (
                    "Reading Comprehension",
                    "Urban Micro-Forests and Heat Island Mitigation",
                    "Phân tích bài đọc học thuật về đô thị bền vững, suy luận thái độ tác giả.",
                    "[Paragraph 1] Across densely populated cities, urban planners are planting "
                    "pocket-sized micro-forests on vacant lots near bus terminals and schools. "
                    "By combining native canopy trees with shrub layers, these plots grow "
                    "rapidly and absorb both stormwater runoff and traffic noise.\n"
                    "[Paragraph 2] Temperature sensors installed by environmental researchers "
                    "recorded that shaded walkways beside micro-forests remained up to three "
                    "degrees cooler than exposed asphalt streets at midday. Even modest green "
                    "corridors can substantially strengthen urban resilience.",
                ),
                (
                    "Grammar and Academic Discourse",
                    "Inversion, Cleft Sentences and Discourse Markers",
                    "Vận dụng cấu trúc đảo ngữ nhấn mạnh, câu chẻ và từ nối học thuật.",
                    "[Notes] 1. Negative inversion places the auxiliary before the subject: "
                    "'Not only do micro-forests cool the air, but they also restore bird "
                    "habitats.' / 'Seldom had residents seen such rapid tree growth.'\n"
                    "2. Cleft sentences highlight key information: "
                    "'It is native plant diversity that makes pocket forests resilient.'\n"
                    "3. Academic connectors: furthermore (hơn nữa), nevertheless (tuy nhiên), "
                    "consequently (do đó).",
                ),
            ],
        ),
        (
            "tin-hoc-12-ai-mang-web-1",
            "Tin học",
            "12",
            "Trí tuệ nhân tạo, Mạng và Web THPT",
            "Tập 1",
            [
                (
                    "Trí tuệ nhân tạo và giao thức mạng máy tính",
                    "Khái niệm hệ thống AI, học máy và bộ giao thức TCP/IP",
                    "Phân biệt các đặc trưng của AI, học có giám sát và vai trò của IP, TCP, DNS.",
                    "Trong mạng máy tính, giao thức `IP` định danh địa chỉ và định tuyến gói "
                    "tin, giao thức `TCP` đảm bảo truyền dữ liệu tin cậy theo đúng thứ tự, còn "
                    "hệ thống `DNS` phân giải tên miền thành địa chỉ IP. Trong trí tuệ nhân tạo, "
                    "bài toán học có giám sát (supervised learning) huấn luyện mô hình từ tập "
                    "dữ liệu đã được gán nhãn đầu ra chuẩn.",
                ),
                (
                    "Thiết kế trang web với HTML và CSS",
                    "Cấu trúc phần tử HTML ngữ nghĩa, bảng, biểu mẫu và bộ chọn CSS",
                    "Nhận biết thẻ HTML ngữ nghĩa và độ ưu tiên của bộ chọn `#id`, `.class`, thẻ.",
                    "Trang web chuẩn dùng các thẻ ngữ nghĩa `<header>`, `<main>`, `<section>`, "
                    "`<table>` và `<form>`. Bảng so sánh bộ chọn CSS:\n"
                    "| Bộ chọn CSS | Cú pháp ví dụ | Phạm vi áp dụng và độ ưu tiên |\n"
                    "|---|---|---|\n"
                    "| Bộ chọn thẻ | `p { line-height: 1.5; }` "
                    "| Mọi thẻ `<p>` (ưu tiên thấp nhất) |\n"
                    "| Bộ chọn lớp | `.card { padding: 12px; }` "
                    '| Các phần tử có `class="card"` |\n'
                    "| Bộ chọn định danh | `#banner { color: #1d4ed8; }` "
                    '| Phần tử có `id="banner"` (ưu tiên cao) |',
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
            "sourceTitle": f"Khung học liệu tự biên soạn · {subject} {grade} ({book})",
            "curriculumStandard": "GDPT 2018",
            "schoolYear": "2026-2027",
            "gradeLevel": _grade_level(grade),
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
    allowed_subjects = _SUBJECT_ALIASES.get(subject_norm, frozenset({subject_norm}))
    book_norm = normalize_nfd_text(book) if book else ""
    volume_norm = normalize_nfd_text(volume) if volume else ""

    exact_matched: list[dict[str, Any]] = []
    alias_matched: list[dict[str, Any]] = []
    for collection in lesson_catalog():
        if grade_str and collection["grade"] != grade_str:
            continue
        col_subject_norm = normalize_nfd_text(collection["subject"])
        if subject_norm and col_subject_norm not in allowed_subjects:
            continue
        if book_norm and normalize_nfd_text(collection["book"]) != book_norm:
            continue
        if volume_norm and normalize_nfd_text(collection["volume"]) != volume_norm:
            continue

        lessons = collection["lessons"]
        if needle:
            subject_tokens = (
                "Tiếng Việt Ngữ văn"
                if col_subject_norm in _SUBJECT_ALIASES
                else collection["subject"]
            )
            lessons = [
                lesson
                for lesson in lessons
                if needle
                in normalize_nfd_text(
                    " ".join(
                        [
                            subject_tokens,
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
            item = {**collection, "lessons": list(lessons)}
            if not subject_norm or col_subject_norm == subject_norm:
                exact_matched.append(item)
            else:
                alias_matched.append(item)
    return exact_matched + alias_matched


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
