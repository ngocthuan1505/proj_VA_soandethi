"""Server demo nhánh lỗi bằng phản hồi SOẠN SẴN, không gọi AI hoặc dùng kho app thật."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend/src"), str(ROOT / "backend/tests")]

from test_local_workspace import AgentModelFixture  # noqa: E402

CASES = (
    "repair",
    "missing_question",
    "multiple_correct",
    "unsupported",
    "unknown",
    "wrong_level",
    "duplicate",
    "budget",
    "cancel",
)


class FixtureCase:
    def __init__(self, case):
        if case not in CASES:
            raise ValueError("Chọn tình huống fixture có sẵn.")
        self.case = case
        self.model = AgentModelFixture(always_wrong=case == "budget")
        self.slots = []

    async def __call__(self, purpose, body):
        if purpose == "question_check":
            data = json.loads(body["messages"][1]["content"])
            kind = data["question"]["type"]
            return {
                "content": json.dumps(
                    {
                        **{k: data[k] for k in ("jobId", "examId", "baseRevision")},
                        "questionId": data["question"]["questionId"],
                        "questionVersion": data["question"]["questionVersion"],
                        "answer": {
                            "mcq": 0,
                            "essay": None,
                            "short": "Mai",
                            "truefalse": [True, False, True, False],
                        }[kind],
                        **(
                            {
                                "optionVerdicts": [
                                    "correct",
                                    "incorrect",
                                    "incorrect",
                                    "incorrect",
                                ]
                            }
                            if kind == "mcq"
                            else {}
                        ),
                        "explanation": "Lời giải GIẢ LẬP để kiểm giao diện, không phải AI thật.",
                        "uncertain": False,
                        "evidence": [
                            {
                                "sourceId": source["sourceId"],
                                "sourceVersion": source["sourceVersion"],
                                "locator": source["locator"],
                                "quote": source["text"][:1000],
                            }
                            for source in data["sources"]
                        ],
                    },
                    ensure_ascii=False,
                )
            }
        if purpose.startswith("scoped_patch"):
            data = json.loads(body["messages"][1]["content"])
            if purpose == "scoped_patch":
                self.patch_answers = [q["answer"] for q in data["questions"]]
                edits = []
                for q in data["questions"]:
                    scope = next(s for s in data["scopes"] if s["id"] == q["id"])
                    field = scope["field"]
                    content = q[field]
                    if field in {"stem", "explanation"}:
                        content = (
                            content + " (đã sửa)"
                            if scope["wholeField"]
                            else content.replace(
                                scope["text"], scope["text"] + " (đã sửa)", 1
                            )
                        )
                    for f in (
                        ("stem", "options", "answer", "explanation")
                        if field == "stem"
                        else (field,)
                    ):
                        edits.append(
                            {
                                "blockId": q["blockIds"][f],
                                "op": "replace",
                                "content": content if f == field else q[f],
                            }
                        )
                value = {
                    "edits": edits,
                    "message": "Đề xuất fixture kiểm UI, không phải AI thật.",
                }
            elif purpose == "scoped_patch_blind":
                value = {
                    "reviews": [
                        {
                            "ordinal": i,
                            "answer": answer,
                            "uncertain": False,
                            "optionVerdicts": [
                                "correct" if j == answer else "incorrect"
                                for j in range(4)
                            ],
                        }
                        for i, answer in enumerate(self.patch_answers)
                    ]
                }
            else:
                value = {
                    "reviews": [
                        {"ordinal": i, "agrees": True}
                        for i in range(len(data["questions"]))
                    ]
                }
            return {
                "role": "assistant",
                "content": json.dumps(value, ensure_ascii=False),
            }
        if self.case == "cancel":
            await asyncio.sleep(2)
        if purpose == "agent":
            self.slots = json.loads(body["messages"][1]["content"])["matrix"]["slots"]
        response = await self.model(purpose, body)
        if purpose == "agent":
            args = response["tool_calls"][0]["function"]["arguments"]
            if "questions" in args:
                template = args["questions"][0]
                args["questions"] = [
                    {**template, "stem": f"Câu giả lập {i}?"}
                    for i in range(len(self.slots))
                ]
        else:
            value = json.loads(response["content"])
            template = value["reviews"][0]
            value["reviews"] = [
                {
                    **template,
                    "ordinal": i,
                    **(
                        {"observedLevel": slot["level"]}
                        if purpose == "blind_content_check"
                        else {}
                    ),
                }
                for i, slot in enumerate(self.slots)
            ]
            response["content"] = json.dumps(value)
        first = self.model.attempts == 1
        if purpose == "agent" and first:
            args = response["tool_calls"][0]["function"]["arguments"]
            if self.case == "missing_question":
                args["questions"].pop()
            elif self.case != "budget":
                for q in args.get("questions", []):
                    q["answer"] = 0
                if self.case == "repair":
                    for q in args["questions"]:
                        q["answer"] = 1
        if purpose == "blind_content_check" and first:
            value = json.loads(response["content"])
            row = value["reviews"][0]
            if self.case == "multiple_correct":
                row.update(
                    answer=None,
                    uncertain=True,
                    optionVerdicts=["correct", "correct", "incorrect", "incorrect"],
                )
            elif self.case == "unsupported":
                row["supported"] = False
            elif self.case == "unknown":
                row.update(
                    answer=None,
                    uncertain=True,
                    optionVerdicts=["unknown", "incorrect", "incorrect", "incorrect"],
                )
            elif self.case == "wrong_level":
                row["observedLevel"] = 1
            elif self.case == "duplicate":
                value["reviews"][1]["duplicateWith"] = [0]
            response["content"] = json.dumps(value)
        return response


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="repair")
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="Kho thử riêng, không dùng kho app thật",
    )
    parser.add_argument("--port", type=int, choices=(4183, 4184), default=4183)
    args = parser.parse_args()
    if args.data.resolve() == (ROOT / "outputs/local-demo/data").resolve():
        parser.error("Không dùng kho app thật cho fixture.")
    os.environ["MACH_MODEL"] = "GIA_LAP_KIEM_CO_CHE"
    import uvicorn
    from mach_backend.local_workspace import create_app

    app = create_app(args.data, agent_call=FixtureCase(args.case))
    print(
        "ĐÂY LÀ FIXTURE. Không dùng làm số đo AI thật hoặc kết luận sư phạm.",
        flush=True,
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
