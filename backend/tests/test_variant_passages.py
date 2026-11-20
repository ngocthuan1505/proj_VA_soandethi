"""Kiểm thử nhóm ngữ liệu nhiều câu (passageId/groupId) và bảng đối chiếu sau hoán vị."""

import io
import zipfile
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError
from mach_backend.local_documents import (
    describe_variant_option_mapping,
    exam_variant,
    preview_exam_variant,
)
from mach_backend.local_workspace import create_app

INTERNAL_KEYS = {
    "optionMapping",
    "optionsShuffled",
    "originalAnswer",
    "variantAnswer",
    "originalNumber",
}


def _mcq(
    qid: str,
    stem: str,
    options: list[str],
    answer: int = 1,
    **extra,
) -> dict:
    return {
        "id": qid,
        "type": "mcq",
        "stem": stem,
        "options": list(options),
        "answer": answer,
        "explanation": f"LOI_GIAI_BI_MAT_{qid}",
        "rubric": [{"text": f"BAREM_BI_MAT_{qid}", "points": 0.5}],
        "evidence": [{"quote": f"NGUON_BI_MAT_{qid}"}],
        **extra,
    }


def _rich_doc(text: str) -> dict:
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text, "marks": [{"type": "bold"}]}],
            }
        ],
    }


def _two_passage_exam() -> dict:
    return {
        "title": "Đề đọc hiểu nhiều ngữ liệu",
        "subject": "Ngữ văn",
        "grade": "8",
        "minutes": 45,
        "questions": [
            _mcq(
                "p1_q1",
                "Nội dung chính đoạn 1 là gì?",
                ["Mùa xuân", "Mùa thu", "Mùa hạ", "Mùa đông"],
                answer=1,
                passageId="p1",
                passageTitle="Ngữ liệu 1",
                passageText="Đoạn văn số 1 về bầu trời thu trong xanh.",
                pageBreak=True,
                optionDocs=[None, _rich_doc("Mùa thu"), None, None],
            ),
            _mcq(
                "p1_q2",
                "Nhân vật nào xuất hiện ở đoạn 1?",
                ["Nam", "Minh", "Lan", "Cả hai đáp án trên"],
                answer=3,
                passageId="p1",
            ),
            _mcq(
                "p2_q1",
                "Ý nghĩa hình ảnh con thuyền ở đoạn 2?",
                ["Khát vọng", "Nỗi buồn", "Sự chờ đợi", "Kỷ niệm"],
                answer=0,
                passageId="p2",
                passageTitle="Ngữ liệu <script>alert(9)</script> 2",
                passageText="Đoạn văn số 2 kể về chuyến đò sớm.",
            ),
            _mcq(
                "p2_q2",
                "Biện pháp tu từ nổi bật ở đoạn 2 là gì?",
                ["So sánh", "Ẩn dụ", "Hoán dụ", "Điệp ngữ"],
                answer=2,
                passageId="p2",
            ),
        ],
    }


def test_intra_passage_shuffle_preserves_passage_header_on_first_question():
    exam = {
        "title": "Đề một khối ngữ liệu",
        "subject": "Ngữ văn",
        "grade": "7",
        "questions": [
            _mcq("q0", "Ý hỏi mở đầu độc lập", ["Một", "Hai", "Ba", "Bốn"], answer=0),
            _mcq(
                "q1",
                "Ý hỏi thứ nhất của ngữ liệu",
                ["A1", "B1", "C1", "D1"],
                answer=0,
                passageId="p-van-1",
                passageTitle="Văn bản đọc hiểu A",
                passageText="Buổi sáng mùa thu nắng trải vàng trên sân trường.",
            ),
            _mcq(
                "q2",
                "Ý hỏi thứ hai của ngữ liệu",
                ["A2", "B2", "C2", "D2"],
                answer=1,
                passageId="p-van-1",
            ),
            _mcq(
                "q3",
                "Ý hỏi thứ ba của ngữ liệu",
                ["A3", "B3", "C3", "D3"],
                answer=2,
                passageId="p-van-1",
            ),
        ],
    }
    before = deepcopy(exam)

    variant_1 = exam_variant(
        exam, {"questionIds": ["q1", "q2", "q3"], "offset": 1, "shuffleOptions": True}
    )
    assert [q["id"] for q in variant_1["questions"]] == ["q0", "q2", "q3", "q1"]
    assert variant_1["questions"][1]["passageTitle"] == "Văn bản đọc hiểu A"
    assert (
        variant_1["questions"][1]["passageText"]
        == "Buổi sáng mùa thu nắng trải vàng trên sân trường."
    )
    assert "passageTitle" not in variant_1["questions"][2]
    assert "passageText" not in variant_1["questions"][2]
    assert "passageTitle" not in variant_1["questions"][3]
    assert "passageText" not in variant_1["questions"][3]

    variant_2 = exam_variant(
        exam, {"questionIds": ["q1", "q2", "q3"], "offset": 2, "shuffleOptions": False}
    )
    assert [q["id"] for q in variant_2["questions"]] == ["q0", "q3", "q1", "q2"]
    assert variant_2["questions"][1]["passageTitle"] == "Văn bản đọc hiểu A"
    assert (
        variant_2["questions"][1]["passageText"]
        == "Buổi sáng mùa thu nắng trải vàng trên sân trường."
    )
    assert "passageText" not in variant_2["questions"][2]

    for question in variant_1["questions"] + variant_2["questions"]:
        assert not (INTERNAL_KEYS & question.keys())
    assert exam == before


