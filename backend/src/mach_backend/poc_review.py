"""Phiếu tự giải trước khi xem đáp án AI, kế thừa quy trình rà độc lập của nhánh PoC."""

import html
import io
import json
import re
import zipfile

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import points_p100, saved_answer_label
from mach_backend.export_assets import render_assets
from mach_backend.local_documents import chrome_path
from mach_backend.matrix_agent import sha256_json
from mach_backend.word_export import math_parts

LEVELS = ("Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao")


def review_pack(pending, result, audit):
    report = result.get("report", {})
    candidate = report.get("candidateHash", "")
    if (
        not isinstance(candidate, str)
        or re.fullmatch(r"[a-f0-9]{64}", candidate) is None
        or result.get("proposalSha256") != sha256_json(pending.proposal.model_dump(mode="json"))
    ):
        raise AIError("needs_review", "Chưa có báo cáo khớp bộ đề xuất để tạo phiếu rà.")

    content = [source.text for source in pending.job.sources]
    for question in pending.proposal.questions:
        content.extend([question.stem, question.explanation, *question.options])
        content.extend(step.text for step in question.rubric)
        content.extend(e.quote for e in question.evidence)
        if isinstance(question.answer, str):
            content.append(question.answer)
    formulas = [value for item in content for is_math, value in math_parts(item) if is_math]
    rendered = render_assets(formulas, [], chrome_path())["math"]

    def formatted(value):
        return "".join(
            '<span class="formula">' + rendered[part] + "</span>"
            if is_math
            else html.escape(part).replace("\n", "<br>")
            for is_math, part in math_parts(str(value))
        )

    def text(value):
        return html.escape(str(value))

    identity = (
        f"<p>{text(pending.job.subject)} · Lớp {text(pending.job.grade)} · "
        f"Job {pending.job.jobId}</p><p>Mã bản: <code>{text(candidate)}</code></p>"
    )
    sources = "<h2>Ngữ liệu dùng sinh câu</h2>" + "".join(
        f"<blockquote>{formatted(s.text)}</blockquote>" for s in pending.job.sources
    )
    questions, answers = [], []
    for index, question in enumerate(pending.proposal.questions, 1):
        questions.append(
            f"<section><h2>Câu {index}</h2><p>{formatted(question.stem)}</p><ol type='A'>"
            + "".join(f"<li>{formatted(option)}</li>" for option in question.options)
            + "</ol><p>Đáp án tự giải / các phương án cùng hợp lý: __________________</p>"
            "<p>Đáp án/nhận định/lời giải có đủ căn cứ không? Lý do: __________________</p>"
            "<p>Học sinh cần thực hiện thao tác gì? __________________</p>"
            "<p>Mức thực tế (NB/TH/VD/VDC/chưa kết luận) và lý do: __________________</p></section>"
        )
        answers.append(
            f"<section><h2>Câu {index} · Yêu cầu {LEVELS[question.level]}</h2>"
            "<p>Đáp án AI đề xuất: "
            + formatted(
                "Tự luận · chấm theo barem"
                if question.type == "essay"
                else saved_answer_label(question.model_dump(mode="json"))
            )
            + "</p>"
            f"<p>Lời giải AI: {formatted(question.explanation)}</p>"
            + "".join(
                f"<p>Bước {i}: {formatted(step.text)} · {points_p100(step) / 100} điểm</p>"
                for i, step in enumerate(question.rubric, 1)
            )
            + "".join(f"<blockquote>{formatted(e.quote)}</blockquote>" for e in question.evidence)
            + "<p>Sau đối chiếu: giữ / sửa / chưa kết luận. Lý do: __________________</p></section>"
        )

    def page(title, content):
        return (
            '<!doctype html><html lang="vi"><meta charset="utf-8">'
            f"<title>{title}</title><style>body{{max-width:850px;margin:32px auto;"
            "font:17px/1.6 Arial;padding:20px}blockquote{white-space:pre-wrap;"
            "border-left:3px solid #777;padding-left:16px}code{overflow-wrap:anywhere}"
            "section{break-inside:avoid;margin-bottom:40px}.formula{display:inline-block;"
            "max-width:100%;overflow-x:auto;vertical-align:middle}math{font-size:1.1em}</style>"
            f"<h1>{title}</h1>{identity}{content}</html>"
        )

    first = page(
        "1. Tự giải và nhận định độc lập",
        "<p>Người rà: __________________ · Thời điểm: __________________</p>"
        "<p>Chỉ mở file 2 sau khi đã lưu câu trả lời của mình. Phiếu này chưa có nhãn "
        "chuyên gia và không tự công nhận bộ câu đúng.</p>" + sources + "".join(questions),
    )
    second = page(
        "2. Đối chiếu sau khi tự giải",
        "<p>Đây là đáp án/nhận xét của AI, không phải đáp án chuẩn đã được giáo viên duyệt. "
        "Ghi cả lỗi bộ kiểm bỏ sót, chặn nhầm hoặc chưa kết luận.</p>" + "".join(answers),
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("1_TU_GIAI_TRUOC.html", first)
        archive.writestr("2_DOI_CHIEU_SAU.html", second)
        archive.writestr("bao-cao-kiem.json", json.dumps(report, ensure_ascii=False, indent=2))
        archive.writestr("doi-chieu-log.json", json.dumps(audit, ensure_ascii=False, indent=2))
    return output.getvalue()
