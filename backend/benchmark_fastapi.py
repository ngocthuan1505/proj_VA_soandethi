"""Đo HTTP đọc danh mục khi rảnh và khi OCR cùng xuất PDF trên một worker."""

import asyncio
import base64
import io
import json
import math
import multiprocessing
import platform
import socket
import subprocess
import tempfile
from pathlib import Path
from threading import Thread
from time import perf_counter

import httpx
import uvicorn
from PIL import Image, ImageDraw
from pypdf import PdfReader

from mach_backend.local_documents import chrome_path
from mach_backend.local_workspace import create_app

ROUNDS = 12
PROBES = 20
READ_PATH = "/api/lesson-catalog"
HEADERS = ("content-type", "content-length", "content-encoding", "cache-control", "etag", "vary")
OCR_PAYLOAD = {
    "fileId": "benchmark",
    "name": "benchmark.pdf",
    "page": 10,
    "onlyNeedsOcr": True,
    "consent": True,
}
EXPORT_PAYLOAD = {
    "type": "exam",
    "format": "pdf",
    "exam": {
        "title": "Đề Toán dùng đo tải",
        "subject": "Toán",
        "grade": "9",
        "minutes": 45,
        "questions": [
            {
                "id": f"q{number}",
                "type": "mcq",
                "stem": f"Tính {number} + 1.",
                "options": [str(number + offset) for offset in (1, 0, 2, 3)],
                "answer": 0,
                "points": 0.25,
            }
            for number in range(1, 41)
        ],
    },
}


def scanned_pdf():
    pages = []
    for number in range(1, 21):
        page = Image.new("L", (1440, 1920), "white")
        draw = ImageDraw.Draw(page)
        for row in range(30):
            draw.text(
                (80, 80 + row * 58),
                f"Page {number:02d} / Question {row + 1:02d}: calculate {number} + {row}.",
                fill="black",
                font_size=32,
            )
        pages.append(page)
    buffer = io.BytesIO()
    pages[0].save(buffer, "PDF", save_all=True, append_images=pages[1:], dpi=(150, 150), quality=85)
    return buffer.getvalue()


async def fixture_ocr(purpose, body):
    pdf = base64.b64decode(body["document"]["data"])
    if purpose != "source_ocr" or len(PdfReader(io.BytesIO(pdf)).pages) != 1:
        raise RuntimeError("Adapter OCR phải nhận đúng một trang PDF.")
    await asyncio.sleep(0.12)
    return {
        "content": json.dumps(
            {
                "pages": [{"number": 1, "text": "Trang 10, đề Toán giả lập.", "uncertain": False}],
                "notes": "",
            }
        )
    }


def serve(directory, listener, stop):
    server = uvicorn.Server(
        uvicorn.Config(create_app(directory, agent_call=fixture_ocr), log_level="warning")
    )

    def shutdown():
        stop.wait()
        server.should_exit = True

    Thread(target=shutdown, daemon=True).start()
    server.run(sockets=[listener])


async def timed_request(client, method, path, **kwargs):
    started = perf_counter()
    response = await client.request(method, path, **kwargs)
    ended = perf_counter()
    response.raise_for_status()
    return response, started, ended


async def probe(client, delay):
    await asyncio.sleep(delay)
    return await timed_request(client, "GET", READ_PATH)


def summarize(samples):
    durations = sorted((end - start) * 1000 for _, start, end in samples)
    responses = [response for response, _, _ in samples]
    return {
        "samples": len(samples),
        "p50_ms": round(durations[math.ceil(len(durations) * 0.50) - 1], 2),
        "p95_ms": round(durations[math.ceil(len(durations) * 0.95) - 1], 2),
        "max_ms": round(durations[-1], 2),
        "status": sorted({response.status_code for response in responses}),
        "body_bytes": sorted({len(response.content) for response in responses}),
        "headers": {
            name: sorted({response.headers.get(name, "(absent)") for response in responses})
            for name in HEADERS
        },
    }


