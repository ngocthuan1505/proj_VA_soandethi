# Bàn giao: xây app và kiểm thử

Cập nhật: 07/11/2026.

## Hiện trạng đã kiểm

- 07/11 theo Thuận: dùng **tên tạm Soạn đề thi (Exam Maker)**, chưa chốt tên sản phẩm. Đổi title/nhãn/logo editor và đăng nhập, tiêu đề Swagger, README/tóm tắt/hướng dẫn/tài liệu môn/khung báo cáo; không sửa hồ sơ Docs/Canva hay bản bàn giao lý thuyết chưa commit. Có launcher mới `OPEN-SOAN-DE.ps1`, wrapper cũ tương thích; PDF sửa 3 tên trung tính, 6 trang/66 link đã render/kiểm metadata và đọc đủ trang, bản ở đường dẫn cũ cùng nội dung để giữ link đã gửi. Các module/liveness ID/biến/volume/đường dẫn lưu trữ/marker cũ giữ để dữ liệu, lệnh chạy và task không hỏng. Bảng GitHub đã đổi tên, vẫn Private; không đổi quyền, assignee hoặc Status.
- Kiểm lượt đổi tên: npm ci, 98 test Node, 14 test kế hoạch/link, uv sync frozen, 2 pytest, Ruff/format/ty đạt; 13 ca chat/usability và 12 ca authoring desktop/mobile đạt, có assert title/nhãn/logo mới. Bộ online lần đầu timeout 30 giây ở save-export; chạy lại riêng cùng source/fixture đạt đủ 9 ca gồm login/tên mới/lưu/reload/xuất Word-PDF/logout/quyền/mobile. Chưa kết luận nguyên nhân biến động thời gian; không sửa nghiệp vụ export trong lượt đổi tên. Không coi kiểm fixture là nghiệm thu dịch vụ AI thật hoặc chuyển hết Python. Tác động bên lý thuyết: dùng tên tạm này trong tài liệu mới; hồ sơ trực tuyến chưa tự sửa, không tuyên bố nhóm đã chốt thương hiệu.

- Có [bản tóm tắt toàn repo cho người mới](../../DOC_REPO_TRONG_5_PHUT.md), README dẫn bản này trước và thu gọn tài liệu chi tiết. Kiểm FastAPI thực tại loopback 8000/8080 trên clone riêng: cả hai health/docs 200, readiness 503 đúng foundation; dừng đúng tiến trình test, không đụng app 4173. Không có log máy thành viên nên chưa kết luận lỗi 8000 trên máy đó. [Hướng dẫn cổng thay thế/chẩn đoán](../team/LOI_CONG_API.md); không thay nghiệp vụ hoặc port mặc định toàn app.

- Theo Thuận sửa cơ chế nhận việc: chỉ chốt nhóm 3 UI/5 backend trong members.json, mã UI-1/BE-2… là mảng để nghiên cứu và tự chọn/làm chung; không gán người theo thứ tự. Có [menu định hướng và đăng ký](../team/CHON_VIEC.md). Bỏ auto-assign từ roster; quyền repo/Project và yêu cầu Python giữ nguyên, GreenNode chỉ Thuận. Bản PDF sửa 2 thay bảng phân công cứng trước đó.

- Đã xác minh tám username và nhóm UI/backend theo Thuận: [danh sách nhóm](../team/ROLES.md); mapping chuyên môn cũ đã được thay bằng cơ chế tự chọn. Gửi lời mời repo Write cho bảy thành viên; quyền chỉ có hiệu lực khi họ nhận. Project Private đã có owner + bảy người Write. Username đúng là lamngoc25032007-netizen và 2512716757-source; lời mời sai LamNgoc đã hủy. Có [file hướng dẫn gửi Discord](../team/HUONG_DAN_GUI_DISCORD.md); không tự gửi file lên Discord.

