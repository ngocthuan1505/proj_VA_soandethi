# Cải thiện chọn vùng, sửa đề và chat — 19/10/2026

## Kết quả

- Ánh xạ vị trí từ TipTap sang văn bản đúng với chữ lặp, công thức nguyên tử, xuống dòng và bảng; công thức lặp lấy đúng vị trí thực.
- Chọn/caret trong lời giải, phương án hoặc từng bước barem mang đúng trường và chỉ số. Bỏ chip xóa cả ngữ cảnh dự phòng. Vùng cũ không còn khớp bị chặn.
- “Viết lại bài 2”, “sửa câu 2”, “rút gọn”, “câu khác khó hơn”, “sửa vào đi” được hiểu là chỉnh sửa. Tạo đề mới vẫn có luồng cấu trúc riêng.
- Tên bài trong chat ưu tiên hơn vùng cũ; hỗ trợ danh sách/khoảng và cả đề. Kiểm tra đáp án giữ nguyên đề và phương án.
- Chế độ Chỉ hỏi / Đề xuất sửa / Tự hiểu yêu cầu. Chat nhận đề hiện tại và tối đa 6 tin gần đây; luồng sửa cũng có lịch sử tham chiếu, môn và lớp.
- Giới hạn patch theo trường, bước, điểm và phần chữ ngoài vùng. Tái kiểm tra ngay trên frontend trước xem trước/áp dụng; AI sửa quá vùng được yêu cầu làm lại tối đa một lượt phía client.
- Patch giữ các đoạn/định dạng/công thức ngoài chỗ đổi. Cả cụm patch áp dụng nguyên vẹn hoặc không đổi gì nếu bảo toàn cấu trúc thất bại. Không tăng phiên bản cho khối không đổi.
- Hoàn tác khôi phục cả nội dung và rich document. Hỏi AI từ công thức đóng sạch hộp nhập. Lỗi chat giữ lại yêu cầu để người dùng sửa/gửi lại.

## Bằng chứng

- `kiem_thu_Node_chon_sua.txt`: **94/94** kiểm tra Node.
- `kiem_thu_chon_sua_chat.json`: **9/9** luồng trình duyệt mới, mô hình giả lập trên tài liệu dùng một lần. Có ca giả lập server trả patch sửa quá vùng để kiểm tra chặn ngay trên frontend đang dùng.
- `kiem_thu_workbench_sua_chon.json`: **13/13** luồng hồi quy trình duyệt, AI giả lập.
- `kiem_thu_Studio_UI.json`: **11/11** luồng editor, barem, công thức, nhập Word, hình và mobile, AI giả lập.
- `kiem_thu_AI_sua_thuc_te.json`: gọi **Qwen3:8b trên GreenNode thật** với bài mẫu không lưu. Đổi đúng số 11 thành 15 trong `2x+3=11`, cập nhật lời giải `x=6` và hai bước barem, giữ 2 điểm; **6,17 giây** trong lần thử này.
- `kiem_thu_chat_thuc_te.json`: chat AI thật giải thích đúng vì sao trừ 3 trước khi chia 2; **7,24 giây** trong lần thử này. Không sửa tài liệu.
- `kiem_thu_AI_khi_sua.json`: GreenNode kết nối được; Gemini vẫn có khóa trong phiên và model đã chọn vẫn giữ nguyên. Không ghi khóa vào báo cáo/gói.

Không dùng các đề người dùng đang lưu làm dữ liệu thử AI; không thay kho đề để kiểm thử. Hai lần gọi AI thật dùng nội dung phương trình tự tạo. Kiểm thử giả lập xác nhận cơ chế UI/phạm vi; không phải đánh giá chất lượng mọi môn của mô hình.

## Cách dùng

1. Bôi đen đúng chữ → Hỏi AI; kiểm tra chip tên bài/phần/bước.
2. Gõ yêu cầu tự nhiên, hoặc ghi rõ “Viết lại đề bài 2”.
3. Chọn Chỉ hỏi nếu chỉ cần giải thích. Với sửa, xem thay đổi rồi Áp dụng; dùng Hoàn tác khi cần.
4. Gỡ chip để bỏ ngữ cảnh. Nếu đã sửa tay/hoàn tác làm vùng cũ đổi, chọn lại đoạn.

## Triển khai và giới hạn

Các module frontend được phục vụ trực tiếp từ `outputs/app`; nạp lại trang để nhận bản mới. Không khởi động lại server đang giữ khóa trong bộ nhớ. Frontend kiểm tra lại patch trước áp dụng, kể cả khi server hiện tại còn nạp bản kiểm tra cũ; ca trình duyệt thứ 9 xác nhận cơ chế này. Lần khởi động server tiếp theo sẽ nạp thêm kiểm tra mới trong module blocks dùng chung. Không thay tuyến model: Sinh/Sửa/Chat dùng GreenNode Qwen3:8b, Kiểm dùng Gemini đã cấu hình.

Một số thay đổi xuyên cấu trúc bảng phức tạp cần chọn riêng ô/đoạn để giữ định dạng. Vùng chọn qua hai editor không được gộp thành một phạm vi. Chưa tuyên bố AI luôn giải đúng; kết quả đề/lời giải vẫn cần người soạn duyệt.
