# Đối chiếu đề bài riêng của đồ án

Nguồn: bản `2026_Project_Virtual_Assistant_Academic.pdf` (8 trang) đã có trong hồ sơ chat còn lại, đối chiếu ngày 04/11/2026. File gốc giữ ngoài repo; checksum trong [manifest hồ sơ](existing-evidence.json). Phần dưới diễn giải các yêu cầu để bổ sung kế hoạch, không thay thông báo lớp mới hơn.

## R1–R8 — trang 3

| Mã | Đề bài yêu cầu | Hồ sơ/việc cần truy vết |
|---|---|---|
| R1 | Người dùng/vấn đề cụ thể, 8–12 use case đại diện, non-goals, constraints, tiêu chí đo được | Proposal đã có nhiều phần; CT-01 hoàn thiện bằng chứng và metrics |
| R2 | Ít nhất một quy tắc/thuật toán/workflow minh bạch, kiểm được | CT-05; đếm/đối chiếu ma trận, validation hoặc kiểm phiên bản bằng Python |
| R3 | Ít nhất một nguồn dữ liệu có provenance, metadata, logic truy xuất | CT-03/04, BE-1/4; dùng SourceDocument và evidence đã thiết kế |
| R4 | Ít nhất một khả năng AI/ML/LLM có lý do kỹ thuật | CT-04, BE-1; có kết quả thật và giới hạn |
| R5 | Điều phối/routing rõ, có làm rõ yêu cầu và fallback | BE-1/2/5, UI-3; phân rule/retrieval/AI, hỏi lại và giữ dữ liệu khi lỗi |
| R6 | UI hoặc API E2E nối với backend thật | Task 002/003 vào FastAPI, không chỉ mock hoặc facade |
| R7 | Validation, lỗi/timeout, privacy, misuse/prompt-injection phù hợp | BE-2/5 và release checklist; test cả nguồn chứa lệnh giả |
| R8 | Bộ test lặp lại được, metrics/rubric, phân loại lỗi, ít nhất một vòng cải tiến có bằng chứng | CT-06; trước/sau về sản phẩm, không chỉ nhật ký sửa slide |

## Gói nộp — trang 6

1. Báo cáo kỹ thuật, **khuyến nghị** 12–18 trang chưa tính phụ lục; không biến khuyến nghị thành số trang cứng.
2. Repo/source, dependency/config mẫu, hướng dẫn cài/chạy/test tái lập và demo.
3. Bộ thiết kế: context/component/sequence hoặc data-flow, model/schema, pseudocode, interface.
4. Bộ đánh giá: dataset/expected output, script hoặc rubric, metrics/error taxonomy/regression, bằng chứng trước/sau.
5. Hồ sơ lỗi/rủi ro: privacy, ca misuse, safeguards, fallback/escalation và rủi ro chưa xử lý.
6. Trình bày và demo cuối có quyết định, bằng chứng, giới hạn và bài học.
7. Nhật ký nhóm theo tuần, issue/PR, phân công/đóng góp và cách dùng AI đã được kiểm chứng.

Các link trong [hướng dẫn nhóm](../team/README.md), [nhật ký #32](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/32), [khung báo cáo](../reports/BAO_CAO_DO_AN.md) là nơi tổng hợp; phải dùng lại [hồ sơ đã có](HO_SO_DA_CO.md).

## Rubric của đề bài — trang 7

| Tiêu chí | Trọng số trong rubric đồ án |
|---|---|
| Xác định vấn đề và lập luận CT | 15% |
| Kiến trúc và điều phối | 15% |
| Dữ liệu/truy xuất | 10% |
| Thuật toán và lựa chọn công nghệ | 10% |
| MVP và tích hợp | 20% |
| Độ tin cậy, an toàn và AI có trách nhiệm | 10% |
| Kiểm thử và đánh giá | 10% |
| Báo cáo, demo và trình bày | 10% |

Không trộn bảng này với tỷ trọng **30% bài tập / 70% đồ án** trong Topic 1; đó là hai cấp đánh giá. Không quy đổi thành điểm nhóm đã đạt.

## Tổ chức nhóm — trang 8

Đề bài ghi nhóm **5–7 sinh viên trừ khi được chấp thuận khác**, repo/board chung và nhật ký tuần. Thuận đã xác nhận nhóm 8 người; hồ sơ đã đọc còn để chỗ xác nhận giảng viên cho quy mô này. Giữ phân công 3 UI + 5 backend; Thuận cần lưu xác nhận đã có hoặc kiểm tra lại với lớp, không tự kết luận nhóm sai quy định hay tự bỏ thành viên.

Mỗi người cần đóng góp qua phân tích, thiết kế, hiện thực, đánh giá và trình bày; chia UI/backend là trách nhiệm chính, không có nghĩa chỉ làm một phần cô lập. AI được dùng hỗ trợ nhưng nhóm chịu trách nhiệm hiểu, sửa và test. Nội dung AI sinh không tự là bằng chứng thực nghiệm. Không đưa khóa/dữ liệu hạn chế lên repo hoặc dịch vụ ngoài.

Lộ trình 10 tuần trong đề bài và minh họa 11 tuần trong bài giảng cần đối chiếu lịch lớp; ngày nộp cũ ghi trên proposal không tự thành deadline hiện hành. Quy định Python vẫn theo trao đổi giảng viên Thuận cung cấp, xem [kế hoạch Python](../architecture/PYTHON_MIGRATION.md).
