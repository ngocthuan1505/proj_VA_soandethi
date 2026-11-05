# Nghiên cứu rồi tự chọn việc, có thể làm chung

Chỉ chốt nhóm **3 UI + 5 backend**, chưa gán cứng từng người một chuyên môn. [Danh sách thành viên](ROLES.md). UI-1/UI-2/BE-2… là mã mảng, không phải người. Quyền repo/Project không thay đổi khi chọn việc; chỉ vận hành GreenNode thuộc riêng Thuận.

## Chọn trên GitHub như thế nào?

1. Mở [bảng task](https://github.com/users/ngocthuan1505/projects/1/views/1), đọc menu dưới đây và thử [demo](CHAY_VA_TEST_DEMO.md). Xem source/fixture trong task, đừng chọn chỉ vì tên nghe quen.
2. Nghiên cứu vấn đề, thử một luồng/mẫu nhỏ và ghi đề xuất: giữ gì từ demo, cải thiện gì, phương án/trade-off và điều chưa rõ. Chưa cần chọn công nghệ ngay; không đổi framework/tải model lớn/mua API chỉ để nghiên cứu.
3. Comment đăng ký **cá nhân hoặc nhóm**: thành viên, Wxx muốn làm, đầu ra và cách chia PR/test/review. Cả ba bạn UI có thể cùng nhận một mảng hoặc một luồng xuyên ba mảng.
4. Trao đổi với người đang nhận/consumer rồi thêm Assignees đúng người làm. Không tự gỡ người đã nhận thật. Hạn chế một việc đang làm mỗi người; không bắt một người giữ độc quyền một mảng. Đổi mảng thì bàn giao phần dở.
5. Báo tiến độ theo task/Wxx, task/Txx và expected/actual. Chưa đăng ký thì task mở để chọn, không phải thiếu danh tính. Không cần sửa roster để nhận việc.

## Menu định hướng - không phải phân công sẵn

| Mảng | Mảng này làm gì? | Nên nghiên cứu/thử, đầu ra gợi ý | Đọc task và đăng ký |
|---|---|---|---|
| UI-1: Shell, kho đề, tài khoản | Giúp giáo viên tạo/mở/tìm/lưu đề và biết trạng thái lưu. | Thử kho rỗng/lỗi/hết phiên, Tab/mobile; đề xuất luồng và ảnh rồi chia PR. | [001 #1](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/1) · [002 #9](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/9) · [003 #17](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/17) |
| UI-2: Editor, công thức, bảng/hình | Giúp soạn không cần nhớ LaTeX; lưu/undo giữ richDoc và định dạng. | Thử mẫu/MathLive, node trùng, bảng/hình, reload và Word/PDF; đề xuất fixture/UX rồi cải thiện editor. | [001 #2](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/2) · [002 #10](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/10) · [003 #18](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/18) |
| UI-3: Trợ lý, vùng chọn, diff | Giúp hỏi khác sửa, xem AI định đổi gì và xác nhận/hủy rõ. | Chạy selection/workbench fixture, thử stale/quá vùng/cancel/scroll; đề xuất state/contract mock rồi nối Python. | [001 #3](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/3) · [002 #11](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/11) · [003 #19](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/19) |
| BE-1: AI/routing/validation | Chọn rule/truy xuất/model; kiểm schema/evidence và sửa an toàn. | Đọc adapter cũ, thử thiếu nguồn/sai schema/stale; đề xuất contract/validator Python và PoC. AI code có thể làm chung; server chỉ Thuận. | [001 #4](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/4) · [002 #12](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/12) · [003 #20](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/20) |
| BE-2: API/auth/quyền | Nối UI với FastAPI, kiểm owner/session/input và confirm đúng version. | Inventory route, thử hai user/request sai quyền; đề xuất OpenAPI/error matrix rồi router/pytest. | [001 #5](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/5) · [002 #13](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/13) · [003 #21](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/21) |
| BE-3: Database/version | Lưu đúng ID/revision/richDoc, migrate/restore không mất dữ liệu. | Đọc KV cũ/ADT, thử conflict/rollback/checksum; đề xuất ADR/schema/repository và fixture before-after. | [001 #6](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/6) · [002 #14](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/14) · [003 #22](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/22) |
| BE-4: Import/OCR/export | Đọc nguồn có locator, báo chỗ không chắc, xuất đúng bản và quyền. | Tạo file synthetic hợp lệ/hỏng, thử công thức/bảng/OCR; đề xuất ma trận định dạng và document service Python. | [001 #7](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/7) · [002 #15](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/15) · [003 #23](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/23) |
| BE-5: Job/tích hợp/QA | Theo dõi/hủy/retry an toàn, không ghi kết quả muộn/lặp; giữ regression/CI. | Thử stream đứt/cancel/duplicate; đề xuất event/state/giới hạn rồi job Python và test tích hợp. | [001 #8](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/8) · [002 #16](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/16) · [003 #24](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/24) |

Mỗi mảng có ba giai đoạn 001 baseline/contract, 002 triển khai/tích hợp, 003 nghiệm thu. Đọc phụ thuộc và tiêu chí trước khi bắt đầu; 150 bước/90 ca kiểm là kế hoạch để chọn có căn cứ, không phải kết quả đã đạt.

## Làm chung cả ba bạn UI

Ví dụ cả ba cùng chọn luồng **sửa công thức bằng chat**: cùng đọc/đề xuất; một bạn lo thao tác editor, một bạn lo ngữ cảnh/diff, một bạn chuẩn bị fixture/test. Nhóm tự đổi/luân phiên cách chia này, không phải phân công mới. Ghi Wxx ai làm, đầu mối mỗi PR và người kiểm lại khác người viết; tránh cùng đè một file. Được cùng làm nhiều mảng trong một luồng, không cần ba bạn bị chia cố định ba chuyên môn.

Backend cũng nhận cá nhân/nhóm giữa các mảng. Ai cũng có thể nghiên cứu/viết/test AI hoặc worker local; chỉ thao tác hạ tầng thật do Thuận. Python vẫn là core/backend theo yêu cầu môn.

## Comment đăng ký dùng ngay

```text
Đăng ký cá nhân / nhóm:
Thành viên GitHub:
Mảng hoặc luồng muốn nghiên cứu:
Đã đọc/thử demo/source/fixture nào:
Đề xuất giữ/cải thiện, phương án và điều chưa rõ:
Muốn nhận task/Wxx:
Ai làm bước nào, đầu mối PR, người test/review:
Đầu ra dự kiến và ca Txx để chứng minh:
Phụ thuộc/cần trao đổi với ai:
```

Không thêm cả ba assignee cho đẹp mà không chia việc. Có thể nghiên cứu chung trước, chốt người làm sau. [Backlog kỹ thuật](BACKLOG.md), [hồ sơ môn](../course/BACKLOG_CT.md), [hợp đồng/gates](KE_HOACH_TICH_HOP.md) và [báo tiến độ](BAO_CAO.md) giữ hướng dẫn chi tiết; hồ sơ CT là việc chung, không giao cứng một người viết thay cả nhóm.
