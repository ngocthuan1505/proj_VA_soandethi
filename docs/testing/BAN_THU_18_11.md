# Bản thử 18/11 và đối chiếu nghiệm thu MVP

Bản tích hợp Python tại máy. Gói thử được tạo từ working tree ngày 18/11, kèm manifest SHA-256. Các use case và mã IT đối chiếu với [kế hoạch kiểm tích hợp](KIEM_THU_TICH_HOP.md) và [kết quả ứng viên 13](NGHIEM_THU_BAN_13.md). Cột cuối ghi các phần còn thiếu bằng chứng nghiệm thu trên cùng bản.

| Ca | Bằng chứng đã có | Cần kiểm tiếp |
| --- | --- | --- |
| IT-01 Tài khoản và kho riêng | Pytest chế độ nhóm với hai tài khoản và khách. Gói sạch mở trang đăng nhập và khởi tạo lời mời local. | Lặp hành trình CRUD và hết phiên trên browser cho bản đóng gói. |
| IT-02 Nhập nguồn và ma trận | Gói sạch đọc CSV năm câu tại máy. Có bằng chứng API/UI trước đó cho DOCX/XLSX/PDF/ảnh và sửa văn bản nguồn. | Bảng gộp phức tạp, chất lượng OCR thật và nghiệm thu ký hiệu trên bộ mẫu. |
| IT-03 Cấu trúc đề | Có kiểm cơ cấu gợi ý, ma trận bốn mức, bốn loại, tới 30 câu hoặc ý và tổng điểm. | Nghiệm thu các mẫu đề dài và cơ cấu chuyên môn theo từng môn. |
| IT-04 Sinh và tự kiểm | Đã có một lượt Gemini hỗn hợp bốn dạng và các lượt tự sửa Sinh học trước đó, cộng fixture lỗi/timeout/dự phòng. | Lượt hỗn hợp dài từ file và bằng chứng tích hợp đầy đủ trên bản thử mới. |
| IT-05 Biên tập trực quan | Có renderer công thức, trình soạn rich, các kiểm riêng lưu/undo và bản xuất. | Rà một hành trình rich lớn với IME, nhiều trang và thiết bị thực. |
| IT-06 Sửa theo phạm vi | Các ca bôi đen, diff, chấp nhận, bỏ và undo cho vùng chữ và bốn dạng câu đã có trước đó. | Phạm vi sửa hình/bảng và hành trình liên kết dữ kiện. |
| IT-07 Kiểm và duyệt | Có luồng giải lại, kết quả kiểm, duyệt giáo viên và kiểm vô hiệu hóa khi đổi câu. | Mở rộng đánh giá phần hình, lời giải/barem và chuyên môn độc lập. |
| IT-08 Dữ kiện liên kết | Chrome trên kho thử đã kiểm bảng, biểu đồ, HTML xuất, tải lại, hoàn tác và khước từ lưu từ phiên cũ. Test lỗi giữa bước rà giữ nguyên cả cụm. | Kiểm tiếp cách liên kết dữ kiện với hình và bảng tự tạo ngoài mẫu. |
| IT-09 Phiên bản nguồn | Có sửa văn bản trích xuất và đánh dấu kết quả kiểm cần rà khi phiên bản đổi. | Nghiệm thu phiên bản A/B cùng câu, ID nguồn, locator, quyền và đối chiếu bản gốc. |
| IT-10 Xuất và chia sẻ | Gói sạch tạo bốn file Word/PDF, đã đọc PDF và XML Word để đối chiếu lời giải chỉ ở bản giáo viên và phân số OMML. Trước đó có kiểm quyền và thu hồi snapshot. | Hành trình gộp tài khoản, rich dài, file tải thực tế, chia sẻ và thu hồi trên cùng bản. |
| IT-11 Lưu và khôi phục | Bản sao qua preview/confirm và CAS. Kiểm rollback khi ghi tệp lỗi, file gốc dùng trong lịch sử, UUID và rich, hai owner và khách, desktop/mobile và JSON hỏng. Có bằng chứng riêng cho offline/cancel/reload. | Diễn tập chuyển kho PoC sang tài khoản và rollback migration trên bản sao, cùng các ca ngắt mạng sát xác nhận. |

## Bằng chứng ngày 18/11

- `outputs/mvp-18-11/restore-ui/result.json` và hai ảnh preview ghi bốn ca Chrome trên kho nhóm thử.
- `outputs/mvp-18-11/phat-hanh-thu/archive-browser.json`, `archive-team.json`, `archive-export-check.json` có kết quả trên thư mục giải nén mới. Bộ production cài 21 gói từ cache theo `uv.lock`. Thử gói ở Windows, cài lần đầu trên máy thành viên vẫn phụ thuộc mạng.
- `outputs/mvp-18-11/main-after.json` xác nhận app chính mở trên cổng 4182 với 31 đề, revision 318 và băm dữ liệu/kết nối khớp bản sao trước khi mở.
- Bản ZIP có kiểm tra CRC, SHA-256, 209 tệp source/tài nguyên và kiểm mẫu khóa/host trên 113 tệp văn bản. App 4182 được bật trước lần bổ sung kiểm số JSON ngoài phạm vi. Gói ZIP có lần bổ sung này.
- `npm ci --offline` trên thư mục build mới cài 98 gói. Hồi quy Node và kiểm nhóm đạt 124 và 14 ca trên worktree.
- Python đạt 619 ca, bỏ qua 5 ca model, 2 subtest đạt và một cảnh báo deprecation từ Starlette. Ruff, format và ty đạt. `pytest-final.log` giữ kết quả đầy đủ.
- `sqlite-restore-drill.json` ghi diễn tập backup SQLite sang kho riêng, kiểm tính toàn vẹn và đối chiếu UUID, revision, rich document và ảnh. Đây là backup/restore cùng schema.
- Sau khi đóng ZIP này, app 4182 đã dùng renderer chung cho cả hai phía của màn sửa thủ công. Hành trình Chrome và ảnh mobile nằm ở `outputs/mvp-18-11/manual`.
- Đối chiếu kỹ thuật phục vụ CT-04 và CT-06. Kết luận về sư phạm và báo cáo của nhóm cần bằng chứng riêng. Mục tiêu MVP còn mở.