def test_intra_passage_subset_and_shared_headers_behavior():
    exam = {
        "title": "Đề thử tiêu đề ngữ liệu",
        "subject": "Ngữ văn",
        "grade": "7",
        "questions": [
            _mcq(
                "q1",
                "Hỏi 1",
                ["Một", "Hai", "Ba", "Bốn"],
                passageId="p1",
                passageText="Đoạn văn duy nhất ở câu đầu.",
            ),
            _mcq("q2", "Hỏi 2", ["Năm", "Sáu", "Bảy", "Tám"], passageId="p1"),
            _mcq("q3", "Hỏi 3", ["Chín", "Mười", "Mười một", "Mười hai"], passageId="p1"),
        ],
    }
    variant = exam_variant(exam, {"questionIds": ["q1", "q3"], "offset": 1})
    assert [q["id"] for q in variant["questions"]] == ["q3", "q2", "q1"]
    assert variant["questions"][0]["passageText"] == "Đoạn văn duy nhất ở câu đầu."
    assert "passageTitle" not in variant["questions"][0]
    assert "passageText" not in variant["questions"][2]

    shared_exam = deepcopy(exam)
    for q in shared_exam["questions"]:
        q["passageTitle"] = "Tiêu đề chung"
        q["passageText"] = "Ngữ liệu lặp trên từng câu."
    shared_variant = exam_variant(shared_exam, {"questionIds": ["q1", "q2", "q3"], "offset": 1})
    assert all(q["passageTitle"] == "Tiêu đề chung" for q in shared_variant["questions"])
    assert all(
        q["passageText"] == "Ngữ liệu lặp trên từng câu." for q in shared_variant["questions"]
    )


