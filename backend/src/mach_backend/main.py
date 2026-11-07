"""Minimal executable foundation. Business routes are team migration tasks."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Soạn đề thi Python API", version="0.1.0")


@app.get("/api/health")
async def health() -> dict[str, str | bool]:
    """Liveness only; does not claim that DB, AI or migrations are ready."""
    return {"ok": True, "service": "mach-python", "stage": "foundation"}


@app.get("/api/readiness", status_code=503)
async def readiness() -> JSONResponse:
    """Do not promote a scaffold as a production-ready exam application."""
    return JSONResponse(
        status_code=503,
        content={
            "ready": False,
            "pending": ["authentication", "database", "exam-api", "ai-jobs", "documents"],
        },
    )
