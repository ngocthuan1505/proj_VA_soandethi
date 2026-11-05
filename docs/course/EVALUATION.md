# Kiểm thử và đánh giá phản biện

**Baseline kỹ thuật đã chạy 05/11/2026:** xem [kết quả demo kế thừa](../testing/BASELINE_2026_11_05.md), [chức năng/giới hạn](../product/DEMO_DA_CO.md) và [cách thành viên tự test](../team/CHAY_VA_TEST_DEMO.md). Đã có regression fixture; chưa có thử nghiệm giáo viên hoặc số đo chất lượng AI. Không lấy kết quả kỹ thuật này thay phần đánh giá người dùng dưới đây.

Nguồn: Topic 6 trang 17–24, 26–30, 32. Đây là kế hoạch chưa có dữ liệu thực nghiệm. BE-5 tổng hợp, từng vai trò thực hiện test phần mình; người đánh giá độc lập review kết luận.

## Bốn loại bằng chứng

| Loại | Câu hỏi với Mạch | Cách thu thập dự kiến |
|---|---|---|
| Giá trị/khái niệm | Giáo viên có tiết kiệm công sức ở bước họ thực sự gặp khó không? | Phỏng vấn + tác vụ trước/sau bằng nội dung tự tạo, không chỉ hỏi thích UI |
| Chức năng | Tạo/sửa/lưu/reload/xuất có đúng, giữ công thức/ownership/version không? | Pytest/contract/golden fixture/UI, gồm input rỗng/hỏng/quá lớn, stale/cancel |
| Usability | Người dùng làm được mà không cần nhớ LaTeX hoặc đoán vùng AI sẽ sửa không? | Quan sát tác vụ, thời gian, lỗi, lần cần trợ giúp; xin phép trước think-aloud |
| Accessibility | Tab/focus/label/contrast/text thay màu có dùng được không? | Bàn phím và kiểm nhãn trên desktop/mobile; ghi phạm vi kiểm, không tự chứng nhận WCAG |

Tác vụ người dùng đề xuất: chèn phân số/hệ mà không gõ lệnh; sửa một câu bằng chat rồi hoàn tác; lưu/reload đề có bảng; xuất bản học sinh không có đáp án. Chốt bộ task, cỡ mẫu, điều kiện môi trường, thứ tự/bias và ngưỡng trước chạy. Không giả kết quả từ CI là quan sát giáo viên thật.

## Nhật ký dữ liệu mẫu

| Mã ca/người ẩn danh | Commit/môi trường | Tác vụ/kỳ vọng | Thời gian/lỗi/trợ giúp | Kết quả và bằng chứng | Vấn đề cần sửa |
|---|---|---|---|---|---|
| Chưa chạy | — | — | — | — | — |

## Phản hồi → quyết định

Mỗi phát hiện ghi vấn đề quan sát, bằng chứng, mức nghiêm trọng, phương án sửa, issue phụ trách và kết quả kiểm lại. Phân loại: blocker (không hoàn thành/mất dữ liệu/sai quyền), nghiêm trọng nhưng có đường vòng, cải tiến tiện dụng. Số liệu từ mẫu nhỏ chỉ mô tả mẫu đó; ghi mẫu số, số ca bỏ dở và giới hạn.

Mỗi vòng nhóm trả lời: giữ gì, sửa gì, bỏ/defer gì, tại sao bằng chứng ủng hộ; đánh đổi tốc độ/độ đúng, ít bước/khả năng kiểm soát, phạm vi/thời gian. So sánh ít nhất một phương án khác cho rủi ro chính. Không chỉ liệt kê tính năng đẹp hoặc test xanh.

## Đề nghị nghiệm thu

Task hoàn thành khi có đầu ra theo acceptance, kết quả kiểm lại, PR/reviewer và giới hạn. Prototype/MVP còn cần giả thuyết cốt lõi được kiểm chứng, tác vụ chính ổn định, không còn blocker trong phạm vi demo, trade-off được chấp nhận và vòng cải tiến tiếp theo rõ. Xem [release checklist](../team/RELEASE.md) và [khung báo cáo](../reports/BAO_CAO_DO_AN.md).

Chưa có GreenNode thì đánh dấu phần model thật/deploy thật chưa kiểm; không chặn các test fixture/local độc lập. Chỉ Thuận quyết định mở web và test server; mọi nguồn dữ liệu phải được phép sử dụng.