def test_multi_block_passage_and_group_shuffle_keeps_contiguity_and_bounds():
    exam = {
        "title": "Đề nhiều khối khác kích thước",
        "subject": "Tiếng Anh",
        "grade": "9",
        "questions": [
            _mcq(
                "a1",
                "Đoạn A - hỏi 1",
                ["A1", "B1", "C1", "D1"],
                passageId="pA",
                passageTitle="Reading A",
                passageText="Text A",
                pageBreak=True,
            ),
            _mcq("a2", "Đoạn A - hỏi 2", ["A2", "B2", "C2", "D2"], passageId="pA"),
            _mcq(
                "b1",
                "Đoạn B - hỏi 1",
                ["A3", "B3", "C3", "D3"],
                passageId="pB",
                passageTitle="Reading B",
                passageText="Text B",
            ),
            _mcq("b2", "Đoạn B - hỏi 2", ["A4", "B4", "C4", "D4"], passageId="pB"),
            _mcq("b3", "Đoạn B - hỏi 3", ["A5", "B5", "C5", "D5"], passageId="pB"),
            _mcq("solo", "Câu độc lập", ["A6", "B6", "C6", "D6"]),
        ],
    }
    ids = ["a1", "a2", "b1", "b2", "b3", "solo"]
    before = deepcopy(exam)

    v0 = exam_variant(exam, {"questionIds": ids, "offset": 0})
    v1 = exam_variant(exam, {"questionIds": ids, "offset": 1})
    v2 = exam_variant(exam, {"questionIds": ids, "offset": 2})

    assert [q["id"] for q in v0["questions"]] == ["a1", "a2", "b1", "b2", "b3", "solo"]
    assert [q["id"] for q in v1["questions"]] == ["b1", "b2", "b3", "solo", "a1", "a2"]
    assert [q["id"] for q in v2["questions"]] == ["solo", "a1", "a2", "b1", "b2", "b3"]

    # Cờ ngắt trang đầu vùng giữ ở đơn vị đầu tiên, không chen ngang giữa khối ngữ liệu.
    assert v1["questions"][0]["pageBreak"] is True
    assert v1["questions"][1]["pageBreak"] is False
    assert v1["questions"][2]["pageBreak"] is False
    assert v1["questions"][4]["passageText"] == "Text A"
    assert v1["questions"][0]["passageText"] == "Text B"

    with pytest.raises(AIError) as err:
        exam_variant(exam, {"questionIds": ids, "offset": 3})
    assert err.value.code == "invalid_variant"

    # Hai nhóm groupId hoàn chỉnh cũng hoán vị nguyên khối liên tục.
    group_exam = {
        "title": "Đề hai nhóm groupId",
        "subject": "Toán",
        "grade": "9",
        "questions": [
            _mcq("g1_1", "Nhóm đầu tiên - ý hỏi thứ nhất", ["1", "2", "3", "4"], groupId="g1"),
            _mcq("g1_2", "Nhóm đầu tiên - ý hỏi thứ hai", ["5", "6", "7", "8"], groupId="g1"),
            _mcq("g2_1", "Nhóm thứ hai - ý hỏi thứ nhất", ["9", "10", "11", "12"], groupId="g2"),
            _mcq("g2_2", "Nhóm thứ hai - ý hỏi thứ hai", ["13", "14", "15", "16"], groupId="g2"),
        ],
    }
    gv = exam_variant(group_exam, {"questionIds": ["g1_1", "g1_2", "g2_1", "g2_2"], "offset": 1})
    assert [q["id"] for q in gv["questions"]] == ["g2_1", "g2_2", "g1_1", "g1_2"]
    with pytest.raises(AIError) as err2:
        exam_variant(group_exam, {"questionIds": ["g1_1", "g1_2", "g2_1", "g2_2"], "offset": 2})
    assert err2.value.code == "invalid_variant"

    # Hai khối bằng kích thước có câu giữ cố định ở giữa vẫn hoán vị nguyên khối.
    held_exam = {
        "title": "Đề có câu giữ ở giữa",
        "subject": "Ngữ văn",
        "grade": "8",
        "questions": [
            _mcq("x1", "Khối X 1", ["1", "2", "3", "4"], passageId="pX"),
            _mcq("x2", "Khối X 2", ["1", "2", "3", "4"], passageId="pX"),
            _mcq("mid", "Câu giữ cố định", ["1", "2", "3", "4"]),
            _mcq("y1", "Khối Y 1", ["1", "2", "3", "4"], passageId="pY"),
            _mcq("y2", "Khối Y 2", ["1", "2", "3", "4"], passageId="pY"),
        ],
    }
    hv = exam_variant(held_exam, {"questionIds": ["x1", "x2", "y1", "y2"], "offset": 1})
    assert [q["id"] for q in hv["questions"]] == ["y1", "y2", "mid", "x1", "x2"]
    assert exam == before


@pytest.mark.parametrize(
    "selected_ids",
    [
        ["p1_q2", "p2_q1", "p2_q2"],
        ["p1_q1", "p1_q2", "p2_q1"],
        ["p1_q2", "p2_q1"],
    ],
)
def test_partial_passage_selection_rejected_with_http_400_invalid_variant(selected_ids, tmp_path):
    exam = _two_passage_exam()
    with pytest.raises(AIError) as err:
        exam_variant(exam, {"questionIds": selected_ids, "offset": 1})
    assert err.value.code == "invalid_variant"

    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        preview_res = client.post(
            "/api/preview-variant",
            json={"exam": exam, "variant": {"questionIds": selected_ids, "offset": 1}},
        )
        assert preview_res.status_code == 400
        assert preview_res.json()["code"] == "invalid_variant"

        pack_res = client.post(
            "/api/save-export",
            json={
                "type": "variant-pack",
                "exam": exam,
                "format": "html",
                "questionIds": selected_ids,
            },
        )
        assert pack_res.status_code == 400
        assert pack_res.json()["code"] == "invalid_variant"


