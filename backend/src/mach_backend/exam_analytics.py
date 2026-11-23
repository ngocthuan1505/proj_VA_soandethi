"""Phân tích chất lượng đề thi tức thì (<20ms): điểm sẵn sàng, phân bố, trùng lặp & kiểm lỗi."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from mach_backend.ai_contract import AIError, validate_math_markers, validate_math_structure

LEVEL_LABELS: tuple[str, str, str, str] = (
    "Nhận biết",
    "Thông hiểu",
    "Vận dụng",
    "Vận dụng cao",
)

TYPE_LABELS: dict[str, str] = {
    "mcq": "Trắc nghiệm",
    "truefalse": "Đúng / Sai",
    "short": "Trả lời ngắn",
    "essay": "Tự luận",
}

TYPE_ALIASES: dict[str, str] = {
    "mcq": "mcq",
    "multiple_choice": "mcq",
    "truefalse": "truefalse",
    "true_false": "truefalse",
    "short": "short",
    "short_answer": "short",
    "essay": "essay",
}

# Thời lượng ước lượng (phút) theo (dạng câu, mức nhận thức 0..3).
ESTIMATED_MINUTES_BY_TYPE_LEVEL: dict[str, tuple[float, float, float, float]] = {
    "mcq": (1.0, 1.5, 2.5, 3.5),
    "truefalse": (2.0, 3.0, 4.0, 5.0),
    "short": (2.0, 2.5, 3.5, 4.5),
    "essay": (5.0, 8.0, 12.0, 15.0),
}

_VN_TOKEN_RE = re.compile(r"[0-9a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]+")
_MINUTES_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


class ExamAnalyticsInput(BaseModel):
    """Mô hình đề thi linh hoạt (`extra="ignore"`) tương thích mọi trường giao diện."""

    model_config = ConfigDict(extra="ignore")

    questions: list[dict[str, Any]] = Field(default_factory=list)
    minutes: int | float | str | None = None
    timeMinutes: int | float | str | None = None
    duration: int | float | str | None = None
    targetPoints: float | None = None
    title: str | None = None
    subject: str | None = None
    grade: str | None = None


class AnalyzeExamRequest(BaseModel):
    """Payload yêu cầu phân tích chất lượng đề cho `POST /api/exams/analyze`."""

    model_config = ConfigDict(extra="forbid")

    exam: ExamAnalyticsInput


def _walk_rich_text(node: Any, depth: int = 0) -> list[str]:
    if not isinstance(node, dict) or depth > 64:
        return []
    kind = node.get("type")
    if kind == "text":
        text = node.get("text")
        return [text] if isinstance(text, str) and text else []
    if kind == "mathInline":
        attrs = node.get("attrs")
        if isinstance(attrs, dict) and isinstance(attrs.get("latex"), str):
            return [f"${attrs['latex']}$"]
        return []
    out: list[str] = []
    children = node.get("content")
    if isinstance(children, list):
        for child in children:
            out.extend(_walk_rich_text(child, depth + 1))
    return out


def _stem_text(question: dict[str, Any]) -> str:
    stem = question.get("stem")
    if isinstance(stem, str) and stem.strip():
        return stem
    rich_doc = question.get("richDoc")
    if isinstance(rich_doc, dict):
        return " ".join(_walk_rich_text(rich_doc)).strip()
    return stem if isinstance(stem, str) else ""


def _explanation_text(question: dict[str, Any]) -> str:
    exp = question.get("explanation")
    if isinstance(exp, str) and exp.strip():
        return exp.strip()
    exp_doc = question.get("explanationDoc")
    if isinstance(exp_doc, dict):
        return " ".join(_walk_rich_text(exp_doc)).strip()
    return ""


def _normalize_qtype(question: dict[str, Any]) -> str:
    raw = str(question.get("type") or "mcq").strip().lower()
    return TYPE_ALIASES.get(raw, "mcq")


def _normalize_level(question: dict[str, Any]) -> int:
    raw = question.get("level", 0)
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int) and 0 <= raw <= 3:
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        val = int(raw.strip())
        if 0 <= val <= 3:
            return val
    return 0


def _parse_points(question: dict[str, Any]) -> float:
    raw = question.get("points")
    if isinstance(raw, bool) or raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw) if math.isfinite(raw) and raw >= 0 else 0.0
    if isinstance(raw, str):
        try:
            val = float(raw.strip().replace(",", "."))
            return val if math.isfinite(val) and val >= 0 else 0.0
        except ValueError:
            return 0.0
    return 0.0


def _parse_exam_minutes(exam: dict[str, Any]) -> float:
    for key in ("minutes", "timeMinutes", "duration"):
        raw = exam.get(key)
        if isinstance(raw, bool) or raw is None:
            continue
        if isinstance(raw, (int, float)) and math.isfinite(raw) and raw > 0:
            return float(raw)
        if isinstance(raw, str):
            match = _MINUTES_RE.search(raw)
            if match:
                try:
                    val = float(match.group(1).replace(",", "."))
                    if math.isfinite(val) and val > 0:
                        return val
                except ValueError:
                    continue
    return 45.0


def _is_approved(question: dict[str, Any]) -> bool:
    if question.get("approved") is True:
        return True
    version = question.get("v")
    for field in ("approval", "check"):
        info = question.get(field)
        if isinstance(info, dict) and info.get("status") == "approved":
            if version is None or info.get("version") == version:
                return True
    return False


def _has_valid_answer(question: dict[str, Any], qtype: str) -> tuple[bool, int | None]:
    """Trả về `(có_đáp_án_hợp_lệ, chỉ_số_mcq_0_3_hoặc_None)`."""
    if question.get("answerKnown") is False:
        return False, None

    if qtype == "mcq":
        options = question.get("options")
        opt_len = len(options) if isinstance(options, list) else 4
        ans = question.get("answer")
        if isinstance(ans, bool):
            return False, None
        if isinstance(ans, int) and 0 <= ans < max(1, min(4, opt_len)):
            return True, ans
        if isinstance(ans, str):
            clean = ans.strip().upper()
            if clean in {"A", "B", "C", "D"}:
                idx = ord(clean) - 65
                if idx < max(1, opt_len):
                    return True, idx
        return False, None

    if qtype == "truefalse":
        truth = question.get("truthValues")
        if isinstance(truth, list) and len(truth) == 4 and all(type(v) is bool for v in truth):
            return True, None
        ans = question.get("answer")
        if isinstance(ans, list) and len(ans) == 4 and all(type(v) is bool for v in ans):
            return True, None
        if isinstance(ans, str):
            compact = ans.strip().upper()
            if len(compact) == 4 and set(compact) <= {"0", "1", "T", "F", "Đ", "D", "S"}:
                return True, None
        return False, None

    if qtype == "short":
        ans_text = question.get("answerText")
        if isinstance(ans_text, str) and ans_text.strip():
            return True, None
        ans = question.get("answer")
        if isinstance(ans, str) and ans.strip():
            return True, None
        if isinstance(ans, (int, float)) and not isinstance(ans, bool) and math.isfinite(ans):
            return True, None
        return False, None

    # Essay: coi là hợp lệ nếu có rubric hoặc lời giải mẫu
    rubric = question.get("rubric")
    has_rubric = isinstance(rubric, list) and len(rubric) > 0
    return (has_rubric or bool(_explanation_text(question))), None


def _has_unbalanced_braces(text: str) -> bool:
    depth = 0
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return True
    return depth != 0


def _has_unbalanced_dollars(text: str) -> bool:
    count = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "$":
            if i + 1 < n and text[i + 1] == "$":
                count += 2
                i += 2
                continue
            count += 1
        i += 1
    # Nếu lẻ dấu $ thì chắc chắn lỗi; kiểm thêm $$ cặp riêng
    if count % 2 != 0:
        return True
    return False


def _question_math_error(question: dict[str, Any]) -> str | None:
    texts: list[str] = []
    for key in ("stem", "explanation", "answerText"):
        val = question.get(key)
        if isinstance(val, str) and val:
            texts.append(val)
    options = question.get("options")
    if isinstance(options, list):
        texts.extend(opt for opt in options if isinstance(opt, str) and opt)
    rubric = question.get("rubric")
    if isinstance(rubric, list):
        for step in rubric:
            if isinstance(step, dict):
                for key in ("text", "criterion", "content", "step"):
                    val = step.get(key)
                    if isinstance(val, str) and val:
                        texts.append(val)

    for chunk in texts:
        if _has_unbalanced_dollars(chunk):
            return "Công thức có dấu $ lẻ cặp."
        if "$" in chunk and _has_unbalanced_braces(chunk):
            return "Công thức có cặp ngoặc {} không cân."
        try:
            validate_math_markers(chunk)
        except AIError as err:
            return str(err)

    formulas = question.get("formulas")
    if isinstance(formulas, list):
        for formula in formulas:
            if isinstance(formula, dict) and isinstance(formula.get("latex"), str):
                latex = formula["latex"]
                if _has_unbalanced_braces(latex):
                    return "Công thức độc lập có ngoặc {} không cân."
                try:
                    validate_math_structure(latex)
                except AIError as err:
                    return str(err)
    return None


def _normalize_vietnamese_tokens(text: str) -> set[str]:
    nfc = unicodedata.normalize("NFC", str(text or "")).casefold()
    # Loại bỏ các dấu phân tách LaTeX nhưng giữ từ/số tiếng Việt
    cleaned = nfc.replace("$", " ")
    tokens = _VN_TOKEN_RE.findall(cleaned)
    return {tok for tok in tokens if tok}


def analyze_exam(exam: dict[str, Any]) -> dict[str, Any]:
    """Phân tích chất lượng đề thi trong bộ nhớ, thời gian chạy mục tiêu <20ms."""
    raw_questions = exam.get("questions")
    questions: list[dict[str, Any]] = (
        [q for q in raw_questions if isinstance(q, dict)] if isinstance(raw_questions, list) else []
    )
    total_questions = len(questions)

    raw_target = exam.get("targetPoints")
    target_points = (
        float(raw_target)
        if isinstance(raw_target, (int, float))
        and not isinstance(raw_target, bool)
        and math.isfinite(raw_target)
        and raw_target > 0
        else 10.0
    )
    exam_minutes = _parse_exam_minutes(exam)

    level_counts = [0, 0, 0, 0]
    level_points = [0.0, 0.0, 0.0, 0.0]
    type_counts: dict[str, int] = {k: 0 for k in TYPE_LABELS}
    type_points: dict[str, float] = {k: 0.0 for k in TYPE_LABELS}

    answer_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    mcq_letter_sequence: list[tuple[int, str]] = []

    total_points = 0.0
    estimated_minutes = 0.0
    approved_count = 0
    issues: list[dict[str, Any]] = []
    token_sets: list[set[str]] = []

    for idx, q in enumerate(questions):
        qtype = _normalize_qtype(q)
        level = _normalize_level(q)
        pts = _parse_points(q)

        total_points += pts
        level_counts[level] += 1
        level_points[level] += pts
        type_counts[qtype] += 1
        type_points[qtype] += pts
        estimated_minutes += ESTIMATED_MINUTES_BY_TYPE_LEVEL[qtype][level]

        if _is_approved(q):
            approved_count += 1

        has_ans, mcq_idx = _has_valid_answer(q, qtype)
        if not has_ans:
            issues.append(
                {
                    "severity": "error" if qtype != "essay" else "warn",
                    "code": "missing_answer" if qtype != "essay" else "missing_rubric",
                    "message": (
                        f"Câu {idx + 1} chưa có đáp án đúng."
                        if qtype != "essay"
                        else f"Câu {idx + 1} (Tự luận) chưa có barem hoặc lời giải mẫu."
                    ),
                    "questionIndex": idx,
                }
            )
        elif qtype == "mcq" and mcq_idx is not None:
            letter = "ABCD"[mcq_idx]
            answer_counts[letter] += 1
            mcq_letter_sequence.append((idx, letter))

        if not _explanation_text(q) and qtype != "essay":
            issues.append(
                {
                    "severity": "warn",
                    "code": "missing_explanation",
                    "message": f"Câu {idx + 1} chưa có lời giải chi tiết.",
                    "questionIndex": idx,
                }
            )

        math_err = _question_math_error(q)
        if math_err is not None:
            issues.append(
                {
                    "severity": "error",
                    "code": "math_syntax_error",
                    "message": f"Câu {idx + 1}: {math_err}",
                    "questionIndex": idx,
                }
            )

        token_sets.append(_normalize_vietnamese_tokens(_stem_text(q)))

    total_points_rounded = round(total_points, 4)
    points_delta = round(total_points_rounded - target_points, 4)
    estimated_minutes_rounded = round(estimated_minutes, 1)

    if total_questions == 0:
        issues.append(
            {
                "severity": "error",
                "code": "empty_exam",
                "message": "Đề thi chưa có câu hỏi nào.",
            }
        )
    elif abs(points_delta) > 1e-6:
        issues.append(
            {
                "severity": "error",
                "code": "points_mismatch",
                "message": (
                    f"Tổng điểm hiện tại là {total_points_rounded:g}đ, "
                    f"lệch {points_delta:+g}đ so với mục tiêu {target_points:g}đ."
                ),
            }
        )

    # Phân bố đáp án MCQ và phát hiện chuỗi lặp liên tiếp
    total_mcq = len(mcq_letter_sequence)
    max_streak = 0
    streak_questions: list[int] = []
    if mcq_letter_sequence:
        cur_letter = mcq_letter_sequence[0][1]
        cur_indices = [mcq_letter_sequence[0][0]]
        for q_idx, letter in mcq_letter_sequence[1:]:
            if letter == cur_letter:
                cur_indices.append(q_idx)
            else:
                if len(cur_indices) > max_streak:
                    max_streak = len(cur_indices)
                    streak_questions = list(cur_indices)
                cur_letter = letter
                cur_indices = [q_idx]
        if len(cur_indices) > max_streak:
            max_streak = len(cur_indices)
            streak_questions = list(cur_indices)

    max_ratio = (max(answer_counts.values()) / total_mcq) if total_mcq > 0 else 0.0
    imbalanced = bool((total_mcq >= 4 and max_ratio > 0.45) or max_streak >= 3)
    if imbalanced:
        reasons: list[str] = []
        if total_mcq >= 4 and max_ratio > 0.45:
            top_letter = max(answer_counts, key=lambda k: answer_counts[k])
            reasons.append(f"đáp án {top_letter} chiếm {round(max_ratio * 100, 1)}% (>45%)")
        if max_streak >= 3:
            labels = ", ".join(f"Câu {i + 1}" for i in streak_questions)
            reasons.append(f"lặp liên tiếp {max_streak} câu ({labels})")
        issues.append(
            {
                "severity": "warn",
                "code": "answer_imbalance",
                "message": "Phân bố đáp án trắc nghiệm bị lệch: " + "; ".join(reasons) + ".",
            }
        )

    # Kiểm lệch thời lượng > 30%
    if (
        total_questions > 0
        and exam_minutes > 0
        and abs(estimated_minutes_rounded - exam_minutes) / exam_minutes > 0.30
    ):
        issues.append(
            {
                "severity": "warn",
                "code": "duration_mismatch",
                "message": (
                    f"Thời lượng ước tính (~{estimated_minutes_rounded:g} phút) "
                    f"lệch hơn 30% so với thời gian làm bài ({exam_minutes:g} phút)."
                ),
            }
        )

    # Phát hiện câu trùng lặp (Jaccard >= 0.65)
    duplicates: list[dict[str, Any]] = []
    for i in range(total_questions):
        s1 = token_sets[i]
        if len(s1) < 2:
            continue
        for j in range(i + 1, total_questions):
            s2 = token_sets[j]
            if len(s2) < 2:
                continue
            union_len = len(s1 | s2)
            if union_len == 0:
                continue
            sim = len(s1 & s2) / union_len
            if sim >= 0.65:
                sim_rounded = round(sim, 4)
                duplicates.append({"q1Index": i, "q2Index": j, "similarity": sim_rounded})
                issues.append(
                    {
                        "severity": "warn",
                        "code": "duplicate_question",
                        "message": (
                            f"Câu {i + 1} và Câu {j + 1} có độ tương đồng cao "
                            f"({round(sim_rounded * 100, 1)}%)."
                        ),
                        "questionIndex": j,
                    }
                )

    level_distribution = [
        {
            "level": lv,
            "label": LEVEL_LABELS[lv],
            "count": level_counts[lv],
            "points": round(level_points[lv], 4),
            "percent": round((level_counts[lv] / total_questions) * 100, 1)
            if total_questions
            else 0.0,
        }
        for lv in range(4)
    ]

    type_distribution = [
        {
            "type": qtype,
            "label": label,
            "count": type_counts[qtype],
            "points": round(type_points[qtype], 4),
            "percent": round((type_counts[qtype] / total_questions) * 100, 1)
            if total_questions
            else 0.0,
        }
        for qtype, label in TYPE_LABELS.items()
    ]

    answer_distribution = {
        "A": answer_counts["A"],
        "B": answer_counts["B"],
        "C": answer_counts["C"],
        "D": answer_counts["D"],
        "totalMcq": total_mcq,
        "maxStreak": max_streak,
        "streakQuestions": streak_questions,
        "imbalanced": imbalanced,
    }

    if total_questions == 0:
        readiness_score = 0
    else:
        score = 100
        for issue in issues:
            sev = issue["severity"]
            if sev == "error":
                score -= 15
            elif sev == "warn":
                score -= 5
            else:
                score -= 1
        readiness_score = max(0, min(100, score))

    return {
        "readinessScore": readiness_score,
        "totalQuestions": total_questions,
        "totalPoints": total_points_rounded,
        "targetPoints": target_points,
        "pointsDelta": points_delta,
        "estimatedMinutes": estimated_minutes_rounded,
        "examMinutes": int(exam_minutes) if exam_minutes.is_integer() else exam_minutes,
        "approvedCount": approved_count,
        "levelDistribution": level_distribution,
        "typeDistribution": type_distribution,
        "answerDistribution": answer_distribution,
        "duplicates": duplicates,
        "issues": issues,
    }


def register_exam_analytics_routes(app: FastAPI) -> None:
    """Đăng ký tuyến `POST /api/exams/analyze` trên FastAPI."""

    @app.post("/api/exams/analyze")
    def analyze_exam_endpoint(payload: AnalyzeExamRequest) -> dict[str, Any]:
        return analyze_exam(payload.exam.model_dump())
