import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from mach_backend.ai_contract import AIError, PatchJob, SourceFragment
from mach_backend.patch_confirmation import (
    ConfirmationState,
    PatchReceipt,
    PendingPatch,
    prepare_patch,
)
from mach_backend.patch_jobs import PatchJobRunner
from mach_backend.patch_routes import build_patch_confirmation_router, build_patch_job_router

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[2] / "tests/fixtures/ai-patch-local.json").read_text(
        encoding="utf-8"
    )
)
OWNER = "teacher-1"
HEADERS = {"Authorization": "Bearer owner-fixture"}
OTHER = {"Authorization": "Bearer second-fixture"}
SOURCES = TypeAdapter(tuple[SourceFragment, ...])


class SQLiteFixture:
    """Adapter kiểm hợp đồng trên SQLite tạm trước khi ghép schema BE-3."""

    def __init__(self, file):
        self.file = file
        self.fail_after_update = False
        with closing(sqlite3.connect(file)) as conn:
            conn.executescript(
                """
                CREATE TABLE exams(owner, exam, payload, sources, PRIMARY KEY(owner, exam));
                CREATE TABLE proposals(
                    owner, exam, job, pending, receipt, active, PRIMARY KEY(owner, exam, job)
                );
                CREATE TABLE history(
                    owner, exam, revision, payload, PRIMARY KEY(owner, exam, revision)
                );
                """
            )

    def seed(self, job, exam):
        with closing(sqlite3.connect(self.file)) as conn, conn:
            conn.execute(
                "INSERT INTO exams VALUES(?, ?, ?, ?)",
                (job.ownerId, str(job.examId), json.dumps(exam), SOURCES.dump_json(job.sources)),
            )

    def snapshot(self, job):
        with closing(sqlite3.connect(self.file)) as conn:
            exam, sources = self.get_exam(conn, job.ownerId, str(job.examId))
        return exam, SOURCES.validate_json(sources)

    @staticmethod
    def get_exam(conn, owner, exam):
        payload, sources = conn.execute(
            "SELECT payload,sources FROM exams WHERE owner=? AND exam=?", (owner, exam)
        ).fetchone()
        return json.loads(payload), sources

    async def current(self, job):
        exam, sources = self.snapshot(job)
        return exam["revision"] == job.baseRevision and sources == job.sources

    async def stage(self, pending):
        job = pending.job
        key = (job.ownerId, str(job.examId))
        with closing(sqlite3.connect(self.file)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            exam, sources = self.get_exam(conn, *key)
            if (
                exam["revision"] != job.baseRevision
                or SOURCES.validate_json(sources) != job.sources
            ):
                return False
            result = conn.execute(
                "INSERT OR IGNORE INTO proposals VALUES(?, ?, ?, ?, NULL, 1)",
                (*key, str(job.jobId), pending.model_dump_json()),
            )
            return result.rowcount == 1

    @contextmanager
    def transaction(self, owner_id, exam_id, job_id):
        key = (owner_id, str(exam_id), str(job_id))
        with closing(sqlite3.connect(self.file)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            yield SQLiteTransaction(conn, key, self.fail_after_update)

    def update_exam(self, job, exam):
        with closing(sqlite3.connect(self.file)) as conn, conn:
            conn.execute(
                "UPDATE exams SET payload=? WHERE owner=? AND exam=?",
                (json.dumps(exam), job.ownerId, str(job.examId)),
            )

    def update_sources(self, job, sources):
        with closing(sqlite3.connect(self.file)) as conn, conn:
            conn.execute(
                "UPDATE exams SET sources=? WHERE owner=? AND exam=?",
                (SOURCES.dump_json(sources), job.ownerId, str(job.examId)),
            )

    def deactivate(self, job):
        with closing(sqlite3.connect(self.file)) as conn, conn:
            conn.execute(
                "UPDATE proposals SET active=0 WHERE owner=? AND exam=? AND job=?",
                (job.ownerId, str(job.examId), str(job.jobId)),
            )

    def history_count(self):
        with closing(sqlite3.connect(self.file)) as conn:
            return conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]


class SQLiteTransaction:
    def __init__(self, conn, key, fail_after_update):
        self.conn = conn
        self.key = key
        self.fail_after_update = fail_after_update

    def read(self):
        row = self.conn.execute(
            "SELECT pending,receipt FROM proposals WHERE owner=? AND exam=? AND job=? AND active=1",
            self.key,
        ).fetchone()
        if row is None:
            return None
        pending, receipt = row
        exam, sources = SQLiteFixture.get_exam(self.conn, *self.key[:2])
        return ConfirmationState(
            owner_id=self.key[0],
            pending=PendingPatch.model_validate_json(pending),
            exam=exam,
            sources=SOURCES.validate_json(sources),
            receipt=PatchReceipt.model_validate_json(receipt) if receipt else None,
        )

    def write(self, exam, receipt):
        owner, exam_id, _ = self.key
        old, _ = SQLiteFixture.get_exam(self.conn, owner, exam_id)
        self.conn.execute(
            "INSERT INTO history VALUES(?, ?, ?, ?)",
            (owner, exam_id, old["revision"], json.dumps(old)),
        )
        self.conn.execute(
            "UPDATE exams SET payload=? WHERE owner=? AND exam=?",
            (json.dumps(exam), owner, exam_id),
        )
        if self.fail_after_update:
            raise sqlite3.IntegrityError("Lỗi ghi biên nhận giả lập")
        self.conn.execute(
            "UPDATE proposals SET receipt=? WHERE owner=? AND exam=? AND job=?",
            (receipt.model_dump_json(), *self.key),
        )


@pytest.fixture
def sample():
    first = FIXTURE["text"]
    selected = FIXTURE["selectionText"]
    start = first.index(selected)
    end = start + len(selected)
    job_id, exam_id, source_id = (str(uuid4()) for _ in range(3))
    locator = {"kind": "page", "index": 1}
    identity = {"jobId": job_id, "examId": exam_id, "baseRevision": 4}
    citation = {
        "sourceId": source_id,
        "sourceVersion": 3,
        "locator": locator,
        "quote": "Thay giá trị để kiểm kết quả",
    }
    job = PatchJob.model_validate_json(
        json.dumps(
            {
                **identity,
                "ownerId": OWNER,
                "request": "Viết lại câu trong lời giải.",
                "requireEvidence": True,
                "targets": [
                    {
                        "questionId": FIXTURE["questionId"],
                        "questionVersion": 2,
                        "blockId": FIXTURE["blockId"],
                        "field": "explanation",
                        "text": first,
                        "selection": [
                            len(first[:n].encode("utf-16-le")) // 2 for n in (start, end)
                        ],
                    }
                ],
                "sources": [
                    {
                        "sourceId": source_id,
                        "sourceVersion": 3,
                        "locator": locator,
                        "ownerId": OWNER,
                        "text": "Thay giá trị để kiểm kết quả của biểu thức.",
                    }
                ],
            }
        )
    )
    content = [
        {"type": "text", "text": "🔎 Giữ ", "marks": [{"type": "bold"}]},
        {"type": "mathInline", "attrs": {"latex": "x^2", "display": False, "id": str(uuid4())}},
        {"type": "text", "text": ". "},
        {"type": "text", "text": selected, "marks": [{"type": "italic"}]},
        {"type": "text", "text": " Kết luận giữ nguyên."},
    ]
    exam = {
        "id": exam_id,
        "title": "Đề giữ nguyên tiêu đề",
        "revision": 4,
        "draftStatus": "ready",
        "questions": [
            {
                "id": FIXTURE["questionId"],
                "blockIds": {"explanation": FIXTURE["blockId"]},
                "v": 2,
                "explanation": first,
                "explanationDoc": {
                    "type": "doc",
                    "content": [{"type": "paragraph", "content": content}],
                },
                "stem": "Tính $x^2$.",
                "options": [],
                "check": {"version": 2, "status": "approved"},
                "verificationStatus": "consistent",
                "approvalStatus": "approved",
            },
            {"id": str(uuid4()), "v": 7, "explanation": "Giữ nguyên câu khác."},
        ],
    }
    result = {
        **identity,
        "edits": [
            {
                "op": "replace",
                "blockId": FIXTURE["blockId"],
                "content": FIXTURE["cases"][0]["content"],
            }
        ],
        "evidence": [citation],
        "message": "Đề xuất thay câu giải thích.",
    }
    return job, exam, result


def fixture_app(repo, runner=None):
    def authenticated_owner(request: Request) -> str:
        match request.headers.get("Authorization"):
            case "Bearer owner-fixture":
                return OWNER
            case "Bearer second-fixture":
                return "teacher-2"
            case _:
                raise HTTPException(status_code=401)

    app = FastAPI()
    app.include_router(build_patch_confirmation_router(repo, authenticated_owner))
    if runner is not None:
        app.include_router(build_patch_job_router(runner, authenticated_owner))
    return app


def app_client(repo):
    return TestClient(fixture_app(repo), raise_server_exceptions=False)


def stage(repo, job, result):
    async def provider(_job):
        return json.dumps(result)

    return asyncio.run(prepare_patch(job, provider, repo.current, repo.stage, timeout_seconds=1))


@pytest.fixture
def staged(tmp_path, sample):
    job, exam, result = sample
    repo = SQLiteFixture(tmp_path / "confirmation.sqlite")
    repo.seed(job, exam)
    proposal = stage(repo, job, result)
    path = f"/api/exams/{job.examId}/proposals/{job.jobId}/confirm"
    return repo, path, job, exam, proposal


def test_preview_then_confirm_preserves_unaffected_fields_and_replays_receipt(staged):
    repo, path, job, exam, proposal = staged
    assert repo.snapshot(job)[0] == exam
    assert repo.history_count() == 0

    with app_client(repo) as client:
        response = client.post(path, headers=HEADERS, json={"baseRevision": 4})
        assert response.status_code == 200, response.text
        receipt = response.json()
        assert receipt["changedQuestionIds"] == [FIXTURE["questionId"]]
        assert receipt["revision"] == 5
        assert client.post(path, headers=HEADERS, json={"baseRevision": 4}).json() == receipt

    current, sources = repo.snapshot(job)
    assert sources == job.sources
    assert current["draftStatus"] == exam["draftStatus"]
    assert current["title"] == exam["title"]
    assert current["questions"][1] == exam["questions"][1]
    q, original = current["questions"][0], exam["questions"][0]
    assert q["stem"] == original["stem"]
    assert q["blockIds"] == original["blockIds"]
    assert q["v"] == 3
    assert (q["check"], q["verificationStatus"], q["approvalStatus"]) == (
        None,
        "unverified",
        "draft",
    )
    assert q["explanation"] == proposal.edits[0].content
    before = original["explanationDoc"]["content"][0]["content"]
    after = q["explanationDoc"]["content"][0]["content"]
    assert before[:3] == after[:3]
    assert before[4:] == after[4:]
    assert after[3] == {"type": "text", "text": "Viết lại lời giải.", "marks": [{"type": "italic"}]}
    assert repo.history_count() == 1


def test_confirm_edits_existing_formula_without_replacing_its_node(tmp_path, sample):
    job, exam, result = sample
    target = job.targets[0]
    formula = "$x^2$"
    start = target.text.index(formula)
    offsets = tuple(
        len(target.text[:offset].encode("utf-16-le")) // 2
        for offset in (start, start + len(formula))
    )
    job = job.model_copy(update={"targets": (target.model_copy(update={"selection": offsets}),)})
    result["edits"][0]["content"] = target.text.replace(formula, "$x^3$")
    repo = SQLiteFixture(tmp_path / "formula.sqlite")
    repo.seed(job, exam)
    stage(repo, job, result)

    with app_client(repo) as client:
        path = f"/api/exams/{job.examId}/proposals/{job.jobId}/confirm"
        response = client.post(path, headers=HEADERS, json={"baseRevision": 4})
        assert response.status_code == 200, response.text

    current, _ = repo.snapshot(job)
    before = exam["questions"][0]["explanationDoc"]["content"][0]["content"]
    after = current["questions"][0]["explanationDoc"]["content"][0]["content"]
    assert after[0] == before[0]
    assert after[2:] == before[2:]
    assert after[1] == {**before[1], "attrs": {**before[1]["attrs"], "latex": "x^3"}}


def test_http_owner_session_and_body_boundaries(staged):
    repo, path, job, exam, _ = staged
    with app_client(repo) as client:
        assert client.post(path, json={"baseRevision": 4}).status_code == 401
        assert client.post(path, headers=OTHER, json={"baseRevision": 4}).status_code == 404
        assert (
            client.post(
                path, headers=HEADERS, json={"baseRevision": 4, "ownerId": OWNER, "edits": []}
            ).status_code
            == 422
        )
        assert client.post(path, headers=HEADERS, json={"baseRevision": 3}).status_code == 409
    assert repo.snapshot(job)[0] == exam
    assert repo.history_count() == 0


@pytest.mark.parametrize(
    "change", ["exam", "question", "block", "source", "finalized", "cancelled"]
)
def test_changed_snapshot_or_inactive_job_never_writes(staged, change):
    repo, path, job, exam, _ = staged
    if change == "exam":
        exam["revision"] = 5
    elif change == "question":
        exam["questions"][0]["v"] += 1
    elif change == "block":
        exam["questions"][0]["blockIds"]["explanation"] = str(uuid4())
    elif change == "source":
        changed = job.sources[0].model_copy(update={"sourceVersion": 4})
        repo.update_sources(job, (changed,))
    elif change == "finalized":
        exam["draftStatus"] = "finalized"
    else:
        repo.deactivate(job)
    repo.update_exam(job, exam)
    with app_client(repo) as client:
        response = client.post(path, headers=HEADERS, json={"baseRevision": 4})
        assert response.status_code == (404 if change == "cancelled" else 409)
        if change not in ("cancelled", "finalized"):
            assert response.json()["detail"]["code"] == "stale_snapshot"
    assert repo.snapshot(job)[0] == exam
    assert repo.history_count() == 0


def test_sqlite_rolls_back_update_and_history_when_receipt_cannot_write(staged):
    repo, path, job, exam, _ = staged
    repo.fail_after_update = True
    with app_client(repo) as client:
        assert client.post(path, headers=HEADERS, json={"baseRevision": 4}).status_code == 500
        assert repo.snapshot(job)[0] == exam
        assert repo.history_count() == 0
        repo.fail_after_update = False
        assert client.post(path, headers=HEADERS, json={"baseRevision": 4}).status_code == 200
    assert repo.history_count() == 1


def test_concurrent_confirms_share_one_commit(staged):
    repo, path, job, _, _ = staged

    def confirm():
        with app_client(repo) as client:
            result = client.post(path, headers=HEADERS, json={"baseRevision": 4})
            assert result.status_code == 200, result.text
            return result.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = [pool.submit(confirm) for _ in range(2)]
        assert left.result(timeout=10) == right.result(timeout=10)
    assert repo.snapshot(job)[0]["revision"] == 5
    assert repo.history_count() == 1


def test_rich_change_across_formatted_runs_is_rejected(tmp_path, sample):
    job, exam, result = sample
    target = job.targets[0].model_copy(update={"selection": None})
    job = job.model_copy(update={"targets": (target,)})
    result["edits"][0]["content"] = "Lời giải khác, không còn giữ các nút hiện tại."
    repo = SQLiteFixture(tmp_path / "rich.sqlite")
    repo.seed(job, exam)
    stage(repo, job, result)

    with app_client(repo) as client:
        response = client.post(
            f"/api/exams/{job.examId}/proposals/{job.jobId}/confirm",
            headers=HEADERS,
            json={"baseRevision": 4},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "rich_document_conflict"
    assert repo.snapshot(job)[0] == exam
    assert repo.history_count() == 0


def test_stage_refuses_revision_changed_after_provider_check(tmp_path, sample):
    job, exam, result = sample
    repo = SQLiteFixture(tmp_path / "stage.sqlite")
    repo.seed(job, exam)

    async def provider(_job):
        return json.dumps(result)

    async def stage_after_write(pending):
        repo.update_exam(job, {**exam, "revision": 5})
        return await repo.stage(pending)

    with pytest.raises(AIError) as raised:
        asyncio.run(
            prepare_patch(job, provider, repo.current, stage_after_write, timeout_seconds=1)
        )
    assert raised.value.code == "stale_snapshot"
    with repo.transaction(job.ownerId, job.examId, UUID(result["jobId"])) as tx:
        assert tx.read() is None


async def disconnect_after_first_event(app, path):
    first = asyncio.Event()
    frames = []

    async def receive():
        await first.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            frames.append(message["body"])
            first.set()

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": [(b"authorization", HEADERS["Authorization"].encode())],
        },
        receive,
        send,
    )
    return b"".join(frames).decode()