def test_variant_rejects_broken_groups_and_legacy_disallowed_cases():
    # Chọn dở dang 1 câu trong passageId lẫn với câu độc lập ngoài nhóm.
    partial_with_solo = {
        "title": "Đề dở dang",
        "questions": [
            _mcq("p1", "Ngữ liệu 1", ["1", "2", "3", "4"], passageId="doc1"),
            _mcq("p2", "Ngữ liệu 2", ["1", "2", "3", "4"], passageId="doc1"),
            _mcq("solo", "Câu độc lập", ["1", "2", "3", "4"]),
        ],
    }
    with pytest.raises(AIError, match="dở dang") as err:
        exam_variant(partial_with_solo, {"questionIds": ["p2", "solo"], "offset": 1})
    assert err.value.code == "invalid_variant"

    # Nhóm ngữ liệu bị tách rời sẵn trong đề gốc.
    non_contiguous = {
        "title": "Đề ngữ liệu tách rời",
        "questions": [
            _mcq("p1", "Ý thứ nhất của ngữ liệu", ["1", "2", "3", "4"], passageId="doc1"),
            _mcq("mid", "Xen giữa", ["1", "2", "3", "4"]),
            _mcq("p2", "Ý thứ hai của ngữ liệu", ["1", "2", "3", "4"], passageId="doc1"),
        ],
    }
    with pytest.raises(AIError, match="không liên tiếp") as err:
        exam_variant(non_contiguous, {"questionIds": ["p1", "mid", "p2"], "offset": 1})
    assert err.value.code == "invalid_variant"

    # Hai khối khác kích thước có câu không chọn chen giữa.
    unequal_with_gap = {
        "title": "Khác kích thước có khoảng trống",
        "questions": [
            _mcq("a1", "A1", ["1", "2", "3", "4"], passageId="A"),
            _mcq("a2", "A2", ["1", "2", "3", "4"], passageId="A"),
            _mcq("gap", "Giữ lại", ["1", "2", "3", "4"]),
            _mcq("b1", "B1", ["1", "2", "3", "4"], passageId="B"),
            _mcq("b2", "B2", ["1", "2", "3", "4"], passageId="B"),
            _mcq("b3", "B3", ["1", "2", "3", "4"], passageId="B"),
        ],
    }
    with pytest.raises(AIError, match="liền nhau") as err:
        exam_variant(unequal_with_gap, {"questionIds": ["a1", "a2", "b1", "b2", "b3"], "offset": 1})
    assert err.value.code == "invalid_variant"

    # Hai câu độc lập vắt qua khối ngữ liệu không được chọn ở giữa.
    across_unselected_passage = {
        "title": "Vắt qua ngữ liệu",
        "questions": [
            _mcq("s1", "Độc lập 1", ["1", "2", "3", "4"]),
            _mcq("p1", "Khối giữa 1", ["1", "2", "3", "4"], passageId="mid"),
            _mcq("p2", "Khối giữa 2", ["1", "2", "3", "4"], passageId="mid"),
            _mcq("s2", "Độc lập 2", ["1", "2", "3", "4"]),
        ],
    }
    with pytest.raises(AIError, match="cùng phần") as err:
        exam_variant(across_unselected_passage, {"questionIds": ["s1", "s2"], "offset": 1})
    assert err.value.code == "invalid_variant"

    # Kiểm lại các quy tắc chặn cũ: khác sectionId và passageId sai kiểu.
    exam = _two_passage_exam()
    exam["questions"][2]["sectionId"] = "phan-2"
    exam["questions"][3]["sectionId"] = "phan-2"
    with pytest.raises(AIError, match="cùng phần") as err:
        exam_variant(exam, {"questionIds": ["p1_q1", "p1_q2", "p2_q1", "p2_q2"], "offset": 1})
    assert err.value.code == "invalid_variant"

    exam_bad_token = _two_passage_exam()
    exam_bad_token["questions"][0]["passageId"] = ["invalid"]
    with pytest.raises(AIError, match="chưa hợp lệ") as err:
        exam_variant(
            exam_bad_token, {"questionIds": ["p1_q1", "p1_q2", "p2_q1", "p2_q2"], "offset": 1}
        )
    assert err.value.code == "invalid_variant"


