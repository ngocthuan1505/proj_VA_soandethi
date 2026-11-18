"""Phiếu rà ngoại tuyến: dựng toán, giữ bí mật đáp án ở phiếu đầu."""

import io
import zipfile

import pytest
from test_mixed_questions import mixed as mixed

from mach_backend.ai_contract import AIError
from mach_backend.matrix_agent import candidate_proposal, sha256_json
from mach_backend.patch_confirmation import PendingGeneration
from mach_backend.poc_review import review_pack


def test_review_pack_renders_math_without_exposing_solution_or_executing_html(mixed, monkeypatch):
    job, arguments = mixed
    arguments["questions"][0]["stem"] = r"Tính $\frac{160}{2}$ <script>alert(1)</script>"
    arguments["questions"][2]["answer"] = "$80$"
    arguments["questions"][3]["explanation"] = r"BÍ MẬT $\sqrt{6400}=80$"
    proposal = candidate_proposal(job, arguments)
    calls = []

    def render(formulas, figures, chrome):
        calls.append(formulas)
        return {"math": {f: "<math><mn>80</mn></math>" for f in formulas}}

    monkeypatch.setattr("mach_backend.poc_review.render_assets", render)
    pending = PendingGeneration(job=job, proposal=proposal)
    result = {
        "report": {"candidateHash": "a" * 64},
        "proposalSha256": sha256_json(proposal.model_dump(mode="json")),
    }
    with zipfile.ZipFile(io.BytesIO(review_pack(pending, result, {}))) as archive:
        first = archive.read("1_TU_GIAI_TRUOC.html").decode()
        second = archive.read("2_DOI_CHIEU_SAU.html").decode()
    assert len(calls) == 1 and r"\frac{160}{2}" in calls[0]
    assert "<math>" in first and "<math>" in second
    assert "BÍ MẬT" not in first and "BÍ MẬT" in second
    assert "&lt;script&gt;" in first and "<script>" not in first
    assert r"\frac" not in first and r"\sqrt" not in second
    assert "Tự luận · chấm theo barem" in second
    assert "<script" not in second and "https://" not in first


def test_review_pack_reports_formula_failure_instead_of_silently_exporting_code(mixed, monkeypatch):
    job, arguments = mixed
    arguments["questions"][0]["stem"] = r"Tính $\unsupported{80}$"
    proposal = candidate_proposal(job, arguments)

    def invalid(*_args):
        raise AIError("invalid_math", "Công thức lỗi ở câu 1.")

    monkeypatch.setattr("mach_backend.poc_review.render_assets", invalid)
    with pytest.raises(AIError, match="Công thức lỗi"):
        review_pack(
            PendingGeneration(job=job, proposal=proposal),
            {
                "report": {"candidateHash": "b" * 64},
                "proposalSha256": sha256_json(proposal.model_dump(mode="json")),
            },
            {},
        )
