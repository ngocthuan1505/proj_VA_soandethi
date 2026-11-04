# Hồ sơ nhóm đã có và phần cần làm tiếp

Đối chiếu ngày 04/11/2026 từ chat còn lại trong cùng dự án, các bản Word/PPTX đã xuất và nhật ký rà soát đã lưu. **Nhóm đã có proposal, baseline, Decomposition–Pattern Recognition và Abstraction; không bắt đầu các phần này từ trang trắng.** Lượt chuẩn bị GitHub trước chưa đọc chat còn lại nên phần ghi nhận tiến độ thiếu các đầu ra này.

Đây là kết quả kiểm tra **hồ sơ đã lưu**, không phải xác nhận mọi thay đổi hiện tại trên Canva/Docs hoặc xác nhận của giảng viên. File xuất có thể cũ hơn tài liệu online. Không sao chép toàn bộ chat, bản ghi âm, slide bài giảng hoặc tài liệu có thông tin riêng lên repo. [Manifest](existing-evidence.json) ghi tên file, nguồn và SHA-256 để nhận diện đúng bản đã kiểm.

## Đối chiếu với sáu task CT

| Task | Phần đã có bằng chứng | Phần cần làm tiếp để nghiệm thu cả task |
|---|---|---|
| [CT-01 #26](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/26) | Proposal Why/What/How/Novelty, stakeholder, scope, kế hoạch đánh giá; baseline các công cụ và đối chiếu ba video soandethi | Gộp thành Problem Brief theo bài giảng mới; bổ sung/xác nhận ghi chép ít nhất 3 người dùng; đo cùng tác vụ nếu tuyên bố tiết kiệm thời gian. Baseline đã nghiên cứu không phải benchmark trực tiếp đồng đều |
| [CT-02 #27](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/27) | PPTX Decomposition–Pattern 23 trang: cây tổng thể 3 cấp, 7 chức năng, input/output, luồng phối hợp và 4 mẫu dùng chung; có nhật ký rà nội dung/ghi chú | Ánh xạ lá vào owner và 24 task triển khai mới, tách việc lớn, chỉ ra lá PoC, chốt lịch; không vẽ lại cây chỉ vì mở repo mới |
| [CT-03 #28](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/28) | Docs Abstraction và bản xuất: sáu đối tượng + SessionContext, KEEP/DEFER/RE-THINK/REMOVE, UML, bảng kiểu/đơn vị, Schema QuestionVersion, ADT và Interface; Canva đã có phần trình bày | Chuyển mô hình thiết kế sang DTO/OpenAPI/DB Python có review và fixture; đối chiếu bản online mới nhất, xử lý điểm sơ đồ còn thiếu nếu chưa sửa. Không coi UML/Schema là backend đã chạy |
| [CT-04 #29](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/29) | Proposal có phạm vi/kế hoạch PoC và ví dụ sửa câu | Trong hồ sơ đã đọc chưa thấy bộ kết quả PoC chạy lại được cho thí nghiệm sửa vùng này. Cần input/output, ngưỡng đặt trước, log, lỗi và kết luận; tài liệu tổng hợp không thay thí nghiệm |
| [CT-05 #30](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/30) | Abstraction có giả mã gọi bộ đọc và pre/postconditions của thay câu/xác nhận | Đây là thiết kế ADT/Interface; còn phải hoàn thiện thuật toán nghiệp vụ, flowchart, trace, phân tích và test Python đúng commit |
| [CT-06 #31](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/31) | Có slide trình bày, speaker notes, nhật ký sửa theo phản hồi, kế hoạch đánh giá và kịch bản demo | Rà nội dung slide là bằng chứng cải tiến tài liệu; chưa thay benchmark sản phẩm, usability với giáo viên hoặc báo cáo kết quả/demo cuối |

Trên GitHub ghi **đã có đầu ra thiết kế, còn phần hoàn thiện** cho CT-01/02/03; không tự đóng ba task khi acceptance tổng thể chưa đủ. Các checklist mới không có nghĩa nhóm phải làm lại nội dung cũ. Đầu ra cũ thuộc tập thể; vai trò UI/BE mới là điều phối phần tiếp theo, không dùng để gán ngược công lao hay danh tính người chưa xác nhận.

## Nguồn hồ sơ nhóm

- **Proposal:** `proposal_revision_2026-10-19_v2/Proposal_final.docx`. Đã đọc phần vấn đề, stakeholders, baseline/nguồn, phạm vi và kế hoạch. Tài liệu tự ghi chưa báo cáo kết quả thực nghiệm; các kế hoạch cũ cần đối chiếu phiên bản nhóm chốt tiếp.
- **Decomposition–Pattern:** `Slide_Decomposition_Pattern_da_ra_soat_01-11.pptx`, 23 trang, cùng bản nội dung/ghi chú đối chiếu và nhật ký. [Canva của nhóm](https://www.canva.com/design/DAHYob9z0Bo/2xadi3fIg6gSd8Xro1hDdw/edit). Nhật ký ngày 03/11 ghi đã bổ sung notes đủ 23 trang; chưa kiểm bản xuất PDF/PPTX sau Canva và độ rõ trên máy chiếu.
- **Abstraction:** [Docs bài chính](https://docs.google.com/document/d/1aPbp3jybeoFp9i9B5i2bilZhTqHkqRgkJvQZ8MZ_hkU/edit?tab=t.u9x5d9udf8y9), [nội dung slide](https://docs.google.com/document/d/1aPbp3jybeoFp9i9B5i2bilZhTqHkqRgkJvQZ8MZ_hkU/edit?tab=t.50y8uzv8i7t3), [Canva](https://www.canva.com/design/DAHZrGO7nH4/MbMX5UDD1iybiHf1pZHmhg/edit). Đã đọc bản xuất `Abstraction_ra_soat_cuoi_02-11/Abstraction_kiem_tra.docx` và nhật ký chỉnh sửa; chat sau đó đổi cách gọi Interface thành “Quy ước chung cho các bộ đọc tài liệu”. Không lấy file xuất cũ làm bản online mới nhất.
- **Đề bài riêng của đồ án:** `2026_Project_Virtual_Assistant_Academic.pdf`, 8 trang. Đã đọc R1–R8, gói nộp và rubric; xem [bảng áp dụng](DE_BAI_GOC.md). Đây là nguồn bổ sung từ hồ sơ nhóm, ngoài sáu PDF bài giảng.

Quyền repo Private không tự cấp quyền xem Docs/Canva. Nếu thành viên không mở được thì chủ tài liệu cấp đúng quyền cho nhóm; không chuyển công khai hoặc chia sẻ tài khoản để vượt quyền.

## Những quyết định thiết kế phải dùng lại

1. Sáu đối tượng: **ExamRequest, SourceDocument, ExamMatrix, Question, ExamDraft, TeacherPreference**; **SessionContext** giữ ngữ cảnh. Cần bổ sung mô hình job/session kỹ thuật khi triển khai, nhưng không bỏ mô hình miền nhóm đã làm.
2. Yêu cầu sửa có `target`, `changes`, `keep` theo ngữ cảnh/phiên bản. `questionId` khác vị trí Câu 5. Sửa cùng câu giữ ID, tạo phiên bản mới; kiểu sinh ID thật chốt ở backend, không lấy mã minh họa Q05 làm quy tắc.
3. `QuestionVersion` có 7 trường bắt buộc trong Schema minh họa: `questionId`, `versionId`, `content`, `questionType`, `evidence`, `verificationStatus`, `approvalStatus`. `evidence` có thể là danh sách rỗng; vẫn phải báo thiếu căn cứ khi cần. Schema này dành mẫu văn bản, chưa thay DTO richDoc đầy đủ.
4. Kết quả hệ thống kiểm tra, giáo viên duyệt câu và trạng thái cả bản đề là **ba ý nghĩa riêng**. Sửa nội dung phải xét lại kiểm tra/duyệt của phiên bản đó; không coi “không phát hiện vấn đề” là đúng tuyệt đối.
5. ADT `ProposeReplaceQuestion` tạo đề xuất; `ConfirmProposal` chỉ lưu sau xác nhận và kiểm lại phiên bản. Giữ câu ngoài phạm vi; rà đáp án/giải thích/căn cứ/hình liên quan thay vì giữ đáp án cũ bằng mọi giá.
6. `ISourceReader.ReadSource` thống nhất đầu vào và `Success(document)`/`Failure(message)`; đọc được không có nghĩa nội dung đã đúng hết. Giữ phần chưa rõ để giáo viên xem lại.
7. Bốn pattern trong bộ Decomposition: tìm căn cứ theo yêu cầu; đối chiếu ô ma trận; rà phần bị ảnh hưởng; xác nhận trước khi lưu. Dùng chúng để phân task và viết test, không phát minh lại bốn quy trình khác nhau.

## Điểm chưa xác nhận

Lần rà Canva Abstraction trước có ghi sơ đồ slide 4 cần đồng bộ `draftStatus`; người dùng yêu cầu sửa các trang khác và giữ nguyên slide 4 trong lượt đó. Chưa kiểm lại live trong đợt đối chiếu này, nên không khẳng định điểm đó đã sửa hay còn lỗi. Bản xuất Docs có `draftStatus` trong ADT. Cần đối chiếu đúng phiên bản hiện tại trước khi trình bày.

Không tìm thấy trong các hồ sơ đã đọc: bộ ghi chép ba giáo viên, benchmark tác vụ đồng đều, log PoC mới đầy đủ hoặc ngày nộp hiện hành. Điều này là **chưa thấy bằng chứng**, không phải khẳng định nhóm chưa từng làm ở nơi khác. Không suy từ tên file `final` ra việc giảng viên đã duyệt hoặc đã nộp.
