"""Đóng gói source chạy Python và tài nguyên giao diện theo danh sách cho phép."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = "SoanDeThi-BanThu-18-11-2026"
OUT = ROOT / "outputs/mvp-18-11/phat-hanh-thu"


def build(name=NAME, out=OUT, guide="HUONG_DAN_BAN_THU_18_11.md"):
    explicit = (
        "index.html",
        "CHAY_THU_NHOM.cmd",
        "CHAY_NHOM_CO_TAI_KHOAN.cmd",
        "CHAY_DEMO_VA_LOG.cmd",
        "THIRD_PARTY.md",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "backend/poc-data/bio-tham-thau.json",
        "backend/poc-data/thu-vien.json",
        "scripts/chay-nhom-tai-khoan.py",
        "scripts/theo-doi-poc.py",
        "docs/testing/Ma-tran-demo-8-cau.csv",
        "docs/testing/DE_DEMO_TOAN_5.md",
        "docs/testing/DAP_AN_DEMO_TOAN_5.md",
        "assets/demo-ai-exam.json",
        "assets/reference-exam.json",
        "assets/editor-engine.js.LEGAL.txt",
    )
    paths = {name: ROOT / name for name in explicit}
    for pattern in (
        "*.js",
        "*.css",
        "backend/src/mach_backend/**/*.py",
        "assets/*.js",
        "assets/*.css",
        "assets/*.mjs",
        "assets/team-login.html",
        "assets/exam-icon.svg",
        "assets/katex/**/*",
        "assets/mathlive/**/*",
    ):
        for file in ROOT.glob(pattern):
            if file.is_file():
                paths[file.relative_to(ROOT).as_posix()] = file
    paths["HUONG_DAN_TEST_NHOM.md"] = ROOT / "docs/testing" / guide
    out.mkdir(parents=True, exist_ok=True)
    package = out / (name + ".zip")
    temporary = package.with_suffix(".tmp")
    manifest = {}
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
        for relative, file in sorted(paths.items()):
            if not file.resolve().is_relative_to(ROOT) or file.suffix not in {
                ".py",
                ".js",
                ".mjs",
                ".css",
                ".html",
                ".md",
                ".cmd",
                ".csv",
                ".toml",
                ".lock",
                ".json",
                ".svg",
                ".woff",
                ".woff2",
                ".ttf",
                ".txt",
                "",
            }:
                raise ValueError(f"Tệp ngoài phạm vi đóng gói: {relative}")
            content = file.read_bytes()
            archive.writestr(f"{name}/{relative}", content)
            manifest[relative] = hashlib.sha256(content).hexdigest()
        archive.writestr(f"{name}/MANIFEST.json", json.dumps(manifest, indent=2))
    with ZipFile(temporary) as archive:
        if archive.testzip() or any(
            hashlib.sha256(archive.read(f"{name}/{relative}")).hexdigest() != digest
            for relative, digest in manifest.items()
        ):
            raise RuntimeError("ZIP không khớp source.")
    temporary.replace(package)
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    package.with_suffix(".sha256").write_text(f"{digest}  {package.name}\n", encoding="ascii")
    print(json.dumps({"zip": str(package), "files": len(manifest), "sha256": digest}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ung-vien", nargs="?", const=1, type=int, help="Đóng gói theo số bản ứng viên"
    )
    candidate = parser.parse_args().ung_vien
    if candidate is not None:
        if candidate < 1:
            parser.error("Số bản ứng viên phải lớn hơn 0.")
        suffix = f"{candidate:02d}"
        build(
            f"SoanDeThi-UngVien-{suffix}",
            ROOT / f"outputs/ung-vien-{suffix}",
            "HUONG_DAN_UNG_VIEN_01.md",
        )
    else:
        build()
