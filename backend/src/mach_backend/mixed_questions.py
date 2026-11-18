"""Dạng truyền gọn cho đề hỗn hợp; Python vẫn kiểm đáp án và barem theo từng ô."""

from typing import Annotated

from pydantic import Field

from mach_backend.ai_contract import AIError, BlockText, ContractModel
from mach_backend.ai_questions import Answer, RubricStep, validate_answer

ANSWER_GUIDE = (
    "Đề hỗn hợp: làm đúng type của từng slot, không đổi loại câu. "
    "answer luôn là CHUỖI: mcq dùng '0'/'1'/'2'/'3'; truefalse dùng đúng bốn ký tự 1/0 "
    "theo thứ tự nhận định (1010 là đúng,sai,đúng,sai); short ghi đáp án ngắn; essay dùng ''. "
    "Đáp án short phải theo yêu cầu trong stem: nếu đề yêu cầu điền số hoặc đã ghi đơn vị "
    "ở ô trả lời thì chỉ ghi số, giữ đơn vị và phép tính trong lời giải; nếu đề yêu cầu "
    "đơn vị trong đáp án thì ghi đủ đơn vị. Không tự bỏ đơn vị khi đề chưa xác định. "
    "mcq và truefalse có bốn options khác nhau; short/essay có options=[]. "
    "Mỗi câu có rubric gồm text và pointsQ4 (đơn vị 0,25 điểm), tổng bằng pointsQ4 của slot. "
    "Tự luận có lời giải hoàn chỉnh và barem từng bước; không thay bằng 'chọn đúng'."
)


class MixedDraftQuestion(ContractModel):
    stem: BlockText
    options: Annotated[tuple[BlockText, ...], Field(max_length=4)]
    answer: Annotated[str, Field(max_length=1000)]
    explanation: BlockText
    rubric: Annotated[tuple[RubricStep, ...], Field(min_length=1, max_length=40)]
    evidenceIds: Annotated[tuple[int, ...], Field(max_length=12)]


class MixedDraftBatch(ContractModel):
    questions: Annotated[tuple[MixedDraftQuestion, ...], Field(min_length=1, max_length=30)]


def decode_answer(kind, value, *, uncertain=False) -> Answer:
    if not isinstance(value, str):
        raise AIError("invalid_answer", "Đáp án trong lượt truyền hỗn hợp cần là chuỗi.")
    if uncertain and value == "":
        return None
    answer: Answer
    if kind == "mcq":
        if value not in {"0", "1", "2", "3"}:
            raise AIError("invalid_answer", "Đáp án trắc nghiệm cần chỉ số 0..3.")
        answer = int(value)
    elif kind == "truefalse":
        if len(value) != 4 or any(c not in "01" for c in value):
            raise AIError("invalid_answer", "Đáp án đúng-sai cần đủ bốn ký tự 1/0.")
        answer = (value[0] == "1", value[1] == "1", value[2] == "1", value[3] == "1")
    elif kind == "essay":
        if value != "":
            raise AIError("invalid_answer", "Câu tự luận cần answer rỗng và có lời giải/barem.")
        answer = None
    else:
        answer = value
    validate_answer(kind, answer)
    return answer