def test_describe_variant_option_mapping_and_mcq_shuffle_with_option_docs():
    exam = _two_passage_exam()
    before = deepcopy(exam)
    ids = ["p1_q1", "p1_q2", "p2_q1", "p2_q2"]
    variant = exam_variant(exam, {"questionIds": ids, "offset": 1, "shuffleOptions": True})

    # Trong offset=1: khối p2 lên trước ([p2_q1, p2_q2]), khối p1 ra sau ([p1_q1, p1_q2]).
    orig_by_id = {q["id"]: q for q in exam["questions"]}
    var_p1_q1 = variant["questions"][2]
    var_p1_q2 = variant["questions"][3]
    var_p2_q1 = variant["questions"][0]

    # p1_q1 có answer=1 ("Mùa thu") và optionDocs[1] đậm; offset=1 xoay order=[2, 3, 0, 1].
    assert var_p1_q1["options"] == ["Mùa hạ", "Mùa đông", "Mùa xuân", "Mùa thu"]
    assert var_p1_q1["answer"] == 3
    assert var_p1_q1["optionDocs"] == [None, None, None, orig_by_id["p1_q1"]["optionDocs"][1]]

    map_p1_q1 = describe_variant_option_mapping(orig_by_id["p1_q1"], var_p1_q1)
    assert map_p1_q1 == {
        "optionsShuffled": True,
        "optionMapping": {"A": "C", "B": "D", "C": "A", "D": "B"},
        "originalAnswer": "B",
        "variantAnswer": "D",
    }
    assert map_p1_q1["optionMapping"][map_p1_q1["originalAnswer"]] == map_p1_q1["variantAnswer"]

    # p1_q2 có phương án phụ thuộc vị trí "Cả hai đáp án trên" -> giữ nguyên thứ tự gốc.
    assert var_p1_q2["options"] == orig_by_id["p1_q2"]["options"]
    assert var_p1_q2["answer"] == 3
    map_p1_q2 = describe_variant_option_mapping(orig_by_id["p1_q2"], var_p1_q2)
    assert map_p1_q2 == {
        "optionsShuffled": False,
        "optionMapping": {"A": "A", "B": "B", "C": "C", "D": "D"},
        "originalAnswer": "D",
        "variantAnswer": "D",
    }

    # p2_q1 có answer=0 ("Khát vọng") -> xoay sang vị trí 2 ("C").
    map_p2_q1 = describe_variant_option_mapping(orig_by_id["p2_q1"], var_p2_q1)
    assert map_p2_q1["optionsShuffled"] is True
    assert map_p2_q1["originalAnswer"] == "A"
    assert map_p2_q1["variantAnswer"] == "C"
    assert map_p2_q1["optionMapping"]["A"] == "C"

    # Câu tự luận trả về không trộn phương án và đáp án None.
    essay = {"id": "e1", "type": "essay", "stem": "Viết đoạn văn.", "options": []}
    assert describe_variant_option_mapping(essay, essay) == {
        "optionsShuffled": False,
        "optionMapping": {},
        "originalAnswer": None,
        "variantAnswer": None,
    }
    assert exam == before


def test_preview_exam_variant_preserves_legacy_questions_and_exposes_mappings_and_passages(
    tmp_path,
):
    exam = _two_passage_exam()
    payload = {
        "exam": exam,
        "variant": {
            "questionIds": ["p1_q1", "p1_q2", "p2_q1", "p2_q2"],
            "offset": 1,
            "shuffleOptions": True,
        },
    }
    direct = preview_exam_variant(payload)
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        response = client.post("/api/preview-variant", json=payload).raise_for_status().json()
    assert response == direct
    assert response["title"].endswith("Mã đề 102")

    # Tương thích ngược 100% với mvp.js và test_local_documents.py: questions chỉ có 3 khóa gốc.
    assert [set(q.keys()) for q in response["questions"]] == [
        {"originalNumber", "stem", "options"} for _ in range(4)
    ]
    assert [q["originalNumber"] for q in response["questions"]] == [3, 4, 1, 2]

    mappings = response["questionMappings"]
    assert len(mappings) == 4
    assert mappings[0]["passageId"] == "p2"
    assert mappings[0]["optionsShuffled"] is True
    assert mappings[0]["originalAnswer"] == "A"
    assert mappings[0]["variantAnswer"] == "C"
    assert mappings[0]["optionMapping"] == {"A": "C", "B": "D", "C": "A", "D": "B"}

    assert mappings[2]["passageId"] == "p1"
    assert mappings[2]["originalNumber"] == 1
    assert mappings[2]["optionsShuffled"] is True
    assert mappings[2]["originalAnswer"] == "B"
    assert mappings[2]["variantAnswer"] == "D"

    assert mappings[3]["passageId"] == "p1"
    assert mappings[3]["originalNumber"] == 2
    assert mappings[3]["optionsShuffled"] is False
    assert mappings[3]["originalAnswer"] == "D"
    assert mappings[3]["variantAnswer"] == "D"

    assert response["passageGroups"] == [
        {
            "passageId": "p1",
            "groupId": None,
            "label": "Ngữ liệu p1 (Ngữ liệu 1)",
            "originalNumbers": [1, 2],
            "questionNumbers": [3, 4],
            "contiguous": True,
        },
        {
            "passageId": "p2",
            "groupId": None,
            "label": "Ngữ liệu p2 (Ngữ liệu <script>alert(9)</script> 2)",
            "originalNumbers": [3, 4],
            "questionNumbers": [1, 2],
            "contiguous": True,
        },
    ]