- Task được bổ sung chi tiết: 24 kỹ thuật + 6 hồ sơ, 150 bước Wxx và 90 ca Txx có expected result, điều kiện bắt đầu và artifact/consumer. [11 use case](../product/USE_CASES.md), [test tích hợp](../testing/KIEM_THU_TICH_HOP.md), [hợp đồng/gates](../team/KE_HOACH_TICH_HOP.md). Đây là **kế hoạch cần làm**, không phải code/test đã hoàn thành; giữ tiến độ/assignee/checklist cũ khi đồng bộ. Thêm bốn phụ thuộc nghiệm thu được giải thích trong gates.
- Đã kiểm kê [16 nhóm chức năng demo có sẵn](../product/DEMO_DA_CO.md), phân việc kế thừa theo tám vai trò và viết [hướng dẫn thành viên tự mở/dùng/test app](../team/CHAY_VA_TEST_DEMO.md). [Baseline 05/11](../testing/BASELINE_2026_11_05.md): 98 test Node, 10 test kế hoạch, 80 bước UI trong 7 bộ và 2 pytest nền đều đạt; ruff/format/ty đạt. Dùng clone tạm riêng để cài/test, không dùng DB cá nhân; chuyển tài liệu về thư mục chung bằng commit sau kiểm tra sạch.
- Bằng chứng trên chỉ là fixture/cục bộ, không là nghiệm thu AI thật/hosting/giáo viên hoặc hoàn tất Python. Có một deprecation warning Starlette/httpx trong pytest; chưa sửa dependency vì test vẫn đạt. Báo cáo ghi rõ phần chưa thử và log manifest; không đính kèm tài liệu thật.
- Source MVP kế thừa còn frontend/editor và Node backend ở gốc. `backend/` mới là nền FastAPI với health/readiness; chưa chuyển đủ auth/database/core/AI/job/import-export. [Hiện trạng](../architecture/CURRENT_STATE.md), [kế hoạch Python](../architecture/PYTHON_MIGRATION.md).
- Repo Private; đã chuẩn bị 24 task kỹ thuật, sáu task CT, phân vai 3 UI + 5 backend, bảng tiến độ và ba mẫu báo tiến độ/vướng mắc/nghiệm thu. [Bắt đầu làm nhóm](../team/README.md), [cách báo cáo](../team/BAO_CAO.md).
- Commit `361f1492c34df2ac48d1abfc4112a3d55e568115` đã đối chiếu hồ sơ chat nghiên cứu, ghi bằng chứng vào CT-01/02/03, sửa đầu vào bảy task để dùng lại thiết kế. CI commit đó thành công; không có nghĩa tính năng Python đã hoàn tất.
- Quy ước liên kết hai chat đặt trong [điểm bắt đầu chung](README.md) và AGENTS.md. Cả hai đã được kiểm tra cùng thuộc một project/thư mục; bản bàn giao file thay việc phải đọc lại toàn bộ hội thoại.

## Chuyển cho bên lý thuyết

- Trình bày riêng MVP kế thừa, thiết kế đích và phần Python thật sự đã chuyển. Chưa có bằng chứng kiểm thử thì không báo hoàn thành.
- Hồ sơ đã có được kế thừa qua [bảng đối chiếu](../course/HO_SO_DA_CO.md); nhóm không phải viết lại proposal/decomposition/abstraction từ đầu.
- Các task CT-01/02/03 đang làm từng phần, chưa nghiệm thu cả task. Không dùng việc chuyển cột trên bảng thay số đo khảo sát/PoC/UX.
- Chỉ Thuận vận hành GreenNode. Công việc chuẩn bị code, fixture, test và runbook không đòi server đang chạy; không tự triển khai hoặc gửi dữ liệu thật tới AI trả phí.

## Làm tiếp

Theo task đã nhận trong [backlog](../team/BACKLOG.md), chốt contracts/fixture rồi port theo từng lát chức năng sang Python. Khi hoàn tất mỗi lát, bổ sung commit, test, hành vi và giới hạn để bên nghiên cứu cập nhật đúng báo cáo. Ngôn ngữ/tỉ lệ GitHub không phải bằng chứng core đã chuyển.