def test_job_events_resume_and_confirm_same_proposal(tmp_path, sample):
    job, exam, result = sample
    repo = SQLiteFixture(tmp_path / "job.sqlite")
    repo.seed(job, exam)

    async def run():
        released = asyncio.Event()
        calls = 0

        async def provider(_job):
            nonlocal calls
            calls += 1
            await released.wait()
            return json.dumps(result)

        runner = PatchJobRunner(
            provider, repo.current, repo.stage, timeout_seconds=2, max_active=1, max_retained=2
        )
        assert runner.submit(job) == runner.submit(job)
        with pytest.raises(AIError, match="Mã tác vụ"):
            runner.submit(job.model_copy(update={"request": "Yêu cầu khác"}))

        base = f"/api/exams/{job.examId}/proposals/{job.jobId}"
        app = fixture_app(repo, runner)
        initial = await disconnect_after_first_event(app, base + "/events")
        assert initial.startswith("id: 1\n")
        assert json.loads(initial.split("data: ", 1)[1])["status"] == "running"
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get(base + "/events", headers=OTHER)).status_code == 404
            assert (await client.get(base + "/status")).status_code == 401
            status = await client.get(base + "/status", headers=HEADERS)
            assert status.json()["status"] == "running"
            released.set()

            resumed = await client.get(base + "/events", headers={**HEADERS, "Last-Event-ID": "1"})
            assert resumed.status_code == 200
            assert resumed.headers["content-type"].startswith("text/event-stream")
            assert resumed.text.count("event: patch") == 1
            assert resumed.text.startswith("id: 2\n")
            terminal = json.loads(resumed.text.split("data: ", 1)[1])
            assert terminal["status"] == "complete"
            assert terminal["proposal"]["edits"] == result["edits"]
            replay = await client.get(base + "/events", headers={**HEADERS, "Last-Event-ID": "2"})
            assert replay.text == ""

            assert repo.snapshot(job)[0] == exam
            stopped = await client.post(base + "/cancel", headers=HEADERS)
            assert stopped.json() == terminal
            receipt = await client.post(
                base + "/confirm", headers=HEADERS, json={"baseRevision": 4}
            )
            assert receipt.status_code == 200
            assert receipt.json()["revision"] == 5
            assert calls == 1

    asyncio.run(asyncio.wait_for(run(), timeout=5))


