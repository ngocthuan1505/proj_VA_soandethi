# Problem Brief — bản nháp để kiểm chứng

Trạng thái: **đã có proposal và baseline nghiên cứu** ở chat còn lại; dùng lại phần Why/What/How/Novelty, stakeholders, scope và nguồn đã đối chiếu. Trong bộ hồ sơ đã đọc chưa thấy ghi chép ba người dùng hoặc benchmark trực tiếp đồng đều. UI-1 điều phối phần còn thiếu, không viết lại từ đầu. Xem [bằng chứng và giới hạn](HO_SO_DA_CO.md). Nguồn phương pháp: Topic 2 trang 24–36, 42, 45–46; Topic 4 trang 39.

## Vấn đề và người dùng

Giáo viên phổ thông cần chuẩn bị, chỉnh và xuất đề có chữ Việt/công thức đúng định dạng. Giả thuyết cần kiểm chứng: nhập ký hiệu, sửa một vùng bằng AI và sửa lỗi chuyển Word/PDF khiến họ mất thời gian, dễ ghi đè hoặc phải làm lại. Đây là giả thuyết từ phản hồi chủ dự án; chưa đủ thay bằng chứng từ ba giáo viên độc lập.

Người dùng chính: giáo viên tự soạn đề. Bên liên quan: tổ chuyên môn/người duyệt, học sinh nhận bản đề, nhóm phát triển và người quản trị dữ liệu/chi phí AI. Không thu dữ liệu học sinh thật để làm demo.

Mẫu chốt sau phỏng vấn: “Giáo viên [môn/lớp, bối cảnh] cần [việc cụ thể] vì [nguyên nhân đã kiểm chứng]. Hiện mất [số đo + cách đo]. Nhóm coi thành công khi [chỉ số/ngưỡng] trước [ngày lớp xác nhận].” Chưa điền số/ngày khi chưa có bằng chứng.

## Thu thập ít nhất 3 người dùng thật

Xin phép trước khi quan sát/ghi chép, dùng mã GV-01… thay tên/email. Không đưa bản đề riêng hay ghi âm lên GitHub nếu chưa được phép. Hỏi về việc lần gần nhất họ đã làm, tránh chỉ hỏi họ có thích app không:

1. Lần gần nhất soạn đề mất bao lâu, phần nào phải sửa lại nhiều nhất?
2. Họ chèn phân số, hệ phương trình, công thức Hóa/Lý bằng cách nào?
3. Khi dùng AI sửa một câu, điều gì giúp họ biết vùng khác vẫn được giữ?
4. Làm sao kiểm đáp án, tổng điểm và bản học sinh không lộ đáp án?
5. Có thể quan sát một tác vụ với đề tự tạo tương đương để đo thời gian/lỗi không?

| Mã | Vai trò/môn/lớp tự khai phù hợp | Ngày + cách xin phép | Quan sát/tác vụ | Thời gian/lỗi | Kết luận + liên kết ghi chép đã ẩn danh |
|---|---|---|---|---|---|
| GV-01 | Chưa thu thập | — | — | — | — |
| GV-02 | Chưa thu thập | — | — | — | — |
| GV-03 | Chưa thu thập | — | — | — | — |

Chuỗi 5 Whys cần làm sau quan sát: mất thời gian → bước cụ thể → nguyên nhân → điều kiểm soát được → cách kiểm chứng. Chưa xác nhận “không nhớ LaTeX” là nguyên nhân duy nhất.

## Input → Output → Constraints

- Input: yêu cầu môn/lớp/thời lượng, đề/vùng chọn và revision hiện tại; tài liệu nguồn được phép; lựa chọn AI của chủ tài khoản.
- Output: đề chỉnh được, gợi ý sửa có preview, đáp án/barem để giáo viên duyệt, Word/PDF theo lựa chọn giáo viên/học sinh.
- Constraints: không mất công thức/ID/nội dung ngoài vùng; không lộ đề giữa tài khoản; không tự gọi dịch vụ trả phí; kết quả AI cần duyệt; backend/core Python; thiếu server thì dùng fixture rõ nhãn.

