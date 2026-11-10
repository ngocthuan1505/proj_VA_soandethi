# Bàn giao: xây app và kiểm thử

Cập nhật: 10/11/2026.

## Hiện trạng đã kiểm

- 10/11 (BE-3): Hoàn tất đặc tả kỹ thuật và kiểm chứng thực nghiệm cho task `BE-3-001` tại [Hợp đồng dữ liệu (`docs/contracts/du-lieu.md`)](../contracts/du-lieu.md) và đồng bộ [Kế hoạch dữ liệu (`docs/architecture/DATA_PLAN.md`)](../architecture/DATA_PLAN.md):
  - **W01–W04**: Kiểm kê đủ 12 nhóm key/prefix trong SQLite KV cũ; đối chiếu chính xác tên trường thực tế từ `core.js`/`blocks.js`/`mvp.js` (`q.richDoc`, `q.optionDocs`, `q.blockIds`, `exam.data`, `exam.history`, `points_q4` nguyên); lập ERD và Data Dictionary 15 bảng tách 3 trạng thái (`draft_status`, `verification_status`, `approval_status`), khóa chính kép `(owner_id, id)` cho `source_documents`, `ON DELETE SET NULL` cho `ai_jobs`/`share_snapshots` khi đề gốc đã xóa; chốt ADR-001 dùng `sqlite3` stdlib WAL mode (chưa thêm dependency vào `backend/pyproject.toml`); thiết kế 8 Python Repository Contracts theo đúng khuôn mẫu 9 mục của `docs/course/CONTRACTS.md`.
  - **W05 & Bằng chứng thực nghiệm T01–T03**: Chạy kiểm chứng thực tế trên Node `backend-store.mjs` và Python `3.12.10` (`sqlite3` `3.49.1`) với bộ fixture 18 bản ghi KV sạch (đủ 12 prefix) và 2 bản ghi KV hỏng: `T01` khớp 100% SHA-256 canonical JSON trước-sau di trú (`user_a`: `75fe5228...`, `user_b`: `51e480ea...`, `foreign_key_check=0`, `integrity_check=ok`); `T02` cô lập đúng 2 bản ghi lỗi vào `migration_quarantine`, rollback nguyên tử giữ nguyên 20 dòng `kv` khi giả lập lỗi I/O, và `conn.backup()` đạt; `T03` chạy lại migration lần 2 giữ nguyên số dòng (`idempotent_equal=true`) và bắt đúng `RevisionConflictError` (`409 Conflict`). Đây là thiết kế/hợp đồng M1 (`BE-3-001`) đã có bằng chứng kiểm thử thực nghiệm trên fixture; việc gắn repository vào route FastAPI thuộc `BE-3-002`/`BE-3-003` ở M2/M3.

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
