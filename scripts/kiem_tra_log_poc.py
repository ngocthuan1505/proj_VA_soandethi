"""Đối chiếu log PoC với request/response đã lưu, không gọi model hoặc sửa log."""

import argparse
import json
from itertools import pairwise
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tool_calls(response, protocol):
    message = response.get("message", {})
    if protocol == "structured":
        action = json.loads(message.get("content", "{}"))
        if isinstance(action, dict) and "action" in action:
            return [{"name": action["action"], "arguments": action.get("arguments")}]
        return []
    return [item.get("function", {}) for item in message.get("tool_calls", [])]


def feedback_matches(request, report):
    for message in request.get("messages", []):
        try:
            content = json.loads(message.get("content", ""))
            if message.get("role") == "tool" and message.get("tool_name") == "check_exam":
                if content == report:
                    return True
            if isinstance(content, dict) and content.get("toolResult") == "check_exam":
                if json.loads(content["result"]) == report:
                    return True
        except (ValueError, TypeError, KeyError):
            continue
    return False


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
                checks.append(
                    {
                        "index": index,
                        "modelCall": active_call,
                        "attempt": event.get("generationAttempt"),
                        "arguments": action.get("arguments"),
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
                )
        elif event.get("event") == "generation_result" and checks:
            if event.get("generationAttempt") != checks[-1]["attempt"]:
                issues.append(f"Số lần kiểm ở sự kiện {index + 1} không khớp lời gọi công cụ.")
            checks[-1]["report"] = {
                k: v
                for k, v in event.items()
                if k not in {"event", "utc", "elapsedSeconds", "generationAttempt"}
            }

    repairs = []
    for previous, current in pairwise(checks):
        if not previous["report"] or previous["report"].get("ok") is not False:
            continue
        between = [c for c in calls if previous["index"] < c["index"] < current["index"]]
        feedback = any(feedback_matches(c["request"], previous["report"]) for c in between)
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
                "recheckCompleted": current["report"] is not None,
                "recheckPassed": bool(current["report"] and current["report"].get("ok") is True),
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
