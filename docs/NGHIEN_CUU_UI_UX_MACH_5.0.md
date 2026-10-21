# Nghiên cứu và đánh giá UI/UX — Mạch 5.0

Ngày: 18/10/2026. Mục tiêu: giảm yêu cầu nhớ cú pháp khi soạn nội dung chuyên môn, đồng thời tạo nhận diện và cách điều hướng riêng cho app. Phạm vi là bàn soạn MVP đang chạy ở máy người dùng; không triển khai công khai.

## Phương pháp và nguồn

Đã đọc tài liệu gốc về nhận biết/ghi nhớ, progressive disclosure, vùng chạm, tương phản, dialog và bộ nhập toán. Sau đó walkthrough các nhiệm vụ, triển khai trên app, kiểm tra tự động và xem ảnh desktop/viewport điện thoại. **Chưa phỏng vấn hoặc đo thời gian thao tác của giáo viên thật.** Các nhận định về tiết kiệm thời gian là mục tiêu thiết kế, không phải số liệu nghiên cứu người dùng.

| Cơ sở | Áp dụng trong app |
|---|---|
| [NN/g — Recognition and Recall](https://www.nngroup.com/articles/recognition-and-recall/) | Tên mẫu tiếng Việt + hình xem trước + ô có nhãn; người dùng chọn cấu trúc thay vì nhớ sqrt/cases. |
| [NN/g — Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/) | Điền ô là mặc định cho mẫu phổ biến; sửa trực quan tự do và mã nâng cao mở khi cần. |
| [W3C — Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | Tăng kích thước nút chủ đạo/ô nhập, khoảng cách nút, kiểm thư viện tại viewport 390×844. Không tuyên bố mọi control của app đã qua audit WCAG. |
| [W3C — Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) | Chữ phụ của bộ nhập đổi sang xanh xám đậm; cặp #57735f/trắng xấp xỉ 5,22:1; #62776b/trắng xấp xỉ 4,81:1. Đây là một số cặp màu, không phải chứng nhận toàn app. |
| [W3C APG — Modal Dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) | Nhãn dialog, vòng Tab/Shift+Tab trong bộ nhập, Escape đóng, trả focus và phím tắt lưu. Chưa thử toàn diện với trình đọc màn hình. |
| [MathLive — Getting Started](https://mathlive.io/mathfield/guides/getting-started/) và [Virtual Keyboard](https://mathlive.io/mathfield/guides/virtual-keyboard/) | Sửa phân số/căn/mũ theo vị trí, bàn phím ký hiệu khi cần; serialize về LaTeX để giữ tương thích KaTeX và Word. |
| [MDN — Dynamic import](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/import) | MathLive chỉ tải khi mở bộ nhập, không thêm vào luồng tải ban đầu. Assets/phông lưu tại máy. |

## Đánh giá vấn đề cũ → quyết định mới

| Vấn đề quan sát | Quyết định | Tiêu chí kiểm |
|---|---|---|
| Ô LaTeX là nơi nhập chính, lỗi còn báo kiểu kỹ thuật | Chọn mẫu → điền từng ô → xem kết quả; lỗi ngắn, có ngữ cảnh | Hoàn thành căn/hệ mà không mở mã nâng cao |
| Hóa học vẫn giống bàn nhập toán | Ô chất tham gia/sản phẩm/điều kiện; preview mhchem; ghi rõ phạm vi kiểm nguyên tố | Phản ứng thường, ion và điều kiện giữ đúng khi chèn |
| Chỉ có điểm vào Toán/Hóa | Một thư viện sáu môn; tìm không dấu; khung nội dung phù hợp môn | Lý/Sinh/Văn/Anh đều tạo block thật, sửa lại được |
| Nhiều cách tìm công cụ nằm trong menu | Thanh điều hướng cố định + thư viện theo môn + Ctrl+K | Tìm và mở đúng công cụ, không làm mất bản soạn |
| Bố cục/nhận diện quá sát dịch vụ tham khảo | Nhận diện Mạch, rail xanh đậm, cấu trúc dạng thẻ, toolbar trong bàn soạn, panel riêng | Duy trì định dạng in; giao diện làm việc có thiết kế riêng |
| Trợ lý luôn chiếm không gian | Chế độ tập trung có nút thoát rõ | Ẩn/hiện hai cột phụ mà dữ liệu giữ nguyên |
| Ngữ liệu nhiều dòng bị làm phẳng trong bộ tuần tự hóa | Dùng chung documentPlain cho editor và xuất; giữ blockquote/dòng/bảng | Nhập thơ, reload, giữ từng dòng và nguồn |

Thiết kế dùng nét đơn giản, màu xanh rừng/xanh xám và một tông vàng nhỏ ở nhãn hiệu. Giấy thi vẫn trắng/đen, tách khỏi màu giao diện. Không sao chép logo, ảnh, stylesheet hoặc mã của soandethi.com; bố cục thao tác soạn thảo quen thuộc được giữ ở mức chức năng chung.

## Luồng theo môn đã làm

Có 31 mẫu ở 6 nhóm. Toán: phân số/căn/mũ/hệ, công thức mở rộng. Lý: vận tốc/Newton/Ohm/công suất/động năng/sóng, có đơn vị và điều kiện. Hóa: chất/ion/phản ứng/thuận nghịch/mol/nồng độ. Sinh: ADN/nguyên phân/phép lai/bảng Punnett. Văn: ngữ liệu/thơ/câu hỏi/dàn ý; nguồn do người dùng điền. Anh: reading/cloze.

Mẫu không cần AI để nhập. Từ trang trống, Chèn sẽ tạo câu đầu; một undo phục hồi trạng thái trống. Công thức cũ vẫn sửa được; hệ và phản ứng nhận diện được sẽ mở thành các ô tương ứng. Các cấu trúc phức tạp khác giữ nguyên trong MathLive hoặc mục Nâng cao.

## Kiểm tra đã hoàn tất

- **74/74 Node:** logic và xuất/nhập cũ + 7 ca mới về thư viện, chuyển mẫu, tìm kiếm, hóa, ngữ liệu an toàn/giữ dòng và bảng lai.
- **13/13 Workbench UI:** pipeline/patch/undo/offline/chia sẻ/tài khoản/phục hồi, AI fixture ghi nhãn.
- **11/11 Studio UI:** sửa đáp án/barem, công thức, bảng, hình kéo điểm, hủy/hoàn điểm, Word và viewport nhỏ, AI fixture.
- **12/12 Authoring UI:** các thao tác trực quan/sáu môn, sửa MathLive bằng bàn phím thường, lưu/hoàn tác/reload, Ctrl+K/tập trung, viewport nhỏ; **không gọi AI**, không phát sinh yêu cầu HTTP ra ngoài localhost.
- Đã xem ảnh desktop, form hệ/Hóa/Văn, viewport 390×844 và PDF mẫu. MathLive không được tải ở lượt mở workspace ban đầu trong lần đo kiểm, chỉ khi mở bộ nhập. Số thời gian quan sát trong JSON là một lần chạy trên máy kiểm thử, không đại diện hiệu năng mọi máy và không phải chỉ số Core Web Vitals.

Báo cáo máy: kiem_thu_Node_5.0.txt, kiem_thu_workbench_UI_5.0.json, kiem_thu_Studio_UI_5.0.json, kiem_thu_Mach_UI_5.0.json. Không dùng các ca UI fixture để khẳng định chất lượng AI đa môn.

## Giới hạn và bước đánh giá người dùng

Chưa có dựng phân tử/giải Hóa tổng quát, kiểm thứ nguyên Lý tổng quát, bộ mô phỏng Sinh hoặc chứng nhận GDPT cho mọi mẫu. Bộ soạn chữ không tự cung cấp ngữ liệu bản quyền. Giới hạn cộng tác/cloud/thanh toán/phân trang của MVP trước vẫn được ghi trong README.

Kịch bản dùng thử đề xuất: giáo viên tạo một hệ hai phương trình, một phản ứng có điều kiện, chèn một đoạn thơ có nguồn, sửa một công thức có sẵn, rồi xuất Word. Quan sát tỷ lệ hoàn thành không cần trợ giúp, số lần mở mã, lỗi còn lại và thời gian mỗi nhiệm vụ; so sánh cùng nhiệm vụ trên bản 4.0. Cần thực hiện với giáo viên thực tế trước khi khẳng định mức giảm thời gian.
