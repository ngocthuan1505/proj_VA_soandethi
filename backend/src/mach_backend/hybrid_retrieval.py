"""Truy xuất lai: SQLite FTS5, BM25, chuẩn hóa i/y & đồng nghĩa, và Ollama /api/embed."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import httpx

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
EMBED_MODEL_CANDIDATES: tuple[str, ...] = (
    "bge-m3",
    "nomic-embed-text",
    "mxbai-embed-large",
)

_TOKEN_RE = re.compile(r"[0-9a-z]+", re.ASCII)
_OPEN_SYLLABLE_Y_RE = re.compile(r"\b([hklmnstv])y\b")
_QUY_RE = re.compile(r"\bquy\b")

# Tập từ hư tiếng Việt chuẩn (đã chuẩn hóa không dấu) để chống dương tính giả ở RAG/search.
VI_STOPWORDS: frozenset[str] = frozenset(
    {
        "ai",
        "ay",
        "bao",
        "bi",
        "boi",
        "cac",
        "cho",
        "chua",
        "co",
        "cua",
        "cung",
        "da",
        "dang",
        "dau",
        "day",
        "de",
        "den",
        "do",
        "duoc",
        "gi",
        "hay",
        "hoac",
        "khi",
        "kia",
        "la",
        "ma",
        "mot",
        "nao",
        "nay",
        "nen",
        "neu",
        "nhu",
        "nhung",
        "nua",
        "o",
        "ra",
        "roi",
        "sao",
        "sau",
        "se",
        "tai",
        "the",
        "theo",
        "thi",
        "trong",
        "truoc",
        "tu",
        "va",
        "vao",
        "vay",
        "ve",
        "vi",
        "voi",
    }
)

# Nhóm cụm từ đồng nghĩa chuyên ngành Toán/KHTN phổ thông (đã chuẩn hóa).
_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        "giai he phuong trinh",
        "giai he bang phep the",
        "he hai phuong trinh bac nhat hai an",
        "he phuong trinh bac nhat hai an",
    ),
    ("ti so luong giac", "ty so luong giac"),
    ("dao ham", "vi phan"),
    ("nguyen ham", "tich phan"),
)


def normalize_vi_search(text: str) -> str:
    """Chuẩn hóa NFC->NFD bỏ dấu, đ->d, chữ thường và quy đồng biến thể chính tả i/y."""
    raw = unicodedata.normalize("NFC", str(text or ""))
    decomposed = unicodedata.normalize("NFD", raw)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    folded = stripped.replace("đ", "d").replace("Đ", "d").casefold()
    collapsed = " ".join(folded.split())
    if not collapsed:
        return ""
    # Quy đồng âm tiết mở i/y (tỉ/tỷ, lí/lý, kĩ/kỹ, mĩ/mỹ, sĩ/sỹ, hi/hy, qui/quy).
    normalized = _OPEN_SYLLABLE_Y_RE.sub(r"\1i", collapsed)
    normalized = _QUY_RE.sub("qui", normalized)
    return normalized


def expand_vi_synonyms(text: str) -> list[str]:
    """Sinh danh sách biến thể truy vấn (bản chuẩn hóa + cụm đồng nghĩa môn học)."""
    base = normalize_vi_search(text)
    if not base:
        return []
    variants: list[str] = [base]
    seen = {base}
    for group in _SYNONYM_GROUPS:
        norm_group = [normalize_vi_search(term) for term in group]
        matched = [term for term in norm_group if term and term in base]
        if not matched:
            continue
        for src_term in matched:
            for alt_term in norm_group:
                if alt_term and alt_term != src_term:
                    candidate = base.replace(src_term, alt_term)
                    if candidate not in seen:
                        seen.add(candidate)
                        variants.append(candidate)
                    if alt_term not in seen:
                        seen.add(alt_term)
                        variants.append(alt_term)
    return variants


def tokenize_vi_search(text: str) -> list[str]:
    """Tách token chữ-số đã chuẩn hóa để lập chỉ mục BM25/FTS5."""
    return _TOKEN_RE.findall(normalize_vi_search(text))


def extract_vi_content_tokens(tokens: Sequence[str]) -> list[str]:
    """Lọc token mang nội dung (loại từ hư tiếng Việt và token ngắn < 2 ký tự)."""
    return [tok for tok in tokens if len(tok) >= 2 and tok not in VI_STOPWORDS]


_DIACRITIC_LIGHT_COLLOCATION_RE = re.compile(r"\bdiễn\s+ra\b")


def strip_vi_light_collocations(text: str) -> str:
    """Loại cụm động từ rỗng nghĩa có dấu chuẩn (như 'diễn ra') trước khi đối chiếu nội dung."""
    nfc = unicodedata.normalize("NFC", str(text or "")).casefold()
    return _DIACRITIC_LIGHT_COLLOCATION_RE.sub(" ", nfc)


def _trigram_cosine(left: str, right: str) -> float:
    a = normalize_vi_search(left)
    b = normalize_vi_search(right)
    if len(a) < 3 or len(b) < 3:
        return 1.0 if a and a == b else 0.0
    ca = Counter(a[i : i + 3] for i in range(len(a) - 2))
    cb = Counter(b[i : i + 3] for i in range(len(b) - 2))
    shared = set(ca) & set(cb)
    if not shared:
        return 0.0
    dot = sum(ca[k] * cb[k] for k in shared)
    norm_a = math.sqrt(sum(v * v for v in ca.values()))
    norm_b = math.sqrt(sum(v * v for v in cb.values()))
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(float(x) * float(y) for x, y in zip(vec_a, vec_b, strict=False))
    na = math.sqrt(sum(float(x) * float(x) for x in vec_a))
    nb = math.sqrt(sum(float(y) * float(y) for y in vec_b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def ensure_hybrid_schema(conn: sqlite3.Connection) -> bool:
    """Khởi tạo bảng source_chunks và bảng ảo FTS5 (trả False nếu SQLite không hỗ trợ FTS5)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_chunks (
            chunk_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            page_number INTEGER NOT NULL DEFAULT 1,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL DEFAULT '',
            text TEXT NOT NULL,
            norm_text TEXT NOT NULL,
            embedding_json TEXT,
            created_at INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_source_chunks_owner_doc
            ON source_chunks (owner_id, doc_id, version)
        """
    )
    fts_enabled = False
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS source_chunks_fts USING fts5(
                chunk_id UNINDEXED,
                owner_id UNINDEXED,
                doc_id UNINDEXED,
                title,
                norm_text
            )
            """
        )
        fts_enabled = True
    except sqlite3.OperationalError:
        fts_enabled = False
    conn.commit()
    return fts_enabled


