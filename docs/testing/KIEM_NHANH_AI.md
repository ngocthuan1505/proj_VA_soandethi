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


## Kiểm model thật đến bước lưu lời giải

Từ thư mục `backend`, có thể kiểm riêng route tạo đề xuất, SSE và xác nhận bằng cùng model đã tải:

```sh
uv run pytest tests/test_patch_confirmation.py -k test_smoke_sua_va_luu_qua_http --smoke-ollama-model MODEL_DA_TAI --smoke-timeout 120 -o junit_family=legacy --junitxml ../.runtime/ai-save-smoke.xml
```

Ca này dùng FastAPI, phiên giả lập và SQLite tạm. Sau khi model trả đề xuất, kiểm đề vẫn nguyên trước khi bấm xác nhận. Sau xác nhận, kiểm revision, lịch sử, công thức và các câu ngoài vùng sửa. Chế độ pytest mặc định bỏ qua ca này.

## Kiểm đáp án từ câu đã lưu qua HTTP

Từ `backend`, có thể thử riêng route Kiểm với model đã tải:

```sh
uv run pytest tests/test_check_routes.py -k test_smoke_kiem_qua_http --smoke-ollama-model MODEL_DA_TAI --smoke-timeout 120 -o junit_family=legacy --junitxml ../.runtime/ai-check-http.xml
```

Ca mẫu lưu sẵn một đáp án sai. Backend đọc câu và nguồn theo phiên giả lập, model giải từ đề/phương án và kết quả được đối chiếu với đáp án trong SQLite tạm. Kết quả phải báo bất đồng, có trích dẫn và giữ nguyên đề/lịch sử. Các ca fixture cùng file kiểm sai quyền, ghi đè đáp án từ trình duyệt, đổi nguồn/câu giữa chừng, timeout và giới hạn đồng thời.

## Kiểm hủy khi Ollama đang nhận yêu cầu

Từ `backend`, chọn đúng model đã tải:

```sh
uv run pytest tests/test_patch_confirmation.py -k test_smoke_huy_ollama_qua_http --smoke-ollama-model MODEL_DA_TAI --smoke-timeout 120 -o junit_family=legacy --junitxml ../.runtime/ai-cancel-smoke.xml
```

Ca thử đợi HTTPX gửi xong yêu cầu tới Ollama và bắt đầu chờ header phản hồi. Tài khoản khác bị từ chối hủy. Chủ đề thi hủy qua route FastAPI, kết nối HTTP từ app đóng, SSE chỉ phát lại một kết quả cuối và xác nhận trả 404. Với giới hạn một tác vụ, yêu cầu mới vẫn tới Ollama và nhận được đề xuất. Revision và lịch sử đề mẫu giữ nguyên. JUnit ghi thời gian đóng kết nối phía app sau khi hủy. [Trace HTTPX](https://www.python-httpx.org/advanced/extensions/#trace)

## Kết quả cục bộ ngày 11/11/2026

Đo trên laptop Windows bằng CPU, Ollama 0.40.16, ngữ cảnh 4.096 token và thời hạn 120 giây mỗi ca. Ba ca gọi trực tiếp adapter Python từ commit nghiệp vụ `200724a`. Chạy tuần tự và giữ cấu hình mặc định của model. Thời gian bên dưới là từng ca pytest, gồm thời gian tải model vào bộ nhớ ở ca đầu khi cần.

| Model | Sửa lời giải | Sinh đề | Kiểm đáp án |
|---|---|---|---|
| `qwen2.5:1.5b` · `65ec06548149` | `invalid_scope` · 17,041 giây | `invalid_answer` · 21,467 giây | `disagrees` · 14,705 giây |
| `qwen2.5:3b` · `357c53fb659c` | `invalid_scope` · 33,333 giây | `invalid_answer` · 46,108 giây | Đạt · 29,000 giây |

Lượt chẩn đoán riêng với 1.5B thấy bản sửa lệch cả hai đầu vùng được phép. Ca Sinh trả chuỗi cho đáp án trắc nghiệm. Ca Kiểm trả chỉ số 3 trong khi chỉ số đúng là 2. Bộ kiểm giữ trạng thái lỗi hoặc bất đồng tương ứng.

Ba ca dùng phản hồi mẫu đều đạt. Trên model thật, 1.5B đạt 0/3 và 3B đạt 1/3. Chưa chốt model mặc định. Hai lỗi lặp lại cần kiểm tiếp là yêu cầu model chép toàn khối lời giải và kiểu đáp án trắc nghiệm trong schema gửi model.


### Sau khi giới hạn vùng sửa và ràng buộc ma trận

Giữ cùng laptop, runtime, model digest và thời hạn. Adapter gửi riêng phần cần sửa rồi Python ghép lại từ snapshot. Schema Sinh ràng buộc dạng, chủ đề, mức độ, điểm và kiểu đáp án theo ma trận. Bộ kiểm phía Python tiếp tục kiểm tổng điểm barem, vị trí nguồn và nội dung trích dẫn.

| Model | Sửa lời giải | Sinh đề | Kiểm đáp án | Sửa rồi lưu qua HTTP |
|---|---|---|---|---|
| `qwen2.5:1.5b` | Đạt · 17,357 giây | `invalid_rubric` · 24,711 giây | `disagrees` · 14,992 giây | Chưa chạy |
| `qwen2.5:3b` | Đạt · 27,320 giây | Đạt · 37,945 giây | Đạt · 23,370 giây | Đạt · 28,008 giây |

Ca HTTP dùng model 3B xác nhận đề giữ nguyên trước khi bấm xác nhận. Sau xác nhận, revision đề 4→5, phiên bản câu 2→3, thêm một mục lịch sử và giữ nguyên công thức, định dạng, câu khác. Bộ mẫu này có một câu Sinh, một vùng Sửa và một câu Kiểm. Cần thêm bộ mẫu đa môn, kho dữ liệu thật và giao diện để nghiệm thu candidate.


### Hủy và chạy lại với Ollama thật

Ca HTTP hủy đạt với `qwen2.5:3b` digest `357c53fb659c`, Ollama 0.40.16 trên CPU, cloud tắt và thời hạn 120 giây. Từ lúc gọi hủy đến khi transport phía app đóng và thoát là 5,180 ms ở lượt ghi JUnit. Cả ca mất 28,010 giây, gồm yêu cầu mới chạy tới bản xem trước. Tài khoản khác nhận 404 khi hủy. Sau khi hủy, SSE có đúng một sự kiện cuối và xác nhận nhận 404. Revision đề vẫn 4, số mục lịch sử vẫn 0.

Phép thử dùng phiên giả lập và SQLite tạm. Số đo tính ở backend Python. Thời điểm Ollama ngừng tính toán bên server và luồng bấm Dừng trên giao diện thật còn cần đo riêng.


### Kiểm đáp án từ kho qua HTTP với model thật

Ca `test_smoke_kiem_qua_http` đạt với Qwen2.5 3B digest `357c53fb659c`, Ollama 0.40.16 CPU và cloud tắt. Thời gian pytest 35,099 giây. Kho mẫu cố ý lưu đáp án chỉ số 1. Model giải từ đề/phương án và nguồn rồi trả chỉ số đúng 2. API báo `disagrees`, kèm trích dẫn. Nội dung đề, revision và lịch sử giữ nguyên. Phiên và kho dùng fixture SQLite tạm.
