"""Khôi phục state và tệp cùng một transaction; không phục hồi khóa hay tác vụ AI cũ."""

import base64
import binascii
import io
import json
import math
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Never
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from PIL import Image
from pydantic import ValidationError

from mach_backend.ai_contract import AIError
from mach_backend.curriculum_sources import (
    CITABLE_LICENSE_STATUSES,
    CurriculumSourceCreate,
    compute_source_sha256,
)
from mach_backend.local_documents import pdf_pages
from mach_backend.matrix_import import MIME
from mach_backend.matrix_templates import (
    list_owner_matrix_templates,
    validate_and_restore_matrix_templates,
)
from mach_backend.question_bank import (
    list_owner_question_bank,
    validate_and_restore_question_bank,
)

MAX_BACKUP = 150 * 1024 * 1024
MAX_FILE = 15 * 1024 * 1024
BACKUP_PATHS = {"/api/workspace/restore/preview", "/api/workspace/restore"}
FILE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
OFFICE = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word/",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xl/",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "ppt/",
}
ATTACHMENT_MIME = {
    **MIME,
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def invalid(message="Bản sao không đúng định dạng hoặc thiếu dữ liệu đề.") -> Never:
    raise AIError("invalid_backup", message)


def finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        invalid("Bản sao chứa số không hợp lệ. Chưa thay dữ liệu.")
    return number


def file_references(value):
    """Duyệt cả history/undo/redo, không chỉ các nguồn đang mở."""
    found: dict[str, set[str]] = {}
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if depth > 50 or count > 500000:
            invalid("Bản sao quá phức tạp; hãy tách bớt lịch sử trước khi xuất.")
        if isinstance(item, dict):
            if item.get("fileId") is not None:
                key = item["fileId"]
                if not isinstance(key, str) or not FILE_ID.fullmatch(key):
                    invalid("Mã tệp trong bản sao không hợp lệ.")
                types = found.setdefault(key, set())
                name = item.get("name")
                if isinstance(name, str) and (
                    mime := ATTACHMENT_MIME.get(Path(name).suffix.lower())
                ):
                    types.add(mime)
            stack.extend((v, depth + 1) for v in item.values() if isinstance(v, (dict, list)))
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item if isinstance(v, (dict, list)))
    return found


def check_file(key, value, referenced_types):
    if not isinstance(key, str) or not FILE_ID.fullmatch(key) or not isinstance(value, str):
        invalid("Tệp đính kèm trong bản sao không hợp lệ.")
    match = re.fullmatch(r"data:([^;,]*);base64,([A-Za-z0-9+/=]+)", value)
    if match is None or len(value) > MAX_FILE * 4 // 3 + 200:
        invalid("Tệp đính kèm hỏng hoặc vượt 15 MB.")
    mime, encoded = match.groups()
    generic = mime in {"", "application/octet-stream"}
    if generic:
        if len(referenced_types) != 1:
            invalid("Tệp trong bản sao thiếu loại hoặc có tên tham chiếu không nhất quán.")
        mime = next(iter(referenced_types))
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_FILE:
            raise ValueError
        if mime in {"image/png", "image/jpeg", "image/webp"}:
            with Image.open(io.BytesIO(raw), formats=("PNG", "JPEG", "WEBP")) as image:
                if image.width * image.height > 20000000 or (
                    generic and mime != "image/" + (image.format or "").lower()
                ):
                    raise ValueError
                image.verify()
        elif mime == "application/pdf":
            pdf_pages(raw)
        elif mime in OFFICE:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if not any(name.startswith(OFFICE[mime]) for name in archive.namelist()):
                    raise ValueError
        elif mime in {"text/plain", "text/markdown"}:
            raw.decode("utf-8-sig")
        else:
            raise ValueError
    except (
        ValueError,
        OSError,
        SyntaxError,
        binascii.Error,
        zipfile.BadZipFile,
        Image.DecompressionBombError,
    ):
        invalid("Nội dung tệp đính kèm hỏng hoặc không khớp loại tệp hỗ trợ.")
    return f"data:{mime};base64,{encoded}" if generic else value