def _fts5_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'source_chunks_fts'"
    ).fetchone()
    return row is not None


def _split_text_overlapping(text: str, chunk_size: int, overlap: int) -> list[str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]
    step = max(1, chunk_size - overlap)
    slices: list[str] = []
    start = 0
    total = len(cleaned)
    while start < total:
        raw_end = min(total, start + chunk_size)
        end = raw_end
        if raw_end < total:
            # Cắt tại khoảng trắng hoặc xuống dòng gần cuối đoạn để giữ trọn từ tiếng Việt.
            min_cut = start + max(step, int(chunk_size * 0.65))
            space_idx = cleaned.rfind(" ", min_cut, raw_end)
            nl_idx = cleaned.rfind("\n", min_cut, raw_end)
            best_break = max(space_idx, nl_idx)
            if best_break > start:
                end = best_break
        piece = cleaned[start:end].strip()
        if piece:
            slices.append(piece)
        if end >= total:
            break
        next_start = max(start + 1, end - overlap)
        start = next_start
    return slices


def _extract_page_number(mapping: Mapping[str, Any], default_page: int) -> int:
    for key in ("page_number", "pageNumber", "page", "number"):
        val = mapping.get(key)
        if val is not None and val != "":
            try:
                num = int(val)
                if num > 0:
                    return num
            except (TypeError, ValueError):
                continue
    return default_page


