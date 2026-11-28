"""Chạy PoC qua chính API app; key giữ ở app, CMD không đọc hoặc nhận key."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

BASE = "http://127.0.0.1:4182"


def request(route, body=None, *, method=None, revision=None, config_fingerprint=None):
    headers = {"Origin": BASE, "Content-Type": "application/json"}
    if revision is not None:
        headers["If-Match"] = str(revision)
    if config_fingerprint:
        headers["X-PoC-Config"] = config_fingerprint
    req = urllib.request.Request(
        BASE + route,
        data=None if body is None else json.dumps(body, ensure_ascii=False).encode(),
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"App trả HTTP {error.code}: {error.read(2048).decode('utf8')}"
        ) from None


def make_exam(sample):
    return {
        "id": str(uuid4()),
        "revision": 1,
        "subject": sample["subject"],
        "grade": sample["grade"],
        "title": "PoC sinh theo ma trận · ngữ liệu tự viết · chạy CMD",
        "minutes": 15,
        "school": "BỘ THỬ PoC",
        "instructions": "Chọn một phương án đúng.",
        "aiInstructions": sample.get("instructions", ""),
        "questions": [],
        "docs": [],
        "data": [],
        "appliedPrefs": [],
        "matrix": sample["matrix"],
        "matrixConfirmed": True,
        "quote": {"text": sample["text"], "chosen": None, "versions": []},
        "layout": {"font": "Arial", "fontSize": 15},
        "history": [],
        "undo": [],
        "redo": [],
        "chat": [],
        "updated": int(time.time() * 1000),
        "sample": False,
    }


def load_sample(dataset):
    data = json.loads(
        (Path(__file__).resolve().parents[1] / "backend/poc-data" / (dataset + ".json")).read_text(
            encoding="utf8"
        )
    )
    matrix = {}
    for slot in data["slots"]:
        assert slot["type"] == "mcq" and slot["pointsQ4"] == 10
        matrix.setdefault(slot["topic"], [0, 0, 0])[slot["level"]] += 1
    return {
        "subject": data["subject"],
        "grade": data["grade"],
        "text": "\n\n".join(s["text"] for s in data["sources"]),
        "matrix": [{"topic": topic, "targets": targets} for topic, targets in matrix.items()],
        "dataset": dataset,
        "instructions": data["instructions"],
    }


def run(
    output,
    dataset="bio-tham-thau",
    *,
    generator_model=None,
    review_model=None,
    generator_provider="gemini",
):
    if generator_provider not in {"gemini", "ollama"}:
        raise ValueError("Chọn Gemini hoặc Ollama cho model sinh.")
    if generator_model or review_model or generator_provider == "ollama":
        update = {
            "gemini": {},
            "ollama": {},
            "routes": {
                "generate": generator_provider,
                "check": "gemini",
            },
        }
        if generator_model:
            update[generator_provider]["model"] = generator_model
        if review_model:
            update["gemini"]["checkModel"] = review_model
        request("/api/config", update)
    status = request("/api/status")
    config = status.get("config", {})
    if not (
        status.get("matrixAgent")
        and status.get("aiProvider") == generator_provider
        and config.get("gemini", {}).get("hasKey")
        and config["gemini"].get("freeTierConfirmed")
    ):
        raise RuntimeError("Mở Kết nối AI trong app, chọn Gemini và lưu key/Free tier trước.")
    output.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")

    started = time.perf_counter()
    sample = load_sample(dataset)
    exam = make_exam(sample)
    prior = request("/api/kv?key=state")
    state = prior["value"] or {"exams": [], "prefs": []}
    state["exams"].append(exam)
    state["current"] = exam["id"]
    request("/api/kv", {"key": "state", "value": state}, method="PUT", revision=prior["revision"])
    prefix = "/api/exams/" + exam["id"]
    approval = request(
        prefix + "/matrix/approve",
        {
            "baseRevision": 1,
            "sourceText": sample["text"],
            "sourceName": "Ngữ liệu nhóm tự viết cho PoC",
        },
    )
    save("input.json", {"sample": sample, "approval": approval, "examId": exam["id"]})
    submission = request(
        prefix + "/proposals/generate",
        {
            **approval,
            "requestId": str(uuid4()),
            "consent": True,
            "requireEvidence": True,
        },
        config_fingerprint=config.get("fingerprint"),
    )
    save("submission.json", submission)
    base = prefix + "/proposals/" + submission["jobId"]
    print(f"Model: {status['model']} | Tác vụ: {submission['jobId']}", flush=True)
    print(
        f"Ngân sách: {status.get('runBudget', {})}. Tự kiểm/sửa; không tự xác nhận/lưu.", flush=True
    )
    seen = 0
    while time.perf_counter() - started < 930:
        trace = request(base + "/trace")
        for row in trace[seen:]:
            print(json.dumps(row, ensure_ascii=False), flush=True)
        seen = len(trace)
        result = request(base + "/status")
        if result["status"] != "running":
            break
        time.sleep(1)
    else:
        raise RuntimeError("CMD đã hết thời gian chờ; kiểm trạng thái app trước khi chạy lại.")
    current = next(
        e for e in request("/api/kv?key=state")["value"]["exams"] if e["id"] == exam["id"]
    )
    assert current["revision"] == 1 and current["questions"] == []
    save("trace.json", request(base + "/trace"))
    checks = request(base + "/report")
    save("checks.json", checks)
    summary = {
        "at": datetime.now(UTC).isoformat(),
        "provider": status["aiProvider"],
        "model": status["model"],
        "seconds": round(time.perf_counter() - started, 6),
        "job": result,
        "savedQuestionCount": 0,
        "revision": 1,
        "teacherConfirmed": False,
        "reviewer": status.get("reviewer"),
        "budget": status.get("runBudget"),
        "checks": checks,
    }
    save("result.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Thư mục log mới, chưa tồn tại")
    parser.add_argument("--dataset", choices=["thu-vien", "bio-tham-thau"], default="bio-tham-thau")
    parser.add_argument("--generator-model", help="Đổi riêng model sinh Gemini/Ollama được cho phép")
    parser.add_argument("--generator-provider", choices=["gemini", "ollama"], default="gemini")
    parser.add_argument("--review-model", help="Model kiểm Gemini giữ cố định cho các lượt so sánh")
    parser.add_argument(
        "--run", action="store_true", help="Gọi Gemini thật bằng ngữ liệu tự viết của bộ thử"
    )
    args = parser.parse_args()
    if not args.run:
        parser.error("Thêm --run khi đã sẵn sàng dùng hạn mức Gemini.")
    run(
        args.output,
        args.dataset,
        generator_model=args.generator_model,
        review_model=args.review_model,
        generator_provider=args.generator_provider,
    )
