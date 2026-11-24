"""Tham chiếu nguồn dùng chung cho các thao tác AI."""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, ValidationError

from mach_backend.ai_contract import (
    AIError,
    ContractModel,
    Locator,
    Revision,
    SourceFragment,
    validate_locator,
)
from mach_backend.curriculum_sources import read_usable_curriculum_source
from mach_backend.lesson_catalog import lesson_catalog

type WireUUID = Annotated[UUID, Field(strict=False)]
type SourceKey = tuple[UUID, Locator]


class SelectedSource(ContractModel):
    sourceId: WireUUID
    sourceVersion: Revision
    locator: Locator

    @property
    def key(self) -> SourceKey:
        return self.sourceId, self.locator


class SourceSelection(ContractModel):
    consent: bool = False
    sources: Annotated[list[SelectedSource], Field(max_length=12)] = Field(default_factory=list)
    requireEvidence: bool = False


def selected_source_keys(request: SourceSelection) -> tuple[SourceKey, ...]:
    if not request.consent:
        raise AIError("consent_required", "Xác nhận dùng AI trước khi gửi.")
    keys = tuple(source.key for source in request.sources)
    if len(set(keys)) != len(keys):
        raise AIError("invalid_locator", "Vị trí nguồn bị chọn trùng.")
    for _, locator in keys:
        validate_locator(locator)
    if request.requireEvidence and not keys:
        raise AIError("missing_source", "Chọn nguồn trước khi yêu cầu kết quả có căn cứ.")
    return keys


def read_selected_sources(
    owner_id: str, request: SourceSelection, sources: tuple[SourceFragment, ...]
) -> tuple[SourceFragment, ...]:
    selected = []
    for choice in request.sources:
        matches = [
            source
            for source in sources
            if source.ownerId == owner_id and (source.sourceId, source.locator) == choice.key
        ]
        if len(matches) != 1:
            raise AIError("source_not_found", "Không tìm thấy đoạn nguồn đã chọn.")
        if matches[0].sourceVersion != choice.sourceVersion:
            raise AIError("stale_snapshot", "Nguồn đã đổi. Hãy tải lại.")
        selected.append(matches[0])
    return tuple(selected)


_TOKEN_RE = re.compile(r"[0-9a-z]+")
_IY_TOKEN_RE = re.compile(r"\b([klmst])y\b")
_MIN_BM25_SCORE = 1e-6
_MIN_TRIGRAM_COSINE = 0.14


def is_teacher_owned_source(doc: dict[str, Any]) -> bool:
    """Trả về True nếu tài liệu do giáo viên tự tải/soạn, loại bỏ mẫu/SGK/cộng đồng."""
    if not isinstance(doc, dict):
        return False
    return not (
        doc.get("catalog") is True
        or doc.get("sample") is True
        or doc.get("sourceOrigin") in {"lesson_catalog", "community"}
        or bool(doc.get("communityToken"))
    )


def _strip_accents(value: str) -> str:
    nfd = unicodedata.normalize("NFD", str(value or ""))
    no_marks = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return no_marks.replace("đ", "d").replace("Đ", "D").casefold()


def _normalize_search_text(value: str) -> str:
    return _IY_TOKEN_RE.sub(r"\1i", _strip_accents(value))


def _fragment_text(fragment: Any) -> str:
    if isinstance(fragment, SourceFragment):
        return fragment.text
    if isinstance(fragment, dict):
        parts: list[str] = []
        for key in (
            "name",
            "title",
            "topic",
            "text",
            "excerpt",
            "content",
            "passage",
            "sourceText",
        ):
            val = fragment.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val)
        return "\n".join(parts)
    if isinstance(fragment, str):
        return fragment
    text = getattr(fragment, "text", None)
    return str(text) if isinstance(text, str) else ""


def _char_trigrams(normalized_text: str) -> Counter[str]:
    compact = re.sub(r"\s+", " ", normalized_text).strip()
    if not compact:
        return Counter()
    if len(compact) < 3:
        return Counter({compact: 1})
    return Counter(compact[i : i + 3] for i in range(len(compact) - 2))