def chunk_document_pages(
    pages: Sequence[Any],
    chunk_size: int = 420,
    overlap: int = 80,
    *,
    doc_id: str = "",
    version: int = 1,
) -> list[dict[str, Any]]:
    """Tách văn bản trang thành chunk chồng lấp, giữ (doc_id, version, page_number, chunk_index)."""
    eff_size = max(40, int(chunk_size))
    eff_overlap = max(0, min(int(overlap), eff_size - 1))
    chunks: list[dict[str, Any]] = []
    for default_page, page in enumerate(pages, 1):
        page_doc = doc_id
        page_version = int(version)
        page_title = ""
        if isinstance(page, Mapping):
            page_num = _extract_page_number(page, default_page)
            page_text = str(page.get("text", page.get("content", "")) or "")
            page_doc = str(page.get("doc_id", page.get("docId", page_doc)) or page_doc)
            if page.get("version") is not None:
                page_version = int(page["version"])
            page_title = str(page.get("title", "") or "")
        elif isinstance(page, (tuple, list)) and len(page) >= 2:
            page_num = int(page[0] or default_page)
            page_text = str(page[1] or "")
        else:
            page_num = default_page
            page_text = str(page or "")

        for chunk_idx, slice_text in enumerate(
            _split_text_overlapping(page_text, eff_size, eff_overlap)
        ):
            chunks.append(
                {
                    "doc_id": page_doc,
                    "version": page_version,
                    "page_number": page_num,
                    "chunk_index": chunk_idx,
                    "title": page_title,
                    "text": slice_text,
                    "norm_text": normalize_vi_search(slice_text),
                }
            )
    return chunks


def _compute_chunk_id(
    owner_id: str, doc_id: str, version: int, page_number: int, chunk_index: int
) -> str:
    return f"{owner_id}:{doc_id}:v{version}:p{page_number}:c{chunk_index}"


def _chunks_content_hash(rows: Sequence[tuple[str, str, int, int, int, str, str]]) -> str:
    ordered = sorted(rows, key=lambda r: (r[3], r[4], r[0]))
    serialized = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def index_document_chunks(
    conn: sqlite3.Connection,
    owner_id: str,
    doc_id: str,
    pages: Sequence[Any],
    *,
    version: int = 1,
    title: str = "",
    chunk_size: int = 420,
    overlap: int = 80,
    ollama_embed_fn: Callable[[list[str]], list[list[float]] | None] | None = None,
) -> list[dict[str, Any]]:
    """Lưu các chunk của tài liệu vào SQLite (+ FTS5 và vector Ollama nếu khả dụng)."""
    has_fts = ensure_hybrid_schema(conn)
    if pages and all(
        isinstance(item, Mapping) and "chunk_index" in item and "text" in item for item in pages
    ):
        prepared: list[dict[str, Any]] = [
            {
                "doc_id": str(item.get("doc_id", doc_id) or doc_id),
                "version": int(item.get("version", version)),
                "page_number": _extract_page_number(item, 1),
                "chunk_index": int(item["chunk_index"]),
                "title": str(item.get("title", title) or title),
                "text": str(item["text"]),
                "norm_text": normalize_vi_search(str(item["text"])),
            }
            for item in pages
            if str(item.get("text", "")).strip()
        ]
    else:
        prepared = chunk_document_pages(
            pages,
            chunk_size=chunk_size,
            overlap=overlap,
            doc_id=doc_id,
            version=version,
        )

    resolved: list[dict[str, Any]] = []
    for item in prepared:
        eff_doc = str(item.get("doc_id") or doc_id)
        eff_ver = int(item["version"])
        page_num = int(item["page_number"])
        chunk_idx = int(item["chunk_index"])
        chunk_id = _compute_chunk_id(owner_id, eff_doc, eff_ver, page_num, chunk_idx)
        item_title = str(item.get("title") or title)
        resolved.append(
            {
                "chunkId": chunk_id,
                "docId": eff_doc,
                "version": eff_ver,
                "pageNumber": page_num,
                "chunkIndex": chunk_idx,
                "title": item_title,
                "text": item["text"],
                "normText": item["norm_text"],
            }
        )

    existing_rows = conn.execute(
        """
        SELECT chunk_id, doc_id, version, page_number, chunk_index, title, text, embedding_json
        FROM source_chunks
        WHERE owner_id = ? AND doc_id = ? AND version = ?
        ORDER BY page_number, chunk_index, chunk_id
        """,
        (owner_id, doc_id, int(version)),
    ).fetchall()

    if len(existing_rows) == len(resolved) and all(
        r["docId"] == doc_id and r["version"] == int(version) for r in resolved
    ):
        prepared_hash = _chunks_content_hash(
            [
                (
                    r["chunkId"],
                    r["docId"],
                    r["version"],
                    r["pageNumber"],
                    r["chunkIndex"],
                    r["title"],
                    r["text"],
                )
                for r in resolved
            ]
        )
        existing_hash = _chunks_content_hash(
            [
                (r[0], r[1], int(r[2]), int(r[3]), int(r[4]), str(r[5]), str(r[6]))
                for r in existing_rows
            ]
        )
        if prepared_hash == existing_hash:
            fts_intact = True
            if has_fts and existing_rows:
                existing_chunk_ids = [r[0] for r in existing_rows]
                placeholders = ",".join("?" for _ in existing_chunk_ids)
                fts_count = conn.execute(
                    f"SELECT COUNT(*) FROM source_chunks_fts WHERE chunk_id IN ({placeholders})",
                    existing_chunk_ids,
                ).fetchone()[0]
                fts_intact = fts_count == len(existing_rows)
            embeddings_ok = (ollama_embed_fn is None) or all(
                r[7] is not None for r in existing_rows
            )
            if fts_intact and embeddings_ok:
                return [
                    {
                        "chunkId": r["chunkId"],
                        "docId": r["docId"],
                        "version": r["version"],
                        "pageNumber": r["pageNumber"],
                        "chunkIndex": r["chunkIndex"],
                        "title": r["title"],
                        "text": r["text"],
                    }
                    for r in resolved
                ]

    embeddings: list[list[float]] | None = None
    if ollama_embed_fn is not None and resolved:
        try:
            raw_vecs = ollama_embed_fn([str(item["text"]) for item in resolved])
            if isinstance(raw_vecs, list) and len(raw_vecs) == len(resolved):
                embeddings = raw_vecs
        except Exception:
            embeddings = None

    existing_ids = [r[0] for r in existing_rows]
    if existing_ids:
        conn.execute(
            "DELETE FROM source_chunks WHERE owner_id = ? AND doc_id = ? AND version = ?",
            (owner_id, doc_id, int(version)),
        )
        if has_fts:
            placeholders = ",".join("?" for _ in existing_ids)
            conn.execute(
                f"DELETE FROM source_chunks_fts WHERE chunk_id IN ({placeholders})",
                existing_ids,
            )

    now_ms = int(time.time() * 1000)
    rows_out: list[dict[str, Any]] = []
    norm_title = normalize_vi_search(title)
    for idx, item in enumerate(resolved):
        vec_json = json.dumps(embeddings[idx]) if embeddings is not None else None
        conn.execute(
            """
            INSERT INTO source_chunks (
                chunk_id, owner_id, doc_id, version, page_number, chunk_index,
                title, text, norm_text, embedding_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["chunkId"],
                owner_id,
                item["docId"],
                item["version"],
                item["pageNumber"],
                item["chunkIndex"],
                item["title"],
                item["text"],
                item["normText"],
                vec_json,
                now_ms,
            ),
        )
        if has_fts:
            conn.execute(
                """
                INSERT INTO source_chunks_fts (chunk_id, owner_id, doc_id, title, norm_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item["chunkId"],
                    owner_id,
                    item["docId"],
                    normalize_vi_search(item["title"]) or norm_title,
                    item["normText"],
                ),
            )
        rows_out.append(
            {
                "chunkId": item["chunkId"],
                "docId": item["docId"],
                "version": item["version"],
                "pageNumber": item["pageNumber"],
                "chunkIndex": item["chunkIndex"],
                "title": item["title"],
                "text": item["text"],
            }
        )
    conn.commit()
    return rows_out


