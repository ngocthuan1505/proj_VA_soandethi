# Cây công việc và lộ trình

Nguồn: Topic 1 trang 16, 36–38; Topic 3 trang 8–9, 17–18, 42. Cây dưới phân rã **vấn đề → chức năng → đầu ra**, sau đó mới gắn người; không dùng “UI/backend” làm toàn bộ phân tích vấn đề.

```mermaid
flowchart TD
  A[Giúp giáo viên chuẩn bị đề kiểm tra có thể kiểm chứng] --> B[Hiểu vấn đề và kiểm chứng giá trị]
  A --> C[Biên tập và quản lý đề]
  A --> D[Đề xuất sửa bằng AI an toàn]
  A --> E[Chuyển đổi tài liệu và kiểm bản xuất]
  A --> F[Kiểm thử và đánh giá]
  B --> B1[CT-01 Phỏng vấn và Problem Brief]
  B --> B2[CT-02 Cây phân rã và baseline kế hoạch]
  C --> C1[UI-1 + BE-2 Kho đề và phân quyền]
  C --> C2[UI-2 + BE-3 Nội dung, lưu và phiên bản]
  C --> C3[CT-03 Mô hình và hợp đồng]
  D --> D1[UI-3 + BE-1 Yêu cầu và preview]
  D --> D2[BE-5 Job, hủy và kết quả cũ]
  D --> D3[CT-04 PoC sửa đúng vùng]
  E --> E1[BE-4 Import và kiểm nguồn]
  E --> E2[UI-2 + BE-4 Word, PDF và công thức]
  F --> F1[CT-05 Thuật toán và dry run]
  F --> F2[CT-06 Kiểm người dùng và quyết định cải tiến]
  F --> F3[BE-5 Tổng hợp nghiệm thu Python]
```

Các lá chỉ chức năng vẫn còn là **gói việc**. 24 issue `UI/BE-*-001/002/003` chia mỗi gói thành đặc tả → triển khai → nghiệm thu; trong issue có các bước nhỏ, input/output và điều kiện xong. Mỗi bước gán đúng một người; nếu không hoàn thành được trong khoảng một ngày thì tách tiếp issue, liên kết cha/phụ thuộc và thêm vào bảng. Chưa có ước lượng ngày công thật từ thành viên; không coi cây này là lịch cam kết.

## Mẫu nhận diện pattern cho từng lá

Ghi `mục tiêu → pattern → công cụ đã có → đầu vào → đầu ra → owner → xong khi`. Ví dụ sửa vùng: validation + optimistic concurrency; Pydantic/repository Python; input có revision/vùng; output là đề xuất đã kiểm, chỉ ghi sau consent; BE-1/2/3 chia interface; xong khi ca stale/ngoài vùng/hủy không ghi đề. AI sinh nội dung là phần xác suất, không thay quy tắc kiểm quyền/version.

## Lộ trình tương đối, chưa đặt ngày nộp

| Giai đoạn | Đầu ra môn | Công việc kỹ thuật đi kèm | Điều kiện chuyển |
|---|---|---|---|
| Phân tích | CT-01 Problem Brief + 3 người dùng, baseline công cụ | UI/BE task 001 ghi hành vi hiện có | Có bằng chứng, phạm vi/metrics được nhóm duyệt |
| Phân rã và trừu tượng | CT-02/03 cây 3 cấp, model, contracts | Chốt API/DB/fixture, mock UI | Các phần ghép cùng field/type/units; PoC đã chọn |
| Proposal + PoC | CT-04 một thí nghiệm rủi ro nhất | BE-1 + UI-3 + BE-5, dữ liệu mẫu | Có kết quả thật hoặc kết luận chưa đủ bằng chứng, không thay bằng login đẹp |
| Thuật toán và MVP | CT-05 pseudocode/flowchart/dry run; core test được | Task 002, Python từng slice, UI tích hợp | Tạo/sửa/lưu/xuất và test vào Python; chưa giả full migration |
| Nghiệm thu và đánh giá | CT-06 phản hồi, trade-off, báo cáo/demo | Task 003 và release checklist | Không còn blocker ở phạm vi demo; có giới hạn và mục tiêu vòng sau |

Tuần 1–11 trong Topic 1 là khung môn; Thuận xác nhận tuần hiện tại, ngày nộp và lịch nhóm trước khi thêm deadline vào milestone. Không đổi assignee/tiến độ sẵn có để khớp lịch minh họa.

## Trách nhiệm tài liệu chung

UI-1 điều phối Problem Brief/flow; UI-2 đóng góp mẫu công thức và tính đúng bản in; UI-3 đóng góp giả thuyết chat/preview; BE-1 PoC AI và runbook riêng; BE-2 hợp đồng/thuật toán; BE-3 model/version/restore; BE-4 import/export; BE-5 CI, test log và báo cáo tổng hợp. Người điều phối tổng hợp, không làm thay phần bằng chứng của bảy người còn lại.

Thiếu GreenNode không chặn phỏng vấn, wireframe, OpenAPI, DB local, thuật toán hay fixture. Chỉ ghi chặn model thật/triển khai thật trong phần cần server, chuẩn bị code/runbook để Thuận tự chạy sau.
