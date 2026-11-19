# Phát hành bản thử cho nhóm

[Trang kiểm thử ghim #47](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/47) là điểm bắt đầu. [Releases](https://github.com/ngocthuan1505/proj_VA_soandethi/releases) giữ lịch sử bản cài. [Issues](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+is%3Aopen+label%3Atype%3Abug) giữ lỗi và kết quả thử lại.

## Tester

1. Theo link bản thử ở #47, tải ZIP bên dưới Assets và giải nén vào thư mục mới. Mở `CHAY_THU_NHOM.cmd` hoặc đọc `HUONG_DAN_TEST_NHOM.md` trong ZIP nếu máy chưa có uv. Lỗi ở bản cũ vẫn đối chiếu theo số bản cũ.
2. Chọn ca chưa ai thử trong ma trận #47. Báo kết quả theo mẫu **bản · mã ca · Windows/trình duyệt · Đạt/Lỗi/Chưa test**. Khi có lỗi, dùng [mẫu báo lỗi](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=bug.md) hoặc ghi thêm vào issue trùng.
3. Bật **Watch → Custom → Releases** trong repo để nhận thông báo bản mới. Theo dõi issue của mình để nhận yêu cầu thử lại.

## Nhóm sửa app

1. Nhận issue và tái hiện. Ghi kết quả, mở PR hoặc liên kết commit sửa với issue. Nếu PR được merge trước khi tester xác nhận, dùng liên kết `Refs #...` để issue còn mở cho bước thử lại.
2. Khi có phần sửa hoặc tính năng đáng để nhóm thử, chọn số bản mới và đúng SHA mà nhóm muốn kiểm. Kiểm bản đóng gói, mở app và chạy ca thay đổi bằng dữ liệu mẫu. Từ checkout sạch có script đóng gói của app, chạy:

   ```powershell
   python scripts/dong-goi-ban-thu.py --ung-vien 48
   Get-FileHash outputs/ung-vien-48/SoanDeThi-UngVien-48.zip -Algorithm SHA256
   ```

   Số 48 là ví dụ. Gói đóng từ mã nguồn của checkout này, nên đối chiếu `git rev-parse HEAD` và `git status --porcelain` trước khi đóng. ZIP chỉ chứa source và tài nguyên nằm trong danh sách đóng gói.
3. Mở **Releases → Draft a new release**, tạo tag `ban-thu-<số>` từ đúng commit rồi chọn **pre-release**. Nếu dùng GitHub CLI, có thể đặt chính xác SHA bằng tham số `--target <SHA>`. Đính kèm ZIP và `.sha256`. Mô tả phần mới, ca cần test, issue cần thử lại và lỗi đã biết. Xuất bản khi cả hai tệp đã tải lên.
4. Cập nhật đường dẫn bản đang thử ở đầu #47, rồi bình luận một dòng gồm số bản, link tải và các mã ca cần thử lại để người đã Subscribe nhận tin. Ghi số bản vào các issue cần thử lại. Khi tester xác nhận trên đúng bản, ghi kết quả và đóng issue nếu các tiêu chí của nó đã đạt. Nếu lỗi còn, giữ issue mở và bổ sung cách tái hiện.

Chỉ người có quyền ghi repo phát hành bản thử. Giữ repo riêng tư và chỉ chia sẻ dữ liệu mẫu cùng bản cài. Bản thử và trạng thái nghiệm thu Final có tiêu chí riêng.
