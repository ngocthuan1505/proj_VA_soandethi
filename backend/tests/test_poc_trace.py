"""Ca tổng hợp để kiểm công cụ đọc log, không phải số đo PoC model thật."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "src/mach_backend/poc_trace.py"
SPEC = importlib.util.spec_from_file_location("kiem_tra_log_poc", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TestPoCTrace(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def write_run(
        self, protocol="native", *, feedback=True, changed=True, finished=True, reused=None
    ):
        events = [
            {
                "event": "run_start",
                "trialId": "fixture",
                "mode": "fixture",
                "toolProtocol": "native" if protocol == "native" else "structured",
            }
        ]
        bad, good = {"ok": False, "errors": [{"code": "answer_disagreement"}]}, {"ok": True}
        if reused is not None:
            bad["candidateHash"] = "a" * 64
            good = {**bad, "reusedFromAttempt": reused}
        first, second = {"answer": 0}, {"answer": 1 if changed else 0}
        for number, (name, arguments, report) in enumerate(
            [("check_exam", first, bad), ("check_exam", second, good), ("finish_exam", {}, None)], 1
        ):
            messages = []
            if number > 1 and feedback:
                previous = bad if number == 2 else good
                if protocol == "native":
                    messages = [
                        {
                            "role": "tool",
                            "tool_name": "check_exam",
                            "content": json.dumps(previous),
                        }
                    ]
                else:
                    messages = [
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "toolResult": "check_exam",
                                    "result": json.dumps(previous)
                                    if protocol == "structured"
                                    else previous,
                                }
                            ),
                        }
                    ]
            message = {
                "role": "assistant",
                "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
            }
            if protocol != "native":
                message = {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "action": name,
                            "arguments": arguments,
                        }
                    ),
                }
            (self.directory / f"call-{number:02}-request.json").write_text(
                json.dumps({"messages": messages}), encoding="utf-8"
            )
            (self.directory / f"call-{number:02}-response.json").write_text(
                json.dumps({"message": message}), encoding="utf-8"
            )
            events.extend(
                [
                    {"event": "model_start", "purpose": "agent", "modelCall": number},
                    {"event": "tool_call", "tool": name, "generationAttempt": min(number, 2)},
                ]
            )
            if report is not None:
                events.append(
                    {
                        "event": "generation_result",
                        "generationAttempt": number,
                        **report,
                    }
                )
        (self.directory / "events.jsonl").write_text(
            "\n".join(map(json.dumps, events)), encoding="utf-8"
        )
        if finished:
            (self.directory / "result.json").write_text(
                json.dumps(
                    {
                        "status": "ready_for_teacher_review",
                        "saved": False,
                    }
                ),
                encoding="utf-8",
            )

    def test_native_and_structured_feedback_are_both_recognized(self):
        for protocol in ("native", "structured", "structured_object"):
            with self.subTest(protocol=protocol):
                self.write_run(protocol)
                report = MODULE.inspect_run(self.directory)
                self.assertTrue(report["successfulRepairObserved"])
                self.assertTrue(report["finishAfterPassedCheck"])
                self.assertEqual(report["evidenceIssues"], [])
                self.assertEqual(report["recordedMode"], "fixture")

    def test_changed_answer_without_feedback_does_not_prove_self_repair(self):
        self.write_run(feedback=False)
        report = MODULE.inspect_run(self.directory)
        self.assertFalse(report["successfulRepairObserved"])
        self.assertFalse(report["repairSteps"][0]["feedbackInNextRequest"])

    def test_rechecking_identical_content_does_not_prove_repair(self):
        self.write_run(changed=False)
        self.assertFalse(MODULE.inspect_run(self.directory)["successfulRepairObserved"])

    def test_reused_rejection_is_not_a_new_check(self):
        self.write_run(changed=False, finished=False, reused=1)
        report = MODULE.inspect_run(self.directory)
        self.assertEqual(report["evidenceIssues"], [])
        self.assertFalse(report["repairSteps"][0]["recheckCompleted"])
        self.assertFalse(report["repairSteps"][0]["recheckPassed"])
        self.assertFalse(report["successfulRepairObserved"])
        self.write_run(changed=False, finished=False, reused=2)
        self.assertTrue(MODULE.inspect_run(self.directory)["evidenceIssues"])

    def test_claimed_finish_needs_matching_response(self):
        self.write_run()
        path = self.directory / "call-03-response.json"
        path.write_text(json.dumps({"message": {"tool_calls": []}}), encoding="utf-8")
        report = MODULE.inspect_run(self.directory)
        self.assertFalse(report["finishAfterPassedCheck"])
        self.assertFalse(report["successfulRepairObserved"])
        self.assertTrue(report["evidenceIssues"])

    def test_running_log_is_reported_as_incomplete(self):
        self.write_run(finished=False)
        self.assertFalse(MODULE.inspect_run(self.directory)["completed"])

    def gemini_run(self):
        self.write_run()
        for number in range(1, 4):
            response = self.directory / f"call-{number:02}-response.json"
            message = json.loads(response.read_text(encoding="utf8"))["message"]
            call = message["tool_calls"][0]
            call["id"] = f"call-{number}"
            call["function"]["arguments"] = json.dumps(call["function"]["arguments"])
            response.write_text(json.dumps({"choices": [{"message": message}]}), encoding="utf8")
            request = self.directory / f"call-{number:02}-request.json"
            body = json.loads(request.read_text(encoding="utf8"))
            for entry in body["messages"]:
                entry.pop("tool_name", None)
                entry["tool_call_id"] = f"call-{number - 1}"
            request.write_text(json.dumps(body), encoding="utf8")

    def test_gemini_wire_ids_and_json_arguments_are_verified(self):
        self.gemini_run()
        report = MODULE.inspect_run(self.directory)
        self.assertTrue(report["traceVerified"])
        self.assertTrue(report["successfulRepairObserved"])
        self.assertTrue(report["finishAfterPassedCheck"])

    def test_wrong_gemini_tool_call_id_cannot_prove_feedback(self):
        self.gemini_run()
        request = self.directory / "call-02-request.json"
        body = json.loads(request.read_text(encoding="utf8"))
        body["messages"][0]["tool_call_id"] = "unrelated-call"
        request.write_text(json.dumps(body), encoding="utf8")
        report = MODULE.inspect_run(self.directory)
        self.assertFalse(report["traceVerified"])
        self.assertFalse(report["successfulRepairObserved"])

    def test_pass_report_cannot_reuse_other_candidate_hash(self):
        self.gemini_run()
        path = self.directory / "events.jsonl"
        events = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
        for event in events:
            if event.get("event") == "generation_result" and event["ok"]:
                event.update(
                    candidateHash="a" * 64,
                    checks=[
                        {"toolName": name, "status": "PASS", "candidateHash": "b" * 64}
                        for name in MODULE.CHECK_NAMES
                    ],
                )
        path.write_text("\n".join(map(json.dumps, events)), encoding="utf8")
        self.assertFalse(MODULE.inspect_run(self.directory)["traceVerified"])

    def test_compact_feedback_keeps_hash_and_errors_required(self):
        self.gemini_run()
        events_file = self.directory / "events.jsonl"
        rows = [json.loads(line) for line in events_file.read_text(encoding="utf8").splitlines()]
        for event in rows:
            if event.get("event") == "generation_result" and not event["ok"]:
                event.update(candidateHash="a" * 64, checks=[], reviews=[{"private": "detail"}])
        events_file.write_text("\n".join(map(json.dumps, rows)), encoding="utf8")
        request = self.directory / "call-02-request.json"
        body = json.loads(request.read_text(encoding="utf8"))
        content = json.loads(body["messages"][0]["content"])
        content["candidateHash"] = "a" * 64
        body["messages"][0]["content"] = json.dumps(content)
        request.write_text(json.dumps(body), encoding="utf8")
        self.assertTrue(MODULE.inspect_run(self.directory)["successfulRepairObserved"])
        content["candidateHash"] = "b" * 64
        body["messages"][0]["content"] = json.dumps(content)
        request.write_text(json.dumps(body), encoding="utf8")
        self.assertFalse(MODULE.inspect_run(self.directory)["traceVerified"])


if __name__ == "__main__":
    unittest.main()


def test_run_log_survives_ascii_terminal(tmp_path, monkeypatch):
    import io

    from mach_backend.poc_matrix import RunLog

    buffer = io.BytesIO()
    terminal = io.TextIOWrapper(buffer, encoding="ascii")
    monkeypatch.setattr("sys.stdout", terminal)
    RunLog(tmp_path / "unicode-log").emit("status", message="Kiểm đề tiếng Việt")
    terminal.flush()
    assert json.loads(buffer.getvalue())["message"] == "Kiểm đề tiếng Việt"