async def measure(origin, pdf):
    async with httpx.AsyncClient(
        base_url=origin,
        headers={"Origin": origin, "Accept-Encoding": "gzip, deflate"},
        timeout=60,
        trust_env=False,
    ) as client:
        for _ in range(100):
            try:
                if (await client.get(READ_PATH)).raise_for_status().json()["collections"]:
                    break
            except httpx.ConnectError:
                await asyncio.sleep(0.05)
        else:
            raise RuntimeError("FastAPI chưa sẵn sàng sau 100 lần thử.")
        pdf_uri = "data:application/pdf;base64," + base64.b64encode(pdf).decode("ascii")
        (
            await client.put(
                "/api/kv",
                headers={"If-Match": "0"},
                json={"key": "file:benchmark", "value": pdf_uri},
            )
        ).raise_for_status()

        async def loaded_round():
            export = asyncio.create_task(
                timed_request(client, "POST", "/api/save-export", json=EXPORT_PAYLOAD)
            )
            await asyncio.sleep(0.05)
            ocr, *reads = await asyncio.gather(
                timed_request(client, "POST", "/api/ocr", json=OCR_PAYLOAD),
                *(probe(client, index / 100) for index in range(PROBES)),
            )
            exported = await export
            if ocr[0].json()["number"] != 10:
                raise RuntimeError("OCR trả sai số trang.")
            metadata = exported[0].json()
            download = (await client.get(metadata["url"])).raise_for_status()
            if (
                not download.content.startswith(b"%PDF-")
                or len(download.content) != metadata["bytes"]
            ):
                raise RuntimeError("Tệp xuất sai định dạng PDF hoặc kích thước.")
            overlap = [
                sample
                for sample in reads
                if max(ocr[1], exported[1]) <= sample[1] < min(ocr[2], exported[2])
            ]
            if not overlap:
                raise RuntimeError("Không có yêu cầu đọc chồng thời gian với cả OCR và xuất.")
            return reads, ocr, exported, overlap, len(download.content)

        await loaded_round()
        idle = []
        loaded = []
        ocr_samples = []
        export_samples = []
        overlaps = []
        overlapping_reads = []
        pdf_sizes = set()
        for _ in range(ROUNDS):
            idle.extend(await asyncio.gather(*(probe(client, n / 100) for n in range(PROBES))))
            reads, ocr, exported, overlap, pdf_size = await loaded_round()
            loaded.extend(reads)
            ocr_samples.append(ocr)
            export_samples.append(exported)
            overlaps.append(len(overlap))
            overlapping_reads.extend(overlap)
            pdf_sizes.add(pdf_size)
        return {
            "idle": summarize(idle),
            "loaded": summarize(loaded),
            "loaded_overlapping": summarize(overlapping_reads),
            "ocr": summarize(ocr_samples),
            "export": summarize(export_samples),
            "overlap_per_round": overlaps,
            "exported_pdf_bytes": sorted(pdf_sizes),
        }


def main():
    browser = chrome_path()
    if browser is None:
        raise SystemExit("Cần cài sẵn Chrome/Edge hoặc đặt BROWSER_PATH.")
    pdf = scanned_pdf()
    context = multiprocessing.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mach-benchmark-") as temp, socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        if port == 4317:
            raise RuntimeError("Chọn lại cổng benchmark.")
        stop = context.Event()
        server = context.Process(target=serve, args=(Path(temp), listener, stop))
        server.start()
        try:
            results = asyncio.run(measure(f"http://127.0.0.1:{port}", pdf))
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], text=True
            ).strip()
            print(
                json.dumps(
                    {
                        "commit": commit,
                        "python": platform.python_version(),
                        "platform": platform.platform(),
                        "browser": Path(browser).name,
                        "fixture_pdf_bytes": len(pdf),
                        **results,
                    },
                    indent=2,
                )
            )
        finally:
            stop.set()
            server.join(timeout=60)
            if server.is_alive():
                server.terminate()
                server.join()


if __name__ == "__main__":
    main()
