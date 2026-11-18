# PoC sinh đề theo ma trận trên bàn soạn thật

Hồ sơ lịch sử ngày 12–13/11. Xem [kết quả bản thử 13](NGHIEM_THU_BAN_13.md) để biết trạng thái hiện tại.

## Cập nhật 13/11/2026 — dùng vòng công cụ, chỉ xác nhận ở cuối

Phần triển khai hiện tại được mô tả ở [POC_AGENT_CMD.md](POC_AGENT_CMD.md). Mặc định `create_app` dùng `AgentGeneration`, cùng `run_matrix_agent` và các validator với CLI. Model chọn `check_exam`/`finish_exam` qua JSON action; code thực thi công cụ, đưa lỗi về model và giới hạn hai lần nộp bộ câu. Bản cũ sinh từng ô bên dưới chỉ còn là lịch sử thử nghiệm, không phải luồng mặc định.

Thử app thật ngày 13/11 qua `scripts/kiem-ui-poc.mjs --run-real`: job `723a008c-e3f8-4cb6-ab96-0b72e70fbf6f`, Qwen2.5 3B, 215,14 giây phía client; kết thúc `attempt_limit` vì câu trùng. Không có bộ xem trước hợp lệ, số câu lưu vẫn 0, revision vẫn 1. Nguồn tự viết, kho thử riêng. Đây là bằng chứng nhánh lỗi chạy qua UI/backend/model thật, chưa phải ca sinh đề thành công.

Người dùng không phải tự rà từng lỗi để model chạy tiếp. Khi model hoàn thành vòng kiểm, app chỉ yêu cầu giáo viên xem lại và xác nhận cuối. Mọi góp ý chưa xử lý vẫn chặn lưu. Có kiểm hồi quy giả lập cho vòng sửa rồi đạt, hai lần vẫn sai, xác nhận cuối và giữ lịch sử/undo. Bản hiện tại đạt 237 pytest, 5 ca model smoke bỏ qua mặc định; Ruff/format/ty đạt. 101 test Node và 14 test kế hoạch đã đạt trong lượt tích hợp trước. Không gọi các test giả lập là chất lượng của model.

Giới hạn app mới và CLI là 900 giây cho toàn tác vụ nhiều lượt. Không cộng các lượt app cũ 300 giây hoặc các phiên bản khác vào phép đối chiếu mới. Bằng chứng gốc nằm trong hồ sơ cục bộ. Nhánh PoC chưa merge vào app chung; không thao tác GreenNode.

## Hồ sơ thử trước khi chuyển sang vòng công cụ

Ngày bắt đầu: 12/11/2026. Trạng thái: đang tích hợp và kiểm, chưa kết luận thành công.

## Căn cứ và phạm vi

Thuận cung cấp hai ảnh trao đổi với giảng viên: phần rủi ro cần thử là sinh bộ câu theo ma trận; bộ câu phải phù hợp mức nhận thức yêu cầu; phải thể hiện hậu xử lý, sinh lại khi lỗi và ví dụ thuận/lỗi/bất ngờ. Đây là phản hồi thực tế của giảng viên, không phải góp ý của AI khác. Tham chiếu kiến thức CT-03/04/05/06 trong `docs/course/README.md`; không thay nó bằng một video dựng.

Nhánh `codex/sinh-ma-tran-app-that` kế thừa PR #39 tại `ab11137`. Giao diện vẫn là `index.html`, `app.js`, bàn soạn/editor của dự án. Python phục vụ giao diện, kho SQLite và luồng sinh ma trận; không chạy Node API để thực hiện nghiệp vụ này. `local_workspace.py` là điểm chạy lát tích hợp, không phải giao diện PoC riêng trước đây.

Bản này chỉ lắng nghe localhost, một chủ máy. Chưa chuyển đăng nhập nhiều người, chat legacy, nhập/xuất/OCR sang Python; route chưa chuyển báo rõ 503. Không gọi đây là toàn bộ app đã migrate. Dữ liệu thử nằm riêng; không chuyển DB hay tài liệu thật và không thao tác GreenNode.

## Những việc phải chứng minh

| Yêu cầu | Bằng chứng cần có | Trạng thái ban đầu |
|---|---|---|
| Sinh cả bộ theo ma trận đã duyệt | Request từ bàn soạn, bộ bốn câu thực, đối chiếu từng ô và tổng 10 điểm | Chờ chạy thật |
| Model thật tạo câu | Model/digest, nguồn nhập, trace, kết quả thật; không dùng provider fixture trong bản quay | Chờ kết quả |
| Bộ kiểm là code | Pytest cho số câu, dạng, nhãn ô, điểm, barem, đáp án, phương án, đoạn trích và câu trùng chữ | Kế thừa validator PR #39; bổ sung kiểm tích hợp |
| Rà mức nhận thức thực tế | Đọc từng câu, nêu thao tác học sinh cần làm; tách nhãn yêu cầu với mức người rà | Chờ bộ câu thật; không tự gán là giáo viên đã chấm |
| Gọi lại khi lỗi | Trace từng lần gọi, mã lỗi, phản hồi tiếp theo; tối đa hai lượt/tác vụ | Có code, cần kiểm |
| Không đạt thì dừng | Ca cố ý thiếu câu/hết lượt, bản đề không bị ghi dở | Chờ kiểm |
| Xem trước khác lưu | Trước xác nhận giữ nguyên đề, sau xác nhận đổi bộ câu trong chính bàn soạn | Chờ kiểm E2E |
| Giữ dữ liệu và phiên bản | Transaction, nguồn, UUID, lịch sử/undo, xác nhận lặp và stale | Chờ hồi quy + E2E |
| Có ca thuận/lỗi/bất ngờ | Đầu vào và kết quả được lưu, ghi rõ fixture kiểm code khác kết quả AI thật | Chờ tổng hợp |
| Demo dễ hiểu | Quay app sau kiểm, giải thích trước khi bấm, chỉ rõ kết quả; video không thay log | Chưa quay bản này |

## Cách phân biệt đúng nhãn và đúng mức

Nhận biết: tìm/nhớ chi tiết nêu trực tiếp. Thông hiểu: giải thích, nối thông tin hoặc suy ra ý nghĩa. Vận dụng: dùng kiến thức cho tình huống mới. Không dựa riêng vào từ hỏi “vì sao”, độ dài câu hay nhãn model tự gán.

Người rà ghi mức thực tế và lý do cho từng câu. Nhận xét lệch mức được gửi vào lượt sinh tiếp theo cùng nguồn, không tự đổi nhãn để che lỗi. Chỉ được xác nhận khi đủ nhận xét và không còn ý kiến lệch mức. Điều kiện này hỗ trợ quy trình, không chứng nhận kiến thức đúng tuyệt đối. Cần khai đúng ai rà; đánh giá của trợ lý không phải giáo viên duyệt độc lập.

## Tái lập

Backend: `uv sync --frozen`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`. Giao diện: kiểm hồi quy Node/nhóm và E2E riêng. Không gọi model trong CI; phép chạy model thật phải ghi riêng với nguồn tự viết/được phép sử dụng.

Điểm chạy dự kiến: `uv run uvicorn mach_backend.local_workspace:app --host 127.0.0.1 --port 4180 --app-dir src` từ `backend`. Phải đặt `MACH_DATA_DIR` tới kho thử riêng và bật Ollama local trước. Chưa đánh dấu bản nộp/PoC đạt trước khi đủ bằng chứng phía trên.
