"""Đối chiếu log PoC với request/response đã lưu, không gọi model hoặc sửa log."""

import argparse
import json
from itertools import pairwise
from pathlib import Path

from mach_backend.poc_policy import CHECK_NAMES


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tool_calls(response, protocol):
    choices = response.get("choices", [])
    message = response.get("message") or (choices[0]["message"] if len(choices) == 1 else {})
    if protocol == "structured":
        action = json.loads(message.get("content", "{}"))
        if isinstance(action, dict) and "action" in action:
            return [{"name": action["action"], "arguments": action.get("arguments")}]
        return []
    calls = []
    for item in message.get("tool_calls", []):
        function = item.get("function", {})
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        calls.append({**function, "arguments": arguments, "id": item.get("id")})
    return calls


def feedback_matches(request, report, call_id=None):
    compact = {k: v for k, v in report.items() if k not in {"checks", "reviews", "explanations"}}
    for message in request.get("messages", []):
        try:
            content = json.loads(message.get("content", ""))
            if message.get("role") == "tool":
                identity_matches = (
                    bool(call_id) and message.get("tool_call_id") == call_id
                    if "tool_call_id" in message
                    else call_id is None and message.get("tool_name") == "check_exam"
                )
                if identity_matches and content in (report, compact):
                    return True
            if isinstance(content, dict) and content.get("toolResult") == "check_exam":
                result = content["result"]
                if isinstance(result, str):
                    result = json.loads(result)
                if result in (report, compact):
                    return True
        except (ValueError, TypeError, KeyError):
            continue
    return False


def repair_submission(request, arguments, previous):
    messages = request.get("messages", [])
    if len(messages) < 2 or messages[1].get("role") != "user":
        return arguments
    try:
        assignment = json.loads(messages[1].get("content", ""))
    except (ValueError, TypeError):
        return arguments
    if not isinstance(assignment, dict) or "repairOrdinals" not in assignment:
        return arguments
    if previous is None or previous["report"] is None:
        raise ValueError("Thiếu lần kiểm gốc cho lượt sửa theo câu.")
    baseline = (previous["arguments"] or {}).get("questions")
    errors = previous["report"].get("errors", [])
    indices = assignment["repairOrdinals"]
    if (
        not isinstance(baseline, list)
        or any(not isinstance(row, dict) for row in baseline)
        or not isinstance(indices, list)
        or not indices
        or any(type(i) is not int or not 0 <= i < len(baseline) for i in indices)
        or any(type(e.get("ordinal")) is not int for e in errors)
        or indices != sorted({e["ordinal"] for e in errors})
        or assignment.get("previousStems") != [row.get("stem") for row in baseline]
        or not feedback_matches(request, previous["report"], previous["callId"])
    ):
        raise ValueError("Phạm vi sửa không khớp bộ câu và lỗi trước đó.")
    replacements = arguments.get("questions") if isinstance(arguments, dict) else None
    if (
        not isinstance(replacements, list)
        or len(replacements) != len(indices)
        or set(arguments) != {"questions"}
    ):
        return {}
    if (stem := assignment.get("plannedStem")) is not None and (
        len(replacements) != 1
        or not isinstance(replacements[0], dict)
        or replacements[0].get("stem") != stem
    ):
        return {}
    combined = baseline.copy()
    for index, question in zip(indices, replacements, strict=True):
        combined[index] = question
    return {"questions": combined}


