# Thử app và phát hành bản mới

[Trang kiểm thử #47](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/47) là nơi cả nhóm nhận bản mới, chọn ca kiểm và báo kết quả.

## Tester

1. Đăng nhập GitHub bằng tài khoản đã nhận lời mời repo. Mở #47 và bấm link bản mới nhất, hoặc xem [Releases](https://github.com/ngocthuan1505/proj_VA_soandethi/releases). Trong **Assets**, tải tệp `SoanDeThi-UngVien-<số>.zip`. Bản ZIP này có sẵn tệp chạy Windows.
2. Giải nén vào thư mục mới. Cài [uv](https://docs.astral.sh/uv/getting-started/installation/) một lần rồi mở `CHAY_THU_NHOM.cmd`. Lần đầu cần Internet để cài Python và thư viện. Khi CMD báo **Application startup complete**, mở [app tại máy](http://127.0.0.1:4182/) và giữ cửa sổ CMD mở. Trong ZIP có `HUONG_DAN_TEST_NHOM.md` cho chế độ tài khoản và demo ghi log.
3. Thử T01 ở #47 trước: tạo đề, lưu và mở lại. Có thể thử công thức, hoàn tác và xuất Word/PDF trước khi cấu hình AI. Khi thử ca sinh đề, chọn kết nối đã được phép trong **Kết nối** và dùng ngữ liệu tự viết.
4. Ghi **bản · mã ca · Windows/trình duyệt · Đạt/Lỗi** ở #47. Khi phát hiện lỗi, dùng [mẫu báo lỗi](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=bug.md) hoặc bình luận vào issue cũ nếu trùng, kèm các bước, mong đợi, thực tế và ảnh/log đã loại thông tin riêng.
5. Bấm **Subscribe** ở #47 để nhận thông báo khi có bình luận phát hành. Khi được nhờ thử lại, tải đúng bản và báo ngay trên issue lỗi, ví dụ `Bản 48 · T03 · Windows 11 / Chrome · Đạt`.

## Người sửa app

1. Tái hiện lỗi từ issue, sửa trên nhánh của mình rồi mở PR. Ghi `Refs #52` (thay 52 bằng số lỗi thật), cách kiểm và kết quả. Khi CI xanh, mở danh sách commit của PR và chép SHA đầy đủ của commit cần đóng gói. Chọn commit có bộ chạy Python và `scripts/dong-goi-ban-thu.py`.
2. Người có quyền ghi mở [Actions → Phát hành bản thử](https://github.com/ngocthuan1505/proj_VA_soandethi/actions/workflows/phat-hanh-ban-thu.yml) → **Run workflow**. Giữ nhánh chạy là `main`. Nhập `so_ban` (ví dụ 48), `commit` (SHA 40 ký tự) và `ghi_chu` (lỗi đã sửa, ca cần thử lại và lỗi đã biết).
3. Lượt đầu để trống ô **Xuất bản cho nhóm**. Tải gói từ **Artifacts** của lượt chạy, giải nén, mở app và thử ca vừa sửa. Sau khi đạt, chạy lại cùng số bản và SHA, lần này đánh dấu **Xuất bản cho nhóm**. Workflow kiểm CI của đúng SHA, đóng ZIP, kiểm SHA-256, tạo pre-release và bình luận link ở #47.
4. Dán link bản vào issue lỗi gốc và nhờ tester thử đúng số bản. Khi tester xác nhận đạt, ghi kết quả rồi đóng issue. Nếu còn lỗi, tiếp tục trong issue đó.

Nếu bước đóng ZIP lỗi, mở log của lượt chạy. Nếu Release đã xuất hiện nhưng bước **Báo bản mới** lỗi, dùng **Re-run failed jobs** trên lượt đó để thử lại thông báo. Các bản đã phát dùng để đối chiếu lỗi theo số bản. Dùng số mới khi thay đổi nội dung ZIP.
