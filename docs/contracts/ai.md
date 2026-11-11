# Hợp đồng AI Python cho Sinh, Sửa và Kiểm

Bản để BE-2, BE-3, BE-5 và UI-3 review theo [BE-1-001 #4](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/4). Các service Python của [BE-1-002 #12](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/12) đã có bộ kiểm cục bộ cho Sinh đề, Sửa lời giải và Kiểm đáp án. Đã có service và router ghép cho xác nhận sửa lời giải và đề mới. Cần nối phiên xác thực, repository thật và UI. Hợp đồng kế thừa QuestionRef, SourceRef và thao tác đề xuất/xác nhận từ [mô hình Abstraction](../course/CONTRACTS.md).

## Chọn cách xử lý

| Ý định | Kiểm tra trước khi chạy | Kết quả dự kiến |
|---|---|---|
| Sinh đề | Làm rõ môn, lớp, số câu, cấu trúc điểm và nguồn nếu thiếu. Dùng quy tắc cục bộ để kiểm cấu trúc trước khi yêu cầu model sinh. | Service Python trả đề xuất khớp từng ô ma trận, điểm, barem và trích dẫn đã đối chiếu. |
| Sửa | Xác định đúng đề, revision, câu và đoạn giáo viên chọn. Nếu không xác định được phạm vi thì yêu cầu chọn lại. | Đề xuất sửa lời giải đã có trong Python. Các dạng sửa đề bài, đáp án, barem, bảng hoặc hình cần bổ sung quy tắc phụ thuộc và bảo toàn rich document. |
| Kiểm đáp án | Dùng bộ kiểm cục bộ cho dạng hỗ trợ. Nếu cần model giải lại, chỉ gửi đề bài, phương án và nguồn đã chọn. | Service Python nhận lời giải độc lập rồi đối chiếu câu trắc nghiệm hoặc đúng sai với đáp án lưu. |

## Đầu vào và đầu ra đã có

- BE-2 lấy chủ sở hữu từ phiên đã xác thực. BE-3 đọc đề và các nguồn bằng quyền của người đó, rồi tạo snapshot cho [AIJob](../../backend/src/mach_backend/ai_contract.py). Trình duyệt gửi vùng chọn và yêu cầu. Backend tự xác định nội dung khối, chủ sở hữu, nguồn được phép và mã job. Không nhận snapshot tùy ý từ trình duyệt để gửi model.
- Job giữ `jobId`, `examId` và `baseRevision`. Mỗi đích giữ `questionId`, `questionVersion`, `blockId`, `field` và văn bản gốc. `selection` gồm vị trí đầu và cuối không bao gồm ký tự cuối, theo đơn vị UTF-16 của JavaScript. Đích toàn khối dùng giá trị null. Khâu đọc snapshot chỉ cấp khối lời giải dạng văn bản mà editor có thể hiển thị an toàn.
- Mỗi đoạn nguồn có `sourceId`, `sourceVersion`, `locator` và văn bản. `locator.kind` là `page`, `passage` hoặc `region`. `index` bắt đầu từ 1. Vị trí vùng ảnh có thêm `regionId`. Giáo viên hoặc lớp truy xuất chọn đoạn cần dùng trước khi gọi service.
- Service kiểm đúng snapshot cả trước và sau lời gọi. Adapter gửi chỉ dẫn hệ thống và dữ liệu được chọn tới Ollama. Nội dung nguồn đi dưới dạng dữ liệu. Adapter không cấp công cụ hay gửi ID chủ sở hữu.
- Với mỗi khối cần sửa, Ollama chỉ nhận đoạn được chọn và trả `replacement` theo `blockId`. Python ghép phần thay thế vào snapshot gốc. `PatchProposal` giữ ba mã của job, danh sách `edits` với thao tác `replace`, `blockId` và toàn bộ văn bản khối sau sửa. Backend kiểm phần ngoài vùng, khối lặp, schema và cấu trúc công thức. Trích dẫn phải khớp ID, phiên bản, vị trí và đoạn văn thật sau khi chuẩn hóa khoảng trắng.
- Gọi `prepare_patch` để tạo và ghi bản xem trước. Callback lưu chỉ nhận đề xuất nếu snapshot và tác vụ vẫn còn hiệu lực tại thời điểm ghi. Bản xem trước chưa sửa đề. UI escape văn bản và dựng preview theo block ID. Khi gặp lỗi phiên bản, giữ phần nhập để giáo viên thử lại.

## Xác nhận sửa lời giải

- [Router](../../backend/src/mach_backend/patch_routes.py) cung cấp `POST /api/exams/{exam_id}/proposals/{job_id}/confirm`, body `{"baseRevision": 4}`. Chủ sở hữu lấy từ dependency phiên. API tìm đề xuất theo chủ sở hữu, đề và job. Trả 404 nếu không tìm thấy trong phạm vi, 409 nếu đề/nguồn đã đổi hoặc không thể giữ định dạng. Body sai schema trả 422.
- [Service](../../backend/src/mach_backend/patch_confirmation.py) kiểm lại đề, câu, khối, vùng chọn và nguồn trong giao dịch của BE-3. Sau khi lưu, tăng revision của đề và phiên bản các câu đổi, giữ UUID, đặt lại kết quả kiểm/duyệt của những câu đó. Trả `jobId`, `examId`, `baseRevision`, `revision` và `changedQuestionIds`. Xác nhận lại cùng job và base revision trả biên nhận cũ.
- Repository ghi bản đề, lịch sử và biên nhận cùng giao dịch. Job hủy hoặc hết hiệu lực phải bị loại trước khi xác nhận. Adapter test dùng SQLite tạm. Khi ghép BE-2/BE-3/BE-5, cần thay bằng phiên, trạng thái job và repository thật rồi mount router vào app.
- Với rich document, có thể sửa trong một nút chữ cùng định dạng hoặc đổi LaTeX của một nút công thức có sẵn. Thay đổi vắt qua nhiều nút hoặc thêm nút công thức mới trả `rich_document_conflict` và không ghi dữ liệu. UI có thể hướng dẫn chọn đoạn nhỏ hơn.

## Kiểm cấu trúc công thức

`validate_ai_text` dùng chung cho đầu ra Sinh/Sửa/Kiểm. Trong các đoạn công thức `$…$`, `$$…$$`, `\(…\)` và `\[…\]`, Python kiểm cặp dấu, ngoặc nhóm `{…}` và tên/thứ tự lồng nhau của `\begin{…}` / `\end{…}`. Ký hiệu escape, văn bản nguyên dạng `\verb` hợp lệ và chú thích `%` không làm lệch bộ đếm nhóm. Ngoặc trong văn bản ngoài công thức được giữ nguyên. Lỗi trả `invalid_math`; bước xác nhận Sinh/Sửa kiểm lại trước khi repository ghi và trả HTTP 409 nếu bản đề xuất không còn hợp lệ.

[17 ca chung với renderer Node](../../tests/fixtures/ai-math-structure.json) và [pytest cấu trúc](../../backend/tests/test_math_structure.py) bao phủ phân số, căn, hệ, ma trận, nhóm/môi trường lồng nhau và các trường hợp bị cắt. Bộ kiểm này chưa biên dịch mọi lệnh/đối số LaTeX, chưa chứng minh công thức render được hoặc đúng kiến thức. UI vẫn cần renderer hiện hành; BE-4 kiểm bản xuất riêng. Không dùng kết quả cấu trúc để gắn nhãn giáo viên đã duyệt hoặc đáp án đúng.

## Xác nhận lưu đề mới

- Sau khi có `GenerateJob` từ ma trận đã duyệt, `prepare_generation` trả bản xem trước và gọi repository để ghi `PendingGeneration`. Repository kiểm lại revision, đoạn nguồn và ma trận hiện hành trước khi ghi bản xem trước.
- Dùng cùng route `POST /api/exams/{exam_id}/proposals/{job_id}/confirm` với body `{"baseRevision": 4}`. Repository trả `ConfirmationState` có `approved_plan` kiểu `GenerationPlan`, được đọc trong cùng giao dịch. Backend kiểm chủ sở hữu, revision, nguồn và ma trận trước khi thay bộ câu của đề bằng kết quả đã xem trước.
- Python cấp UUID cho câu và các khối, đặt phiên bản câu mới bằng 1, giữ điểm và barem theo đơn vị 0,25 điểm. Đáp án trắc nghiệm, đúng–sai, trả lời ngắn được ánh xạ sang các trường hiện có. Trích dẫn giữ trong `evidence`. Câu và cả đề về trạng thái chờ duyệt.
- Repository lưu bản đề trước đó vào lịch sử, bộ câu mới và biên nhận trong cùng giao dịch. Đề tăng revision một lần. Xác nhận lại cùng job trả cùng UUID từ biên nhận. Lỗi ghi rollback cả đề và lịch sử. Tiêu đề và thiết lập trang được giữ từ bản hiện tại.
- [Các ca xác nhận Sinh](../../backend/tests/test_generation_confirmation.py) kiểm bốn dạng câu, ma trận đổi, nguồn đổi, đề khóa, hủy, rollback, xác nhận đồng thời và đọc lại biên nhận bằng repository mới trên cùng SQLite tạm. Route tạo job Sinh được mô tả bên dưới; cần nối UI và reader ma trận đã duyệt của kho thật.

## Tạo tác vụ Sinh qua HTTP

`build_generation_router` nhận runner dùng chung, dependency phiên và `read_inputs` theo [GenerationInputs](../../backend/src/mach_backend/generation_submission.py). Mount cùng `build_patch_job_router` và router xác nhận trên một app/event loop. Reader đọc đề, ma trận đã duyệt và đúng các đoạn nguồn theo owner trong cùng snapshot; không dùng ma trận của request làm bản phê duyệt. Reader và phiên thật vẫn do BE-2/BE-3 ghép, chưa mount vào app foundation mặc định.

`POST /api/exams/{exam_id}/proposals/generate` nhận ví dụ:

```json
{
  "requestId": "6cdd6c81-8024-4f26-a487-f818f6be71ae",
  "baseRevision": 4,
  "consent": true,
  "plan": {
    "subject": "Toán",
    "grade": "6",
    "instructions": "Sinh câu theo ma trận đã duyệt.",
    "slots": [{"type": "mcq", "topic": "Thay giá trị", "level": 0, "pointsQ4": 40}]
  },
  "sources": [],
  "requireEvidence": false
}
```

- `plan` là bản giáo viên đang xem để so với ma trận đã duyệt trong kho. Khác bản đã duyệt hoặc chưa có bản duyệt trả 409 `plan_not_approved`, không gọi AI. Kiểm revision, trạng thái đề, tổng 10 điểm, quyền/phiên bản nguồn trước khi xếp tác vụ. Nếu chọn nguồn, gửi tham chiếu `sourceId`, `sourceVersion`, `locator` như Sửa; backend tự đọc nội dung. Không nhận owner/jobId hoặc nội dung nguồn từ trình duyệt.
- Thành công trả 202 với `jobId` do Python tạo và trạng thái. Cùng owner/đề/requestId/nội dung trả cùng tác vụ trong phạm vi runner còn giữ; dùng lại requestId cho nội dung khác hoặc thao tác Sửa trả 409 `job_conflict`.
- Dùng chung `/proposals/{job_id}/status`, `/events`, `/cancel` và `/confirm`. SSE giữ tên sự kiện `patch` để tương thích bộ nhận hiện có; đề xuất Sinh chứa `questions`, đề xuất Sửa chứa `edits`. `Last-Event-ID` giữ quy tắc 1/2. Runner dùng chung hạn mức đồng thời và thời hạn cho Sinh/Sửa, giữ suất tới khi adapter thoát; hủy/quá hạn loại phản hồi muộn.
- Callback snapshot phải kiểm cả ma trận đã duyệt khi job là `GenerateJob`, ngoài revision và nguồn. Repository kiểm lại chúng cùng trạng thái tác vụ khi ghi `PendingGeneration` và khi xác nhận. Ma trận đổi khi đang chờ model khiến tác vụ thất bại, không tạo bản xem trước để lưu.
- Các lỗi trước tạo tác vụ: 401 chưa đăng nhập, 403 chưa đồng ý, 404 đề/nguồn ngoài quyền, 409 xung đột/ma trận chưa duyệt/đề khóa, 422 payload hoặc ma trận không hợp lệ, 429 hết suất. Lỗi model sau 202 nằm trong trạng thái/SSE `failed` và `errorCode`, không thay đổi đề.

[Các ca HTTP tạo Sinh](../../backend/tests/test_generation_submission.py) kiểm bốn dạng câu đến lưu, chỉ gửi nguồn đã chọn, replay, hủy/quá hạn, giả mạo payload và ma trận đổi trước/trong khi gọi model. Runner hiện giữ tác vụ trong RAM một tiến trình; receipt chỉ bền vững nếu repository được ghép lưu bền vững. Cần kiểm UI/phiên/kho thật và phục hồi tác vụ sau restart.

## Sinh đề và Kiểm đáp án

Hai luồng dùng chung mã tác vụ, kiểm phiên bản trước và sau khi xử lý, giới hạn thời gian, kiểm quyền nguồn và đối chiếu trích dẫn. Khi sinh, schema gửi Ollama ràng buộc dạng câu, chủ đề, mức độ, điểm đã duyệt và kiểu đáp án tương ứng. Python vẫn đối chiếu thứ tự, điểm, barem và kiểu đáp án sau khi nhận phản hồi. [Schema câu hỏi](../../backend/src/mach_backend/ai_questions.py) · [Service Python](../../backend/src/mach_backend/ai_service.py)

- `propose_exam` nhận 1–30 vị trí câu đã duyệt trong `slots`. Mỗi vị trí có dạng, chủ đề, mức độ và `pointsQ4`, số đơn vị 0,25 điểm. Tổng đề là 40 đơn vị. Kết quả cần đúng thứ tự, không thiếu câu, mỗi barem cộng đúng điểm của câu và mỗi trích dẫn khớp nguồn đã chọn. Khi xác nhận lưu, service cấp UUID cho câu và các khối rồi repository ghi cùng biên nhận. Bộ thử bao phủ trắc nghiệm, đúng sai, trả lời ngắn và tự luận.
- `check_question` kiểm một `BlindQuestion` gồm ID, phiên bản, dạng, đề bài và phương án. Khi gọi model, chỉ gửi các trường này, mã tác vụ và nguồn được phép. Đáp án lưu đi qua tham số riêng để đối chiếu sau khi có kết quả. `comparison` có thể là `agrees`, `disagrees` hoặc `needs_review`. Tự luận, trả lời ngắn, lời giải chưa chắc chắn hoặc thiếu đáp án lưu cần người xem lại. Kết quả trùng đáp án chỉ ghi nhận sự đồng thuận của hai giá trị.
- Python tự tính cho câu trắc nghiệm khớp trọn mẫu `Tính $x+1$ khi $x=2$.` với một phép cộng, trừ, nhân hoặc chia, có biến `x` và toàn bộ phương án là số. Phép tính dùng phân số chính xác, hỗ trợ số thập phân có dấu phẩy hoặc dấu chấm. Chia cho 0, không có đáp án khớp hoặc nhiều phương án cùng giá trị trả `needs_review`. Có chọn nguồn, yêu cầu trích dẫn hoặc câu ngoài mẫu thì dùng nhánh model. [Bộ kiểm thay số](../../backend/src/mach_backend/check_arithmetic.py)
- Khi nối HTTP, BE-2 cần lấy snapshot và đáp án lưu từ repository theo phiên người dùng. BE-5 cần gắn deadline và hủy vào tác vụ đang chạy. UI-3 có thể dùng [fixture Sinh/Kiểm](../../tests/fixtures/ai-sinh-kiem.json) để dựng màn hình xem trước và cảnh báo. Sau bước xác nhận, service lưu cần kiểm lại phiên bản trong giao dịch. Điểm hiển thị bằng `pointsQ4 / 4`.

## Kiểm đáp án qua HTTP

- `POST /api/exams/{exam_id}/questions/{question_id}/check` nhận `baseRevision`, `questionVersion`, `consent`, `sources` và `requireEvidence`. Body chỉ nhận tham chiếu nguồn, dạng locator như luồng Sửa. Backend lấy câu và đáp án đã lưu bằng quyền của phiên.
- [Router](../../backend/src/mach_backend/check_routes.py) nhận callback `read_inputs(owner, exam_id, question_id, source_keys)`. BE-3 trả `CheckInputs` có đúng chủ sở hữu, đề, revision, `BlindQuestion`, `saved_answer` và các đoạn nguồn hiện hành. `saved_answer` theo kiểu `Answer` được giữ ngoài payload provider. Bản chưa biết đáp án dùng `null`. Chỉ nguồn đã chọn được gửi model.
- Kết quả là `CheckReport` với `comparison` bằng `agrees`, `disagrees` hoặc `needs_review`. Backend ghi `method: "local_arithmetic"` khi tự tính và `method: "model"` khi nhận lời giải qua provider. Cả hai nhánh dùng cùng kiểm quyền và phiên bản. Route chỉ đọc, kể cả khi hai đáp án trùng nhau. Trước khi trả, route đọc lại câu, đáp án và nguồn để đối chiếu snapshot.
- Sai quyền hoặc thiếu câu/nguồn trả 404. Thiếu đồng ý trả 403, dữ liệu trình duyệt sai trả 422, câu/đáp án/nguồn đã đổi trả 409. Giới hạn provider trả 429, thiếu kết nối trả 503, quá hạn trả 504 và phản hồi model sai trả 502. Thời hạn bao gồm lần đọc kho ban đầu. Hủy hoặc lỗi trả lại suất xử lý của route.
- Router hiện đã được thử với phiên và SQLite tạm. Khi ghép app, BE-2 inject phiên thật, BE-3 ánh xạ kho đã chốt, BE-5 phối hợp giới hạn tác vụ giữa các luồng. UI-3 có thể gọi route để hiện đồng thuận/bất đồng và căn cứ cho giáo viên xem lại.

## Tạo yêu cầu sửa lời giải và chọn nguồn

- `POST /api/exams/{exam_id}/proposals` nhận `requestId`, `baseRevision`, `request`, `consent` và `targets`. Mỗi đích gồm `questionId`, `questionVersion`, `blockId` lời giải và `selection` theo UTF-16. Gửi `null` nếu chọn cả khối. `sources` là danh sách `sourceId`, `sourceVersion`, `locator`. Có thể dùng `requireEvidence` để yêu cầu căn cứ. Khi đã chọn nguồn, luôn kiểm trích dẫn.
- [Service tạo snapshot](../../backend/src/mach_backend/patch_submission.py) lấy chủ sở hữu từ phiên. BE-3 cung cấp `read_inputs(owner, exam_id, source_keys)` đọc đề và các đoạn hiện hành trong cùng một snapshot. Mỗi đoạn cần ID, phiên bản, locator và văn bản trích. Request chỉ được chứa tham chiếu. Khóa đoạn nguồn là cặp ID và locator. Đoạn bị xóa, thiếu, hoặc của người khác trả 404. Phiên bản lệch trả 409. Chỉ đoạn đã chọn được gửi provider.
- API trả 202 cùng `jobId` do server tạo. Gửi lại cùng `requestId` và nội dung trong phạm vi tài khoản/đề sẽ nhận lại job cũ khi còn lưu trong runner. Đổi nội dung với cùng mã trả 409. Khi chủ động bấm Thử lại sau lỗi, tạo `requestId` mới. Thiếu đồng ý trả 403, sai phạm vi đầu vào trả 422, hết suất trả 429.

## Chạy, theo dõi và hủy bản sửa lời giải

### Chia sẻ suất xử lý model giữa Sinh, Sửa và Kiểm

Khi ghép app, gọi `app.include_router(build_ai_router(...))` một lần, với phiên xác thực, repository xác nhận, ba reader, callback kiểm snapshot và callback lưu bản xem trước. [Điểm ghép FastAPI](../../backend/src/mach_backend/ai_routes.py)

Truyền một `OllamaProvider(model, max_active=1)` vào điểm ghép. Router dùng chung provider cho cả Sinh, Sửa và Kiểm, đồng thời tạo một runner cho Sinh/Sửa. Tham số `max_active` của router quản lý số tác vụ trong từng nhóm route. Tham số cùng tên của provider giới hạn tổng số lượt gọi model. Khi `provider=None`, câu Kiểm khớp mẫu vẫn tính được và yêu cầu cần model báo chưa cấu hình. App mặc định cần phiên và repository thật trước khi bật các route này.

Suất được giữ đến khi lời gọi adapter thoát, gồm lúc xử lý lỗi hoặc bị hủy. Nếu transport bắt hủy và còn chưa thoát, yêu cầu khác vẫn bị chặn. Sau lỗi HTTP hoặc sau khi transport đã thoát, suất được trả trong `finally`. API Kiểm trả 429 nếu model đang đủ suất; tác vụ Sinh/Sửa đã nhận 202 báo `failed`/`job_limit` qua trạng thái hoặc SSE khi tới bước gọi provider. Không tự xếp thêm hàng đợi hoặc gọi provider khác.

[Các ca giới hạn provider](../../backend/tests/test_ai_capacity.py) kiểm Sinh/Sửa cạnh tranh với HTTP Kiểm, lỗi 429/503, hủy và cấu hình hai suất. Giới hạn áp dụng trong một instance dùng chung trên cùng event loop. Tạo provider riêng cho từng route hoặc chạy nhiều process sẽ có các bộ đếm riêng; khi tích hợp nhiều worker cần tầng điều phối chung. Phép kiểm không đo thời điểm model ngừng tính toán phía Ollama.

[Ca tích hợp router](../../backend/tests/test_ai_routes.py) ghép đủ bảy đường dẫn trên một app. Kiểm cả hai chiều tranh suất, sai quyền, tạo lại tác vụ với mã mới, xem trước và xác nhận vào SQLite tạm.

- [PatchJobRunner](../../backend/src/mach_backend/patch_jobs.py) nhận snapshot đã được backend tạo. Gửi lại cùng job và snapshot trong thời gian còn lưu trả trạng thái hiện tại. Dùng lại ID với snapshot khác báo `job_conflict`. Vượt giới hạn job đang chạy báo `job_limit`. Chỗ còn giữ được đặt qua `max_retained`, chỉ loại job đã kết thúc. Khi tích hợp, tầng lưu cần bảo đảm idempotency cả sau khi app khởi động lại.
- Router của BE-2 dùng cùng tiền tố `/api/exams/{exam_id}/proposals/{job_id}`. `GET /status` đọc trạng thái, `GET /events` nhận SSE và `POST /cancel` yêu cầu hủy. Tất cả lấy chủ sở hữu từ phiên. Sai đề hoặc chủ sở hữu trả 404.
- SSE phát sự kiện `patch` với ID 1 khi còn chạy và ID 2 khi hoàn tất, hủy hoặc lỗi. Khi nối lại, gửi `Last-Event-ID` để lấy sự kiện mới hơn. Tác vụ đã kết thúc có thể chỉ phát ID 2. `complete` chứa bản xem trước đã lưu. Chỉ nút xác nhận riêng ghi vào đề.
- Ngắt kết nối SSE cho phép nối lại. Khi bấm Dừng hoặc quá thời hạn xử lý, kết quả về sau bị bỏ và API chỉ có một trạng thái cuối. Suất chạy vẫn được tính cho tới khi coroutine provider thoát. Hủy và lưu bản xem trước cùng dùng một khóa. Nếu bản xem trước đã ghi thì trả `complete` để người dùng tự chọn xác nhận. Repository kiểm revision khi ghi bản xem trước.
- Runtime hiện dùng một event loop và giữ trạng thái job trong bộ nhớ. UI còn cần gọi route tạo job. Phiên, reader dữ liệu thật, kho job bền vững và phục hồi khi tiến trình khởi động lại cần ghép với BE-2/BE-3/BE-5. Ca kiểm hiện chạy qua HTTP với SQLite tạm cho bản xem trước và xác nhận.

## Lỗi và phần BE-5/UI-3 cần ghép

| Trường hợp | Mã lỗi từ service | Hành vi đề xuất cho UI/API |
|---|---|---|
| Lệch phiên bản đề hoặc nguồn | `stale_snapshot` | Yêu cầu chọn lại. Không mở nút xác nhận trên phản hồi cũ. |
| Khối ngoài phạm vi, lệch job hoặc schema hỏng | `invalid_scope`, `wrong_job`, `invalid_result` | Hiển thị thông báo chung, giữ bản soạn và cho thử lại. |
| Ma trận, phương án, đáp án hoặc barem lệch | `invalid_plan`, `invalid_options`, `invalid_answer`, `invalid_rubric` | Chỉ rõ phần cần sửa trước khi thử lại. |
| Thiếu hoặc sai trích dẫn | `missing_source`, `missing_evidence`, `invalid_evidence` | Hướng dẫn chọn hoặc đối chiếu lại nguồn. |
| Chưa cấu hình, quá hạn hoặc provider lỗi | `provider_unconfigured`, `timeout`, `rate_limited`, `provider_unavailable` | Ghi lỗi có thể xử lý, chỉ gọi lại khi người dùng yêu cầu. |
| Người dùng hủy | `cancelled` ở API job | UI kết thúc chờ khi nhận trạng thái này. Phản hồi muộn không tạo bản xem trước. |

Deadline được áp trong service và bao gồm cả hai lần đọc snapshot. Người gọi chọn thời hạn từ cấu hình đã review, tối đa 300 giây. Giới hạn hiện tại là 12 khối, 12 đoạn nguồn, tổng 50.000 ký tự nguồn và phản hồi 256 KiB. Các route tạo, SSE và hủy bản sửa đã có. Ghép quyền lưu thật và retry bền vững cần phối hợp BE-2/BE-3/BE-5. Khi đưa vào API, mã trạng thái phải phản ánh lỗi và không trả nội dung thô từ model. Ghi provider, model do backend cấu hình, revision, trạng thái và thời gian vào log kỹ thuật khi ghép job.

## Chạy trên máy và chuẩn bị cho Thuận

Từ gốc repo, đối chiếu hành vi vùng chọn của Node và Python trên [fixture chung](../../tests/fixtures/ai-patch-local.json). [Kiểm nhanh ba luồng và xuất JUnit](../testing/KIEM_NHANH_AI.md) dùng cùng các ca mẫu với adapter giả lập hoặc model đã tải ở máy. Có thêm ca opt-in để kiểm lưu và hủy với Ollama thật.

```sh
node --test tests/selection.test.mjs tests/mvp-backend.test.mjs tests/greennode.test.mjs tests/cloud-ai.test.mjs
cd backend
uv sync --frozen
uv run pytest tests/test_ai_patch.py tests/test_ai_questions.py tests/test_patch_confirmation.py
```

Test Python dùng HTTP provider giả lập, snapshot tự tạo và HTTP FastAPI với SQLite tạm cho xác nhận. Để thử model thật sau khi API đã ghép, Thuận chọn model có sẵn trên máy và dùng Ollama ở `127.0.0.1:11434`. Tắt tính năng cloud ở tiến trình Ollama bằng `OLLAMA_NO_CLOUD=1`, rồi xác nhận log đã tắt cloud trước khi dùng dữ liệu ngoài fixture. Chọn model đã tải, thử trước với dữ liệu mẫu. Adapter gọi endpoint cố định và chỉ dùng kết nối được chọn. [API Ollama](https://docs.ollama.com/api/chat) · [Cấu hình chỉ chạy cục bộ](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)

Mọi kết nối ngoài máy về sau cần được chọn rõ, xác nhận nguồn gửi đi và ghi model/căn cứ trước khi gọi. Khi không có provider phù hợp, vẫn dùng editor và phép thử fixture. Thuận dùng [runbook](../../ops/greennode/README.md) và [checklist phát hành](../team/RELEASE.md) để chuẩn bị hạ tầng khi có release tích hợp.

Các kiểm tra cấu trúc công thức, phạm vi và trích dẫn là bằng chứng kỹ thuật phục vụ CT-03/04/05/06. Chất lượng kiến thức cần chấm riêng theo PoC. Cần ghép phiên, repository, kho job bền vững và UI thật rồi mới nghiệm thu luồng đầu cuối. Xác nhận Sinh đề dùng chung route giao dịch với Sửa, nhận snapshot ma trận đã duyệt từ repository.
