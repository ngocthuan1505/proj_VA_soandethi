"""Ngân sách dùng chung và báo cáo kiểm đúng bản đề của một tác vụ PoC."""

import time
from typing import Annotated, Any, Literal

from pydantic import Field

from mach_backend.ai_contract import AIError, ContractModel


class RunPolicy(ContractModel):
    maxModelCalls: Annotated[int, Field(ge=4, le=64)] = 24
    timeoutSeconds: Annotated[int, Field(ge=30, le=900)] = 900


class CallBudget:
    def __init__(self, max_calls=24, seconds=900):
        if type(max_calls) is not int or not 1 <= max_calls <= 64 or not 0 < seconds <= 900:
            raise ValueError("Ngân sách gọi AI hoặc thời gian không hợp lệ.")
        self.max_calls, self.deadline, self.calls = max_calls, time.monotonic() + seconds, 0

    def remaining(self):
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise AIError("timeout", "Đã hết thời gian tự xử lý; bản đề giữ nguyên.")
        return seconds

    def spend(self):
        self.remaining()
        if self.calls >= self.max_calls:
            raise AIError("call_budget", "Đã hết ngân sách gọi AI; bản đề giữ nguyên.")
        self.calls += 1


CHECK_NAMES = (
    "validate_schema",
    "check_matrix_and_scoring",
    "retrieve_evidence",
    "check_evidence",
    "solve_blind",
    "verify_options",
    "review_level",
    "check_duplicates",
    "check_explanation",
    "aggregate_checks",
)


class CheckReport(ContractModel):
    toolName: Annotated[str, Field(pattern="^(" + "|".join(CHECK_NAMES) + ")$")]
    candidateHash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    findings: tuple[dict[str, Any], ...] = ()
    durationMs: Annotated[int, Field(ge=0)] = 0


class CandidateChecks:
    def __init__(self, candidate_hash, emit):
        self.candidate_hash, self.emit = candidate_hash, emit
        self.reports = {
            name: CheckReport(toolName=name, candidateHash=candidate_hash, status="UNKNOWN")
            for name in CHECK_NAMES
        }

    def record(self, name, *, status="PASS", findings=(), started=None):
        report = CheckReport(
            toolName=name,
            candidateHash=self.candidate_hash,
            status=status,
            findings=tuple(findings),
            durationMs=max(0, round((time.perf_counter() - started) * 1000)) if started else 0,
        )
        self.reports[name] = report
        self.emit("check_report", **report.model_dump(mode="json"))

    def finish(self, errors):
        required = [v for k, v in self.reports.items() if k != "aggregate_checks"]
        status = (
            "FAIL"
            if errors or any(r.status == "FAIL" for r in required)
            else "UNKNOWN"
            if any(r.status == "UNKNOWN" for r in required)
            else "PASS"
        )
        self.record("aggregate_checks", status=status, findings=errors)
        return {
            "ok": status == "PASS",
            "candidateHash": self.candidate_hash,
            "errors": errors,
            "checks": [r.model_dump(mode="json") for r in self.reports.values()],
        }


def report_from_trace(events):
    start = next(
        (
            i
            for i in range(len(events) - 1, -1, -1)
            if events[i].get("event") == "tool_call" and events[i].get("tool") == "check_exam"
        ),
        None,
    )
    if start is None:
        return {}
    current = events[start + 1 :]
    complete = next((e for e in reversed(current) if e.get("event") == "generation_result"), None)
    if complete:
        return complete
    rows = [e for e in current if e.get("event") == "check_report"]
    if not rows:
        return {"generationAttempt": events[start].get("generationAttempt")}
    candidate = rows[-1]["candidateHash"]
    checks = {
        name: CheckReport(toolName=name, candidateHash=candidate, status="UNKNOWN").model_dump(
            mode="json"
        )
        for name in CHECK_NAMES
    }
    for row in rows:
        if row.get("candidateHash") == candidate and row.get("toolName") in checks:
            checks[row["toolName"]].update(
                {k: row[k] for k in CheckReport.model_fields if k in row}
            )
    errors = [
        error
        for e in current
        if e.get("event") == "blind_content_check"
        for error in e.get("errors", [])
    ]
    missing = [name for name, row in checks.items() if row["status"] == "UNKNOWN"]
    if missing:
        errors.append({"code": "check_not_completed", "checks": missing})
    return {
        "generationAttempt": events[start].get("generationAttempt"),
        "candidateHash": candidate,
        "checks": list(checks.values()),
        "errors": errors,
    }