def pick_installed_embed_model(installed_models: Iterable[str]) -> str | None:
    """Chọn model embedding cục bộ khả dụng theo thứ tự ưu tiên."""
    normalized: dict[str, str] = {}
    for raw in installed_models:
        name = str(raw or "").strip()
        if not name:
            continue
        base = name.split(":", 1)[0].casefold()
        normalized.setdefault(name.casefold(), name)
        normalized.setdefault(base, name)
    for cand in EMBED_MODEL_CANDIDATES:
        if cand in normalized:
            return normalized[cand]
    return None


def make_ollama_embed_fn(
    model: str,
    *,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout: float = 12.0,
) -> Callable[[list[str]], list[list[float]] | None]:
    """Tạo hàm đồng bộ gọi Ollama /api/embed (không thêm dependency ngoài httpx)."""
    endpoint = base_url.rstrip("/") + "/api/embed"

    def _embed(texts: list[str]) -> list[list[float]] | None:
        if not texts:
            return []
        try:
            response = httpx.post(
                endpoint,
                json={"model": model, "input": texts},
                timeout=timeout,
            )
            if response.status_code >= 300:
                return None
            payload = response.json()
            vecs = payload.get("embeddings")
            if isinstance(vecs, list) and len(vecs) == len(texts):
                return vecs
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        return None

    return _embed