@pytest.mark.parametrize("timed_out", [False, True])
def test_job_discards_late_result_and_holds_slot(tmp_path, sample, timed_out):
    job, exam, result = sample
    repo = SQLiteFixture(tmp_path / "cancel.sqlite")
    repo.seed(job, exam)

    async def run():
        started, caught, released, exited = (asyncio.Event() for _ in range(4))

        async def provider(_job):
            started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                caught.set()
                await released.wait()
                return json.dumps(result)
            finally:
                exited.set()

        runner = PatchJobRunner(
            provider,
            repo.current,
            repo.stage,
            timeout_seconds=0.05 if timed_out else 2,
            max_active=1,
            max_retained=1,
        )
        runner.submit(job)
        await started.wait()
        base = f"/api/exams/{job.examId}/proposals/{job.jobId}"
        transport = httpx.ASGITransport(app=fixture_app(repo, runner))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.post(base + "/cancel", headers=OTHER)).status_code == 404
            if timed_out:
                await caught.wait()
                stopped = await client.get(base + "/status", headers=HEADERS)
                assert stopped.json()["status"] == "failed"
                assert stopped.json()["errorCode"] == "timeout"
            else:
                stopped = await client.post(base + "/cancel", headers=HEADERS)
                assert stopped.json()["status"] == "cancelled"
                await caught.wait()
            assert stopped.status_code == 200
            assert (await client.post(base + "/cancel", headers=HEADERS)).json() == stopped.json()

            other = job.model_copy(update={"jobId": uuid4()})
            with pytest.raises(AIError) as limit:
                runner.submit(other)
            assert limit.value.code == "job_limit"
            released.set()
            await exited.wait()

            events = await client.get(base + "/events", headers=HEADERS)
            assert events.text.count("event: patch") == 1
            assert json.loads(events.text.split("data: ", 1)[1]) == stopped.json()
            refused = await client.post(
                base + "/confirm", headers=HEADERS, json={"baseRevision": 4}
            )
            assert refused.status_code == 404
            assert repo.snapshot(job)[0] == exam
            assert repo.history_count() == 0
            assert runner.submit(other).status == "running"
            assert (await runner.cancel(other.ownerId, other.examId, other.jobId)).status == (
                "cancelled"
            )

    asyncio.run(asyncio.wait_for(run(), timeout=5))
