"""Kiểu trao đổi với Ollama cho đề xuất sửa và sinh câu hỏi."""

import re
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


def selected_targets(job: PatchJob) -> list[dict[str, object]]:
    targets = []
    for target in job.targets:
        prefix, suffix = selection_parts(target)
        selected = target.text[len(prefix) : len(target.text) - len(suffix)]
        payload: dict[str, object] = {"blockId": str(target.blockId), "text": selected}
        if target.context is not None:
            payload["context"] = target.context.model_dump(mode="json")
        targets.append(payload)
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


def evidence_format(sources) -> dict:
    # Model chọn đoạn có thật; backend vẫn kiểm phiên bản, trích dẫn và độ đủ căn cứ.
    evidence = GenerateProposal.model_json_schema()["$defs"]["Evidence"]
    choices = []
    for source in sources:
        quotes = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+|\n+", source.text)
            if 8 <= len(part.strip()) <= 1000
        ]
        if not quotes:
            quotes = [source.text[:1000]]
        choices.append(
            {
                **evidence,
                "properties": {
                    **evidence["properties"],
                    "sourceId": {"const": str(source.sourceId)},
                    "sourceVersion": {"const": source.sourceVersion},
                    "locator": {"const": source.locator.model_dump(mode="json")},
                    "quote": {"type": "string", "enum": quotes},
                },
            }
        )
    return choices[0] if len(choices) == 1 else {"anyOf": choices}


def generation_format(job: GenerateJob) -> dict:
    answer_formats = {
        "mcq": TypeAdapter(Choice).json_schema(),
        "truefalse": {"type": "array", "items": {"type": "boolean"}, "minItems": 4, "maxItems": 4},
        "short": TypeAdapter(ShortAnswer).json_schema(),
        "essay": {"type": "null"},
    }
    schema = GenerateProposal.model_json_schema()
    if job.sources:
        schema["$defs"]["Evidence"] = evidence_format(job.sources)
    question = schema["$defs"].pop("GeneratedQuestion")
    variants = [
        {
            **question,
            "properties": {
                **question["properties"],
                **{key: {"const": value} for key, value in slot.model_dump().items()},
                "answer": answer_formats[slot.type],
                "evidence": {
                    **question["properties"]["evidence"],
                    "minItems": 1 if job.requireEvidence else 0,
                    "maxItems": 2 if len(job.sources) == 1 else 12,
                },
                **(
                    {
                        "rubric": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["text", "pointsQ4"],
                                "properties": {
                                    "text": {"const": "Chọn đúng phương án."},
                                    "pointsQ4": {"const": slot.pointsQ4},
                                },
                            },
                        }
                    }
                    if slot.type == "mcq"
                    else {}
                ),
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
