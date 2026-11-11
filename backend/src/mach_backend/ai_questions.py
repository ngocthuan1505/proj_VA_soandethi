"""Kiểu dữ liệu và kiểm tra câu hỏi sinh mới hoặc giải lại."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

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

QuestionType = Literal["mcq", "essay", "short", "truefalse"]
Choice = Annotated[int, Field(ge=0, le=3)]
ShortAnswer = Annotated[str, Field(min_length=1, max_length=1000)]
type Answer = Choice | ShortAnswer | tuple[bool, bool, bool, bool] | None
PointsQ4 = Annotated[int, Field(ge=1, le=40)]
EvidenceList = Annotated[tuple[Evidence, ...], Field(max_length=12)]


class ExamSlot(ContractModel):
    type: QuestionType
    topic: Annotated[str, Field(min_length=1, max_length=200)]
    level: Annotated[int, Field(ge=0, le=2)]
    pointsQ4: PointsQ4


class GenerationPlan(ContractModel):
    subject: Annotated[str, Field(min_length=1, max_length=100)]
    grade: Annotated[str, Field(min_length=1, max_length=80)]
    instructions: Annotated[str, Field(max_length=4000)] = ""
    slots: Annotated[tuple[ExamSlot, ...], Field(min_length=1, max_length=30)]


class GenerateJob(AIJob, GenerationPlan):
    pass


class RubricStep(ContractModel):
    text: BlockText
    pointsQ4: PointsQ4


class GeneratedQuestion(ExamSlot):
    stem: BlockText
    options: Annotated[tuple[BlockText, ...], Field(max_length=4)]
    answer: Answer
    explanation: BlockText
    rubric: Annotated[tuple[RubricStep, ...], Field(min_length=1, max_length=40)]
    evidence: EvidenceList


class GenerateProposal(JobIdentity):
    questions: Annotated[tuple[GeneratedQuestion, ...], Field(min_length=1, max_length=30)]


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


def validate_generation_plan(job: GenerateJob) -> None:
    if (
        not job.subject.strip()
        or not job.grade.strip()
        or any(not slot.topic.strip() for slot in job.slots)
        or sum(slot.pointsQ4 for slot in job.slots) != 40
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


def validate_generation(job: GenerateJob, raw: str) -> GenerateProposal:
    proposal = read_result(job, raw, GenerateProposal)
    if len(proposal.questions) != len(job.slots):
        raise AIError("invalid_plan", "Số câu AI trả về chưa khớp ma trận đã duyệt.")
    for slot, question in zip(job.slots, proposal.questions, strict=True):
        if (slot.type, slot.topic, slot.level, slot.pointsQ4) != (
            question.type,
            question.topic,
            question.level,
            question.pointsQ4,
        ):
            raise AIError("invalid_plan", "Dạng, chủ đề, mức độ hoặc điểm không khớp ma trận.")
        validate_ai_text(question.stem)
        validate_options(question.type, question.options)
        validate_answer(question.type, question.answer)
        validate_ai_text(question.explanation)
        if sum(step.pointsQ4 for step in question.rubric) != slot.pointsQ4:
            raise AIError("invalid_rubric", "Tổng điểm barem chưa bằng điểm của câu.")
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
