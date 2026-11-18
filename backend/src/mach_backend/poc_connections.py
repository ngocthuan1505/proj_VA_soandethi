"""Cấu hình PoC; lưu mã hóa theo tài khoản Windows khi người dùng chọn lưu cục bộ."""

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from mach_backend.ai_service import OllamaProvider
from mach_backend.gemini_model import GEMINI_MODEL, GEMINI_MODELS, clean_api_key
from mach_backend.local_credentials import LocalConnectionStore
from mach_backend.poc_policy import RunPolicy
from mach_backend.workspace_agent import AgentGeneration

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def connection_config(provider: AgentGeneration):
    return {
        "localPoC": True,
        "ollama": {
            "url": "http://127.0.0.1:11434",
            "model": provider.model,
            "checkModel": provider.review_model
            if provider.review_provider_name
            else provider.model,
        },
        "gemini": {
            "url": GEMINI_BASE,
            "model": provider.gemini_model,
            "models": GEMINI_MODELS,
            "checkModel": provider.review_gemini_model
            if provider.review_provider_name
            else provider.gemini_model,
            "hasKey": bool(provider.gemini_key),
            "hasBackupKey": bool(provider.gemini_backup_key),
            "freeTierConfirmed": provider.gemini_free_tier,
            "autoFallback": provider.gemini_auto_fallback,
        },
        "routes": {
            "generate": provider.provider_name,
            "patch": provider.provider_name,
            "check": provider.review_provider_name or provider.provider_name,
        },
        "runBudget": provider.run_policy.model_dump(),
        "fingerprint": provider.connection_stamp,
        "saveLocally": provider.persist_locally,
        "persistence": {
            "available": provider.persistence_available,
            "saved": provider.connection_saved,
            "warning": provider.persistence_error,
        },
    }


def install_poc_connections(app: FastAPI, provider: AgentGeneration):
    store = LocalConnectionStore(provider.directory.parent)
    provider.persistence_available = store.available
    provider.persist_locally = store.available
    try:
        saved = store.load()
        if saved:
            for field in ("model", "checkModel"):
                if saved.get("gemini", {}).get(field) == "gemini-3.5-flash-lite":
                    saved["gemini"][field] = GEMINI_MODEL
            apply_config(provider, saved, store, persist=False)
    except (OSError, ValueError, HTTPException):
        provider.persistence_error = (
            "Không mở được cấu hình mã hóa. Nhập lại khóa trong app nếu cần."
        )

    @app.get("/api/config")
    def config():
        return connection_config(provider)

    @app.post("/api/config")
    async def update_config(request: Request):
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "Cấu hình không phải JSON hợp lệ.") from None
        return apply_config(provider, body, store)


def apply_config(provider, body, store, *, persist=True):
    if not isinstance(body, dict):
        raise HTTPException(400, "Cấu hình kết nối không hợp lệ.")
    gemini, ollama, routes = (
        body.get("gemini", {}),
        body.get("ollama", {}),
        body.get("routes", {}),
    )
    if any(not isinstance(item, dict) for item in (gemini, ollama, routes)):
        raise HTTPException(400, "Cấu hình kết nối không hợp lệ.")
    selected = routes.get("generate", provider.provider_name)
    if not isinstance(selected, str) or selected not in {"ollama", "gemini"}:
        raise HTTPException(400, "PoC hiện hỗ trợ Ollama hoặc Gemini.")
    check_provider = routes.get("check") or provider.review_provider_name or selected
    if (
        routes.get("check") is not None and not isinstance(routes["check"], str)
    ) or check_provider not in {"ollama", "gemini"}:
        raise HTTPException(400, "Chọn Ollama hoặc Gemini cho bộ kiểm.")
    if gemini.get("url", GEMINI_BASE) != GEMINI_BASE:
        raise HTTPException(400, "Chỉ gửi khóa tới endpoint Gemini chính thức.")
    gemini_model = gemini.get("model", provider.gemini_model)
    if gemini_model not in GEMINI_MODELS:
        raise HTTPException(400, "Chọn model Gemini trong danh sách Free tier đã kiểm.")
    check_gemini_model = gemini.get("checkModel", provider.review_gemini_model)
    if check_gemini_model not in GEMINI_MODELS:
        raise HTTPException(400, "Model kiểm Gemini chưa được cho phép.")
    new_key = provider.gemini_key
    if gemini.get("clearKey") is True:
        new_key = ""
    elif gemini.get("key"):
        new_key = clean_api_key(gemini["key"])
    backup_key = provider.gemini_backup_key
    if gemini.get("clearBackupKey") is True:
        backup_key = ""
    elif gemini.get("backupKey"):
        backup_key = clean_api_key(gemini["backupKey"])
    if backup_key and (not new_key or backup_key == new_key):
        raise HTTPException(400, "Key dự phòng phải khác key chính và cần giữ một key chính.")
    free_tier = gemini.get("freeTierConfirmed", provider.gemini_free_tier) is True
    auto_fallback = gemini.get("autoFallback", provider.gemini_auto_fallback)
    if type(auto_fallback) is not bool:
        raise HTTPException(400, "Lựa chọn tự đổi model cần bật hoặc tắt.")
    if "gemini" in {selected, check_provider} and (not new_key or not free_tier):
        raise HTTPException(400, "Nhập key và xác nhận project Gemini đang ở Free tier.")
    local_model = ollama.get("model") or provider.model
    if not isinstance(local_model, str):
        raise HTTPException(400, "Tên model local không hợp lệ.")
    OllamaProvider(local_model)
    check_local_model = ollama.get("checkModel") or provider.review_model
    if not isinstance(check_local_model, str):
        raise HTTPException(400, "Tên model kiểm local không hợp lệ.")
    OllamaProvider(check_local_model)
    try:
        policy = RunPolicy.model_validate(body.get("runBudget", provider.run_policy.model_dump()))
    except ValidationError:
        raise HTTPException(
            400, "Ngân sách phải từ 4–64 lần gọi AI, thời gian 30–900 giây."
        ) from None
    save_locally = body.get("saveLocally", provider.persist_locally)
    if type(save_locally) is not bool:
        raise HTTPException(400, "Lựa chọn lưu cục bộ không hợp lệ.")
    if persist:
        try:
            if save_locally:
                store.save(
                    {
                        "saveLocally": True,
                        "routes": {"generate": selected, "check": check_provider},
                        "gemini": {
                            "key": new_key,
                            "backupKey": backup_key,
                            "freeTierConfirmed": free_tier,
                            "autoFallback": auto_fallback,
                            "model": gemini_model,
                            "checkModel": check_gemini_model,
                        },
                        "ollama": {"model": local_model, "checkModel": check_local_model},
                        "runBudget": policy.model_dump(),
                    }
                )
            else:
                store.clear()
        except (OSError, TimeoutError):
            raise HTTPException(
                503, "Không lưu được cấu hình mã hóa. Cấu hình cũ được giữ nguyên."
            ) from None
    provider.persist_locally = save_locally
    provider.connection_saved = store.path.is_file()
    provider.persistence_error = None
    provider.model = local_model
    provider.gemini_key = new_key
    provider.gemini_backup_key = backup_key
    provider.gemini_free_tier = free_tier if new_key else False
    provider.gemini_auto_fallback = auto_fallback
    provider.gemini_model = gemini_model
    provider.provider_name = selected
    provider.review_provider_name = (
        check_provider if routes.get("check") else provider.review_provider_name
    )
    provider.review_gemini_model = check_gemini_model
    provider.review_model = check_local_model
    provider.run_policy = policy
    return connection_config(provider)
