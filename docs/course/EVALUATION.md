# Kiểm thử và đánh giá phản biện

**Baseline kỹ thuật đã chạy 05/11/2026.** Xem [kết quả demo kế thừa](../testing/BASELINE_2026_11_05.md), [chức năng và giới hạn](../product/DEMO_DA_CO.md) và [cách thành viên tự test](../team/CHAY_VA_TEST_DEMO.md). Phần đánh giá với giáo viên vẫn chờ quan sát trực tiếp.

Nguồn phương pháp là Topic 6 trang 17–24, 26–30, 32. Phần dưới lưu một vòng đo kỹ thuật với Qwen3 cục bộ và kế hoạch đánh giá người dùng. BE-5 tổng hợp, các mảng kiểm phần mình và người đánh giá độc lập rà kết luận.

## Bốn loại bằng chứng

| Loại | Câu hỏi với Soạn đề thi | Cách thu thập dự kiến |
|---|---|---|
| Giá trị/khái niệm | Giáo viên có tiết kiệm công sức ở bước họ thực sự gặp khó không? | Phỏng vấn + tác vụ trước/sau bằng nội dung tự tạo, không chỉ hỏi thích UI |
| Chức năng | Tạo/sửa/lưu/reload/xuất có đúng, giữ công thức/ownership/version không? | Pytest/contract/golden fixture/UI, gồm input rỗng/hỏng/quá lớn, stale/cancel |
| Usability | Người dùng làm được mà không cần nhớ LaTeX hoặc đoán vùng AI sẽ sửa không? | Quan sát tác vụ, thời gian, lỗi, lần cần trợ giúp; xin phép trước think-aloud |
| Accessibility | Tab/focus/label/contrast/text thay màu có dùng được không? | Bàn phím và kiểm nhãn trên desktop/mobile; ghi phạm vi kiểm, không tự chứng nhận WCAG |

Tác vụ người dùng đề xuất: chèn phân số/hệ mà không gõ lệnh; sửa một câu bằng chat rồi hoàn tác; lưu/reload đề có bảng; xuất bản học sinh không có đáp án. Chốt bộ task, cỡ mẫu, điều kiện môi trường, thứ tự/bias và ngưỡng trước chạy. Không giả kết quả từ CI là quan sát giáo viên thật.

## Trước và sau trên cùng mẫu Toán lớp 5

Mẫu nhóm tự viết gồm năm câu, bốn dạng và tổng 10 điểm. Các lượt dưới dùng Qwen3 4B qua Ollama cục bộ với Chrome và kho SQLite thử. Transport QA chạy Vulkan và tắt chế độ suy nghĩ. Thời hạn tác vụ là 900 giây.

| Chủ đề | Dạng | Mức yêu cầu | Điểm |
|---|---|---|---|
| Số sách theo thể loại | Trắc nghiệm | 1 Nhận biết, 1 Thông hiểu | 2 mỗi câu |
| Lịch đọc tại thư viện | Đúng/Sai | 1 Nhận biết | 2 |
| Số sách trên kệ | Trả lời ngắn | 1 Thông hiểu | 2 |
| Tính tiền mua bút | Tự luận | 1 Vận dụng | 2 |

> Thư viện trường có 24 sách truyện và 16 sách khoa học. Ngày đọc sách diễn ra vào thứ sáu. Buổi sáng thư viện mở lúc 8 giờ, buổi chiều mở lúc 14 giờ. Mỗi buổi đọc kéo dài 45 phút. Trên kệ A có 12 cuốn, trên kệ B có 18 cuốn. Cửa hàng bán mỗi cây bút với giá 5.000 đồng. Nếu mua từ 10 cây bút trở lên, cửa hàng giảm 5.000 đồng trên tổng hóa đơn.

Trong kho thử trống, tạo đề Toán lớp 5, nhập nguồn và ma trận trên rồi gõ **Soạn đề theo ma trận này**. Đối chiếu lần nộp, `candidateHash`, phản hồi lỗi của lần trước, trạng thái lượt kiểm nội dung và revision trước/sau. Mở đề xuất và xác nhận chỉ khi toàn bộ bộ kiểm đạt. [Mở app và xem nhật ký](../testing/THEO_DOI_LOG_POC.md)

| Commit runtime | Thay đổi đang đo | Quan sát trên một lượt |
|---|---|---|
| `c1dc33a` | Trả lỗi cho Ollama bằng đối tượng JSON | Nộp bốn lần, ba lần sau lặp bộ đầu. Không có đề xuất qua kiểm. |
| `c02daca` | Sau lần nộp trùng, rút bộ cũ khỏi ngữ cảnh và giữ ma trận, nguồn, lỗi | Lần ba viết lại cả năm câu, qua cấu trúc rồi trượt rà nội dung. Bộ giải từng tính được 40 nhưng chỉ phương án ghi 30. |
| `20201ea` | Bộ giải trả nội dung phương án, Python tìm vị trí | Ánh xạ đúng 6/6 lần ở ba lượt rà. Sai Đúng/Sai, lệch mức và bất đồng bảng đánh giá vẫn bị chặn. |

Ba lượt đều kết thúc vì hết thời gian, revision giữ ở 1 và lưu 0 câu. Kết quả 6/6 đo ánh xạ của Python, còn chất lượng câu hỏi và đáp án cần kiểm riêng. Dữ liệu chỉ gồm một đề và một lượt cho mỗi commit, chưa dùng để so tốc độ hoặc suy rộng tỷ lệ đạt. Nhật ký đầy đủ nằm trong kho QA cục bộ, kèm mã commit và file kiểm đối chiếu từng lượt. [Nhánh tích hợp và ca hồi quy](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/46)

Quyết định sau thử nghiệm là giữ kiểm độc lập và chặn khi bộ kiểm mâu thuẫn. Khi đề xuất chưa đạt trong ngân sách, giáo viên giữ bản đang soạn và có thể soạn tiếp thủ công. Phần cần xác nhận tiếp là model thật sửa qua kiểm, sau đó người rà độc lập kiểm nội dung và mức nhận thức.

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