def _cosine_sim(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(val * b.get(key, 0) for key, val in a.items())
    if dot <= 0:
        return 0.0
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_source_fragments(
    query: str,
    fragments: Sequence[Any],
    top_k: int = 8,
) -> list[Any]:
    """Xếp hạng lai thuần Python: 0.6 BM25 không dấu + 0.4 cosine char-trigram."""
    items = list(fragments)
    limit = max(0, int(top_k))
    if not items or limit == 0:
        return []
    q_norm = _normalize_search_text(query).strip()
    if not q_norm:
        return items[:limit]

    q_tokens = _TOKEN_RE.findall(q_norm)
    q_trigrams = _char_trigrams(q_norm)

    doc_norms = [_normalize_search_text(_fragment_text(frag)) for frag in items]
    doc_tokens = [_TOKEN_RE.findall(txt) for txt in doc_norms]
    doc_trigrams = [_char_trigrams(txt) for txt in doc_norms]

    n_docs = len(items)
    avgdl = sum(len(toks) for toks in doc_tokens) / max(1, n_docs)
    df: Counter[str] = Counter()
    for toks in doc_tokens:
        for tok in set(toks):
            df[tok] += 1

    k1 = 1.5
    b = 0.75
    bm25_scores: list[float] = []
    for toks in doc_tokens:
        if not q_tokens or not toks:
            bm25_scores.append(0.0)
            continue
        tf = Counter(toks)
        dl = len(toks)
        score = 0.0
        for tok in q_tokens:
            freq = tf.get(tok, 0)
            if freq <= 0:
                continue
            n_df = df.get(tok, 0)
            idf = math.log((n_docs - n_df + 0.5) / (n_df + 0.5) + 1.0)
            denom = freq + k1 * (1.0 - b + b * (dl / max(1.0, avgdl)))
            score += idf * (freq * (k1 + 1.0)) / denom
        bm25_scores.append(score)

    max_bm25 = max(bm25_scores) if bm25_scores else 0.0
    tri_scores = [_cosine_sim(q_trigrams, doc_trigrams[idx]) for idx in range(n_docs)]
    eligible = [
        idx
        for idx in range(n_docs)
        if bm25_scores[idx] >= _MIN_BM25_SCORE or tri_scores[idx] >= _MIN_TRIGRAM_COSINE
    ]
    if not eligible:
        return []

    def _hybrid_key(idx: int) -> tuple[float, int]:
        bm25_norm = (bm25_scores[idx] / max_bm25) if max_bm25 > 0.0 else 0.0
        combined = 0.6 * bm25_norm + 0.4 * tri_scores[idx]
        return (-combined, idx)

    eligible.sort(key=_hybrid_key)
    return [items[idx] for idx in eligible[:limit]]


def workspace_page_sources(
    exam,
    owner_id: str,
    keys: tuple[SourceKey, ...],
    db,
    *,
    teacher_files_only: bool = False,
    reject_non_teacher: bool = False,
):
    """Resolve selected pages from the current exam snapshot."""
    chosen = {
        (str(source_id), locator.index) for source_id, locator in keys if locator.kind == "page"
    }
    if not chosen:
        return ()
    catalog = {collection["id"]: collection for collection in lesson_catalog()}
    sources = []
    skipped_non_teacher = False
    for doc in exam.get("docs", []):
        doc_id = doc.get("id")
        if not any(source_id == doc_id for source_id, _ in chosen):
            continue
        if teacher_files_only and not is_teacher_owned_source(doc):
            skipped_non_teacher = True
            if reject_non_teacher:
                raise AIError(
                    "strict_source_policy",
                    "Đề đang bật chế độ chỉ bám tài liệu giáo viên tải lên.",
                    http_status=400,
                )
            continue
        license_status = str(
            doc.get("licenseStatus") or doc.get("license_status") or "allowed"
        ).strip()
        if license_status in {"restricted", "pending_review"}:
            raise AIError(
                "source_license_restricted",
                "Nguồn chưa có quyền dùng cho AI hoặc đang bị hạn chế.",
                http_status=403,
            )
        collection = catalog.get(doc_id)
        saved_pages = doc.get("pages") or []
        doc_version = doc.get("version", 1)
        edited_copy = (
            doc.get("catalog") is True
            and type(doc_version) is int
            and doc_version > 1
            and any(page.get("method") == "manual" for page in saved_pages)
        )
        if doc.get("personalLesson") is True:
            record = read_usable_curriculum_source(db, owner_id, doc_id)
            version = record.updated_at
            if doc_version != version:
                raise AIError("stale_snapshot", "Học liệu cá nhân đã đổi. Hãy chọn lại bài.")
            pages = [{"number": 1, "text": record.content_excerpt}]
        elif edited_copy or collection is None:
            if not edited_copy and doc.get("catalog") is True:
                raise AIError("source_not_found", "Học liệu đã chọn không còn trong thư viện.")
            pages = saved_pages or [{"number": 1, "text": doc.get("text", "")}]
            version = doc.get("version", 1)
        else:
            if doc.get("version", 1) != collection["version"]:
                raise AIError("stale_snapshot", "Học liệu đã đổi. Hãy chọn lại bài trong thư viện.")
            pages = [
                {
                    "number": lesson["number"],
                    "text": (
                        f"Bài {lesson['number']}. {lesson['title']}\n{lesson['text']}\n"
                        f"Mục tiêu: {lesson['outcome']}"
                    ),
                }
                for lesson in collection["lessons"]
            ]
            version = collection["version"]
        for page in pages:
            number = page.get("number")
            if type(number) is not int or (doc_id, number) not in chosen:
                continue
            text = page.get("text")
            if not isinstance(text, str) or not text.strip():
                raise AIError("invalid_source", "Trang nguồn không có văn bản hợp lệ.")
            if len(text) > 12000:
                raise AIError("source_limit", "Trang nguồn vượt 12.000 ký tự.")
            try:
                sources.append(
                    SourceFragment(
                        ownerId=owner_id,
                        sourceId=UUID(doc_id),
                        sourceVersion=version,
                        locator=Locator(kind="page", index=number),
                        text=text,
                    )
                )
            except (ValidationError, ValueError):
                raise AIError("invalid_source", "Trang nguồn đang lưu không hợp lệ.") from None
    if teacher_files_only and skipped_non_teacher and not sources:
        raise AIError(
            "strict_source_policy",
            "Đề đang bật chế độ chỉ bám tài liệu giáo viên tải lên.",
            http_status=400,
        )
    if sum(len(source.text) for source in sources) > 12000:
        raise AIError("source_limit", "Chọn các trang có tổng cộng tối đa 12.000 ký tự.")
    return tuple(sources)
