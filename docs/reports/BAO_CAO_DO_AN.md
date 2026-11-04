# Báo cáo đồ án Mạch — khung điền theo bằng chứng

Trạng thái: **khung chuẩn bị, chưa phải báo cáo kết quả hoàn thành**. Nhóm điền khi có dữ liệu; BE-5 tổng hợp, mỗi vai trò chịu trách nhiệm phần mình. Đối chiếu [yêu cầu môn và nguồn](../course/README.md), không tự nhận rubric chi tiết chưa được phát.

## 1. Thông tin và đóng góp

Tên đề tài, lớp, giảng viên, thành viên/mã sinh viên theo quy định nộp của lớp, vai trò và phạm vi đóng góp. Thông tin định danh chỉ đưa lên repo khi phù hợp quyền chia sẻ; hiện [roster](../team/roster.json) chưa đủ bảy username. Liên kết issue/PR và review từng người, không đánh giá đóng góp chỉ bằng số commit.

## 2. Vấn đề và bằng chứng người dùng

Problem statement đã kiểm chứng; ít nhất ba người dùng theo hướng dẫn Topic 2; root cause, stakeholder, baseline đo được, phạm vi và MoSCoW. Link CT-01, ghi phương pháp, dữ liệu còn thiếu và hạn chế mẫu.

## 3. Giải pháp và baseline

So sánh 2–3 công cụ theo tác vụ người dùng; giải thích khoảng trống nhóm giải quyết và quyết định thiết kế riêng. Nêu tính năng ngoài phạm vi. Không tuyên bố “tốt hơn mọi công cụ” khi mới thử ít mẫu.

## 4. Phân rã và nhận diện mẫu

Cây 3 cấp, WBS/Kanban và dependencies, pattern/công cụ tái sử dụng/owner/done-when từng lá. Nêu cách phần việc ghép lại qua interface và phần rủi ro nhất. Link CT-02 và các task UI/BE liên quan.

## 5. Trừu tượng hóa và mô hình

ERD, data dictionary, contract/API, keep/defer/drop, version/ownership và giả định. Phân biệt thiết kế đề xuất với code đã thực thi. Link CT-03, ADR dữ liệu và OpenAPI của commit demo.

## 6. Proposal và PoC

Câu hỏi yes/no, bộ mẫu, ngưỡng đặt trước, model/tool/steps, kết quả cả đúng và sai, ảnh/script/notebook/demo chạy lại được, kết luận và lựa chọn sửa. Link CT-04. Tách fixture khỏi model thật và kiến thức cần giáo viên duyệt.

## 7. Thuật toán và hiện thực Python

Pseudocode/flowchart, dry run, điều kiện dừng/lỗi, phân tích chi phí và benchmark nếu đã đo. Nêu phần deterministic và phần AI xác suất. Chỉ rõ backend/core Python nào đã thực thi; frontend JS và Node legacy nào còn dùng; không dùng thống kê ngôn ngữ làm bằng chứng thay nghiệp vụ. Link CT-05 và [kế hoạch Python](../architecture/PYTHON_MIGRATION.md).

## 8. Prototype/MVP, kiểm thử và đánh giá

Phiên bản/giả thuyết từng vòng; functional + value + usability + accessibility; input/environment/commit/mẫu số; bug/feedback và cách kiểm lại. So sánh trước/sau có phương pháp, nêu trade-off, phương án khác, giữ/sửa/bỏ. Link CT-06; chưa có số liệu thì ghi chưa đo, không điền số minh họa.

## 9. Demo và tái lập

Commit/tag cụ thể; clone/cài deps; fixture; lệnh chạy; tài khoản demo giả; kịch bản tạo → công thức → sửa vùng/preview/undo → lưu/reload → xuất học sinh; ca lỗi stale/cancel; địa chỉ public chỉ do Thuận cung cấp riêng nếu mở test. Giữ video/ảnh không lộ khóa hoặc dữ liệu cá nhân. Dữ liệu server cũ chưa khôi phục thì ghi rõ.

## 10. Hạn chế, trách nhiệm và vòng sau

Giới hạn AI/định dạng/tải/bảo mật/dữ liệu; blocker còn mở; ưu tiên vòng sau; quyết định không làm và lý do. Không gọi app production-ready hoặc full Python khi chưa đủ bằng chứng. Trích nguồn thư viện/model/tài liệu và phần dùng AI hỗ trợ viết code; từng thành viên giải thích và kiểm code mình nộp. Không nhận đầu ra AI thành dữ liệu phỏng vấn hay kết quả đo thật.

## Kiểm trước nộp

- [ ] Mỗi tuyên bố kết quả có evidence/commit/người review, không lẫn dự kiến với đã làm.
- [ ] Tất cả thành viên đã kiểm phần đóng góp và có thể trình bày thuật toán/thiết kế.
- [ ] Có bảng đối chiếu CT-01…06 với tài liệu, task và kết quả.
- [ ] Lịch, định dạng file và kênh nộp đã đối chiếu thông báo lớp mới nhất.
- [ ] Nguồn được ghi, dữ liệu có quyền sử dụng, không lộ secret/URL server riêng.
- [ ] Demo chạy lại trên môi trường sạch theo phạm vi đã công bố; bug/giới hạn được ghi trung thực.
