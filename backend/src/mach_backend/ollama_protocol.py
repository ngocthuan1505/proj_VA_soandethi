"""Kiểu trao đổi với Ollama cho đề xuất sửa và sinh câu hỏi."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, TypeAdapter

from mach_backend.ai_contract import (
    MAX_BLOCK_TEXT,
    AIError,
    ContractModel,
    Evidence,
    JobIdentity,
    PatchJob,
    PatchProposal,
    TextEdit,
    read_result,
    selection_parts,
)
from mach_backend.ai_questions import Choice, GenerateJob, GenerateProposal, ShortAnswer


class OllamaTextEdit(ContractModel):
    op: Literal["replace"]
    blockId: UUID
    replacement: Annotated[str, Field(max_length=MAX_BLOCK_TEXT)]


class OllamaPatchDraft(JobIdentity):
    edits: Annotated[tuple[OllamaTextEdit, ...], Field(min_length=1, max_length=12)]
    evidence: Annotated[tuple[Evidence, ...], Field(max_length=12)]
    message: Annotated[str, Field(min_length=1, max_length=1000)]


def selected_targets(job: PatchJob) -> list[dict[str, str]]:
    targets = []
    for target in job.targets:
        prefix, suffix = selection_parts(target)
        selected = target.text[len(prefix) : len(target.text) - len(suffix)]
        targets.append({"blockId": str(target.blockId), "text": selected})
    return targets


def rebuild_patch(job: PatchJob, raw: str) -> str:
    draft = read_result(job, raw, OllamaPatchDraft)
    targets = {target.blockId: target for target in job.targets}
    edits = []
    for edit in draft.edits:
        target = targets.get(edit.blockId)
        if target is None:
            raise AIError("invalid_scope", "Đề xuất sửa ngoài vùng chọn.")
        prefix, suffix = selection_parts(target)
        content = prefix + edit.replacement + suffix
        if not content or len(content) > MAX_BLOCK_TEXT:
            raise AIError("invalid_result", "Văn bản sau sửa rỗng hoặc vượt giới hạn.")
        edits.append(TextEdit(op=edit.op, blockId=edit.blockId, content=content))
    return PatchProposal(
        jobId=draft.jobId,
        examId=draft.examId,
        baseRevision=draft.baseRevision,
        edits=tuple(edits),
        evidence=draft.evidence,
        message=draft.message,
    ).model_dump_json()


def generation_format(job: GenerateJob) -> dict:
    answer_formats = {
        "mcq": TypeAdapter(Choice).json_schema(),
        "truefalse": {"type": "array", "items": {"type": "boolean"}, "minItems": 4, "maxItems": 4},
        "short": TypeAdapter(ShortAnswer).json_schema(),
        "essay": {"type": "null"},
    }
    schema = GenerateProposal.model_json_schema()
    question = schema["$defs"].pop("GeneratedQuestion")
    variants = [
        {
            **question,
            "properties": {
                **question["properties"],
                **{key: {"const": value} for key, value in slot.model_dump().items()},
                "answer": answer_formats[slot.type],
            },
        }
        for slot in dict.fromkeys(job.slots)
    ]
    schema["properties"]["questions"].update(
        items=variants[0] if len(variants) == 1 else {"anyOf": variants},
        minItems=len(job.slots),
        maxItems=len(job.slots),
    )
    return schema
