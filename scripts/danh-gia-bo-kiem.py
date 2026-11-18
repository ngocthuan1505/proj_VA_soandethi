"""Tạo phiếu rà và tính lỗi bộ kiểm từ nhãn đã được người rà cung cấp; không gọi AI."""

import argparse
import hashlib
import json
from pathlib import Path

STATUSES = {"PASS", "FAIL", "UNKNOWN"}
AGENT_LOGS = Path(__file__).resolve().parents[1] / "outputs/local-demo/data/agent-logs"


def prepare(report):
    candidate = report.get("candidateHash")
    checks = report.get("checks", [])
    if not isinstance(candidate, str) or len(candidate) != 64 or not checks:
        raise ValueError("Cần báo cáo có candidateHash và các phép kiểm.")
    names = set()
    rows = []
    for check in checks:
        name, status = check["toolName"], check["status"]
        if name in names or check["candidateHash"] != candidate or status not in STATUSES:
            raise ValueError("Báo cáo lặp phép kiểm, sai bản đề hoặc trạng thái không hợp lệ.")
        names.add(name)
        rows.append(
            {
                "toolName": name,
                "candidateHash": candidate,
                "observedStatus": status,
                "findings": check.get("findings", []),
                "expectedStatus": None,
                "referenceKind": "pending",
                "confirmedBy": "",
                "reason": "",
            }
        )
    return {
        "note": "Tự đối chiếu câu/nguồn trước khi điền nhãn. "
        "Không dùng nhãn AI làm nhãn chuyên gia.",
        "cases": rows,
    }


def evaluate(manifest):
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 10000:
        raise ValueError("Cần từ 1 đến 10000 dòng rà.")
    pending, groups = 0, {}
    for row in cases:
        observed, expected = row.get("observedStatus"), row.get("expectedStatus")
        if observed not in STATUSES or expected not in {*STATUSES, None}:
            raise ValueError("Nhãn phải là PASS, FAIL, UNKNOWN hoặc để trống khi chưa rà.")
        kind = row.get("referenceKind", "pending")
        if kind not in {"pending", "mechanism", "expert"}:
            raise ValueError("referenceKind phải là pending, mechanism hoặc expert.")
        if (
            expected is None
            or expected == "UNKNOWN"
            or kind == "pending"
            or not row.get("confirmedBy")
        ):
            pending += 1
            continue
        if not row.get("reason", "").strip():
            raise ValueError("Nhãn đã chốt phải có lý do và người rà.")
        key = (kind, row["toolName"])
        group = groups.setdefault(
            key,
            {
                "referenceKind": kind,
                "toolName": row["toolName"],
                "labels": 0,
                "bad": 0,
                "clean": 0,
                "detected": 0,
                "missed": 0,
                "falseBlocked": 0,
                "unknown": 0,
            },
        )
        group["labels"] += 1
        group["bad" if expected == "FAIL" else "clean"] += 1
        if observed == "UNKNOWN":
            group["unknown"] += 1
        elif expected == "FAIL" and observed == "FAIL":
            group["detected"] += 1
        elif expected == "FAIL" and observed == "PASS":
            group["missed"] += 1
        elif expected == "PASS" and observed == "FAIL":
            group["falseBlocked"] += 1
    for group in groups.values():
        group["detectionRate"] = group["detected"] / group["bad"] if group["bad"] else None
        group["falseBlockRate"] = group["falseBlocked"] / group["clean"] if group["clean"] else None
        group["unknownRate"] = group["unknown"] / group["labels"]
    return {
        "total": len(cases),
        "pending": pending,
        "groups": list(groups.values()),
        "pedagogicalApproval": False,
        "note": "Chỉ tính theo nhãn người rà cung cấp. "
        "Chuyên môn người rà chưa được công cụ xác minh. "
        "Cohort mechanism kiểm phần mềm, không là kết quả đánh giá sư phạm. "
        "UNKNOWN vẫn nằm trong mẫu số, không được tính là phát hiện đúng.",
    }


def compare_runs(directories):
    if not 2 <= len(directories) <= 100:
        raise ValueError("Chọn từ 2 đến 100 thư mục chạy để đối chiếu.")
    rows, fingerprints = [], []
    for directory in directories:
        path = Path(directory)

        def read(name, run_path=path):
            return json.loads((run_path / name).read_text(encoding="utf-8-sig"))

        data = read("result.json") if (path / "result.json").exists() else {}
        inputs = read("input.json")
        job = data.get("job", {})
        metadata = data.get("checks", {}).get("summary") or {}
        environment_path = AGENT_LOGS / str(job.get("jobId", "")) / "environment.json"
        environment = (
            json.loads(environment_path.read_text(encoding="utf8"))
            if environment_path.is_file()
            else {}
        )
        events_path = environment_path.parent / "events.jsonl"
        events = (
            [json.loads(line) for line in events_path.read_text(encoding="utf8").splitlines()]
            if events_path.is_file()
            else []
        )
        reviewer = metadata.get("reviewer") or environment.get("reviewer")
        policy = metadata.get("budget") or environment.get("runPolicy")
        comparable = {
            "source": inputs["sample"]["text"],
            "plan": inputs["approval"]["plan"],
            "reviewer": reviewer,
            "budget": policy,
            "code": environment.get("sourceSha256"),
            "protocol": environment.get("toolProtocol"),
        }
        fingerprint = hashlib.sha256(
            json.dumps(comparable, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        fingerprints.append(
            fingerprint if reviewer and policy and environment.get("sourceSha256") else None
        )
        rows.append(
            {
                "directory": str(path),
                "generatorModel": data.get("model"),
                "generatorProvider": data.get("provider"),
                "mode": environment.get("mode"),
                "reviewer": reviewer,
                "status": job.get("status", "interrupted"),
                "clientSeconds": data.get("seconds"),
                "modelCalls": metadata.get("modelCalls"),
                "firstDraftSeconds": next(
                    (
                        e.get("elapsedSeconds")
                        for e in events
                        if e.get("event") == "tool_call" and e.get("tool") == "check_exam"
                    ),
                    None,
                ),
                "readySeconds": metadata.get("elapsedSeconds")
                if job.get("status") == "complete"
                else None,
                "callMetrics": metadata.get("calls", []),
                "submissions": data.get("checks", {}).get("generationAttempt"),
                "ready": job.get("status") == "complete",
                "teacherConfirmed": data.get("teacherConfirmed", False),
            }
        )
    controlled = all(fingerprints) and len(set(fingerprints)) == 1
    return {
        "runs": rows,
        "totalRuns": len(rows),
        "controlledComparison": bool(controlled),
        "pedagogicalApproval": False,
        "note": "Giữ cả lượt lỗi/gián đoạn trong bảng. Chỉ so riêng model sinh khi nguồn, ma trận, "
        "rubric, bộ kiểm và ngân sách giống nhau. Một lượt/model chưa đủ xếp hạng; "
        "trạng thái complete không thay chấm chuyên môn.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path, help="Báo cáo checks.json từ app/CMD")
    mode.add_argument("--evaluate", type=Path, help="Phiếu JSON có nhãn người rà")
    mode.add_argument(
        "--compare", type=Path, nargs="+", help="Các thư mục log CMD, giữ cả lượt thất bại"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.compare:
            result = compare_runs(args.compare)
        else:
            payload = json.loads((args.prepare or args.evaluate).read_text(encoding="utf-8-sig"))
            result = prepare(payload) if args.prepare else evaluate(payload)
        with args.output.open("x", encoding="utf8") as file:
            file.write(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
