"""Ca tổng hợp để kiểm công cụ đọc log, không phải số đo PoC model thật."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/kiem_tra_log_poc.py"
SPEC = importlib.util.spec_from_file_location("kiem_tra_log_poc", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TestPoCTrace(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def write_run(self, protocol="native", *, feedback=True, changed=True, finished=True):
        events = [
            {
                "event": "run_start",
                "trialId": "fixture",
                "mode": "fixture",
                "toolProtocol": protocol,
            }
        ]
        bad, good = {"ok": False, "errors": [{"code": "answer_disagreement"}]}, {"ok": True}
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
                                    "result": json.dumps(previous),
                                }
                            ),
                        }
                    ]
            message = {
                "role": "assistant",
                "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
            }
            if protocol == "structured":
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
        for protocol in ("native", "structured"):
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


if __name__ == "__main__":
    unittest.main()
