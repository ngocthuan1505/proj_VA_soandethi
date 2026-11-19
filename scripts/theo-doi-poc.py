"""Đọc log API PoC local, xuất JSON lượt mới; không tạo tác vụ, lưu đề hoặc gọi model."""

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import Thread
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
DEMO_PORT = 4188
LOCAL_PORTS = (4182, 4183, 4184, DEMO_PORT)

ERROR_CODES = {
    "uncertain_answer",
    "answer_disagreement",
    "option_verdicts_failed",
    "answer_verdict_disagreement",
    "level_disagreement",
    "semantic_duplicate",
    "uncertain_duplicate",
    "explanation_disagreement",
    "unsupported_answer",
    "topic_disagreement",
    "invalid_result",
    "invalid_evidence",
    "duplicate_question",
    "invalid_options",
    "invalid_plan",
    "invalid_rubric",
    "not_verified",
    "check_not_completed",
    "call_budget",
    "timeout",
    "provider_quota",
    "provider_auth",
    "provider_http_error",
    "provider_unavailable",
    "provider_timeout",
    "incomplete_response",
    "invalid_response",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Reader:
    def __init__(self, port):
        if port not in LOCAL_PORTS:
            raise ValueError("Chỉ đọc các cổng PoC trên máy này.")
        self.base = f"http://127.0.0.1:{port}"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def get(self, path):
        with self.opener.open(
            urllib.request.Request(self.base + path, method="GET"), timeout=4
        ) as response:
            return json.load(response)


def trace_summary(row):
    # Không xuất nguồn, nội dung câu hỏi, khóa hay lỗi nguyên văn từ provider.
    allowed = {
        "event": {
            "run_start",
            "run_end",
            "model_call_start",
            "model_start",
            "model_end",
            "provider_key_switch",
            "provider_model_switch",
            "provider_retry",
            "model_call_end",
            "tool_call",
            "structure_check",
            "blind_content_check",
            "candidate_check",
            "generation_result",
            "check_report",
        },
        "model": {"gemini-3.6-flash", "gemini-3.8-flash", "gemini-4-hydrogen"},
        "fromModel": {"gemini-3.6-flash", "gemini-3.8-flash", "gemini-4-hydrogen"},
        "toModel": {"gemini-3.6-flash", "gemini-3.8-flash", "gemini-4-hydrogen"},
        "tool": {"check_exam", "finish_exam"},
        "purpose": {"agent", "blind_content_check", "explanation_check"},
        "status": {
            "ready_for_teacher_review",
            "failed",
            "cancelled",
            "PASS",
            "FAIL",
            "UNKNOWN",
        },
        "toolName": {
            "validate_schema",
            "check_matrix_and_scoring",
            "retrieve_evidence",
            "solve_blind",
            "verify_options",
            "review_level",
            "check_duplicates",
            "check_explanation",
            "check_evidence",
            "aggregate_checks",
        },
        "errorCode": ERROR_CODES,
    }
    result = {
        key: value
        for key, values in allowed.items()
        if isinstance(value := row.get(key), str) and value in values
    }
    for key in (
        "ok",
        "modelCall",
        "keySlot",
        "fromKeySlot",
        "toKeySlot",
        "httpStatus",
        "saved",
        "generationAttempt",
        "reusedFromAttempt",
        "toolCallNumber",
        "seconds",
        "maxModelCalls",
        "timeoutSeconds",
        "elapsedSeconds",
        "durationMs",
    ):
        if type(row.get(key)) in (bool, int, float):
            result[key] = row[key]
    for key in ("errors", "findings"):
        if isinstance(row.get(key), list):
            result[key + "Codes"] = sorted(
                {
                    item["code"]
                    for item in row[key]
                    if isinstance(item, dict) and item.get("code") in ERROR_CODES
                }
            )
    return result


class Watcher:
    def __init__(self, reader, emit, exam_id=None, job_id=None, *, new_run=False, output_root=None):
        self.reader, self.emit = reader, emit
        self.exam_id = str(UUID(exam_id)) if exam_id else None
        self.explicit_exam = bool(exam_id)
        self.job_id = str(UUID(job_id)) if job_id else None
        if self.job_id and not self.exam_id:
            raise ValueError("Cần --exam-id khi chỉ định --job-id.")
        self.previous = None
        self.trace_count = 0
        self.new_run = new_run
        self.fixture = False
        self.ignored_jobs = set()
        self.armed_at = None
        self.output_root = Path(
            output_root or Path(__file__).resolve().parents[1] / "outputs/demo-truc-tiep"
        )
        self.output_dir = None
        self.output_created = False
        self.exported_path = None
        self.export_error = False
        self.run_input = None

    def arm_new_run(self):
        state = self.reader.get("/api/kv?key=state").get("value") or {}
        for exam in state.get("exams", []):
            exam_id = str(UUID(exam["id"]))
            latest = self.reader.get(f"/api/exams/{exam_id}/proposals/latest")
            if latest:
                self.ignored_jobs.add(str(UUID(latest["jobId"])))
        self.armed_at = datetime.now().astimezone().isoformat()
        self.emit(
            "CHO_LUOT_MOI",
            {"text": "Đã sẵn sàng. Tạo đề trên web và bấm sinh. Không đọc lại lượt cũ."},
        )

    def export_result(self, prefix, status, rows):
        # Chỉ xuất đúng job đã ghim; không đọc kết nối, khóa hoặc các đề khác.
        report = self.reader.get(prefix + "/report")
        audit = self.reader.get(prefix + "/audit")
        files = {
            "session.json": {
                "examId": self.exam_id,
                "jobId": self.job_id,
                "armedAt": self.armed_at,
                "exportedAt": datetime.now().astimezone().isoformat(),
                "fixture": self.fixture,
                "note": "Lượt phát sinh sau khi CMD sẵn sàng. "
                "complete là chờ giáo viên duyệt, không phải đã lưu đề.",
            },
            "input.json": self.run_input,
            "result.json": status,
            "trace.json": rows,
            "report.json": report,
            "audit.json": audit,
        }
        try:
            if not self.output_created:
                self.output_dir.mkdir(parents=True, exist_ok=False)
                self.output_created = True
            for name, content in files.items():
                temporary = self.output_dir / (name + ".tmp")
                temporary.write_text(
                    json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                temporary.replace(self.output_dir / name)
        except OSError:
            if not self.export_error:
                self.emit(
                    "LOI_LUU_JSON",
                    {"text": "Chưa lưu được JSON. Kiểm tra ổ đĩa/quyền ghi; CMD sẽ thử lại."},
                )
            self.export_error = True
            return
        self.exported_path = self.output_dir.resolve()
        self.emit(
            "DA_LUU_JSON",
            {
                "jobId": self.job_id,
                "status": status.get("status"),
                "folder": str(self.exported_path),
            },
        )

    def poll(self):
        state = self.reader.get("/api/kv?key=state").get("value") or {}
        if not self.explicit_exam and not self.job_id and state.get("current"):
            self.exam_id = str(UUID(state["current"]))
        exam = next((e for e in state.get("exams", []) if e.get("id") == self.exam_id), None)
        observed = {
            "examId": self.exam_id,
            "jobId": self.job_id,
            "examFound": exam is not None,
        }
        if exam:
            latest = self.reader.get(f"/api/exams/{self.exam_id}/proposals/latest")
            if self.new_run and not self.job_id:
                if not latest or str(UUID(latest["jobId"])) in self.ignored_jobs:
                    return
                self.job_id = str(UUID(latest["jobId"]))
                self.run_input = latest.get("input")
                self.output_dir = self.output_root / (
                    datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f") + "_" + self.job_id
                )
                self.emit("BAT_DAU_LUOT_MOI", {"examId": self.exam_id, "jobId": self.job_id})
            if latest and not self.job_id:
                self.job_id = str(UUID(latest["jobId"]))
            observed.update(
                jobId=self.job_id,
                revision=exam.get("revision"),
                questionCount=len(exam.get("questions", [])),
                undoCount=len(exam.get("undo", [])),
                redoCount=len(exam.get("redo", [])),
            )
            if self.job_id:
                prefix = f"/api/exams/{self.exam_id}/proposals/{self.job_id}"
                status = self.reader.get(prefix + "/status")
                observed["jobStatus"] = status.get("status")
                observed["savedHistoryObserved"] = any(
                    h.get("id") == self.job_id for h in exam.get("history", [])
                )
                if latest and latest.get("jobId") == self.job_id:
                    reviews = latest.get("reviews", {})
                    questions = (latest.get("proposal") or {}).get("questions", [])
                    observed.update(
                        discarded=latest.get("discarded", False),
                        reviewCount=len(reviews),
                        unresolvedReviewCount=sum(
                            not r.get("contentOk", False)
                            or int(i) >= len(questions)
                            or r.get("observed") != questions[int(i)].get("level")
                            for i, r in reviews.items()
                        ),
                    )
                rows = self.reader.get(prefix + "/trace")
                for index, row in enumerate(rows[self.trace_count :], self.trace_count + 1):
                    self.emit(
                        "APP_TRACE",
                        {"jobId": self.job_id, "index": index, **trace_summary(row)},
                    )
                self.trace_count = len(rows)
                if (
                    self.new_run
                    and status.get("status") in {"complete", "failed", "cancelled"}
                    and not self.exported_path
                ):
                    self.export_result(prefix, status, rows)
        elif self.new_run:
            return
        if observed != self.previous:
            self.emit("QUAN_SAT_API", observed)
            self.previous = observed


@contextmanager
def demo_server():
    import uvicorn

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", DEMO_PORT))
        except OSError:
            raise RuntimeError(
                f"Cổng {DEMO_PORT} chưa mở được. Kiểm tra xem CMD demo khác đang chạy."
            ) from None
        listener.listen()
        os.environ["MACH_DATA_DIR"] = str(ROOT / "outputs" / "demo-nhom" / "data")
        sys.path.insert(0, str(ROOT / "backend" / "src"))
        server = uvicorn.Server(
            uvicorn.Config(
                "mach_backend.local_workspace:app",
                log_level="warning",
                timeout_graceful_shutdown=4,
            )
        )
        worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not worker.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("App demo chưa khởi động được.")
                time.sleep(0.1)
            yield
        finally:
            server.should_exit = True
            worker.join(timeout=6)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, choices=LOCAL_PORTS, default=4183)
    parser.add_argument("--demo", action="store_true", help="Mở app và theo dõi lượt thao tác mới.")
    parser.add_argument("--exam-id", type=lambda x: str(UUID(x)))
    parser.add_argument("--job-id", type=lambda x: str(UUID(x)))
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--new-run",
        action="store_true",
        help="Chờ một lượt mới, xuất JSON rồi kết thúc; bỏ qua mọi lượt cũ.",
    )
    parser.add_argument("--output", type=Path, help="Thư mục gốc lưu JSON của lượt mới.")
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Theo dõi đến khi Ctrl+C; tiếp tục khi máy thức lại.",
    )
    parser.add_argument(
        "--seconds", type=int, choices=range(1, 3601), default=900, metavar="1..3600"
    )
    args = parser.parse_args()
    if args.demo:
        args.port, args.new_run, args.follow = DEMO_PORT, True, True
        args.output = ROOT / "JSON-demo"
    if args.job_id and not args.exam_id:
        parser.error("Cần --exam-id khi chỉ định --job-id.")
    if args.new_run and args.job_id:
        parser.error("--new-run không đọc lại --job-id đã có.")
    if args.output and not args.new_run:
        parser.error("--output cần --new-run.")
    if not args.demo:
        return observe(args)
    try:
        with demo_server():
            result = observe(args)
            if result == 0:
                try:
                    input("App vẫn mở để bạn xem hoặc lưu đề. Nhấn Enter khi muốn đóng app demo.")
                except EOFError:
                    pass
            return result
    except KeyboardInterrupt:
        print("Đã đóng app demo.")
        return 0
    except RuntimeError as error:
        print(error)
        return 1


