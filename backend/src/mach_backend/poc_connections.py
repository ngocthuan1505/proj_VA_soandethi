"""Cấu hình PoC; lưu mã hóa theo tài khoản Windows khi người dùng chọn lưu cục bộ."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from mach_backend.ai_contract import AIError
from mach_backend.ai_safety import (
    extract_api_key_token,
    load_local_secrets_env,
    normalize_openai_base_url,
)
from mach_backend.ai_service import OllamaProvider
from mach_backend.deepseek_model import is_valid_gateway_model
from mach_backend.gemini_model import GEMINI_MODEL, GEMINI_MODELS, clean_api_key
from mach_backend.local_credentials import LocalConnectionStore
from mach_backend.poc_policy import TIME_PRESET_POLICIES, ExtendedRunPolicy, RunPolicy
from mach_backend.workspace_agent import AgentGeneration

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEEPSEEK_BASE = "https://api.deepseek.com/v1"


def hydrate_provider_from_secrets_env(
    provider: AgentGeneration,
    path: Path | None = None,
    *,
    allow_in_pytest: bool = True,
) -> bool:
    """Nạp mặc định khóa Gemini và cổng API từ api-keys.env vào RAM (không ghi ra đĩa)."""
    loaded = load_local_secrets_env(path, allow_in_pytest=allow_in_pytest)
    if not loaded:
        return False
    hydrated = False
    gemini_keys = loaded.get("geminiKeys")
    if isinstance(gemini_keys, tuple) and gemini_keys and not provider.gemini_key:
        provider.gemini_key = gemini_keys[0]
        provider.gemini_backup_key = gemini_keys[1] if len(gemini_keys) > 1 else ""
        provider.gemini_extra_keys = tuple(gemini_keys[2:8])
        provider.gemini_free_tier = True
        hydrated = True

    gateway_key = loaded.get("gatewayApiKey")
    if isinstance(gateway_key, str) and gateway_key and not provider.deepseek_key:
        provider.deepseek_key = gateway_key
        if isinstance(loaded.get("gatewayBaseUrl"), str):
            provider.deepseek_url = loaded["gatewayBaseUrl"]
        if isinstance(loaded.get("gatewayFastModel"), str) and is_valid_gateway_model(
            loaded["gatewayFastModel"]
        ):
            provider.deepseek_model = loaded["gatewayFastModel"]
        if isinstance(loaded.get("gatewayProModel"), str) and is_valid_gateway_model(
            loaded["gatewayProModel"]
        ):
            provider.deepseek_reasoner_model = loaded["gatewayProModel"]
        if isinstance(loaded.get("gatewayCrossModel"), str) and is_valid_gateway_model(
            loaded["gatewayCrossModel"]
        ):
            provider.deepseek_cross_model = loaded["gatewayCrossModel"]
        raw_backups = loaded.get("gatewayBackupModels")
        if isinstance(raw_backups, tuple):
            valid_backups = tuple(m for m in raw_backups if is_valid_gateway_model(m))[:12]
            if valid_backups:
                provider.deepseek_backup_models = valid_backups
        sess_limit = loaded.get("gatewaySessionLimitUsd")
        total_limit = loaded.get("gatewayTotalLimitUsd")
        if isinstance(total_limit, float):
            provider.deepseek_total_limit_usd = total_limit
        if isinstance(sess_limit, float) and sess_limit <= provider.deepseek_total_limit_usd:
            provider.deepseek_session_limit_usd = sess_limit
        hydrated = True
    return hydrated


def connection_config(provider: AgentGeneration):
    extra_keys = getattr(provider, "gemini_extra_keys", ())
    extended = getattr(provider, "extended_policy", None) or ExtendedRunPolicy()
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
            "extraKeysCount": len(extra_keys),
            "totalKeysCount": (
                (1 if provider.gemini_key else 0)
                + (1 if provider.gemini_backup_key else 0)
                + len(extra_keys)
            ),
            "freeTierConfirmed": provider.gemini_free_tier,
            "autoFallback": provider.gemini_auto_fallback,
        },
        "deepseek": {
            "url": getattr(provider, "deepseek_url", DEEPSEEK_BASE),
            "model": getattr(provider, "deepseek_model", "deepseek-chat"),
            "reasonerModel": getattr(provider, "deepseek_reasoner_model", "deepseek-reasoner"),
            "crossModel": getattr(provider, "deepseek_cross_model", ""),
            "backupModels": list(getattr(provider, "deepseek_backup_models", ())),
            "hasKey": bool(getattr(provider, "deepseek_key", "")),
            "sessionLimitUsd": getattr(provider, "deepseek_session_limit_usd", 0.5),
            "totalLimitUsd": getattr(provider, "deepseek_total_limit_usd", 5.0),
            "spentSessionUsd": round(getattr(provider, "deepseek_spent_session_usd", 0.0), 4),
            "spentTotalUsd": round(getattr(provider, "deepseek_spent_total_usd", 0.0), 4),
        },
        "fixedRouter": {
            "enabled": getattr(provider, "fixed_router_enabled", True),
            "timePreset": extended.timePreset,
            "timeoutSeconds": extended.timeoutSeconds,
            "maxModelCalls": extended.maxModelCalls,
            "maxRepairRounds": extended.maxRepairRounds,
            "agyAvailable": bool(getattr(provider, "agy_available", False)),
            "agyCustomPathSet": bool(getattr(provider, "agy_custom_path", "")),
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
    loaded_saved = False
    try:
        saved = store.load()
        if saved:
            loaded_saved = True
            for field in ("model", "checkModel"):
                if saved.get("gemini", {}).get(field) == "gemini-3.5-flash-lite":
                    saved["gemini"][field] = GEMINI_MODEL
            apply_config(provider, saved, store, persist=False)
    except (OSError, ValueError, HTTPException, AIError):
        provider.persistence_error = (
            "Không mở được cấu hình mã hóa. Nhập lại khóa trong app nếu cần."
        )
    if not loaded_saved:
        hydrate_provider_from_secrets_env(provider, allow_in_pytest=False)

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


def _parse_extra_gemini_keys(
    gemini: dict,
    current_extra: tuple[str, ...],
    new_key: str,
    backup_key: str,
) -> tuple[str, ...]:
    if gemini.get("clearExtraKeys") is True or gemini.get("clearKey") is True:
        return ()
    extra_keys = current_extra
    if "extraKeys" in gemini and gemini["extraKeys"] is not None:
        raw_extra = gemini["extraKeys"]
        if isinstance(raw_extra, str):
            tokens = [
                part.strip()
                for line in raw_extra.splitlines()
                for part in line.split(",")
                if part.strip()
            ]
        elif isinstance(raw_extra, list) and all(isinstance(item, str) for item in raw_extra):
            tokens = [
                part.strip()
                for item in raw_extra
                for line in item.splitlines()
                for part in line.split(",")
                if part.strip()
            ]
        else:
            raise HTTPException(400, "Danh sách key Gemini bổ sung không hợp lệ.")
        if tokens:
            cleaned = [clean_api_key(token) for token in tokens]
            filtered = [k for k in dict.fromkeys(cleaned) if k not in {new_key, backup_key}]
            if len(filtered) > 6:
                raise HTTPException(400, "Tối đa 6 key Gemini dự phòng bổ sung (tổng cộng 8 key).")
            extra_keys = tuple(filtered)
    if extra_keys:
        extra_keys = tuple(k for k in extra_keys if k not in {new_key, backup_key})
        if extra_keys and not new_key:
            raise HTTPException(400, "Cần giữ một key Gemini chính khi dùng key bổ sung.")
    return extra_keys


def _parse_gateway_model_field(value: object, *, default: str, allow_empty: bool = False) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or "\r" in value or "\n" in value:
        raise HTTPException(400, "Tên model cổng API không hợp lệ.")
    cleaned = value.strip()
    if not cleaned:
        if allow_empty:
            return ""
        return default
    if not is_valid_gateway_model(cleaned):
        raise HTTPException(400, "Tên model cổng API không hợp lệ (2–80 ký tự chữ/số/._:/-).")
    return cleaned


def _parse_deepseek_config(
    provider: AgentGeneration, deepseek: object
) -> tuple[str, str, str, str, str, tuple[str, ...], float, float]:
    if not isinstance(deepseek, dict):
        raise HTTPException(400, "Cấu hình kết nối không hợp lệ.")
    ds_url = getattr(provider, "deepseek_url", DEEPSEEK_BASE)
    if "url" in deepseek and deepseek["url"] is not None:
        raw_url = deepseek["url"]
        if raw_url == "":
            ds_url = DEEPSEEK_BASE
        else:
            try:
                ds_url = normalize_openai_base_url(raw_url)
            except AIError as exc:
                raise HTTPException(400, str(exc)) from None

    ds_model = _parse_gateway_model_field(
        deepseek.get("model"),
        default=getattr(provider, "deepseek_model", "deepseek-chat"),
    )
    ds_reasoner = _parse_gateway_model_field(
        deepseek.get("reasonerModel"),
        default=getattr(provider, "deepseek_reasoner_model", "deepseek-reasoner"),
    )
    ds_cross = _parse_gateway_model_field(
        deepseek.get("crossModel"),
        default=getattr(provider, "deepseek_cross_model", ""),
        allow_empty=True,
    )

    ds_backups = tuple(getattr(provider, "deepseek_backup_models", ()))
    if "backupModels" in deepseek and deepseek["backupModels"] is not None:
        raw_backups = deepseek["backupModels"]
        if isinstance(raw_backups, str):
            tokens = [
                part.strip()
                for line in raw_backups.splitlines()
                for part in line.split(",")
                if part.strip()
            ]
        elif isinstance(raw_backups, list) and all(isinstance(item, str) for item in raw_backups):
            tokens = [part.strip() for part in raw_backups if part.strip()]
        else:
            raise HTTPException(400, "Danh sách model dự phòng của cổng API không hợp lệ.")
        validated: list[str] = []
        for token in tokens:
            if "\r" in token or "\n" in token or not is_valid_gateway_model(token):
                raise HTTPException(400, "Tên model dự phòng của cổng API không hợp lệ.")
            if token not in validated:
                validated.append(token)
        if len(validated) > 12:
            raise HTTPException(400, "Tối đa 12 model dự phòng cho cổng API.")
        ds_backups = tuple(validated)

    deepseek_key = getattr(provider, "deepseek_key", "")
    if deepseek.get("clearKey") is True:
        deepseek_key = ""
    elif "key" in deepseek and deepseek["key"] != "":
        raw_ds_key = deepseek["key"]
        if not isinstance(raw_ds_key, str) or "\r" in raw_ds_key or "\n" in raw_ds_key:
            raise HTTPException(400, "Khóa DeepSeek không hợp lệ.")
        extracted_key = extract_api_key_token(raw_ds_key)
        if not 8 <= len(extracted_key) <= 300:
            raise HTTPException(400, "Khóa DeepSeek không hợp lệ.")
        deepseek_key = extracted_key

    session_limit = deepseek.get(
        "sessionLimitUsd", getattr(provider, "deepseek_session_limit_usd", 0.5)
    )
    total_limit = deepseek.get("totalLimitUsd", getattr(provider, "deepseek_total_limit_usd", 5.0))
    if (
        type(session_limit) not in (int, float)
        or not (0.05 <= float(session_limit) <= 30.0)
        or type(total_limit) not in (int, float)
        or not (0.10 <= float(total_limit) <= 30.0)
        or float(session_limit) > float(total_limit)
    ):
        raise HTTPException(
            400, "Hạn mức DeepSeek phải từ 0.05–30.0 USD/phiên và 0.10–30.0 USD tổng."
        )
    return (
        ds_url,
        deepseek_key,
        ds_model,
        ds_reasoner,
        ds_cross,
        ds_backups,
        round(float(session_limit), 4),
        round(float(total_limit), 4),
    )


def _parse_fixed_router_config(
    provider: AgentGeneration, fixed_router: object
) -> tuple[bool, ExtendedRunPolicy, str]:
    if not isinstance(fixed_router, dict):
        raise HTTPException(400, "Cấu hình kết nối không hợp lệ.")
    fixed_enabled = fixed_router.get("enabled", getattr(provider, "fixed_router_enabled", True))
    if type(fixed_enabled) is not bool:
        raise HTTPException(400, "Lựa chọn điều phối cố định không hợp lệ.")
    agy_custom_path = fixed_router.get("agyCustomPath", getattr(provider, "agy_custom_path", ""))
    if (
        not isinstance(agy_custom_path, str)
        or "\r" in agy_custom_path
        or "\n" in agy_custom_path
        or len(agy_custom_path) > 500
    ):
        raise HTTPException(400, "Đường dẫn AGY CLI không hợp lệ.")
    agy_custom_path = agy_custom_path.strip()

    current_ext = getattr(provider, "extended_policy", None) or ExtendedRunPolicy()
    if not fixed_router:
        return fixed_enabled, current_ext, agy_custom_path

    preset = fixed_router.get("timePreset")
    raw_timeout = fixed_router.get("timeoutSeconds")
    raw_calls = fixed_router.get("maxModelCalls")
    raw_rounds = fixed_router.get("maxRepairRounds")
    if preset is None:
        if raw_timeout is not None or raw_calls is not None:
            preset = "custom"
        else:
            preset = current_ext.timePreset
    if not isinstance(preset, str) or preset not in {*TIME_PRESET_POLICIES, "custom"}:
        raise HTTPException(400, "Chế độ thời gian điều phối không hợp lệ.")
    if preset in TIME_PRESET_POLICIES:
        spec = TIME_PRESET_POLICIES[preset]
        if raw_timeout is None or (
            preset != current_ext.timePreset
            and raw_timeout == current_ext.timeoutSeconds
            and raw_timeout != spec["timeoutSeconds"]
        ):
            eff_timeout = spec["timeoutSeconds"]
        else:
            eff_timeout = raw_timeout
        if raw_calls is None or (
            preset != current_ext.timePreset
            and raw_calls == current_ext.maxModelCalls
            and raw_calls != spec["maxModelCalls"]
        ):
            eff_calls = spec["maxModelCalls"]
        else:
            eff_calls = raw_calls
    else:
        eff_timeout = current_ext.timeoutSeconds if raw_timeout is None else raw_timeout
        eff_calls = current_ext.maxModelCalls if raw_calls is None else raw_calls
    try:
        extended_policy = ExtendedRunPolicy.from_preset(
            preset, timeout_seconds=eff_timeout, max_calls=eff_calls
        )
        if raw_rounds is not None:
            extended_policy = ExtendedRunPolicy.model_validate(
                {**extended_policy.model_dump(), "maxRepairRounds": raw_rounds}
            )
    except ValidationError:
        raise HTTPException(
            400, "Khung thời gian mở rộng phải từ 30–7200 giây và 4–240 lần gọi AI."
        ) from None
    return fixed_enabled, extended_policy, agy_custom_path


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
    extra_keys = _parse_extra_gemini_keys(
        gemini,
        tuple(getattr(provider, "gemini_extra_keys", ())),
        new_key,
        backup_key,
    )
    (
        ds_url,
        deepseek_key,
        ds_model,
        ds_reasoner,
        ds_cross,
        ds_backups,
        ds_session_limit,
        ds_total_limit,
    ) = _parse_deepseek_config(provider, body.get("deepseek", {}))
    fixed_enabled, extended_policy, agy_custom_path = _parse_fixed_router_config(
        provider, body.get("fixedRouter", {})
    )
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
                            "extraKeys": list(extra_keys),
                            "freeTierConfirmed": free_tier,
                            "autoFallback": auto_fallback,
                            "model": gemini_model,
                            "checkModel": check_gemini_model,
                        },
                        "deepseek": {
                            "url": ds_url,
                            "key": deepseek_key,
                            "model": ds_model,
                            "reasonerModel": ds_reasoner,
                            "crossModel": ds_cross,
                            "backupModels": list(ds_backups),
                            "sessionLimitUsd": ds_session_limit,
                            "totalLimitUsd": ds_total_limit,
                        },
                        "fixedRouter": {
                            "enabled": fixed_enabled,
                            "timePreset": extended_policy.timePreset,
                            "timeoutSeconds": extended_policy.timeoutSeconds,
                            "maxModelCalls": extended_policy.maxModelCalls,
                            "maxRepairRounds": extended_policy.maxRepairRounds,
                            "agyCustomPath": agy_custom_path,
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
    provider.gemini_extra_keys = extra_keys
    provider.gemini_free_tier = free_tier if new_key else False
    provider.gemini_auto_fallback = auto_fallback
    provider.gemini_model = gemini_model
    provider.deepseek_url = ds_url
    provider.deepseek_key = deepseek_key
    provider.deepseek_model = ds_model
    provider.deepseek_reasoner_model = ds_reasoner
    provider.deepseek_cross_model = ds_cross
    provider.deepseek_backup_models = ds_backups
    provider.deepseek_session_limit_usd = ds_session_limit
    provider.deepseek_total_limit_usd = ds_total_limit
    provider.fixed_router_enabled = fixed_enabled
    provider.extended_policy = extended_policy
    provider.agy_custom_path = agy_custom_path
    provider.provider_name = selected
    provider.review_provider_name = (
        check_provider if routes.get("check") else provider.review_provider_name
    )
    provider.review_gemini_model = check_gemini_model
    provider.review_model = check_local_model
    provider.run_policy = policy
    return connection_config(provider)
