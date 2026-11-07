from fastapi.testclient import TestClient

from mach_backend.main import app

client = TestClient(app)


def test_python_service_liveness_does_not_claim_business_readiness() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "mach-python",
        "stage": "foundation",
    }
    readiness = client.get("/api/readiness")
    assert readiness.status_code == 503
    assert readiness.json()["ready"] is False
    assert "authentication" in readiness.json()["pending"]


def test_no_fake_business_routes_or_proxy_to_node() -> None:
    assert client.get("/api/kv").status_code == 404
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Soạn đề thi Python API"
    assert set(schema["paths"]) == {"/api/health", "/api/readiness"}