def _extract_pages_filter(spec: Mapping[str, Any]) -> set[int] | None:
    if "pages" in spec:
        raw_pages = spec["pages"]
        if raw_pages is None:
            return None
        if isinstance(raw_pages, Iterable) and not isinstance(raw_pages, (str, bytes)):
            return {int(p) for p in raw_pages}
    for key in ("page", "pageNumber", "page_number"):
        val = spec.get(key)
        if val is not None and val != "":
            return {int(val)}
    return None


def _parse_allowed_docs(
    allowed_docs: Iterable[Any] | Mapping[str, Any] | None,
) -> tuple[bool, dict[tuple[str, int | None], set[int] | None]]:
    """Trả về (has_filter, {(doc_id, version_or_None): allowed_pages_or_None})."""
    if allowed_docs is None:
        return False, {}
    rules: dict[tuple[str, int | None], set[int] | None] = {}

    def _add_rule(doc_id: str, ver: int | None, pages: set[int] | None) -> None:
        key = (doc_id, ver)
        if key not in rules:
            rules[key] = None if pages is None else set(pages)
            return
        current = rules[key]
        if current is None or pages is None:
            rules[key] = None
        else:
            current.update(pages)

    if isinstance(allowed_docs, Mapping):
        if any(k in allowed_docs for k in ("docId", "doc_id", "id")):
            items: Iterable[Any] = [allowed_docs]
        else:
            for raw_id, spec in allowed_docs.items():
                doc_id = str(raw_id or "").strip()
                if not doc_id:
                    continue
                if spec is None:
                    _add_rule(doc_id, None, None)
                elif isinstance(spec, Mapping):
                    ver = spec.get("version")
                    _add_rule(
                        doc_id,
                        int(ver) if ver is not None else None,
                        _extract_pages_filter(spec),
                    )
                elif isinstance(spec, (set, frozenset, list, tuple)):
                    _add_rule(doc_id, None, {int(p) for p in spec})
                elif isinstance(spec, int):
                    _add_rule(doc_id, None, {int(spec)})
            return True, rules
    else:
        items = allowed_docs

    for item in items:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                _add_rule(cleaned, None, None)
        elif isinstance(item, tuple) and len(item) >= 2:
            doc_id = str(item[0] or "").strip()
            if not doc_id:
                continue
            ver = int(item[1]) if item[1] is not None else None
            pages: set[int] | None = None
            if len(item) >= 3 and item[2] is not None:
                raw_p = item[2]
                pages = (
                    {int(p) for p in raw_p}
                    if isinstance(raw_p, (set, frozenset, list, tuple))
                    else {int(raw_p)}
                )
            _add_rule(doc_id, ver, pages)
        elif isinstance(item, Mapping):
            doc_id = str(item.get("docId") or item.get("doc_id") or item.get("id") or "").strip()
            if not doc_id:
                continue
            ver = item.get("version")
            _add_rule(
                doc_id,
                int(ver) if ver is not None else None,
                _extract_pages_filter(item),
            )
    return True, rules


def _is_chunk_allowed(
    rules: Mapping[tuple[str, int | None], set[int] | None],
    doc_id: str,
    version: int,
    page_num: int,
) -> bool:
    for key in ((doc_id, version), (doc_id, None)):
        if key in rules:
            allowed_pages = rules[key]
            if allowed_pages is None or page_num in allowed_pages:
                return True
    return False


