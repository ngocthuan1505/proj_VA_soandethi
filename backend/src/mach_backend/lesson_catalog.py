"""Ngữ liệu tự biên soạn cho thư viện học liệu, theo từng bài."""

from uuid import NAMESPACE_URL, uuid5


def lesson_catalog():
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
