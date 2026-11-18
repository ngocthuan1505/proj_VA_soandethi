FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium ca-certificates fonts-liberation fonts-dejavu-core fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 soande \
    && install -d -o soande -g soande /var/lib/soande

WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 MACH_DATA_DIR=/var/lib/soande BROWSER_PATH=/usr/bin/chromium
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --project backend --frozen --no-dev --no-install-project

COPY backend/src ./backend/src
COPY backend/poc-data ./backend/poc-data
COPY *.js *.css index.html THIRD_PARTY.md ./
COPY assets ./assets

USER soande
EXPOSE 4182
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD ["/app/backend/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4182/api/kv?key=state', timeout=3).close()"]
CMD ["/app/backend/.venv/bin/python", "-m", "uvicorn", "mach_backend.local_workspace:app", "--app-dir", "backend/src", "--host", "0.0.0.0", "--port", "4182"]
