"""Cấu hình PoC; lưu mã hóa theo tài khoản Windows khi người dùng chọn lưu cục bộ."""

import asyncio
import re
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from mach_backend.agy_cli_model import (
    AGY_RECOMMENDED_MODELS,
    DEFAULT_AGY_FAST_MODEL,
    DEFAULT_AGY_ORCHESTRATOR_MODEL,
    VALID_EFFORT_LEVELS,
    build_sanitized_env,
    detect_agy_cli,
    is_blocked_agy_model,
)
from mach_backend.ai_contract import AIError
from mach_backend.ai_router import reset_shared_circuit_breaker
from mach_backend.ai_safety import (
    extract_api_key_token,
    load_local_secrets_env,
    normalize_openai_base_url,
    redact_secrets,
)
from mach_backend.ai_service import OllamaProvider
from mach_backend.deepseek_model import is_valid_gateway_model
from mach_backend.gemini_model import (
    _VERTEX_DISABLED_KEY_HASHES,
    GEMINI_MODEL,
    GEMINI_MODELS,
    VERTEX_EXPRESS_BASE,
    GeminiKeyPool,
    _vertex_key_hash,
    clean_api_key,
    is_vertex_express_key,
)
from mach_backend.local_credentials import LocalConnectionStore
from mach_backend.poc_policy import TIME_PRESET_POLICIES, ExtendedRunPolicy, RunPolicy
from mach_backend.workspace_agent import AgentGeneration

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEEPSEEK_BASE = "https://api.deepseek.com/v1"
OLLAMA_DEFAULT_BASE = "http://127.0.0.1:11434"
_VALID_AGY_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")
_EMBED_HINTS = ("embed", "bge-m3", "nomic-embed", "mxbai-embed", "all-minilm", "arctic-embed")
_VISION_HINTS = (
    "vision",
    "-vl",
    "qwen2.5vl",
    "qwen3-vl",
    "llava",
    "bakllava",
    "minicpm-v",
    "moondream",
    "llama3.2-vision",
    "gemma3",
    "ocr",
)


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


def connection_config(provider: AgentGeneration, *, mask_gateway_url: bool = False):
    extra_keys = getattr(provider, "gemini_extra_keys", ())
    extended = getattr(provider, "extended_policy", None) or ExtendedRunPolicy()
    ds_url = getattr(provider, "deepseek_url", DEEPSEEK_BASE)
    is_default_gateway = str(ds_url or DEEPSEEK_BASE).rstrip("/") == DEEPSEEK_BASE.rstrip("/")
    exposed_ds_url = (
        DEEPSEEK_BASE
        if is_default_gateway
        else ("[cổng riêng đã cấu hình]" if mask_gateway_url else ds_url)
    )
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
            "url": exposed_ds_url,
            "customGatewayConfigured": not is_default_gateway,
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
            "agyModel": getattr(provider, "agy_model", DEFAULT_AGY_ORCHESTRATOR_MODEL)
            or DEFAULT_AGY_ORCHESTRATOR_MODEL,
            "agyFastModel": getattr(provider, "agy_fast_model", DEFAULT_AGY_FAST_MODEL)
            or DEFAULT_AGY_FAST_MODEL,
            "agyEffort": getattr(provider, "agy_effort", "medium") or "medium",
            "autoPilot": bool(getattr(provider, "auto_pilot", True)),
            "workspaceAiConsent": bool(getattr(provider, "workspace_ai_consent", False)),
            "agyRecommendedModels": list(AGY_RECOMMENDED_MODELS),
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
            saved_fr = saved.get("fixedRouter")
            if isinstance(saved_fr, dict):
                if not str(saved_fr.get("agyModel") or "").strip() or is_blocked_agy_model(
                    saved_fr.get("agyModel")
                ):
                    saved_fr["agyModel"] = DEFAULT_AGY_ORCHESTRATOR_MODEL
                if not str(saved_fr.get("agyFastModel") or "").strip() or is_blocked_agy_model(
                    saved_fr.get("agyFastModel")
                ):
                    saved_fr["agyFastModel"] = DEFAULT_AGY_FAST_MODEL
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

    @app.get("/api/providers/health")
    async def providers_health():
        return await probe_providers_health(provider, None)

    @app.post("/api/providers/{provider_name}/test")
    async def provider_single_test(provider_name: str, request: Request):
        payload: dict[str, Any] = {}
        raw_body = await request.body()
        if raw_body.strip():
            try:
                parsed = await request.json()
            except ValueError:
                raise HTTPException(
                    400, "Dữ liệu kiểm tra kết nối không phải JSON hợp lệ."
                ) from None
            if not isinstance(parsed, dict):
                raise HTTPException(400, "Dữ liệu kiểm tra kết nối không hợp lệ.")
            payload = parsed
        return await test_single_provider(provider_name, provider, None, payload=payload)


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


