"""Bản chia sẻ cố định, đọc theo token và chỉ chủ sở hữu được thu hồi."""

import asyncio
import html
import json
import re
import secrets
import tempfile
import time
import unicodedata
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from mach_backend.ai_contract import AIError
from mach_backend.local_documents import export_file
from mach_backend.share_snapshot import snapshot

TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
PAGE_SIZE = 20


def search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return " ".join("".join(c for c in normalized if not unicodedata.combining(c)).split())


class ShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    examId: UUID
    baseRevision: int = Field(ge=1)
    answers: bool = False
    allowCopy: bool = False
    community: bool = False


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


def install_shares(app: FastAPI, connect, owner, read_exam, *, clock=time.time):
    rendering = asyncio.Semaphore(1)
    if AIError not in app.exception_handlers:

        async def ai_error(_request, error):
            return JSONResponse(
                {"error": str(error), "code": error.code},
                404 if error.code == "exam_not_found" else 409,
            )

        app.add_exception_handler(AIError, ai_error)
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS shared_snapshots(
            token TEXT PRIMARY KEY, owner TEXT NOT NULL, exam_id TEXT NOT NULL,
            revision INTEGER NOT NULL, created INTEGER NOT NULL, revoked INTEGER NOT NULL,
            answers INTEGER NOT NULL, allow_copy INTEGER NOT NULL,
            snapshot TEXT NOT NULL, html TEXT NOT NULL)""")
        db.execute("CREATE INDEX IF NOT EXISTS shares_owner ON shared_snapshots(owner,exam_id)")
        db.execute("""CREATE TABLE IF NOT EXISTS community_listings(
            token TEXT PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL,
            grade TEXT NOT NULL, question_count INTEGER NOT NULL,
            search_title TEXT NOT NULL, search_subject TEXT NOT NULL
        )""")

    def read(token):
        if not TOKEN.fullmatch(token):
            raise HTTPException(404, "Liên kết không tồn tại hoặc đã thu hồi.")
        with connect() as db:
            row = db.execute(
                "SELECT snapshot,html,answers,allow_copy,revision FROM shared_snapshots "
                "WHERE token=? AND revoked=0",
                (token,),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Liên kết không tồn tại hoặc đã thu hồi.")
        return row

    def create_snapshot(body, request):
        user_id = owner(request)
        if body.community and body.answers:
            raise AIError("invalid_share", "Kho cộng đồng chỉ nhận bản học sinh.")
        _, exam = read_exam(request, str(body.examId))
        if exam.get("revision") != body.baseRevision:
            raise AIError("stale_snapshot", "Đề đã thay đổi. Mở lại Chia sẻ để chọn bản mới.")
        selected = snapshot(exam, body.answers)
        # Chỉ lưu sau khi dựng thành công toàn bộ ảnh/công thức; không giữ liên kết dở.
        with tempfile.TemporaryDirectory(prefix="exam-share-") as temp:
            output = export_file(
                {"type": "exam", "format": "html", "teacher": body.answers, "exam": selected},
                Path(temp),
                "",
            )
            content = (Path(temp) / output["filename"]).read_text(encoding="utf-8")
        _, latest = read_exam(request, str(body.examId))
        if (
            latest.get("revision") != body.baseRevision
            or snapshot(latest, body.answers) != selected
        ):
            raise AIError("stale_snapshot", "Đề vừa thay đổi trong khi tạo bản chia sẻ. Thử lại.")
        token, created = secrets.token_urlsafe(32), int(clock() * 1000)
        with connect() as db:
            db.execute(
                "INSERT INTO shared_snapshots VALUES(?,?,?,?,?,0,?,?,?,?)",
                (
                    token,
                    user_id,
                    str(body.examId),
                    body.baseRevision,
                    created,
                    int(body.answers),
                    int(body.allowCopy),
                    json.dumps(selected, ensure_ascii=False),
                    content,
                ),
            )
            if body.community:
                title = str(selected.get("title") or "Đề thi")[:240]
                subject = str(selected.get("subject") or "")[:80]
                grade = str(selected.get("grade") or "")[:16]
                db.execute(
                    "INSERT INTO community_listings VALUES(?,?,?,?,?,?,?)",
                    (
                        token,
                        title,
                        subject,
                        grade,
                        len(selected["questions"]),
                        search_text(title),
                        search_text(subject),
                    ),
                )
        return {
            "token": token,
            "url": str(request.base_url) + "s/" + token,
            "revision": body.baseRevision,
            "created": created,
            "community": body.community,
        }

    @app.post("/api/share")
    async def create(body: ShareRequest, request: Request):
        async with rendering:
            return await asyncio.to_thread(create_snapshot, body, request)

    @app.get("/api/share")
    def listing(examId: UUID, request: Request):
        user_id = owner(request)
        with connect() as db:
            rows = db.execute(
                "SELECT s.token,s.revision,s.created,s.answers,s.allow_copy,c.token IS NOT NULL "
                "FROM shared_snapshots s LEFT JOIN community_listings c ON s.token=c.token "
                "WHERE s.owner=? AND s.exam_id=? AND s.revoked=0 ORDER BY s.created DESC",
                (user_id, str(examId)),
            ).fetchall()
        return {
            "shares": [
                {
                    "token": r[0],
                    "url": str(request.base_url) + "s/" + r[0],
                    "revision": r[1],
                    "created": r[2],
                    "answers": bool(r[3]),
                    "allowCopy": bool(r[4]),
                    "community": bool(r[5]),
                }
                for r in rows
            ]
        }

    @app.get("/api/community-exams")
    def community_exams(
        request: Request,
        q: str = Query("", max_length=120),
        subject: str = Query("", max_length=80),
        grade: str = Query("", max_length=16),
        page: int = Query(1, ge=1, le=10000),
    ):
        owner(request)
        with connect() as db:
            rows = db.execute(
                "SELECT c.token,c.title,c.subject,c.grade,c.question_count,s.created,s.allow_copy "
                "FROM community_listings c JOIN shared_snapshots s ON c.token=s.token "
                "WHERE s.revoked=0 AND s.answers=0 "
                "AND instr(c.search_title, ?) > 0 "
                "AND (? = '' OR c.search_subject = ?) AND (? = '' OR c.grade = ?) "
                "ORDER BY s.created DESC,c.token LIMIT ? OFFSET ?",
                (
                    search_text(q),
                    subject.strip(),
                    search_text(subject),
                    grade.strip(),
                    grade.strip(),
                    PAGE_SIZE + 1,
                    (page - 1) * PAGE_SIZE,
                ),
            ).fetchall()
        return JSONResponse(
            {
                "exams": [
                    {
                        "token": token,
                        "title": title,
                        "subject": subject,
                        "grade": grade,
                        "questions": count,
                        "created": created,
                        "allowCopy": bool(copy),
                    }
                    for token, title, subject, grade, count, created, copy in rows[:PAGE_SIZE]
                ],
                "page": page,
                "hasMore": len(rows) > PAGE_SIZE,
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/share/revoke")
    def revoke(body: RevokeRequest, request: Request):
        user_id = owner(request)
        with connect() as db:
            found = db.execute(
                "UPDATE shared_snapshots SET revoked=1 WHERE token=? AND owner=?",
                (body.token, user_id),
            ).rowcount
        if not found:
            raise HTTPException(404, "Không tìm thấy liên kết của bạn.")
        return {"ok": True}

    @app.get("/api/share/read/{token}")
    def shared_data(token: str):
        row = read(token)
        return JSONResponse(
            {
                "allowCopy": bool(row[3]),
                "revision": row[4],
                **({"exam": json.loads(row[0])} if row[3] else {}),
            },
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @app.get("/s/{token}")
    def view(token: str):
        row = read(token)
        copy = (
            '<a href="/?copy=' + html.escape(token, quote=True) + '">Tạo bản sao riêng</a>'
            if row[3]
            else ""
        )
        bar = (
            '<nav class="shared-bar" aria-label="Bản chia sẻ"><div><b>Bản chia sẻ · chỉ xem</b>'
            "<span>Bản "
            + str(row[4])
            + (" · Có đáp án" if row[2] else " · Bản học sinh")
            + "</span></div><div>"
            + copy
            + '<button type="button" onclick="window.print()">In bản này</button></div></nav>'
        )
        content = row[1].replace(
            "<body>", '<body><link rel="stylesheet" href="/assets/shared-view.css">' + bar, 1
        )
        return HTMLResponse(
            content,
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Robots-Tag": "noindex, nofollow",
                "X-Content-Type-Options": "nosniff",
            },
        )
