# Nhận việc, báo tiến độ, báo vướng và nghiệm thu

**Cách nhận việc mới:** [nghiên cứu rồi tự chọn cá nhân/nhóm](CHON_VIEC.md). Mã mảng không phải người; báo thành viên và chia Wxx/code/test/review khi làm chung.


Issue gốc là nơi giữ acceptance và thảo luận; **Status trên Project** là nguồn tiến độ. Không lấy số commit, số dòng code hoặc phần trăm tự khai làm bằng chứng hoàn thành.

**Mở ngay:** [Nhật ký tiến độ chung #32](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/32) · [Báo cáo tiến độ](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+label%3Atype%3Aprogress) · [Vướng mắc đang mở](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+is%3Aopen+label%3Atype%3Ablocker) · [Đề nghị nghiệm thu đang mở](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+is%3Aopen+label%3Atype%3Acompletion).

## Mỗi người bắt đầu trong một buổi

1. Đọc [hướng dẫn nhóm](README.md), [phân công](ROLES.md), [yêu cầu môn](../course/README.md). Chạy baseline local theo README; ghi lỗi môi trường nếu có, không chờ GreenNode để làm UI/API/DB/fixture.
2. Mở task `001` của vai trò đã thống nhất. Đọc **Đầu vào / Bước làm / Đầu ra / Reviewer / Tiêu chí nghiệm thu**; bình luận nhận việc và hẹn người giữ file chung. Chỉ assign khi đã được cấp quyền; không nhận hai vai trò thay cho người chưa có username.
3. Chọn một bước nhỏ, tạo nhánh, đưa thẻ sang Đang làm. Nếu bước hơn khoảng một ngày, tạo task con, liên kết cha/phụ thuộc và thêm lên bảng.
4. Làm PR nhỏ có bằng chứng; cập nhật cuối buổi làm hoặc ngay khi cần phối hợp. Nhịp cuối buổi là quy ước nhóm đề xuất, không phải lịch nộp của giảng viên.

## Chọn đúng chỗ ghi

| Tình huống | Nơi dùng | Việc tiếp theo |
|---|---|---|
| Cập nhật nhỏ hằng buổi | Bình luận trong issue task bằng mẫu bên dưới | Sửa Status nếu thay đổi; người theo dõi Subscribe issue |
| Muốn báo cáo có ô điền rõ ràng | [Mẫu cập nhật tiến độ](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=tien_do.yml) | Ghi số task gốc, rồi dán link báo cáo vào task |
| Không tiếp tục được/cần người hỗ trợ | [Mẫu báo vướng mắc](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=vuong_mac.yml) | Thẻ gốc sang Bị chặn, nêu ai cần quyết định, việc vẫn làm được |
| Đã có đầu ra để người khác duyệt | [Mẫu đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=nghiem_thu.yml) hoặc PR đủ nội dung tương đương | Thẻ gốc sang Chờ duyệt; reviewer chấp nhận mới đóng/Hoàn thành |
| Lỗi tái hiện độc lập | Mẫu Báo lỗi ở Issues → New issue | Liên kết task, fixture/commit và mức ảnh hưởng |
| Tổng hợp một tuần/một vòng | Bình luận ở issue **Nhật ký tiến độ chung** | Mỗi vai trò một dòng với link; không sao chép toàn bộ báo cáo cá nhân |

Forms tạo **issue báo cáo riêng** để lọc/tìm dễ hơn; không tạo task mới thay task gốc. Số issue báo cáo không được cộng vào số task hoàn thành. Chọn một cách đủ cho mỗi lần cập nhật, không bắt thành viên vừa viết form vừa chép lại toàn bộ comment. Chỉ dán link đối ứng khi cần.

Không có bot tự chuyển Status, đồng bộ nhãn hay gửi thông báo tới mọi thành viên. GitHub thông báo theo Subscribe/mention và cài đặt cá nhân; người lập report cần nhắc đúng reviewer đã biết, không bịa username.

## Mẫu comment tiến độ

Ghi cả mã bước/ca của task (ví dụ `UI-2-002/W03`, `UI-2-002/T02`) và expected/actual. Một Wxx đã xong không tự đóng cả task. Đính kèm artifact và xác nhận bên nhận bàn giao; chưa tích hợp/model thật/chưa test phải ghi rõ. Xem [gates và cách chia PR](KE_HOACH_TICH_HOP.md).

```text
Vai trò / task: UI-2 / #2
Ngày, buổi làm:
Đã làm: đầu ra cụ thể...
Bằng chứng: link PR/commit/ảnh/test...
Còn lại: bước cụ thể tiếp theo...
Đang vướng: không / vấn đề + đã thử + cần ai giúp...
Trạng thái đề nghị: Đang làm / Bị chặn / Chờ duyệt
```

## Khi bị chặn

Ghi kỳ vọng/thực tế, lỗi đã che thông tin riêng, cách tái hiện với fixture, việc đã thử, phụ thuộc cần chốt và người/vai trò cần hỗ trợ. Báo ngay khi biết, không đợi tới buổi họp. Chỉ đánh dấu phần bị chặn: thiếu server model thật không ngăn viết contract, parser, fixture hoặc test local. Gỡ chặn xong ghi quyết định và link bằng chứng rồi chuyển Sẵn sàng/Đang làm.

## Khi đề nghị hoàn thành

Người làm đối chiếu từng acceptance và đính kèm PR/commit, lệnh + kết quả test, ảnh/video UI nếu cần, đầu ra CT, giới hạn và migration/rollback nếu liên quan. **Đề nghị nghiệm thu chưa phải hoàn thành.** Reviewer xem code/kết quả, kiểm lại phần rủi ro và ghi chấp nhận hoặc yêu cầu sửa. PR đạt CI và được duyệt mới merge/đóng task theo quy ước nhóm. Issue báo cáo được đóng sau khi xử lý; không thay việc đóng task gốc.

Mỗi phần CT có [issue riêng](../course/github-issues.json) và khung báo cáo. Nếu thiếu phỏng vấn/model thật/test người dùng, giữ ô đó chưa đạt; không ghi “pass” vì demo fixture chạy được.

## Mẫu tổng hợp cuối tuần/vòng

```text
Kỳ báo cáo: [từ ... đến ...] — [người tổng hợp]
UI-1: task / status / đầu ra + link / vướng / bước tiếp
UI-2: ...
UI-3: ...
BE-1 (Thuận): ...
BE-2: ...
BE-3: ...
BE-4: ...
BE-5: ...
Quyết định chung cần chốt: ...
CT/PoC/test đã có bằng chứng: ...
Giữ / sửa / bỏ ở vòng sau, lý do: ...
```

Không tự lập lịch nhắc qua email/chat hoặc Actions cron. Sau khi có đủ username, Thuận cấp quyền repo và Project; nhóm chốt lịch họp/ngày nộp. Giữ khóa, URL server riêng, thông tin người dùng và tài liệu chưa được phép ngoài GitHub.
