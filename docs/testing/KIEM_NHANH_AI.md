# Kiểm nhanh Sinh, Sửa và Kiểm bằng Python

Dùng cho [BE-1-002 #12](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/12), [BE-1-003 #20](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/20) và người tổng hợp candidate ở [BE-5-003 #24](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/24).

## Chạy bằng phản hồi mẫu

Từ gốc repo, vào `backend` rồi chạy:

```sh
cd backend
uv sync --frozen
uv run pytest tests/test_ai_patch.py tests/test_ai_questions.py -k test_smoke
```

Ba ca đi qua adapter Ollama và bộ kiểm Python với HTTP giả lập. Sinh kiểm một câu theo ma trận và barem 10 điểm. Sửa kiểm đúng đoạn được chọn, phần giữ nguyên và trích dẫn. Kiểm giải lại câu trắc nghiệm rồi mới so đáp án lưu. Bộ pytest đầy đủ còn có ca bốn dạng câu, sai quyền, nguồn đổi phiên bản, timeout và hủy.

## Chạy model thật trên laptop

Thuận chọn model đã tải, bật Ollama tại `127.0.0.1:11434` với `OLLAMA_NO_CLOUD=1` trong môi trường của tiến trình Ollama. Kiểm log có `Ollama cloud disabled: true`. Model phải xuất hiện trong danh sách cục bộ. Lệnh smoke dùng đúng ba ca mẫu ở trên và kiểm model trước khi gọi. [Cấu hình Ollama cục bộ](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)

Từ thư mục `backend`, thay `MODEL_DA_TAI` bằng tên chính xác:

```sh
uv run pytest tests/test_ai_patch.py tests/test_ai_questions.py -k test_smoke --smoke-ollama-model MODEL_DA_TAI --smoke-timeout 120 -o junit_family=legacy --junitxml ../.runtime/ai-smoke.xml
```

JUnit ghi chế độ, tên và digest model, phiên bản Ollama, thời hạn, thời gian từng ca và mã lỗi khi có. Ghi kèm commit SHA từ `git rev-parse HEAD`, môi trường CPU/GPU và thời điểm chạy khi cập nhật issue. Báo riêng từng ca đạt hoặc lỗi. File kết quả để trong `.runtime`.

Ba ca kiểm giao tiếp và quy tắc đầu ra trên dữ liệu mẫu. Bằng chứng chấm nội dung, UI và cơ sở dữ liệu thật, hủy model thật, GreenNode và vận hành candidate cần ghi riêng theo [checklist phát hành](../team/RELEASE.md).


## Kết quả cục bộ ngày 11/11/2026

Đo trên laptop Windows bằng CPU, Ollama 0.40.16, ngữ cảnh 4.096 token và thời hạn 120 giây mỗi ca. Ba ca gọi trực tiếp adapter Python từ commit nghiệp vụ `200724a`. Chạy tuần tự và giữ cấu hình mặc định của model. Thời gian bên dưới là từng ca pytest, gồm thời gian tải model vào bộ nhớ ở ca đầu khi cần.

| Model | Sửa lời giải | Sinh đề | Kiểm đáp án |
|---|---|---|---|
| `qwen2.5:1.5b` · `65ec06548149` | `invalid_scope` · 17,041 giây | `invalid_answer` · 21,467 giây | `disagrees` · 14,705 giây |
| `qwen2.5:3b` · `357c53fb659c` | `invalid_scope` · 33,333 giây | `invalid_answer` · 46,108 giây | Đạt · 29,000 giây |

Lượt chẩn đoán riêng với 1.5B thấy bản sửa lệch cả hai đầu vùng được phép. Ca Sinh trả chuỗi cho đáp án trắc nghiệm. Ca Kiểm trả chỉ số 3 trong khi chỉ số đúng là 2. Bộ kiểm giữ trạng thái lỗi hoặc bất đồng tương ứng.

Ba ca dùng phản hồi mẫu đều đạt. Trên model thật, 1.5B đạt 0/3 và 3B đạt 1/3. Chưa chốt model mặc định. Hai lỗi lặp lại cần kiểm tiếp là yêu cầu model chép toàn khối lời giải và kiểu đáp án trắc nghiệm trong schema gửi model.
