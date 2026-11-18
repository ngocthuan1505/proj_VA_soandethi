# Nghiệm thu kỹ thuật bản 13

SHA-256 của ZIP app bên trong gói là `248d591cfed560071602662fc13e52642ed99d380eed1419686790a0f186f0c7`. Tải gói và đối chiếu chi tiết từng ca ở `BANG_IT_01_DEN_11.md` trong [bản thử 13](https://github.com/ngocthuan1505/proj_VA_soandethi/releases/tag/ban-thu-13).

- Đã qua các luồng kiểm IT-01…11 trên bản Python 13. Máy QA đã cài sạch, soạn, lưu, tải lại và mở đủ bốn bản xuất Word/PDF cho học sinh và giáo viên. Thuận xác nhận cài được, chưa có xác nhận mở bản xuất trên máy vừa cài.
- Gemini thật sinh 8 câu thuộc 4 dạng, tổng 10 điểm, sau 2 vòng với 7 lời gọi. App chuyển sang kết nối dự phòng đã cấu hình khi kết nối chính trả 429. Kết quả dừng ở chờ duyệt. Lượt thử Ollama Qwen3 4B chạm giới hạn trả lời và app giữ nguyên nháp.
- Rà đề mẫu phát hiện câu 8b chỉ đủ dữ kiện để hỏi cận trên 75 ô theo diện tích. Không dùng đáp án gốc để khẳng định xếp được 75 ô. Khi demo, hỏi diện tích còn lại và số ô không thể vượt quá nếu chỉ xét diện tích.
- Khi báo lỗi, ghi mã IT nếu có, hệ điều hành, bước tái hiện, kết quả mong đợi và thực tế. Bản thử đang chờ nghiệm thu Final.