def observe(args):
    def emit(kind, value):
        if args.new_run and kind == "CHO_LUOT_MOI":
            label = " [GIẢ LẬP]" if status.get("fixture") else ""
            print("Sẵn sàng. Tạo đề trên web để bắt đầu." + label, flush=True)
            return
        print(
            json.dumps(
                {
                    "observedAt": datetime.now().astimezone().isoformat(),
                    "kind": kind,
                    **value,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    reader = Reader(args.port)
    status = reader.get("/api/status")
    if not status.get("localPoC"):
        raise ValueError("Cổng này không phải app PoC local.")
    if not args.new_run:
        emit("QUAN_SAT_API", {"fixture": bool(status.get("fixture")), "port": args.port})
        emit(
            "DIEN_GIAI",
            {
                "text": "Chỉ GET API. Trước lượt sinh, theo đề đang mở; khi có job thì ghim "
                "đúng đề/job đó. Chạy lại CMD để theo dõi lượt khác. APP_TRACE giữ thứ tự log API, "
                "observedAt là lúc đọc, không phải thời điểm model chạy. "
                "complete không có nghĩa đã lưu. Ctrl+C để dừng theo dõi."
            },
        )
    watcher = Watcher(
        reader, emit, args.exam_id, args.job_id, new_run=args.new_run, output_root=args.output
    )
    watcher.fixture = bool(status.get("fixture"))
    if args.new_run:
        watcher.arm_new_run()
    if args.demo:
        print("Mở app demo tại " + reader.base, flush=True)
        webbrowser.open(reader.base)
    deadline = time.monotonic() + args.seconds
    offline = False
    while args.follow or time.monotonic() < deadline:
        try:
            watcher.poll()
            if watcher.exported_path:
                return 0
            if offline:
                emit("QUAN_SAT_API", {"connection": "restored"})
            offline = False
        except (OSError, ValueError, urllib.error.URLError):
            if not offline:
                emit(
                    "QUAN_SAT_API",
                    {"connection": "unavailable", "retrying": not args.once},
                )
            offline = True
        if args.once:
            return 1 if offline else 0
        time.sleep(1)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Đã dừng theo dõi; app và tác vụ vẫn giữ nguyên.")
    except (OSError, ValueError, urllib.error.URLError):
        print("Chưa đọc được API PoC local. Kiểm tra app/cổng; không tự khởi động dịch vụ.")
        raise SystemExit(1) from None
