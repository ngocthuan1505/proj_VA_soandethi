# Báo cáo đồ án Soạn đề thi — khung điền theo bằng chứng

**Bản đang hoàn thiện để nhóm rà trước khi nộp.** Nhóm điền khi có dữ liệu; BE-5 tổng hợp, mỗi vai trò chịu trách nhiệm phần mình. Đối chiếu [yêu cầu môn và nguồn](../course/README.md), không tự nhận rubric chi tiết chưa được phát.

Dùng lại [hồ sơ nhóm đã có](../course/HO_SO_DA_CO.md) cho Proposal, Decomposition và Abstraction; không viết lại từ đầu. Đã đối chiếu [R1–R8, gói nộp và rubric trong đề bài riêng](../course/DE_BAI_GOC.md). Kết quả thực nghiệm cần bằng chứng riêng; rà soát slide chưa thay được benchmark sản phẩm.

## Bảng truy vết R1–R8

Bảng dùng để đối chiếu yêu cầu môn trong lúc duyệt PR và báo cáo kết quả. Cột bằng chứng mô tả những gì người đọc có thể tự kiểm trong repo. Cột còn thiếu ghi phần cần bổ sung trước khi đề nghị nghiệm thu.

| Yêu cầu | Bằng chứng trong repo | Còn thiếu |
| --- | --- | --- |
| R1 · Vấn đề và phạm vi | [Problem Brief](../course/PROBLEM_BRIEF.md) nêu nhóm giáo viên, phạm vi và giả thuyết. [Danh sách 11 use case](../product/USE_CASES.md) có đầu ra, tình huống lỗi và giới hạn. | Xác nhận phỏng vấn tối thiểu ba người dùng, baseline và mục tiêu đo được. |
| R2 · Quy tắc kiểm được | [Thuật toán sửa vùng](../course/ALGORITHM.md) mô tả điều kiện trước/sau. [Kiểm giao dịch](../../backend/tests/test_poc_scoped_patch.py) đối chiếu revision, vùng chọn và hoàn tác. | Review phản ví dụ, phạm vi xử lý tài liệu có nhiều công thức và quyết định giới hạn trước Final. |
| R3 · Nguồn và truy xuất | [Hợp đồng dữ liệu](../contracts/du-lieu.md) ghi định danh và phiên bản. [Kiểm nhập nguồn](../../backend/tests/test_source_documents.py) và [kiểm nguồn A/B](../../scripts/kiem-ui-nguon-ab.mjs) truy vết tài liệu và locator. | Đo chất lượng OCR với nguồn được phép và rà độ chính xác căn cứ của đề đa môn. |
| R4 · Khả năng AI | [PoC vòng công cụ](../testing/POC_AGENT_CMD.md) ghi cách model gọi kiểm, nhận lỗi và nộp lại. [Kiểm thật với Ollama](../testing/KIEM_NHANH_AI.md) mô tả cách tái lập theo model và digest. | Rà chất lượng độc lập và xác nhận độ ổn định của các dạng câu ở bản đề nghị nộp. |
| R5 · Điều phối | [Mô hình trạng thái trợ lý](../design/tro-ly-va-job.md) và [ca gợi ý cơ cấu](../../scripts/kiem-ui-co-cau.mjs) kiểm hỏi lại và xác nhận. [Vòng công cụ Python](../../backend/src/mach_backend/matrix_agent.py) quyết định khi nào mở quyền kết thúc. | Review các nhánh thiếu dữ kiện, quota, hủy và thử lại qua giao diện với cấu hình dự kiến dùng khi demo. |
| R6 · Luồng tích hợp | [Hướng dẫn cài và demo](../../HUONG_DAN_TEST_NHOM.md) chạy FastAPI. [Bộ 11 ca Chrome](../testing/KIEM_THU_TICH_HOP.md) gọi route Python với kho thử. | Một thành viên khác cài và chạy lại ứng viên được đề nghị nộp, rồi kiểm bản xuất trên máy đó. |
| R7 · Tin cậy và an toàn | [Kiểm quyền kho nhóm](../../backend/tests/test_team_workspace.py), [kiểm sửa đúng vùng](../../backend/tests/test_patch_confirmation.py) và [kiểm khôi phục](../../backend/tests/test_workspace_backup.py) cho thấy cách chặn quyền, kiểm snapshot và giữ dữ liệu. | Reviewer xác nhận phạm vi lỗi còn mở, giới hạn tải và phương án khi hệ thống từ chối đề xuất. |
| R8 · Đánh giá lặp lại được | [Kế hoạch đánh giá CT-06](../course/EVALUATION.md), [11 tình huống tích hợp](../testing/KIEM_THU_TICH_HOP.md) và [PR có bằng chứng trước/sau](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/46). | Kết hợp số đo kỹ thuật với đánh giá usability, accessibility, giá trị sử dụng và nhận xét độc lập của nhóm. |

## 1. Thông tin và đóng góp

Tên đề tài, lớp, giảng viên, thành viên/mã sinh viên theo quy định nộp của lớp, vai trò và phạm vi đóng góp. Thông tin định danh chỉ đưa lên repo khi phù hợp quyền chia sẻ; danh sách nhóm gồm [tám tài khoản GitHub đã xác nhận](../team/members.json). Hồ sơ xác nhận quy mô nhóm từ giảng viên cần được đối chiếu riêng. Liên kết issue/PR và review từng người, không đánh giá đóng góp chỉ bằng số commit.

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

Ứng dụng chạy FastAPI và lưu kho bằng SQLite. Python kiểm ma trận, điểm theo đơn vị 0,25, trạng thái tác vụ, phạm vi sửa và revision trước khi xác nhận lưu. Người dùng làm việc trong bàn soạn JavaScript, nơi hiển thị công thức, vùng chọn và bản xem trước. [Sơ đồ và chỉ mục kiến trúc](../architecture/CURRENT_STATE.md) · [Đối chiếu Python](../testing/DOI_CHIEU_PYTHON.md).

Pseudocode/flowchart, dry run, điều kiện dừng/lỗi, phân tích chi phí và benchmark nếu đã đo. Nêu phần deterministic và phần AI xác suất. Chỉ rõ backend/core Python nào đã thực thi; frontend JS và Node legacy nào còn dùng; không dùng thống kê ngôn ngữ làm bằng chứng thay nghiệp vụ. Link CT-05 và [kế hoạch Python](../architecture/PYTHON_MIGRATION.md).

## 8. Prototype/MVP, kiểm thử và đánh giá

Ứng viên `0198f75` qua 11 ca Chrome với phản hồi mẫu và 669 ca pytest trên Windows. Năm ca gọi model được bỏ qua trong lượt pytest mặc định. Lượt pytest chạy với PATH không chứa Node hoặc npm. Ca nhập tài liệu và ca gợi ý cơ cấu chờ bàn soạn lưu ID khối của đề mẫu trước khi ghi nhận mốc so sánh. [Cách chạy lại bộ kiểm](../testing/KIEM_THU_TICH_HOP.md) · [Mã nguồn ứng viên](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/0198f75ad02881fd04ad3391dc95e206765a9656).

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
