"""CMD tạo đề riêng, không xóa đề đang có hoặc tự giả lập kết quả."""

import importlib.util
from pathlib import Path

import pytest


def test_cmd_creates_distinct_empty_drafts_without_teacher_approval():
    script = Path(__file__).resolve().parents[2] / "scripts/chay-poc-app.py"
    spec = importlib.util.spec_from_file_location("poc_app_cmd", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sample = {
        "subject": "Ngữ văn",
        "grade": "6",
        "matrix": [{"topic": "Đọc hiểu", "targets": [1, 1, 0]}],
        "text": "Ngữ liệu tự viết",
    }
    first, second = module.make_exam(sample), module.make_exam(sample)
    assert first["id"] != second["id"]
    assert first["questions"] == [] and first["revision"] == 1
    assert first["quote"]["chosen"] is None
    assert first["history"] == []
    assert sum(first["matrix"][0]["targets"]) == 2


def test_biology_dataset_matches_team_matrix_without_reference_answers():
    script = Path(__file__).resolve().parents[2] / "scripts/chay-poc-app.py"
    spec = importlib.util.spec_from_file_location("poc_app_cmd", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sample = module.load_sample("bio-tham-thau")
    assert sample["subject"] == "Sinh học"
    assert [row["targets"] for row in sample["matrix"]] == [[1, 1, 0], [1, 0, 1]]
    assert all(marker in sample["text"] for marker in ["S1.", "S2.", "S3.", "cùng nhiệt độ"])
    assert "Đáp án" not in sample["text"]
    assert "chưa được giáo viên duyệt" in sample["instructions"]


def test_cmd_routes_qwen_generation_to_ollama_while_keeping_gemini_reviewer(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/chay-poc-app.py"
    spec = importlib.util.spec_from_file_location("poc_app_cmd", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    def request(route, body=None, **_):
        calls.append((route, body))
        if route == "/api/status":
            raise RuntimeError("Dừng trước khi tạo tác vụ thật.")
        return {}

    module.request = request
    with pytest.raises(RuntimeError, match="Dừng trước"):
        module.run(
            tmp_path,
            generator_provider="ollama",
            generator_model="qwen3:4b-instruct-2507-q4_K_M",
            review_model="gemini-3.6-flash",
        )
    assert calls[0] == (
        "/api/config",
        {
            "routes": {"generate": "ollama", "check": "gemini"},
            "ollama": {"model": "qwen3:4b-instruct-2507-q4_K_M"},
            "gemini": {"checkModel": "gemini-3.6-flash"},
        },
    )
