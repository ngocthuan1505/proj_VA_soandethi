"""Kiểu dữ liệu và kiểm tra câu hỏi sinh mới hoặc giải lại."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, model_serializer, model_validator

from mach_backend.ai_contract import (
    AIError,
    AIJob,
    BlockText,
    ContractModel,
    Evidence,
    JobIdentity,
    Revision,
    read_result,
    validate_ai_text,
    validate_evidence,
)

MAX_MATRIX_QUESTIONS = 30
QuestionType = Literal["mcq", "essay", "short", "truefalse"]
Choice = Annotated[int, Field(ge=0, le=3)]
ShortAnswer = Annotated[str, Field(min_length=1, max_length=1000)]
type Answer = Choice | ShortAnswer | tuple[bool, bool, bool, bool] | None
PointsQ4 = Annotated[int, Field(ge=1, le=40)]
EvidenceList = Annotated[tuple[Evidence, ...], Field(max_length=12)]


def points_p100(item: Any) -> int:
    """Quy đổi điểm của slot/câu/barem về đơn vị nguyên 0,01 điểm."""
    q4 = getattr(item, "pointsQ4", None)
    pts = getattr(item, "points", None)
    if q4 is not None and pts is not None:
        if q4 * 25 != round(pts * 100):
            raise ValueError("pointsQ4 và points không khớp.")
        return q4 * 25
    if q4 is not None:
        return q4 * 25
    if pts is not None:
        p100 = round(float(pts) * 100)
        if not 5 <= p100 <= 1000 or abs(float(pts) * 100 - p100) > 1e-6:
            raise ValueError("Điểm phải từ 0,05 đến 10,00 điểm (tối đa 2 chữ số thập phân).")
        return p100
    raise ValueError("Cần chỉ định pointsQ4 hoặc points.")


class ExamSlot(ContractModel):
    type: QuestionType
    topic: Annotated[str, Field(min_length=1, max_length=200)]
    level: Annotated[int, Field(ge=0, le=3)]
    pointsQ4: PointsQ4 | None = None
    points: Annotated[float, Field(gt=0, le=10)] | None = None
    choiceGroup: Annotated[str, Field(min_length=1, max_length=80)] | None = None

    @model_validator(mode="after")
    def validate_points_pair(self):
        points_p100(self)
        return self

    @model_serializer(mode="wrap")
    def _omit_unset_points(self, handler):
        data = handler(self)
        for key in ("pointsQ4", "points", "choiceGroup"):
            if key in data and data[key] is None:
                data.pop(key)
        return data


class GenerationPlan(ContractModel):
    subject: Annotated[str, Field(min_length=1, max_length=100)]
    grade: Annotated[str, Field(min_length=1, max_length=80)]
    instructions: Annotated[str, Field(max_length=4000)] = ""
    slots: Annotated[
        tuple[ExamSlot, ...], Field(strict=False, min_length=1, max_length=MAX_MATRIX_QUESTIONS * 2)
    ]


class GenerateJob(AIJob, GenerationPlan):
    pass


class RubricStep(ContractModel):
    text: BlockText
    pointsQ4: PointsQ4 | None = None
    points: Annotated[float, Field(gt=0, le=10)] | None = None

    @model_validator(mode="after")
    def validate_step_points(self):
        points_p100(self)
        return self

    @model_serializer(mode="wrap")
    def _omit_unset_points(self, handler):
        data = handler(self)
        for key in ("pointsQ4", "points"):
            if key in data and data[key] is None:
                data.pop(key)
        return data


class GeneratedQuestion(ExamSlot):
    stem: BlockText
    options: Annotated[tuple[BlockText, ...], Field(max_length=4)]
    answer: Answer
    explanation: BlockText
    rubric: Annotated[tuple[RubricStep, ...], Field(min_length=1, max_length=40)]
    evidence: EvidenceList


class GenerateProposal(JobIdentity):
    questions: Annotated[
        tuple[GeneratedQuestion, ...], Field(min_length=1, max_length=MAX_MATRIX_QUESTIONS)
    ]


class BlindQuestion(ContractModel):
    questionId: UUID
    questionVersion: Revision
    type: QuestionType
    stem: BlockText
    options: Annotated[tuple[BlockText, ...], Field(max_length=4)]


class CheckJob(AIJob):
    question: BlindQuestion


class CheckProposal(JobIdentity):
    questionId: UUID
    questionVersion: Revision
    answer: Answer
    explanation: BlockText
    uncertain: bool
    evidence: EvidenceList


class CheckReport(CheckProposal):
    comparison: Literal["agrees", "disagrees", "needs_review"]
    method: Literal["local_arithmetic", "model"] = "model"


def _plan_totals_ok(slots: tuple[ExamSlot, ...]) -> bool:
    common_p100 = 0
    common_count = 0
    track_p100: dict[str, int] = {}
    track_count: dict[str, int] = {}
    for slot in slots:
        grp = (slot.choiceGroup or "").strip().casefold()
        p100 = points_p100(slot)
        if grp:
            track_p100[grp] = track_p100.get(grp, 0) + p100
            track_count[grp] = track_count.get(grp, 0) + 1
        else:
            common_p100 += p100
            common_count += 1
    active_count = common_count + (max(track_count.values()) if track_count else 0)
    if not 1 <= active_count <= MAX_MATRIX_QUESTIONS:
        return False
    if not track_p100:
        return common_p100 == 1000
    return all(common_p100 + pts == 1000 for pts in track_p100.values())


def validate_generation_plan(job: GenerateJob) -> None:
    if (
        not job.subject.strip()
        or not job.grade.strip()
        or any(not slot.topic.strip() for slot in job.slots)
        or not _plan_totals_ok(job.slots)
    ):
        raise AIError("invalid_plan", "Ma trận cần môn, lớp, chủ đề và tổng đúng 10 điểm.")


def validate_options(question_type: QuestionType, options: tuple[str, ...]) -> None:
    expected = 4 if question_type in ("mcq", "truefalse") else 0
    if len(options) != expected:
        raise AIError("invalid_options", "Số phương án chưa khớp dạng câu hỏi.")
    for option in options:
        validate_ai_text(option)
    if len({" ".join(option.split()).casefold() for option in options}) != len(options):
        raise AIError("invalid_options", "Các phương án hoặc nhận định bị lặp.")


def validate_answer(question_type: QuestionType, answer: Answer) -> None:
    valid = {
        "mcq": type(answer) is int and 0 <= answer <= 3,
        "truefalse": isinstance(answer, tuple)
        and len(answer) == 4
        and all(type(value) is bool for value in answer),
        "short": isinstance(answer, str) and bool(answer.strip()),
        "essay": answer is None,
    }
    if not valid[question_type]:
        raise AIError("invalid_answer", "Đáp án chưa khớp dạng câu hỏi.")
    if isinstance(answer, str):
        validate_ai_text(answer)


def saved_answer(question: dict) -> Answer:
    kind = question.get("type", "mcq")
    if kind == "essay" or question.get("answerKnown") is False:
        return None
    answer = question.get("answer")
    if kind == "short":
        answer = question.get("answerText") or answer
    elif kind == "truefalse":
        answer = question.get("truthValues") or answer
        if isinstance(answer, list):
            answer = tuple(answer)
    if answer is not None:
        if kind not in {"mcq", "short", "truefalse"}:
            raise AIError("invalid_answer", "Dạng câu hỏi đang lưu chưa hợp lệ.")
        validate_answer(kind, answer)
    return answer


def saved_answer_label(question: dict) -> str:
    answer = saved_answer(question)
    if answer is None:
        return "Chưa nhập đáp án"
    if type(answer) is int:
        return "ABCD"[answer]
    if isinstance(answer, tuple):
        return " · ".join(f"{i}. {'Đúng' if value else 'Sai'}" for i, value in enumerate(answer, 1))
    return str(answer)


def validate_generation(job: GenerateJob, raw: str) -> GenerateProposal:
    proposal = read_result(job, raw, GenerateProposal)
    if len(proposal.questions) != len(job.slots):
        raise AIError("invalid_plan", "Số câu AI trả về chưa khớp ma trận đã duyệt.")
    for index, (slot, question) in enumerate(zip(job.slots, proposal.questions, strict=True), 1):
        if (slot.type, slot.topic, slot.level, points_p100(slot)) != (
            question.type,
            question.topic,
            question.level,
            points_p100(question),
        ):
            raise AIError("invalid_plan", "Dạng, chủ đề, mức độ hoặc điểm không khớp ma trận.")
        validate_ai_text(question.stem)
        validate_options(question.type, question.options)
        validate_answer(question.type, question.answer)
        validate_ai_text(question.explanation)
        total = sum(points_p100(step) for step in question.rubric)
        expected = points_p100(slot)
        if total != expected:
            if slot.pointsQ4 is not None and total % 25 == 0:
                msg = (
                    f"Câu {index}: tổng barem là {total // 25}, "
                    f"cần {slot.pointsQ4} đơn vị 0,25 điểm. "
                    "Nhân điểm với 4 để được số đơn vị. Ví dụ, 2 điểm bằng 8 đơn vị."
                )
                raise AIError("invalid_rubric", msg)
            raise AIError(
                "invalid_rubric",
                f"Câu {index}: tổng barem là {total / 100:.2f} điểm, "
                f"cần {expected / 100:.2f} điểm.",
            )
        for step in question.rubric:
            validate_ai_text(step.text)
        validate_evidence(job, question.evidence)
    return proposal


def validate_check(job: CheckJob, raw: str, saved_answer: Answer) -> CheckReport:
    proposal = read_result(job, raw, CheckProposal)
    question = job.question
    if (proposal.questionId, proposal.questionVersion) != (
        question.questionId,
        question.questionVersion,
    ):
        raise AIError("wrong_job", "Lời giải không khớp câu hoặc phiên bản đã chọn.")
    validate_ai_text(proposal.explanation)
    validate_evidence(job, proposal.evidence, allow_missing=proposal.uncertain)
    if not proposal.uncertain or proposal.answer is not None:
        validate_answer(question.type, proposal.answer)
    comparison = "needs_review"
    if (
        not proposal.uncertain
        and question.type in ("mcq", "truefalse")
        and saved_answer is not None
    ):
        comparison = "agrees" if proposal.answer == saved_answer else "disagrees"
    return CheckReport.model_validate({**proposal.model_dump(), "comparison": comparison})
