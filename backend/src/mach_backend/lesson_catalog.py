"""Ngữ liệu tự biên soạn cho thư viện học liệu, theo từng bài."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from mach_backend.hybrid_retrieval import expand_vi_synonyms, normalize_vi_search


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
    """Chuẩn hóa NFD, bỏ dấu tiếng Việt (kể cả đ -> d) và quy đồng chính tả i/y."""
    return normalize_vi_search(value)


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


KNTT_SERIES = "Kết nối tri thức với cuộc sống"
_VOLUME_ORDER = {
    "Cả năm": 0,
    "Tập một": 0,
    "Tập hai": 1,
    "Chuyên đề học tập": 2,
    "Tập 1": 3,
    "Tập 2": 4,
}

_KNTT_OFFICIAL_SOURCES: dict[str, tuple[str, str]] = {
    "kntt-toan-5-t1": (
        "Toán 5 – Tập một (Kết nối tri thức với cuộc sống)",
        "https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/shs-toan-tap-1.4491508429",
    ),
    "kntt-toan-5-t2": (
        "Toán 5 – Tập hai (Kết nối tri thức với cuộc sống)",
        "https://olm.vn/thu-vien-so/doc-sach/shs-toan-tap-2.4491513564",
    ),
    "kntt-toan-9-t1": (
        "Toán 9 – Tập một (Kết nối tri thức với cuộc sống)",
        "https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/shs-toan-tap-1.4491668113",
    ),
    "kntt-toan-10-t1": (
        "Toán 10 – Tập một (Kết nối tri thức với cuộc sống)",
        "https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/shs-toan-tap-1.4491362330",
    ),
    "kntt-ngu-van-12-t1": (
        "Ngữ văn 12 – Tập một (Kết nối tri thức với cuộc sống)",
        "https://sachdientu.nxbgd.vn/bg/ngu-van-12/",
    ),
    "kntt-ngu-van-12-t2": (
        "Ngữ văn 12 – Tập hai (Kết nối tri thức với cuộc sống)",
        "https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/sgv-ngu-van-12-tap-2.4503020593",
    ),
    "kntt-ngu-van-12-cd": (
        "Chuyên đề học tập Ngữ văn 12 (Kết nối tri thức với cuộc sống)",
        "https://sachdientu.nxbgd.vn/bg/ngu-van-12-chuyen-de/",
    ),
    "kntt-tieng-anh-8-t1": (
        "Tiếng Anh 8 Global Success (Sách học sinh · Kết nối tri thức với cuộc sống)",
        "https://heid.vn/product/sach-giao-khoa-tieng-anh-lop-8-global-success/",
    ),
    "kntt-khtn-8-t1": (
        "Khoa học tự nhiên 8 – Tập một (Kết nối tri thức với cuộc sống)",
        "https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/sgv-khoa-hoc-tu-nhien.4492016197",
    ),
    "kntt-khtn-8-t2": (
        "Khoa học tự nhiên 8 – Tập hai (Kết nối tri thức với cuộc sống)",
        "https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/sgv-khoa-hoc-tu-nhien.4492016197",
    ),
}


def _kntt_raw_collections() -> list[
    tuple[
        str,
        str,
        str,
        str,
        int,
        list[tuple[str, str, int, int, int, str, tuple[str, ...]]],
    ]
]:
    """Mục lục SGK Bộ Kết nối tri thức với cuộc sống (GDPT 2018) Lớp 1–12."""
    return [
        # ==================== TOÁN 1–12 ====================
        (
            "kntt-toan-1-t1",
            "Toán",
            "1",
            "Tập một",
            108,
            [
                (
                    "Chủ đề 1: Các số từ 0 đến 10",
                    "Bài 1: Các số 0, 1, 2, 3, 4, 5",
                    6,
                    13,
                    3,
                    (
                        "Nhận biết, đọc, viết và đếm các số tự nhiên từ 0 đến 5 thông qua đồ "
                        "vật trực quan."
                    ),
                    (
                        "Đếm, đọc, viết được các số từ 0 đến 5.",
                        "Nhận biết được số lượng nhóm đồ vật trong phạm vi 5.",
                    ),
                ),
                (
                    "Chủ đề 1: Các số từ 0 đến 10",
                    "Bài 2: Các số 6, 7, 8, 9, 10",
                    14,
                    21,
                    3,
                    (
                        "Mở rộng đếm, đọc, viết các số từ 6 đến 10 và so sánh số lượng hai "
                        "nhóm đồ vật."
                    ),
                    (
                        "Đếm, đọc, viết được các số từ 6 đến 10.",
                        "So sánh và sắp xếp được các số trong phạm vi 10.",
                    ),
                ),
                (
                    "Chủ đề 2: Làm quen với một số hình phẳng",
                    "Bài 6: Hình vuông, hình tròn, hình tam giác, hình chữ nhật",
                    38,
                    43,
                    2,
                    (
                        "Nhận dạng bốn hình phẳng cơ bản qua đồ vật quen thuộc trong lớp học "
                        "và gia đình."
                    ),
                    (
                        "Nhận biết được hình vuông, hình tròn, hình tam giác, hình chữ nhật.",
                        "Ghép và xếp được hình đơn giản từ các mảnh ghép phẳng.",
                    ),
                ),
                (
                    "Chủ đề 3: Phép cộng, phép trừ trong phạm vi 10",
                    "Bài 10: Phép cộng trong phạm vi 10",
                    56,
                    63,
                    4,
                    (
                        "Hình thành khái niệm phép cộng qua thao tác gộp hai nhóm đồ vật và "
                        "lập bảng cộng trong phạm vi 10."
                    ),
                    (
                        "Thực hiện được phép cộng các số trong phạm vi 10.",
                        "Nêu được phép cộng thích hợp với tranh vẽ hoặc tình huống thực tế.",
                    ),
                ),
                (
                    "Chủ đề 3: Phép cộng, phép trừ trong phạm vi 10",
                    "Bài 11: Phép trừ trong phạm vi 10",
                    64,
                    71,
                    4,
                    (
                        "Hình thành khái niệm phép trừ qua thao tác tách bớt và mối liên hệ "
                        "giữa phép cộng, phép trừ."
                    ),
                    (
                        "Thực hiện được phép trừ các số trong phạm vi 10.",
                        "Vận dụng phép trừ giải quyết tình huống đơn giản.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-1-t2",
            "Toán",
            "1",
            "Tập hai",
            104,
            [
                (
                    "Chủ đề 6: Các số đến 100",
                    "Bài 21: Số có hai chữ số",
                    4,
                    15,
                    4,
                    (
                        "Nhận biết cấu tạo thập phân gồm hàng chục, hàng đơn vị của các số từ "
                        "10 đến 99."
                    ),
                    (
                        "Đếm, đọc, viết được các số có hai chữ số.",
                        "Phân tích được số có hai chữ số thành chục và đơn vị.",
                    ),
                ),
                (
                    "Chủ đề 7: Độ dài và đo độ dài",
                    "Bài 25: Dài hơn, ngắn hơn và đơn vị xăng-ti-mét",
                    28,
                    35,
                    3,
                    "So sánh trực tiếp độ dài hai vật và sử dụng thước có vạch xăng-ti-mét để đo.",
                    (
                        "So sánh được độ dài hai vật bằng trực giác hoặc thước đo.",
                        "Đo và ước lượng được độ dài theo đơn vị cm.",
                    ),
                ),
                (
                    "Chủ đề 8: Phép cộng, phép trừ (không nhớ) trong phạm vi 100",
                    "Bài 31: Phép cộng số có hai chữ số với số có hai chữ số",
                    52,
                    59,
                    4,
                    "Đặt tính và tính phép cộng không nhớ trong phạm vi 100 theo cột dọc.",
                    (
                        "Thực hiện được phép cộng không nhớ trong phạm vi 100.",
                        "Giải được bài toán thực tế có một bước tính cộng.",
                    ),
                ),
                (
                    "Chủ đề 9: Thời gian, giờ và lịch",
                    "Bài 36: Thực hành xem lịch và giờ",
                    76,
                    83,
                    3,
                    "Đọc giờ đúng trên đồng hồ kim và nhận biết các ngày trong tuần trên tờ lịch.",
                    (
                        "Xem được giờ đúng trên đồng hồ và gọi tên các thứ trong tuần.",
                        "Gắn thời điểm trong ngày với hoạt động sinh hoạt quen thuộc.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-2-t1",
            "Toán",
            "2",
            "Tập một",
            124,
            [
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 3: Các thành phần của phép cộng, phép trừ",
                    13,
                    18,
                    3,
                    (
                        "Nhận biết số hạng, tổng, số bị trừ, số trừ, hiệu và ứng dụng giải "
                        "bài toán nhiều hơn, ít hơn."
                    ),
                    (
                        "Gọi đúng tên các thành phần của phép cộng và phép trừ.",
                        "Giải được bài toán về nhiều hơn, ít hơn một số đơn vị.",
                    ),
                ),
                (
                    "Chủ đề 2: Phép cộng, phép trừ trong phạm vi 20",
                    "Bài 7: Phép cộng (qua 10) trong phạm vi 20",
                    26,
                    33,
                    4,
                    "Tính nhẩm phép cộng qua 10 bằng cách tách số tạo thành tròn chục.",
                    (
                        "Thực hiện thành thạo phép cộng qua 10 trong phạm vi 20.",
                        "Vận dụng tính nhẩm giải bài toán thực tế.",
                    ),
                ),
                (
                    "Chủ đề 3: Làm quen với khối lượng, dung tích",
                    "Bài 15: Ki-lô-gam và Lít",
                    56,
                    65,
                    3,
                    (
                        "Nhận biết đơn vị đo khối lượng kg, đơn vị đo dung tích l và thực "
                        "hành cân, đong."
                    ),
                    (
                        "Đọc được số đo khối lượng (kg) và dung tích (l) trên dụng cụ đo.",
                        "Tính toán được với số đo kg, l trong bài toán có lời văn.",
                    ),
                ),
                (
                    "Chủ đề 4: Phép cộng, phép trừ (có nhớ) trong phạm vi 100",
                    "Bài 19: Phép cộng (có nhớ) số có hai chữ số với số có hai chữ số",
                    72,
                    79,
                    4,
                    "Đặt tính theo cột dọc và thực hiện nhớ 1 sang hàng chục trong phép cộng.",
                    (
                        "Tính đúng phép cộng có nhớ trong phạm vi 100.",
                        "Kiểm tra lại kết quả bằng ước lượng đơn giản.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-2-t2",
            "Toán",
            "2",
            "Tập hai",
            124,
            [
                (
                    "Chủ đề 8: Phép nhân, phép chia",
                    "Bài 37: Phép nhân và bảng nhân 2, bảng nhân 5",
                    4,
                    15,
                    5,
                    (
                        "Nhận biết phép nhân là tổng các số hạng bằng nhau; thuộc bảng nhân 2 "
                        "và bảng nhân 5."
                    ),
                    (
                        "Viết được phép nhân tương ứng với tổng các số hạng bằng nhau.",
                        "Vận dụng bảng nhân 2, 5 tính nhẩm và giải toán.",
                    ),
                ),
                (
                    "Chủ đề 8: Phép nhân, phép chia",
                    "Bài 41: Phép chia và bảng chia 2, bảng chia 5",
                    16,
                    25,
                    4,
                    (
                        "Hình thành phép chia từ bài toán chia đều và lập bảng chia 2, chia 5 "
                        "từ bảng nhân."
                    ),
                    (
                        "Thực hiện được phép chia trong bảng chia 2 và bảng chia 5.",
                        "Nhận biết mối liên hệ giữa phép nhân và phép chia.",
                    ),
                ),
                (
                    "Chủ đề 11: Độ dài và đơn vị đo độ dài. Tiền Việt Nam",
                    "Bài 53: Đơn vị đo độ dài đề-xi-mét, mét, ki-lô-mét",
                    58,
                    67,
                    4,
                    (
                        "Nhận biết quan hệ quy đổi giữa cm, dm, m, km và ước lượng khoảng "
                        "cách thực tế."
                    ),
                    (
                        "Đổi được đơn vị đo độ dài giữa m, dm, cm.",
                        "Chọn đơn vị đo phù hợp cho đồ vật và quãng đường.",
                    ),
                ),
                (
                    "Chủ đề 12: Phép cộng, phép trừ trong phạm vi 1000",
                    "Bài 61: Phép cộng, phép trừ (không nhớ) trong phạm vi 1000",
                    82,
                    91,
                    4,
                    "Đặt tính và tính phép cộng, trừ số có ba chữ số không nhớ.",
                    (
                        "Thực hiện được phép cộng, phép trừ không nhớ trong phạm vi 1000.",
                        "Giải được bài toán có một bước tính trong phạm vi 1000.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-3-t1",
            "Toán",
            "3",
            "Tập một",
            124,
            [
                (
                    "Chủ đề 2: Bảng nhân, bảng chia",
                    "Bài 8: Luyện tập bảng nhân 6, 7, 8, 9",
                    24,
                    37,
                    5,
                    (
                        "Xây dựng và ghi nhớ các bảng nhân, bảng chia 6, 7, 8, 9 qua quy luật "
                        "tăng dần."
                    ),
                    (
                        "Thuộc và vận dụng được bảng nhân, bảng chia 6, 7, 8, 9.",
                        "Giải được bài toán gấp một số lên nhiều lần và giảm một số đi nhiều lần.",
                    ),
                ),
                (
                    "Chủ đề 4: Phép nhân, phép chia trong phạm vi 100",
                    "Bài 23: Nhân số có hai chữ số với số có một chữ số",
                    68,
                    72,
                    3,
                    "Đặt tính nhân theo cột dọc và thực hiện phép chia hết, phép chia có dư.",
                    (
                        "Thực hiện được phép nhân, chia số có hai chữ số cho số có một chữ số.",
                        "Kiểm tra điều kiện số dư luôn bé hơn số chia.",
                    ),
                ),
                (
                    "Chủ đề 6: Phép nhân, phép chia trong phạm vi 1000",
                    "Bài 38: Biểu thức số và tính giá trị biểu thức số",
                    103,
                    111,
                    4,
                    (
                        "Vận dụng quy tắc thứ tự thực hiện phép tính có cộng, trừ, nhân, chia "
                        "và dấu ngoặc."
                    ),
                    (
                        "Tính đúng giá trị biểu thức số có đến hai dấu phép tính và dấu ngoặc.",
                        "Vận dụng biểu thức số để giải bài toán có hai bước tính.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-3-t2",
            "Toán",
            "3",
            "Tập hai",
            124,
            [
                (
                    "Chủ đề 8: Các số đến 10 000",
                    "Bài 45: Các số có bốn chữ số và làm tròn số",
                    4,
                    15,
                    4,
                    "Đọc, viết, so sánh số đến 10 000 và làm tròn số đến hàng chục, hàng trăm.",
                    (
                        "Nhận biết cấu tạo thập phân của số có bốn chữ số.",
                        "Làm tròn được số đến hàng chục, hàng trăm gần nhất.",
                    ),
                ),
                (
                    "Chủ đề 9: Chu vi, diện tích một số hình phẳng",
                    "Bài 51: Diện tích của một hình và đơn vị xăng-ti-mét vuông",
                    26,
                    35,
                    4,
                    (
                        "Hình thành biểu tượng diện tích, đơn vị cm² và công thức diện tích "
                        "hình chữ nhật, hình vuông."
                    ),
                    (
                        "Tính được chu vi và diện tích hình chữ nhật, hình vuông.",
                        "Giải được bài toán thực tế gắn với chu vi, diện tích.",
                    ),
                ),
                (
                    "Chủ đề 14: Nhân, chia trong phạm vi 100 000",
                    "Bài 67: Thực hành xem đồng hồ, tiền Việt Nam và thống kê đơn giản",
                    80,
                    95,
                    4,
                    (
                        "Đọc bảng số liệu thống kê, làm quen khả năng xảy ra của sự kiện và "
                        "tính toán tiền Việt Nam."
                    ),
                    (
                        "Thu thập, phân loại và đọc được bảng số liệu đơn giản.",
                        "Nêu được các khả năng xảy ra của một sự kiện đơn giản.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-4-t1",
            "Toán",
            "4",
            "Tập một",
            128,
            [
                (
                    "Chủ đề 2: Góc và đơn vị đo góc",
                    "Bài 8: Góc nhọn, góc tù, góc bẹt và đo góc bằng thước đo góc",
                    26,
                    34,
                    3,
                    "Phân loại góc nhọn, góc vuông, góc tù, góc bẹt và sử dụng thước đo độ.",
                    (
                        "Nhận biết và đo được số đo các loại góc cơ bản.",
                        "Nhận biết được hai đường thẳng vuông góc, hai đường thẳng song song.",
                    ),
                ),
                (
                    "Chủ đề 3: Số có nhiều chữ số",
                    "Bài 12: Các số trong phạm vi lớp triệu",
                    40,
                    49,
                    4,
                    (
                        "Đọc, viết, phân tích hàng và lớp của số đến lớp triệu; làm tròn đến "
                        "hàng trăm nghìn."
                    ),
                    (
                        "Đọc, viết và so sánh được các số đến lớp triệu.",
                        "Nhận biết giá trị theo vị trí của chữ số trong số nhiều chữ số.",
                    ),
                ),
                (
                    "Chủ đề 6: Đường thẳng vuông góc, đường thẳng song song",
                    "Bài 29: Hình bình hành và hình thoi",
                    96,
                    103,
                    3,
                    (
                        "Khám phá tính chất cạnh đối song song bằng nhau của hình bình hành "
                        "và bốn cạnh bằng nhau của hình thoi."
                    ),
                    (
                        "Nhận biết được đặc điểm cơ bản của hình bình hành và hình thoi.",
                        "Vẽ và ghép được hình bình hành, hình thoi trên lưới ô vuông.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-4-t2",
            "Toán",
            "4",
            "Tập hai",
            128,
            [
                (
                    "Chủ đề 8: Phép nhân và phép chia",
                    "Bài 44: Chia cho số có hai chữ số",
                    22,
                    29,
                    4,
                    "Thực hiện đặt tính chia cho số có hai chữ số và tìm số trung bình cộng.",
                    (
                        "Thực hiện thành thạo phép nhân, phép chia cho số có hai chữ số.",
                        "Giải được bài toán tìm số trung bình cộng và rút về đơn vị.",
                    ),
                ),
                (
                    "Chủ đề 10: Phân số",
                    "Bài 53: Khái niệm phân số và tính chất cơ bản của phân số",
                    49,
                    61,
                    4,
                    "Nhận biết tử số, mẫu số; rút gọn, quy đồng mẫu số và so sánh phân số.",
                    (
                        "Đọc, viết, rút gọn và quy đồng được hai phân số.",
                        "So sánh và sắp xếp được các phân số theo thứ tự.",
                    ),
                ),
                (
                    "Chủ đề 11: Phép cộng, phép trừ phân số",
                    "Bài 60: Phép cộng, phép trừ, phép nhân và phép chia phân số",
                    74,
                    95,
                    5,
                    "Thực hiện bốn phép tính với phân số cùng mẫu và khác mẫu số.",
                    (
                        "Tính đúng tổng, hiệu, tích, thương của hai phân số.",
                        "Giải được bài toán tìm phân số của một số.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-5-t1",
            "Toán",
            "5",
            "Tập một",
            128,
            [
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 1: Ôn tập số tự nhiên",
                    6,
                    8,
                    2,
                    "Ôn tập đọc, viết, so sánh số tự nhiên và cấu tạo thập phân.",
                    ("Đọc, viết, so sánh được số tự nhiên có nhiều chữ số.",),
                ),
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 2: Ôn tập các phép tính với số tự nhiên",
                    9,
                    11,
                    2,
                    "Ôn tập cộng, trừ, nhân, chia số tự nhiên và tính giá trị biểu thức.",
                    ("Thực hiện được bốn phép tính với số tự nhiên và giải toán có lời văn.",),
                ),
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 3: Ôn tập phân số",
                    12,
                    14,
                    2,
                    "Ôn tập khái niệm phân số, phân số bằng nhau, rút gọn và quy đồng mẫu số.",
                    ("Rút gọn, quy đồng mẫu số và so sánh được hai phân số.",),
                ),
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 4: Phân số thập phân",
                    15,
                    17,
                    2,
                    "Nhận biết phân số thập phân có mẫu số 10, 100, 1000 và chuyển đổi phân số.",
                    ("Nhận biết và viết được phân số thập phân.",),
                ),
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 5: Ôn tập các phép tính với phân số",
                    18,
                    20,
                    2,
                    "Ôn tập cộng, trừ phân số cùng mẫu số, nhân và chia phân số.",
                    ("Thực hiện được phép cộng, trừ cùng mẫu, nhân, chia phân số.",),
                ),
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 6: Cộng, trừ hai phân số khác mẫu số",
                    21,
                    24,
                    3,
                    (
                        "Quy đồng mẫu số và thực hiện cộng, trừ hai phân số khác mẫu số "
                        "trong tính toán và giải toán có lời văn."
                    ),
                    (
                        "Thực hiện được cộng, trừ hai phân số khác mẫu số.",
                        "Vận dụng cộng, trừ hai phân số khác mẫu số vào bài toán thực tế.",
                    ),
                ),
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 7: Hỗn số",
                    25,
                    27,
                    2,
                    (
                        "Nhận biết cấu tạo hỗn số gồm phần nguyên và phần phân số; chuyển hỗn số "
                        "thành phân số."
                    ),
                    ("Đọc, viết được hỗn số và chuyển đổi giữa hỗn số với phân số.",),
                ),
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 8: Ôn tập hình học và đo lường",
                    28,
                    30,
                    2,
                    (
                        "Ôn tập đơn vị đo độ dài, khối lượng, diện tích và chu vi, diện tích hình "
                        "phẳng."
                    ),
                    (
                        (
                            "Vận dụng đổi đơn vị đo và tính chu vi, diện tích hình chữ nhật, hình "
                            "vuông."
                        ),
                    ),
                ),
                (
                    "Chủ đề 1: Ôn tập và bổ sung",
                    "Bài 9: Luyện tập chung",
                    31,
                    31,
                    1,
                    (
                        "Luyện tập tổng hợp về phân số, hỗn số, cộng trừ hai phân số khác mẫu số "
                        "và đo lường."
                    ),
                    ("Giải được bài toán tổng hợp Chủ đề 1.",),
                ),
                (
                    "Chủ đề 2: Số thập phân",
                    "Bài 10: Khái niệm số thập phân",
                    32,
                    37,
                    2,
                    (
                        "Nhận biết phần nguyên, phần thập phân, hàng của số thập phân và viết "
                        "phân số thập phân."
                    ),
                    ("Đọc, viết số thập phân và chuyển đổi phân số thập phân sang số thập phân.",),
                ),
                (
                    "Chủ đề 2: Số thập phân",
                    "Bài 11: So sánh các số thập phân",
                    38,
                    41,
                    2,
                    "Quy tắc so sánh hai số thập phân và sắp xếp dãy số thập phân theo thứ tự.",
                    ("So sánh và sắp xếp được các số thập phân.",),
                ),
                (
                    "Chủ đề 2: Số thập phân",
                    "Bài 13: Làm tròn số thập phân",
                    42,
                    45,
                    2,
                    (
                        "Làm tròn số thập phân đến số tự nhiên gần nhất, hàng phần mười, hàng "
                        "phần trăm."
                    ),
                    ("Làm tròn được số thập phân theo yêu cầu.",),
                ),
                (
                    "Chủ đề 3: Một số đơn vị đo diện tích",
                    "Bài 15: Ki-lô-mét vuông. Héc-ta (km2, ha)",
                    48,
                    53,
                    2,
                    (
                        "Nhận biết đơn vị đo diện tích ki-lô-mét vuông (km², km2), héc-ta (ha) "
                        "và quy đổi giữa km2, ha, m2."
                    ),
                    ("Đọc, viết và chuyển đổi được giữa km2, ha và m2.",),
                ),
                (
                    "Chủ đề 3: Một số đơn vị đo diện tích",
                    "Bài 16: Các đơn vị đo diện tích (m2, dm2, cm2, mm2)",
                    54,
                    59,
                    2,
                    (
                        "Hệ thống hóa bảng đơn vị đo diện tích mét vuông (m2) và vận dụng giải "
                        "toán đất đai."
                    ),
                    ("Quy đổi thành thạo các đơn vị đo diện tích.",),
                ),
                (
                    "Chủ đề 4: Các phép tính với số thập phân",
                    "Bài 19: Phép cộng số thập phân",
                    64,
                    67,
                    2,
                    "Đặt tính và tính phép cộng các số thập phân; tính chất giao hoán, kết hợp.",
                    ("Thực hiện đúng phép cộng số thập phân và tính thuận tiện.",),
                ),
                (
                    "Chủ đề 4: Các phép tính với số thập phân",
                    "Bài 20: Phép trừ số thập phân",
                    68,
                    71,
                    2,
                    "Đặt tính và tính phép trừ hai số thập phân; tìm thành phần chưa biết.",
                    ("Thực hiện đúng phép trừ số thập phân.",),
                ),
                (
                    "Chủ đề 4: Các phép tính với số thập phân",
                    "Bài 21: Phép nhân số thập phân",
                    72,
                    77,
                    3,
                    (
                        "Nhân số thập phân với số tự nhiên, với số thập phân và nhân nhẩm với 10, "
                        "100, 0,1."
                    ),
                    ("Thực hiện thành thạo phép nhân số thập phân.",),
                ),
                (
                    "Chủ đề 4: Các phép tính với số thập phân",
                    "Bài 22: Phép chia số thập phân",
                    78,
                    85,
                    3,
                    (
                        "Chia số thập phân cho số tự nhiên, cho số thập phân và chia nhẩm cho 10, "
                        "100, 0,1."
                    ),
                    ("Thực hiện thành thạo phép chia số thập phân và giải toán.",),
                ),
                (
                    "Chủ đề 5: Một số hình phẳng. Chu vi và diện tích",
                    "Bài 25: Hình tam giác. Diện tích hình tam giác",
                    94,
                    97,
                    2,
                    "Nhận biết đáy, đường cao và công thức tính diện tích hình tam giác.",
                    ("Tính được diện tích hình tam giác.",),
                ),
                (
                    "Chủ đề 5: Một số hình phẳng. Chu vi và diện tích",
                    "Bài 26: Hình thang. Diện tích hình thang",
                    98,
                    103,
                    2,
                    "Nhận biết hai đáy, chiều cao và công thức tính diện tích hình thang.",
                    ("Tính được diện tích hình thang trong bài toán thực tế.",),
                ),
                (
                    "Chủ đề 5: Một số hình phẳng. Chu vi và diện tích",
                    "Bài 27: Đường tròn. Chu vi và diện tích hình tròn",
                    104,
                    111,
                    3,
                    "Thiết lập và vận dụng công thức tính chu vi, diện tích hình tròn.",
                    ("Tính được chu vi và diện tích hình tròn.",),
                ),
                (
                    "Chủ đề 6: Ôn tập học kỳ I",
                    "Bài 31: Ôn tập học kỳ I số thập phân và các phép tính",
                    114,
                    119,
                    2,
                    "Hệ thống hóa học kỳ I (học kì I): phân số, số thập phân và bốn phép tính.",
                    ("Vận dụng kiến thức số học học kỳ I giải toán.",),
                ),
                (
                    "Chủ đề 6: Ôn tập học kỳ I",
                    "Bài 32: Ôn tập học kỳ I đo diện tích và hình phẳng",
                    120,
                    125,
                    2,
                    (
                        "Ôn tập học kỳ I về đơn vị đo diện tích km2, ha, m2 và diện tích hình tam "
                        "giác, hình thang, hình tròn."
                    ),
                    ("Thành thạo quy đổi đơn vị đo và tính diện tích hình phẳng.",),
                ),
            ],
        ),
        (
            "kntt-toan-5-t2",
            "Toán",
            "5",
            "Tập hai",
            128,
            [
                (
                    "Chủ đề 7: Tỉ số và các bài toán liên quan",
                    "Bài 36: Tỉ số. Tỉ số phần trăm",
                    4,
                    9,
                    3,
                    "Nhận biết tỉ số của hai số, tỉ số phần trăm và cách viết kí hiệu phần trăm.",
                    ("Viết và tính được tỉ số, tỉ số phần trăm của hai số.",),
                ),
                (
                    "Chủ đề 7: Tỉ số và các bài toán liên quan",
                    "Bài 37: Tỉ lệ bản đồ và ứng dụng",
                    10,
                    13,
                    2,
                    "Hiểu ý nghĩa tỉ lệ bản đồ và tìm độ dài thật, độ dài thu nhỏ.",
                    ("Vận dụng được tỉ lệ bản đồ giải bài toán thực tế.",),
                ),
                (
                    "Chủ đề 7: Tỉ số và các bài toán liên quan",
                    "Bài 40: Tìm tỉ số phần trăm của hai số",
                    14,
                    19,
                    2,
                    "Giải bài toán tìm tỉ số phần trăm của hai số trong thống kê và mua bán.",
                    ("Tính đúng tỉ số phần trăm của hai số.",),
                ),
                (
                    "Chủ đề 7: Tỉ số và các bài toán liên quan",
                    "Bài 41: Tìm giá trị phần trăm của một số",
                    20,
                    25,
                    2,
                    "Tính giá trị phần trăm của một số và bài toán lãi suất, giảm giá.",
                    ("Giải được bài toán tìm giá trị phần trăm của một số.",),
                ),
                (
                    "Chủ đề 8: Thể tích. Đơn vị đo thể tích",
                    "Bài 45: Thể tích của một hình",
                    26,
                    29,
                    2,
                    "Nhận biết biểu tượng thể tích của một hình qua xếp ghép hình khối.",
                    ("So sánh được thể tích hai hình đơn giản.",),
                ),
                (
                    "Chủ đề 8: Thể tích. Đơn vị đo thể tích",
                    "Bài 46: Xăng-ti-mét khối. Đề-xi-mét khối (cm3, dm3)",
                    30,
                    33,
                    2,
                    (
                        "Nhận biết đơn vị đo thể tích cm³ (cm3), dm³ (dm3) và quy đổi 1 dm3 = "
                        "1000 cm3."
                    ),
                    ("Đọc, viết và quy đổi được cm3, dm3.",),
                ),
                (
                    "Chủ đề 8: Thể tích. Đơn vị đo thể tích",
                    "Bài 47: Mét khối (m3)",
                    34,
                    37,
                    2,
                    "Nhận biết đơn vị mét khối m³ (m3) và mối liên hệ giữa m3, dm3, cm3.",
                    ("Chuyển đổi được giữa các đơn vị đo thể tích cm3, dm3, m3.",),
                ),
                (
                    "Chủ đề 9: Diện tích và thể tích của một số hình khối",
                    "Bài 49: Diện tích xung quanh và diện tích toàn phần của hình hộp chữ nhật",
                    38,
                    43,
                    2,
                    (
                        "Thiết lập công thức tính diện tích xung quanh và diện tích toàn phần "
                        "hình hộp chữ nhật."
                    ),
                    ("Tính được diện tích xung quanh, toàn phần hình hộp chữ nhật.",),
                ),
                (
                    "Chủ đề 9: Diện tích và thể tích của một số hình khối",
                    "Bài 50: Diện tích xung quanh và diện tích toàn phần của hình lập phương",
                    44,
                    47,
                    2,
                    "Tính diện tích xung quanh và diện tích toàn phần hình lập phương.",
                    ("Tính được diện tích xung quanh, toàn phần hình lập phương.",),
                ),
                (
                    "Chủ đề 9: Diện tích và thể tích của một số hình khối",
                    "Bài 52: Thể tích của hình hộp chữ nhật",
                    48,
                    51,
                    2,
                    (
                        "Thiết lập công thức $V = a \\cdot b \\cdot c$ tính thể tích hình hộp chữ "
                        "nhật."
                    ),
                    ("Tính được thể tích hình hộp chữ nhật theo cm3, dm3, m3.",),
                ),
                (
                    "Chủ đề 9: Diện tích và thể tích của một số hình khối",
                    "Bài 53: Thể tích của hình lập phương",
                    52,
                    55,
                    2,
                    "Thiết lập công thức $V = a \\cdot a \\cdot a$ tính thể tích hình lập phương.",
                    ("Tính được thể tích hình lập phương trong bài toán bể nước, thùng hàng.",),
                ),
                (
                    "Chủ đề 10: Số đo thời gian, vận tốc. Các bài toán chuyển động đều",
                    "Bài 58: Nhân, chia số đo thời gian với một số",
                    64,
                    70,
                    3,
                    (
                        "Thực hiện phép cộng, trừ, nhân, chia số đo thời gian với một số và đổi "
                        "giờ, phút, giây."
                    ),
                    ("Tính đúng phép nhân, chia số đo thời gian với một số tự nhiên.",),
                ),
                (
                    "Chủ đề 10: Số đo thời gian, vận tốc. Các bài toán chuyển động đều",
                    "Bài 59: Vận tốc của một chuyển động đều",
                    71,
                    76,
                    3,
                    "Nhận biết khái niệm vận tốc, đơn vị km/h, m/s và công thức $v = s : t$.",
                    ("Tính được vận tốc và đổi đơn vị km/h, m/s.",),
                ),
                (
                    "Chủ đề 10: Số đo thời gian, vận tốc. Các bài toán chuyển động đều",
                    "Bài 60: Quãng đường, thời gian của một chuyển động đều",
                    77,
                    87,
                    4,
                    (
                        "Vận dụng $s = v \\cdot t$, $t = s : v$ giải bài toán chuyển động cùng "
                        "chiều, ngược chiều."
                    ),
                    ("Tính được quãng đường, thời gian và bài toán hai động tử.",),
                ),
                (
                    "Chủ đề 11: Một số yếu tố thống kê và xác suất",
                    "Bài 63: Thu thập, phân loại, sắp xếp các số liệu",
                    90,
                    93,
                    2,
                    "Thu thập, phân loại và lập bảng số liệu thống kê từ tình huống thực tiễn.",
                    ("Thu thập, phân loại và đọc bảng số liệu thống kê.",),
                ),
                (
                    "Chủ đề 11: Một số yếu tố thống kê và xác suất",
                    "Bài 64: Biểu đồ hình quạt tròn",
                    94,
                    97,
                    2,
                    "Đọc, mô tả và phân tích số liệu tỉ lệ phần trăm trên biểu đồ hình quạt tròn.",
                    ("Đọc và phân tích được số liệu thống kê từ biểu đồ hình quạt tròn.",),
                ),
                (
                    "Chủ đề 11: Một số yếu tố thống kê và xác suất",
                    "Bài 65: Tỉ số của số lần lặp lại một sự kiện so với tổng số lần thực hiện",
                    98,
                    103,
                    2,
                    "Kiểm đếm và mô tả xác suất thực nghiệm qua tỉ số lần lặp lại của một sự kiện.",
                    ("Mô tả được xác suất thực nghiệm qua tỉ số lần xuất hiện của một sự kiện.",),
                ),
                (
                    "Chủ đề 12: Ôn tập cuối năm",
                    "Bài 68: Ôn tập cuối năm Toán 5",
                    106,
                    125,
                    5,
                    (
                        "Ôn tập cuối năm toàn bộ phân số, số thập phân, tỉ số phần trăm, đo "
                        "diện tích, thể tích, chuyển động đều, thống kê và xác suất."
                    ),
                    ("Hệ thống hóa và vận dụng tổng hợp kiến thức Toán 5 giải bài toán thực tế.",),
                ),
            ],
        ),
        (
            "kntt-toan-6-t1",
            "Toán",
            "6",
            "Tập một",
            112,
            [
                (
                    "Chương I: Tập hợp các số tự nhiên",
                    "Bài 1: Tập hợp",
                    5,
                    8,
                    2,
                    (
                        "Giới thiệu khái niệm tập hợp, phần tử thuộc tập hợp và hai cách mô "
                        "tả tập hợp."
                    ),
                    (
                        (
                            "Sử dụng được kí hiệu thuộc, không thuộc và cách liệt kê, chỉ ra "
                            "tính chất đặc trưng."
                        ),
                        "Viết được tập hợp các số tự nhiên $\\mathbb{N}$, $\\mathbb{N}^*$.",
                    ),
                ),
                (
                    "Chương I: Tập hợp các số tự nhiên",
                    "Bài 6: Lũy thừa với số mũ tự nhiên",
                    22,
                    24,
                    2,
                    (
                        "Định nghĩa lũy thừa bậc n của a và quy tắc nhân, chia hai lũy thừa "
                        "cùng cơ số."
                    ),
                    (
                        "Thực hiện được phép tính lũy thừa với số mũ tự nhiên.",
                        "Vận dụng thứ tự thực hiện các phép tính trong biểu thức có lũy thừa.",
                    ),
                ),
                (
                    "Chương II: Tính chia hết trong tập hợp các số tự nhiên",
                    "Bài 11: Ước chung, ước chung lớn nhất và bội chung nhỏ nhất",
                    44,
                    55,
                    4,
                    (
                        "Phân tích số ra thừa số nguyên tố để tìm ƯCLN, BCNN và ứng dụng rút "
                        "gọn, quy đồng phân số."
                    ),
                    (
                        "Tìm được ƯCLN và BCNN của hai hoặc ba số tự nhiên.",
                        "Vận dụng ƯCLN, BCNN giải bài toán chia đều, chu kì thực tế.",
                    ),
                ),
                (
                    "Chương III: Số nguyên",
                    "Bài 14: Phép cộng, phép trừ, phép nhân và phép chia hết các số nguyên",
                    62,
                    74,
                    5,
                    (
                        "Mở rộng tập số nguyên $\\mathbb{Z}$, quy tắc dấu ngoặc và bốn phép "
                        "toán trên số nguyên."
                    ),
                    (
                        "Thực hiện thành thạo các phép tính cộng, trừ, nhân, chia hết số nguyên.",
                        "Vận dụng quy tắc dấu ngoặc để tính hợp lí.",
                    ),
                ),
                (
                    "Chương IV: Một số hình phẳng trong thực tiễn",
                    "Bài 20: Chu vi và diện tích của một số tứ giác đã học",
                    90,
                    95,
                    3,
                    (
                        "Tổng hợp công thức chu vi, diện tích hình chữ nhật, hình vuông, hình "
                        "bình hành, hình thoi, hình thang cân."
                    ),
                    (
                        "Tính được chu vi và diện tích các tứ giác đặc biệt trong thực tiễn.",
                        "Nhận biết trục đối xứng và tâm đối xứng của hình phẳng.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-6-t2",
            "Toán",
            "6",
            "Tập hai",
            112,
            [
                (
                    "Chương VI: Phân số",
                    "Bài 25: Phép cộng, phép trừ, phép nhân và phép chia phân số",
                    15,
                    25,
                    4,
                    (
                        "Mở rộng phân số có tử và mẫu nguyên, hỗn số dương và hai bài toán cơ "
                        "bản về phân số."
                    ),
                    (
                        "Thực hiện được bốn phép toán với phân số và hỗn số.",
                        "Giải được bài toán tìm giá trị phân số của một số cho trước và ngược lại.",
                    ),
                ),
                (
                    "Chương VII: Số thập phân",
                    "Bài 31: Một số bài toán về tỉ số và tỉ số phần trăm",
                    38,
                    42,
                    3,
                    "Tính toán với số thập phân âm, làm tròn số và ứng dụng tỉ số phần trăm.",
                    (
                        "Thực hiện được các phép tính với số thập phân và làm tròn theo hàng.",
                        "Giải được bài toán thực tế về chiết khấu, lãi suất, tỉ lệ bản đồ.",
                    ),
                ),
                (
                    "Chương VIII: Những hình hình học cơ bản",
                    "Bài 35: Trung điểm của đoạn thẳng và góc",
                    54,
                    66,
                    4,
                    "Khảo sát điểm, đường thẳng, tia, đoạn thẳng, trung điểm và số đo góc.",
                    (
                        "Xác định được trung điểm của đoạn thẳng và tính độ dài đoạn thẳng.",
                        "Đo và phân loại được góc nhọn, vuông, tù, bẹt.",
                    ),
                ),
                (
                    "Chương IX: Dữ liệu và xác suất thực nghiệm",
                    "Bài 42: Kết quả có thể và sự kiện trong trò chơi, thí nghiệm",
                    88,
                    96,
                    3,
                    "Đọc biểu đồ cột kép và tính xác suất thực nghiệm qua nhiều lần thử.",
                    (
                        "Đọc, vẽ được bảng thống kê và biểu đồ cột kép.",
                        "Tính được xác suất thực nghiệm của một sự kiện đơn giản.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-7-t1",
            "Toán",
            "7",
            "Tập một",
            108,
            [
                (
                    "Chương I: Số hữu tỉ",
                    "Bài 3: Lũy thừa với số mũ tự nhiên của một số hữu tỉ",
                    16,
                    21,
                    3,
                    (
                        "Thực hiện các phép toán trong tập số hữu tỉ $\\mathbb{Q}$ và quy tắc "
                        "chuyển vế."
                    ),
                    (
                        (
                            "Thực hiện thành thạo phép tính lũy thừa và thứ tự phép tính trên "
                            "$\\mathbb{Q}$."
                        ),
                        "Vận dụng quy tắc chuyển vế tìm số hữu tỉ chưa biết.",
                    ),
                ),
                (
                    "Chương II: Số thực",
                    "Bài 6: Số vô tỉ, căn bậc hai số học và tập hợp số thực",
                    29,
                    37,
                    4,
                    (
                        "Giới thiệu số thập phân vô hạn không tuần hoàn, căn bậc hai số học "
                        "và trục số thực $\\mathbb{R}$."
                    ),
                    (
                        (
                            "Tính được căn bậc hai số học và làm tròn số thực với độ chính "
                            "xác cho trước."
                        ),
                        "Nhận biết giá trị tuyệt đối của một số thực.",
                    ),
                ),
                (
                    "Chương III: Góc và đường thẳng song song",
                    "Bài 9: Hai đường thẳng song song và dấu hiệu nhận biết",
                    46,
                    54,
                    4,
                    (
                        "Vận dụng góc đối đỉnh, góc so le trong, đồng vị và tiên đề Euclid "
                        "chứng minh song song."
                    ),
                    (
                        "Nhận biết và chứng minh được hai đường thẳng song song.",
                        "Vận dụng tính chất hai đường thẳng song song để tính số đo góc.",
                    ),
                ),
                (
                    "Chương IV: Tam giác bằng nhau",
                    "Bài 13: Ba trường hợp bằng nhau của tam giác",
                    63,
                    75,
                    5,
                    (
                        "Chứng minh hai tam giác bằng nhau theo các trường hợp c-c-c, c-g-c, "
                        "g-c-g và tam giác cân."
                    ),
                    (
                        (
                            "Chứng minh được hai tam giác bằng nhau và suy ra cạnh, góc tương "
                            "ứng bằng nhau."
                        ),
                        "Vận dụng tính chất tam giác cân và đường trung trực của đoạn thẳng.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-7-t2",
            "Toán",
            "7",
            "Tập hai",
            108,
            [
                (
                    "Chương VI: Tỉ lệ thức và đại lượng tỉ lệ",
                    "Bài 21: Tính chất của dãy tỉ số bằng nhau",
                    8,
                    17,
                    4,
                    (
                        "Vận dụng tính chất tỉ lệ thức, dãy tỉ số bằng nhau giải bài toán đại "
                        "lượng tỉ lệ thuận, tỉ lệ nghịch."
                    ),
                    (
                        "Áp dụng được tính chất dãy tỉ số bằng nhau tìm các đại lượng chưa biết.",
                        "Giải được bài toán thực tế về đại lượng tỉ lệ thuận và tỉ lệ nghịch.",
                    ),
                ),
                (
                    "Chương VII: Biểu thức đại số và đa thức một biến",
                    "Bài 26: Phép cộng, phép trừ, phép nhân và phép chia đa thức một biến",
                    31,
                    43,
                    5,
                    (
                        "Thu gọn, sắp xếp đa thức một biến, tìm nghiệm và thực hiện bốn phép "
                        "toán trên đa thức."
                    ),
                    (
                        (
                            "Xác định được bậc, hệ số cao nhất, hệ số tự do và nghiệm của đa "
                            "thức một biến."
                        ),
                        "Thực hiện thành thạo cộng, trừ, nhân và chia đa thức một biến.",
                    ),
                ),
                (
                    "Chương IX: Quan hệ giữa các yếu tố trong một tam giác",
                    (
                        "Bài 34: Sự đồng quy của ba đường trung tuyến, phân giác, trung trực, "
                        "đường cao"
                    ),
                    72,
                    83,
                    4,
                    (
                        "Khảo sát bất đẳng thức tam giác và tính chất trọng tâm, trực tâm, "
                        "tâm đường tròn nội tiếp, ngoại tiếp."
                    ),
                    (
                        "Vận dụng được quan hệ giữa góc và cạnh đối diện, bất đẳng thức tam giác.",
                        "Xác định được tính chất đồng quy của bốn đường đặc biệt trong tam giác.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-8-t1",
            "Toán",
            "8",
            "Tập một",
            112,
            [
                (
                    "Chương I: Đa thức",
                    "Bài 3: Phép cộng, phép trừ, phép nhân và phép chia đa thức nhiều biến",
                    15,
                    24,
                    4,
                    (
                        "Nhận biết đơn thức, đa thức nhiều biến và thực hiện các phép toán "
                        "thu gọn đa thức."
                    ),
                    (
                        (
                            "Thực hiện thành thạo cộng, trừ, nhân đa thức và chia đa thức cho "
                            "đơn thức."
                        ),
                        "Tính được giá trị đa thức nhiều biến tại giá trị cho trước.",
                    ),
                ),
                (
                    "Chương II: Hằng đẳng thức đáng nhớ và ứng dụng",
                    "Bài 9: Phân tích đa thức thành nhân tử",
                    42,
                    46,
                    4,
                    (
                        "Vận dụng bảy hằng đẳng thức đáng nhớ, đặt nhân tử chung và nhóm hạng "
                        "tử phân tích đa thức."
                    ),
                    (
                        "Vận dụng được bảy hằng đẳng thức đáng nhớ vào khai triển và rút gọn.",
                        "Phân tích được đa thức thành nhân tử bằng nhiều phương pháp phối hợp.",
                    ),
                ),
                (
                    "Chương III: Tứ giác",
                    "Bài 12: Hình bình hành, hình chữ nhật, hình thoi và hình vuông",
                    58,
                    72,
                    5,
                    "Hệ thống hóa tính chất và dấu hiệu nhận biết các loại tứ giác đặc biệt.",
                    (
                        (
                            "Chứng minh được một tứ giác là hình bình hành, hình chữ nhật, "
                            "hình thoi hoặc hình vuông."
                        ),
                        "Vận dụng tính chất tứ giác giải bài toán chứng minh hình học.",
                    ),
                ),
                (
                    "Chương IV: Định lí Thalès",
                    "Bài 15: Định lí Thalès trong tam giác và đường trung bình",
                    78,
                    87,
                    4,
                    (
                        "Thiết lập định lí Thalès thuận, đảo, tính chất đường trung bình và "
                        "tính chất đường phân giác."
                    ),
                    (
                        "Tính được độ dài đoạn thẳng và chứng minh song song bằng định lí Thalès.",
                        "Vận dụng tính chất đường phân giác của tam giác.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-8-t2",
            "Toán",
            "8",
            "Tập hai",
            116,
            [
                (
                    "Chương VI: Phân thức đại số",
                    "Bài 23: Phép cộng, phép trừ, phép nhân và phép chia phân thức đại số",
                    15,
                    24,
                    4,
                    (
                        "Tìm điều kiện xác định, rút gọn và thực hiện bốn phép tính trên phân "
                        "thức đại số."
                    ),
                    (
                        "Rút gọn và quy đồng mẫu thức của các phân thức đại số.",
                        "Tính đúng giá trị và chứng minh đẳng thức chứa phân thức.",
                    ),
                ),
                (
                    "Chương VII: Phương trình bậc nhất và hàm số bậc nhất",
                    "Bài 28: Hàm số bậc nhất và đồ thị của hàm số bậc nhất",
                    44,
                    54,
                    4,
                    "Giải phương trình bậc nhất một ẩn, vẽ đồ thị $y = ax + b$ và xét hệ số góc.",
                    (
                        "Giải được phương trình bậc nhất một ẩn và bài toán lập phương trình.",
                        (
                            "Vẽ được đồ thị hàm số $y = ax + b$ và nhận biết hai đường thẳng "
                            "song song, cắt nhau."
                        ),
                    ),
                ),
                (
                    "Chương IX: Tam giác đồng dạng",
                    "Bài 34: Ba trường hợp đồng dạng của hai tam giác và định lí Pythagore",
                    80,
                    95,
                    5,
                    (
                        "Chứng minh hai tam giác đồng dạng (c-c-c, c-g-c, g-g) và ứng dụng "
                        "định lí Pythagore."
                    ),
                    (
                        "Chứng minh được hai tam giác đồng dạng và suy ra tỉ lệ cạnh.",
                        "Vận dụng định lí Pythagore tính độ dài trong tam giác vuông.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-9-t1",
            "Toán",
            "9",
            "Tập một",
            112,
            [
                (
                    "Chương I: Phương trình và hệ hai phương trình bậc nhất hai ẩn",
                    "Bài 2: Giải hệ hai phương trình bậc nhất hai ẩn",
                    11,
                    18,
                    3,
                    (
                        "Giải hệ hai phương trình bậc nhất hai ẩn bằng phương pháp thế, cộng "
                        "đại số và giải bài toán thực tế."
                    ),
                    (
                        "Giải thành thạo hệ hai phương trình bậc nhất hai ẩn.",
                        "Lập và giải được hệ phương trình từ bài toán thực tiễn.",
                    ),
                ),
                (
                    "Chương II: Phương trình và bất phương trình bậc nhất một ẩn",
                    "Bài 6: Bất phương trình bậc nhất một ẩn",
                    36,
                    41,
                    3,
                    (
                        "Giải phương trình quy về bậc nhất, phương trình chứa ẩn ở mẫu và bất "
                        "phương trình bậc nhất."
                    ),
                    (
                        "Giải được phương trình tích, phương trình chứa ẩn ở mẫu.",
                        "Giải được bất phương trình bậc nhất một ẩn và biểu diễn tập nghiệm.",
                    ),
                ),
                (
                    "Chương III: Căn bậc hai và căn bậc ba",
                    "Bài 9: Biến đổi đơn giản và rút gọn biểu thức chứa căn thức bậc hai",
                    56,
                    64,
                    4,
                    (
                        "Vận dụng hằng đẳng thức $\\sqrt{A^2} = |A|$, trục căn thức ở mẫu để "
                        "rút gọn biểu thức."
                    ),
                    (
                        "Tìm được điều kiện xác định và rút gọn biểu thức chứa căn bậc hai.",
                        "Tính được căn bậc ba của biểu thức số đơn giản.",
                    ),
                ),
                (
                    "Chương IV: Hệ thức lượng trong tam giác vuông",
                    "Bài 11: Tỉ số lượng giác của góc nhọn",
                    69,
                    75,
                    3,
                    (
                        "Định nghĩa $\\sin, \\cos, \\tan, \\cot$ của góc nhọn và vận dụng "
                        "giải tam giác vuông."
                    ),
                    (
                        "Tính được tỉ số lượng giác và hệ thức cạnh - góc trong tam giác vuông.",
                        "Ứng dụng giải bài toán đo chiều cao, khoảng cách thực tế.",
                    ),
                ),
                (
                    "Chương V: Đường tròn",
                    "Bài 15: Độ dài của cung tròn, diện tích hình quạt tròn và vị trí tương đối",
                    92,
                    102,
                    4,
                    (
                        "Khảo sát tiếp tuyến đường tròn, góc ở tâm, góc nội tiếp và độ dài "
                        "cung, diện tích hình quạt."
                    ),
                    (
                        "Nhận biết và chứng minh được tính chất hai tiếp tuyến cắt nhau.",
                        "Tính được độ dài cung tròn và diện tích hình quạt tròn.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-9-t2",
            "Toán",
            "9",
            "Tập hai",
            116,
            [
                (
                    "Chương VI: Hàm số $y = ax^2$ ($a \\neq 0$). Phương trình bậc hai một ẩn",
                    "Bài 19: Phương trình bậc hai một ẩn và định lí Viète",
                    11,
                    24,
                    5,
                    (
                        "Giải phương trình bậc hai bằng công thức nghiệm và vận dụng định lí "
                        "Viète tìm tổng, tích hai nghiệm."
                    ),
                    (
                        "Giải thành thạo phương trình bậc hai một ẩn bằng biệt thức $\\Delta$.",
                        "Vận dụng định lí Viète nhẩm nghiệm và tìm điều kiện tham số.",
                    ),
                ),
                (
                    "Chương VII: Tần số và tần số tương đối",
                    "Bài 23: Bảng tần số tương đối và biểu đồ tần số tương đối ghép nhóm",
                    38,
                    50,
                    3,
                    (
                        "Lập bảng tần số, tần số tương đối và vẽ biểu đồ cột, hình quạt biểu "
                        "diễn dữ liệu."
                    ),
                    (
                        "Thiết lập và đọc được bảng tần số, tần số tương đối ghép nhóm.",
                        "Nhận xét xu hướng phân bố dữ liệu từ biểu đồ.",
                    ),
                ),
                (
                    "Chương VIII. Xác suất của biến cố trong một số mô hình xác suất đơn giản",
                    "Bài 25: Phép thử ngẫu nhiên và không gian mẫu",
                    53,
                    58,
                    3,
                    (
                        "Nhận biết phép thử ngẫu nhiên, kết quả có thể và mô tả không gian "
                        "mẫu $\\Omega$ trong các mô hình xác suất đơn giản."
                    ),
                    (
                        "Xác định được phép thử ngẫu nhiên và liệt kê không gian mẫu $\\Omega$.",
                        (
                            "Mô tả được kết quả có thể của phép thử gieo xúc xắc, tung đồng xu, "
                            "chọn ngẫu nhiên."
                        ),
                    ),
                ),
                (
                    "Chương VIII. Xác suất của biến cố trong một số mô hình xác suất đơn giản",
                    "Bài 26: Xác suất của biến cố liên quan tới phép thử",
                    59,
                    66,
                    3,
                    (
                        "Nhận biết biến cố đồng khả năng và tính xác suất của biến cố theo "
                        "công thức $P(A) = \\frac{n(A)}{n(\\Omega)}$."
                    ),
                    (
                        (
                            "Đếm được số kết quả thuận lợi và tính được xác suất của biến cố "
                            "trong mô hình đồng khả năng."
                        ),
                        "Giải thích được ý nghĩa xác suất của biến cố trong bài toán thực tế.",
                    ),
                ),
                (
                    "Chương VIII. Xác suất của biến cố trong một số mô hình xác suất đơn giản",
                    "Luyện tập chung: Kiểm nghiệm & luyện tập xác suất Chương VIII",
                    67,
                    72,
                    2,
                    (
                        "Kiểm nghiệm và luyện tập ước lượng xác suất của biến cố qua tần số "
                        "tương đối thực nghiệm và mô hình đồng khả năng."
                    ),
                    (
                        (
                            "Thực hiện kiểm nghiệm và luyện tập giải bài toán xác suất trong "
                            "các mô hình đơn giản."
                        ),
                        (
                            "Liên hệ được giữa xác suất thực nghiệm qua kiểm nghiệm và xác "
                            "suất lí thuyết."
                        ),
                    ),
                ),
                (
                    "Chương IX: Đường tròn ngoại tiếp và đường tròn nội tiếp",
                    "Bài 29: Tứ giác nội tiếp",
                    75,
                    82,
                    4,
                    (
                        "Chứng minh tứ giác nội tiếp đường tròn và vận dụng tính chất tổng "
                        "hai góc đối bằng $180^\\circ$."
                    ),
                    (
                        "Nhận biết và chứng minh được tứ giác nội tiếp đường tròn.",
                        (
                            "Vận dụng tính chất tứ giác nội tiếp vào bài toán chứng minh góc "
                            "và độ dài."
                        ),
                    ),
                ),
                (
                    "Chương X: Một số hình khối trong thực tiễn",
                    "Bài 31: Hình trụ, hình nón và hình cầu",
                    90,
                    104,
                    4,
                    (
                        "Tính diện tích xung quanh và thể tích hình trụ, hình nón, diện tích "
                        "mặt cầu và thể tích hình cầu."
                    ),
                    (
                        "Tính được diện tích xung quanh và thể tích hình trụ, hình nón, hình cầu.",
                        "Giải được bài toán thực tế về vật thể tròn xoay.",
                    ),
                ),
            ],
        ),
        # ==================== TOÁN 10 (MẪU ĐIỂN HÌNH ĐẦY ĐỦ) ====================
        (
            "kntt-toan-10-t1",
            "Toán",
            "10",
            "Tập một",
            106,
            [
                (
                    "Chương I: Mệnh đề và tập hợp",
                    "Bài 1: Mệnh đề",
                    5,
                    11,
                    3,
                    (
                        "Khái niệm mệnh đề, mệnh đề chứa biến, mệnh đề phủ định, mệnh đề kéo "
                        "theo, mệnh đề đảo, mệnh đề tương đương và kí hiệu lượng từ "
                        "$\\forall, \\exists$."
                    ),
                    (
                        (
                            "Thiết lập và phát biểu được các mệnh đề toán học, bao gồm mệnh "
                            "đề phủ định, đảo, tương đương, điều kiện cần và đủ."
                        ),
                        (
                            "Xác định được tính đúng sai của một mệnh đề trong những trường "
                            "hợp đơn giản."
                        ),
                    ),
                ),
                (
                    "Chương I: Mệnh đề và tập hợp",
                    "Bài 2: Tập hợp và các phép toán trên tập hợp",
                    12,
                    19,
                    4,
                    (
                        "Cách mô tả tập hợp, tập hợp con, hai tập hợp bằng nhau, các tập hợp "
                        "số và các phép toán giao, hợp, hiệu, phần bù trên tập hợp, biểu diễn "
                        "bằng biểu đồ Ven."
                    ),
                    (
                        (
                            "Nhận biết được các khái niệm cơ bản về tập hợp (tập con, hai tập "
                            "hợp bằng nhau, tập rỗng) và biết sử dụng các kí hiệu $\\subset, "
                            "\\supset, \\emptyset$."
                        ),
                        (
                            "Thực hiện được các phép toán trên tập hợp (hợp, giao, hiệu của "
                            "hai tập hợp, phần bù của một tập con) và biểu diễn bằng biểu đồ "
                            "Ven."
                        ),
                        "Giải quyết được một số vấn đề thực tiễn gắn với phép toán trên tập hợp.",
                    ),
                ),
                (
                    "Chương I: Mệnh đề và tập hợp",
                    "Bài tập cuối chương I",
                    20,
                    21,
                    1,
                    (
                        "Hệ thống hóa kiến thức và luyện tập tổng hợp về mệnh đề, lượng từ và "
                        "các phép toán tập hợp trên trục số."
                    ),
                    (
                        (
                            "Vận dụng tổng hợp kiến thức mệnh đề và tập hợp giải bài tập trắc "
                            "nghiệm, tự luận."
                        ),
                    ),
                ),
                (
                    "Chương II: Bất phương trình và hệ bất phương trình bậc nhất hai ẩn",
                    "Bài 3: Bất phương trình bậc nhất hai ẩn",
                    22,
                    25,
                    2,
                    (
                        "Định nghĩa bất phương trình bậc nhất hai ẩn $ax + by \\le c$ và cách "
                        "biểu diễn miền nghiệm trên mặt phẳng tọa độ $Oxy$."
                    ),
                    (
                        "Nhận biết được bất phương trình bậc nhất hai ẩn.",
                        (
                            "Biểu diễn được miền nghiệm của bất phương trình bậc nhất hai ẩn "
                            "trên mặt phẳng tọa độ."
                        ),
                    ),
                ),
                (
                    "Chương II: Bất phương trình và hệ bất phương trình bậc nhất hai ẩn",
                    "Bài 4: Hệ bất phương trình bậc nhất hai ẩn",
                    26,
                    30,
                    3,
                    (
                        "Xác định miền nghiệm đa giác của hệ bất phương trình bậc nhất hai ẩn "
                        "và tìm cực trị biểu thức tuyến tính $F(x; y) = ax + by$ trong bài "
                        "toán tối ưu."
                    ),
                    (
                        (
                            "Biểu diễn được miền nghiệm của hệ bất phương trình bậc nhất hai "
                            "ẩn trên mặt phẳng tọa độ."
                        ),
                        (
                            "Vận dụng được kiến thức về hệ bất phương trình bậc nhất hai ẩn "
                            "giải quyết bài toán quy hoạch tuyến tính thực tiễn."
                        ),
                    ),
                ),
                (
                    "Chương II: Bất phương trình và hệ bất phương trình bậc nhất hai ẩn",
                    "Bài tập cuối chương II",
                    31,
                    32,
                    1,
                    (
                        "Ôn tập biểu diễn miền nghiệm và mô hình hóa bài toán sản xuất, dinh "
                        "dưỡng bằng hệ bất phương trình bậc nhất hai ẩn."
                    ),
                    (
                        (
                            "Củng cố kĩ năng xác định tọa độ đỉnh miền đa giác nghiệm và kết "
                            "luận giá trị lớn nhất, nhỏ nhất."
                        ),
                    ),
                ),
                (
                    "Chương III: Hệ thức lượng trong tam giác",
                    "Bài 5: Giá trị lượng giác của một góc từ 0° đến 180°",
                    33,
                    37,
                    2,
                    (
                        "Mở rộng định nghĩa $\\sin \\alpha, \\cos \\alpha, \\tan \\alpha, "
                        "\\cot \\alpha$ trên nửa đường tròn đơn vị và quan hệ giữa hai góc bù "
                        "nhau, phụ nhau."
                    ),
                    (
                        (
                            "Tính được giá trị lượng giác của một góc từ $0^\\circ$ đến "
                            "$180^\\circ$, kể cả góc đặc biệt."
                        ),
                        "Vận dụng được hệ thức lượng giác cơ bản cho góc tù.",
                    ),
                ),
                (
                    "Chương III: Hệ thức lượng trong tam giác",
                    "Bài 6: Hệ thức lượng trong tam giác",
                    38,
                    43,
                    4,
                    (
                        "Thiết lập định lí côsin, định lí sin, các công thức tính diện tích "
                        "tam giác và công thức Heron để giải tam giác và đo đạc thực địa."
                    ),
                    (
                        "Giải thích và vận dụng được định lí côsin, định lí sin trong tam giác.",
                        (
                            "Tính được diện tích tam giác bằng nhiều công thức và giải quyết "
                            "bài toán đo đạc thực tiễn."
                        ),
                    ),
                ),
                (
                    "Chương III: Hệ thức lượng trong tam giác",
                    "Bài tập cuối chương III",
                    44,
                    45,
                    1,
                    (
                        "Luyện tập tổng hợp giải tam giác và bài toán ứng dụng định lí sin, "
                        "côsin trong hàng hải, trắc địa."
                    ),
                    (
                        (
                            "Lựa chọn linh hoạt định lí côsin, định lí sin và công thức diện "
                            "tích phù hợp dữ kiện."
                        ),
                    ),
                ),
                (
                    "Chương IV: Vectơ",
                    "Bài 7: Các khái niệm mở đầu",
                    46,
                    49,
                    2,
                    (
                        "Khái niệm vectơ, độ dài vectơ, hai vectơ cùng phương, cùng hướng, "
                        "bằng nhau và vectơ-không."
                    ),
                    (
                        "Nhận biết được khái niệm vectơ, vectơ bằng nhau và vectơ-không.",
                        "Biểu thị được một số đại lượng vật lí như lực, vận tốc bằng vectơ.",
                    ),
                ),
                (
                    "Chương IV: Vectơ",
                    "Bài 8: Tổng và hiệu của hai vectơ",
                    50,
                    54,
                    3,
                    (
                        "Quy tắc ba điểm, quy tắc hình bình hành, tính chất phép cộng, hiệu "
                        "hai vectơ và ứng dụng phân tích lực."
                    ),
                    (
                        (
                            "Thực hiện được phép cộng, phép trừ hai vectơ và vận dụng quy tắc "
                            "trung điểm, trọng tâm."
                        ),
                    ),
                ),
                (
                    "Chương IV: Vectơ",
                    "Bài 9: Tích của một vectơ với một số",
                    55,
                    58,
                    2,
                    (
                        "Định nghĩa tích một số thực với vectơ, tính chất phân phối và điều "
                        "kiện hai vectơ cùng phương, ba điểm thẳng hàng."
                    ),
                    (
                        (
                            "Thực hiện được phép nhân vectơ với một số và chứng minh ba điểm "
                            "thẳng hàng."
                        ),
                    ),
                ),
                (
                    "Chương IV: Vectơ",
                    "Bài 10: Vectơ trong mặt phẳng tọa độ",
                    59,
                    64,
                    3,
                    (
                        "Biểu diễn tọa độ của điểm và vectơ trong hệ trục $Oxy$; công thức "
                        "tọa độ tổng, hiệu, trung điểm và trọng tâm."
                    ),
                    (
                        (
                            "Tìm được tọa độ của vectơ, độ dài vectơ và khoảng cách giữa hai "
                            "điểm trong $Oxy$."
                        ),
                    ),
                ),
                (
                    "Chương IV: Vectơ",
                    "Bài 11: Tích vô hướng của hai vectơ",
                    65,
                    69,
                    3,
                    (
                        "Định nghĩa góc giữa hai vectơ, tích vô hướng và biểu thức tọa độ "
                        "tích vô hướng; ứng dụng chứng minh vuông góc và tính công cơ học."
                    ),
                    (
                        "Tính được tích vô hướng hai vectơ theo định nghĩa và theo tọa độ.",
                        "Vận dụng tích vô hướng tính góc giữa hai vectơ và giải bài toán vật lí.",
                    ),
                ),
                (
                    "Chương IV: Vectơ",
                    "Bài tập cuối chương IV",
                    70,
                    71,
                    1,
                    (
                        "Hệ thống hóa khái niệm vectơ, tổng hiệu, tích với một số, tọa độ và tích "
                        "vô hướng trong mặt phẳng."
                    ),
                    ("Vận dụng tổng hợp các phép toán vectơ giải bài toán hình học và vật lí.",),
                ),
                (
                    "Chương V: Các số đặc trưng của mẫu số liệu không ghép nhóm",
                    "Bài 12: Số gần đúng và sai số",
                    72,
                    75,
                    2,
                    (
                        "Khái niệm số gần đúng, sai số tuyệt đối, sai số tương đối và quy tắc "
                        "làm tròn số gần đúng."
                    ),
                    (
                        (
                            "Xác định được số gần đúng với độ chính xác cho trước và ước "
                            "lượng sai số tương đối."
                        ),
                    ),
                ),
                (
                    "Chương V: Các số đặc trưng của mẫu số liệu không ghép nhóm",
                    "Bài 13: Các số đặc trưng đo xu thế trung tâm",
                    76,
                    81,
                    3,
                    (
                        "Tính và giải thích ý nghĩa của số trung bình cộng, trung vị, tứ phân "
                        "vị và mốt của mẫu số liệu."
                    ),
                    (
                        (
                            "Tính được số trung bình, trung vị, tứ phân vị và mốt của mẫu số "
                            "liệu không ghép nhóm."
                        ),
                        "Lựa chọn được số đặc trưng đại diện phù hợp khi có giá trị bất thường.",
                    ),
                ),
                (
                    "Chương V: Các số đặc trưng của mẫu số liệu không ghép nhóm",
                    "Bài 14: Các số đặc trưng đo độ phân tán",
                    82,
                    87,
                    3,
                    (
                        "Tính khoảng biến thiên, khoảng tứ phân vị, phương sai, độ lệch chuẩn "
                        "và phát hiện giá trị ngoại lệ."
                    ),
                    (
                        (
                            "Tính được khoảng biến thiên, khoảng tứ phân vị, phương sai và độ "
                            "lệch chuẩn."
                        ),
                        "So sánh mức độ ổn định của hai mẫu số liệu qua độ lệch chuẩn.",
                    ),
                ),
                (
                    "Chương V: Các số đặc trưng của mẫu số liệu không ghép nhóm",
                    "Bài tập cuối chương V",
                    88,
                    89,
                    1,
                    "Ôn tập tổng hợp số gần đúng, xu thế trung tâm và độ phân tán của mẫu số liệu.",
                    ("Tính và phân tích được các số đặc trưng của mẫu số liệu thực tiễn.",),
                ),
            ],
        ),
        (
            "kntt-toan-10-t2",
            "Toán",
            "10",
            "Tập hai",
            104,
            [
                (
                    "Chương VI: Hàm số, đồ thị và ứng dụng",
                    "Bài 15: Hàm số",
                    4,
                    10,
                    3,
                    "Khái niệm hàm số, tập xác định, tập giá trị, sự biến thiên và đồ thị hàm số.",
                    (
                        (
                            "Tìm được tập xác định và nhận biết khoảng đồng biến, nghịch biến của "
                            "hàm số."
                        ),
                    ),
                ),
                (
                    "Chương VI: Hàm số, đồ thị và ứng dụng",
                    "Bài 16: Hàm số bậc hai",
                    11,
                    17,
                    4,
                    (
                        "Khảo sát đỉnh, trục đối xứng, bảng biến thiên và đồ thị parabol $y = "
                        "ax^2 + bx + c$."
                    ),
                    (
                        "Thiết lập được bảng giá trị và vẽ đồ thị hàm số bậc hai.",
                        (
                            "Vận dụng hàm số bậc hai giải bài toán quỹ đạo chuyển động, tối ưu "
                            "diện tích."
                        ),
                    ),
                ),
                (
                    "Chương VI: Hàm số, đồ thị và ứng dụng",
                    "Bài 17: Dấu của tam thức bậc hai",
                    18,
                    24,
                    3,
                    "Định lí về dấu tam thức bậc hai và giải bất phương trình bậc hai một ẩn.",
                    ("Xét được dấu tam thức bậc hai và giải bất phương trình bậc hai một ẩn.",),
                ),
                (
                    "Chương VI: Hàm số, đồ thị và ứng dụng",
                    "Bài 18: Phương trình quy về phương trình bậc hai",
                    25,
                    27,
                    2,
                    (
                        "Giải phương trình chứa căn thức bậc hai dạng $\\sqrt{ax^2+bx+c} = "
                        "\\sqrt{dx^2+ex+f}$ và $\\sqrt{ax^2+bx+c} = dx+e$."
                    ),
                    (
                        (
                            "Giải được phương trình chứa căn quy về phương trình bậc hai và kiểm "
                            "tra nghiệm."
                        ),
                    ),
                ),
                (
                    "Chương VII: Phương pháp tọa độ trong mặt phẳng",
                    "Bài 19: Phương trình đường thẳng",
                    30,
                    37,
                    3,
                    (
                        "Vectơ chỉ phương, vectơ pháp tuyến, phương trình tham số và phương trình "
                        "tổng quát đường thẳng."
                    ),
                    ("Lập được phương trình tham số và tổng quát của đường thẳng trong $Oxy$.",),
                ),
                (
                    "Chương VII: Phương pháp tọa độ trong mặt phẳng",
                    "Bài 20: Vị trí tương đối giữa hai đường thẳng. Góc và khoảng cách",
                    38,
                    42,
                    2,
                    (
                        "Xét vị trí tương đối hai đường thẳng, tính góc giữa hai đường thẳng và "
                        "khoảng cách từ điểm đến đường thẳng."
                    ),
                    ("Xác định được vị trí tương đối, góc và khoảng cách trong mặt phẳng tọa độ.",),
                ),
                (
                    "Chương VII: Phương pháp tọa độ trong mặt phẳng",
                    "Bài 21: Đường tròn trong mặt phẳng tọa độ",
                    43,
                    47,
                    2,
                    (
                        "Phương trình đường tròn tâm $I(a; b)$ bán kính $R$ và phương trình tiếp "
                        "tuyến của đường tròn."
                    ),
                    ("Viết được phương trình đường tròn và phương trình tiếp tuyến tại một điểm.",),
                ),
                (
                    "Chương VII: Phương pháp tọa độ trong mặt phẳng",
                    "Bài 22: Ba đường conic",
                    48,
                    56,
                    3,
                    (
                        "Nhận biết và viết phương trình chính tắc của elip, hypebol, parabol cùng "
                        "ứng dụng thực tiễn."
                    ),
                    ("Nhận biết và xác định được các yếu tố của elip, hypebol, parabol.",),
                ),
                (
                    "Chương VIII: Đại số tổ hợp",
                    "Bài 23: Quy tắc đếm",
                    60,
                    65,
                    3,
                    "Quy tắc cộng, quy tắc nhân và sơ đồ hình cây trong các bài toán đếm.",
                    ("Vận dụng được quy tắc cộng, quy tắc nhân giải bài toán đếm.",),
                ),
                (
                    "Chương VIII: Đại số tổ hợp",
                    "Bài 24: Hoán vị, chỉnh hợp và tổ hợp",
                    66,
                    71,
                    3,
                    "Công thức tính số hoán vị $P_n$, chỉnh hợp $A_n^k$ và tổ hợp $C_n^k$.",
                    ("Tính được số cách chọn bằng hoán vị, chỉnh hợp, tổ hợp.",),
                ),
                (
                    "Chương VIII: Đại số tổ hợp",
                    "Bài 25: Nhị thức Newton",
                    72,
                    75,
                    2,
                    (
                        "Công thức khai triển nhị thức Newton $(a+b)^n$ với $n = 4, 5$ và ứng "
                        "dụng tam giác Pascal."
                    ),
                    ("Khai triển được nhị thức Newton với số mũ $n = 4, 5$ và tìm hệ số hạng tử.",),
                ),
                (
                    "Chương IX: Tính xác suất theo định nghĩa cổ điển",
                    "Bài 26: Biến cố và định nghĩa cổ điển của xác suất",
                    78,
                    82,
                    2,
                    "Xác định không gian mẫu, biến cố đối và định nghĩa cổ điển của xác suất.",
                    ("Xác định được không gian mẫu, biến cố và biến cố đối.",),
                ),
                (
                    "Chương IX: Tính xác suất theo định nghĩa cổ điển",
                    "Bài 27: Thực hành tính xác suất theo định nghĩa cổ điển",
                    83,
                    88,
                    2,
                    "Tính xác suất theo định nghĩa cổ điển kết hợp tổ hợp và quy tắc biến cố đối.",
                    ("Tính được xác suất của biến cố trong phép thử đồng khả năng.",),
                ),
            ],
        ),
        (
            "kntt-toan-10-cd",
            "Toán",
            "10",
            "Chuyên đề học tập",
            64,
            [
                (
                    "Chuyên đề 1: Hệ phương trình bậc nhất ba ẩn",
                    "Bài 1: Hệ phương trình bậc nhất ba ẩn và ứng dụng",
                    5,
                    22,
                    5,
                    (
                        "Giải hệ phương trình bậc nhất ba ẩn bằng phương pháp Gauss và vận "
                        "dụng giải bài toán vật lí, hóa học, kinh tế."
                    ),
                    (
                        "Giải được hệ phương trình bậc nhất ba ẩn bằng phương pháp khử ẩn dần.",
                        "Vận dụng hệ bậc nhất ba ẩn mô hình hóa bài toán thực tế.",
                    ),
                ),
                (
                    "Chuyên đề 2: Phương pháp quy nạp toán học. Nhị thức Newton",
                    "Bài 3: Phương pháp quy nạp toán học và nhị thức Newton tổng quát",
                    23,
                    40,
                    5,
                    (
                        "Chứng minh đẳng thức, bất đẳng thức bằng quy nạp toán học và khai "
                        "triển nhị thức Newton tổng quát."
                    ),
                    (
                        "Chứng minh được mệnh đề toán học bằng phương pháp quy nạp.",
                        "Tìm được hệ số hạng tử trong khai triển $(a+b)^n$.",
                    ),
                ),
                (
                    "Chuyên đề 3: Ba đường conic và ứng dụng",
                    "Bài 5: Elip, hypebol, parabol và tính chất quang học",
                    41,
                    60,
                    5,
                    (
                        "Nghiên cứu tâm sai, đường chuẩn, bán kính qua tiêu và ứng dụng thiết "
                        "kế gương parabol, quỹ đạo hành tinh."
                    ),
                    ("Xác định được tâm sai, tiêu điểm, đường chuẩn của ba đường conic.",),
                ),
            ],
        ),
        # ==================== TOÁN 11 ====================
        (
            "kntt-toan-11-t1",
            "Toán",
            "11",
            "Tập một",
            120,
            [
                (
                    "Chương I: Hàm số lượng giác và phương trình lượng giác",
                    "Bài 1: Giá trị lượng giác của góc lượng giác và công thức lượng giác",
                    5,
                    21,
                    5,
                    (
                        "Góc lượng giác theo radian, đường tròn lượng giác và các công thức "
                        "cộng, nhân đôi, biến đổi tích thành tổng."
                    ),
                    (
                        "Đổi được giữa độ và radian; tính giá trị lượng giác của góc bất kì.",
                        (
                            "Vận dụng thành thạo công thức cộng, công thức nhân đôi và biến "
                            "đổi tổng thành tích."
                        ),
                    ),
                ),
                (
                    "Chương I: Hàm số lượng giác và phương trình lượng giác",
                    "Bài 4: Phương trình lượng giác cơ bản",
                    31,
                    40,
                    4,
                    (
                        "Giải các phương trình $\\sin x = m, \\cos x = m, \\tan x = m, \\cot "
                        "x = m$ và phương trình đưa về dạng cơ bản."
                    ),
                    (
                        (
                            "Giải được phương trình lượng giác cơ bản và biểu diễn nghiệm "
                            "theo radian hoặc độ."
                        ),
                        "Vận dụng phương trình lượng giác giải bài toán dao động điều hòa.",
                    ),
                ),
                (
                    "Chương II: Dãy số. Cấp số cộng và cấp số nhân",
                    "Bài 6: Cấp số cộng và cấp số nhân",
                    48,
                    59,
                    5,
                    (
                        "Xác định số hạng tổng quát $u_n$ và tổng $n$ số hạng đầu $S_n$ của "
                        "cấp số cộng, cấp số nhân."
                    ),
                    (
                        (
                            "Tính được số hạng tổng quát và tổng $n$ số hạng đầu của cấp số "
                            "cộng, cấp số nhân."
                        ),
                        "Giải được bài toán thực tiễn về tăng trưởng, lãi kép.",
                    ),
                ),
                (
                    "Chương III: Các số đặc trưng đo xu thế trung tâm của mẫu số liệu ghép nhóm",
                    "Bài 9: Các số đặc trưng đo xu thế trung tâm mẫu ghép nhóm",
                    64,
                    75,
                    4,
                    (
                        "Tính số trung bình, trung vị, tứ phân vị và mốt cho bảng phân bố tần "
                        "số ghép nhóm."
                    ),
                    (
                        (
                            "Tính và giải thích được số trung bình, trung vị, tứ phân vị và "
                            "mốt mẫu ghép nhóm."
                        ),
                    ),
                ),
                (
                    "Chương IV: Quan hệ song song trong không gian",
                    "Bài 11: Đường thẳng và mặt phẳng song song trong không gian",
                    78,
                    97,
                    6,
                    (
                        "Xác định giao tuyến hai mặt phẳng, chứng minh đường thẳng song song "
                        "mặt phẳng và hai mặt phẳng song song."
                    ),
                    (
                        (
                            "Xác định được giao tuyến, giao điểm và chứng minh quan hệ song "
                            "song trong không gian."
                        ),
                        "Vận dụng định lí Thalès trong không gian và phép chiếu song song.",
                    ),
                ),
                (
                    "Chương V: Giới hạn. Hàm số liên tục",
                    "Bài 16: Giới hạn của dãy số, giới hạn của hàm số và hàm số liên tục",
                    104,
                    118,
                    5,
                    (
                        "Tính giới hạn dãy số, giới hạn hàm số tại một điểm và tại vô cực; "
                        "xét tính liên tục trên khoảng."
                    ),
                    (
                        "Tính được giới hạn hữu hạn, vô cực của dãy số và hàm số.",
                        (
                            "Xét được tính liên tục của hàm số và vận dụng chứng minh phương "
                            "trình có nghiệm."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-11-t2",
            "Toán",
            "11",
            "Tập hai",
            116,
            [
                (
                    "Chương VI: Hàm số mũ và hàm số lôgarit",
                    "Bài 19: Lôgarit, hàm số mũ, hàm số lôgarit và phương trình",
                    11,
                    31,
                    6,
                    (
                        "Quy tắc tính lôgarit, tính chất đồ thị hàm mũ, hàm lôgarit và giải "
                        "phương trình, bất phương trình mũ, lôgarit."
                    ),
                    (
                        (
                            "Vận dụng được tính chất lũy thừa số mũ thực và lôgarit để biến "
                            "đổi biểu thức."
                        ),
                        "Giải được phương trình, bất phương trình mũ và lôgarit cơ bản.",
                    ),
                ),
                (
                    "Chương VII: Quan hệ vuông góc trong không gian",
                    "Bài 23: Đường thẳng vuông góc mặt phẳng, góc và khoảng cách",
                    36,
                    64,
                    7,
                    (
                        "Chứng minh đường thẳng vuông góc mặt phẳng, hai mặt phẳng vuông góc; "
                        "tính góc nhị diện, khoảng cách và thể tích khối chóp, lăng trụ."
                    ),
                    (
                        (
                            "Chứng minh được đường thẳng vuông góc mặt phẳng và hai mặt phẳng "
                            "vuông góc."
                        ),
                        (
                            "Tính được góc giữa đường thẳng với mặt phẳng, góc nhị diện, "
                            "khoảng cách và thể tích."
                        ),
                    ),
                ),
                (
                    "Chương VIII: Các quy tắc tính xác suất",
                    "Bài 29: Công thức cộng và công thức nhân xác suất",
                    68,
                    81,
                    4,
                    (
                        "Xác định biến cố hợp, giao, xung khắc, độc lập và vận dụng quy tắc "
                        "cộng, quy tắc nhân xác suất."
                    ),
                    ("Tính được xác suất biến cố hợp và biến cố giao của các biến cố độc lập.",),
                ),
                (
                    "Chương IX: Đạo hàm",
                    "Bài 32: Các quy tắc tính đạo hàm và đạo hàm cấp hai",
                    86,
                    103,
                    5,
                    (
                        "Tính đạo hàm hàm sơ cấp, hàm hợp; viết phương trình tiếp tuyến và ý "
                        "nghĩa cơ học của đạo hàm cấp hai."
                    ),
                    (
                        "Tính thành thạo đạo hàm hàm đa thức, lượng giác, mũ, lôgarit và hàm hợp.",
                        "Viết được phương trình tiếp tuyến của đồ thị hàm số tại một điểm.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-11-cd",
            "Toán",
            "11",
            "Chuyên đề học tập",
            68,
            [
                (
                    "Chuyên đề 1: Phép biến hình trong mặt phẳng",
                    "Bài 1: Phép dời hình và phép đồng dạng trong mặt phẳng",
                    5,
                    24,
                    5,
                    (
                        "Khảo sát phép tịnh tiến, đối xứng trục, đối xứng tâm, phép quay và "
                        "phép vị tự."
                    ),
                    (
                        (
                            "Xác định được ảnh của điểm, đường thẳng, đường tròn qua các phép "
                            "biến hình."
                        ),
                    ),
                ),
                (
                    "Chuyên đề 2: Làm quen với một vài khái niệm của Lí thuyết đồ thị",
                    "Bài 3: Đường đi Euler, đường đi Hamilton và bài toán đường đi ngắn nhất",
                    25,
                    46,
                    5,
                    (
                        "Nhận biết đỉnh, cạnh, bậc đỉnh của đồ thị và vận dụng thuật toán tìm "
                        "đường đi ngắn nhất."
                    ),
                    ("Vận dụng được đồ thị mô hình hóa bài toán mạng giao thông và lịch trình.",),
                ),
            ],
        ),
        # ==================== TOÁN 12 ====================
        (
            "kntt-toan-12-t1",
            "Toán",
            "12",
            "Tập một",
            108,
            [
                (
                    "Chương I: Ứng dụng đạo hàm để khảo sát và vẽ đồ thị hàm số",
                    "Bài 1: Tính đơn điệu và cực trị của hàm số",
                    5,
                    14,
                    4,
                    (
                        "Xét dấu đạo hàm cấp một xác định khoảng đồng biến, nghịch biến và "
                        "điểm cực đại, cực tiểu của hàm số."
                    ),
                    (
                        (
                            "Nhận biết được tính đồng biến, nghịch biến và điểm cực trị qua "
                            "bảng biến thiên và đồ thị."
                        ),
                        "Tìm được khoảng đơn điệu và cực trị của hàm đa thức, phân thức.",
                    ),
                ),
                (
                    "Chương I: Ứng dụng đạo hàm để khảo sát và vẽ đồ thị hàm số",
                    "Bài 2: Giá trị lớn nhất, giá trị nhỏ nhất và đường tiệm cận của đồ thị hàm số",
                    15,
                    25,
                    4,
                    (
                        "Tìm GTLN, GTNN trên đoạn; xác định tiệm cận đứng, tiệm cận ngang và "
                        "tiệm cận xiên của đồ thị."
                    ),
                    (
                        (
                            "Tìm được GTLN, GTNN của hàm số trên đoạn và giải bài toán tối ưu "
                            "thực tiễn."
                        ),
                        "Xác định được đường tiệm cận đứng, ngang, xiên của đồ thị hàm phân thức.",
                    ),
                ),
                (
                    "Chương I: Ứng dụng đạo hàm để khảo sát và vẽ đồ thị hàm số",
                    "Bài 4: Khảo sát sự biến thiên và vẽ đồ thị của hàm số",
                    26,
                    38,
                    4,
                    (
                        "Thực hiện quy trình khảo sát và vẽ đồ thị hàm bậc ba, phân thức bậc "
                        "nhất trên bậc nhất và bậc hai trên bậc nhất."
                    ),
                    (
                        (
                            "Khảo sát và vẽ thành thạo đồ thị ba dạng hàm số cơ bản và biện "
                            "luận tương giao."
                        ),
                    ),
                ),
                (
                    "Chương II: Vectơ và hệ trục tọa độ trong không gian",
                    "Bài 6: Vectơ và hệ trục tọa độ trong không gian Oxyz",
                    44,
                    66,
                    5,
                    (
                        "Thực hiện phép toán vectơ trong không gian, tọa độ điểm, biểu thức "
                        "tọa độ tích vô hướng và tính góc, độ dài."
                    ),
                    (
                        (
                            "Tính được tọa độ tổng, hiệu, tích vô hướng và góc giữa hai vectơ "
                            "trong $Oxyz$."
                        ),
                        "Vận dụng hệ tọa độ $Oxyz$ mô tả vị trí vật thể trong không gian thực tế.",
                    ),
                ),
                (
                    "Chương III: Các số đặc trưng đo mức độ phân tán của mẫu số liệu ghép nhóm",
                    (
                        "Bài 9: Khoảng biến thiên, khoảng tứ phân vị, phương sai và độ lệch "
                        "chuẩn mẫu ghép nhóm"
                    ),
                    74,
                    86,
                    4,
                    (
                        "Tính và đánh giá độ phân tán của mẫu số liệu thống kê ghép nhóm trong "
                        "phân tích dữ liệu."
                    ),
                    (
                        (
                            "Tính được khoảng biến thiên, khoảng tứ phân vị, phương sai và độ "
                            "lệch chuẩn mẫu số liệu thống kê ghép nhóm."
                        ),
                        "Giải thích được ý nghĩa thống kê của các số đặc trưng đo độ phân tán.",
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-12-t2",
            "Toán",
            "12",
            "Tập hai",
            104,
            [
                (
                    "Chương IV: Nguyên hàm và tích phân",
                    "Bài 11: Nguyên hàm và tích phân",
                    5,
                    23,
                    6,
                    (
                        "Tìm nguyên hàm các hàm sơ cấp, tính tích phân theo công thức "
                        "Newton–Leibniz và ứng dụng tính diện tích, thể tích khối tròn xoay."
                    ),
                    (
                        "Tìm được nguyên hàm và tính được tích phân của các hàm số cơ bản.",
                        (
                            "Tính được diện tích hình phẳng và thể tích vật thể tròn xoay "
                            "bằng tích phân."
                        ),
                    ),
                ),
                (
                    "Chương V: Phương pháp tọa độ trong không gian",
                    "Bài 14: Phương trình mặt phẳng, đường thẳng và mặt cầu trong không gian",
                    30,
                    60,
                    7,
                    (
                        "Lập phương trình mặt phẳng, phương trình tham số và chính tắc đường "
                        "thẳng, phương trình mặt cầu; tính góc và khoảng cách."
                    ),
                    (
                        "Viết được phương trình mặt phẳng, đường thẳng và mặt cầu trong $Oxyz$.",
                        (
                            "Tính được khoảng cách từ điểm đến mặt phẳng và góc giữa đường "
                            "thẳng, mặt phẳng."
                        ),
                    ),
                ),
                (
                    "Chương VI: Xác suất có điều kiện",
                    "Bài 18: Xác suất có điều kiện",
                    66,
                    73,
                    2,
                    (
                        "Định nghĩa xác suất có điều kiện $P(A|B)$, công thức nhân xác suất "
                        "và sử dụng sơ đồ hình cây."
                    ),
                    (
                        (
                            "Hiểu và tính được xác suất có điều kiện bằng định nghĩa và sơ "
                            "đồ hình cây."
                        ),
                        "Vận dụng quy tắc nhân xác suất tính xác suất giao của hai biến cố.",
                    ),
                ),
                (
                    "Chương VI: Xác suất có điều kiện",
                    "Bài 19: Công thức xác suất toàn phần và công thức Bayes",
                    74,
                    82,
                    3,
                    (
                        "Thiết lập công thức xác suất toàn phần "
                        "$P(B) = P(A)P(B|A) + P(\\bar{A})P(B|\\bar{A})$ và công thức Bayes."
                    ),
                    (
                        "Vận dụng được công thức xác suất toàn phần và công thức Bayes.",
                        (
                            "Giải quyết bài toán ứng dụng công thức Bayes trong y học, kiểm "
                            "định chất lượng."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-toan-12-cd",
            "Toán",
            "12",
            "Chuyên đề học tập",
            68,
            [
                (
                    (
                        "Chuyên đề 1: Biến ngẫu nhiên rời rạc. Các số đặc trưng của biến ngẫu "
                        "nhiên rời rạc"
                    ),
                    "Bài 1: Biến ngẫu nhiên rời rạc, phân bố nhị thức và kì vọng",
                    5,
                    24,
                    5,
                    (
                        "Lập bảng phân bố xác suất, tính kì vọng, phương sai, độ lệch chuẩn "
                        "và vận dụng phân bố Bernoulli, nhị thức."
                    ),
                    (
                        (
                            "Tính được kì vọng và phương sai của biến ngẫu nhiên rời rạc và "
                            "phân bố nhị thức."
                        ),
                    ),
                ),
                (
                    (
                        "Chuyên đề 2: Ứng dụng toán học để giải quyết một số vấn đề liên quan "
                        "đến tài chính"
                    ),
                    "Bài 3: Tiền tệ, lãi suất, tín dụng và lập kế hoạch tài chính",
                    25,
                    48,
                    5,
                    (
                        "Tính lãi đơn, lãi kép, trả góp và đánh giá rủi ro cơ bản trong bài "
                        "toán tài chính cá nhân."
                    ),
                    ("Vận dụng được công thức lãi kép và cấp số nhân vào tính toán tài chính.",),
                ),
            ],
        ),
        # ==================== TIẾNG VIỆT 1–5 ====================
        (
            "kntt-tieng-viet-1-t1",
            "Tiếng Việt",
            "1",
            "Tập một",
            172,
            [
                (
                    "Phần 1: Làm quen âm chữ và dấu thanh",
                    "Bài 1–10: Các chữ cái và thanh điệu cơ bản",
                    10,
                    33,
                    6,
                    "Nhận diện âm, chữ cái đầu tiên, ghép vần đơn giản và tập viết nét cơ bản.",
                    (
                        "Đọc đúng âm, tiếng và từ ngữ chứa các chữ cái, dấu thanh đã học.",
                        "Viết đúng cỡ chữ và khoảng cách chữ cái trên vở ô li.",
                    ),
                ),
                (
                    "Phần 2: Vần có âm cuối và đọc hiểu câu ngắn",
                    "Bài 45–60: Ghép vần và đọc đoạn văn ngắn",
                    102,
                    135,
                    6,
                    "Luyện đọc trơn câu và đoạn văn ngắn về gia đình, trường học, thiên nhiên.",
                    ("Đọc trơn được đoạn văn ngắn và trả lời câu hỏi về chi tiết trực tiếp.",),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-1-t2",
            "Tiếng Việt",
            "1",
            "Tập hai",
            176,
            [
                (
                    "Chủ điểm: Tôi và các bạn",
                    "Bài 1: Tôi là học sinh lớp 1",
                    10,
                    21,
                    4,
                    (
                        "Đọc hiểu câu chuyện về ngày đầu đi học, rèn kĩ năng nói lời chào hỏi "
                        "và viết câu kể ngắn."
                    ),
                    (
                        "Đọc hiểu nội dung văn bản ngắn và nhận biết nhân vật chính.",
                        "Viết được câu kể đơn giản đúng chính tả cơ bản.",
                    ),
                ),
                (
                    "Chủ điểm: Thiên nhiên kì thú",
                    "Bài 5: Mùa xuân và những khu vườn nhỏ",
                    96,
                    112,
                    4,
                    (
                        "Đọc văn bản miêu tả cây cối, con vật và mở rộng vốn từ chỉ màu sắc, "
                        "hoạt động."
                    ),
                    ("Tìm được từ ngữ chỉ đặc điểm thiên nhiên trong đoạn đọc.",),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-2-t1",
            "Tiếng Việt",
            "2",
            "Tập một",
            152,
            [
                (
                    "Chủ điểm: Em lớn lên từng ngày",
                    "Bài 1: Đọc hiểu câu chuyện và đặt câu giới thiệu",
                    10,
                    24,
                    4,
                    (
                        "Rèn đọc trơn văn bản kể chuyện, phân biệt từ chỉ sự vật, hoạt động "
                        "và viết đoạn ngắn 3–4 câu."
                    ),
                    (
                        "Đọc trơn và hiểu trình tự sự việc chính trong văn bản kể chuyện.",
                        "Đặt được câu theo mẫu Ai là gì, Ai làm gì và dùng đúng dấu chấm, dấu hỏi.",
                    ),
                ),
                (
                    "Chủ điểm: Mái ấm gia đình",
                    "Bài 15: Đọc hiểu thơ và viết đoạn văn kể việc nhà",
                    64,
                    79,
                    4,
                    (
                        "Cảm nhận tình cảm gia đình qua thơ thiếu nhi và viết đoạn văn ngắn "
                        "kể việc giúp người thân."
                    ),
                    ("Nêu được cảm nhận về chi tiết thể hiện tình yêu thương gia đình.",),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-2-t2",
            "Tiếng Việt",
            "2",
            "Tập hai",
            152,
            [
                (
                    "Chủ điểm: Vẻ đẹp quanh em",
                    "Bài 1: Đọc hiểu văn bản miêu tả cảnh vật và từ chỉ đặc điểm",
                    10,
                    26,
                    4,
                    (
                        "Đọc hiểu bài văn tả cảnh bốn mùa, sử dụng từ chỉ đặc điểm và dấu "
                        "phẩy liệt kê."
                    ),
                    ("Nhận biết từ chỉ đặc điểm và sử dụng dấu phẩy đúng vị trí trong câu.",),
                ),
                (
                    "Chủ điểm: Giao tiếp và kết nối",
                    "Bài 20: Văn bản thông tin ngắn và viết bưu thiếp, lời nhắn",
                    88,
                    104,
                    4,
                    (
                        "Tiếp cận văn bản thông tin đơn giản, đọc bảng chỉ dẫn và viết lời "
                        "nhắn lịch sự."
                    ),
                    ("Đọc hiểu thông tin chính và viết được đoạn văn ngắn 4–5 câu theo chủ đề.",),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-3-t1",
            "Tiếng Việt",
            "3",
            "Tập một",
            148,
            [
                (
                    "Chủ điểm: Trải nghiệm và khám phá",
                    "Bài 1: Đọc hiểu truyện thiếu nhi và biện pháp so sánh",
                    10,
                    25,
                    4,
                    (
                        "Đọc hiểu văn bản tự sự, nhận biết hình ảnh so sánh và viết đoạn văn "
                        "kể lại trải nghiệm."
                    ),
                    (
                        "Nhận biết được hình ảnh so sánh trong câu văn, câu thơ.",
                        "Viết được đoạn văn kể lại một hoạt động hoặc sự việc đã trải qua.",
                    ),
                ),
                (
                    "Chủ điểm: Cổng trường rộng mở",
                    "Bài 12: Từ có nghĩa giống nhau, trái ngược nhau và viết đoạn tả đồ vật",
                    56,
                    72,
                    4,
                    (
                        "Mở rộng vốn từ theo chủ điểm trường học, luyện đặt câu cảm và viết "
                        "đoạn văn tả đồ dùng học tập."
                    ),
                    (
                        (
                            "Tìm được từ đồng nghĩa, trái nghĩa đơn giản và viết đoạn tả đồ "
                            "vật rõ đặc điểm."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-3-t2",
            "Tiếng Việt",
            "3",
            "Tập hai",
            148,
            [
                (
                    "Chủ điểm: Những sắc màu thiên nhiên",
                    "Bài 1: Đọc hiểu văn bản thông tin và câu khiến",
                    10,
                    26,
                    4,
                    (
                        "Khai thác thông tin từ văn bản khoa học thường thức, phân biệt câu "
                        "kể, câu hỏi, câu khiến, câu cảm."
                    ),
                    (
                        "Nhận biết được mục đích nói của bốn kiểu câu cơ bản.",
                        "Viết được đoạn văn nêu tình cảm, cảm xúc về cảnh đẹp quê hương.",
                    ),
                ),
                (
                    "Chủ điểm: Trái đất của chúng mình",
                    "Bài 22: Đọc hiểu văn bản bảo vệ môi trường và viết thư ngắn",
                    92,
                    108,
                    4,
                    (
                        "Đọc hiểu văn bản về bảo vệ môi trường, rèn luyện cấu trúc một bức "
                        "thư thăm hỏi ngắn."
                    ),
                    ("Trình bày được ý kiến cá nhân và viết được bức thư ngắn đủ bố cục.",),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-4-t1",
            "Tiếng Việt",
            "4",
            "Tập một",
            148,
            [
                (
                    "Chủ điểm: Mỗi người một vẻ",
                    "Bài 1: Danh từ, động từ, tính từ và nhân hóa",
                    10,
                    32,
                    5,
                    (
                        "Phân loại danh từ, động từ, tính từ; nhận biết biện pháp nhân hóa và "
                        "viết bài văn kể lại câu chuyện."
                    ),
                    (
                        "Phân biệt được danh từ, động từ, tính từ trong câu văn.",
                        "Viết được bài văn kể lại câu chuyện đã đọc, đã nghe có bố cục ba phần.",
                    ),
                ),
                (
                    "Chủ điểm: Niềm vui sáng tạo",
                    "Bài 17: Quy tắc viết hoa tên cơ quan, tổ chức và viết báo cáo thảo luận nhóm",
                    74,
                    92,
                    4,
                    (
                        "Nắm quy tắc viết hoa tên riêng, viết đoạn văn nêu ý kiến và lập báo "
                        "cáo thảo luận nhóm."
                    ),
                    ("Viết đúng quy tắc viết hoa và trình bày báo cáo thảo luận rõ ràng.",),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-4-t2",
            "Tiếng Việt",
            "4",
            "Tập hai",
            148,
            [
                (
                    "Chủ điểm: Sống để yêu thương",
                    "Bài 1: Chủ ngữ, vị ngữ, trạng ngữ trong câu",
                    10,
                    32,
                    5,
                    (
                        "Xác định thành phần chính (chủ ngữ, vị ngữ) và thành phần phụ trạng "
                        "ngữ chỉ thời gian, nơi chốn."
                    ),
                    (
                        "Phân tích được chủ ngữ, vị ngữ và trạng ngữ trong câu đơn.",
                        "Viết được bài văn miêu tả cây cối có quan sát sinh động.",
                    ),
                ),
                (
                    "Chủ điểm: Quê hương trong tôi",
                    "Bài 18: Văn bản tả con vật và hướng dẫn thực hiện công việc",
                    78,
                    96,
                    4,
                    (
                        "Viết bài văn miêu tả con vật gần gũi và văn bản hướng dẫn các bước "
                        "làm một sản phẩm thủ công."
                    ),
                    ("Lập dàn ý và viết được bài văn tả con vật mạch lạc, giàu hình ảnh.",),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-5-t1",
            "Tiếng Việt",
            "5",
            "Tập một",
            152,
            [
                (
                    "Chủ điểm: Thế giới tuổi thơ",
                    "Bài 1: Từ đồng nghĩa, từ đa nghĩa và viết bài văn tả phong cảnh",
                    10,
                    34,
                    5,
                    (
                        "Phân biệt từ đồng nghĩa, từ đa nghĩa (nghĩa gốc, nghĩa chuyển) và "
                        "rèn viết bài văn tả phong cảnh."
                    ),
                    (
                        "Phân biệt được nghĩa gốc, nghĩa chuyển của từ đa nghĩa trong ngữ cảnh.",
                        "Viết được bài văn tả phong cảnh có cảm xúc và biện pháp tu từ.",
                    ),
                ),
                (
                    "Chủ điểm: Nghệ thuật muôn màu",
                    "Bài 17: Kết từ, đại từ và viết báo cáo công việc",
                    76,
                    94,
                    4,
                    (
                        "Sử dụng đại từ, kết từ liên kết câu và viết đoạn văn giới thiệu một "
                        "nhân vật văn học."
                    ),
                    ("Nhận biết và dùng đúng đại từ, kết từ để liên kết câu văn.",),
                ),
            ],
        ),
        (
            "kntt-tieng-viet-5-t2",
            "Tiếng Việt",
            "5",
            "Tập hai",
            152,
            [
                (
                    "Chủ điểm: Vẻ đẹp cuộc sống",
                    "Bài 1: Câu đơn, câu ghép và cách nối các vế câu ghép",
                    10,
                    34,
                    5,
                    (
                        "Phân biệt câu đơn, câu ghép; sử dụng cặp kết từ biểu thị quan hệ "
                        "nguyên nhân, điều kiện, tương phản."
                    ),
                    (
                        "Xác định và đặt được câu ghép nối bằng kết từ hoặc dấu phẩy.",
                        (
                            "Viết được bài văn tả người có chi tiết tiêu biểu về ngoại hình, "
                            "tính cách."
                        ),
                    ),
                ),
                (
                    "Chủ điểm: Chung sống hòa bình",
                    "Bài 18: Liên kết câu bằng lặp từ ngữ, thay thế từ ngữ và viết đoạn nêu ý kiến",
                    78,
                    98,
                    4,
                    (
                        "Vận dụng phép lặp, phép thế để liên kết câu trong đoạn và viết đoạn "
                        "văn bày tỏ thái độ trước một hiện tượng."
                    ),
                    ("Nhận biết và vận dụng được phép liên kết câu trong đoạn văn.",),
                ),
            ],
        ),
        # ==================== NGỮ VĂN 6–12 ====================
        (
            "kntt-ngu-van-6-t1",
            "Ngữ văn",
            "6",
            "Tập một",
            132,
            [
                (
                    "Bài 1: Tôi và các bạn",
                    (
                        "Đọc hiểu truyện đồng thoại, từ đơn, từ phức và viết bài văn kể lại "
                        "một trải nghiệm"
                    ),
                    10,
                    35,
                    5,
                    (
                        "Tìm hiểu đặc điểm nhân vật, lời kể ngôi thứ nhất trong truyện đồng "
                        "thoại; phân biệt từ ghép, từ láy."
                    ),
                    (
                        (
                            "Nhận biết được người kể chuyện ngôi thứ nhất, chi tiết tiêu biểu "
                            "trong truyện đồng thoại."
                        ),
                        "Viết được bài văn kể lại một trải nghiệm đáng nhớ của bản thân.",
                    ),
                ),
                (
                    "Bài 2: Gõ cửa trái tim",
                    "Đọc hiểu thơ có yếu tố tự sự, miêu tả và biện pháp ẩn dụ",
                    36,
                    56,
                    4,
                    (
                        "Phân tích hình ảnh, cảm xúc trong thơ thiếu nhi, nhận diện biện pháp "
                        "ẩn dụ và viết đoạn ghi lại cảm xúc về bài thơ."
                    ),
                    (
                        "Nhận biết được biện pháp tu từ ẩn dụ và tác dụng biểu đạt.",
                        (
                            "Viết được đoạn văn ghi lại cảm xúc về một bài thơ có yếu tố tự "
                            "sự, miêu tả."
                        ),
                    ),
                ),
                (
                    "Bài 3: Yêu thương và chia sẻ",
                    "Đọc hiểu truyện ngắn, cụm danh từ, cụm động từ và kể lại trải nghiệm",
                    57,
                    82,
                    5,
                    (
                        "Phân tích tình huống và nhân vật truyện ngắn; mở rộng thành phần "
                        "chính của câu bằng cụm từ."
                    ),
                    (
                        "Phân tích được đặc điểm nhân vật qua hành động, lời nói, suy nghĩ.",
                        "Vận dụng cụm danh từ, cụm động từ để mở rộng câu văn.",
                    ),
                ),
                (
                    "Bài 5: Những nẻo đường xứ sở",
                    "Đọc hiểu kí (du kí) và viết bài văn tả cảnh sinh hoạt",
                    105,
                    128,
                    4,
                    (
                        "Nhận biết đặc trưng thể loại du kí, phép ẩn dụ, hoán dụ và kĩ năng "
                        "viết bài văn tả cảnh sinh hoạt."
                    ),
                    (
                        "Nhận biết được sự kết hợp giữa tự sự và miêu tả trong văn bản du kí.",
                        "Viết được bài văn tả cảnh sinh hoạt giàu chi tiết quan sát.",
                    ),
                ),
            ],
        ),
        (
            "kntt-ngu-van-6-t2",
            "Ngữ văn",
            "6",
            "Tập hai",
            124,
            [
                (
                    "Bài 6: Chuyện kể về những người anh hùng",
                    "Đọc hiểu truyền thuyết và viết bài văn thuyết minh thuật lại một sự kiện",
                    6,
                    30,
                    5,
                    (
                        "Khám phá yếu tố kì ảo, cốt lõi lịch sử trong truyền thuyết dân gian "
                        "và kĩ năng kể lại truyền thuyết."
                    ),
                    (
                        (
                            "Nhận biết được đặc trưng cốt truyện, nhân vật anh hùng và yếu tố "
                            "kì ảo trong truyền thuyết."
                        ),
                        "Viết được bài văn thuyết minh thuật lại một lễ hội hoặc sự kiện.",
                    ),
                ),
                (
                    "Bài 7: Thế giới cổ tích",
                    "Đọc hiểu truyện cổ tích và đóng vai nhân vật kể lại câu chuyện",
                    31,
                    52,
                    4,
                    "Phân tích kiểu nhân vật, motip kì ảo và ước mơ công lí trong truyện cổ tích.",
                    (
                        "Nêu được chủ đề và bài học rút ra từ truyện cổ tích.",
                        "Viết được bài văn đóng vai nhân vật kể lại một truyện cổ tích.",
                    ),
                ),
                (
                    "Bài 8: Khác biệt và gần gũi",
                    "Đọc hiểu văn bản nghị luận xã hội và viết bài văn trình bày ý kiến",
                    53,
                    76,
                    5,
                    (
                        "Nhận diện vấn đề nghị luận, ý kiến, lí lẽ và bằng chứng trong văn "
                        "bản nghị luận ngắn."
                    ),
                    (
                        "Xác định được ý kiến, lí lẽ, bằng chứng trong văn bản nghị luận.",
                        "Viết được bài văn trình bày ý kiến về một hiện tượng đời sống.",
                    ),
                ),
                (
                    "Bài 9: Trái Đất – ngôi nhà chung",
                    "Đọc hiểu văn bản thông tin đa phương thức và viết biên bản",
                    77,
                    102,
                    4,
                    (
                        "Đọc hiểu văn bản thông tin kết hợp nhan đề, sa-pô, hình ảnh, số liệu "
                        "và kĩ năng tóm tắt bằng sơ đồ."
                    ),
                    (
                        (
                            "Nhận biết được tác dụng của phương tiện phi ngôn ngữ trong văn "
                            "bản thông tin."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-ngu-van-7-t1",
            "Ngữ văn",
            "7",
            "Tập một",
            136,
            [
                (
                    "Bài 1: Bầu trời tuổi thơ",
                    "Đọc hiểu truyện hiện đại, mở rộng trạng ngữ và tóm tắt văn bản",
                    10,
                    34,
                    5,
                    (
                        "Phân tích cốt truyện, tính cách nhân vật và thực hành tóm tắt văn "
                        "bản theo yêu cầu độ dài."
                    ),
                    (
                        "Nhận biết được đề tài, chi tiết tiêu biểu và tính cách nhân vật.",
                        "Tóm tắt được văn bản tự sự theo các mức độ dài ngắn khác nhau.",
                    ),
                ),
                (
                    "Bài 2: Khúc nhạc tâm hồn",
                    "Đọc hiểu thơ bốn chữ, năm chữ và biện pháp tu từ nói giảm nói tránh",
                    35,
                    56,
                    4,
                    (
                        "Khảo sát vần, nhịp, hình ảnh trong thơ bốn chữ, năm chữ và viết đoạn "
                        "ghi lại cảm xúc sau khi đọc thơ."
                    ),
                    ("Phân tích được vần, nhịp và cảm xúc chủ đạo trong thơ bốn chữ, năm chữ.",),
                ),
                (
                    "Bài 3: Cội nguồn yêu thương",
                    (
                        "Đọc hiểu truyện ngắn, số từ, phó từ và viết bài văn phân tích đặc "
                        "điểm nhân vật"
                    ),
                    57,
                    82,
                    5,
                    (
                        "Nhận biết vai trò của số từ, phó từ và cấu trúc bài văn phân tích "
                        "nhân vật trong tác phẩm văn học."
                    ),
                    (
                        (
                            "Viết được bài văn phân tích đặc điểm nhân vật dựa trên bằng "
                            "chứng từ tác phẩm."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-ngu-van-7-t2",
            "Ngữ văn",
            "7",
            "Tập hai",
            128,
            [
                (
                    "Bài 6: Bài học cuộc sống",
                    (
                        "Đọc hiểu truyện ngụ ngôn, tục ngữ và viết bài văn nghị luận về một "
                        "vấn đề đời sống"
                    ),
                    6,
                    30,
                    5,
                    (
                        "Giải mã bài học triết lí trong truyện ngụ ngôn, tục ngữ; rèn kĩ năng "
                        "viết bài nghị luận trình bày tán thành/phản đối."
                    ),
                    (
                        (
                            "Nhận biết được đặc điểm hình thức và bài học ứng xử của truyện "
                            "ngụ ngôn, tục ngữ."
                        ),
                        "Viết được bài văn nghị luận về một vấn đề trong đời sống.",
                    ),
                ),
                (
                    "Bài 7: Thế giới viễn tưởng",
                    "Đọc hiểu truyện khoa học viễn tưởng và viết bài văn kể lại sự việc có thật",
                    31,
                    54,
                    4,
                    (
                        "Phân tích không gian, thời gian, cốt truyện giàu trí tưởng tượng "
                        "khoa học và biện pháp liên kết đoạn."
                    ),
                    (
                        (
                            "Nhận biết được đề tài, sự kiện, tình huống trong truyện khoa học "
                            "viễn tưởng."
                        ),
                    ),
                ),
                (
                    "Bài 9: Hòa điệu với tự nhiên",
                    (
                        "Đọc hiểu văn bản thông tin giới thiệu quy tắc, luật lệ và viết bài "
                        "thuyết minh"
                    ),
                    76,
                    102,
                    4,
                    (
                        "Khai thác cấu trúc văn bản thông tin giải thích hiện tượng tự nhiên "
                        "và viết bài thuyết minh quy tắc hoạt động."
                    ),
                    (
                        (
                            "Viết được bài văn thuyết minh về quy tắc hoặc luật lệ trong một "
                            "trò chơi, hoạt động."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-ngu-van-8-t1",
            "Ngữ văn",
            "8",
            "Tập một",
            136,
            [
                (
                    "Bài 1: Câu chuyện của lịch sử",
                    (
                        "Đọc hiểu truyện lịch sử và viết bài văn kể lại một chuyến đi hoặc "
                        "hoạt động xã hội"
                    ),
                    10,
                    34,
                    5,
                    (
                        "Phân tích bối cảnh lịch sử, nhân vật và cốt truyện đa tuyến trong "
                        "truyện lịch sử; nhận biết biệt ngữ xã hội."
                    ),
                    (
                        (
                            "Nhận biết được đặc trưng bối cảnh, cốt truyện và nhân vật của "
                            "truyện lịch sử."
                        ),
                        (
                            "Viết được bài văn kể lại một chuyến đi có kết hợp yếu tố miêu "
                            "tả, biểu cảm."
                        ),
                    ),
                ),
                (
                    "Bài 2: Vẻ đẹp cổ điển",
                    "Đọc hiểu thơ thất ngôn bát cú và tứ tuyệt Đường luật",
                    35,
                    56,
                    4,
                    (
                        "Phân tích bố cục, niêm luật, đối và nghệ thuật tả cảnh ngụ tình "
                        "trong thơ Đường luật; phép đảo ngữ."
                    ),
                    (
                        (
                            "Nhận biết được bố cục, vần, nhịp, phép đối trong thơ thất ngôn "
                            "bát cú và tứ tuyệt."
                        ),
                        "Viết được bài văn phân tích một bài thơ Đường luật.",
                    ),
                ),
                (
                    "Bài 3: Lời sông núi",
                    "Đọc hiểu văn bản nghị luận trung đại và hiện đại",
                    57,
                    82,
                    5,
                    (
                        "Phân tích mối quan hệ giữa luận đề, luận điểm, lí lẽ và bằng chứng; "
                        "nhận biết đoạn văn diễn dịch, quy nạp."
                    ),
                    (
                        (
                            "Phân tích được luận đề, luận điểm, lí lẽ và bằng chứng trong văn "
                            "bản nghị luận."
                        ),
                        "Viết được bài văn nghị luận về một vấn đề của đời sống.",
                    ),
                ),
                (
                    "Bài 5: Những câu chuyện hài",
                    "Đọc hiểu hài kịch, truyện cười và viết bài nghị luận về vấn đề đời sống",
                    103,
                    128,
                    4,
                    (
                        "Nhận diện xung đột kịch, thủ pháp trào phúng, câu hỏi tu từ và nghĩa "
                        "hàm ẩn trong đối thoại."
                    ),
                    ("Phân tích được xung đột, hành động và tiếng cười phê phán trong hài kịch.",),
                ),
            ],
        ),
        (
            "kntt-ngu-van-8-t2",
            "Ngữ văn",
            "8",
            "Tập hai",
            132,
            [
                (
                    "Bài 6: Chân dung cuộc sống",
                    "Đọc hiểu truyện ngắn hiện đại và viết bài văn phân tích một tác phẩm truyện",
                    6,
                    32,
                    5,
                    (
                        "Phân tích cốt truyện, nhân vật, chi tiết nghệ thuật và trợ từ, thán "
                        "từ trong lời thoại nhân vật."
                    ),
                    (
                        (
                            "Viết được bài văn phân tích chủ đề và nét đặc sắc nghệ thuật của "
                            "một tác phẩm truyện."
                        ),
                    ),
                ),
                (
                    "Bài 7: Tin yêu và ước vọng",
                    "Đọc hiểu thơ tự do và viết bài phân tích một tác phẩm thơ",
                    33,
                    56,
                    4,
                    (
                        "Phân tích mạch cảm xúc, hình ảnh, nhịp điệu trong thơ tự do và thành "
                        "phần biệt lập trong câu."
                    ),
                    ("Nhận biết được đặc điểm hình thức và cảm hứng chủ đạo của thơ tự do.",),
                ),
                (
                    "Bài 9: Hôm nay và ngày mai",
                    (
                        "Đọc hiểu văn bản thông tin giải thích hiện tượng tự nhiên và viết "
                        "văn bản thuyết minh"
                    ),
                    78,
                    106,
                    4,
                    (
                        "Đọc hiểu văn bản thông tin giải thích nguyên nhân - kết quả và cách "
                        "trình bày thông tin khách quan."
                    ),
                    (
                        (
                            "Viết được văn bản thuyết minh giải thích một hiện tượng tự nhiên "
                            "hoặc giới thiệu cuốn sách."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-ngu-van-9-t1",
            "Ngữ văn",
            "9",
            "Tập một",
            144,
            [
                (
                    "Bài 1: Thế giới kì ảo",
                    (
                        "Đọc hiểu truyện truyền kì và viết bài văn nghị luận về một vấn đề "
                        "cần giải quyết"
                    ),
                    10,
                    36,
                    5,
                    (
                        "Phân tích không gian, thời gian, yếu tố kì ảo trong truyện truyền "
                        "kì; nhận biết điển tích, điển cố."
                    ),
                    (
                        (
                            "Phân tích được vai trò của yếu tố kì ảo và thông điệp trong "
                            "truyện truyền kì."
                        ),
                        (
                            "Viết được bài văn nghị luận đề xuất giải pháp khả thi cho một "
                            "vấn đề đời sống."
                        ),
                    ),
                ),
                (
                    "Bài 2: Những cung bậc tâm trạng",
                    "Đọc hiểu thơ song thất lục bát và viết bài phân tích tác phẩm văn học (thơ)",
                    37,
                    60,
                    4,
                    (
                        "Nhận diện vần, nhịp, thanh điệu đặc trưng của thể thơ song thất lục "
                        "bát và biện pháp tu từ chơi chữ, điệp thanh."
                    ),
                    (
                        (
                            "Phân tích được nét đặc sắc nghệ thuật và cảm xúc trong thơ song "
                            "thất lục bát."
                        ),
                    ),
                ),
                (
                    "Bài 3: Hồn nước nằm trong tiếng mẹ cha",
                    "Đọc hiểu truyện thơ Nôm và chữ viết tiếng Việt",
                    61,
                    86,
                    5,
                    (
                        "Khảo sát cốt truyện, nhân vật, nghệ thuật tả người, tả cảnh trong "
                        "truyện thơ Nôm và cách dẫn trực tiếp, gián tiếp."
                    ),
                    (
                        (
                            "Phân tích được nội dung chủ đề và nghệ thuật xây dựng nhân vật "
                            "trong truyện thơ Nôm."
                        ),
                        "Phân biệt và chuyển đổi được lời dẫn trực tiếp sang lời dẫn gián tiếp.",
                    ),
                ),
                (
                    "Bài 5: Đối diện với nỗi đau",
                    "Đọc hiểu bi kịch và viết bài văn nghị luận phân tích tác phẩm kịch",
                    110,
                    136,
                    4,
                    (
                        "Nhận diện xung đột bi kịch, hành động, lời thoại và hiệu ứng thanh "
                        "lọc cảm xúc."
                    ),
                    ("Phân tích được xung đột và nhân vật bi kịch trong văn bản kịch.",),
                ),
            ],
        ),
        (
            "kntt-ngu-van-9-t2",
            "Ngữ văn",
            "9",
            "Tập hai",
            140,
            [
                (
                    "Bài 6: Giải mã những bí mật",
                    "Đọc hiểu truyện trinh thám và viết truyện kể sáng tạo",
                    6,
                    32,
                    5,
                    (
                        "Phân tích đầu mối, suy luận, không gian, thời gian trong truyện "
                        "trinh thám và câu rút gọn, câu đặc biệt."
                    ),
                    (
                        (
                            "Nhận biết được cốt truyện, chi tiết manh mối và nghệ thuật tạo "
                            "kịch tính trong truyện trinh thám."
                        ),
                        "Viết được một truyện kể sáng tạo có chi tiết miêu tả và biểu cảm.",
                    ),
                ),
                (
                    "Bài 7: Hồn thơ muôn điệu",
                    "Đọc hiểu thơ tám chữ, thơ tự do và viết đoạn văn ghi lại cảm nghĩ",
                    33,
                    56,
                    4,
                    (
                        "Phân tích kết cấu, hình ảnh biểu tượng, nhịp điệu thơ hiện đại và "
                        "viết bài nghị luận phân tích bài thơ."
                    ),
                    ("Phân tích được giá trị thẩm mĩ của hình ảnh, ngôn ngữ trong thơ hiện đại.",),
                ),
                (
                    "Bài 8: Tiếng nói của lương tri",
                    "Đọc hiểu văn bản nghị luận xã hội và viết bài nghị luận phân tích tác phẩm",
                    57,
                    84,
                    5,
                    (
                        "Đánh giá sức thuyết phục của hệ thống luận điểm, lí lẽ và bằng chứng "
                        "trong văn bản nghị luận."
                    ),
                    (
                        (
                            "Viết được bài văn nghị luận trình bày quan điểm thuyết phục về "
                            "vấn đề xã hội."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-ngu-van-10-t1",
            "Ngữ văn",
            "10",
            "Tập một",
            144,
            [
                (
                    "Bài 1: Sức hấp dẫn của truyện kể",
                    (
                        "Đọc hiểu thần thoại, truyện ngắn và viết văn bản nghị luận phân tích "
                        "tác phẩm truyện"
                    ),
                    10,
                    38,
                    5,
                    (
                        "Khảo sát không gian, thời gian thần thoại, ngôi kể, điểm nhìn và "
                        "nghệ thuật xây dựng nhân vật truyện kể."
                    ),
                    (
                        (
                            "Phân tích được cốt truyện, nhân vật, ngôi kể và điểm nhìn trong "
                            "văn bản truyện."
                        ),
                        (
                            "Viết được văn bản nghị luận phân tích, đánh giá chủ đề và nghệ "
                            "thuật tác phẩm truyện."
                        ),
                    ),
                ),
                (
                    "Bài 2: Vẻ đẹp của thơ ca",
                    "Đọc hiểu thơ Đường luật, thơ Hai-cư, thơ tự do và phân tích bài thơ",
                    39,
                    68,
                    5,
                    (
                        "Nhận diện nhân vật trữ tình, cảm hứng chủ đạo, hình ảnh, ngôn từ cô "
                        "đọng và sửa lỗi dùng từ."
                    ),
                    (
                        "Phân tích được giá trị thẩm mĩ của từ ngữ, hình ảnh, vần, nhịp trong thơ.",
                        "Viết được bài nghị luận phân tích, đánh giá một tác phẩm thơ.",
                    ),
                ),
                (
                    "Bài 3: Nghệ thuật thuyết phục trong văn nghị luận",
                    "Đọc hiểu văn bản nghị luận xã hội, văn học và viết bài luận thuyết phục",
                    69,
                    98,
                    5,
                    (
                        "Đánh giá cách triển khai luận đề, luận điểm, lí lẽ, bằng chứng và "
                        "sửa lỗi viết đoạn văn."
                    ),
                    (
                        (
                            "Viết được bài luận thuyết phục người khác từ bỏ một thói quen "
                            "hay quan niệm."
                        ),
                    ),
                ),
                (
                    "Bài 4: Sức sống của sử thi",
                    "Đọc hiểu sử thi anh hùng và viết báo cáo nghiên cứu có trích dẫn",
                    99,
                    124,
                    4,
                    (
                        "Phân tích không gian cộng đồng, nhân vật anh hùng sử thi và biện "
                        "pháp so sánh phóng đại."
                    ),
                    (
                        (
                            "Nhận biết được đặc trưng thể loại sử thi và viết báo cáo nghiên "
                            "cứu có chú thích."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-ngu-van-10-t2",
            "Ngữ văn",
            "10",
            "Tập hai",
            136,
            [
                (
                    "Bài 6: Nguyễn Trãi – 'Dành còn để trợ dân này'",
                    "Đọc hiểu văn chính luận, thơ Nôm Nguyễn Trãi và viết văn bản nghị luận xã hội",
                    6,
                    38,
                    5,
                    (
                        "Tìm hiểu tư tưởng nhân nghĩa, nghệ thuật chính luận và vẻ đẹp tâm "
                        "hồn trong thơ văn Nguyễn Trãi."
                    ),
                    (
                        (
                            "Phân tích được tư tưởng nhân nghĩa và nghệ thuật lập luận trong "
                            "văn chính luận trung đại."
                        ),
                        "Viết được bài văn nghị luận về một vấn đề xã hội có lập luận chặt chẽ.",
                    ),
                ),
                (
                    "Bài 7: Quyền năng của người kể chuyện",
                    "Đọc hiểu truyện ngắn hiện đại và viết bài phân tích một tác phẩm truyện",
                    39,
                    68,
                    5,
                    (
                        "Khảo sát vai trò người kể chuyện toàn tri, hạn tri, lời người kể "
                        "chuyện và lời nhân vật."
                    ),
                    ("Phân tích được sự dịch chuyển điểm nhìn và quyền năng của người kể chuyện.",),
                ),
                (
                    "Bài 8: Thế giới đa dạng của thông tin",
                    "Đọc hiểu văn bản thông tin tổng hợp và viết bản nội quy, hướng dẫn",
                    69,
                    98,
                    4,
                    (
                        "Đánh giá tính cập nhật, khách quan của dữ liệu và phương tiện phi "
                        "ngôn ngữ trong văn bản thông tin."
                    ),
                    (
                        (
                            "Phân tích được cách trình bày dữ liệu, biểu đồ và thông điệp "
                            "trong văn bản thông tin."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-ngu-van-10-cd",
            "Ngữ văn",
            "10",
            "Chuyên đề học tập",
            88,
            [
                (
                    "Chuyên đề 1: Tập nghiên cứu và viết báo cáo về một vấn đề văn học dân gian",
                    "Quy trình chọn đề tài, thu thập tư liệu và viết báo cáo văn học dân gian",
                    5,
                    32,
                    5,
                    (
                        "Hướng dẫn phương pháp điền dã, phân loại tư liệu và trích dẫn chuẩn "
                        "trong nghiên cứu văn học dân gian."
                    ),
                    (
                        (
                            "Viết và thuyết trình được báo cáo nghiên cứu về một vấn đề văn "
                            "học dân gian."
                        ),
                    ),
                ),
                (
                    "Chuyên đề 2: Sân khấu hóa tác phẩm văn học",
                    "Chuyển thể kịch bản và dàn dựng trích đoạn tác phẩm văn học",
                    33,
                    58,
                    5,
                    (
                        "Chuyển hóa cốt truyện, lời thoại văn học sang kịch bản sân khấu và "
                        "trình diễn."
                    ),
                    ("Xây dựng được kịch bản chuyển thể từ một tác phẩm văn học đã học.",),
                ),
            ],
        ),
        (
            "kntt-ngu-van-11-t1",
            "Ngữ văn",
            "11",
            "Tập một",
            148,
            [
                (
                    "Bài 1: Câu chuyện và điểm nhìn trong truyện kể",
                    "Đọc hiểu truyện ngắn hiện đại và viết văn bản nghị luận về tác phẩm truyện",
                    10,
                    40,
                    5,
                    (
                        "Phân tích sự kết hợp giữa câu chuyện, truyện kể, điểm nhìn trần "
                        "thuật và đặc điểm ngôn ngữ nói, viết."
                    ),
                    (
                        (
                            "Phân tích được nghệ thuật tổ chức điểm nhìn và lời trần thuật "
                            "trong truyện ngắn."
                        ),
                        (
                            "Viết được bài nghị luận phân tích giá trị nội dung và nghệ thuật "
                            "tác phẩm truyện."
                        ),
                    ),
                ),
                (
                    "Bài 2: Cấu tứ và hình ảnh trong thơ trữ tình",
                    "Đọc hiểu thơ trữ tình có yếu tố tượng trưng và viết bài phân tích thơ",
                    41,
                    72,
                    5,
                    (
                        "Nhận diện cấu tứ độc đáo, hình ảnh biểu tượng, yếu tố tượng trưng "
                        "trong thơ hiện đại."
                    ),
                    (
                        (
                            "Phân tích được cấu tứ, hình ảnh và vai trò của yếu tố tượng "
                            "trưng trong thơ trữ tình."
                        ),
                    ),
                ),
                (
                    "Bài 3: Cấu trúc của văn bản nghị luận",
                    "Đọc hiểu văn bản nghị luận xã hội, văn học và viết bài nghị luận xã hội",
                    73,
                    102,
                    5,
                    (
                        "Phân tích cấu trúc lập luận tầng bậc, yếu tố biểu cảm và cách phản "
                        "biện trong văn bản nghị luận."
                    ),
                    ("Viết được bài văn nghị luận về một vấn đề xã hội có lập luận đa chiều.",),
                ),
            ],
        ),
        (
            "kntt-ngu-van-11-t2",
            "Ngữ văn",
            "11",
            "Tập hai",
            140,
            [
                (
                    "Bài 6: Nguyễn Du – 'Những điều trông thấy mà đau đớn lòng'",
                    (
                        "Đọc hiểu Truyện Kiều, thơ chữ Hán Nguyễn Du và viết bài thuyết minh "
                        "tác phẩm văn học"
                    ),
                    6,
                    38,
                    5,
                    (
                        "Khảo sát chủ nghĩa nhân đạo, nghệ thuật miêu tả nội tâm và ngôn ngữ "
                        "văn học trong Truyện Kiều."
                    ),
                    (
                        "Phân tích được giá trị nhân đạo và bút pháp nghệ thuật của Nguyễn Du.",
                        "Viết được văn bản thuyết minh về một tác phẩm văn học.",
                    ),
                ),
                (
                    "Bài 7: Ghi chép và tưởng tượng trong kí",
                    (
                        "Đọc hiểu tùy bút, tản văn, truyện kí và viết bài thuyết minh về một "
                        "sự vật, hiện tượng"
                    ),
                    39,
                    68,
                    5,
                    (
                        "Nhận diện sự đan xen giữa tính xác thực và cảm xúc chủ quan, cái tôi "
                        "trữ tình trong kí."
                    ),
                    (
                        (
                            "Phân tích được sự kết hợp giữa tự sự, trữ tình và cái tôi tác "
                            "giả trong tùy bút, tản văn."
                        ),
                    ),
                ),
                (
                    "Bài 8: Cấu trúc của văn bản thông tin",
                    "Đọc hiểu văn bản thông tin tổng hợp và viết báo cáo nghiên cứu",
                    69,
                    98,
                    4,
                    (
                        "Phân tích bố cục, dữ liệu sơ cấp/thứ cấp và quan điểm người viết "
                        "trong văn bản thông tin."
                    ),
                    ("Đánh giá được độ tin cậy thông tin và viết báo cáo nghiên cứu khoa học.",),
                ),
            ],
        ),
        (
            "kntt-ngu-van-11-cd",
            "Ngữ văn",
            "11",
            "Chuyên đề học tập",
            88,
            [
                (
                    (
                        "Chuyên đề 1: Tập nghiên cứu và viết báo cáo về một vấn đề văn học "
                        "trung đại Việt Nam"
                    ),
                    "Phương pháp nghiên cứu thi pháp và giá trị văn học trung đại",
                    5,
                    34,
                    5,
                    (
                        "Tìm hiểu đặc trưng thể loại, quy phạm thẩm mĩ và cách lập hồ sơ tư "
                        "liệu văn học trung đại."
                    ),
                    (
                        (
                            "Viết được báo cáo nghiên cứu có luận điểm rõ ràng về một vấn đề "
                            "văn học trung đại."
                        ),
                    ),
                ),
                (
                    "Chuyên đề 2: Tìm hiểu ngôn ngữ trong đời sống xã hội hiện đại",
                    "Bản chất xã hội của ngôn ngữ và các yếu tố mới của tiếng Việt",
                    35,
                    62,
                    5,
                    (
                        "Khảo sát hiện tượng từ ngữ mới, ngôn ngữ truyền thông số và giữ gìn "
                        "sự trong sáng của tiếng Việt."
                    ),
                    ("Phân tích được tác động của truyền thông hiện đại đến ngôn ngữ giao tiếp.",),
                ),
            ],
        ),
        (
            "kntt-ngu-van-12-t1",
            "Ngữ văn",
            "12",
            "Tập một",
            156,
            [
                (
                    "Bài 1: Khả năng lớn lao của tiểu thuyết",
                    "Đọc hiểu: Tiểu thuyết hiện đại, giọng điệu châm biếm và đa thanh",
                    10,
                    32,
                    3,
                    (
                        "Phân tích đặc trưng tiểu thuyết hiện đại, điểm nhìn, ngôi kể, nói mỉa và "
                        "nghịch ngữ."
                    ),
                    (
                        (
                            "Phân tích được cốt truyện, nhân vật, điểm nhìn và ngôn ngữ tiểu "
                            "thuyết hiện đại."
                        ),
                    ),
                ),
                (
                    "Bài 1: Khả năng lớn lao của tiểu thuyết",
                    "Viết: Bài văn nghị luận so sánh, đánh giá hai tác phẩm truyện",
                    33,
                    42,
                    2,
                    (
                        "Lập luận so sánh, đánh giá giá trị nội dung và nghệ thuật của hai tác "
                        "phẩm truyện."
                    ),
                    ("Viết được bài văn nghị luận so sánh, đánh giá hai tác phẩm truyện.",),
                ),
                (
                    "Bài 2: Những thế giới thơ",
                    "Đọc hiểu: Thơ có yếu tố lãng mạn, siêu thực và biểu tượng",
                    43,
                    64,
                    3,
                    (
                        "Khảo sát phong cách cổ điển, lãng mạn, yếu tố siêu thực và hình ảnh biểu "
                        "tượng trong thơ."
                    ),
                    (
                        (
                            "Phân tích được biểu hiện của yếu tố lãng mạn và siêu thực trong thơ "
                            "trữ tình."
                        ),
                    ),
                ),
                (
                    "Bài 2: Những thế giới thơ",
                    "Viết: Bài văn nghị luận so sánh, đánh giá hai tác phẩm thơ",
                    65,
                    74,
                    2,
                    "Thực hành viết bài nghị luận so sánh, đánh giá hai tác phẩm thơ trữ tình.",
                    ("Viết được bài nghị luận so sánh, đánh giá hai tác phẩm thơ.",),
                ),
                (
                    "Bài 3: Lập luận trong văn bản nghị luận",
                    "Đọc hiểu: Văn bản nghị luận xã hội và nghị luận văn học",
                    75,
                    96,
                    3,
                    "Đánh giá nghệ thuật lập luận, dẫn chứng xác thực, thao tác bác bỏ và bác lập.",
                    (
                        (
                            "Phân tích được luận đề, luận điểm, lí lẽ và bằng chứng trong văn bản "
                            "nghị luận."
                        ),
                    ),
                ),
                (
                    "Bài 3: Lập luận trong văn bản nghị luận",
                    "Viết: Bài văn nghị luận về một vấn đề liên quan đến tuổi trẻ",
                    97,
                    106,
                    2,
                    (
                        "Triển khai lập luận sắc bén về cơ hội, thách thức và trách nhiệm của thế "
                        "hệ trẻ."
                    ),
                    ("Viết được bài văn nghị luận về một vấn đề liên quan đến tuổi trẻ hiện nay.",),
                ),
                (
                    "Bài 4: Yếu tố kì ảo trong truyện kể",
                    "Đọc hiểu: Truyện kể có yếu tố kì ảo trong văn học trung đại và hiện đại",
                    107,
                    122,
                    3,
                    (
                        "Khảo sát vai trò của yếu tố kì ảo, chi tiết tưởng tượng và thông điệp "
                        "nhân sinh trong truyện kể."
                    ),
                    ("Phân tích được chức năng của yếu tố kì ảo trong tác phẩm tự sự.",),
                ),
                (
                    "Bài 4: Yếu tố kì ảo trong truyện kể",
                    (
                        "Viết: Bài văn nghị luận về việc vay mượn, cải biến, sáng tạo trong tác "
                        "phẩm văn học"
                    ),
                    123,
                    131,
                    2,
                    (
                        "Phân tích và đánh giá hiện tượng vay mượn cốt truyện, mô-típ và sáng tạo "
                        "nghệ thuật."
                    ),
                    (
                        (
                            "Viết được bài nghị luận về việc vay mượn – cải biến – sáng tạo trong "
                            "văn học."
                        ),
                    ),
                ),
                (
                    "Bài 5: Tiếng cười của hài kịch",
                    "Đọc hiểu: Hài kịch, xung đột trào phúng và tiếng cười của hài kịch",
                    132,
                    146,
                    3,
                    (
                        "Nhận diện xung đột kịch, hành động, lời thoại, thủ pháp phóng đại và "
                        "tiếng cười của hài kịch."
                    ),
                    (
                        (
                            "Phân tích được xung đột, nhân vật và ý nghĩa phê phán của tiếng cười "
                            "hài kịch."
                        ),
                    ),
                ),
                (
                    "Bài 5: Tiếng cười của hài kịch",
                    "Viết: Báo cáo kết quả nghiên cứu về một vấn đề tự nhiên hoặc xã hội",
                    147,
                    155,
                    2,
                    (
                        "Trình bày giả thuyết, phương pháp khảo sát, dữ liệu và kết luận nghiên "
                        "cứu khoa học."
                    ),
                    ("Viết được báo cáo nghiên cứu hoàn chỉnh, trích dẫn rõ ràng.",),
                ),
            ],
        ),
        (
            "kntt-ngu-van-12-t2",
            "Ngữ văn",
            "12",
            "Tập hai",
            148,
            [
                (
                    "Bài 6: Hồ Chí Minh – 'Văn hóa phải soi đường cho quốc dân đi'",
                    "Đọc hiểu: Văn chính luận, truyện ngắn và thơ Hồ Chí Minh",
                    6,
                    30,
                    3,
                    (
                        "Phân tích phong cách nghệ thuật đa dạng, lập luận sắc bén trong sáng tác "
                        "Hồ Chí Minh."
                    ),
                    (
                        (
                            "Phân tích được phong cách nghệ thuật và giá trị tư tưởng trong tác "
                            "phẩm Hồ Chí Minh."
                        ),
                    ),
                ),
                (
                    "Bài 6: Hồ Chí Minh – 'Văn hóa phải soi đường cho quốc dân đi'",
                    "Viết: Báo cáo kết quả của bài tập dự án (báo cáo dự án)",
                    31,
                    40,
                    2,
                    (
                        "Viết báo cáo dự án học tập: mục tiêu, tiến trình thực hiện, sản phẩm và "
                        "đánh giá."
                    ),
                    ("Viết được báo cáo kết quả của bài tập dự án rõ ràng, mạch lạc.",),
                ),
                (
                    "Bài 7: Sự thật trong tác phẩm kí",
                    "Đọc hiểu: Phóng sự, hồi kí, nhật kí và tính phi hư cấu",
                    41,
                    62,
                    3,
                    (
                        "Nhận diện tính phi hư cấu, chi tiết xác thực và nghệ thuật kể chuyện "
                        "trong phóng sự, hồi kí."
                    ),
                    (
                        (
                            "Phân tích được sự kết hợp giữa tính phi hư cấu và thủ pháp nghệ "
                            "thuật trong kí."
                        ),
                    ),
                ),
                (
                    "Bài 7: Sự thật trong tác phẩm kí",
                    "Viết: Bài văn nghị luận về cách ứng xử của tuổi trẻ",
                    63,
                    72,
                    2,
                    (
                        "Trình bày quan điểm và lập luận về cách ứng xử, lối sống có trách nhiệm "
                        "của tuổi trẻ."
                    ),
                    ("Viết được bài nghị luận về một vấn đề liên quan đến ứng xử của tuổi trẻ.",),
                ),
                (
                    "Bài 8: Dữ liệu trong văn bản thông tin",
                    "Đọc hiểu: Văn bản thông tin hiện đại và độ tin cậy dữ liệu",
                    73,
                    94,
                    3,
                    (
                        "Phân biệt dữ liệu sơ cấp, thứ cấp, độ tin cậy nguồn tin và trình bày "
                        "thông tin khoa học."
                    ),
                    (
                        (
                            "Đánh giá được tính chính xác, khách quan của dữ liệu trong văn bản "
                            "thông tin."
                        ),
                    ),
                ),
                (
                    "Bài 8: Dữ liệu trong văn bản thông tin",
                    "Viết: Thư trao đổi về công việc hoặc một vấn đề đáng quan tâm",
                    95,
                    104,
                    2,
                    (
                        "Viết thư trao đổi công việc chuẩn mực, lịch sự, đúng thể thức và rõ mục "
                        "đích giao tiếp."
                    ),
                    ("Viết được thư trao đổi công việc hoặc vấn đề đáng quan tâm.",),
                ),
                (
                    "Bài 9: Văn học và cuộc đời",
                    "Đọc hiểu: Văn học và cuộc đời – tác phẩm kết nối đời sống đương đại",
                    105,
                    128,
                    3,
                    (
                        "Khảo sát mối quan hệ giữa văn học và cuộc đời, sức sống lâu bền và giá "
                        "trị nhân văn của tác phẩm."
                    ),
                    ("Phân tích được ý nghĩa nhân sinh và sức tác động của văn học với cuộc đời.",),
                ),
                (
                    "Bài 9: Văn học và cuộc đời",
                    (
                        "Viết: Bài phát biểu trong lễ phát động một phong trào hoặc một hoạt động "
                        "xã hội"
                    ),
                    129,
                    142,
                    2,
                    (
                        "Xây dựng bài phát biểu truyền cảm hứng, kết hợp lí lẽ thuyết phục và lời "
                        "kêu gọi hành động."
                    ),
                    ("Viết được bài phát biểu trong lễ phát động phong trào xã hội.",),
                ),
            ],
        ),
        (
            "kntt-ngu-van-12-cd",
            "Ngữ văn",
            "12",
            "Chuyên đề học tập",
            88,
            [
                (
                    "Chuyên đề 1: Tập nghiên cứu và viết báo cáo về một vấn đề văn học hiện đại",
                    "Nghiên cứu trào lưu, tác giả và phong cách văn học hiện đại",
                    5,
                    34,
                    5,
                    (
                        "Triển khai đề tài nghiên cứu văn học hiện đại với trích dẫn và danh mục "
                        "tài liệu tham khảo."
                    ),
                    ("Viết được báo cáo nghiên cứu hoàn chỉnh về một vấn đề văn học hiện đại.",),
                ),
                (
                    "Chuyên đề 2: Tìm hiểu về một tác phẩm nghệ thuật chuyển thể từ văn học",
                    "Phân tích sự sáng tạo giữa nguyên tác văn học và tác phẩm điện ảnh, hội họa",
                    35,
                    62,
                    5,
                    (
                        "So sánh ngôn ngữ văn học với ngôn ngữ điện ảnh, âm nhạc trong tác phẩm "
                        "chuyển thể."
                    ),
                    ("Phân tích và đánh giá được giá trị sáng tạo của một tác phẩm chuyển thể.",),
                ),
                (
                    (
                        "Chuyên đề 3: Tìm hiểu phong cách sáng tác của một trường phái văn học: "
                        "cổ điển, hiện thực hoặc lãng mạn"
                    ),
                    "Phong cách sáng tác của một trường phái văn học: cổ điển, hiện thực, lãng mạn",
                    63,
                    86,
                    5,
                    (
                        "Nhận diện đặc trưng thẩm mĩ, thi pháp và phong cách sáng tác của các "
                        "trường phái văn học."
                    ),
                    (
                        (
                            "Phân tích được dấu ấn trường phái cổ điển, hiện thực hoặc lãng mạn "
                            "qua tác phẩm."
                        ),
                    ),
                ),
            ],
        ),
        # ==================== TIẾNG ANH 3–12 (GLOBAL SUCCESS) ====================
        (
            "kntt-tieng-anh-3-t1",
            "Tiếng Anh",
            "3",
            "Tập một",
            72,
            [
                (
                    "Unit 1–5: Hello, Our names, Our friends, Our bodies, My hobbies",
                    "Greetings, introductions, body parts and hobbies",
                    10,
                    39,
                    6,
                    (
                        "Basic greetings, asking names and ages, naming body parts and "
                        "talking about simple hobbies."
                    ),
                    (
                        (
                            "Greet and introduce oneself using 'What is your name?' and 'How "
                            "old are you?'."
                        ),
                        "Identify basic body parts and express simple hobbies with 'I like...'.",
                    ),
                ),
                (
                    (
                        "Unit 6–10: Our school, Classroom instructions, My school things, "
                        "Colours, Break time activities"
                    ),
                    "School rooms, instructions, stationery, colours and games",
                    44,
                    71,
                    6,
                    (
                        "Following classroom instructions, naming school items, colours and "
                        "break-time activities."
                    ),
                    (
                        (
                            "Use 'Do you have...?' and 'What colour is it?' in simple "
                            "classroom exchanges."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-3-t2",
            "Tiếng Anh",
            "3",
            "Tập hai",
            72,
            [
                (
                    "Unit 11–15: My family, Jobs, My house, My bedroom, At the dining table",
                    "Family members, occupations, rooms and food",
                    6,
                    35,
                    6,
                    "Talking about family members, jobs, rooms in a house and polite food offers.",
                    ("Ask and answer about family jobs and rooms using 'There is / There are'.",),
                ),
                (
                    (
                        "Unit 16–20: My pets, Our toys, Playing and doing, Outdoor "
                        "activities, At the zoo"
                    ),
                    "Pets, toys, present continuous actions and zoo animals",
                    40,
                    69,
                    6,
                    (
                        "Describing ongoing activities with present continuous and naming "
                        "common animals."
                    ),
                    ("Describe actions happening now with 'What are you doing? - I am...'.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-4-t1",
            "Tiếng Anh",
            "4",
            "Tập một",
            72,
            [
                (
                    (
                        "Unit 1–5: All about me, Time and daily routines, My week, My "
                        "birthday party, Things we can do"
                    ),
                    "Countries, telling time, days of the week, months and abilities",
                    10,
                    39,
                    6,
                    (
                        "Talking about nationalities, daily schedules, birthdays and "
                        "expressing abilities with 'can'."
                    ),
                    (
                        "Tell the time and describe daily routines and weekly timetables.",
                        "Use 'can / can't' to ask and answer about abilities.",
                    ),
                ),
                (
                    (
                        "Unit 6–10: Our school facilities, Our timetables, My favourite "
                        "subjects, Our sports day, Our summer holidays"
                    ),
                    "School facilities, subjects, sports and past simple 'were'",
                    44,
                    71,
                    6,
                    (
                        "Describing school rooms, favourite subjects and asking where someone "
                        "was last summer."
                    ),
                    (
                        (
                            "Explain reasons for favourite subjects and use 'Were you at...?' "
                            "accurately."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-4-t2",
            "Tiếng Anh",
            "4",
            "Tập hai",
            72,
            [
                (
                    "Unit 11–15: My home, Jobs, Appearance, Daily activities, My family's weekends",
                    "Addresses, jobs, describing appearance and weekend routines",
                    6,
                    35,
                    6,
                    (
                        "Asking about addresses, describing people's physical appearance and "
                        "weekend activities."
                    ),
                    ("Describe appearance with 'What does he/she look like?' and weekend habits.",),
                ),
                (
                    (
                        "Unit 16–20: Weather, In the city, At the shopping centre, The animal "
                        "world, At summer camp"
                    ),
                    "Weather, directions, shopping prices and animals",
                    40,
                    69,
                    6,
                    (
                        "Asking about the weather, giving simple street directions and asking "
                        "prices with 'How much'."
                    ),
                    (
                        (
                            "Ask and answer about weather, directions and item prices in "
                            "daily contexts."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-5-t1",
            "Tiếng Anh",
            "5",
            "Tập một",
            72,
            [
                (
                    (
                        "Unit 1–5: All about me, Our homes, My foreign friends, Our free-time "
                        "activities, My future job"
                    ),
                    "Personal profiles, homes, personality adjectives, free time and future jobs",
                    10,
                    39,
                    6,
                    (
                        "Describing personality, frequency of hobbies and expressing future "
                        "career wishes with 'would like to be'."
                    ),
                    ("Use adverbs of frequency and 'would like to be' in simple conversations.",),
                ),
                (
                    (
                        "Unit 6–10: Our school rooms, Our favourite school activities, In our "
                        "classroom, Our outdoor activities, Our school trip"
                    ),
                    "Floor locations, possessions, past simple regular and irregular verbs",
                    44,
                    71,
                    6,
                    (
                        "Asking locations in school and recounting past outdoor trips using "
                        "past simple tense."
                    ),
                    ("Recount past events accurately using 'Did you...?' and past simple verbs.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-5-t2",
            "Tiếng Anh",
            "5",
            "Tập hai",
            72,
            [
                (
                    (
                        "Unit 11–15: Family time, Our Tet holiday, Our special days, Staying "
                        "healthy, Our health"
                    ),
                    "Family trips, Tet plans with 'will', healthy habits and health advice",
                    6,
                    35,
                    6,
                    (
                        "Talking about festival plans, healthy eating habits and giving "
                        "health advice with 'should'."
                    ),
                    (
                        (
                            "Give simple health advice with 'should / shouldn't' and talk "
                            "about future holiday plans."
                        ),
                    ),
                ),
                (
                    (
                        "Unit 16–20: Seasons and the weather, Stories for children, Means of "
                        "transport, Places of interest, Our summer holidays"
                    ),
                    "Seasonal clothing, characters, transport and 'be going to' plans",
                    40,
                    69,
                    6,
                    (
                        "Talking about means of transport, famous landmarks and summer plans "
                        "with 'be going to'."
                    ),
                    ("Ask and answer about travel plans and distances using 'be going to'.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-6-t1",
            "Tiếng Anh",
            "6",
            "Tập một",
            72,
            [
                (
                    "Unit 1–3: My New School, My House, My Friends",
                    "Present simple, possessive case, prepositions of place and present continuous",
                    6,
                    35,
                    6,
                    (
                        "Talking about school routines, describing houses and furniture, and "
                        "describing friends' appearance and personality."
                    ),
                    (
                        (
                            "Distinguish present simple for routines and present continuous "
                            "for current actions."
                        ),
                        "Use prepositions of place and possessive 's accurately.",
                    ),
                ),
                (
                    "Unit 4–6: My Neighbourhood, Natural Wonders of Viet Nam, Our Tet Holiday",
                    (
                        "Comparative adjectives, countable/uncountable nouns, must/mustn't "
                        "and should/shouldn't"
                    ),
                    38,
                    67,
                    6,
                    (
                        "Comparing neighbourhoods, discussing Vietnamese natural wonders and "
                        "Tet customs."
                    ),
                    ("Form comparative adjectives and use 'must / should' for rules and advice.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-6-t2",
            "Tiếng Anh",
            "6",
            "Tập hai",
            72,
            [
                (
                    "Unit 7–9: Television, Sports and Games, Cities of the World",
                    "Wh-questions, conjunctions, past simple, imperatives and possessive pronouns",
                    6,
                    35,
                    6,
                    (
                        "Discussing TV programmes, sports events in the past and famous "
                        "cities around the world."
                    ),
                    (
                        (
                            "Use past simple tense and coordinating conjunctions (and, but, "
                            "so) accurately."
                        ),
                    ),
                ),
                (
                    "Unit 10–12: Our Houses in the Future, Our Greener World, Robots",
                    "Future simple 'will', might, first conditional and superlative adjectives",
                    38,
                    67,
                    6,
                    (
                        "Predicting future homes, environmental protection with first "
                        "conditional and comparing robots."
                    ),
                    ("Form first conditional sentences and superlative adjectives accurately.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-7-t1",
            "Tiếng Anh",
            "7",
            "Tập một",
            72,
            [
                (
                    "Unit 1–3: Hobbies, Healthy Living, Community Service",
                    "Verbs of liking + V-ing, simple sentences and past simple",
                    8,
                    37,
                    6,
                    (
                        "Talking about hobbies, health tips and volunteer community "
                        "activities in the past."
                    ),
                    ("Use verbs of liking + V-ing and past simple to recount volunteer work.",),
                ),
                (
                    "Unit 4–6: Music and Arts, Food and Drink, A Visit to a School",
                    (
                        "Comparisons (like, different from, as...as), some/any/lots of and "
                        "prepositions of time/place"
                    ),
                    40,
                    69,
                    6,
                    "Comparing art forms, ordering traditional food and describing school visits.",
                    (
                        (
                            "Use 'as...as', 'different from', quantifiers and prepositions "
                            "'in, on, at' correctly."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-7-t2",
            "Tiếng Anh",
            "7",
            "Tập hai",
            72,
            [
                (
                    "Unit 7–9: Traffic, Films, Festivals around the World",
                    (
                        "It indicating distance, should/shouldn't, although/however and "
                        "Yes/No questions"
                    ),
                    8,
                    37,
                    6,
                    (
                        "Talking about traffic rules, reviewing films with concessive linkers "
                        "and describing world festivals."
                    ),
                    ("Connect contrasting clauses with 'although / though' and 'however'.",),
                ),
                (
                    (
                        "Unit 10–12: Energy Sources, Travelling in the Future, "
                        "English-speaking Countries"
                    ),
                    "Present continuous, future simple, possessive pronouns and articles a/an/the",
                    40,
                    69,
                    6,
                    (
                        "Discussing renewable energy, future transport predictions and "
                        "English-speaking cultures."
                    ),
                    ("Use articles 'a, an, the' and future simple predictions accurately.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-8-t1",
            "Tiếng Anh",
            "8",
            "Cả năm",
            128,
            [
                (
                    "Học kỳ I · Unit 1–6",
                    "Unit 1: Leisure Time",
                    8,
                    17,
                    7,
                    "Leisure activities, verbs of liking/disliking + gerunds/to-infinitives.",
                    (
                        (
                            "Use verbs of liking + V-ing/to-V accurately when talking about "
                            "leisure time."
                        ),
                    ),
                ),
                (
                    "Học kỳ I · Unit 1–6",
                    "Unit 2: Life in the Countryside",
                    18,
                    27,
                    7,
                    "Countryside life vocabulary and comparative forms of adverbs.",
                    ("Form comparative adverbs to compare rural and urban lifestyles.",),
                ),
                (
                    "Học kỳ I · Unit 1–6",
                    "Unit 3: Teenagers",
                    28,
                    37,
                    7,
                    "Teenage interests, school clubs, social media, simple and compound sentences.",
                    (
                        (
                            "Build compound sentences with 'however, therefore, otherwise, for, "
                            "and, but'."
                        ),
                    ),
                ),
                (
                    "Học kỳ I · Unit 1–6",
                    "Unit 4: Ethnic Groups of Viet Nam",
                    40,
                    49,
                    7,
                    "Ethnic cultures, Yes/No and Wh-questions, countable and uncountable nouns.",
                    (
                        (
                            "Use countable/uncountable nouns and Wh-questions to discuss ethnic "
                            "cultures."
                        ),
                    ),
                ),
                (
                    "Học kỳ I · Unit 1–6",
                    "Unit 5: Our Customs and Traditions",
                    50,
                    59,
                    7,
                    "Vietnamese customs, festivals, table manners and zero article usage.",
                    ("Apply definite, indefinite and zero articles accurately.",),
                ),
                (
                    "Học kỳ I · Unit 1–6",
                    "Unit 6: Lifestyles",
                    60,
                    69,
                    7,
                    (
                        "Traditional vs. modern lifestyles, future simple and first conditional "
                        "with 'unless'."
                    ),
                    ("Use future simple and first conditional with 'if / unless' accurately.",),
                ),
                (
                    "Học kỳ II · Unit 7–12",
                    "Unit 7: Environmental Protection",
                    72,
                    81,
                    7,
                    (
                        "Ecosystems, pollution prevention and complex sentences with adverb "
                        "clauses of time."
                    ),
                    (
                        (
                            "Combine clauses using adverbial time conjunctions 'before, after, "
                            "when, while, until'."
                        ),
                    ),
                ),
                (
                    "Học kỳ II · Unit 7–12",
                    "Unit 8: Shopping",
                    82,
                    91,
                    7,
                    (
                        "Shopping habits, online markets, adverbs of frequency and present simple "
                        "for future."
                    ),
                    (
                        (
                            "Use adverbs of frequency and present simple for schedules and "
                            "shopping habits."
                        ),
                    ),
                ),
                (
                    "Học kỳ II · Unit 7–12",
                    "Unit 9: Natural Disasters",
                    92,
                    101,
                    7,
                    "Storms, floods, emergency preparedness and past continuous tense.",
                    ("Combine past simple and past continuous with 'when / while' accurately.",),
                ),
                (
                    "Học kỳ II · Unit 7–12",
                    "Unit 10: Communication in the Future",
                    104,
                    113,
                    7,
                    "Digital communication, prepositions of place/time and possessive pronouns.",
                    ("Use prepositions of place/time and possessive pronouns accurately.",),
                ),
                (
                    "Học kỳ II · Unit 7–12",
                    "Unit 11: Science and Technology",
                    114,
                    121,
                    7,
                    "Scientific inventions, smart devices and reported speech (statements).",
                    ("Transform direct statements into reported speech accurately.",),
                ),
                (
                    "Học kỳ II · Unit 7–12",
                    "Unit 12: Life on Other Planets",
                    122,
                    128,
                    7,
                    "Solar system, space exploration and reported speech (questions).",
                    ("Report Yes/No and Wh-questions about space and planets accurately.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-9-t1",
            "Tiếng Anh",
            "9",
            "Tập một",
            72,
            [
                (
                    "Unit 1–3: Local Community, City Life, Healthy Living for Teens",
                    (
                        "Question words before to-infinitives, phrasal verbs, double "
                        "comparatives and modal verbs in first conditional"
                    ),
                    8,
                    37,
                    6,
                    (
                        "Exploring local craft villages, city challenges and balanced "
                        "study-health habits for teenagers."
                    ),
                    (
                        (
                            "Use 'question word + to-V', double comparatives ('the more..., "
                            "the more...') and phrasal verbs."
                        ),
                    ),
                ),
                (
                    (
                        "Unit 4–6: Remembering the Past, Our Experiences, Vietnamese "
                        "Lifestyle: Then and Now"
                    ),
                    "Past continuous, wish + past simple, present perfect and verbs + to-V / V-ing",
                    40,
                    69,
                    6,
                    (
                        "Expressing present wishes, sharing memorable life experiences and "
                        "contrasting lifestyles across generations."
                    ),
                    ("Use 'wish + past simple' and present perfect tense accurately in context.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-9-t2",
            "Tiếng Anh",
            "9",
            "Tập hai",
            72,
            [
                (
                    "Unit 7–9: Natural Wonders of the World, Tourism, World Englishes",
                    "Reported Yes/No questions, defining relative clauses (who, which, whose)",
                    8,
                    37,
                    6,
                    (
                        "Reporting inquiries about natural wonders, planning tourism "
                        "itineraries and exploring global varieties of English."
                    ),
                    ("Use defining relative clauses and reported Yes/No questions accurately.",),
                ),
                (
                    "Unit 10–12: Planet Earth, Electronic Devices, Career Choices",
                    (
                        "Non-defining relative clauses, suggest/advise/recommend + "
                        "V-ing/clause, adverbial clauses of concession/result/reason"
                    ),
                    40,
                    69,
                    6,
                    (
                        "Discussing ecosystems, digital devices and future career pathways "
                        "with complex adverbial clauses."
                    ),
                    (
                        (
                            "Use non-defining relative clauses and 'so...that / such...that / "
                            "although' accurately."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-10-t1",
            "Tiếng Anh",
            "10",
            "Tập một",
            64,
            [
                (
                    "Unit 1–3: Family Life, Humans and the Environment, Music",
                    (
                        "Present simple vs. present continuous, passive voice, will vs. be "
                        "going to, compound sentences & to-infinitives"
                    ),
                    8,
                    37,
                    6,
                    (
                        "Discussing household chores, reducing carbon footprints and "
                        "exploring musical genres."
                    ),
                    (
                        (
                            "Use passive voice, future forms and compound sentences "
                            "accurately in academic topics."
                        ),
                    ),
                ),
                (
                    "Unit 4–5: For a Better Community, Inventions",
                    "Past simple vs. past continuous, present perfect, gerunds and to-infinitives",
                    42,
                    61,
                    5,
                    (
                        "Sharing community volunteer projects and evaluating modern "
                        "technological inventions."
                    ),
                    (
                        (
                            "Distinguish gerunds and to-infinitives as subjects and objects; "
                            "apply present perfect."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-10-t2",
            "Tiếng Anh",
            "10",
            "Tập hai",
            64,
            [
                (
                    (
                        "Unit 6–8: Gender Equality, Viet Nam and International Organisations, "
                        "New Ways to Learn"
                    ),
                    "Passive voice with modals, comparatives/superlatives and relative clauses",
                    66,
                    95,
                    6,
                    (
                        "Discussing gender equality, international cooperation and "
                        "blended/online learning methods."
                    ),
                    (
                        (
                            "Form passive voice with modal verbs and defining/non-defining "
                            "relative clauses."
                        ),
                    ),
                ),
                (
                    "Unit 9–10: Protecting the Environment, Ecotourism",
                    "Reported speech and conditional sentences type 1 and type 2",
                    100,
                    119,
                    5,
                    (
                        "Reporting environmental viewpoints and proposing sustainable "
                        "ecotourism solutions."
                    ),
                    ("Use reported speech and conditional type 1 & 2 accurately in context.",),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-11-t1",
            "Tiếng Anh",
            "11",
            "Tập một",
            64,
            [
                (
                    "Unit 1–3: A Long and Healthy Life, The Generation Gap, Cities of the Future",
                    (
                        "Past simple vs. present perfect, modal verbs (must, have to, "
                        "should), stative verbs and linking verbs"
                    ),
                    8,
                    37,
                    6,
                    (
                        "Analysing healthy habits, bridging generational differences and "
                        "designing smart sustainable cities."
                    ),
                    (
                        (
                            "Distinguish past simple and present perfect; use modals of "
                            "obligation and stative verbs."
                        ),
                    ),
                ),
                (
                    "Unit 4–5: ASEAN and Viet Nam, Global Warming",
                    "Gerunds as subjects and objects, present and past participle clauses",
                    42,
                    61,
                    5,
                    (
                        "Exploring ASEAN youth programmes and analysing causes and solutions "
                        "for global warming."
                    ),
                    (
                        (
                            "Use present and past participle clauses to condense complex "
                            "sentences accurately."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-11-t2",
            "Tiếng Anh",
            "11",
            "Tập hai",
            64,
            [
                (
                    (
                        "Unit 6–8: Preserving Our Heritage, Education Options for "
                        "School-Leavers, Becoming Independent"
                    ),
                    (
                        "To-infinitive clauses, perfect gerunds, perfect participle clauses "
                        "and cleft sentences"
                    ),
                    66,
                    95,
                    6,
                    (
                        "Discussing heritage conservation, post-secondary education pathways "
                        "and independent life skills."
                    ),
                    (
                        (
                            "Use cleft sentences ('It is... that...') and perfect participle "
                            "clauses accurately."
                        ),
                    ),
                ),
                (
                    "Unit 9–10: Social Issues, The Ecosystem",
                    "Linking words/phrases (because of, despite, in addition) and compound nouns",
                    100,
                    119,
                    5,
                    (
                        "Addressing peer pressure, social issues and biodiversity "
                        "conservation in ecosystems."
                    ),
                    (
                        (
                            "Use cohesive discourse markers to structure persuasive essays "
                            "and discussions."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-12-t1",
            "Tiếng Anh",
            "12",
            "Tập một",
            72,
            [
                (
                    "Unit 1–3: Life Stories We Admire, A Multicultural World, Green Living",
                    (
                        "Past simple & past continuous, articles, verbs with prepositions and "
                        "relative clauses referring to a whole sentence"
                    ),
                    8,
                    43,
                    6,
                    (
                        "Examining inspiring biographies, cultural diversity and zero-waste "
                        "green living practices."
                    ),
                    (
                        (
                            "Use sentential relative clauses (', which...') and academic "
                            "verb-preposition collocations."
                        ),
                    ),
                ),
                (
                    "Unit 4–5: Urbanisation, The World of Work",
                    "Present perfect, double comparatives and simple/compound/complex sentences",
                    48,
                    71,
                    5,
                    (
                        "Evaluating urbanisation trends and preparing job applications for "
                        "the modern workplace."
                    ),
                    (
                        (
                            "Apply double comparatives and varied sentence structures in "
                            "academic writing."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tieng-anh-12-t2",
            "Tiếng Anh",
            "12",
            "Tập hai",
            72,
            [
                (
                    (
                        "Unit 6–8: Artificial Intelligence, The World of Mass Media, Wildlife "
                        "Conservation"
                    ),
                    (
                        "Active & passive causatives (have/get something done), adverbial "
                        "clauses of manner/result/condition/comparison"
                    ),
                    76,
                    111,
                    6,
                    (
                        "Evaluating AI applications, digital media literacy and endangered "
                        "wildlife protection."
                    ),
                    ("Use causative structures and complex adverbial clauses accurately.",),
                ),
                (
                    "Unit 9–10: Career Paths, Lifelong Learning",
                    (
                        "Three-word phrasal verbs and reported speech (orders, requests, "
                        "offers, advice)"
                    ),
                    116,
                    139,
                    5,
                    "Planning adaptive career paths and cultivating lifelong learning habits.",
                    (
                        (
                            "Use reporting verbs (advise, offer, remind) and three-word "
                            "phrasal verbs accurately."
                        ),
                    ),
                ),
            ],
        ),
        # ==================== KHOA HỌC TỰ NHIÊN 6–9 ====================
        (
            "kntt-khtn-6-t1",
            "Khoa học tự nhiên",
            "6",
            "Tập một",
            96,
            [
                (
                    "Chương I: Mở đầu về Khoa học tự nhiên",
                    "Bài 4–7: Đo chiều dài, khối lượng, thời gian và nhiệt độ",
                    16,
                    31,
                    4,
                    (
                        "Lựa chọn dụng cụ đo phù hợp, đọc kết quả theo GHĐ, ĐCNN và chuyển "
                        "đổi đơn vị đo cơ bản."
                    ),
                    (
                        (
                            "Thực hành đo được chiều dài, khối lượng, thời gian và nhiệt độ "
                            "đúng quy trình."
                        ),
                    ),
                ),
                (
                    "Chương II–III: Chất quanh ta và Hỗn hợp",
                    "Bài 12–16: Nhiên liệu, lương thực, dung dịch và tách chất ra khỏi hỗn hợp",
                    42,
                    63,
                    5,
                    (
                        "Phân biệt chất tinh khiết, hỗn hợp, dung dịch và vận dụng phương "
                        "pháp lọc, cô cạn, chiết tách chất."
                    ),
                    ("Đề xuất và thực hiện được cách tách chất đơn giản ra khỏi hỗn hợp.",),
                ),
                (
                    "Chương IV–V: Tế bào và Cơ thể sinh vật",
                    "Bài 18–21: Tế bào – đơn vị cơ bản của sự sống và tổ chức cơ thể đa bào",
                    66,
                    85,
                    4,
                    (
                        "Nhận biết cấu tạo tế bào nhân sơ, nhân thực và các cấp độ tổ chức từ "
                        "tế bào đến cơ thể."
                    ),
                    (
                        (
                            "Nêu được chức năng các thành phần chính của tế bào và quá trình "
                            "lớn lên, sinh sản của tế bào."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-khtn-6-t2",
            "Khoa học tự nhiên",
            "6",
            "Tập hai",
            96,
            [
                (
                    "Chương VI: Phân loại thế giới sống",
                    "Bài 23–28: Khóa lưỡng phân, virus, vi khuẩn, thực vật và động vật",
                    6,
                    38,
                    5,
                    (
                        "Xây dựng khóa lưỡng phân phân loại sinh vật và nhận biết vai trò đa "
                        "dạng sinh học."
                    ),
                    (
                        (
                            "Xây dựng được khóa lưỡng phân đơn giản và nêu biện pháp bảo vệ "
                            "đa dạng sinh học."
                        ),
                    ),
                ),
                (
                    "Chương VII–IX: Lực, Năng lượng và Trái Đất – Bầu trời",
                    "Bài 35–44: Lực và biểu diễn lực, ma sát, chuyển hóa năng lượng và Hệ Mặt Trời",
                    42,
                    88,
                    6,
                    (
                        "Biểu diễn lực bằng mũi tên, đo lực bằng lực kế, phân loại năng lượng "
                        "tái tạo và chuyển động Trái Đất."
                    ),
                    (
                        (
                            "Tính được trọng lượng $P = 10m$, giải thích tác dụng lực ma sát "
                            "và bảo toàn năng lượng."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-khtn-7-t1",
            "Khoa học tự nhiên",
            "7",
            "Tập một",
            96,
            [
                (
                    "Chương I–II: Nguyên tử, Bảng tuần hoàn và Phân tử – Liên kết hóa học",
                    "Bài 2–7: Nguyên tử, nguyên tố hóa học, liên kết ion, cộng hóa trị và hóa trị",
                    12,
                    45,
                    6,
                    (
                        "Mô tả mô hình nguyên tử, vị trí nguyên tố trong bảng tuần hoàn và "
                        "lập công thức hóa học theo quy tắc hóa trị."
                    ),
                    (
                        (
                            "Xác định được khối lượng nguyên tử, phân tử và lập công thức hóa "
                            "học đúng quy tắc hóa trị."
                        ),
                    ),
                ),
                (
                    "Chương III–IV: Tốc độ và Âm thanh",
                    "Bài 8–13: Tốc độ chuyển động, đồ thị quãng đường – thời gian và sóng âm",
                    46,
                    75,
                    5,
                    (
                        "Tính tốc độ $v = s/t$, vẽ đồ thị $s-t$ và phân tích biên độ, tần số, "
                        "độ cao, độ to của âm."
                    ),
                    (
                        (
                            "Vẽ và đọc được đồ thị quãng đường – thời gian; giải thích phản "
                            "xạ âm và chống ô nhiễm tiếng ồn."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-khtn-7-t2",
            "Khoa học tự nhiên",
            "7",
            "Tập hai",
            96,
            [
                (
                    "Chương V–VI: Ánh sáng và Từ",
                    "Bài 15–20: Phản xạ ánh sáng, ảnh qua gương phẳng, nam châm và từ trường",
                    6,
                    38,
                    5,
                    (
                        "Vận dụng định luật phản xạ ánh sáng dựng ảnh qua gương phẳng và khảo "
                        "sát từ phổ, nam châm điện."
                    ),
                    (
                        (
                            "Vận dụng được định luật phản xạ ánh sáng và giải thích hoạt động "
                            "của nam châm điện."
                        ),
                    ),
                ),
                (
                    "Chương VII–IX: Trao đổi chất, Cảm ứng và Sinh trưởng, Sinh sản ở sinh vật",
                    "Bài 22–38: Quang hợp, hô hấp tế bào, trao đổi nước và sinh sản ở sinh vật",
                    42,
                    88,
                    6,
                    (
                        "Trình bày phương trình chữ quang hợp, hô hấp tế bào và con đường vận "
                        "chuyển nước, muối khoáng."
                    ),
                    (
                        (
                            "Giải thích được mối liên hệ giữa quang hợp và hô hấp tế bào "
                            "trong thực tiễn trồng trọt."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-khtn-8-t1",
            "Khoa học tự nhiên",
            "8",
            "Tập một",
            104,
            [
                (
                    "Chương I: Phản ứng hóa học",
                    "Bài 1: Sử dụng một số hóa chất, thiết bị cơ bản trong phòng thí nghiệm",
                    6,
                    11,
                    2,
                    "Nhận biết dụng cụ, hóa chất và quy tắc an toàn trong phòng thí nghiệm KHTN.",
                    ("Sử dụng đúng dụng cụ đo và tuân thủ an toàn hóa chất.",),
                ),
                (
                    "Chương I: Phản ứng hóa học",
                    "Bài 2: Phản ứng hóa học",
                    12,
                    15,
                    2,
                    "Phân biệt biến đổi vật lí, biến đổi hóa học và dấu hiệu có phản ứng hóa học.",
                    ("Nêu được bản chất và dấu hiệu nhận biết phản ứng hóa học.",),
                ),
                (
                    "Chương I: Phản ứng hóa học",
                    "Bài 3: Mol và tỉ khối chất khí",
                    16,
                    19,
                    2,
                    (
                        "Khái niệm mol, khối lượng mol $M$, thể tích mol khí (24,79 L ở 25 °C, 1 "
                        "bar) và tỉ khối khí."
                    ),
                    ("Tính được số mol, khối lượng mol và tỉ khối của chất khí.",),
                ),
                (
                    "Chương I: Phản ứng hóa học",
                    "Bài 4: Dung dịch và nồng độ",
                    20,
                    24,
                    2,
                    "Khái niệm dung dịch, độ tan, nồng độ phần trăm $C\\%$ và nồng độ mol $C_M$.",
                    ("Tính được nồng độ $C\\%$, $C_M$ và pha chế dung dịch đơn giản.",),
                ),
                (
                    "Chương I: Phản ứng hóa học",
                    "Bài 5: Định luật bảo toàn khối lượng và phương trình hóa học",
                    25,
                    28,
                    2,
                    "Phát biểu định luật bảo toàn khối lượng và lập phương trình hóa học.",
                    ("Cân bằng được phương trình hóa học và vận dụng bảo toàn khối lượng.",),
                ),
                (
                    "Chương I: Phản ứng hóa học",
                    "Bài 6: Tính theo phương trình hóa học",
                    29,
                    33,
                    2,
                    (
                        "Tính lượng chất tham gia, sản phẩm theo phương trình hóa học và hiệu "
                        "suất phản ứng."
                    ),
                    ("Tính được khối lượng, thể tích chất phản ứng và hiệu suất phản ứng.",),
                ),
                (
                    "Chương I: Phản ứng hóa học",
                    "Bài 7: Tốc độ phản ứng và chất xúc tác",
                    34,
                    37,
                    2,
                    (
                        "Các yếu tố ảnh hưởng tốc độ phản ứng: nồng độ, nhiệt độ, diện tích tiếp "
                        "xúc và chất xúc tác."
                    ),
                    ("Phân tích được yếu tố làm thay đổi tốc độ phản ứng hóa học.",),
                ),
                (
                    "Chương II: Một số hợp chất thông dụng",
                    "Bài 8: Acid",
                    38,
                    42,
                    2,
                    (
                        "Khái niệm acid, tính chất hóa học của acid ($\\ce{HCl, H2SO4}$) với kim "
                        "loại và base."
                    ),
                    ("Viết được PTHH minh họa tính chất của acid.",),
                ),
                (
                    "Chương II: Một số hợp chất thông dụng",
                    "Bài 9: Base. Thang pH",
                    43,
                    47,
                    2,
                    (
                        "Khái niệm base, kiềm, thang pH ($\\text{pH} < 7$, $= 7$, $> 7$) và chất "
                        "chỉ thị màu."
                    ),
                    ("Xác định được môi trường acid, trung tính, kiềm qua thang pH.",),
                ),
                (
                    "Chương II: Một số hợp chất thông dụng",
                    "Bài 10: Oxide",
                    48,
                    51,
                    2,
                    (
                        "Phân loại oxide acid, oxide base, oxide lưỡng tính, oxide trung tính và "
                        "tính chất hóa học."
                    ),
                    ("Phân loại và viết được PTHH của oxide với nước, acid hoặc base.",),
                ),
                (
                    "Chương II: Một số hợp chất thông dụng",
                    "Bài 11: Muối",
                    52,
                    55,
                    2,
                    "Khái niệm muối, độ tan và phản ứng trao đổi giữa muối với acid, base, muối.",
                    ("Viết được PTHH của muối và nêu điều kiện phản ứng trao đổi.",),
                ),
                (
                    "Chương II: Một số hợp chất thông dụng",
                    "Bài 12: Phân bón hóa học",
                    56,
                    59,
                    2,
                    "Vai trò phân đạm, lân, kali, NPK và sử dụng phân bón hợp lí bảo vệ đất.",
                    (
                        (
                            "Nhận biết các loại phân bón hóa học thông dụng và tác dụng đối với "
                            "cây trồng."
                        ),
                    ),
                ),
                (
                    "Chương III: Khối lượng riêng và áp suất",
                    "Bài 13: Khối lượng riêng",
                    60,
                    64,
                    2,
                    (
                        "Định nghĩa khối lượng riêng $D = m/V$, đơn vị $\\text{kg/m}^3$, "
                        "$\\text{g/cm}^3$."
                    ),
                    ("Tính được khối lượng riêng của vật đồng chất.",),
                ),
                (
                    "Chương III: Khối lượng riêng và áp suất",
                    "Bài 14: Thực hành xác định khối lượng riêng",
                    65,
                    68,
                    2,
                    (
                        "Đo khối lượng và thể tích để xác định khối lượng riêng của vật rắn và "
                        "chất lỏng."
                    ),
                    ("Thực hiện được phép đo khối lượng riêng trong phòng thí nghiệm.",),
                ),
                (
                    "Chương III: Khối lượng riêng và áp suất",
                    "Bài 15: Áp suất trên một bề mặt",
                    69,
                    72,
                    2,
                    "Áp lực và công thức áp suất $p = F/S$, cách tăng giảm áp suất trong đời sống.",
                    ("Tính được áp suất lên mặt bị ép và giải thích ứng dụng thực tế.",),
                ),
                (
                    "Chương III: Khối lượng riêng và áp suất",
                    "Bài 16: Áp suất chất lỏng. Áp suất khí quyển",
                    73,
                    77,
                    2,
                    (
                        "Sự truyền áp suất trong chất lỏng và hiện tượng liên quan đến áp suất "
                        "khí quyển."
                    ),
                    ("Giải thích được nguyên lí áp suất chất lỏng và áp suất khí quyển.",),
                ),
                (
                    "Chương III: Khối lượng riêng và áp suất",
                    "Bài 17: Lực đẩy Archimedes",
                    78,
                    81,
                    2,
                    (
                        "Công thức lực đẩy Archimedes $F_A = d \\cdot V$ và điều kiện vật nổi, vật "
                        "chìm."
                    ),
                    ("Tính được lực đẩy Archimedes và giải thích sự nổi của vật.",),
                ),
                (
                    "Chương IV: Tác dụng làm quay của lực",
                    "Bài 18: Tác dụng làm quay của lực. Moment lực",
                    82,
                    85,
                    2,
                    "Tác dụng làm quay của lực quanh trục cố định và khái niệm moment lực.",
                    ("Mô tả được tác dụng làm quay phụ thuộc độ lớn lực và cánh tay đòn.",),
                ),
                (
                    "Chương IV: Tác dụng làm quay của lực",
                    "Bài 19: Đòn bẩy và ứng dụng",
                    86,
                    90,
                    2,
                    "Cấu tạo đòn bẩy, phân loại ba loại đòn bẩy và ứng dụng trong lao động.",
                    ("Vận dụng được nguyên tắc đòn bẩy giải thích công cụ thực tế.",),
                ),
            ],
        ),
        (
            "kntt-khtn-8-t2",
            "Khoa học tự nhiên",
            "8",
            "Tập hai",
            104,
            [
                (
                    "Chương V: Điện",
                    "Bài 20: Hiện tượng nhiễm điện do cọ xát",
                    6,
                    9,
                    2,
                    "Vật nhiễm điện hút vật nhẹ, hai loại điện tích dương, âm và tương tác điện.",
                    ("Giải thích được hiện tượng nhiễm điện do cọ xát.",),
                ),
                (
                    "Chương V: Điện",
                    "Bài 21: Dòng điện, nguồn điện",
                    10,
                    13,
                    2,
                    "Khái niệm dòng điện, nguồn điện, vật dẫn điện và vật cách điện.",
                    ("Phân biệt được vật dẫn điện, vật cách điện và vai trò nguồn điện.",),
                ),
                (
                    "Chương V: Điện",
                    "Bài 22: Mạch điện đơn giản",
                    14,
                    18,
                    2,
                    "Kí hiệu các bộ phận mạch điện, vẽ sơ đồ và lắp mạch điện đơn giản.",
                    ("Vẽ và mắc được mạch điện kín đơn giản theo sơ đồ.",),
                ),
                (
                    "Chương V: Điện",
                    "Bài 23: Tác dụng của dòng điện",
                    19,
                    23,
                    2,
                    "Năm tác dụng của dòng điện: nhiệt, phát sáng, hóa học, sinh lí và từ.",
                    ("Nêu được ví dụ và ứng dụng các tác dụng của dòng điện.",),
                ),
                (
                    "Chương V: Điện",
                    "Bài 24: Cường độ dòng điện và hiệu điện thế",
                    24,
                    27,
                    2,
                    "Định nghĩa cường độ dòng điện (ampe A) và hiệu điện thế (vôn V).",
                    ("Nêu được ý nghĩa cường độ dòng điện, hiệu điện thế và đơn vị đo.",),
                ),
                (
                    "Chương V: Điện",
                    "Bài 25: Thực hành đo cường độ dòng điện và hiệu điện thế",
                    28,
                    31,
                    2,
                    "Cách mắc ampe kế nối tiếp và vôn kế song song để đo trong mạch điện.",
                    ("Đo đúng cường độ dòng điện và hiệu điện thế bằng ampe kế, vôn kế.",),
                ),
                (
                    "Chương VI: Nhiệt",
                    "Bài 26: Năng lượng nhiệt và nội năng",
                    32,
                    35,
                    2,
                    "Chuyển động nhiệt phân tử, nội năng và hai cách làm biến đổi nội năng.",
                    ("Phân biệt được nhiệt năng, nội năng và cách truyền năng lượng nhiệt.",),
                ),
                (
                    "Chương VI: Nhiệt",
                    "Bài 27: Thực hành đo năng lượng nhiệt bằng joulemeter",
                    36,
                    38,
                    2,
                    "Đo năng lượng nhiệt truyền cho nước bằng joulemeter (jun kế).",
                    ("Thực hiện được thí nghiệm đo năng lượng nhiệt cung cấp cho vật.",),
                ),
                (
                    "Chương VI: Nhiệt",
                    "Bài 28: Sự truyền nhiệt",
                    39,
                    42,
                    2,
                    (
                        "Ba hình thức truyền nhiệt: dẫn nhiệt, đối lưu, bức xạ nhiệt và hiệu ứng "
                        "nhà kính."
                    ),
                    ("Giải thích được dẫn nhiệt, đối lưu, bức xạ nhiệt trong tự nhiên.",),
                ),
                (
                    "Chương VI: Nhiệt",
                    "Bài 29: Sự nở vì nhiệt",
                    43,
                    46,
                    2,
                    "Sự nở vì nhiệt của chất rắn, lỏng, khí và ứng dụng kĩ thuật.",
                    ("Giải thích được ứng dụng và phòng tránh tác hại của sự nở vì nhiệt.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 30: Khái quát về cơ thể người",
                    47,
                    49,
                    1,
                    "Các cấp độ tổ chức và sự phối hợp giữa các hệ cơ quan trong cơ thể người.",
                    ("Kể tên được các hệ cơ quan chính và chức năng cơ bản.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 31: Hệ vận động ở người",
                    50,
                    54,
                    2,
                    "Cấu tạo bộ xương, hệ cơ, tật cong vẹo cột sống và phòng tránh chấn thương.",
                    ("Nêu được vai trò hệ vận động và biện pháp giữ tư thế đúng.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 32: Dinh dưỡng và tiêu hóa ở người",
                    55,
                    59,
                    2,
                    "Quá trình tiêu hóa thức ăn ở các cơ quan và chế độ dinh dưỡng hợp lí.",
                    ("Trình bày được chức năng tiêu hóa và phòng bệnh đường tiêu hóa.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 33: Máu và hệ tuần hoàn của cơ thể người",
                    60,
                    64,
                    2,
                    "Thành phần máu, nhóm máu ABO, vòng tuần hoàn và bảo vệ tim mạch.",
                    ("Phân biệt được nhóm máu, nguyên tắc truyền máu và cấu tạo tim.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 34: Hệ hô hấp ở người",
                    65,
                    68,
                    2,
                    "Cấu tạo đường dẫn khí, phổi, cơ chế hít vào thở ra và bảo vệ hô hấp.",
                    ("Trình bày được trao đổi khí ở phổi và phòng chống tác hại thuốc lá.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 35: Hệ bài tiết ở người",
                    69,
                    72,
                    2,
                    "Cấu tạo thận, quá trình lọc máu tạo nước tiểu và phòng bệnh thận.",
                    ("Nêu được vai trò hệ bài tiết nước tiểu và thói quen bảo vệ thận.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 36: Điều hòa môi trường trong của cơ thể người",
                    73,
                    75,
                    1,
                    (
                        "Khái niệm cân bằng nội môi, vai trò duy trì ổn định đường huyết, pH, "
                        "thân nhiệt."
                    ),
                    ("Giải thích được tầm quan trọng của cân bằng môi trường trong cơ thể.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 37: Hệ thần kinh và các giác quan ở người",
                    76,
                    80,
                    2,
                    "Cấu tạo hệ thần kinh trung ương, mắt, tai và bảo vệ giác quan.",
                    ("Trình bày được cấu tạo mắt, tai và phòng tránh tật khúc xạ.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 38: Hệ nội tiết ở người",
                    81,
                    84,
                    2,
                    (
                        "Các tuyến nội tiết, hormone điều hòa cơ thể và phòng bệnh tiểu đường, "
                        "bướu cổ."
                    ),
                    ("Nêu được chức năng các tuyến nội tiết chính.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 39: Da và điều hòa thân nhiệt ở người",
                    85,
                    87,
                    1,
                    "Cấu tạo, chức năng của da và cơ chế điều hòa thân nhiệt.",
                    ("Trình bày được vai trò điều hòa thân nhiệt và chăm sóc da.",),
                ),
                (
                    "Chương VII: Sinh học cơ thể người",
                    "Bài 40: Sinh sản ở người",
                    88,
                    91,
                    2,
                    (
                        "Cơ quan sinh sản nam, nữ, quá trình thụ tinh và sức khỏe sinh sản vị "
                        "thành niên."
                    ),
                    ("Nêu được kiến thức cơ bản về sinh sản và bảo vệ sức khỏe tuổi dậy thì.",),
                ),
                (
                    "Chương VIII: Sinh vật và môi trường",
                    "Bài 41: Môi trường và các nhân tố sinh thái",
                    92,
                    94,
                    2,
                    "Bốn loại môi trường sống, nhân tố vô sinh, hữu sinh và giới hạn sinh thái.",
                    ("Phân biệt được nhân tố vô sinh, hữu sinh và giới hạn sinh thái.",),
                ),
                (
                    "Chương VIII: Sinh vật và môi trường",
                    "Bài 42: Quần thể sinh vật",
                    95,
                    96,
                    1,
                    (
                        "Các đặc trưng cơ bản của quần thể: kích thước, mật độ, tỉ lệ giới tính, "
                        "nhóm tuổi."
                    ),
                    ("Nêu được các đặc trưng và biện pháp bảo vệ quần thể sinh vật.",),
                ),
                (
                    "Chương VIII: Sinh vật và môi trường",
                    "Bài 43: Quần xã sinh vật",
                    97,
                    98,
                    1,
                    "Khái niệm quần xã, độ đa dạng và thành phần loài đặc trưng, loài ưu thế.",
                    ("Phân tích được độ đa dạng của quần xã sinh vật.",),
                ),
                (
                    "Chương VIII: Sinh vật và môi trường",
                    "Bài 44: Hệ sinh thái",
                    99,
                    100,
                    2,
                    "Thành phần hệ sinh thái, chuỗi thức ăn, lưới thức ăn và tháp sinh thái.",
                    ("Xây dựng được chuỗi thức ăn và lưới thức ăn trong hệ sinh thái.",),
                ),
                (
                    "Chương VIII: Sinh vật và môi trường",
                    "Bài 45: Sinh quyển",
                    101,
                    101,
                    1,
                    "Khái niệm sinh quyển và các khu sinh học chủ yếu trên Trái Đất.",
                    ("Nêu được khái niệm sinh quyển và đặc trưng các khu sinh học lớn.",),
                ),
                (
                    "Chương VIII: Sinh vật và môi trường",
                    "Bài 46: Cân bằng tự nhiên",
                    102,
                    102,
                    1,
                    "Khái niệm cân bằng tự nhiên và nguyên nhân gây mất cân bằng sinh thái.",
                    ("Phân tích được nguyên nhân và hậu quả mất cân bằng tự nhiên.",),
                ),
                (
                    "Chương VIII: Sinh vật và môi trường",
                    "Bài 47: Bảo vệ môi trường",
                    103,
                    104,
                    2,
                    (
                        "Tác động của con người, biến đổi khí hậu và biện pháp bảo vệ môi trường "
                        "bền vững."
                    ),
                    ("Đề xuất được biện pháp bảo vệ môi trường và ứng phó biến đổi khí hậu.",),
                ),
            ],
        ),
        (
            "kntt-khtn-9-t1",
            "Khoa học tự nhiên",
            "9",
            "Tập một",
            112,
            [
                (
                    "Chương I–II: Năng lượng cơ học và Ánh sáng",
                    "Bài 2–9: Động năng, thế năng, công, công suất, khúc xạ ánh sáng và thấu kính",
                    10,
                    49,
                    6,
                    (
                        "Tính động năng, thế năng, công suất; vận dụng định luật khúc xạ và "
                        "dựng ảnh qua thấu kính hội tụ, phân kì."
                    ),
                    ("Tính được cơ năng, công, công suất và dựng ảnh vật qua thấu kính mỏng.",),
                ),
                (
                    "Chương III–IV: Điện và Điện từ",
                    (
                        "Bài 11–16: Định luật Ôm, đoạn mạch nối tiếp – song song, năng lượng "
                        "điện và cảm ứng điện từ"
                    ),
                    52,
                    79,
                    5,
                    (
                        "Vận dụng định luật Ôm $I = U/R$, tính điện trở tương đương, công "
                        "suất điện và nguyên tắc tạo dòng điện xoay chiều."
                    ),
                    (
                        (
                            "Giải được bài toán mạch điện nối tiếp, song song và tính tiền "
                            "điện tiêu thụ."
                        ),
                    ),
                ),
                (
                    "Chương VI: Kim loại. Sự khác nhau cơ bản giữa phi kim và kim loại",
                    (
                        "Bài 18–20: Tính chất chung của kim loại, dãy hoạt động hóa học và "
                        "tách kim loại"
                    ),
                    86,
                    104,
                    4,
                    (
                        "Vận dụng dãy hoạt động hóa học dự đoán phản ứng của kim loại với "
                        "nước, acid và dung dịch muối."
                    ),
                    (
                        (
                            "Viết được phương trình phản ứng của kim loại và nêu nguyên tắc "
                            "luyện gang, thép."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-khtn-9-t2",
            "Khoa học tự nhiên",
            "9",
            "Tập hai",
            112,
            [
                (
                    (
                        "Chương VII–IX: Hợp chất hữu cơ, Hydrocarbon, Ethylic alcohol, Acetic "
                        "acid, Lipid, Carbohydrate, Protein"
                    ),
                    (
                        "Bài 22–31: Alkane, alkene, phản ứng cháy, ester hóa và ứng dụng hợp "
                        "chất hữu cơ"
                    ),
                    6,
                    54,
                    6,
                    (
                        "Viết công thức cấu tạo, tính chất hóa học đặc trưng của ethylene, "
                        "ethylic alcohol, acetic acid, glucose và tinh bột."
                    ),
                    (
                        (
                            "Viết được phương trình phản ứng đặc trưng của hydrocarbon, "
                            "alcohol, acid hữu cơ và carbohydrate."
                        ),
                    ),
                ),
                (
                    "Chương XI–XIII: Di truyền học Mendel, Cơ sở phân tử của di truyền và Tiến hóa",
                    (
                        "Bài 36–46: Quy luật phân li, DNA, RNA, đột biến gene, nguyên phân, "
                        "giảm phân và tiến hóa"
                    ),
                    62,
                    104,
                    6,
                    (
                        "Vận dụng quy luật Mendel viết sơ đồ lai; mô tả cấu trúc DNA, quá "
                        "trình tái bản, phiên mã, dịch mã."
                    ),
                    (
                        (
                            "Giải được bài tập lai một và hai cặp tính trạng; phân biệt "
                            "nguyên phân, giảm phân."
                        ),
                    ),
                ),
            ],
        ),
        # ==================== VẬT LÍ 10–12 ====================
        (
            "kntt-vat-li-10-t1",
            "Vật lí",
            "10",
            "Tập một",
            144,
            [
                (
                    "Chương II: Động học",
                    (
                        "Bài 4–10: Độ dịch chuyển, vận tốc, gia tốc, chuyển động thẳng biến "
                        "đổi đều và rơi tự do"
                    ),
                    20,
                    49,
                    6,
                    (
                        "Thiết lập đồ thị $d-t, v-t$ và các phương trình chuyển động thẳng "
                        "biến đổi đều, rơi tự do, chuyển động ném ngang."
                    ),
                    (
                        (
                            "Tính được độ dịch chuyển, vận tốc, gia tốc từ đồ thị và công "
                            "thức động học."
                        ),
                        "Giải được bài toán rơi tự do và chuyển động ném ngang.",
                    ),
                ),
                (
                    "Chương III: Động lực học",
                    (
                        "Bài 13–19: Tổng hợp lực, ba định luật Newton, trọng lực, lực ma sát "
                        "và lực cản"
                    ),
                    56,
                    81,
                    6,
                    (
                        "Vận dụng định luật II Newton $\\vec{F} = m\\vec{a}$ phân tích lực "
                        "trên mặt phẳng ngang, mặt phẳng nghiêng."
                    ),
                    ("Vận dụng được ba định luật Newton giải bài toán động lực học chất điểm.",),
                ),
                (
                    "Chương IV–V: Năng lượng, Công, Công suất và Động lượng",
                    (
                        "Bài 23–29: Công cơ học, động năng, thế năng, định luật bảo toàn cơ "
                        "năng và bảo toàn động lượng"
                    ),
                    90,
                    118,
                    6,
                    (
                        "Áp dụng định luật bảo toàn cơ năng và bảo toàn động lượng giải bài "
                        "toán va chạm đàn hồi, va chạm mềm."
                    ),
                    (
                        (
                            "Vận dụng được định luật bảo toàn cơ năng và bảo toàn động lượng "
                            "vào bài toán va chạm."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-vat-li-10-cd",
            "Vật lí",
            "10",
            "Chuyên đề học tập",
            72,
            [
                (
                    "Chuyên đề 1–2: Vật lí trong một số ngành nghề và Trái Đất – Bầu trời",
                    "Ứng dụng vật lí hiện đại và mô hình chuyển động biểu kiến của thiên thể",
                    5,
                    42,
                    5,
                    (
                        "Khảo sát vai trò vật lí trong kĩ thuật y sinh, năng lượng và quy "
                        "luật chuyển động nhìn thấy của Mặt Trời, Mặt Trăng."
                    ),
                    (
                        (
                            "Giải thích được hiện tượng tuần trăng, nhật thực, nguyệt thực và "
                            "ứng dụng vật lí kĩ thuật."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-vat-li-11-t1",
            "Vật lí",
            "11",
            "Tập một",
            120,
            [
                (
                    "Chương I: Dao động",
                    "Bài 1–6: Dao động điều hòa, năng lượng dao động, con lắc và cộng hưởng",
                    6,
                    31,
                    6,
                    (
                        "Viết phương trình li độ, vận tốc, gia tốc $x = A\\cos(\\omega t + "
                        "\\varphi)$ và tính cơ năng dao động điều hòa."
                    ),
                    (
                        (
                            "Xác định được biên độ, chu kì, tần số, pha và năng lượng của dao "
                            "động điều hòa."
                        ),
                    ),
                ),
                (
                    "Chương II: Sóng",
                    "Bài 8–13: Sóng cơ, sóng điện từ, giao thoa ánh sáng và sóng dừng",
                    34,
                    57,
                    6,
                    (
                        "Tính bước sóng $\\lambda = vT$, khoảng vân giao thoa $i = \\lambda D "
                        "/ a$ và điều kiện sóng dừng trên dây."
                    ),
                    ("Giải được bài toán giao thoa sóng, giao thoa khe Young và sóng dừng.",),
                ),
                (
                    "Chương III–IV: Điện trường và Dòng điện – Mạch điện",
                    (
                        "Bài 16–25: Lực Coulomb, điện trường, tụ điện, định luật Ôm toàn mạch "
                        "và công suất điện"
                    ),
                    62,
                    108,
                    7,
                    (
                        "Tính lực tương tác điện, cường độ điện trường, điện dung tụ điện, "
                        "suất điện động và điện trở trong nguồn điện."
                    ),
                    (
                        (
                            "Vận dụng được định luật Coulomb và định luật Ôm cho toàn mạch "
                            "tính hiệu suất nguồn."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-vat-li-11-cd",
            "Vật lí",
            "11",
            "Chuyên đề học tập",
            72,
            [
                (
                    "Chuyên đề 1–2: Trường hấp dẫn và Truyền thông tin bằng sóng vô tuyến",
                    "Cường độ trường hấp dẫn, thế hấp dẫn và điều chế tín hiệu AM, FM",
                    5,
                    48,
                    5,
                    (
                        "Tính lực hấp dẫn, tốc độ vũ trụ cấp I và phân biệt nguyên lí điều "
                        "chế biên độ AM, tần số FM."
                    ),
                    (
                        (
                            "Vận dụng được công thức trường hấp dẫn và giải thích sơ đồ khối "
                            "hệ thống truyền thông vô tuyến."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-vat-li-12-t1",
            "Vật lí",
            "12",
            "Tập một",
            128,
            [
                (
                    "Chương I: Vật lí nhiệt",
                    (
                        "Bài 1–6: Mô hình động học phân tử, nội năng, định luật I nhiệt động "
                        "lực học và nhiệt dung riêng"
                    ),
                    6,
                    31,
                    6,
                    (
                        "Tính nhiệt lượng trao đổi $Q = mc\\Delta T$, nhiệt nóng chảy, nhiệt "
                        "hóa hơi và vận dụng $\\Delta U = A + Q$."
                    ),
                    (
                        (
                            "Vận dụng được định luật I nhiệt động lực học và công thức nhiệt "
                            "lượng giải bài toán cân bằng nhiệt."
                        ),
                    ),
                ),
                (
                    "Chương II: Khí lí tưởng",
                    (
                        "Bài 8–12: Định luật Boyle, Charles, phương trình trạng thái khí lí "
                        "tưởng và áp suất khí theo mô hình động học"
                    ),
                    34,
                    55,
                    6,
                    (
                        "Vận dụng phương trình $pV = nRT$ giải bài toán các đẳng quá trình và "
                        "tính động năng tịnh tiến trung bình."
                    ),
                    (
                        (
                            "Giải được bài toán đẳng nhiệt, đẳng áp, phương trình trạng thái "
                            "khí lí tưởng."
                        ),
                    ),
                ),
                (
                    "Chương III: Từ trường",
                    (
                        "Bài 14–18: Cảm ứng từ, lực từ, cảm ứng điện từ và máy biến áp, điện "
                        "xoay chiều"
                    ),
                    58,
                    87,
                    6,
                    (
                        "Tính lực từ $F = BIL\\sin\\alpha$, suất điện động cảm ứng theo "
                        "Faraday và giá trị hiệu dụng dòng xoay chiều."
                    ),
                    ("Vận dụng được định luật Faraday, quy tắc Lenz và công thức máy biến áp.",),
                ),
                (
                    "Chương IV: Vật lí hạt nhân",
                    (
                        "Bài 21–24: Cấu trúc hạt nhân, độ hụt khối, năng lượng liên kết, phản "
                        "ứng hạt nhân và phóng xạ"
                    ),
                    90,
                    116,
                    6,
                    (
                        "Tính năng lượng liên kết riêng, năng lượng tỏa/thu phản ứng hạt nhân "
                        "và định luật phóng xạ $N = N_0 2^{-t/T}$."
                    ),
                    ("Tính được độ hụt khối, năng lượng phản ứng hạt nhân và chu kì bán rã.",),
                ),
            ],
        ),
        (
            "kntt-vat-li-12-cd",
            "Vật lí",
            "12",
            "Chuyên đề học tập",
            72,
            [
                (
                    "Chuyên đề 1–2: Dòng điện xoay chiều và Ứng dụng vật lí trong chẩn đoán y học",
                    "Mạch RLC nối tiếp, chỉnh lưu dòng xoay chiều và nguyên lí tia X, siêu âm, MRI",
                    5,
                    52,
                    5,
                    (
                        "Phân tích tổng trở, cộng hưởng điện trong mạch RLC và nguyên lí tạo "
                        "ảnh y học bằng tia X, siêu âm."
                    ),
                    (
                        (
                            "Tính được các đại lượng trong mạch RLC và giải thích nguyên lí "
                            "chẩn đoán hình ảnh y học."
                        ),
                    ),
                ),
            ],
        ),
        # ==================== HOÁ HỌC 10–12 ====================
        (
            "kntt-hoa-hoc-10-t1",
            "Hoá học",
            "10",
            "Tập một",
            128,
            [
                (
                    "Chương I–II: Cấu tạo nguyên tử và Bảng tuần hoàn các nguyên tố hóa học",
                    "Bài 2–8: Đồng vị, cấu hình electron nguyên tử và quy luật biến đổi tuần hoàn",
                    12,
                    47,
                    6,
                    (
                        "Viết cấu hình electron theo phân lớp, tính nguyên tử khối trung bình "
                        "và so sánh bán kính, độ âm điện, tính kim loại – phi kim."
                    ),
                    (
                        (
                            "Viết được cấu hình electron và dự đoán tính chất nguyên tố từ vị "
                            "trí trong bảng tuần hoàn."
                        ),
                    ),
                ),
                (
                    "Chương III–IV: Liên kết hóa học và Phản ứng oxi hóa – khử",
                    (
                        "Bài 10–15: Liên kết ion, cộng hóa trị, liên kết hydrogen và cân bằng "
                        "phản ứng oxi hóa – khử"
                    ),
                    52,
                    79,
                    6,
                    (
                        "Xác định số oxi hóa, chất khử, chất oxi hóa và cân bằng phương trình "
                        "theo phương pháp thăng bằng electron."
                    ),
                    (
                        (
                            "Lập được phương trình hóa học của phản ứng oxi hóa – khử bằng "
                            "thăng bằng electron."
                        ),
                    ),
                ),
                (
                    "Chương V–VII: Năng lượng hóa học, Tốc độ phản ứng và Nguyên tố nhóm VIIA",
                    (
                        "Bài 17–23: Biến thiên enthalpy, định luật tác dụng khối lượng và "
                        "tính chất halogen"
                    ),
                    82,
                    118,
                    6,
                    (
                        "Tính biến thiên enthalpy chuẩn $\\Delta_r H^\\circ_{298}$ theo nhiệt "
                        "tạo thành, năng lượng liên kết và tính chất dãy halogen."
                    ),
                    (
                        (
                            "Tính được biến thiên enthalpy phản ứng và giải thích quy luật "
                            "biến đổi tính oxi hóa của halogen."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-hoa-hoc-10-cd",
            "Hoá học",
            "10",
            "Chuyên đề học tập",
            64,
            [
                (
                    "Chuyên đề 1–2: Cơ sở hóa học và Hóa học trong việc phòng chống cháy nổ",
                    "Cấu trúc hình học phân tử VSEPR và nguyên tắc dập tắt đám cháy",
                    5,
                    44,
                    5,
                    (
                        "Dự đoán dạng hình học phân tử đơn giản và vận dụng kiến thức phản "
                        "ứng cháy trong an toàn phòng cháy chữa cháy."
                    ),
                    (
                        (
                            "Giải thích được điều kiện phát sinh cháy nổ và lựa chọn phương "
                            "tiện chữa cháy phù hợp."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-hoa-hoc-11-t1",
            "Hoá học",
            "11",
            "Tập một",
            156,
            [
                (
                    "Chương I: Cân bằng hóa học",
                    (
                        "Bài 1–3: Cân bằng hóa học, nguyên lí Le Chatelier, thuyết "
                        "Brønsted–Lowry và pH"
                    ),
                    6,
                    25,
                    6,
                    (
                        "Viết biểu thức hằng số cân bằng $K_C$, dự đoán chuyển dịch cân bằng "
                        "và tính pH dung dịch acid, base mạnh, chuẩn độ."
                    ),
                    (
                        (
                            "Vận dụng nguyên lí Le Chatelier và tính pH trong bài toán chuẩn "
                            "độ acid – base."
                        ),
                    ),
                ),
                (
                    "Chương II: Nitrogen – Sulfur",
                    (
                        "Bài 4–8: Ammonia, muối ammonium, nitric acid, hiện tượng phú dưỡng "
                        "và sulfuric acid"
                    ),
                    26,
                    53,
                    5,
                    (
                        "Phân tích tính chất hóa học của $\\ce{NH3}$, $\\ce{HNO3}$, "
                        "$\\ce{SO2}$, $\\ce{H2SO4}$ loãng và đặc."
                    ),
                    (
                        (
                            "Viết được phương trình hóa học của hợp chất nitrogen, sulfur và "
                            "giải thích mưa acid."
                        ),
                    ),
                ),
                (
                    (
                        "Chương IV–VI: Hydrocarbon, Dẫn xuất halogen – Alcohol – Phenol và "
                        "Hợp chất carbonyl – Carboxylic acid"
                    ),
                    (
                        "Bài 15–24: Alkane, alkene, alkyne, arene, alcohol, phenol, aldehyde "
                        "và carboxylic acid"
                    ),
                    82,
                    148,
                    7,
                    (
                        "Gọi tên thay thế IUPAC, viết đồng phân và phản ứng đặc trưng của các "
                        "nhóm chức hữu cơ quan trọng."
                    ),
                    (
                        (
                            "Gọi đúng tên IUPAC và viết phương trình phản ứng nhận biết, điều "
                            "chế các hợp chất hữu cơ lớp 11."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-hoa-hoc-11-cd",
            "Hoá học",
            "11",
            "Chuyên đề học tập",
            68,
            [
                (
                    "Chuyên đề 1–2: Phân bón và Trải nghiệm thực hành hóa học hữu cơ",
                    "Phân bón vô cơ, hữu cơ và quy trình tách tinh dầu, điều chế xà phòng",
                    5,
                    48,
                    5,
                    (
                        "Đánh giá hàm lượng dinh dưỡng phân đạm, lân, kali và thực hành chiết "
                        "xuất tinh dầu từ nguồn thảo mộc."
                    ),
                    (
                        (
                            "Tính được độ dinh dưỡng của phân bón và giải thích nguyên tắc sử "
                            "dụng phân bón hợp lí."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-hoa-hoc-12-t1",
            "Hoá học",
            "12",
            "Tập một",
            152,
            [
                (
                    "Chương I–II: Ester – Lipid và Carbohydrate",
                    (
                        "Bài 1–6: Ester, chất béo, xà phòng, glucose, saccharose, tinh bột và "
                        "cellulose"
                    ),
                    6,
                    35,
                    6,
                    (
                        "Phân tích phản ứng thủy phân ester trong môi trường acid, kiềm (xà "
                        "phòng hóa) và tính chất carbohydrate."
                    ),
                    (
                        (
                            "Viết được phương trình phản ứng xà phòng hóa và phân biệt các "
                            "carbohydrate tiêu biểu."
                        ),
                    ),
                ),
                (
                    "Chương III–IV: Hợp chất chứa nitrogen và Polymer",
                    "Bài 8–13: Amine, amino acid, peptide, protein và vật liệu polymer",
                    38,
                    67,
                    6,
                    (
                        "Tính lưỡng tính của amino acid, phản ứng màu biuret của peptide và "
                        "phản ứng trùng hợp, trùng ngưng tạo polymer."
                    ),
                    ("Giải được bài toán thủy phân peptide và phân loại chất dẻo, tơ, cao su.",),
                ),
                (
                    (
                        "Chương V–VIII: Pin điện và điện phân, Đại cương kim loại, Nhóm "
                        "IA–IIA và Kim loại chuyển tiếp"
                    ),
                    (
                        "Bài 15–29: Thế điện cực chuẩn, sức điện động pin Galvani, điện phân, "
                        "ăn mòn kim loại và phức chất"
                    ),
                    72,
                    142,
                    7,
                    (
                        "Tính sức điện động chuẩn $E^\\circ_{\\text{pin}}$, viết quá trình ở "
                        "các điện cực khi điện phân và tính chất kim loại kiềm, kiềm thổ."
                    ),
                    (
                        (
                            "Vận dụng bảng thế điện cực chuẩn dự đoán chiều phản ứng và tính "
                            "lượng chất sinh ra khi điện phân."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-hoa-hoc-12-cd",
            "Hoá học",
            "12",
            "Chuyên đề học tập",
            68,
            [
                (
                    "Chuyên đề 1–2: Cơ chế phản ứng hữu cơ và Trải nghiệm thực hành hóa học vô cơ",
                    "Phản ứng thế gốc tự do, cộng electrophile và tái chế kim loại",
                    5,
                    48,
                    5,
                    (
                        "Mô tả cơ chế phản ứng cơ bản của hydrocarbon và quy trình xử lí nước "
                        "cứng, bảo vệ môi trường."
                    ),
                    (
                        (
                            "Giải thích được quy tắc Markovnikov theo cơ chế phản ứng cộng "
                            "electrophile."
                        ),
                    ),
                ),
            ],
        ),
        # ==================== SINH HỌC 10–12 ====================
        (
            "kntt-sinh-hoc-10-t1",
            "Sinh học",
            "10",
            "Tập một",
            148,
            [
                (
                    "Phần 1: Sinh học tế bào",
                    (
                        "Bài 5–14: Các phân tử sinh học, cấu trúc tế bào, trao đổi chất qua "
                        "màng và chuyển hóa năng lượng"
                    ),
                    26,
                    71,
                    6,
                    (
                        "Phân tích cấu trúc carbohydrate, lipid, protein, nucleic acid; vận "
                        "chuyển thụ động, chủ động, quang hợp và hô hấp tế bào."
                    ),
                    (
                        (
                            "Phân biệt được cấu trúc tế bào nhân sơ, nhân thực và cơ chế thẩm "
                            "thấu qua màng sinh chất."
                        ),
                        (
                            "Giải thích được vai trò của enzyme, ATP trong chuyển hóa năng "
                            "lượng tế bào."
                        ),
                    ),
                ),
                (
                    "Phần 1: Chu kì tế bào và phân bào",
                    "Bài 16–18: Chu kì tế bào, nguyên phân, giảm phân và công nghệ tế bào",
                    78,
                    95,
                    5,
                    (
                        "Trình bày diễn biến nhiễm sắc thể trong nguyên phân, giảm phân và cơ "
                        "sở kiểm soát ung thư."
                    ),
                    ("So sánh được kết quả và ý nghĩa sinh học của nguyên phân và giảm phân.",),
                ),
                (
                    "Phần 2: Sinh học vi sinh vật và virus",
                    (
                        "Bài 20–29: Dinh dưỡng, sinh trưởng vi sinh vật, ứng dụng lên men và "
                        "cấu tạo, nhân lên của virus"
                    ),
                    98,
                    142,
                    5,
                    (
                        "Phân tích các pha sinh trưởng của quần thể vi khuẩn, ứng dụng công "
                        "nghệ vi sinh và cơ chế phòng chống bệnh do virus."
                    ),
                    (
                        (
                            "Trình bày được chu trình nhân lên của virus và ứng dụng vi sinh "
                            "vật trong đời sống."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-sinh-hoc-10-cd",
            "Sinh học",
            "10",
            "Chuyên đề học tập",
            72,
            [
                (
                    "Chuyên đề 1–2: Công nghệ tế bào và Công nghệ enzyme",
                    "Nuôi cấy mô tế bào thực vật, tế bào gốc và ứng dụng enzyme trong công nghiệp",
                    5,
                    48,
                    5,
                    (
                        "Tìm hiểu quy trình nhân giống vô tính bằng nuôi cấy mô và ứng dụng "
                        "enzyme cố định trong chế biến thực phẩm."
                    ),
                    ("Trình bày được thành tựu của công nghệ tế bào gốc và công nghệ enzyme.",),
                ),
            ],
        ),
        (
            "kntt-sinh-hoc-11-t1",
            "Sinh học",
            "11",
            "Tập một",
            172,
            [
                (
                    "Chương 1: Trao đổi chất và chuyển hóa năng lượng ở sinh vật",
                    (
                        "Bài 2–13: Trao đổi nước, dinh dưỡng khoáng, quang hợp ở thực vật và "
                        "tiêu hóa, hô hấp, tuần hoàn, miễn dịch ở động vật"
                    ),
                    12,
                    87,
                    7,
                    (
                        "So sánh quang hợp ở thực vật C3, C4, CAM; cơ chế tuần hoàn máu, điều "
                        "hòa huyết áp và miễn dịch đặc hiệu, không đặc hiệu."
                    ),
                    (
                        (
                            "Phân tích được các nhân tố ảnh hưởng quang hợp và cơ chế miễn "
                            "dịch ở người."
                        ),
                    ),
                ),
                (
                    "Chương 2–4: Cảm ứng, Sinh trưởng – Phát triển và Sinh sản ở sinh vật",
                    (
                        "Bài 15–27: Hướng động, cung phản xạ, hormone thực vật – động vật và "
                        "cơ chế điều hòa sinh sản"
                    ),
                    92,
                    164,
                    6,
                    (
                        "Trình bày cơ chế dẫn truyền xung thần kinh qua synapse, vai trò "
                        "hormone sinh trưởng và ứng dụng điều khiển sinh sản."
                    ),
                    ("Giải thích được cơ chế hoạt động của cung phản xạ và vai trò của hormone.",),
                ),
            ],
        ),
        (
            "kntt-sinh-hoc-11-cd",
            "Sinh học",
            "11",
            "Chuyên đề học tập",
            72,
            [
                (
                    (
                        "Chuyên đề 1–2: Dinh dưỡng khoáng – Tăng năng suất cây trồng và Một "
                        "số bệnh dịch ở người"
                    ),
                    "Thủy canh, khí canh và nguyên nhân, biện pháp phòng chống bệnh truyền nhiễm",
                    5,
                    50,
                    5,
                    (
                        "Vận dụng kiến thức dinh dưỡng khoáng thiết kế mô hình trồng cây sạch "
                        "và phân tích dịch tễ học cơ bản."
                    ),
                    ("Đề xuất được biện pháp bón phân hợp lí và phòng chống bệnh truyền nhiễm.",),
                ),
            ],
        ),
        (
            "kntt-sinh-hoc-12-t1",
            "Sinh học",
            "12",
            "Tập một",
            168,
            [
                (
                    "Phần 4: Di truyền học",
                    (
                        "Bài 1–13: DNA, phiên mã, dịch mã, điều hòa biểu hiện gene (operon "
                        "Lac), đột biến, quy luật Mendel, liên kết gene và di truyền quần thể"
                    ),
                    6,
                    79,
                    7,
                    (
                        "Phân tích cơ chế di truyền phân tử, quy luật di truyền Mendel, hoán "
                        "vị gene, liên kết giới tính và định luật Hardy–Weinberg."
                    ),
                    (
                        (
                            "Giải được bài toán phiên mã, dịch mã, quy luật di truyền và cấu "
                            "trúc di truyền quần thể."
                        ),
                    ),
                ),
                (
                    "Phần 5–6: Tiến hóa và Sinh thái học",
                    (
                        "Bài 16–29: Bằng chứng tiến hóa, học thuyết tiến hóa tổng hợp, quần "
                        "thể, quần xã, hệ sinh thái và sinh quyển"
                    ),
                    88,
                    160,
                    6,
                    (
                        "Phân tích các nhân tố tiến hóa, cơ chế hình thành loài, diễn thế "
                        "sinh thái, dòng năng lượng và chu trình sinh địa hóa."
                    ),
                    (
                        (
                            "Giải thích được vai trò chọn lọc tự nhiên và đề xuất giải pháp "
                            "bảo tồn hệ sinh thái."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-sinh-hoc-12-cd",
            "Sinh học",
            "12",
            "Chuyên đề học tập",
            72,
            [
                (
                    "Chuyên đề 1–2: Sinh học phân tử và Kiểm soát sinh học",
                    "Kĩ thuật PCR, điện di DNA, liệu pháp gene và thiên địch kiểm soát sâu hại",
                    5,
                    50,
                    5,
                    (
                        "Tìm hiểu nguyên lí nhân bản DNA bằng PCR và ứng dụng thiên địch "
                        "trong nông nghiệp bền vững."
                    ),
                    ("Trình bày được nguyên lí kĩ thuật PCR và ưu điểm của kiểm soát sinh học.",),
                ),
            ],
        ),
        # ==================== TIN HỌC 10–12 ====================
        (
            "kntt-tin-hoc-10-t1",
            "Tin học",
            "10",
            "Tập một",
            168,
            [
                (
                    "Chủ đề 1–2: Máy tính và xã hội tri thức – Mạng máy tính và Internet",
                    (
                        "Bài 1–9: Biểu diễn dữ liệu nhị phân, đơn vị đo thông tin, Internet "
                        "và an toàn không gian mạng"
                    ),
                    5,
                    51,
                    5,
                    (
                        "Chuyển đổi hệ đếm nhị phân – thập phân, mã hóa văn bản Unicode và "
                        "phòng tránh phần mềm độc hại."
                    ),
                    (
                        (
                            "Biểu diễn được số nguyên, văn bản trong hệ nhị phân và nhận biết "
                            "nguy cơ an toàn mạng."
                        ),
                    ),
                ),
                (
                    "Chủ đề 5: Giải quyết vấn đề với sự trợ giúp của máy tính (Python)",
                    (
                        "Bài 16–28: Biến, câu lệnh rẽ nhánh if, vòng lặp for/while, danh "
                        "sách, xâu kí tự và hàm trong Python"
                    ),
                    82,
                    143,
                    7,
                    (
                        "Viết và gỡ lỗi chương trình Python sử dụng cấu trúc rẽ nhánh, lặp, "
                        "kiểu list, string và định nghĩa hàm."
                    ),
                    (
                        (
                            "Viết được chương trình Python giải bài toán xử lí số, xâu kí tự "
                            "và danh sách."
                        ),
                        "Tổ chức được chương trình theo hàm và phát hiện lỗi cú pháp, lỗi logic.",
                    ),
                ),
            ],
        ),
        (
            "kntt-tin-hoc-10-cd",
            "Tin học",
            "10",
            "Chuyên đề học tập",
            76,
            [
                (
                    (
                        "Chuyên đề 1–2: Thực hành làm việc với tệp văn bản, bảng tính và phần "
                        "mềm trình chiếu"
                    ),
                    "Tự động hóa mục lục, trộn thư và phân tích dữ liệu bảng tính nâng cao",
                    5,
                    52,
                    5,
                    (
                        "Thiết lập kiểu định dạng tự động, hàm tra cứu và trình bày báo cáo "
                        "số chuyên nghiệp."
                    ),
                    (
                        (
                            "Vận dụng được các tính năng nâng cao của bộ công cụ văn phòng "
                            "trong học tập."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tin-hoc-11-t1",
            "Tin học",
            "11",
            "Tập một",
            156,
            [
                (
                    "Chủ đề 1–2: Hệ điều hành, phần mềm nguồn mở và tổ chức lưu trữ, tìm kiếm",
                    (
                        "Bài 1–8: Hệ điều hành, phần mềm thương mại – nguồn mở và cấu tạo bên "
                        "trong máy tính"
                    ),
                    5,
                    41,
                    4,
                    (
                        "Phân biệt vai trò hệ điều hành, cổng logic cơ bản AND/OR/NOT và tổ "
                        "chức dữ liệu an toàn."
                    ),
                    ("Giải thích được chức năng hệ điều hành và hoạt động cơ bản của CPU, RAM.",),
                ),
                (
                    "Chủ đề 4: Giới thiệu các hệ cơ sở dữ liệu",
                    "Bài 10–15: Cơ sở dữ liệu quan hệ, khóa chính, khóa ngoài và truy vấn SQL",
                    48,
                    79,
                    6,
                    (
                        "Thiết kế bảng dữ liệu chuẩn hóa, xác định khóa chính, khóa ngoài và "
                        "viết câu lệnh SELECT, JOIN, WHERE."
                    ),
                    ("Thiết kế được bảng cơ sở dữ liệu quan hệ và viết truy vấn SQL cơ bản.",),
                ),
                (
                    "Chủ đề 6 (CS): Kĩ thuật lập trình và Thuật toán",
                    "Bài 17–26: Mảng hai chiều, tìm kiếm nhị phân, sắp xếp và đệ quy",
                    88,
                    146,
                    6,
                    (
                        "Cài đặt thuật toán tìm kiếm tuần tự, tìm kiếm nhị phân, sắp xếp "
                        "chọn/chèn và đánh giá độ phức tạp thời gian."
                    ),
                    (
                        (
                            "Cài đặt được thuật toán tìm kiếm nhị phân, sắp xếp cơ bản và ước "
                            "lượng độ phức tạp."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tin-hoc-11-cd",
            "Tin học",
            "11",
            "Chuyên đề học tập",
            76,
            [
                (
                    (
                        "Chuyên đề 1: Thực hành thiết kế thuật toán theo kĩ thuật đệ quy và "
                        "chia để trị"
                    ),
                    "Đệ quy, quay lui cơ bản và thuật toán sắp xếp nhanh, sắp xếp trộn",
                    5,
                    46,
                    5,
                    (
                        "Phân tích bài toán thành bài toán con và cài đặt thuật toán chia để "
                        "trị bằng Python."
                    ),
                    ("Vận dụng được kĩ thuật đệ quy và chia để trị giải quyết bài toán tin học.",),
                ),
            ],
        ),
        (
            "kntt-tin-hoc-12-t1",
            "Tin học",
            "12",
            "Tập một",
            160,
            [
                (
                    "Chủ đề 1–2: Máy tính và xã hội tri thức (AI) – Mạng máy tính và Internet",
                    (
                        "Bài 1–5: Trí tuệ nhân tạo, thiết bị mạng, giao thức TCP/IP và chia "
                        "sẻ tài nguyên mạng"
                    ),
                    5,
                    31,
                    5,
                    (
                        "Phân biệt AI hẹp/tổng quát, vai trò router, switch, giao thức IP, "
                        "TCP, DNS và đạo đức ứng dụng AI."
                    ),
                    (
                        (
                            "Giải thích được đặc trưng hệ thống AI và vai trò các giao thức "
                            "mạng TCP/IP."
                        ),
                    ),
                ),
                (
                    "Chủ đề 4: Giải quyết vấn đề với sự trợ giúp của máy tính (HTML & CSS)",
                    (
                        "Bài 7–18: Cấu trúc trang HTML, danh sách, bảng, biểu mẫu, bộ chọn "
                        "CSS và bố cục hộp"
                    ),
                    38,
                    103,
                    7,
                    (
                        "Xây dựng trang web ngữ nghĩa với HTML5, tạo form nhập liệu và định "
                        "kiểu bố cục bằng CSS."
                    ),
                    (
                        (
                            "Tạo được trang web hoàn chỉnh dùng thẻ HTML ngữ nghĩa, biểu mẫu "
                            "và bộ chọn CSS."
                        ),
                    ),
                ),
                (
                    "Chủ đề 6 (CS): Học máy và Khoa học dữ liệu",
                    "Bài 23–28: Học có giám sát, phân lớp, hồi quy và mô phỏng dữ liệu",
                    118,
                    152,
                    5,
                    (
                        "Giới thiệu quy trình khoa học dữ liệu, phân biệt học có giám sát và "
                        "không giám sát."
                    ),
                    (
                        (
                            "Nêu được các bước cơ bản của bài toán học máy có giám sát và "
                            "đánh giá mô hình."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-tin-hoc-12-cd",
            "Tin học",
            "12",
            "Chuyên đề học tập",
            76,
            [
                (
                    (
                        "Chuyên đề 1–2: Thực hành thiết kế thuật toán duyệt đồ thị và cấu "
                        "trúc dữ liệu cây"
                    ),
                    "Ngăn xếp, hàng đợi, tìm kiếm theo chiều sâu DFS và chiều rộng BFS",
                    5,
                    50,
                    5,
                    (
                        "Cài đặt stack, queue, biểu diễn đồ thị bằng danh sách kề và duyệt đồ "
                        "thị DFS, BFS."
                    ),
                    (
                        (
                            "Vận dụng được DFS, BFS giải bài toán tìm đường đi và thành phần "
                            "liên thông."
                        ),
                    ),
                ),
            ],
        ),
        # ==================== LỊCH SỬ VÀ ĐỊA LÍ 4–9 ====================
        (
            "kntt-lsdl-4-t1",
            "Lịch sử và Địa lí",
            "4",
            "Tập một",
            64,
            [
                (
                    (
                        "Chủ đề 1–2: Làm quen phương tiện học tập và Địa phương em – Trung "
                        "du, miền núi Bắc Bộ"
                    ),
                    "Bài 1–8: Bản đồ, thiên nhiên, dân cư và Đền Hùng – lễ giỗ Tổ Hùng Vương",
                    6,
                    38,
                    5,
                    (
                        "Đọc kí hiệu bản đồ, mô tả đặc điểm thiên nhiên, văn hóa vùng Trung "
                        "du và miền núi Bắc Bộ."
                    ),
                    (
                        (
                            "Sử dụng được bản đồ xác định vị trí địa lí và nêu nét văn hóa "
                            "tiêu biểu vùng Bắc Bộ."
                        ),
                    ),
                ),
                (
                    "Chủ đề 3: Đồng bằng Bắc Bộ",
                    "Bài 10–14: Thiên nhiên, Thăng Long – Hà Nội và Văn Miếu – Quốc Tử Giám",
                    40,
                    62,
                    4,
                    (
                        "Tìm hiểu địa hình châu thổ sông Hồng, lịch sử Thăng Long và truyền "
                        "thống hiếu học."
                    ),
                    (
                        (
                            "Trình bày được đặc điểm tự nhiên Đồng bằng Bắc Bộ và giá trị di "
                            "tích lịch sử Hà Nội."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-4-t2",
            "Lịch sử và Địa lí",
            "4",
            "Tập hai",
            64,
            [
                (
                    "Chủ đề 4–6: Duyên hải miền Trung, Tây Nguyên và Nam Bộ",
                    (
                        "Bài 15–28: Cố đô Huế, phố cổ Hội An, không gian văn hóa Cồng chiêng "
                        "và Địa đạo Củ Chi"
                    ),
                    6,
                    60,
                    6,
                    (
                        "Khám phá đặc điểm tự nhiên, hoạt động kinh tế và di sản lịch sử các "
                        "vùng miền Trung, Tây Nguyên, Nam Bộ."
                    ),
                    (
                        (
                            "Mô tả được nét đặc trưng tự nhiên, dân cư và di sản văn hóa tiêu "
                            "biểu ba vùng miền."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-5-t1",
            "Lịch sử và Địa lí",
            "5",
            "Tập một",
            64,
            [
                (
                    (
                        "Chủ đề 1–2: Đất nước và con người Việt Nam – Những quốc gia đầu tiên "
                        "trên lãnh thổ"
                    ),
                    "Bài 1–9: Vị trí địa lí, vùng biển đảo, Văn Lang – Âu Lạc, Phù Nam và Chăm-pa",
                    6,
                    42,
                    5,
                    (
                        "Xác định vị trí địa lí, chủ quyền biển đảo và tìm hiểu các nhà nước "
                        "cổ đại trên lãnh thổ Việt Nam."
                    ),
                    (
                        (
                            "Xác định được vị trí địa lí Việt Nam, hai quần đảo Hoàng Sa, "
                            "Trường Sa và nét chính Văn Lang – Âu Lạc."
                        ),
                    ),
                ),
                (
                    "Chủ đề 3: Xây dựng và bảo vệ đất nước Việt Nam",
                    "Bài 10–14: Triều Lý, Triều Trần, khởi nghĩa Lam Sơn và Triều Hậu Lê",
                    44,
                    62,
                    4,
                    (
                        "Tìm hiểu công cuộc định đô Thăng Long, ba lần kháng chiến chống Mông "
                        "– Nguyên và thắng lợi Lam Sơn."
                    ),
                    ("Kể được những sự kiện và nhân vật lịch sử tiêu biểu thời Lý, Trần, Hậu Lê.",),
                ),
            ],
        ),
        (
            "kntt-lsdl-5-t2",
            "Lịch sử và Địa lí",
            "5",
            "Tập hai",
            64,
            [
                (
                    (
                        "Chủ đề 3–6: Việt Nam hiện đại, Các nước láng giềng và Các châu lục "
                        "trên thế giới"
                    ),
                    (
                        "Bài 15–28: Cách mạng tháng Tám 1945, Chiến dịch Điện Biên Phủ, Đại "
                        "thắng mùa Xuân 1975 và các châu lục"
                    ),
                    6,
                    60,
                    6,
                    (
                        "Tìm hiểu các mốc son lịch sử hiện đại Việt Nam và vị trí, tự nhiên "
                        "năm châu lục, đại dương."
                    ),
                    (
                        (
                            "Nêu được ý nghĩa các mốc lịch sử 1945, 1954, 1975 và xác định "
                            "các châu lục trên bản đồ thế giới."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-6-t1",
            "Lịch sử và Địa lí",
            "6",
            "Tập một",
            96,
            [
                (
                    "Lịch sử 6 – Chương 1–3: Thời nguyên thủy và Xã hội cổ đại",
                    (
                        "Bài 1–10: Nguồn gốc loài người, Ai Cập, Lưỡng Hà, Ấn Độ, Trung Quốc "
                        "và Hy Lạp – La Mã cổ đại"
                    ),
                    8,
                    48,
                    6,
                    (
                        "Khảo sát cách tính thời gian trong lịch sử và thành tựu văn minh "
                        "phương Đông, phương Tây cổ đại."
                    ),
                    (
                        (
                            "Nêu được thành tựu văn minh tiêu biểu của các quốc gia cổ đại "
                            "phương Đông và phương Tây."
                        ),
                    ),
                ),
                (
                    "Địa lí 6 – Chương 1–2: Bản đồ và Trái Đất – Hành tinh của Hệ Mặt Trời",
                    (
                        "Bài 1–8: Kinh tuyến, vĩ tuyến, tọa độ địa lí, tỉ lệ bản đồ và chuyển "
                        "động của Trái Đất"
                    ),
                    50,
                    90,
                    5,
                    (
                        "Xác định tọa độ địa lí, tính khoảng cách theo tỉ lệ bản đồ và giải "
                        "thích hiện tượng ngày đêm, các mùa."
                    ),
                    (
                        (
                            "Xác định được tọa độ địa lí, tính giờ khu vực và giải thích hệ "
                            "quả chuyển động Trái Đất."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-6-t2",
            "Lịch sử và Địa lí",
            "6",
            "Tập hai",
            96,
            [
                (
                    (
                        "Lịch sử 6 – Chương 4–5: Đông Nam Á cổ đại và Việt Nam từ thế kỉ VII "
                        "TCN đến thế kỉ X"
                    ),
                    (
                        "Bài 11–20: Nhà nước Văn Lang – Âu Lạc, thời kì Bắc thuộc và chiến "
                        "thắng Bạch Đằng năm 938"
                    ),
                    8,
                    48,
                    6,
                    (
                        "Trình bày các cuộc khởi nghĩa tiêu biểu thời Bắc thuộc và bước ngoặt "
                        "độc lập năm 938."
                    ),
                    (
                        (
                            "Phân tích được ý nghĩa của chiến thắng Bạch Đằng năm 938 chấm "
                            "dứt hơn một nghìn năm Bắc thuộc."
                        ),
                    ),
                ),
                (
                    "Địa lí 6 – Chương 3–6: Cấu tạo Trái Đất, Khí hậu, Nước và Đất – Sinh vật",
                    (
                        "Bài 9–26: Nội lực, ngoại lực, các đới khí hậu, sông hồ, biển đại "
                        "dương và rừng nhiệt đới"
                    ),
                    50,
                    90,
                    5,
                    (
                        "Giải thích tác động nội lực – ngoại lực, đọc biểu đồ nhiệt độ – "
                        "lượng mưa và mối quan hệ tự nhiên – con người."
                    ),
                    (
                        (
                            "Đọc được biểu đồ khí hậu và trình bày đặc điểm các đới khí hậu "
                            "trên Trái Đất."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-7-t1",
            "Lịch sử và Địa lí",
            "7",
            "Tập một",
            96,
            [
                (
                    (
                        "Lịch sử 7 – Chương 1–3: Tây Âu, Trung Quốc, Ấn Độ và Đông Nam Á thời "
                        "phong kiến"
                    ),
                    (
                        "Bài 1–9: Phát kiến địa lí, văn hóa Phục hưng và các triều đại phong "
                        "kiến phương Đông"
                    ),
                    8,
                    46,
                    5,
                    (
                        "Đánh giá tác động của các cuộc phát kiến địa lí, phong trào Văn hóa "
                        "Phục hưng và văn hóa Angkor."
                    ),
                    (
                        (
                            "Trình bày được nguyên nhân, hệ quả các cuộc phát kiến địa lí và "
                            "thành tựu Văn hóa Phục hưng."
                        ),
                    ),
                ),
                (
                    "Địa lí 7 – Chương 1–2: Châu Âu và Châu Á",
                    "Bài 1–8: Vị trí địa lí, thiên nhiên, dân cư, kinh tế châu Âu và châu Á",
                    48,
                    90,
                    5,
                    (
                        "Phân tích đặc điểm địa hình, khí hậu, cơ cấu dân số già châu Âu và "
                        "đặc điểm gió mùa châu Á."
                    ),
                    (
                        (
                            "Phân tích được mối liên hệ giữa vị trí địa lí, khí hậu và phân "
                            "bố dân cư châu Âu, châu Á."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-7-t2",
            "Lịch sử và Địa lí",
            "7",
            "Tập hai",
            96,
            [
                (
                    (
                        "Lịch sử 7 – Chương 4–5: Đất nước thời Ngô – Đinh – Tiền Lê – Lý – "
                        "Trần – Hồ – Lê sơ"
                    ),
                    (
                        "Bài 10–18: Kháng chiến chống Tống, Mông – Nguyên, khởi nghĩa Lam Sơn "
                        "và bộ luật Hồng Đức"
                    ),
                    8,
                    48,
                    6,
                    (
                        "Phân tích nguyên nhân thắng lợi các cuộc kháng chiến bảo vệ Tổ quốc "
                        "và thành tựu kinh tế, văn hóa Đại Việt."
                    ),
                    (
                        (
                            "Đánh giá được vai trò các anh hùng dân tộc và thành tựu văn hóa "
                            "Đại Việt thế kỉ X–XVI."
                        ),
                    ),
                ),
                (
                    "Địa lí 7 – Chương 3–5: Châu Phi, Châu Mỹ, Châu Đại Dương và Châu Nam Cực",
                    (
                        "Bài 9–22: Tự nhiên, tài nguyên, dân cư và vấn đề bảo vệ môi trường "
                        "các châu lục"
                    ),
                    50,
                    90,
                    5,
                    (
                        "Khảo sát môi trường hoang mạc châu Phi, rừng Amazon châu Mỹ và biến "
                        "đổi khí hậu tại Nam Cực."
                    ),
                    (
                        (
                            "So sánh được đặc điểm tự nhiên và vấn đề phát triển kinh tế – "
                            "môi trường các châu lục."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-8-t1",
            "Lịch sử và Địa lí",
            "8",
            "Tập một",
            96,
            [
                (
                    (
                        "Lịch sử 8 – Chương 1–3: Cách mạng tư sản, Cách mạng công nghiệp và "
                        "Việt Nam thế kỉ XVI–XVIII"
                    ),
                    (
                        "Bài 1–8: Cách mạng tư sản Anh – Mỹ – Pháp, phong trào Tây Sơn và "
                        "chiến thắng Ngọc Hồi – Đống Đa"
                    ),
                    8,
                    48,
                    6,
                    (
                        "Phân tích nguyên nhân, tính chất cách mạng tư sản cận đại và công "
                        "lao thống nhất đất nước của phong trào Tây Sơn."
                    ),
                    (
                        (
                            "So sánh được các cuộc cách mạng tư sản và đánh giá vai trò Quang "
                            "Trung – Nguyễn Huệ."
                        ),
                    ),
                ),
                (
                    (
                        "Địa lí 8 – Chương 1–2: Vị trí địa lí, Địa hình, Khoáng sản và Khí "
                        "hậu – Thủy văn Việt Nam"
                    ),
                    (
                        "Bài 1–7: Đặc điểm vị trí lãnh thổ, địa hình đồi núi, khí hậu nhiệt "
                        "đới ẩm gió mùa và hệ thống sông ngòi"
                    ),
                    50,
                    90,
                    5,
                    (
                        "Phân tích ảnh hưởng vị trí địa lí, gió mùa đến khí hậu và chế độ "
                        "nước sông ngòi Việt Nam."
                    ),
                    (
                        (
                            "Trình bày được tính chất nhiệt đới ẩm gió mùa của khí hậu và đặc "
                            "điểm sông ngòi Việt Nam."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-8-t2",
            "Lịch sử và Địa lí",
            "8",
            "Tập hai",
            96,
            [
                (
                    (
                        "Lịch sử 8 – Chương 4–5: Chiến tranh thế giới thứ nhất, Cách mạng "
                        "tháng Mười Nga và Việt Nam 1858–1918"
                    ),
                    (
                        "Bài 9–18: Cuộc kháng chiến chống Pháp xâm lược, phong trào Cần vương "
                        "và xu hướng cứu nước đầu thế kỉ XX"
                    ),
                    8,
                    48,
                    6,
                    (
                        "Phân tích nguyên nhân mất nước cuối thế kỉ XIX và các khuynh hướng "
                        "cứu nước của Phan Bội Châu, Phan Châu Trinh, Nguyễn Tất Thành."
                    ),
                    ("So sánh được chủ trương cứu nước của các sĩ phu yêu nước đầu thế kỉ XX.",),
                ),
                (
                    "Địa lí 8 – Chương 3–4: Thổ nhưỡng, Sinh vật và Biển đảo Việt Nam",
                    (
                        "Bài 8–12: Đất feralit, đất phù sa, đa dạng sinh học và chủ quyền "
                        "biển đảo Việt Nam"
                    ),
                    50,
                    90,
                    5,
                    (
                        "Trình bày đặc điểm ba nhóm đất chính, giá trị tài nguyên biển và "
                        "chứng cứ chủ quyền Hoàng Sa, Trường Sa."
                    ),
                    (
                        (
                            "Nêu được giải pháp bảo vệ đa dạng sinh học và chủ quyền vùng "
                            "biển đảo Việt Nam."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lsdl-9-t1",
            "Lịch sử và Địa lí",
            "9",
            "Tập một",
            96,
            [
                (
                    "Lịch sử 9 – Chương 1–3: Thế giới 1918–1945 và Việt Nam 1918–1945",
                    (
                        "Bài 1–10: Chiến tranh thế giới thứ hai, Đảng Cộng sản Việt Nam ra "
                        "đời năm 1930 và Cách mạng tháng Tám 1945"
                    ),
                    8,
                    48,
                    6,
                    (
                        "Phân tích bước ngoặt thành lập Đảng năm 1930 và diễn biến, ý nghĩa "
                        "lịch sử Cách mạng tháng Tám năm 1945."
                    ),
                    (
                        (
                            "Đánh giá được vai trò lãnh đạo của Đảng và Nguyễn Ái Quốc trong "
                            "thắng lợi Cách mạng tháng Tám 1945."
                        ),
                    ),
                ),
                (
                    "Địa lí 9 – Chương 1–2: Địa lí dân cư và Địa lí các ngành kinh tế Việt Nam",
                    (
                        "Bài 1–9: Dân số, lao động, đô thị hóa, nông nghiệp, công nghiệp và "
                        "dịch vụ Việt Nam"
                    ),
                    50,
                    90,
                    5,
                    (
                        "Phân tích cơ cấu dân số, chuyển dịch cơ cấu kinh tế và các nhân tố "
                        "phát triển nông – công nghiệp, du lịch."
                    ),
                    ("Đọc và phân tích được biểu đồ cơ cấu dân số, cơ cấu kinh tế Việt Nam.",),
                ),
            ],
        ),
        (
            "kntt-lsdl-9-t2",
            "Lịch sử và Địa lí",
            "9",
            "Tập hai",
            96,
            [
                (
                    "Lịch sử 9 – Chương 4–6: Thế giới sau 1945 và Việt Nam từ 1945 đến nay",
                    (
                        "Bài 11–22: Kháng chiến chống Pháp (1945–1954), chống Mỹ (1954–1975) "
                        "và công cuộc Đổi mới từ 1986"
                    ),
                    8,
                    48,
                    6,
                    (
                        "Phân tích chiến thắng Điện Biên Phủ 1954, Đại thắng mùa Xuân 1975 và "
                        "thành tựu công cuộc Đổi mới."
                    ),
                    (
                        (
                            "Trình bày được nguyên nhân thắng lợi hai cuộc kháng chiến và "
                            "thành tựu Đổi mới đất nước."
                        ),
                    ),
                ),
                (
                    (
                        "Địa lí 9 – Chương 3: Sự phân hóa lãnh thổ – 6 vùng kinh tế – xã hội "
                        "và Kinh tế biển"
                    ),
                    (
                        "Bài 10–21: Thế mạnh phát triển các vùng kinh tế từ Bắc vào Nam và "
                        "kinh tế biển đảo"
                    ),
                    50,
                    90,
                    5,
                    (
                        "So sánh thế mạnh tự nhiên, kinh tế – xã hội của 6 vùng kinh tế Việt "
                        "Nam và định hướng phát triển bền vững."
                    ),
                    (
                        (
                            "Phân tích được thế mạnh kinh tế của từng vùng và liên kết vùng "
                            "kinh tế trọng điểm."
                        ),
                    ),
                ),
            ],
        ),
        # ==================== LỊCH SỬ & ĐỊA LÍ THPT 10–12 ====================
        (
            "kntt-lich-su-10-t1",
            "Lịch sử",
            "10",
            "Tập một",
            128,
            [
                (
                    (
                        "Chủ đề 1–3: Lịch sử, Sử học và Một số nền văn minh thế giới thời cổ "
                        "– trung đại"
                    ),
                    (
                        "Bài 1–8: Tri thức lịch sử, văn minh Ai Cập, Trung Hoa, Ấn Độ, Hy Lạp "
                        "– La Mã và Phục hưng"
                    ),
                    6,
                    58,
                    6,
                    (
                        "Phân biệt hiện thực lịch sử và nhận thức lịch sử; so sánh thành tựu "
                        "các nền văn minh lớn cổ – trung đại."
                    ),
                    (
                        (
                            "Đánh giá được giá trị trường tồn của các nền văn minh cổ – trung "
                            "đại đối với nhân loại."
                        ),
                    ),
                ),
                (
                    (
                        "Chủ đề 4–7: Các cuộc cách mạng công nghiệp và Văn minh Đại Việt, "
                        "cộng đồng các dân tộc Việt Nam"
                    ),
                    (
                        "Bài 9–17: Cách mạng công nghiệp 1.0–4.0, văn minh Văn Lang – Âu Lạc "
                        "và văn minh Đại Việt"
                    ),
                    62,
                    122,
                    6,
                    (
                        "Phân tích tác động của bốn cuộc cách mạng công nghiệp và bản sắc văn "
                        "minh Đại Việt qua các triều đại."
                    ),
                    (
                        (
                            "Phân tích được cơ sở hình thành và thành tựu tiêu biểu của văn "
                            "minh Đại Việt."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lich-su-11-t1",
            "Lịch sử",
            "11",
            "Tập một",
            112,
            [
                (
                    (
                        "Chủ đề 1–3: Cách mạng tư sản, Chủ nghĩa xã hội và Quá trình giành "
                        "độc lập ở Đông Nam Á"
                    ),
                    (
                        "Bài 1–6: Cách mạng tư sản cận đại, Liên Xô – hệ thống XHCN và cuộc "
                        "đấu tranh giải phóng ở Đông Nam Á"
                    ),
                    6,
                    48,
                    6,
                    (
                        "So sánh mục tiêu, kết quả các cuộc cách mạng tư sản và con đường "
                        "giành độc lập của các nước Đông Nam Á."
                    ),
                    (
                        (
                            "Phân tích được nguyên nhân thành công và bài học kinh nghiệm của "
                            "phong trào giải phóng dân tộc."
                        ),
                    ),
                ),
                (
                    (
                        "Chủ đề 4–6: Chiến tranh bảo vệ Tổ quốc, Cải cách trong lịch sử và "
                        "Chủ quyền Biển Đông"
                    ),
                    (
                        "Bài 7–13: Các cuộc kháng chiến chống ngoại xâm, cải cách Hồ Quý Ly – "
                        "Lê Thánh Tông – Minh Mạng và Biển Đông"
                    ),
                    52,
                    104,
                    6,
                    (
                        "Đánh giá nghệ thuật quân sự dân tộc, giá trị lịch sử các cuộc cải "
                        "cách và tầm quan trọng chiến lược của Biển Đông."
                    ),
                    (
                        (
                            "Trình bày được cơ sở lịch sử, pháp lí khẳng định chủ quyền Việt "
                            "Nam đối với Hoàng Sa và Trường Sa."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-lich-su-12-t1",
            "Lịch sử",
            "12",
            "Tập một",
            116,
            [
                (
                    "Chủ đề 1–2: Thế giới trong và sau Chiến tranh lạnh – ASEAN",
                    (
                        "Bài 1–5: Liên hợp quốc, Trật tự hai cực Ianta, xu thế đa cực và Cộng "
                        "đồng ASEAN"
                    ),
                    6,
                    38,
                    5,
                    (
                        "Phân tích vai trò Liên hợp quốc, sự sụp đổ Trật tự hai cực Ianta và "
                        "tiến trình hội nhập ASEAN."
                    ),
                    (
                        (
                            "Đánh giá được cơ hội, thách thức của Việt Nam trong Cộng đồng "
                            "ASEAN và trật tự đa cực."
                        ),
                    ),
                ),
                (
                    (
                        "Chủ đề 3–6: Cách mạng tháng Tám, Kháng chiến 1945–1975, Đổi mới, Đối "
                        "ngoại và Hồ Chí Minh"
                    ),
                    (
                        "Bài 6–17: Thắng lợi 1945, 1954, 1975, đường lối Đổi mới 1986 và hoạt "
                        "động đối ngoại Việt Nam"
                    ),
                    40,
                    110,
                    7,
                    (
                        "Hệ thống hóa tiến trình giải phóng dân tộc, công cuộc Đổi mới, hội "
                        "nhập quốc tế và di sản Hồ Chí Minh."
                    ),
                    (
                        (
                            "Phân tích được bài học kinh nghiệm của cách mạng Việt Nam và "
                            "công cuộc Đổi mới."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-dia-li-10-t1",
            "Địa lí",
            "10",
            "Tập một",
            136,
            [
                (
                    "Phần 1: Địa lí tự nhiên",
                    (
                        "Bài 1–19: Bản đồ, Thạch quyển, Khí quyển, Thủy quyển, Sinh quyển và "
                        "quy luật vỏ địa lí"
                    ),
                    6,
                    64,
                    6,
                    (
                        "Phân tích thuyết kiến tạo mảng, hoàn lưu khí quyển, dòng biển và quy "
                        "luật thống nhất, địa đới, phi địa đới."
                    ),
                    (
                        (
                            "Giải thích được cơ chế hình thành các vành đai khí áp, gió và "
                            "quy luật phân hóa tự nhiên."
                        ),
                    ),
                ),
                (
                    "Phần 2: Địa lí kinh tế – xã hội",
                    (
                        "Bài 20–40: Dân số, đô thị hóa, nông nghiệp, công nghiệp, dịch vụ và "
                        "phát triển bền vững"
                    ),
                    68,
                    128,
                    6,
                    (
                        "Phân tích tháp dân số, cơ cấu ngành kinh tế, vai trò giao thông vận "
                        "tải, thương mại và tăng trưởng xanh."
                    ),
                    ("Vận dụng được kiến thức địa lí kinh tế phân tích bảng số liệu và biểu đồ.",),
                ),
            ],
        ),
        (
            "kntt-dia-li-11-t1",
            "Địa lí",
            "11",
            "Tập một",
            160,
            [
                (
                    "Phần 1: Một số vấn đề về kinh tế – xã hội thế giới",
                    (
                        "Bài 1–6: Các nhóm nước, toàn cầu hóa, khu vực hóa, tổ chức kinh tế "
                        "và an ninh toàn cầu"
                    ),
                    6,
                    36,
                    5,
                    (
                        "Phân biệt chỉ số phát triển GDP/người, HDI; đánh giá tác động toàn "
                        "cầu hóa và an ninh lương thực, năng lượng."
                    ),
                    (
                        (
                            "Phân tích được tác động của toàn cầu hóa và vai trò các tổ chức "
                            "quốc tế lớn."
                        ),
                    ),
                ),
                (
                    "Phần 2: Địa lí khu vực và quốc gia",
                    (
                        "Bài 7–30: Mỹ La-tinh, EU, Đông Nam Á, Tây Nam Á, Hoa Kỳ, Nga, Nhật "
                        "Bản, Trung Quốc, Ô-xtrây-li-a"
                    ),
                    38,
                    152,
                    7,
                    (
                        "Phân tích thế mạnh tự nhiên, dân cư và mô hình phát triển kinh tế "
                        "của các khu vực và cường quốc kinh tế."
                    ),
                    (
                        (
                            "So sánh được đặc điểm phát triển kinh tế và quan hệ hợp tác giữa "
                            "các khu vực, quốc gia với Việt Nam."
                        ),
                    ),
                ),
            ],
        ),
        (
            "kntt-dia-li-12-t1",
            "Địa lí",
            "12",
            "Tập một",
            168,
            [
                (
                    "Phần 1–2: Địa lí tự nhiên và Địa lí dân cư Việt Nam",
                    (
                        "Bài 1–8: Vị trí địa lí, thiên nhiên nhiệt đới ẩm gió mùa, phân hóa "
                        "đa dạng tự nhiên, dân số và đô thị hóa"
                    ),
                    6,
                    48,
                    6,
                    (
                        "Phân tích sự phân hóa thiên nhiên theo Bắc – Nam, Đông – Tây, độ cao "
                        "và cơ cấu lao động, đô thị hóa."
                    ),
                    (
                        (
                            "Giải thích được tính phân hóa đa dạng của tự nhiên và vấn đề "
                            "việc làm ở Việt Nam."
                        ),
                    ),
                ),
                (
                    "Phần 3–4: Địa lí các ngành kinh tế và Các vùng kinh tế – xã hội Việt Nam",
                    (
                        "Bài 9–31: Chuyển dịch cơ cấu kinh tế, nông – công nghiệp, dịch vụ và "
                        "6 vùng kinh tế, phát triển kinh tế biển đảo"
                    ),
                    50,
                    160,
                    7,
                    (
                        "Đánh giá thế mạnh, hạn chế và định hướng chuyển dịch cơ cấu ngành, "
                        "lãnh thổ các vùng kinh tế Việt Nam."
                    ),
                    (
                        (
                            "Phân tích được số liệu, biểu đồ và giải thích thế mạnh phát "
                            "triển kinh tế của các vùng Việt Nam."
                        ),
                    ),
                ),
            ],
        ),
    ]


def lesson_catalog() -> list[dict[str, Any]]:
    """Trả về danh mục bộ học liệu tự biên soạn đa môn và SGK KNTT có licenseStatus='allowed'."""
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
    built: list[dict[str, Any]] = [
        {
            "id": str(uuid5(NAMESPACE_URL, f"soan-de-thi/hoc-lieu/{key}/1")),
            "version": 1,
            "subject": subject,
            "grade": grade,
            "book": book,
            "series": book,
            "volume": volume,
            "catalogKind": "sample",
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
                    "id": f"{key}-b{index}",
                    "number": index,
                    "chapter": chapter,
                    "title": title,
                    "outcome": outcome,
                    "text": text,
                    "summary": text,
                    "learningOutcomes": [outcome],
                }
                for index, (chapter, title, outcome, text) in enumerate(lessons, 1)
            ],
        }
        for key, subject, grade, book, volume, lessons in collections
    ]
    for key, subject, grade, volume, total_pages, kntt_lessons in _kntt_raw_collections():
        sha_lessons = [
            (chapter, title, "; ".join(outcomes), summary)
            for chapter, title, _, _, _, summary, outcomes in kntt_lessons
        ]
        default_title = (
            f"{subject} {grade} Global Success – {volume} ({KNTT_SERIES})"
            if subject == "Tiếng Anh"
            else f"{subject} {grade} – {volume} ({KNTT_SERIES})"
        )
        official_title, source_url = _KNTT_OFFICIAL_SOURCES.get(
            key, (default_title, "https://sachdientu.nxbgd.vn/")
        )
        display_name = (
            f"{subject} {grade} · {KNTT_SERIES} · Global Success · {volume}"
            if subject == "Tiếng Anh"
            else f"{subject} {grade} · {KNTT_SERIES} · {volume}"
        )
        built.append(
            {
                "id": str(uuid5(NAMESPACE_URL, f"soan-de-thi/hoc-lieu/{key}/1")),
                "version": 1,
                "subject": subject,
                "grade": grade,
                "book": KNTT_SERIES,
                "series": KNTT_SERIES,
                "publisher": "NXB Giáo dục Việt Nam",
                "edition": "GDPT 2018",
                "bookTitle": official_title,
                "officialTitle": official_title,
                "sourceUrl": source_url,
                "contentType": "summary_outline",
                "volume": volume,
                "totalPages": total_pages,
                "catalogKind": "sgk",
                "name": display_name,
                "sourceTitle": f"Khung học liệu tự biên soạn · {subject} {grade} ({KNTT_SERIES})",
                "curriculumStandard": "GDPT 2018",
                "schoolYear": "2026-2027",
                "gradeLevel": _grade_level(grade),
                "licenseStatus": "allowed",
                "licenseNote": (
                    "Mục lục và yêu cầu cần đạt theo Chương trình GDPT 2018 (Bộ GD&ĐT); "
                    "tóm tắt tự biên soạn"
                ),
                "sourceOrigin": "lesson_catalog",
                "sha256": _catalog_sha256(subject, grade, KNTT_SERIES, volume, sha_lessons),
                "lessons": [
                    {
                        "id": f"{key}-b{index}",
                        "number": index,
                        "chapter": chapter,
                        "title": title,
                        "pageStart": page_start,
                        "pageEnd": page_end,
                        "pageRange": (
                            f"tr. {page_start}-{page_end}"
                            if page_end > page_start
                            else f"tr. {page_start}"
                        ),
                        "periods": periods,
                        "summary": summary,
                        "learningOutcomes": list(outcomes),
                        "outcome": "; ".join(outcomes),
                        "text": summary,
                    }
                    for index, (
                        chapter,
                        title,
                        page_start,
                        page_end,
                        periods,
                        summary,
                        outcomes,
                    ) in enumerate(kntt_lessons, 1)
                ],
            }
        )

    volumes_by_group: dict[tuple[str, str, str], list[str]] = {}
    for col in built:
        group_key = (col["subject"], col["grade"], col["book"])
        group_vols = volumes_by_group.setdefault(group_key, [])
        if col["volume"] not in group_vols:
            group_vols.append(col["volume"])
    for group_vols in volumes_by_group.values():
        group_vols.sort(key=lambda v: (_VOLUME_ORDER.get(v, 99), v))
    for col in built:
        group_key = (col["subject"], col["grade"], col["book"])
        col["volumesAvailable"] = list(volumes_by_group[group_key])
    return built


def search_lesson_catalog(
    query: str = "",
    *,
    subject: str | None = None,
    grade: str | int | None = None,
    book: str | None = None,
    volume: str | None = None,
) -> list[dict[str, Any]]:
    """Lọc danh mục học liệu mẫu theo lớp/môn/bộ sách/tập, chuẩn hóa i/y và đồng nghĩa."""
    query_variants = expand_vi_synonyms(query)
    grade_str = str(grade).strip() if grade is not None else ""
    subject_norm = normalize_vi_search(subject) if subject else ""
    allowed_subjects = _SUBJECT_ALIASES.get(subject_norm, frozenset({subject_norm}))
    book_norm = normalize_vi_search(book) if book else ""
    volume_norm = normalize_vi_search(volume) if volume else ""

    exact_matched: list[dict[str, Any]] = []
    alias_matched: list[dict[str, Any]] = []
    for collection in lesson_catalog():
        if grade_str and collection["grade"] != grade_str:
            continue
        col_subject_norm = normalize_vi_search(collection["subject"])
        if subject_norm and col_subject_norm not in allowed_subjects:
            continue
        if book_norm and normalize_vi_search(collection["book"]) != book_norm:
            continue
        if volume_norm and normalize_vi_search(collection["volume"]) != volume_norm:
            continue

        lessons = collection["lessons"]
        if query_variants:
            subject_tokens = (
                "Tiếng Việt Ngữ văn"
                if col_subject_norm in _SUBJECT_ALIASES
                else collection["subject"]
            )
            filtered_lessons = []
            for lesson in lessons:
                searchable = normalize_vi_search(
                    " ".join(
                        [
                            subject_tokens,
                            collection["book"],
                            collection["volume"],
                            lesson["chapter"],
                            lesson["title"],
                            lesson["outcome"],
                            lesson["text"],
                            lesson.get("pageRange", ""),
                        ]
                    )
                )
                searchable_plain = " ".join(re.sub(r"[^0-9a-z]+", " ", searchable).split())
                if any(
                    variant in searchable or variant in searchable_plain
                    for variant in query_variants
                ):
                    filtered_lessons.append(lesson)
            lessons = filtered_lessons
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
    page_range = str(lesson.get("pageRange") or "").strip()
    locator = (
        f"Bài {lesson['number']} · {lesson['chapter']} ({page_range})"
        if page_range
        else f"Bài {lesson['number']} · {lesson['chapter']}"
    )
    if len(locator) > 300:
        locator = locator[:297] + "..."
    content_excerpt = (
        f"Bài {lesson['number']}. {lesson['title']}\n"
        f"{lesson['text']}\n"
        f"Mục tiêu: {lesson['outcome']}"
    )
    if len(content_excerpt) > 12_000:
        content_excerpt = content_excerpt[:11_997] + "..."
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
        "locator": locator,
        "content_excerpt": content_excerpt,
    }
