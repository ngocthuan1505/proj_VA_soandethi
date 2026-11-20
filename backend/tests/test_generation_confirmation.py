"""Xác nhận Sinh đề dùng cùng giao dịch và route với xác nhận Sửa."""

import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from test_patch_confirmation import HEADERS, OTHER, SQLiteFixture, app_client

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import GenerateJob, GenerationPlan
from mach_backend.ai_service import OllamaProvider
from mach_backend.patch_confirmation import prepare_generation

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[2] / "tests/fixtures/ai-sinh-kiem.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture
def generated(tmp_path):
    identity = {"jobId": str(uuid4()), "examId": str(uuid4()), "baseRevision": 4}
    source = {
        "ownerId": "teacher-1",
        "sourceId": FIXTURE["sourceId"],
        "sourceVersion": FIXTURE["sourceVersion"],
        "locator": {"kind": "page", "index": 1},
        "text": FIXTURE["sourceText"],
    }
    job = GenerateJob.model_validate_json(
        json.dumps(
            {
                **identity,
                "ownerId": "teacher-1",
                "sources": [source],
                "requireEvidence": True,
                "subject": "Toán",
                "grade": "6",
                "instructions": "Đọc kỹ yêu cầu từng câu.",
                "slots": [
                    {field: question[field] for field in ("type", "topic", "level", "pointsQ4")}
                    for question in FIXTURE["questions"]
                ],
            }
        )
    )
    evidence = {key: value for key, value in source.items() if key not in ("ownerId", "text")}
    evidence["quote"] = FIXTURE["quote"]
    result = {
        **identity,
        "questions": [{**question, "evidence": [evidence]} for question in FIXTURE["questions"]],
    }
    exam = {
        "id": identity["examId"],
        "revision": 4,
        "draftStatus": "ready",
        "title": "Giữ tiêu đề giáo viên đã đặt",
        "school": "Trường mẫu",
        "layout": {"font": "Times New Roman", "fontSize": 15},
        "approvedGenerationPlan": job.model_dump(
            mode="json", include=set(GenerationPlan.model_fields)
        ),
        "questions": [
            {
                "id": str(uuid4()),
                "v": 8,
                "stem": "Đề cũ $x^2$.",
                "explanation": "Lời giải cũ.",
                "richDoc": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "mathInline", "attrs": {"latex": "x^2"}}],
                        }
                    ],
                },
            }
        ],
    }
    repo = SQLiteFixture(tmp_path / "generation.sqlite")
    repo.seed(job, exam)

    def reply(request):
        payload = json.loads(json.loads(request.content)["messages"][1]["content"])
        assert payload["slots"] == job.model_dump(mode="json")["slots"]
        return httpx.Response(
            200,
            json={"done": True, "message": {"role": "assistant", "content": json.dumps(result)}},
        )

    provider = OllamaProvider("fixture", transport=httpx.MockTransport(reply))
    proposal = asyncio.run(
        prepare_generation(
            job,
            provider,
            repo.current,
            repo.stage,
            timeout_seconds=1,
        )
    )
    path = f"/api/exams/{job.examId}/proposals/{job.jobId}/confirm"
    return repo, job, exam, proposal, path