def curriculum_records(backup):
    raw = backup.get("curriculumSources", [])
    if not isinstance(raw, list) or len(raw) > 10000:
        invalid("Kho học liệu trong bản sao không hợp lệ.")
    records = {}
    for item in raw:
        try:
            source_id = str(UUID(item["id"]))
            created_at, updated_at = item["created_at"], item["updated_at"]
            if (
                source_id != item["id"]
                or source_id in records
                or type(created_at) is not int
                or type(updated_at) is not int
                or not 0 < created_at <= updated_at <= 2**53 - 1
            ):
                raise ValueError
            payload = CurriculumSourceCreate.model_validate(
                {key: item[key] for key in CurriculumSourceCreate.model_fields}
            ).model_dump()
            if compute_source_sha256(payload) != item["sha256"]:
                raise ValueError
        except (KeyError, TypeError, AttributeError, ValidationError, ValueError):
            invalid("Có học liệu sai mã, phiên bản hoặc nội dung trong bản sao.")
        records[source_id] = (payload, created_at, updated_at, item["sha256"])
    return records


def insert_curriculum_records(db, owner, records, *, dry_run=False):
    for source_id, (payload, created_at, updated_at, digest) in records.items():
        restored = dict(payload)
        if restored["license_status"] in CITABLE_LICENSE_STATUSES:
            restored["license_status"] = "pending_review"
        restored_digest = compute_source_sha256(restored)
        existing = db.execute(
            "SELECT owner_id, sha256, updated_at FROM curriculum_sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        if existing:
            if existing[0] != owner or existing[1] not in {digest, restored_digest}:
                invalid("Học liệu trùng mã với bản khác trong kho đích. Chưa thay dữ liệu.")
            if existing[2] != updated_at:
                invalid("Học liệu đã có phiên bản khác trong kho đích. Chưa thay dữ liệu.")
        elif not dry_run:
            db.execute(
                """
                INSERT INTO curriculum_sources (
                    id, owner_id, grade, subject, series, volume, chapter, lesson, title,
                    license_status, license_note, source_origin, locator, content_excerpt,
                    sha256, created_at, updated_at
                ) VALUES (
                    :id, :owner_id, :grade, :subject, :series, :volume, :chapter, :lesson, :title,
                    :license_status, :license_note, :source_origin, :locator, :content_excerpt,
                    :sha256, :created_at, :updated_at
                )
                """,
                {
                    **restored,
                    "id": source_id,
                    "owner_id": owner,
                    "sha256": restored_digest,
                    "created_at": created_at,
                    "updated_at": updated_at,
                },
            )


def _validate_exam_entry(exam: Any, ids: set[str], *, require_full_fields: bool) -> dict[str, Any]:
    if not isinstance(exam, dict) or not isinstance(exam.get("id"), str) or exam["id"] in ids:
        invalid()
    if not exam["id"].strip():
        invalid()
    ids.add(exam["id"])
    title = exam.get("title")
    if not isinstance(title, str) or not title.strip():
        invalid("Đề trong bản sao thiếu tên đề hợp lệ.")

    required_lists = (
        ("questions", "docs", "matrix", "history", "undo", "redo", "chat", "data")
        if require_full_fields
        else ("questions",)
    )
    if any(not isinstance(exam.get(k), list) for k in required_lists):
        invalid()
    if not require_full_fields:
        for k in ("docs", "matrix", "history", "undo", "redo", "chat", "data"):
            if k in exam and exam[k] is not None and not isinstance(exam[k], list):
                invalid()
        if "quote" in exam and exam["quote"] is not None:
            if not isinstance(exam["quote"], dict) or not isinstance(
                exam["quote"].get("versions"), list
            ):
                invalid()
    elif not isinstance(exam.get("quote"), dict) or not isinstance(
        exam["quote"].get("versions"), list
    ):
        invalid()

    question_ids = set()
    for q in exam["questions"]:
        if not isinstance(q, dict) or not isinstance(q.get("id"), str) or q["id"] in question_ids:
            invalid("Mã câu bị thiếu hoặc trùng trong cùng đề.")
        question_ids.add(q["id"])
        kind, options, answer = q.get("type", "mcq"), q.get("options"), q.get("answer")
        if (
            kind not in ("mcq", "essay", "short", "truefalse")
            or not isinstance(q.get("stem"), str)
            or not isinstance(options, list)
            or any(not isinstance(v, str) for v in options)
        ):
            invalid("Câu hỏi trong bản sao không hợp lệ.")
        if (
            len(options) != (0 if kind in {"essay", "short"} else 4)
            or type(q.get("level")) is not int
            or q["level"] not in range(4)
        ):
            invalid("Loại câu hoặc mức độ trong bản sao không hợp lệ.")
        legacy = type(answer) is int and answer in range(4)
        if (
            not legacy
            and not (kind == "short" and isinstance(answer, str))
            and not (
                kind == "truefalse"
                and isinstance(answer, list)
                and len(answer) == 4
                and all(type(v) is bool for v in answer)
            )
            and not (kind == "essay" and answer in (None, ""))
        ):
            invalid("Đáp án trong bản sao không đúng dạng câu.")
        if "answerText" in q and not isinstance(q["answerText"], str):
            invalid("Đáp án trả lời ngắn cần là văn bản.")
        if (
            kind == "truefalse"
            and "truthValues" in q
            and (
                not isinstance(q["truthValues"], list)
                or len(q["truthValues"]) != 4
                or any(type(v) is not bool for v in q["truthValues"])
            )
        ):
            invalid("Đáp án đúng–sai cần đủ bốn giá trị.")
    for row in exam.get("matrix") or []:
        targets = row.get("targets") if isinstance(row, dict) else None
        if (
            not isinstance(targets, list)
            or len(targets) not in {3, 4}
            or any(type(v) is not int or not 0 <= v <= 100 for v in targets)
        ):
            invalid("Ma trận trong bản sao không hợp lệ.")

    if require_full_fields:
        return exam
    normalized_exam = deepcopy(exam)
    for k in ("docs", "matrix", "history", "undo", "redo", "chat", "data"):
        if not isinstance(normalized_exam.get(k), list):
            normalized_exam[k] = []
    if not isinstance(normalized_exam.get("quote"), dict):
        normalized_exam["quote"] = {"text": "", "versions": []}
    return normalized_exam


def _remap_file_ids_in_value(value: Any, mapping: dict[str, str]) -> None:
    if not mapping:
        return
    stack: list[Any] = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            fid = item.get("fileId")
            if isinstance(fid, str) and fid in mapping:
                item["fileId"] = mapping[fid]
            stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
        elif isinstance(item, list):
            stack.extend(v for v in item if isinstance(v, (dict, list)))


def validate_backup(backup):
    if not isinstance(backup, dict) or type(backup.get("version")) is not int:
        invalid()
    fmt = backup.get("format")
    if fmt not in {"tro-ly-soan-de", "tro-ly-soan-de-batch"} or backup.get("version") != 1:
        invalid()
    files = backup.get("files", {})
    if files is None:
        files = {}
    if not isinstance(files, dict):
        invalid()

    if fmt == "tro-ly-soan-de-batch":
        if (
            "savedAt" in backup
            and backup["savedAt"] is not None
            and not isinstance(backup["savedAt"], str)
        ):
            invalid()
        raw_exams = backup.get("exams")
        if not isinstance(raw_exams, list) or not raw_exams or len(raw_exams) > 1000:
            invalid()
        ids: set[str] = set()
        normalized_exams = [
            _validate_exam_entry(exam, ids, require_full_fields=False) for exam in raw_exams
        ]
        state = {"exams": normalized_exams, "prefs": [], "current": normalized_exams[0]["id"]}
        references = file_references(normalized_exams)
        missing = references.keys() - files.keys()
        if missing:
            invalid(
                f"Bản sao thiếu {len(missing)} tệp gốc (kể cả lịch sử/hoàn tác). Chưa thay dữ liệu."
            )
        return (
            state,
            {
                key: check_file(key, value, references.get(key, set()))
                for key, value in files.items()
            },
            curriculum_records(backup),
        )

    state = backup.get("state")
    if not isinstance(state, dict) or not isinstance(state.get("prefs"), list):
        invalid()
    exams = state.get("exams")
    if not isinstance(exams, list) or not exams or len(exams) > 1000:
        invalid()
    ids = set()
    for exam in exams:
        _validate_exam_entry(exam, ids, require_full_fields=True)
    current = state.get("current")
    if not isinstance(current, str) or current not in ids:
        invalid("Bản sao thiếu đề đang mở.")
    references = file_references(state)
    missing = references.keys() - files.keys()
    if missing:
        invalid(
            f"Bản sao thiếu {len(missing)} tệp gốc (kể cả lịch sử/hoàn tác). Chưa thay dữ liệu."
        )
    return (
        state,
        {key: check_file(key, value, references.get(key, set())) for key, value in files.items()},
        curriculum_records(backup),
    )


def apply_matrix_template_records(db, owner, backup, *, dry_run=False):
    raw = backup.get("matrixTemplates")
    if raw is None:
        return 0
    try:
        return validate_and_restore_matrix_templates(db, owner, raw, dry_run=dry_run)
    except (ValidationError, ValueError, TypeError) as exc:
        message = str(exc)
        if "trong bản sao" in message or "kho đích" in message:
            invalid(message)
        invalid("Mẫu ma trận trong bản sao không hợp lệ.")


def apply_question_bank_records(db, owner, backup, *, dry_run=False):
    raw = backup.get("questionBank", [])
    if raw is None or raw == []:
        return 0
    try:
        return validate_and_restore_question_bank(db, owner, raw, dry_run=dry_run)
    except (ValidationError, ValueError, TypeError) as exc:
        message = str(exc)
        if "trong bản sao" in message or "kho đích" in message or "bản sao" in message:
            invalid(message)
        invalid("Ngân hàng câu hỏi trong bản sao không hợp lệ.")


def _list_owner_curriculum_sources(db, owner_id: str) -> list[dict]:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'curriculum_sources'"
    ).fetchone()
    if not exists:
        return []
    rows = db.execute(
        """
        SELECT id, grade, subject, series, volume, chapter, lesson, title,
               license_status, license_note, source_origin, locator, content_excerpt,
               sha256, created_at, updated_at
        FROM curriculum_sources
        WHERE owner_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (owner_id,),
    ).fetchall()
    out = []
    for row in rows:
        payload = {
            "grade": row[1],
            "subject": row[2],
            "series": row[3],
            "volume": row[4],
            "chapter": row[5],
            "lesson": row[6],
            "title": row[7],
            "license_status": row[8],
            "license_note": row[9],
            "source_origin": row[10],
            "locator": row[11],
            "content_excerpt": row[12],
        }
        out.append(
            {
                "id": row[0],
                **payload,
                "sha256": compute_source_sha256(payload),
                "created_at": row[14],
                "updated_at": row[15],
            }
        )
    return out


def export_workspace_backup(store):
    """Đóng gói snapshot sao lưu đầy đủ gồm state, files, templates, bank và học liệu."""
    with store.connect() as db:
        db.execute("BEGIN")
        state = store.get("state", db)["value"]
        files = {
            row[0].removeprefix("file:"): json.loads(row[1])
            for row in db.execute("SELECT key, value FROM kv WHERE key LIKE 'file:%'").fetchall()
        }
        matrix_templates = list_owner_matrix_templates(db, store.owner)
        question_bank = list_owner_question_bank(db, store.owner)
        curriculum_sources = _list_owner_curriculum_sources(db, store.owner)
    return {
        "format": "tro-ly-soan-de",
        "version": 1,
        "state": state,
        "files": files,
        "matrixTemplates": matrix_templates,
        "questionBank": question_bank,
        "curriculumSources": curriculum_sources,
    }


def restore(store, backup, base_revision):
    state, files, records = validate_backup(backup)
    if backup.get("format") == "tro-ly-soan-de-batch":
        skip_colliding = (
            backup.get("skipDuplicateIds") is True
            or backup.get("skipExisting") is True
            or backup.get("onCollision") == "skip"
        )
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current_state = store.get("state", db)["value"]
            if not isinstance(current_state, dict):
                current_state = {"current": None, "exams": [], "prefs": []}
            existing_exams = list(current_state.get("exams") or [])
            existing_ids = {
                e["id"]
                for e in existing_exams
                if isinstance(e, dict) and isinstance(e.get("id"), str)
            }
            file_remap: dict[str, str] = {}
            imported_files = 0
            for key, value in files.items():
                existing_file = store.get("file:" + key, db)["value"]
                if existing_file is None:
                    store.put("file:" + key, value, db=db)
                    imported_files += 1
                elif existing_file != value:
                    new_key = f"{key[:90]}-{uuid4().hex[:8]}"
                    file_remap[key] = new_key
                    store.put("file:" + new_key, value, db=db)
                    imported_files += 1

            imported_exams = 0
            skipped_exams = 0
            merged_exams = list(existing_exams)
            for incoming in state["exams"]:
                exam_copy = deepcopy(incoming)
                _remap_file_ids_in_value(exam_copy, file_remap)
                if exam_copy["id"] in existing_ids:
                    if skip_colliding:
                        skipped_exams += 1
                        continue
                    new_id = str(uuid4())
                    while new_id in existing_ids:
                        new_id = str(uuid4())
                    exam_copy["id"] = new_id
                existing_ids.add(exam_copy["id"])
                merged_exams.append(exam_copy)
                imported_exams += 1

            merged_state = {
                **current_state,
                "exams": merged_exams,
                "prefs": list(current_state.get("prefs") or []),
                "current": current_state.get("current")
                or (merged_exams[0]["id"] if merged_exams else None),
            }
            revision = store.put("state", merged_state, base_revision, db)
            insert_curriculum_records(db, store.owner, records)
            apply_matrix_template_records(db, store.owner, backup, dry_run=False)
            apply_question_bank_records(db, store.owner, backup, dry_run=False)
        return {
            "revision": revision,
            "restored": True,
            "mode": "merge_batch",
            "importedExams": imported_exams,
            "skippedExams": skipped_exams,
            "importedFiles": imported_files,
        }

    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        revision = store.put("state", state, base_revision, db)
        insert_curriculum_records(db, store.owner, records)
        apply_matrix_template_records(db, store.owner, backup, dry_run=False)
        apply_question_bank_records(db, store.owner, backup, dry_run=False)
        for key, value in files.items():
            store.put("file:" + key, value, db=db)
        # Snapshot phục hồi không được nhận kết quả AI đang chờ của kho trước.
        db.execute("DELETE FROM matrix_pending")
        db.execute("DELETE FROM matrix_trace")
        db.execute("DELETE FROM kv WHERE key LIKE 'matrix%'")
        db.execute("DELETE FROM kv WHERE key LIKE 'scoped-patch:%'")
    return {"revision": revision, "restored": True}


def install_backup(app, store, runner, chat_lock, connection_lock):
    async def payload(request):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_BACKUP:
                raise HTTPException(413, "Bản sao vượt 150 MB.")
        try:
            return json.loads(
                raw,
                parse_float=finite_float,
                parse_constant=lambda _: invalid(
                    "Bản sao chứa số không hợp lệ. Chưa thay dữ liệu."
                ),
            )
        except (ValueError, RecursionError):
            invalid("Tệp JSON hỏng hoặc quá phức tạp. Chưa thay dữ liệu.")

    @app.get("/api/workspace/backup")
    def download_backup():
        return export_workspace_backup(store)

    @app.post("/api/workspace/restore/preview")
    async def preview(request: Request):
        backup = await payload(request)
        state, files, records = validate_backup(backup)
        with store.connect() as db:
            db.execute("BEGIN")
            insert_curriculum_records(db, store.owner, records, dry_run=True)
            template_count = apply_matrix_template_records(db, store.owner, backup, dry_run=True)
            bank_count = apply_question_bank_records(db, store.owner, backup, dry_run=True)
            current_entry = store.get("state", db)
            revision = current_entry["revision"]
            current_state = current_entry["value"]
        if backup.get("format") == "tro-ly-soan-de-batch":
            existing_exams = (
                current_state.get("exams") or [] if isinstance(current_state, dict) else []
            )
            seen_titles = {
                e["title"].strip().casefold()
                for e in existing_exams
                if isinstance(e, dict) and isinstance(e.get("title"), str) and e["title"].strip()
            }
            duplicate_titles: list[str] = []
            for incoming in state["exams"]:
                title_clean = incoming["title"].strip()
                norm_title = title_clean.casefold()
                if norm_title in seen_titles and title_clean not in duplicate_titles:
                    duplicate_titles.append(title_clean)
                seen_titles.add(norm_title)
            return {
                "revision": revision,
                "mode": "merge_batch",
                "examCount": len(state["exams"]),
                "fileCount": len(files),
                "duplicateTitles": duplicate_titles,
                **({"curriculumSources": len(records)} if records else {}),
                **({"matrixTemplates": template_count} if template_count else {}),
                **({"questionBank": bank_count} if bank_count else {}),
            }
        return {
            "revision": revision,
            **({"curriculumSources": len(records)} if records else {}),
            **({"matrixTemplates": template_count} if template_count else {}),
            **({"questionBank": bank_count} if bank_count else {}),
            "exams": len(state["exams"]),
            "files": len(files),
            "prefs": len(state["prefs"]),
        }

    @app.post("/api/workspace/restore")
    async def apply(request: Request):
        backup = await payload(request)
        base = request.headers.get("if-match", "")
        if not base.isdigit():
            raise HTTPException(400, "Khôi phục cần phiên bản kho đã xem trước.")
        async with connection_lock:
            if runner.active or chat_lock.locked():
                raise AIError("job_limit", "Chờ tác vụ AI hoàn tất trước khi khôi phục.")
            return restore(store, backup, int(base))
