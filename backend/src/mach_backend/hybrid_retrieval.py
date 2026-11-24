"""Truy xuất lai: SQLite FTS5, BM25, chuẩn hóa i/y & đồng nghĩa, và Ollama /api/embed."""

from __future__ import annotations

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
_OPEN_SYLLABLE_Y_RE = re.compile(r"\b([klmnstv])y\b")
_QUY_RE = re.compile(r"\bquy\b")

# Nhóm cụm từ đồng nghĩa chuyên ngành Toán/KHTN phổ thông (đã chuẩn hóa).
_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        "giai he phuong trinh",
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
            raw_num = page.get(
                "page_number", page.get("pageNumber", page.get("page", default_page))
            )
            page_num = int(raw_num or default_page)
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
                "page_number": int(item.get("page_number", item.get("pageNumber", 1))),
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

    embeddings: list[list[float]] | None = None
    if ollama_embed_fn is not None and prepared:
        try:
            raw_vecs = ollama_embed_fn([str(item["text"]) for item in prepared])
            if isinstance(raw_vecs, list) and len(raw_vecs) == len(prepared):
                embeddings = raw_vecs
        except Exception:
            embeddings = None

    existing_ids = [
        row[0]
        for row in conn.execute(
            "SELECT chunk_id FROM source_chunks WHERE owner_id = ? AND doc_id = ? AND version = ?",
            (owner_id, doc_id, int(version)),
        ).fetchall()
    ]
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
    for idx, item in enumerate(prepared):
        eff_doc = str(item.get("doc_id") or doc_id)
        eff_ver = int(item["version"])
        page_num = int(item["page_number"])
        chunk_idx = int(item["chunk_index"])
        chunk_id = _compute_chunk_id(owner_id, eff_doc, eff_ver, page_num, chunk_idx)
        item_title = str(item.get("title") or title)
        vec_json = json.dumps(embeddings[idx]) if embeddings is not None else None
        conn.execute(
            """
            INSERT INTO source_chunks (
                chunk_id, owner_id, doc_id, version, page_number, chunk_index,
                title, text, norm_text, embedding_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                owner_id,
                eff_doc,
                eff_ver,
                page_num,
                chunk_idx,
                item_title,
                item["text"],
                item["norm_text"],
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
                    chunk_id,
                    owner_id,
                    eff_doc,
                    normalize_vi_search(item_title) or norm_title,
                    item["norm_text"],
                ),
            )
        rows_out.append(
            {
                "chunkId": chunk_id,
                "docId": eff_doc,
                "version": eff_ver,
                "pageNumber": page_num,
                "chunkIndex": chunk_idx,
                "title": item_title,
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


def _parse_allowed_docs(
    allowed_docs: Iterable[Any] | None,
) -> tuple[bool, set[str], set[tuple[str, int]]]:
    """Trả về (has_filter, doc_ids_only, doc_version_pairs)."""
    if allowed_docs is None:
        return False, set(), set()
    doc_ids: set[str] = set()
    doc_versions: set[tuple[str, int]] = set()
    for item in allowed_docs:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                doc_ids.add(cleaned)
        elif isinstance(item, tuple) and len(item) >= 2:
            doc_id = str(item[0] or "").strip()
            if doc_id:
                doc_versions.add((doc_id, int(item[1])))
        elif isinstance(item, Mapping):
            doc_id = str(item.get("docId") or item.get("doc_id") or item.get("id") or "").strip()
            if not doc_id:
                continue
            ver = item.get("version")
            if ver is not None:
                doc_versions.add((doc_id, int(ver)))
            else:
                doc_ids.add(doc_id)
    return True, doc_ids, doc_versions


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
    allowed_docs: Iterable[Any] | None,
    *,
    top_k: int = 8,
    min_score: float = 0.08,
    ollama_embed_fn: Callable[[list[str]], list[list[float]] | None] | None = None,
    use_fts5: bool | None = None,
) -> list[dict[str, Any]]:
    """Tìm đoạn học liệu kết hợp FTS5/BM25, chuẩn hóa i/y, đồng nghĩa và rerank vector Ollama."""
    has_filter, allowed_ids, allowed_pairs = _parse_allowed_docs(allowed_docs)
    if has_filter and not allowed_ids and not allowed_pairs:
        return []
    variants = expand_vi_synonyms(query)
    if not variants:
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
        if has_filter and doc_id not in allowed_ids and (doc_id, int(version)) not in allowed_pairs:
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
    variant_tokens_list = [tokenize_vi_search(v) for v in variants]
    all_q_tokens = list(dict.fromkeys(tok for toks in variant_tokens_list for tok in toks))
    if not all_q_tokens:
        return []

    fts_available = (
        _fts5_table_exists(conn)
        if use_fts5 is None
        else bool(use_fts5 and _fts5_table_exists(conn))
    )
    fts_raw_scores: dict[str, float] = {}
    if fts_available:
        match_expr = " OR ".join(f'"{tok}"' for tok in all_q_tokens if tok)
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

    doc_tokens = [tokenize_vi_search(f"{c['title']} {c['normText']}") for c in candidates]
    py_bm25_best = [0.0] * len(candidates)
    for v_tokens in variant_tokens_list:
        if not v_tokens:
            continue
        scores = _python_bm25_scores(doc_tokens, v_tokens)
        for i, sc in enumerate(scores):
            if sc > py_bm25_best[i]:
                py_bm25_best[i] = sc
    max_py_bm25 = max(py_bm25_best) if py_bm25_best else 0.0

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
        for v_tokens in variant_tokens_list:
            if not v_tokens:
                continue
            hit = sum(1 for t in set(v_tokens) if t in tok_set) / len(set(v_tokens))
            if hit > best_overlap:
                best_overlap = hit
        phrase_hit = 1.0 if any(v in searchable for v in variants) else 0.0
        trigram = max(_trigram_cosine(v, searchable) for v in variants)
        bm25_norm = (
            fts_raw_scores.get(cand["chunkId"], 0.0)
            if (fts_available and fts_raw_scores)
            else (py_bm25_best[idx] / max(1.0, max_py_bm25) if max_py_bm25 > 0 else 0.0)
        )
        # Chỉ tính trigram khi đạt ngưỡng tối thiểu để chặn khớp nhiễu 1-2 ký tự.
        gated_trigram = trigram if trigram >= 0.14 else 0.0
        lexical_score = min(
            1.0,
            0.45 * bm25_norm + 0.35 * best_overlap + 0.20 * max(phrase_hit, gated_trigram),
        )
        if best_overlap == 0.0 and phrase_hit == 0.0 and bm25_norm == 0.0 and gated_trigram == 0.0:
            lexical_score = 0.0

        semantic_score = 0.0
        if query_vec is not None and cand_vecs[idx] is not None:
            raw_cos = max(0.0, _cosine_similarity(query_vec, cand_vecs[idx] or []))
            # Khi không có bất kỳ khớp từ khóa/BM25 nào, đòi hỏi ngưỡng cosine cao hơn
            # để tránh lọt truy vấn nhiễu/vô nghĩa.
            min_cos = 0.35 if lexical_score > 0.0 else 0.65
            semantic_score = raw_cos if raw_cos >= min_cos else 0.0

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