def test_generation_preview_confirm_and_replay_preserve_history_and_question_types(generated):
    repo, job, old, proposal, path = generated
    assert repo.snapshot(job)[0] == old
    assert repo.history_count() == 0
    with app_client(repo) as client:
        response = client.post(path, headers=HEADERS, json={"baseRevision": 4})
        assert response.status_code == 200, response.text
        receipt = response.json()

    current, _ = repo.snapshot(job)
    assert current["revision"] == 5
    assert current["draftStatus"] == "draft"
    assert current["title"] == old["title"]
    assert current["school"] == old["school"]
    assert current["layout"] == old["layout"]
    assert (current["subject"], current["grade"], current["instructions"]) == (
        job.subject,
        job.grade,
        job.instructions,
    )
    questions = current["questions"]
    ids = [UUID(question["id"]) for question in questions]
    blocks = [UUID(value) for question in questions for value in question["blockIds"].values()]
    assert all(identifier.version == 4 for identifier in ids + blocks)
    assert len(set(ids + blocks)) == 36
    assert str(ids[0]) != old["questions"][0]["id"]
    assert receipt["changedQuestionIds"] == [str(identifier) for identifier in ids]
    assert sum(question["points"] for question in questions) == 10
    for new, expected in zip(questions, proposal.questions, strict=True):
        assert new["type"] == expected.type
        assert new["stem"] == expected.stem
        assert new["evidence"] == expected.model_dump(mode="json")["evidence"]
        assert sum(step["points"] for step in new["rubric"]) == new["points"]
        assert (new["v"], new["verificationStatus"], new["approvalStatus"]) == (
            1,
            "unverified",
            "draft",
        )
        assert new["check"] is None
    assert questions[0]["answer"] == FIXTURE["questions"][0]["answer"]
    assert questions[1]["truthValues"] == FIXTURE["questions"][1]["answer"]
    assert questions[2]["answerText"] == FIXTURE["questions"][2]["answer"]
    assert questions[3]["answerKnown"] is False

    with closing(sqlite3.connect(repo.file)) as conn:
        history = json.loads(conn.execute("SELECT payload FROM history").fetchone()[0])
    assert history == old
    assert repo.history_count() == 1

    restarted = SQLiteFixture(repo.file)
    with app_client(restarted) as client:
        assert client.post(path, headers=HEADERS, json={"baseRevision": 4}).json() == receipt
    assert restarted.snapshot(job)[0] == current
    assert restarted.history_count() == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "revision",
        "source",
        "changed_plan",
        "unapproved_plan",
        "finalized",
        "cancelled",
        "proposal",
        "formula",
    ],
)
def test_generation_refuses_stale_unapproved_or_invalid_state(generated, mutation):
    repo, job, old, _, path = generated
    expected = json.loads(json.dumps(old))
    match mutation:
        case "revision":
            expected["revision"] += 1
        case "source":
            repo.update_sources(job, (job.sources[0].model_copy(update={"sourceVersion": 4}),))
        case "changed_plan":
            expected["approvedGenerationPlan"]["instructions"] = "Yêu cầu khác."
        case "unapproved_plan":
            del expected["approvedGenerationPlan"]
        case "finalized":
            expected["draftStatus"] = "finalized"
        case "cancelled":
            repo.deactivate(job)
        case "proposal":
            with closing(sqlite3.connect(repo.file)) as conn, conn:
                pending = json.loads(conn.execute("SELECT pending FROM proposals").fetchone()[0])
                pending["proposal"]["questions"][0]["pointsQ4"] = 1
                conn.execute("UPDATE proposals SET pending=?", (json.dumps(pending),))
        case "formula":
            with closing(sqlite3.connect(repo.file)) as conn, conn:
                pending = json.loads(conn.execute("SELECT pending FROM proposals").fetchone()[0])
                pending["proposal"]["questions"][0]["stem"] = r"Tính $\frac{1}{2$."
                conn.execute("UPDATE proposals SET pending=?", (json.dumps(pending),))
    repo.update_exam(job, expected)
    with app_client(repo) as client:
        response = client.post(path, headers=HEADERS, json={"baseRevision": 4})
        assert response.status_code == (404 if mutation == "cancelled" else 409), response.text
        if mutation == "formula":
            assert response.json()["detail"]["code"] == "invalid_math"
    assert repo.snapshot(job)[0] == expected
    assert repo.history_count() == 0


