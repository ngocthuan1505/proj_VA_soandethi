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
