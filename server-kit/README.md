# GreenNode — AI riêng trong ProJ_VA

Đã cài Qwen3:8b chạy CUDA trong /network-volume/ProJ_VA/soande_ai, nối app qua Jupyter Contents API. Không mở thêm cổng công khai hoặc sửa Jupyter toàn hệ thống. Mọi model, runtime, cache CUDA, tệp tạm, log và hàng đợi ở trong ProJ_VA. Không dùng mô hình/tệp của dự án khác.

Server cấp MIG 2g.20gb trên H100, không phải toàn bộ 80 GB của card. Đã kiểm CUDA hoạt động và bộ nhớ giảm từ khoảng 20,9 xuống 13,3 GB trống khi nạp model. Trọng số 5,2 GB kiểm SHA-256 theo manifest; runtime llama.cpp v0.7.0 biên dịch bằng CUDA 12.4.

- setup_ai.py: tải/kiểm model và biên dịch. Không chạy đồng thời nhiều bộ cài.
- start_ai.sh: khởi động worker và model loopback 11436; dùng bash, tệp phải giữ xuống dòng LF.
- worker.py: xử lý tác vụ sinh/sửa/giải lại từ jobs; không thực thi lệnh trong nội dung. Có khóa file ngăn worker trùng.
- stop_ai.py: dừng đúng PID worker/model thuộc thư mục dự án; không đụng tiến trình khác.
- start_after_setup.py: tiếp tục khởi động sau một bộ cài đang chạy.
- preflight.py: kiểm tra chỉ đọc, khóa thư mục làm việc vào ProJ_VA.

Khởi động lại sau khi container/server reboot:

    cd /network-volume/ProJ_VA
    bash soande_ai/start_ai.sh

Dừng riêng AI của dự án:

    python -B soande_ai/stop_ai.py

Chưa cài tự khởi động toàn hệ thống. Giữ server và worker chạy khi dùng app. Tệp yêu cầu được worker xóa sau xử lý, tệp trả lời được app xóa sau nhận; nếu app đóng giữa chừng, tệp trả lời có thể còn trong jobs, không đưa thư mục này vào gói chia sẻ.

Ở Kết nối AI chọn GreenNode, nhập URL JupyterLab và qwen3:8b, kiểm kết nối rồi phân việc. Token Jupyter chỉ cần nếu máy chủ yêu cầu. Không cần API key Gemini/GPT/Claude cho model riêng. Giữ bước đồng ý khi gửi tài liệu từ máy lên GreenNode.

Nguồn runtime/model: https://github.com/ggml-org/llama.cpp và https://ollama.com/library/qwen3:8b . Xem README app cho hướng dẫn đầy đủ.