def _parse_agy_model_field(value: object, *, default: str, label: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or "\r" in value or "\n" in value:
        raise HTTPException(400, f"{label} không hợp lệ (2–80 ký tự chữ/số/._:/-).")
    cleaned = value.strip()
    if not cleaned:
        return default
    if is_blocked_agy_model(cleaned):
        raise HTTPException(
            400,
            f"{label} chứa mô hình không được phép sử dụng; hãy chọn mô hình gợi ý hợp lệ.",
        )
    if not _VALID_AGY_MODEL_RE.fullmatch(cleaned):
        raise HTTPException(400, f"{label} không hợp lệ (2–80 ký tự chữ/số/._:/-).")
    return cleaned


def _parse_fixed_router_config(
    provider: AgentGeneration, fixed_router: object
) -> tuple[bool, ExtendedRunPolicy, str, str, str, str, bool, bool]:
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

    default_agy_model = (
        getattr(provider, "agy_model", DEFAULT_AGY_ORCHESTRATOR_MODEL)
        or DEFAULT_AGY_ORCHESTRATOR_MODEL
    )
    agy_model = _parse_agy_model_field(
        fixed_router.get("agyModel", default_agy_model),
        default=DEFAULT_AGY_ORCHESTRATOR_MODEL,
        label="Tên model AGY CLI",
    )

    default_fast_model = (
        getattr(provider, "agy_fast_model", DEFAULT_AGY_FAST_MODEL) or DEFAULT_AGY_FAST_MODEL
    )
    agy_fast_model = _parse_agy_model_field(
        fixed_router.get("agyFastModel", default_fast_model),
        default=DEFAULT_AGY_FAST_MODEL,
        label="Tên model tầng nhanh AGY CLI",
    )

    raw_effort = fixed_router.get("agyEffort", getattr(provider, "agy_effort", "medium"))
    if raw_effort is None or (isinstance(raw_effort, str) and not raw_effort.strip()):
        agy_effort = getattr(provider, "agy_effort", "medium") or "medium"
    elif not isinstance(raw_effort, str) or raw_effort.strip().lower() not in VALID_EFFORT_LEVELS:
        raise HTTPException(
            400, "Mức độ suy luận AGY không hợp lệ (chọn low, medium, high, xhigh hoặc max)."
        )
    else:
        agy_effort = raw_effort.strip().lower()

    auto_pilot = fixed_router.get("autoPilot", getattr(provider, "auto_pilot", True))
    if type(auto_pilot) is not bool:
        raise HTTPException(400, "Lựa chọn tự động hoàn toàn không hợp lệ.")

    workspace_ai_consent = fixed_router.get(
        "workspaceAiConsent", getattr(provider, "workspace_ai_consent", False)
    )
    if type(workspace_ai_consent) is not bool:
        raise HTTPException(400, "Lựa chọn cho phép AI toàn không gian làm việc không hợp lệ.")

    current_ext = getattr(provider, "extended_policy", None) or ExtendedRunPolicy()
    if not fixed_router:
        return (
            fixed_enabled,
            current_ext,
            agy_custom_path,
            agy_model,
            agy_fast_model,
            agy_effort,
            auto_pilot,
            workspace_ai_consent,
        )

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
    return (
        fixed_enabled,
        extended_policy,
        agy_custom_path,
        agy_model,
        agy_fast_model,
        agy_effort,
        auto_pilot,
        workspace_ai_consent,
    )


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
    (
        fixed_enabled,
        extended_policy,
        agy_custom_path,
        agy_model,
        agy_fast_model,
        agy_effort,
        auto_pilot,
        workspace_ai_consent,
    ) = _parse_fixed_router_config(provider, body.get("fixedRouter", {}))
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
                            "agyModel": agy_model,
                            "agyFastModel": agy_fast_model,
                            "agyEffort": agy_effort,
                            "autoPilot": auto_pilot,
                            "workspaceAiConsent": workspace_ai_consent,
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
    provider.agy_model = agy_model
    provider.agy_fast_model = agy_fast_model
    provider.agy_effort = agy_effort
    provider.auto_pilot = auto_pilot
    provider.workspace_ai_consent = workspace_ai_consent
    provider.provider_name = selected
    provider.review_provider_name = (
        check_provider if routes.get("check") else provider.review_provider_name
    )
    provider.review_gemini_model = check_gemini_model
    provider.review_model = check_local_model
    provider.run_policy = policy
    reset_shared_circuit_breaker()
    return connection_config(provider)


def _classify_ollama_tags(name: str, details: Mapping[str, Any] | None = None) -> list[str]:
    lower = name.casefold()
    caps_raw: list[str] = []
    if isinstance(details, Mapping):
        for cap in details.get("capabilities", ()) or ():
            caps_raw.append(str(cap).casefold())
        for fam in details.get("families", ()) or ():
            caps_raw.append(str(fam).casefold())
    joined_caps = " ".join(caps_raw)

    is_embed = any(h in lower for h in _EMBED_HINTS) or "embedding" in joined_caps
    if is_embed:
        return ["embed"]
    tags = ["chat"]
    if any(h in lower for h in _VISION_HINTS) or "vision" in joined_caps:
        tags.append("vision")
    return tags


def _resolve_health_inputs(
    config: Any, secrets: Mapping[str, Any] | None
) -> tuple[dict[str, Any], list[str]]:
    secret_map = dict(secrets or {})
    if isinstance(config, Mapping):
        ollama_cfg = dict(config.get("ollama") or {})
        fixed_cfg = dict(config.get("fixedRouter") or {})
        ds_cfg = dict(config.get("deepseek") or {})
        gemini_cfg = dict(config.get("gemini") or {})
        ollama_url = str(
            ollama_cfg.get("url") or config.get("ollamaUrl") or OLLAMA_DEFAULT_BASE
        ).rstrip("/")
        ollama_model = str(ollama_cfg.get("model") or config.get("model") or "")
        agy_custom_path = str(
            secret_map.get("agyCustomPath")
            or fixed_cfg.get("agyCustomPath")
            or config.get("agyCustomPath")
            or ""
        ).strip()
        agy_model = (
            str(fixed_cfg.get("agyModel") or config.get("agyModel") or "").strip()
            or DEFAULT_AGY_ORCHESTRATOR_MODEL
        )
        agy_fast_model = (
            str(fixed_cfg.get("agyFastModel") or config.get("agyFastModel") or "").strip()
            or DEFAULT_AGY_FAST_MODEL
        )
        ds_url = str(
            secret_map.get("gatewayBaseUrl")
            or secret_map.get("deepseekUrl")
            or ds_cfg.get("url")
            or DEEPSEEK_BASE
        ).rstrip("/")
        if ds_url == "[cổng riêng đã cấu hình]":
            ds_url = DEEPSEEK_BASE
        ds_key = str(
            secret_map.get("deepseekKey")
            or secret_map.get("gatewayApiKey")
            or (secret_map.get("deepseek") or {}).get("key", "")
            or ds_cfg.get("key")
            or ""
        ).strip()
        ds_model = str(ds_cfg.get("model") or "deepseek-chat")
        ds_spent_session = float(ds_cfg.get("spentSessionUsd") or 0.0)
        ds_spent_total = float(ds_cfg.get("spentTotalUsd") or 0.0)
        gemini_free_tier = bool(gemini_cfg.get("freeTierConfirmed", True))
        gemini_model = str(gemini_cfg.get("model") or GEMINI_MODEL)
        raw_g_keys: list[str] = []
        for source in (secret_map, secret_map.get("gemini") or {}, gemini_cfg):
            if not isinstance(source, Mapping):
                continue
            for kfield in ("key", "geminiKey", "backupKey", "geminiBackupKey"):
                if isinstance(source.get(kfield), str) and source[kfield].strip():
                    raw_g_keys.append(source[kfield].strip())
            for list_field in ("extraKeys", "geminiExtraKeys", "geminiKeys", "keys"):
                seq = source.get(list_field)
                if isinstance(seq, (list, tuple)):
                    raw_g_keys.extend(str(item).strip() for item in seq if str(item).strip())
        key_pool = gemini_cfg.get("keyPool") or secret_map.get("geminiKeyPool")
        cooldown_override = gemini_cfg.get("cooldownSlots") or secret_map.get("cooldownSlots")
        disabled_override = gemini_cfg.get("disabledKeys") or secret_map.get("disabledKeys")
    else:
        ollama_url = OLLAMA_DEFAULT_BASE
        ollama_model = str(getattr(config, "model", "") or "")
        agy_custom_path = str(
            secret_map.get("agyCustomPath") or getattr(config, "agy_custom_path", "") or ""
        ).strip()
        agy_model = (
            str(getattr(config, "agy_model", "") or "").strip() or DEFAULT_AGY_ORCHESTRATOR_MODEL
        )
        agy_fast_model = (
            str(getattr(config, "agy_fast_model", "") or "").strip() or DEFAULT_AGY_FAST_MODEL
        )
        ds_url = str(
            secret_map.get("gatewayBaseUrl")
            or getattr(config, "deepseek_url", DEEPSEEK_BASE)
            or DEEPSEEK_BASE
        ).rstrip("/")
        ds_key = str(
            secret_map.get("deepseekKey")
            or secret_map.get("gatewayApiKey")
            or getattr(config, "deepseek_key", "")
            or ""
        ).strip()
        ds_model = str(getattr(config, "deepseek_model", "deepseek-chat") or "deepseek-chat")
        ds_spent_session = float(getattr(config, "deepseek_spent_session_usd", 0.0) or 0.0)
        ds_spent_total = float(getattr(config, "deepseek_spent_total_usd", 0.0) or 0.0)
        gemini_free_tier = bool(getattr(config, "gemini_free_tier", False))
        gemini_model = str(getattr(config, "gemini_model", GEMINI_MODEL) or GEMINI_MODEL)
        raw_g_keys = list(getattr(config, "all_gemini_keys", ()) or ())
        if not raw_g_keys:
            raw_g_keys = [
                k
                for k in (
                    getattr(config, "gemini_key", ""),
                    getattr(config, "gemini_backup_key", ""),
                    *tuple(getattr(config, "gemini_extra_keys", ()) or ()),
                )
                if k
            ]
        key_pool = getattr(config, "gemini_key_pool", None)
        cooldown_override = None
        disabled_override = None

    raw_g_keys = list(dict.fromkeys(raw_g_keys))
    secrets_to_redact = [k for k in (ds_key, *raw_g_keys) if k]
    return (
        {
            "ollamaUrl": ollama_url,
            "ollamaModel": ollama_model,
            "agyCustomPath": agy_custom_path,
            "agyModel": agy_model,
            "agyFastModel": agy_fast_model,
            "dsUrl": ds_url,
            "dsKey": ds_key,
            "dsModel": ds_model,
            "dsSpentSession": round(ds_spent_session, 4),
            "dsSpentTotal": round(ds_spent_total, 4),
            "geminiFreeTier": gemini_free_tier,
            "geminiModel": gemini_model,
            "geminiKeys": raw_g_keys,
            "keyPool": key_pool,
            "cooldownOverride": cooldown_override,
            "disabledOverride": disabled_override,
        },
        secrets_to_redact,
    )


async def _probe_ollama_health(
    state: dict[str, Any],
    http_client: httpx.AsyncClient,
) -> dict[str, Any]:
    url = state["ollamaUrl"]
    try:
        ver_resp = await http_client.get(f"{url}/api/version", timeout=5.0)
        if ver_resp.status_code >= 300:
            return {
                "reachable": False,
                "url": url,
                "version": None,
                "models": [],
                "chatModels": [],
                "visionModels": [],
                "embedModels": [],
                "error": f"Ollama trả HTTP {ver_resp.status_code}.",
            }
        version = str((ver_resp.json() or {}).get("version") or "").strip() or None
        tags_resp = await http_client.get(f"{url}/api/tags", timeout=5.0)
        raw_models = (
            (tags_resp.json() or {}).get("models", []) if tags_resp.status_code < 300 else []
        )
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {
            "reachable": False,
            "url": url,
            "version": None,
            "models": [],
            "chatModels": [],
            "visionModels": [],
            "embedModels": [],
            "error": f"Không kết nối được Ollama cục bộ: {exc}",
        }

    models_out: list[dict[str, Any]] = []
    chat_models: list[str] = []
    vision_models: list[str] = []
    embed_models: list[str] = []
    for item in raw_models:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if not name:
            continue
        tags = _classify_ollama_tags(
            name, item.get("details") if isinstance(item.get("details"), Mapping) else item
        )
        if "chat" in tags:
            chat_models.append(name)
        if "vision" in tags:
            vision_models.append(name)
        if "embed" in tags:
            embed_models.append(name)
        models_out.append(
            {
                "name": name,
                "size": item.get("size"),
                "tags": tags,
                "remote": bool(item.get("remote_host")),
            }
        )
    return {
        "reachable": True,
        "url": url,
        "version": version,
        "models": models_out,
        "chatModels": chat_models,
        "visionModels": vision_models,
        "embedModels": embed_models,
        "error": None,
    }


async def _probe_agy_health(state: dict[str, Any], agy_runner: Any = None) -> dict[str, Any]:
    custom_path = state["agyCustomPath"]
    agy_model = state["agyModel"]
    agy_fast_model = state.get("agyFastModel") or DEFAULT_AGY_FAST_MODEL
    exe = detect_agy_cli(custom_path)
    if not exe:
        return {
            "available": False,
            "detected": False,
            "path": "",
            "version": None,
            "agyModel": agy_model,
            "agyFastModel": agy_fast_model,
            "error": "Không tìm thấy tệp thực thi AGY CLI.",
        }
    run_fn = agy_runner or subprocess.run
    try:
        completed = await asyncio.to_thread(
            run_fn,
            [exe, "--version"],
            env=build_sanitized_env(),
            timeout=5,
            shell=False,
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "detected": True,
            "path": exe,
            "version": None,
            "agyModel": agy_model,
            "agyFastModel": agy_fast_model,
            "error": "Kiểm tra phiên bản AGY CLI quá thời hạn 5 giây.",
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "available": False,
            "detected": True,
            "path": exe,
            "version": None,
            "agyModel": agy_model,
            "agyFastModel": agy_fast_model,
            "error": f"Không chạy được AGY CLI: {exc}",
        }

    raw_out = getattr(completed, "stdout", b"") or getattr(completed, "stderr", b"")
    text_out = (
        raw_out.decode("utf-8", errors="replace").strip()
        if isinstance(raw_out, bytes)
        else str(raw_out or "").strip()
    )
    returncode = getattr(completed, "returncode", 0)
    ok = returncode == 0
    return {
        "available": ok,
        "detected": True,
        "path": exe,
        "version": text_out.splitlines()[0].strip() if text_out else None,
        "agyModel": agy_model,
        "agyFastModel": agy_fast_model,
        "error": None if ok else (text_out[:240] or f"AGY CLI thoát mã {returncode}."),
    }


def _deepseek_error_message(status_code: int) -> tuple[str, str]:
    if status_code == 401:
        return (
            "auth_error",
            "Khóa DeepSeek hoặc cổng API không hợp lệ (HTTP 401). Mở Kết nối để kiểm tra lại khóa.",
        )
    if status_code == 402:
        return (
            "insufficient_balance",
            "Tài khoản DeepSeek hết số dư (HTTP 402). Nạp thêm hoặc dùng kênh dự phòng.",
        )
    if status_code == 429:
        return (
            "rate_limited",
            "DeepSeek đang gặp giới hạn tốc độ 429; chờ ít phút hoặc chuyển kênh dự phòng.",
        )
    if status_code == 403:
        return ("auth_error", "Cổng DeepSeek từ chối quyền truy cập (HTTP 403).")
    return ("http_error", f"Cổng DeepSeek trả HTTP {status_code}.")


async def _probe_deepseek_health(
    state: dict[str, Any],
    http_client: httpx.AsyncClient,
    secret_list: list[str],
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ds_key = state["dsKey"]
    ds_url = state["dsUrl"]
    base_info = {
        "configured": bool(ds_key),
        "url": ds_url if ds_url == DEEPSEEK_BASE else "[cổng riêng đã cấu hình]",
        "model": state["dsModel"],
        "spentSessionUsd": state["dsSpentSession"],
        "spentTotalUsd": state["dsSpentTotal"],
    }
    if not ds_key:
        return {
            **base_info,
            "ok": False,
            "reachable": False,
            "status": "unconfigured",
            "message": "Chưa cấu hình khóa DeepSeek hoặc cổng API.",
        }
    try:
        headers = {"Authorization": f"Bearer {ds_key}"}
        if payload and payload.get("testChat"):
            resp = await http_client.post(
                f"{ds_url}/chat/completions",
                json={
                    "model": str(payload.get("model") or state["dsModel"]),
                    "messages": [{"role": "user", "content": str(payload.get("prompt") or "OK")}],
                    "max_tokens": 8,
                    "stream": False,
                },
                headers=headers,
                timeout=8.0,
            )
        else:
            resp = await http_client.get(f"{ds_url}/models", headers=headers, timeout=5.0)
        if resp.status_code == 404 and ds_url != DEEPSEEK_BASE:
            return {
                **base_info,
                "ok": True,
                "reachable": True,
                "status": "configured",
                "message": "Cổng API đã cấu hình khóa (không mở danh sách /models).",
            }
        if resp.status_code >= 300:
            err_code, err_msg = _deepseek_error_message(resp.status_code)
            return {
                **base_info,
                "ok": False,
                "reachable": resp.status_code < 500,
                "status": err_code,
                "httpStatus": resp.status_code,
                "message": str(redact_secrets(err_msg, secret_list)),
            }
        return {
            **base_info,
            "ok": True,
            "reachable": True,
            "status": "ready",
            "message": "Kết nối DeepSeek / cổng API sẵn sàng.",
        }
    except httpx.TimeoutException:
        return {
            **base_info,
            "ok": False,
            "reachable": False,
            "status": "timeout",
            "message": "Kiểm tra DeepSeek quá thời gian phản hồi.",
        }
    except httpx.HTTPError as exc:
        return {
            **base_info,
            "ok": False,
            "reachable": False,
            "status": "unreachable",
            "message": str(redact_secrets(f"Không kết nối được DeepSeek: {exc}", secret_list)),
        }


def _summarize_gemini_pool(state: dict[str, Any]) -> dict[str, Any]:
    raw_keys: list[str] = state["geminiKeys"]
    valid_tokens: list[str] = []
    invalid_count = 0
    for raw in raw_keys:
        if "\n" in raw or "\r" in raw:
            invalid_count += 1
            continue
        tok = extract_api_key_token(raw)
        if 8 <= len(tok) <= 300:
            valid_tokens.append(tok)
        else:
            invalid_count += 1

    key_pool = state.get("keyPool")
    cooldown_slots: set[int] = set()
    disabled_indices: set[int] = set()
    if isinstance(key_pool, GeminiKeyPool):
        key_pool.refresh_cooldowns()
        for slot_key, until in key_pool.cooldown_until.items():
            if until > time.monotonic():
                slot_idx = (
                    slot_key[1] if isinstance(slot_key, tuple) and len(slot_key) >= 2 else slot_key
                )
                cooldown_slots.add(int(slot_idx))
        disabled_indices.update(int(i) for i in key_pool.invalid)
        disabled_indices.update(int(i) for i in key_pool.vertex_disabled_slots)
    else:
        for idx, tok in enumerate(valid_tokens):
            if is_vertex_express_key(tok) and _vertex_key_hash(tok) in _VERTEX_DISABLED_KEY_HASHES:
                disabled_indices.add(idx)

    if isinstance(state.get("cooldownOverride"), (list, tuple, set)):
        cooldown_slots.update(int(i) for i in state["cooldownOverride"])
    if isinstance(state.get("disabledOverride"), int):
        disabled_count = int(state["disabledOverride"])
    elif isinstance(state.get("disabledOverride"), (list, tuple, set)):
        disabled_count = len(state["disabledOverride"])
    else:
        disabled_count = len(disabled_indices)

    vertex_count = sum(1 for tok in valid_tokens if is_vertex_express_key(tok))
    valid_count = len(valid_tokens)
    active_count = max(0, valid_count - len(cooldown_slots) - disabled_count)
    return {
        "configured": valid_count > 0,
        "freeTierConfirmed": bool(state["geminiFreeTier"]),
        "model": state["geminiModel"],
        "models": list(GEMINI_MODELS),
        "validKeys": valid_count,
        "invalidKeys": invalid_count,
        "cooldownSlots": sorted(cooldown_slots),
        "cooldownCount": len(cooldown_slots),
        "disabledKeys": disabled_count,
        "activeKeys": active_count,
        "vertexExpressKeys": vertex_count,
    }


async def probe_providers_health(
    config: Any,
    secrets: Mapping[str, Any] | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    agy_runner: Any = None,
) -> dict[str, Any]:
    """Kiểm tra tình trạng tất cả provider AI (Ollama, AGY CLI, DeepSeek/Gateway, Gemini Pool)."""
    state, secret_list = _resolve_health_inputs(config, secrets)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(trust_env=False, follow_redirects=False)
    try:
        ollama_res, agy_res, ds_res = await asyncio.gather(
            _probe_ollama_health(state, http_client),
            _probe_agy_health(state, agy_runner=agy_runner),
            _probe_deepseek_health(state, http_client, secret_list),
        )
        gemini_res = _summarize_gemini_pool(state)
        result = {
            "ollama": ollama_res,
            "agy": agy_res,
            "deepseek": ds_res,
            "gemini": gemini_res,
            "checkedAt": int(time.time()),
        }
        return redact_secrets(result, secret_list)
    finally:
        if owns_client:
            await http_client.aclose()


async def test_single_provider(
    provider: str,
    config: Any,
    secrets: Mapping[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    agy_runner: Any = None,
) -> dict[str, Any]:
    """Kiểm tra trực tiếp một nhà cung cấp AI cụ thể và trả thông báo tiếng Việt rõ ràng."""
    target = str(provider or "").strip().casefold()
    state, secret_list = _resolve_health_inputs(config, secrets)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(trust_env=False, follow_redirects=False)
    try:
        if target == "ollama":
            res = await _probe_ollama_health(state, http_client)
            if payload and payload.get("testChat") and res.get("reachable"):
                model_name = str(payload.get("model") or state["ollamaModel"] or "").strip()
                if model_name:
                    chat_resp = await http_client.post(
                        f"{state['ollamaUrl']}/api/chat",
                        json={
                            "model": model_name,
                            "stream": False,
                            "messages": [
                                {"role": "user", "content": str(payload.get("prompt") or "OK")}
                            ],
                        },
                        timeout=15.0,
                    )
                    res["chatStatusCode"] = chat_resp.status_code
            return redact_secrets(
                {"provider": "ollama", "ok": res["reachable"], **res}, secret_list
            )
        if target == "agy":
            res = await _probe_agy_health(state, agy_runner=agy_runner)
            return redact_secrets({"provider": "agy", "ok": res["available"], **res}, secret_list)
        if target in {"deepseek", "gateway"}:
            res = await _probe_deepseek_health(state, http_client, secret_list, payload=payload)
            return redact_secrets({"provider": target, **res}, secret_list)
        if target == "gemini":
            summary = _summarize_gemini_pool(state)
            if summary["validKeys"] == 0:
                return redact_secrets(
                    {
                        "provider": "gemini",
                        "ok": False,
                        "status": "unconfigured",
                        "message": "Chưa có khóa Gemini hợp lệ để kiểm tra.",
                        **summary,
                    },
                    secret_list,
                )
            first_key = extract_api_key_token(state["geminiKeys"][0])
            test_model = str((payload or {}).get("model") or state["geminiModel"] or GEMINI_MODEL)
            try:
                if is_vertex_express_key(first_key):
                    resp = await http_client.post(
                        f"{VERTEX_EXPRESS_BASE}/{test_model}:generateContent",
                        json={
                            "contents": [{"role": "user", "parts": [{"text": "OK"}]}],
                            "generationConfig": {"maxOutputTokens": 4},
                        },
                        headers={"Content-Type": "application/json", "x-goog-api-key": first_key},
                        timeout=8.0,
                    )
                else:
                    resp = await http_client.get(
                        f"{GEMINI_BASE}/models?pageSize=1",
                        headers={"x-goog-api-key": first_key},
                        timeout=5.0,
                    )
                if resp.status_code in {401, 403}:
                    return redact_secrets(
                        {
                            "provider": "gemini",
                            "ok": False,
                            "status": "auth_error",
                            "httpStatus": resp.status_code,
                            "message": f"Khóa Gemini bị từ chối (HTTP {resp.status_code}).",
                            **summary,
                        },
                        secret_list,
                    )
                if resp.status_code == 429:
                    return redact_secrets(
                        {
                            "provider": "gemini",
                            "ok": False,
                            "status": "rate_limited",
                            "httpStatus": 429,
                            "message": (
                                "Khóa Gemini đang chạm hạn mức 429; thử khóa dự phòng "
                                "hoặc chờ phục hồi."
                            ),
                            **summary,
                        },
                        secret_list,
                    )
                if resp.status_code >= 300:
                    return redact_secrets(
                        {
                            "provider": "gemini",
                            "ok": False,
                            "status": "http_error",
                            "httpStatus": resp.status_code,
                            "message": f"Gemini trả HTTP {resp.status_code}.",
                            **summary,
                        },
                        secret_list,
                    )
                return redact_secrets(
                    {
                        "provider": "gemini",
                        "ok": True,
                        "status": "ready",
                        "message": "Khóa Gemini sẵn sàng.",
                        **summary,
                    },
                    secret_list,
                )
            except httpx.HTTPError as exc:
                return redact_secrets(
                    {
                        "provider": "gemini",
                        "ok": False,
                        "status": "unreachable",
                        "message": f"Không kết nối được Gemini: {exc}",
                        **summary,
                    },
                    secret_list,
                )
        return {
            "provider": target,
            "ok": False,
            "status": "unsupported_provider",
            "message": f"Không hỗ trợ kiểm tra provider '{target}'.",
        }
    finally:
        if owns_client:
            await http_client.aclose()