def inspect_run(directory):
    events = [
        json.loads(line)
        for line in (directory / "events.jsonl").read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    start = next((e for e in events if e.get("event") == "run_start"), {})
    protocol = start.get("toolProtocol", "native")
    result_path = directory / "result.json"
    result = read_json(result_path) if result_path.exists() else {}
    checks, calls, issues = [], [], []
    pending_actions = []
    active_call = None
    finish_verified = False
    for index, event in enumerate(events):
        if event.get("event") == "model_start" and event.get("purpose") == "agent":
            active_call = event["modelCall"]
            request_path = directory / f"call-{active_call:02}-request.json"
            response_path = directory / f"call-{active_call:02}-response.json"
            request = read_json(request_path)
            actions = (
                tool_calls(read_json(response_path), protocol) if response_path.exists() else []
            )
            calls.append({"index": index, "number": active_call, "request": request})
            pending_actions = list(actions)
        elif event.get("event") == "tool_call":
            action = pending_actions.pop(0) if pending_actions else {}
            if action.get("name") != event.get("tool"):
                issues.append(f"Công cụ ở sự kiện {index + 1} không khớp phản hồi model đã lưu.")
            if event.get("tool") == "check_exam":
                finish_verified = False
                arguments = action.get("arguments")
                if protocol == "structured" and calls:
                    try:
                        arguments = repair_submission(
                            calls[-1]["request"], arguments, checks[-1] if checks else None
                        )
                    except ValueError as error:
                        issues.append(str(error))
                checks.append(
                    {
                        "index": index,
                        "modelCall": active_call,
                        "attempt": event.get("generationAttempt"),
                        "arguments": arguments,
                        "callId": action.get("id"),
                        "report": None,
                    }
                )
            if event.get("tool") == "finish_exam":
                finish_verified = bool(
                    action.get("name") == "finish_exam"
                    and action.get("arguments") == {}
                    and checks
                    and checks[-1]["report"]
                    and checks[-1]["report"].get("ok") is True
                    and checks[-1]["report"].get("reusedFromAttempt") is None
                )
        elif event.get("event") == "generation_result" and checks:
            if event.get("generationAttempt") != checks[-1]["attempt"]:
                issues.append(f"Số lần kiểm ở sự kiện {index + 1} không khớp lời gọi công cụ.")
            checks[-1]["report"] = {
                k: v
                for k, v in event.items()
                if k not in {"event", "utc", "elapsedSeconds", "generationAttempt"}
            }
            report = checks[-1]["report"]
            reused_from = report.get("reusedFromAttempt")
            if reused_from is not None and (
                report.get("ok") is not False
                or not isinstance(report.get("candidateHash"), str)
                or not any(
                    earlier["attempt"] == reused_from
                    and earlier["arguments"] == checks[-1]["arguments"]
                    and earlier["report"]
                    and earlier["report"].get("ok") is False
                    and earlier["report"].get("reusedFromAttempt") is None
                    and earlier["report"].get("candidateHash") == report["candidateHash"]
                    for earlier in checks[:-1]
                )
            ):
                issues.append(f"Báo cáo tái dùng ở sự kiện {index + 1} thiếu lần kiểm gốc phù hợp.")
            rows = report.get("checks")
            if (
                report.get("ok") is True
                and rows is not None
                and (
                    not isinstance(report.get("candidateHash"), str)
                    or len(report["candidateHash"]) != 64
                    or not isinstance(rows, list)
                    or len(rows) != len(CHECK_NAMES)
                    or any(not isinstance(row, dict) for row in rows)
                    or {row.get("toolName") for row in rows} != set(CHECK_NAMES)
                    or not all(
                        row.get("status") == "PASS"
                        and row.get("candidateHash") == report.get("candidateHash")
                        for row in rows
                    )
                )
            ):
                issues.append("Báo cáo đạt nhưng các phép kiểm còn thiếu, chưa đạt hoặc sai hash.")

    repairs = []
    for previous, current in pairwise(checks):
        if not previous["report"] or previous["report"].get("ok") is not False:
            continue
        between = [c for c in calls if previous["index"] < c["index"] < current["index"]]
        feedback = any(
            feedback_matches(c["request"], previous["report"], previous["callId"]) for c in between
        )
        if not feedback:
            issues.append(f"Không đối chiếu được phản hồi lỗi của lần nộp {previous['attempt']}.")
        repairs.append(
            {
                "fromAttempt": previous["attempt"],
                "toAttempt": current["attempt"],
                "feedbackInNextRequest": feedback,
                "candidateChanged": (
                    previous["arguments"] is not None
                    and current["arguments"] is not None
                    and previous["arguments"] != current["arguments"]
                ),
                "recheckCompleted": (
                    current["report"] is not None
                    and current["report"].get("reusedFromAttempt") is None
                ),
                "recheckPassed": bool(
                    current["report"]
                    and current["report"].get("reusedFromAttempt") is None
                    and current["report"].get("ok") is True
                ),
            }
        )
    if result.get("status") == "ready_for_teacher_review" and not finish_verified:
        issues.append("Kết quả báo sẵn sàng nhưng thiếu công cụ kết thúc sau lần kiểm đạt.")
    if result.get("saved") is True:
        issues.append("Log này báo đã lưu, vượt phạm vi bộ chạy PoC chỉ tạo đề xuất.")
    return {
        "trialId": start.get("trialId"),
        "recordedMode": start.get("mode"),
        "protocol": protocol,
        "completed": bool(result),
        "status": result.get("status", "incomplete"),
        "checkedAttempts": len(checks),
        "repairSteps": repairs,
        "successfulRepairObserved": any(
            r["feedbackInNextRequest"] and r["candidateChanged"] and r["recheckPassed"]
            for r in repairs
        )
        and not issues,
        "finishAfterPassedCheck": finish_verified,
        "traceVerified": bool(result) and bool(calls) and bool(checks) and not issues,
        "evidenceIssues": issues,
        "limit": (
            "Đối chiếu file log đã lưu. "
            "Chưa xác nhận chất lượng sư phạm hoặc nguồn gốc model độc lập."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        report = inspect_run(args.directory)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Chưa đọc được bộ log đầy đủ ({type(error).__name__}).\n")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 2 if report["evidenceIssues"] or not report["completed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
