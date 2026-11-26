"""Chế độ nhóm tại máy: phiên đăng nhập và kho Python riêng theo tài khoản."""

import asyncio
import os
import re
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from mach_backend.ai_contract import AIError
from mach_backend.exam_rooms import install_exam_rooms, is_public_room_path
from mach_backend.local_credentials import LocalConnectionStore
from mach_backend.local_workspace import ROOT, create_app
from mach_backend.poc_connections import apply_config
from mach_backend.team_accounts import SESSION_SECONDS, TeamAccounts, digest, identity
from mach_backend.workspace_backup import BACKUP_PATHS, MAX_BACKUP
from mach_backend.workspace_shares import install_shares
from mach_backend.workspace_store import WorkspaceStore

COOKIE = "soande_team_session"


class SignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=200)


class Register(SignIn):
    name: str = Field(min_length=1, max_length=100)
    inviteCode: str = Field(min_length=20, max_length=100)


class Invitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)


def create_team_app(directory: Path, *, agent_call=None, clock=None):
    app = FastAPI(title="Soạn đề thi · Chế độ nhóm tại máy")
    accounts = TeamAccounts(directory, **({"clock": clock} if clock else {}))
    app.state.accounts = accounts
    # shortcut: giữ app cho mỗi thành viên tới khi tắt; thêm eviction khi phục vụ nhiều nhóm.
    app.state.workspaces = workspaces = {}
    start_lock = asyncio.Lock()

    def account_info(current):
        return {
            "user": current,
            "workspace": "team:" + current["id"],
            "localPoC": True,
            "teamMode": True,
            "sharedSnapshots": True,
            "localOnly": True,
            "online": True,
            "admin": current["role"] == "admin",
            "credits": {"balance": 1000},
        }

    def workspace(current):
        user_id = current["id"]
        if user_id not in workspaces:
            workspaces[user_id] = create_app(
                directory / "users" / user_id,
                agent_call=agent_call,
                account_info=account_info(current),
            )
        return workspaces[user_id]

    def user(request):
        if not hasattr(request.state, "team_user"):
            request.state.team_user = accounts.user(request.cookies.get(COOKIE))
        return request.state.team_user

    def administrator(request):
        current = user(request)
        if not current:
            raise HTTPException(401, "Đăng nhập trước khi tiếp tục.")
        if current["role"] != "admin":
            raise HTTPException(403, "Chỉ quản trị viên được đổi cấu hình hoặc mời thành viên.")
        return current

    def _team_lan_rooms_enabled() -> bool:
        if os.environ.get("MACH_ALLOW_LAN_ROOMS") == "1":
            return True
        try:
            with accounts.connect() as db:
                row = db.execute(
                    "SELECT 1 FROM exam_rooms "
                    "WHERE allow_lan = 1 AND status IN ('open', 'closed') LIMIT 1"
                ).fetchone()
                return row is not None
        except sqlite3.OperationalError:
            return False

    @app.middleware("http")
    async def boundary(request, call_next):
        host, origin = request.headers.get("host", "").split(":")[0], request.headers.get("origin")
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            if not (is_public_room_path(request.url.path) and _team_lan_rooms_enabled()):
                return JSONResponse({"error": "Chế độ nhóm này chỉ dùng tại máy."}, 403)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin != str(
            request.base_url
        ).rstrip("/"):
            return JSONResponse({"error": "Nguồn yêu cầu không hợp lệ."}, 403)
        length = request.headers.get("content-length", "0")
        limit = 8192 if request.url.path.startswith("/api/account/") else 30 * 1024 * 1024
        if request.url.path in BACKUP_PATHS:
            limit = MAX_BACKUP
        if not length.isdigit() or int(length) > limit:
            return JSONResponse({"error": "Yêu cầu quá lớn."}, 413)
        expected = request.headers.get("X-Workspace-Context")
        if expected is not None and request.url.path.startswith("/api/"):
            current = user(request)
            if current is None:
                return JSONResponse({"error": "Phiên hết hạn. Đăng nhập lại."}, 401)
            if expected != "team:" + current["id"]:
                return JSONResponse(
                    {
                        "error": "Tài khoản đã đổi ở tab khác. Tải lại trang để mở đúng kho.",
                        "code": "workspace_context_changed",
                    },
                    409,
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(HTTPException)
    async def error(_request, exc):
        return JSONResponse({"error": exc.detail}, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request, _exc):
        return JSONResponse(
            {"error": "Kiểm tra các trường bắt buộc. Mật khẩu cần từ 10 đến 200 ký tự."}, 422
        )

    @app.get("/login")
    def login_page():
        return FileResponse(ROOT / "assets/team-login.html")

    @app.get("/api/team/health")
    def health():
        return {
            "ok": True,
            "teamMode": True,
            "localOnly": True,
            "instance": digest(str(directory.resolve()).casefold())[:16],
        }

    @app.get("/api/account")
    def account(request: Request):
        current = user(request)
        if not current:
            raise HTTPException(401, "Đăng nhập trước khi mở kho đề.")
        return account_info(current)

    def signed_in(result):
        current, token = result
        response = JSONResponse({"user": current})
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            samesite="strict",
            secure=False,
            max_age=SESSION_SECONDS,
        )
        return response

    @app.post("/api/account/login")
    def login(body: SignIn, request: Request):
        return signed_in(
            accounts.login(
                body.email,
                body.password,
                request.client.host if request.client else "unknown",
                with_session=True,
            )
        )

    @app.post("/api/account/register")
    def register(body: Register):
        return signed_in(
            accounts.create(
                body.email, body.password, body.name, body.inviteCode, with_session=True
            )
        )

    @app.post("/api/account/logout")
    def logout(request: Request):
        accounts.logout(request.cookies.get(COOKIE))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, httponly=True, samesite="strict")
        return response

    @app.post("/api/account/invitations")
    def invitation(body: Invitation, request: Request):
        administrator(request)
        email = identity(body.email, "validation-only")
        token = accounts.invite(email=email)
        return {"inviteCode": token, "email": email, "expiresIn": 86400}

    def share_owner(request):
        current = user(request)
        if current is None:
            raise HTTPException(401, "Đăng nhập trước khi chia sẻ.")
        return current["id"]

    def share_exam(request, exam_id):
        current = user(request)
        if current is None:
            raise HTTPException(401, "Đăng nhập trước khi chia sẻ.")
        return workspace(current).state.store.exam(exam_id)

    def _team_read_file_bytes(req_owner: str, fid: str):
        clean_fid = str(fid or "").strip()
        if not clean_fid or re.fullmatch(r"[\w-]+", clean_fid) is None:
            return None
        ws = workspaces.get(req_owner)
        try:
            if ws is not None:
                return ws.state.store.get("file:" + clean_fid)["value"]
            return WorkspaceStore(directory / "users" / req_owner, owner=req_owner).get(
                "file:" + clean_fid
            )["value"]
        except (HTTPException, AIError, KeyError, OSError):
            return None

    install_shares(app, accounts.connect, share_owner, share_exam, clock=accounts.clock)
    install_exam_rooms(
        app,
        accounts.connect,
        share_owner,
        share_exam,
        read_file_bytes=_team_read_file_bytes,
        clock=accounts.clock,
    )

    class Dispatch:
        async def __call__(self, scope, receive, send):
            request = Request(scope, receive)
            current = user(request)
            path = request.url.path
            if current is None:
                if path.startswith("/api/"):
                    await JSONResponse({"error": "Phiên hết hạn. Đăng nhập lại."}, 401)(
                        scope, receive, send
                    )
                    return
                if path in {"", "/"}:
                    copy = request.query_params.get("copy", "")
                    if len(copy) == 43 and all(c.isalnum() or c in "_-" for c in copy):
                        target = "/login?copy=" + copy
                    else:
                        target = "/login"
                    await RedirectResponse(target)(scope, receive, send)
                    return
                candidate = (ROOT / path.lstrip("/")).resolve()
                relative = candidate.relative_to(ROOT) if candidate.is_relative_to(ROOT) else None
                allowed = relative and (
                    (len(relative.parts) == 1 and candidate.suffix in {".js", ".css"})
                    or (
                        relative.parts[0] == "assets"
                        and candidate.suffix
                        in {
                            ".js",
                            ".mjs",
                            ".css",
                            ".svg",
                            ".woff",
                            ".woff2",
                            ".ttf",
                            ".png",
                            ".json",
                        }
                    )
                    or relative.as_posix() == "assets/exam-room.html"
                )
                response = (
                    FileResponse(candidate)
                    if allowed and candidate.is_file()
                    else JSONResponse({"error": "Không tìm thấy."}, 404)
                )
                await response(scope, receive, send)
                return
            child = workspace(current)
            if (
                (
                    path in {"/api/config", "/api/test-provider"}
                    or (path.startswith("/api/providers/") and path.endswith("/test"))
                )
                and request.method != "GET"
                and current["role"] != "admin"
            ):
                await JSONResponse(
                    {"error": "Chỉ quản trị viên được đổi hoặc thử kết nối AI."}, 403
                )(scope, receive, send)
                return
            changing = path == "/api/config" and request.method == "POST"
            starting = request.method == "POST" and (
                path.endswith("/proposals/generate")
                or path.endswith("/agent/auto-create")
                or path.endswith("/check")
                or path
                in {
                    "/api/assistant/chat",
                    "/api/assistant/chat/stream",
                    "/api/assistant/patch",
                    "/api/ai/matrix",
                    "/api/ai/exam-plan",
                    "/api/ocr",
                    "/api/extract",
                }
            )

            async def run():
                if current["role"] != "admin":
                    admin = accounts.administrator()
                    master = workspace(admin).state.provider if admin else None
                    provider = child.state.provider
                    if (
                        master
                        and master.connection_stamp != provider.connection_stamp
                        and not child.state.ai_busy()
                    ):
                        master_ext = getattr(master, "extended_policy", None)
                        apply_config(
                            provider,
                            {
                                "routes": {
                                    "generate": master.provider_name,
                                    "check": master.review_provider_name or master.provider_name,
                                },
                                "gemini": {
                                    "key": master.gemini_key,
                                    "backupKey": master.gemini_backup_key,
                                    "extraKeys": list(getattr(master, "gemini_extra_keys", ())),
                                    "clearExtraKeys": not bool(
                                        getattr(master, "gemini_extra_keys", ())
                                    ),
                                    "clearKey": not bool(master.gemini_key),
                                    "clearBackupKey": not bool(master.gemini_backup_key),
                                    "freeTierConfirmed": master.gemini_free_tier,
                                    "model": master.gemini_model,
                                    "autoFallback": master.gemini_auto_fallback,
                                    "checkModel": master.review_gemini_model,
                                },
                                "deepseek": {
                                    "url": getattr(
                                        master, "deepseek_url", "https://api.deepseek.com/v1"
                                    ),
                                    "key": getattr(master, "deepseek_key", ""),
                                    "clearKey": not bool(getattr(master, "deepseek_key", "")),
                                    "model": getattr(master, "deepseek_model", "deepseek-chat"),
                                    "reasonerModel": getattr(
                                        master, "deepseek_reasoner_model", "deepseek-reasoner"
                                    ),
                                    "crossModel": getattr(master, "deepseek_cross_model", ""),
                                    "backupModels": list(
                                        getattr(master, "deepseek_backup_models", ())
                                    ),
                                    "sessionLimitUsd": float(
                                        getattr(master, "deepseek_session_limit_usd", 0.5)
                                    ),
                                    "totalLimitUsd": float(
                                        getattr(master, "deepseek_total_limit_usd", 5.0)
                                    ),
                                },
                                "fixedRouter": {
                                    "enabled": bool(getattr(master, "fixed_router_enabled", True)),
                                    "timePreset": (
                                        master_ext.timePreset if master_ext else "standard"
                                    ),
                                    "timeoutSeconds": (
                                        master_ext.timeoutSeconds if master_ext else 300
                                    ),
                                    "maxModelCalls": (
                                        master_ext.maxModelCalls if master_ext else 30
                                    ),
                                    "maxRepairRounds": (
                                        master_ext.maxRepairRounds if master_ext else 3
                                    ),
                                    "agyCustomPath": getattr(master, "agy_custom_path", ""),
                                    "agyModel": getattr(master, "agy_model", ""),
                                    "agyFastModel": getattr(master, "agy_fast_model", ""),
                                    "agyEffort": getattr(master, "agy_effort", "medium"),
                                    "autoPilot": bool(getattr(master, "auto_pilot", True)),
                                    "workspaceAiConsent": bool(
                                        getattr(master, "workspace_ai_consent", False)
                                    ),
                                },
                                "ollama": {
                                    "model": master.model,
                                    "checkModel": master.review_model,
                                },
                                "runBudget": master.run_policy.model_dump(),
                                "saveLocally": False,
                            },
                            LocalConnectionStore(directory / "users" / current["id"]),
                            persist=False,
                        )

                await child(scope, receive, send)

            if changing or starting:
                async with start_lock:
                    if any(item.state.ai_busy() for item in workspaces.values()):
                        await JSONResponse(
                            {"error": "Chờ tác vụ AI đang chạy hoàn tất.", "code": "job_limit"}, 409
                        )(scope, receive, send)
                    else:
                        await run()
            else:
                await run()

    app.mount("/", Dispatch())
    return app


app = create_team_app(Path(os.environ.get("MACH_TEAM_DATA_DIR", ROOT / ".data/team-workspace")))
