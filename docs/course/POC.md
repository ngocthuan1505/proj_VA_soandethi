# PoC — sinh bộ câu theo ma trận và tự kiểm

Ưu tiên hiện tại theo bàn giao lý thuyết và [CT-04 #29](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/29) là sinh cả bộ theo ma trận, tự gọi công cụ kiểm, nhận lỗi rồi sửa và kiểm lại trong giới hạn.

Đã có [công cụ đối chiếu log](../../scripts/kiem_tra_log_poc.py). Lượt structured Qwen2.5 3B v5 có phản hồi lỗi trong request tiếp theo, bộ câu thay đổi và kiểm lại nhưng vẫn dừng ở `attempt_limit`. Lượt Qwen2.5 1.5B v5 nhận phản hồi rồi nộp nguyên bộ cũ. Các lượt ở những bản thử khác nhau được giữ riêng, chưa dùng để tính tỷ lệ chung hoặc kết luận cách nào tốt hơn.

Để rà nội dung đầu ra thật, mỗi người dùng bản riêng của [phiếu tự giải và nhận định mức](poc-ra-doc-lap/1_TU_GIAI_VA_NHAN_DINH.md), ghi và giữ lại kết quả rồi mở [đáp án/lời giải model để đối chiếu](poc-ra-doc-lap/2_DOI_CHIEU_SAU_KHI_TU_GIAI.md). Phiếu gồm bốn câu ở lượt nộp kiểm thứ hai của v5 Qwen2.5 3B, có [mã băm và vị trí nguồn](poc-ra-doc-lap/DOI_CHIEU_NGUON.json). Đây là phiếu trống đang chờ người rà, chưa có bộ đề đạt chất lượng được duyệt.

## Kế hoạch sửa vùng đã đề xuất trước đây

Trạng thái: **kế hoạch, chưa có kết quả thí nghiệm này**. Nguồn: Topic 4 trang 31, 36–40; Topic 6 trang 7–8, 14, 17. BE-1 điều phối, UI-3 và BE-5 hỗ trợ; mọi thao tác GreenNode do Thuận thực hiện sau khi có server.

Proposal cũ đã có kế hoạch/phạm vi PoC gồm đọc nguồn, truy xuất, sinh câu có căn cứ, kiểm và rút trích. Câu hỏi sửa vùng dưới đây là **ứng viên nhóm cần chốt**, không tự thay toàn bộ kế hoạch đã làm. Trong [hồ sơ đã đối chiếu](HO_SO_DA_CO.md) chưa thấy bộ kết quả thực nghiệm đủ để kết luận CT-04 hoàn thành; demo kỹ thuật cũ cần chọn input/output/metrics phù hợp mới dùng làm bằng chứng PoC này.

## Câu hỏi rủi ro

“Từ một đề có công thức và yêu cầu sửa đúng một câu, hệ thống có tạo đề xuất được kiểm phạm vi/revision, cho giáo viên xem trước, và bảo toàn các câu khác không?” Tách hai giả thuyết: bộ kiểm Python chặn thay đổi sai; model thật tạo đề xuất đủ chất lượng. Fixture chỉ kiểm giả thuyết đầu, không chứng minh model giải toán đúng.

## Thí nghiệm dự kiến

1. UI-2/BE-4 tạo bộ 12 đề tự viết, gồm ít nhất Toán/Lý/Hóa và Văn/Anh, có công thức/bảng ở một số mẫu. BE-1/UI-3 viết yêu cầu sửa có đích xác định, gồm cả yêu cầu mơ hồ cần hỏi lại. Đây là đề xuất bộ mẫu của nhóm, không phải số lượng thầy bắt buộc.
2. BE-3 lưu snapshot chuẩn và revision; BE-2 chốt contract. BE-5 xây các phản hồi fixture: hợp lệ, sai schema, sửa ngoài vùng, sai job, stale, duplicate và sau cancel.
3. Chạy validator Python và UI preview/undo; so sánh hash hoặc cấu trúc mọi khối ngoài vùng, lưu kết quả trên dữ liệu mẫu. Ghi commit và lệnh chạy.
4. Khi có backend/model thật, Thuận chạy cùng bộ mẫu với model/params/provenance được ghi nhận, không bật fallback trả phí. Giáo viên/người đánh giá kiểm câu trả lời và lời giải; tách tiêu chí hình thức với đúng kiến thức.
5. Tổng hợp lỗi, phương án khác và quyết định tiếp tục/chỉnh thiết kế. Thất bại cũng là bằng chứng PoC; không bỏ ca lỗi khỏi báo cáo.

## Ngưỡng đề xuất cần chốt trước chạy

- An toàn: **0** lần ghi ngoài vùng, mất công thức hoặc ghi kết quả stale/cancel; mọi phản hồi sai cấu trúc phải bị chặn. Một lỗi loại này là fail, không lấy trung bình che đi.
- Chất lượng model: nhóm và người duyệt chốt số ca cần đạt trên 12 mẫu trước khi chạy; chưa có ngưỡng được phê duyệt, không tự ghi “80% chính xác”.
- Ghi thời gian chờ, số retry và giới hạn tài nguyên thực đo; timeout cần có giá trị cụ thể trong contract, chưa suy ra từ GPU cũ.

| ID mẫu | Commit/môi trường/model hoặc fixture | Kỳ vọng | Ngoài vùng giữ nguyên? | Kiến thức đúng? ai duyệt? | Kết quả + thời gian + bằng chứng |
|---|---|---|---|---|---|
| Chưa chạy | — | — | — | — | — |

## Điều kiện xong

Có script/notebook/test chạy lại được, bộ mẫu hợp lệ, ngưỡng đã chốt, kết quả gồm cả lỗi, kết luận yes/no/chưa đủ bằng chứng và kế hoạch sửa. Có thể nộp script/ảnh/video ngắn minh chứng; màn hình login hay danh sách model không chứng minh được giả thuyết này.

Nếu chưa có model/server: hoàn thành bộ thử và báo kết quả fixture riêng, để **phần model thật đang chờ**; tìm model local phù hợp bằng quyết định của Thuận, không nhận tài khoản server của người khác.