@pytest.mark.parametrize("fmt", ["html", "docx"])
def test_variant_pack_teacher_key_and_zero_leak_student_html_and_docx(fmt, tmp_path):
    exam = _two_passage_exam()
    ids = ["p1_q1", "p1_q2", "p2_q1", "p2_q2"]
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        batch = (
            client.post(
                "/api/save-export",
                json={
                    "type": "variant-pack",
                    "exam": exam,
                    "format": fmt,
                    "questionIds": ids,
                    "shuffleOptions": True,
                    "teacher": True,
                },
            )
            .raise_for_status()
            .json()
        )
        archive_bytes = client.get(batch["url"]).raise_for_status().content

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        # 2 khối ngữ liệu -> đúng 2 mã đề 101 và 102 (không sinh thừa mã lỗi).
        assert archive.namelist() == [
            f"HOC_SINH/Ma_101.{fmt}",
            f"HOC_SINH/Ma_102.{fmt}",
            "GIAO_VIEN/Doi_chieu_dap_an.html",
        ]
        key = archive.read("GIAO_VIEN/Doi_chieu_dap_an.html").decode("utf-8")

        # Giữ nguyên chuỗi <small>(gốc: {source})</small> và thoát HTML chống XSS.
        assert "<script>" not in key
        assert "&lt;script&gt;alert(9)&lt;/script&gt;" in key
        assert "A <small>(gốc: 1)</small>" in key
        assert "D <small>(gốc: 1)</small>" in key
        assert "D <small>(gốc: 2)</small>" in key
        assert "C <small>(gốc: 3)</small>" in key

        # Hiển thị ánh xạ phương án PA gốc cho câu đã trộn.
        assert "PA gốc B → A" in key
        assert "PA gốc B → D" in key
        assert "PA gốc A → C" in key

        # Nhãn nhóm ngữ liệu và tóm tắt xác nhận bảo toàn tính liên tục qua các mã.
        assert "Ngữ liệu p1" in key and "Ngữ liệu p2" in key
        assert "Tóm tắt bảo toàn khối ngữ liệu" in key
        assert "Mã 101: Câu 1–2 (liên tục)" in key
        assert "Mã 102: Câu 3–4 (liên tục)" in key
        assert "Mã 101: Câu 3–4 (liên tục)" in key
        assert "Mã 102: Câu 1–2 (liên tục)" in key
        assert "Giữ nguyên liên tục qua tất cả các mã đề." in key

        # Kiểm bản học sinh (HTML hoặc DOCX): 0 rò đáp án/lời giải/barem/nguồn/trường nội bộ.
        for code in (101, 102):
            raw = archive.read(f"HOC_SINH/Ma_{code}.{fmt}")
            if fmt == "html":
                text = raw.decode("utf-8")
            else:
                with zipfile.ZipFile(io.BytesIO(raw)) as docx_zip:
                    root = ET.fromstring(docx_zip.read("word/document.xml"))
                text = "".join(root.itertext())

            assert f"Mã đề {code}" in text
            for forbidden in (
                "LOI_GIAI_BI_MAT",
                "BAREM_BI_MAT",
                "NGUON_BI_MAT",
                "Đáp án",
                "PA gốc",
                "optionMapping",
                "optionsShuffled",
                "originalAnswer",
                "variantAnswer",
                "Tóm tắt bảo toàn khối ngữ liệu",
            ):
                assert forbidden not in text

            pos_p1_1 = text.index("Nội dung chính đoạn 1 là gì?")
            pos_p1_2 = text.index("Nhân vật nào xuất hiện ở đoạn 1?")
            pos_p2_1 = text.index("Ý nghĩa hình ảnh con thuyền ở đoạn 2?")
            pos_p2_2 = text.index("Biện pháp tu từ nổi bật ở đoạn 2 là gì?")
            if code == 101:
                assert pos_p1_1 < pos_p1_2 < pos_p2_1 < pos_p2_2
            else:
                assert pos_p2_1 < pos_p2_2 < pos_p1_1 < pos_p1_2
