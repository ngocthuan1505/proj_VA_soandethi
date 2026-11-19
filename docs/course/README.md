# Áp dụng môn Computational Thinking vào đồ án Soạn đề thi

**Nhận việc hồ sơ:** [Chi tiết sáu task CT](BACKLOG_CT.md), có bước Wxx, ca kiểm Txx, đầu ra và người nhận bàn giao; kế thừa hồ sơ cũ thay vì viết lại. Các bước này chưa phải kết quả thực hiện hoặc điểm đã đạt.

Tài liệu đã đọc ngày 04/11/2026: **6 PDF, 258 trang** trong [thư mục môn học do Thuận cung cấp](https://drive.google.com/drive/folders/1L_2gLfP4aXve4dcdobSJtAIqDeOoONcK). Chỉ lưu diễn giải, kế hoạch áp dụng và liên kết nguồn; không chép toàn bộ slide vào repo. Danh sách file, số trang và checksum nằm trong [sources.json](sources.json).

**Đã đối chiếu chat còn lại cùng dự án:** nhóm đã có proposal/baseline, Decomposition–Pattern 23 trang và hồ sơ Abstraction. Xem [hồ sơ đã có và việc còn lại](HO_SO_DA_CO.md); dùng lại tài liệu này, không làm lại từ đầu. Đồng thời đã tìm được [đề bài riêng với R1–R8, gói nộp và rubric](DE_BAI_GOC.md), ngoài sáu bài giảng.

## Nguồn và phần áp dụng

| Nguồn | Trang PDF đã đối chiếu | Áp dụng vào đồ án |
|---|---|---|
| [Topic 1 — Introduction](https://drive.google.com/file/d/10TNlV_kvtYEkutskHYtT_nMgvXWpSskS/view) | 16, 36–39 | WBS → kế hoạch thời gian → Kanban; có các mốc Proposal/PoC, MVP, sản phẩm cuối |
| [Topic 2 — Problem Analysis](https://drive.google.com/file/d/1tppsndZ8AvvLwhZzohZOQkCgtPVB6xkB/view) | 24–36, 42, 45–46 | Problem Brief một trang, ít nhất 3 người dùng thật, nguyên nhân gốc, input/output/constraints, MoSCoW, mục tiêu đo được |
| [Topic 3 — Decomposition & Pattern Recognition](https://drive.google.com/file/d/1yYUVMut2OOS3yofcZWHlv4S0ks3zkwhG/view) | 8–9, 17–18, 30, 37, 42 | Cây 3 cấp, các phần ghép được qua interface, nhận diện mẫu và tái sử dụng công cụ; chọn lá rủi ro nhất cho PoC |
| [Topic 4 — Abstraction](https://drive.google.com/file/d/1e5yQP0THCQQcjBywhKgB5XHmh82E4w0f/view) | 10, 22–24, 30–40 | Mô hình trường/kiểu/đơn vị; hợp đồng hàm/API; so sánh 2–3 app; PoC có dữ liệu, cách chạy và ngưỡng kết luận |
| [Topic 5 — Algorithm](https://drive.google.com/file/d/1R2OE7sIcHw8lseHBvYd0YD58wlYb6XC_/view) | 8, 18–23, 26–35, 38, 43–44 | Mô tả thuật toán hữu hạn, pseudocode/flowchart, dry run, phân tích chi phí và cách kiểm chứng; trách nhiệm với kết quả AI |
| [Topic 6 — Prototype, Testing & Critical Evaluation](https://drive.google.com/file/d/1Ce8LL9gTl3J8tUNm7vOkCl1HQr1_IP57/view) | 7–8, 11–15, 17–24, 26–30, 32 | Mỗi prototype kiểm một giả thuyết; test chức năng, giá trị, usability, accessibility; phản hồi → quyết định giữ/sửa/bỏ và tiêu chí hoàn thành |

Topic 5 và 6 trong thư mục ghi **2025** trên slide, trong khi Topic 1–4 ghi 2026. Vẫn áp dụng kiến thức của chúng, nhưng không suy ra deadline hoặc rubric bổ sung cho lớp 2026 từ nhãn năm cũ. Các trang nói về bài tập trên lớp không tự trở thành yêu cầu phải thêm tính năng vào app.

## Mốc đánh giá đã thấy trong slide

Topic 1 trang 39: phần bài tập 30% (quiz 10%, lab 20%); đồ án 70% gồm **Proposal + PoC 20%, MVP 10%, sản phẩm cuối 40%**. Đây là tỉ trọng tổng quan trong slide, không phải rubric chi tiết cho từng chức năng Soạn đề thi.

Topic 1 trang 36 và Topic 2 trang 45 minh họa Proposal/PoC ở tuần 5, phát triển/kiểm thử ở giai đoạn tiếp theo và đánh giá/demo ở tuần 11. Trang 38 liệt kê 10 lab. **Chưa có lịch lớp/ngày nộp cụ thể hoặc đề bài lab chi tiết trong sáu PDF này.** Không lấy ngày minh họa SMART trong slide làm deadline thật.

Ba milestone kỹ thuật M1/M2/M3 trong repo là kế hoạch của nhóm, không đồng nhất máy móc với tuần học. [Lộ trình](WBS.md) gắn chúng với các đầu ra môn để nhóm chốt ngày sau. Các công cụ như Firebase, thanh toán, Maps hay weather trong lộ trình lab không có nghĩa app soạn đề phải tích hợp tất cả; cần xem đề bài lab riêng khi nộp.

Python là ngôn ngữ chính theo **ảnh trao đổi giảng viên mà Thuận đã cung cấp trước**, không phải một tỉ lệ dòng code suy ra từ sáu PDF. Xem [kế hoạch Python](../architecture/PYTHON_MIGRATION.md). [Bản tích hợp Python](../testing/DOI_CHIEU_PYTHON.md) có bằng chứng chạy FastAPI không cần Node API. Xem phạm vi chuyển và giới hạn theo từng luồng trước khi ghi kết luận nghiệm thu.

## Đầu ra đã soạn khung để nhóm làm

| Đầu ra | Nơi làm | Người điều phối theo vai trò |
|---|---|---|
| Problem Brief, bằng chứng 3 người dùng và baseline | [PROBLEM_BRIEF.md](PROBLEM_BRIEF.md) | UI-1; mọi người hỗ trợ phỏng vấn |
| Cây phân rã, kế hoạch phụ thuộc và kế hoạch tuần | [WBS.md](WBS.md), [24 task](../team/BACKLOG.md) | UI-1 + BE-5 |
| Mô hình dữ liệu và hợp đồng | [CONTRACTS.md](CONTRACTS.md), [DATA_PLAN](../architecture/DATA_PLAN.md) | BE-3 + BE-2, UI/AI/tài liệu review |
| PoC phần rủi ro nhất | [POC.md](POC.md) | Thuận BE-1 + UI-3; có chế độ fixture không cần server |
| Thuật toán và dry run | [ALGORITHM.md](ALGORITHM.md) | BE-2 + BE-5; BE-1/3 review |
| Test với người dùng, đánh giá và báo cáo cuối | [EVALUATION.md](EVALUATION.md), [khung báo cáo](../reports/BAO_CAO_DO_AN.md) | BE-5 tổng hợp, từng vai trò cung cấp bằng chứng |

Các file trong repo là khung hoàn thiện **dựa trên hồ sơ nhóm đã có**, chưa phải nghiệm thu cả task. Trong các hồ sơ đã đối chiếu chưa thấy đầy đủ ghi chép ba người dùng, benchmark đồng đều hoặc kết quả PoC mới. Ghi “chưa thấy bằng chứng” cho phần đó, không kết luận nhóm chưa từng làm ở nơi khác và không yêu cầu viết lại proposal/UML đã có.

**Issue nhận việc:** [CT-01 #26](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/26) · [CT-02 #27](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/27) · [CT-03 #28](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/28) · [CT-04 #29](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/29) · [CT-05 #30](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/30) · [CT-06 #31](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/31). Đây là 6 đầu ra chung theo vai trò điều phối và người phối hợp, chưa nghiệm thu.

## Cách nhóm bắt đầu

Đọc [trang bắt đầu nhóm](../team/README.md), nhận việc `001` theo vai trò và phần tài liệu môn liên quan. Từng task đã có input, đầu ra, bước làm, reviewer và bằng chứng CT. Issue là gói việc; nếu một bước mất hơn khoảng một ngày, tách issue nhỏ theo [mẫu task](../../.github/ISSUE_TEMPLATE/task.md) và liên kết cha, tránh PR gom cả module.

Khi có tiến triển, dùng [quy trình báo cáo](../team/BAO_CAO.md). Báo cáo bằng chứng/khó khăn thật; không tick hoàn thành thay người làm và không tự gọi API trả phí hoặc đăng nhập GreenNode.