def _python_bm25_scores(
    docs_tokens: list[list[str]],
    query_tokens: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    if not docs_tokens or not query_tokens:
        return [0.0] * len(docs_tokens)
    n_docs = len(docs_tokens)
    avgdl = sum(len(t) for t in docs_tokens) / max(1, n_docs)
    df: Counter[str] = Counter()
    for tokens in docs_tokens:
        for tok in set(tokens):
            df[tok] += 1
    unique_q = list(dict.fromkeys(query_tokens))
    scores: list[float] = []
    for tokens in docs_tokens:
        tf = Counter(tokens)
        dl = len(tokens) or 1
        score = 0.0
        for tok in unique_q:
            freq = tf.get(tok, 0)
            if freq <= 0:
                continue
            idf = math.log(1.0 + (n_docs - df[tok] + 0.5) / (df[tok] + 0.5))
            denom = freq + k1 * (1.0 - b + b * dl / max(1.0, avgdl))
            score += idf * (freq * (k1 + 1.0)) / denom
        scores.append(score)
    return scores


def search_hybrid_chunks(
    conn: sqlite3.Connection,
    owner_id: str,
    query: str,
    allowed_docs: Iterable[Any] | Mapping[str, Any] | None,
    *,
    top_k: int = 8,
    min_score: float = 0.08,
    ollama_embed_fn: Callable[[list[str]], list[list[float]] | None] | None = None,
    use_fts5: bool | None = None,
) -> list[dict[str, Any]]:
    """Tìm đoạn học liệu kết hợp FTS5/BM25, chuẩn hóa i/y, đồng nghĩa và rerank vector Ollama."""
    has_filter, allowed_rules = _parse_allowed_docs(allowed_docs)
    if has_filter and not any(pages is None or len(pages) > 0 for pages in allowed_rules.values()):
        return []
    variants = expand_vi_synonyms(query)
    if not variants:
        return []
    cleaned_query_variants = expand_vi_synonyms(strip_vi_light_collocations(query)) or variants
    variant_tokens_list = [tokenize_vi_search(v) for v in cleaned_query_variants]
    variant_content_list = [extract_vi_content_tokens(toks) for toks in variant_tokens_list]
    all_q_content = list(dict.fromkeys(tok for toks in variant_content_list for tok in toks))
    if not all_q_content:
        return []

    ensure_hybrid_schema(conn)

    rows = conn.execute(
        """
        SELECT chunk_id, doc_id, version, page_number, chunk_index,
               title, text, norm_text, embedding_json
        FROM source_chunks
        WHERE owner_id = ?
        """,
        (owner_id,),
    ).fetchall()
    if not rows:
        return []

    candidates: list[dict[str, Any]] = []
    for row in rows:
        chunk_id, doc_id, version, page_num, chunk_idx, title, text, norm_text, emb_json = row
        if has_filter and not _is_chunk_allowed(allowed_rules, doc_id, int(version), int(page_num)):
            continue
        candidates.append(
            {
                "chunkId": chunk_id,
                "docId": doc_id,
                "version": int(version),
                "pageNumber": int(page_num),
                "chunkIndex": int(chunk_idx),
                "title": title,
                "text": text,
                "normText": norm_text or normalize_vi_search(text),
                "embeddingJson": emb_json,
            }
        )
    if not candidates:
        return []

    cand_by_id = {c["chunkId"]: c for c in candidates}

    fts_available = (
        _fts5_table_exists(conn)
        if use_fts5 is None
        else bool(use_fts5 and _fts5_table_exists(conn))
    )
    fts_raw_scores: dict[str, float] = {}
    if fts_available:
        match_expr = " OR ".join(f'"{tok}"' for tok in all_q_content if tok)
        if match_expr:
            try:
                fts_rows = conn.execute(
                    """
                    SELECT chunk_id, bm25(source_chunks_fts) AS rank_score
                    FROM source_chunks_fts
                    WHERE owner_id = ? AND source_chunks_fts MATCH ?
                    """,
                    (owner_id, match_expr),
                ).fetchall()
                for cid, raw_bm25 in fts_rows:
                    if cid in cand_by_id:
                        # SQLite bm25() càng âm càng tốt; chuyển về dương [0, 1).
                        pos = max(0.0, -float(raw_bm25))
                        fts_raw_scores[cid] = pos / (1.0 + pos) if pos > 0 else 0.0
            except sqlite3.OperationalError:
                fts_raw_scores = {}

    doc_tokens = [
        tokenize_vi_search(strip_vi_light_collocations(f"{c['title']} {c['text']}"))
        for c in candidates
    ]
    py_bm25_best = [0.0] * len(candidates)
    for v_content in variant_content_list:
        if not v_content:
            continue
        scores = _python_bm25_scores(doc_tokens, v_content)
        for i, sc in enumerate(scores):
            if sc > py_bm25_best[i]:
                py_bm25_best[i] = sc
    max_py_bm25 = max(py_bm25_best) if py_bm25_best else 0.0
    # SQLite FTS5 kẹp IDF xuống 1e-6 khi N<=2 hoặc df>=N/2; chỉ dùng FTS5 khi có tín hiệu > 1e-3.
    use_fts_scores = fts_available and max(fts_raw_scores.values(), default=0.0) > 1e-3

    # Tính embedding truy vấn + đoạn (khi Ollama /api/embed khả dụng).
    query_vec: list[float] | None = None
    cand_vecs: list[list[float] | None] = [None] * len(candidates)
    if ollama_embed_fn is not None:
        try:
            q_vecs = ollama_embed_fn([query])
            if isinstance(q_vecs, list) and len(q_vecs) == 1 and q_vecs[0]:
                query_vec = [float(x) for x in q_vecs[0]]
        except Exception:
            query_vec = None
        if query_vec is not None:
            missing_idx: list[int] = []
            missing_texts: list[str] = []
            for idx, cand in enumerate(candidates):
                emb_raw = cand["embeddingJson"]
                if emb_raw:
                    try:
                        parsed = json.loads(emb_raw)
                        if isinstance(parsed, list) and parsed:
                            cand_vecs[idx] = [float(x) for x in parsed]
                            continue
                    except (ValueError, TypeError):
                        pass
                missing_idx.append(idx)
                missing_texts.append(cand["text"])
            if missing_texts:
                try:
                    computed = ollama_embed_fn(missing_texts)
                    if isinstance(computed, list) and len(computed) == len(missing_texts):
                        for pos, vec in zip(missing_idx, computed, strict=False):
                            if vec:
                                cand_vecs[pos] = [float(x) for x in vec]
                except Exception:
                    pass

    results: list[dict[str, Any]] = []
    for idx, cand in enumerate(candidates):
        searchable = f"{normalize_vi_search(cand['title'])} {cand['normText']}".strip()
        tok_set = set(doc_tokens[idx])
        best_overlap = 0.0
        for v_content in variant_content_list:
            if not v_content:
                continue
            uniq_content = set(v_content)
            hit = sum(1 for t in uniq_content if t in tok_set) / len(uniq_content)
            if hit > best_overlap:
                best_overlap = hit
        phrase_hit = 1.0 if any(v in searchable for v in variants) else 0.0
        trigram = max(_trigram_cosine(v, searchable) for v in variants)
        bm25_norm = (
            fts_raw_scores.get(cand["chunkId"], 0.0)
            if use_fts_scores
            else (py_bm25_best[idx] / max(1.0, max_py_bm25) if max_py_bm25 > 0 else 0.0)
        )
        if best_overlap == 0.0 and phrase_hit == 0.0 and trigram < 0.45:
            lexical_score = 0.0
        else:
            # Chỉ tính trigram khi đạt ngưỡng tối thiểu để chặn khớp nhiễu 1-2 ký tự.
            gated_trigram = trigram if trigram >= 0.14 else 0.0
            lexical_score = min(
                1.0,
                0.45 * bm25_norm + 0.35 * best_overlap + 0.20 * max(phrase_hit, gated_trigram),
            )
            if (
                best_overlap == 0.0
                and phrase_hit == 0.0
                and bm25_norm == 0.0
                and gated_trigram == 0.0
            ):
                lexical_score = 0.0

        semantic_score = 0.0
        if query_vec is not None and cand_vecs[idx] is not None:
            raw_cos = max(0.0, _cosine_similarity(query_vec, cand_vecs[idx] or []))
            # Khi không có khớp nội dung/cụm nào, đòi hỏi ngưỡng semantic >= 0.45.
            min_cos = 0.35 if lexical_score > 0.0 else 0.45
            semantic_score = raw_cos if raw_cos >= min_cos else 0.0

        if best_overlap == 0.0 and phrase_hit == 0.0 and trigram < 0.45 and semantic_score < 0.45:
            continue

        if query_vec is not None and any(v is not None for v in cand_vecs):
            if lexical_score <= 0.0 and semantic_score <= 0.0:
                combined = 0.0
            else:
                combined = 0.55 * lexical_score + 0.45 * semantic_score
        else:
            combined = lexical_score

        if combined < float(min_score):
            continue
        results.append(
            {
                "chunkId": cand["chunkId"],
                "docId": cand["docId"],
                "version": cand["version"],
                "pageNumber": cand["pageNumber"],
                "chunkIndex": cand["chunkIndex"],
                "title": cand["title"],
                "text": cand["text"],
                "score": round(combined, 6),
                "lexicalScore": round(lexical_score, 6),
                "semanticScore": round(semantic_score, 6),
            }
        )

    results.sort(
        key=lambda item: (
            -float(item["score"]),
            item["docId"],
            item["pageNumber"],
            item["chunkIndex"],
        )
    )
    return results[: max(1, int(top_k))]