> **Ranh giới hiện trạng kỹ thuật vs bằng chứng con người (`8d37a0f`, `codex/ban-thu-13`):** Phần ràng buộc kỹ thuật phía hệ thống (`[Hiện có / Đã chạy bằng Python]` — bảo toàn công thức/`richDoc`/`blockIds`, tách kho đa tài khoản, chặn sửa ngoài vùng/phiên bản cũ, xuất Word/PDF Học sinh không rò đáp án/chat khi tắt Node khỏi `PATH`, không fallback trả phí) đã có kiểm chứng trong [Đối chiếu Python](../testing/DOI_CHIEU_PYTHON.md), [Kiểm thử tích hợp](../testing/KIEM_THU_TICH_HOP.md), [Luồng màn hình](../design/luong-man-hinh.md) và [Hợp đồng tài liệu](../contracts/tai-lieu.md). Tuy nhiên, toàn bộ bảng phỏng vấn `GV-01`…`GV-03` và bảng baseline công cụ bên dưới **vẫn ở trạng thái chưa thu thập / chưa đo** (`[Chờ review nhóm / Thành viên xác nhận]`); không dùng kiểm thử kỹ thuật thay cho bằng chứng 3 người dùng thật của `CT-01` hoặc lịch lớp do `ngocthuan1505` xác nhận.

## Ưu tiên phiên bản của nhóm — cần review

| Mức | Phạm vi dự kiến |
|---|---|
| Must | Soạn/lưu/reload; công thức trực quan; sửa vùng có preview/undo/version; kho đề/ownership; xuất bản giáo viên/học sinh; lõi Python có kiểm thử |
| Should | Import DOCX/PDF và OCR có kiểm lại nguồn; thông báo lỗi/hủy/retry rõ; đa môn qua mẫu kiểm chứng |
| Could | Thêm bộ mẫu/định dạng sau khi Must đạt; thống kê cá nhân nếu người dùng cần |
| Won't trong MVP | Đồng biên tập thời gian thực, tự chấm đảm bảo đúng mọi môn, thanh toán, công khai tài liệu người dùng, cam kết uptime |

Đây là ưu tiên đồ án, không xóa chức năng demo kế thừa. [MVP sản phẩm](../product/MVP.md) và hợp đồng nhóm là nguồn chi tiết.

## Mục tiêu đo được — đề xuất, chưa phải kết quả

Đề xuất đo cùng bộ tác vụ tự tạo trước/sau: chèn công thức; sửa đúng một câu; lưu/reload; xuất bản học sinh. So sánh thời gian trung vị, lỗi, mức cần trợ giúp; kiểm mọi câu ngoài vùng nguyên vẹn. Chốt số người/số lần, ngưỡng giảm thời gian, tiêu chí đúng và ngày nghiệm thu **trước khi đo**, ghi vào issue CT-01. Không tuyên bố “giảm 50%” khi chưa đo.

## Baseline 2–3 công cụ

Proposal đã có baseline soandethi, Quizgecko, NotebookLM, Azota và Smallpdf dựa trên nguồn và ba video; không xóa phần đó để thay bằng bảng trắng này. Các nhận xét là kết quả nghiên cứu tại thời điểm tài liệu, chưa phải benchmark trực tiếp đồng đều hoặc xác minh tính năng hiện tại. Bước còn lại: chọn 2–3 công cụ phù hợp, kiểm cùng kịch bản hợp pháp, ghi ngày/phiên bản/quyền truy cập/ảnh được phép và kết quả; không sao chép UI/tài nguyên của họ.

| Nhu cầu giáo viên | Công cụ A + ngày | Công cụ B + ngày | Công cụ C nếu có | Soạn đề thi + commit kiểm | Khoảng trống được người dùng xác nhận |
|---|---|---|---|---|---|
| Chèn công thức không nhớ lệnh | Chưa kiểm | Chưa kiểm | — | Chưa đo | — |
| Sửa vùng, xem trước, hoàn tác | Chưa kiểm | Chưa kiểm | — | Chưa đo | — |
| Xuất bản học sinh giữ công thức | Chưa kiểm | Chưa kiểm | — | Chưa đo | — |

Chỉ chốt tính mới sau baseline và phỏng vấn; chức năng từng demo được không đồng nghĩa đã đáp ứng nhu cầu người dùng.