def test_generation_rejects_other_owner_and_rolls_back_before_retry(generated):
    repo, job, old, _, path = generated
    with app_client(repo) as client:
        assert client.post(path, headers=OTHER, json={"baseRevision": 4}).status_code == 404
        repo.fail_after_update = True
        failed = client.post(path, headers=HEADERS, json={"baseRevision": 4})
        assert failed.status_code == 500
        assert repo.snapshot(job)[0] == old
        assert repo.history_count() == 0
        repo.fail_after_update = False
        assert client.post(path, headers=HEADERS, json={"baseRevision": 4}).status_code == 200
    assert repo.snapshot(job)[0]["revision"] == 5
    assert repo.history_count() == 1


def test_two_generation_confirmations_use_one_set_of_uuids(generated):
    repo, job, _, _, path = generated

    def confirm():
        with app_client(repo) as client:
            result = client.post(path, headers=HEADERS, json={"baseRevision": 4})
            assert result.status_code == 200, result.text
            return result.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(confirm), executor.submit(confirm)
        assert first.result(timeout=10) == second.result(timeout=10)
    assert repo.snapshot(job)[0]["revision"] == 5
    assert repo.history_count() == 1


def test_generation_staging_checks_plan_changed_after_provider(generated):
    repo, job, old, proposal, _ = generated
    job = job.model_copy(update={"jobId": uuid4()})
    proposal = proposal.model_copy(update={"jobId": job.jobId})

    async def provider(_job):
        return proposal.model_dump_json()

    async def stage_after_plan_changed(pending):
        changed = {
            **old,
            "approvedGenerationPlan": {
                **old["approvedGenerationPlan"],
                "instructions": "Cấu trúc vừa được sửa.",
            },
        }
        repo.update_exam(job, changed)
        return await repo.stage(pending)

    with pytest.raises(AIError) as error:
        asyncio.run(
            prepare_generation(
                job,
                provider,
                repo.current,
                stage_after_plan_changed,
                timeout_seconds=1,
            )
        )
    assert error.value.code == "stale_snapshot"
    with repo.transaction(job.ownerId, job.examId, job.jobId) as tx:
        assert tx.read() is None
    assert repo.history_count() == 0


def test_smoke_sinh_va_xac_nhan_qua_http(generated, smoke_evidence):
    mode, model, _, _, timeout = smoke_evidence
    if mode == "fixture":
        pytest.skip("Chạy khi chọn --smoke-ollama-model.")
    repo, job, old, _, _ = generated
    job = job.model_copy(
        update={
            "jobId": uuid4(),
            "slots": (job.slots[0].model_copy(update={"pointsQ4": 40}),),
            "instructions": "Sinh một câu trắc nghiệm tính x + 1 khi x = 2 theo nguồn đã chọn.",
        }
    )
    old = {
        **old,
        "approvedGenerationPlan": job.model_dump(
            mode="json", include=set(GenerationPlan.model_fields)
        ),
    }
    repo.update_exam(job, old)
    proposal = asyncio.run(
        prepare_generation(
            job,
            OllamaProvider(model),
            repo.current,
            repo.stage,
            timeout_seconds=timeout,
        )
    )
    assert repo.snapshot(job)[0] == old
    assert repo.history_count() == 0
    path = f"/api/exams/{job.examId}/proposals/{job.jobId}/confirm"
    with app_client(repo) as client:
        confirmed = client.post(path, headers=HEADERS, json={"baseRevision": 4})
        assert confirmed.status_code == 200, confirmed.text
        assert (
            client.post(path, headers=HEADERS, json={"baseRevision": 4}).json() == confirmed.json()
        )

    saved, _ = repo.snapshot(job)
    assert saved["revision"] == 5
    assert saved["questions"][0]["id"] == confirmed.json()["changedQuestionIds"][0]
    assert saved["questions"][0]["stem"] == proposal.questions[0].stem
    assert (
        saved["questions"][0]["evidence"]
        == proposal.questions[0].model_dump(mode="json")["evidence"]
    )
    assert saved["questions"][0]["points"] == 10
    assert repo.history_count() == 1
