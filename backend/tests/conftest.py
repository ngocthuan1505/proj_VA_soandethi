"""Tùy chọn kiểm tra nhanh adapter với model Ollama cục bộ trên dữ liệu mẫu."""

import asyncio
import json

import httpx
import pytest

from mach_backend.ai_contract import AIError
from mach_backend.ai_service import OLLAMA_CHAT, OllamaProvider


def pytest_addoption(parser):
    group = parser.getgroup("Kiểm tra AI cục bộ")
    group.addoption("--smoke-ollama-model", help="Tên chính xác của model đã tải trong Ollama.")
    group.addoption("--smoke-timeout", type=float, default=120, help="Số giây tối đa mỗi ca smoke.")


@pytest.fixture(scope="session")
def smoke_settings(pytestconfig):
    model = pytestconfig.getoption("--smoke-ollama-model")
    timeout = pytestconfig.getoption("--smoke-timeout")
    if not 0 < timeout <= 300:
        pytest.fail("Thời hạn smoke phải lớn hơn 0 và tối đa 300 giây.", pytrace=False)
    if model is None:
        return "fixture", "mo-hinh-fixture", "", "", timeout

    try:
        OllamaProvider(model)
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            api = OLLAMA_CHAT.removesuffix("/chat")
            tags = client.get(api + "/tags").raise_for_status().json()["models"]
            version = client.get(api + "/version").raise_for_status().json()["version"]
            digest = next(
                (
                    entry["digest"]
                    for entry in tags
                    if entry["name"] == model and entry.get("size", 0) > 0
                ),
                None,
            )
    except (AIError, httpx.HTTPError, ValueError, KeyError, TypeError):
        pytest.fail("Không đọc được danh sách model từ Ollama cục bộ.", pytrace=False)
    if not digest:
        pytest.fail("Model đã chọn chưa có trong danh sách Ollama cục bộ.", pytrace=False)
    return "ollama-cuc-bo", model, digest, version, timeout


@pytest.fixture
def smoke_evidence(smoke_settings, record_property):
    mode, model, digest, version, timeout = smoke_settings
    record_property("che_do", mode)
    record_property("model", model)
    record_property("model_digest", digest)
    record_property("ollama_version", version)
    record_property("timeout_giay", timeout)
    return smoke_settings


@pytest.fixture
def run_smoke(smoke_evidence, record_property):
    mode, model, _, _, timeout = smoke_evidence

    def run(call, fixture_output):
        transport = None
        if mode == "fixture":
            transport = httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={
                        "done": True,
                        "done_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(fixture_output)},
                    },
                )
            )
        provider = OllamaProvider(model, transport=transport)
        try:
            return asyncio.run(call(provider, timeout))
        except AIError as error:
            record_property("ma_loi", error.code)
            pytest.fail(f"[{error.code}] {error}", pytrace=False)

    return run
