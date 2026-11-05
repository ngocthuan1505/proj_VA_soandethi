# Bàn giao: xây app và kiểm thử

Cập nhật: 05/11/2026.

## Hiện trạng đã kiểm

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
