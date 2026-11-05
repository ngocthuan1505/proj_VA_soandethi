# Nhóm thành viên và các mảng việc tự chọn

Thuận xác nhận ngày 05/11/2026: **chỉ chốt nhóm UI/backend, chưa gán cứng chuyên môn từng người**. Nghiên cứu rồi đăng ký cá nhân hoặc làm chung theo [menu chọn việc](CHON_VIEC.md).

| Nhóm đã chốt | Thành viên |
|---|---|
| UI | [@lamngoc25032007-netizen](https://github.com/lamngoc25032007-netizen), [@Mysthaps](https://github.com/Mysthaps), [@PhuQuang0307](https://github.com/PhuQuang0307) |
| Backend | [@ngocthuan1505](https://github.com/ngocthuan1505), [@fiiwk21](https://github.com/fiiwk21), [@2512716757-source](https://github.com/2512716757-source), [@cyan-cpu](https://github.com/cyan-cpu), [@shin-hybrid](https://github.com/shin-hybrid) |

Danh tính nằm trong [members.json](members.json). Đã có quyền repo/Project không có nghĩa đã nhận task. Ba bạn UI có thể cùng làm một mảng/luồng, chia theo Wxx/PR hoặc luân phiên code/test/review; backend cũng có thể cộng tác giữa các mảng.

## Mã mảng không phải tên người

UI-1 là shell/kho; UI-2 editor; UI-3 trợ lý; BE-1 AI; BE-2 API/auth; BE-3 dữ liệu; BE-4 tài liệu; BE-5 job/QA. Giữ các mã/nhãn cũ để task và phụ thuộc không hỏng. **Không đọc UI-1 là lamngoc, UI-2 là Mysthaps hoặc BE-5 là shin-hybrid.** Menu nêu mục tiêu/source/test/đầu ra để mọi người tự cân nhắc.

`roster.json` giữ cấu trúc tương thích công cụ cũ: các vị trí chuyên môn để trống; BE-1 còn tên Thuận để nhận diện chủ vận hành GreenNode. Đây **không phải danh sách người nhận task**. Công cụ đồng bộ không tự gán người từ roster; người thực hiện thực tế xem comment đăng ký và Assignees trên issue, có thể nhiều người.

## Ranh giới giữ nguyên

- Chỉ Thuận thao tác GreenNode. Các bạn vẫn có thể làm AI/worker/runbook local rồi gửi PR.
- Nhóm đang nhận một mảng chọn đầu mối contract và bàn giao với consumer; không tự suy username từ mã mảng.
- File chung phải hẹn trong issue; làm chung ghi ai làm Wxx nào, đầu mối PR, người test/review. Không đè thay đổi của nhau.
- Reviewer là người khác người thực hiện. Mảng reviewer trong task là gợi ý nơi cần tham khảo, không gán cứng username. Server cần Thuận review.
- CT-01…06 là việc chung, dùng lại proposal/decomposition/abstraction và ghi đóng góp thực. Không gán ngược công lao cũ.

Chưa chọn thì task mở để đăng ký. Các mốc, acceptance, test và phụ thuộc vẫn giữ để biết lựa chọn dẫn tới đầu ra gì; chọn mảng không tự đổi Status hoặc hoàn thành task.