Khi có thay đổi tiếp: thay nội dung hiện trạng bằng kết quả có bằng chứng, ghi tác động tới hồ sơ môn và việc còn thiếu; không gom log test dài hoặc thông tin bí mật vào đây.

## 11/11/2026 — hợp đồng AI và phần sửa lời giải cục bộ

- BE-1-001 (#4) có [hợp đồng AI](../contracts/ai.md) để nhóm review. BE-1-002 (#12) có service Python và adapter Ollama cho đề xuất thay văn bản lời giải. Service kiểm mã job, revision, vùng UTF-16, chủ sở hữu nguồn, locator và trích dẫn. Job, lưu xác nhận và UI sẽ ghép qua các hợp đồng BE-2/3/5.
- Bằng chứng cho UI-3 (#3) và BE-5 (#8): 29 pytest, 99 test Node, 14 test kế hoạch, 9 ca trình duyệt selection và kiểm tra Ruff/ty đều đạt. [Fixture chung](../../tests/fixtures/ai-patch-local.json) chạy qua validator Node và Python. Pytest kiểm lỗi sai job/nguồn/vùng, timeout, hủy coroutine và lỗi HTTP giả lập. Starlette còn cảnh báo deprecation từ TestClient.
- Bên lý thuyết có thể dẫn kết quả cho phần kiểm kỹ thuật CT-03/04/05/06. Không cộng ca fixture vào 48 lượt thí nghiệm. Cần ghép FastAPI/repository/UI, triển khai các loại sửa có phụ thuộc, Sinh/Kiểm và chấm kiến thức. Máy chưa thấy Ollama ở cổng 11434 trong lượt kiểm, bằng chứng adapter hiện tại là HTTP giả lập.

### 11/11/2026 — bổ sung Sinh và Kiểm cho BE-1

- PR #39 thêm service Sinh đề theo ma trận đã duyệt và Kiểm đáp án bằng lời giải độc lập. Đầu vào có mã tác vụ, revision, chủ sở hữu và nguồn có phiên bản. Sinh kiểm bốn dạng câu, 40 đơn vị 0,25 điểm, barem và trích dẫn. Kiểm chỉ gửi đề và phương án, dùng đáp án lưu sau khi nhận kết quả. Trạng thái đồng thuận cần người xem lại trước khi duyệt.
- Đã chạy 52 pytest, 100 test Node, 14 test kế hoạch và Ruff/ty. [Fixture Sinh/Kiểm](../../tests/fixtures/ai-sinh-kiem.json) dùng cho Python và đối chiếu trắc nghiệm/tự luận với Node. Kết nối Ollama trong phép thử dùng HTTP giả lập.
- Hợp đồng và fixture hỗ trợ BE-2 ghép snapshot theo phiên, BE-5 kiểm job cũ/hủy, UI-3 dựng preview. Bên lý thuyết dùng số ca này cho kiểm kỹ thuật CT-03/04/05/06. Phần còn lại gồm tuyến API xác thực, xác nhận lưu, hủy job phía server, các kiểu sửa có phụ thuộc và chấm đầu ra model thật.


<!-- ban-giao-xac-nhan-ai-39 -->
### 11/11/2026 — xác nhận lưu bản sửa lời giải

- [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) thêm service xác nhận và router để BE-2 ghép phiên cho #13, BE-3 ghép repository/giao dịch cho #14. Bản xem trước chưa đổi đề. Xác nhận kiểm chủ sở hữu, phiên bản đề/câu, phạm vi và nguồn. Ghi đề, lịch sử và biên nhận cùng giao dịch. Gửi lại cùng job và revision trả biên nhận cũ. [Hợp đồng AI](../contracts/ai.md).
- 13 ca mới kiểm qua FastAPI và SQLite tạm, gồm giữ định dạng/nút công thức, đề hoặc nguồn đã đổi, job mất hiệu lực, truy cập chéo, xác nhận đồng thời và rollback. Tổng cục bộ đạt 65 pytest, 100 test Node, 14 test kế hoạch và Ruff/ty. Starlette báo deprecation trong TestClient, các ca vẫn đạt.
- Bên lý thuyết có thể dùng các ca này làm bằng chứng kỹ thuật cho ADT đề xuất/xác nhận và CT-03/04/05/06. Router mới chạy với phiên và SQLite test. Cần ghép phiên, schema dữ liệu, job và UI thật. Kiểm model thật, xác nhận sinh đề và sửa các vùng phức tạp vẫn đang chờ.


<!-- ban-giao-huy-job-ai-39 -->
### 11/11/2026 — hủy và theo dõi tác vụ sửa lời giải

- [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) bổ sung runner Python và route trạng thái, SSE, hủy. API chỉ phục vụ đúng chủ sở hữu/đề/job. Nối lại SSE bằng Last-Event-ID. Hủy và quá hạn chặn bản xem trước đến muộn. Giới hạn đồng thời giữ suất đến lúc adapter thoát.
- Cục bộ đạt 70 pytest, 100 test Node, 14 test kế hoạch và Ruff/ty. Có ca ngắt HTTP khi đang nhận SSE, nối lại và xác nhận lưu với SQLite tạm, cùng ca quá hạn/hủy mà provider vẫn cố trả kết quả. Đây là bằng chứng kỹ thuật E07 cho CT-04/05/06. Phép thử mô hình thật vẫn riêng.
- [Hợp đồng](../contracts/ai.md) để UI-3, BE-2, BE-3 và BE-5 ghép. Runner hiện giữ job trong bộ nhớ của một tiến trình. Cần nối tạo job từ UI, phiên thật, lưu job bền vững, phục hồi sau khởi động lại và kiểm đầu cuối. Bản xem trước chỉ ghi vào đề sau thao tác xác nhận riêng.


<!-- ban-giao-tao-job-nguon-39 -->
### 11/11/2026 — tạo đề xuất với vùng chọn và đoạn nguồn đã xác thực

- [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) có route tạo job sửa lời giải. Python lấy owner từ phiên, đọc đề và đoạn nguồn theo ID, phiên bản và locator. Chỉ truyền đoạn đã chọn cho adapter. Gửi lặp cùng requestId và nội dung nhận job cũ trong giới hạn lưu của runner.
- Cục bộ đạt 86 pytest, 100 test Node, 14 test kế hoạch và Ruff/ty. Ca HTTP chạy tạo → SSE → xác nhận với SQLite tạm và adapter Ollama qua HTTP giả lập. Có ca từ chối nguồn người khác, payload giả, thiếu đồng ý, sai phiên bản và đổi nguồn trong lúc AI xử lý.
- [Hợp đồng](../contracts/ai.md) bàn giao cho BE-2, BE-4 và UI-3. Bên lý thuyết có thể dùng ca kỹ thuật cho SourceRef, quyền và CT-04/05/06. Cần ghép phiên thật, repository của nhóm, giao diện, khôi phục job và chạy model thật. Không dùng số ca kiểm này thay kết quả PoC.


<!-- ban-giao-smoke-ollama-39 -->
### 11/11/2026 — kiểm nhanh AI với Ollama thật trên laptop

- [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) thêm [bộ kiểm Sinh, Sửa, Kiểm](../testing/KIEM_NHANH_AI.md) dùng chung dữ liệu mẫu. Mặc định 3/3 fixture đạt. Toàn bộ đạt 89 pytest, 100 test Node, 14 test kế hoạch và Ruff/ty cục bộ.
- Ollama 0.40.16 chạy CPU, cloud tắt, dữ liệu synthetic. Qwen2.5 1.5B đạt 0/3. Qwen2.5 3B đạt 1/3 ở Kiểm. Cả hai bị chặn khi sửa ngoài vùng hoặc sinh đáp án trắc nghiệm sai kiểu. Đã lưu thời gian từng ca và digest trong bảng kết quả/JUnit. Tiến trình thử đã dừng.
- Bên lý thuyết có thể dẫn phép đo này làm bằng chứng adapter và các lớp kiểm, tách với 48 lượt PoC. Chưa chốt model mặc định. Cần xử lý hai lỗi ở Sửa/Sinh và kiểm tích hợp tới lưu với model thật. Kết quả không thuộc đợt diễn tập GreenNode.


<!-- ban-giao-rang-buoc-ollama-39 -->
### 11/11/2026 — sửa phạm vi Ollama và kiểm đến bước lưu

- [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) giới hạn dữ liệu gửi Ollama ở đoạn chọn của từng khối rồi Python ghép lại. Schema Sinh ràng buộc thông tin ma trận và kiểu đáp án. DTO đề xuất ra API giữ toàn văn khối sau khi ghép.
- [Kết quả đo](../testing/KIEM_NHANH_AI.md): Qwen2.5 3B đạt 3/3 ca Sinh/Sửa/Kiểm, đạt thêm ca model thật qua FastAPI và SQLite tạm tới xác nhận lưu. Đề giữ nguyên trước xác nhận. Sau xác nhận có đúng một lịch sử, tăng revision và phiên bản câu, giữ công thức và câu khác. 1.5B qua Sửa, còn lệch barem và bất đồng đáp án. Cục bộ 93 pytest đạt, 1 ca model thật bỏ qua mặc định, 100 test Node, 14 test kế hoạch và Ruff/ty đạt.
- Có thể dùng ca lưu làm bằng chứng kỹ thuật cho phạm vi sửa và xác nhận ở CT-03/04/05/06. Kết quả dùng dữ liệu mẫu và phiên giả lập. Cần ghép UI, kho thật, kiểm hủy model thật và nghiệm thu GreenNode riêng.


<!-- ban-giao-huy-ollama-that-39 -->
### 11/11/2026 — kiểm hủy và chạy lại với Ollama thật

- [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) bổ sung ca opt-in hủy sau khi đã gửi request HTTP tới Qwen2.5 3B cục bộ. Tài khoản khác nhận 404. Hủy đúng phiên đóng kết nối phía app, SSE chỉ phát lại một sự kiện cuối, xác nhận job hủy trả 404. Giới hạn một suất vẫn nhận yêu cầu mới tới bản xem trước.
- Đề mẫu giữ revision 4 và 0 lịch sử. [Cách chạy và số đo](../testing/KIEM_NHANH_AI.md) ghi đóng HTTP phía app 5,180 ms, tổng 28,010 giây gồm ca chạy lại. 93 pytest đạt, hai ca thật bỏ qua mặc định. 100 test Node, 14 test kế hoạch và Ruff/ty đạt cục bộ.
- Bằng chứng bổ sung W04 #12, W03/T02 #16, #20 và #24. Phép thử dùng phiên giả lập và SQLite tạm. Thời điểm Ollama ngừng tính toán, phục hồi qua khởi động lại, UI/kho thật và GreenNode cần kiểm riêng.


<!-- ban-giao-check-api-39 -->
### 11/11/2026 — API Kiểm đáp án đọc câu từ kho

- [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) thêm route POST kiểm đáp án theo đề/câu. Python đọc snapshot bằng phiên và tham chiếu nguồn, giữ đáp án lưu ngoài payload model, rồi so kết quả giải độc lập. Kiểm lại câu, nguồn và đáp án hiện hành trước khi trả. Route chỉ đọc.
- Cục bộ đạt 123 pytest, ba ca model thật bỏ qua mặc định, 100 test Node, 14 test kế hoạch và Ruff/ty. 30 ca mới kiểm quyền/consent, nguồn giả, lệch phiên bản giữa chừng, giới hạn đồng thời, timeout/hủy và lỗi provider được lược nội dung. Ca HTTP thật với Qwen2.5 3B đạt trong 35,099 giây, báo bất đồng với đáp án mẫu cố ý sai và giữ nguyên kho.
- BE-2 ghép phiên, BE-3 cung cấp reader theo hợp đồng, UI-3 nhận comparison/căn cứ. [Hợp đồng](../contracts/ai.md), [cách chạy](../testing/KIEM_NHANH_AI.md). Bên lý thuyết có thể dẫn ca HTTP/model thật làm bằng chứng kỹ thuật CT-03/04/05/06. Ca này dùng phiên giả lập, SQLite tạm. Cần kiểm giao diện và kho thật khi tích hợp.

<!-- ban-giao-generation-confirm-39 -->
### 11/11/2026 — xác nhận lưu bộ câu mới theo ma trận đã duyệt

- PR #39 bổ sung `prepare_generation`, `PendingGeneration` và xác nhận Sinh bằng cùng route với Sửa. Trong giao dịch, backend kiểm revision, nguồn, chủ sở hữu và ma trận đã duyệt. Sau xác nhận mới thay bộ câu, cấp UUID, đặt phiên bản 1 và trạng thái chờ kiểm/duyệt; giữ tiêu đề, thiết lập trang và bản đề cũ trong lịch sử. Xác nhận đồng thời hoặc gửi lại trả cùng UUID, lỗi ghi rollback.
- 134 pytest đạt, bốn ca model thật bỏ qua mặc định; Ruff, format và ty đạt. Bộ Node và kế hoạch giữ kết quả 100/14 đạt trong lượt chuẩn bị cùng thay đổi. Các ca SQLite tạm kiểm bốn dạng câu, ma trận chưa duyệt/đổi, nguồn/revision đổi, đề khóa, hủy, rollback và mở lại biên nhận bằng repository mới.
- Model 3B ban đầu bị chặn vì barem lệch. Sau khi làm rõ đơn vị và tổng điểm trong yêu cầu, Qwen2.5 3B thật qua Sinh → xem trước → xác nhận HTTP trong 44,699 giây. Python vẫn kiểm điểm, không tự sửa điểm model. Lệnh và kết quả có trong docs/testing/KIEM_NHANH_AI.md. Đây là một ca cấu trúc/lưu trữ, chưa là chấm chất lượng hay tỷ lệ ổn định đa môn.
- Bàn giao API/repository/UI theo #12, #13, #14 và #11. Kho thật cần đọc `approved_plan` trong giao dịch và lưu lịch sử/biên nhận; UI cần luồng duyệt ma trận, tạo job và xem trước toàn bộ bộ câu thay thế. Chưa ghép phiên/kho/UI thật, chưa triển khai GreenNode, PR còn chờ review. Bên lý thuyết chỉ dẫn phần đã kiểm như bằng chứng kỹ thuật CT-03/04/05/06.

<!-- ban-giao-generation-request-39 -->
### 11/11/2026 — tạo tác vụ Sinh từ request HTTP

- PR #39 bổ sung route POST /api/exams/{exam_id}/proposals/generate. Python đọc đề/ma trận/nguồn theo phiên, đối chiếu ma trận đang xem với bản đã duyệt trước khi gọi model. Không nhận nội dung nguồn, owner hoặc jobId từ trình duyệt. Dùng chung runner, hạn mức, trạng thái/SSE/hủy và xác nhận với Sửa; requestId lặp trả cùng job, dùng cho nội dung/thao tác khác báo xung đột.
- 158 pytest đạt, năm ca model thật bỏ qua mặc định; Ruff/format/ty, 100 test Node và 14 test kế hoạch đạt. 24 ca mới kiểm bốn dạng câu qua HTTP tới lưu, quyền, payload giả, nguồn chọn, ma trận đổi trước/trong lúc chạy, replay, hủy/quá hạn và chặn kết quả muộn. Các ca mặc định dùng SQLite tạm và model giả lập.
- Qwen2.5 3B thật qua request HTTP tạo job → SSE → xem trước → xác nhận lưu trong 52,066 giây, cùng digest/runtime/cấu hình ghi ở docs/testing/KIEM_NHANH_AI.md. Đề không đổi trước xác nhận, gửi lại xác nhận trả cùng biên nhận. Một ca mẫu không thay kết quả PoC A/B hoặc chấm nội dung đa môn. Tiến trình Ollama thử nghiệm đã dừng.
- BE-2 ghép dependency phiên; BE-3 cung cấp ReadGenerationInputs/snapshot ma trận đã duyệt và transaction; UI-3 nối luồng duyệt ma trận, request, preview và confirm. BE-5 dùng chung event/cancel nhưng còn cần kho job bền vững/restart. Hợp đồng và ca kiểm có trong PR; main chưa mount các router này, chưa ghép UI/kho thật, chưa triển khai GreenNode. PR còn chờ review.

<!-- ban-giao-math-structure-39 -->
### 11/11/2026 — chặn công thức thiếu ngoặc hoặc lệch môi trường

- PR #39 bổ sung bộ kiểm cấu trúc LaTeX dùng chung cho Sinh/Sửa/Kiểm và xác nhận. Đã tái hiện 10 ca công thức lỗi từng lọt qua kiểm cặp dấu. Sau sửa, Python kiểm ngoặc nhóm và thứ tự/tên begin/end, giữ ký hiệu escape, verb, chú thích và ngoặc ngoài công thức. Không thêm dependency hoặc chuyển xử lý sang Node.
- 188 pytest đạt, năm ca model thật bỏ qua mặc định; 101 test Node, 14 test kế hoạch, uv sync frozen và Ruff/format/ty đạt. Fixture 17 ca chung đối chiếu với renderer Node; các ca service và xác nhận chặn công thức lỗi, không ghi đề/lịch sử. Phép kiểm cục bộ đọc danh mục hiện hành cho 457 công thức/mẫu dựng mặc định đều qua cấu trúc Python.
- Bàn giao W03/W05 #12, editor #10, nhập/xuất #15 và QA #24. Đây là kiểm cấu trúc, chưa là parser đầy đủ mọi lệnh/đối số, khả năng render hoặc độ đúng toán học. UI/BE-4 vẫn kiểm renderer/xuất riêng. Lượt này không chạy AI thật/GreenNode, không thay số liệu PoC; PR đang chờ review và chưa ghép phiên/kho/UI thật.

<!-- ban-giao-ci-chrome-va-review-db -->
### 11/11/2026 — sửa bước chuẩn bị trình duyệt CI và review hợp đồng database

- Run 43044002628 của bc33bf1 kết thúc lỗi ở bước cài Chromium/font qua apt: DNS không phân giải kho Ubuntu; Python đã success. Đã yêu cầu rerun-failed-jobs đúng một lần, chưa lấy lỗi môi trường làm kết quả test Node. Workflow được sửa để job Node dùng ubuntu-24.04 và Chrome cài sẵn được kiểm đường dẫn/version, giữ nguyên bộ test PDF và BROWSER_PATH. Cần kiểm run của commit mới trước khi kết luận sửa xong.
- Đã đọc PR #38 tại 6c03ced và ghi phản hồi ở PR #38 / task #6, giữ nguyên checklist, assignee và status. Ba mục: đưa bộ DDL/migration/fixture/log vào repo để chạy lại số đo T01–T03; làm rõ giữ QuestionVersion khi Sinh thay bộ câu; lưu đủ loại thao tác/fingerprint để chặn dùng lại requestId cho nội dung khác sau restart. Tài liệu đã đối chiếu contract AI nhưng hiện PR chỉ có Markdown, chưa có code/bộ chạy để xác minh migration. Đây là review đề xuất, không phải nghiệm thu kết quả của thành viên.
- Bên lý thuyết chỉ dùng các kiểm chứng đã có source/log tương ứng; chưa đưa số đo migration từ tài liệu thành kết quả được bên thực hành tái lập. Không thao tác GreenNode hoặc dữ liệu thật.
