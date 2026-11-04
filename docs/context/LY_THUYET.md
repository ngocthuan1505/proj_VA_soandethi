# Bàn giao: lý thuyết, nghiên cứu và thuyết trình

Cập nhật: 04/11/2026, từ hồ sơ đã đọc và nhật ký rà soát; chưa kiểm lại Docs/Canva trực tuyến trong đợt này.

## Đã có

- Proposal: Why/What/How/Novelty, stakeholders, scope, baseline sản phẩm và kế hoạch đánh giá. So sánh tài liệu/video không thay benchmark có cùng tác vụ và số đo.
- Decomposition–Pattern: bộ 23 slide; cây phân rã, bảy module, input/output, luồng phối hợp và bốn pattern. Nhật ký đã ghi đủ notes 23 trang.
- Abstraction: sáu đối tượng miền và SessionContext; UML, QuestionVersion Schema, ADT đề xuất/xác nhận sửa, interface bộ đọc tài liệu. Đây là thiết kế, chưa chứng minh backend đã triển khai.
- Đã đối chiếu sáu PDF bài giảng và đề bài đồ án tám trang; CT-01/02/03 được ghi nhận đang hoàn thiện trên bảng tại thời điểm đối chiếu, không còn coi như bắt đầu từ trắng.

File, liên kết Docs/Canva, SHA-256 và giới hạn bản xuất: [hồ sơ đã có](../course/HO_SO_DA_CO.md), [manifest](../course/existing-evidence.json). Không chép lại tài liệu gốc ở đây.

## Chuyển cho bên thực hành

- Dùng lại mô hình và bốn pattern trong [WBS](../course/WBS.md), [contracts](../course/CONTRACTS.md). Schema minh họa nội dung văn bản chưa thay DTO rich document đầy đủ; phải thống nhất trước khi port.
- `questionId` độc lập thứ tự câu; sửa giữ ID, tạo version mới. Tách ba trạng thái kiểm tra/duyệt câu/cả đề. Xác nhận lại version khi áp dụng đề xuất.
- Cần code/test và log thực nghiệm cho PoC, thuật toán, nguồn trích dẫn, phạm vi sửa và đánh giá cải tiến. Không dùng slide có sơ đồ làm bằng chứng tính năng chạy được.

## Cần kiểm chứng tiếp

- Đối chiếu bản Docs/Canva mới nhất, nhất là `draftStatus` ở sơ đồ Abstraction slide 4; lịch sử chỉ ghi đã giữ slide này trong một lượt sửa.
- Chưa thấy đủ ghi chép khảo sát giáo viên, benchmark đồng đều hoặc log PoC trong bộ đã đọc. Không suy ra nhóm chưa từng làm ở nơi khác; bổ sung bằng chứng nếu có.
- Chốt deadline thực tế, xác nhận giảng viên về nhóm tám người và phiên bản hồ sơ được nghiệm thu.

Khi có thay đổi tiếp: cập nhật các mục trên kèm nguồn, ngày, tác động tới app và điều còn cần kiểm tra; không dán toàn bộ nội dung chat.
