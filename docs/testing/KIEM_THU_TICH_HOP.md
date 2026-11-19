# Kế hoạch nghiệm thu xuyên module

Đây là **test cần làm cho candidate Python**, không phải kết quả đã chạy. Baseline demo 05/11 ở [báo cáo riêng](BASELINE_2026_11_05.md); không chuyển nhãn PASS Node sang Python. BE-5 điều phối; từng owner cung cấp fixture/expected và một reviewer khác kiểm.

## Dữ liệu và cách ghi kết quả

- Tạo ít nhất hai owner và một guest, đề richDoc nhiều version, câu trùng text nhưng khác UUID, công thức/bảng/hình và ngữ liệu nhiều dòng.
- Nguồn synthetic có trang/slide/locator, bản sửa version, file hỏng/quá giới hạn và đoạn chứa lệnh giả. Có expected extraction, ID/checksum và quyền sử dụng.
- AI/job fixture hỗ trợ valid/invalid/schema/refusal/rate-limit/timeout/stale/quá vùng/cancel/duplicate/out-of-order/disconnect; kết nối chỉ loopback trong CI.
- Ghi mỗi ca: `ID / commit / môi trường / config / fixture / bước tái hiện / expected / actual / đạt-không đạt-chưa chạy / log hoặc ảnh / bug / reviewer / lần retest`.
- Giới hạn concurrency/size/timeout do nhóm chốt ở M1 và ghi đơn vị/config trước đo. Không tự lấy số minh họa làm SLA; server/model thật chỉ owner chạy riêng bằng dữ liệu được phép.

## 11 kịch bản bắt buộc xem xét

| Ca / UC | Fixture và hành trình | Kết quả phải chứng minh, gồm ca lỗi | Owner phối hợp / task nghiệm thu |
|---|---|---|---|
| IT-01 / UC-01 | Hai tài khoản, tạo/mở/tìm/đổi tên; guest và session hết hạn | Kho tách biệt; server từ chối đổi ID; nháp của A không sang B | UI-1/BE-2/3; UI-1-003, BE-2-003 |
| IT-02 / UC-02 | Upload nguồn hai trang/slide và file hỏng/giả đuôi/quá lớn | Nội dung/locator/version khớp expected; quyền/giới hạn đúng; cleanup lỗi | BE-4/2/3; BE-4-003, BE-2-003 |
| IT-03 / UC-03 | Cấu trúc/điểm/ma trận, preference nháp/đã xác nhận và yêu cầu mơ hồ | Đếm/điểm/routing minh bạch; chỉ preference đã duyệt được áp; hỏi lại không phá bản đề | UI-1/3, BE-1/2/3; UI-1-003, UI-3-003 |
| IT-04 / UC-04 | Tạo request→job→SSE→đề từ nguồn; thiếu consent/provider và output hỏng | Kết quả schema/nguồn/owner đúng hoặc báo thiếu; không trả thành công giả/fallback trả phí | BE-1/5/2, UI-3; BE-1-003, UI-3-003 |
| IT-05 / UC-05 | Chèn/sửa công thức, bảng/hình/ngữ liệu→lưu Python→reload→undo | RichDoc/UUID/định dạng giữ, IME và node trùng đúng; conflict không last-write-wins ngầm | UI-2/BE-3/2; UI-2-003, BE-3-003 |
| IT-06 / UC-06 | Hỏi→proposal→diff→confirm; version đổi giữa chừng, sửa quá vùng, confirm lặp | Hỏi không ghi; chỉ transaction đúng scope/version được lưu một lần; undo khôi phục cả cụm | UI-3/2, BE-1/2/3/5; UI-3-003, BE-2-003 |
| IT-07 / UC-07 | Giải/check độc lập rồi duyệt; đổi nội dung sau duyệt hoặc đáp án AI bất đồng | Tách ba trạng thái; invalidation đúng version; thiếu evidence không tự gắn đúng | BE-1/2/3, UI-3; BE-1-003, BE-2-003 |
| IT-08 / UC-08 | Đổi dữ kiện có bảng/hình/câu phụ thuộc, gây lỗi giữa transaction rồi undo | Chỉ phần liên quan cập nhật, unit/ID đúng; rollback không để nửa cũ nửa mới | BE-3/2/1, UI-2; BE-3-003, UI-2-003 |
| IT-09 / UC-09 | So sánh/chọn ngữ liệu version A/B, sửa câu, thay nguồn gốc | Giữ đoạn đã chọn/nguồn do người dùng nhập; locator lỗi hoặc version đổi phải yêu cầu xem lại | BE-3/1/4, UI-2; BE-4-003, UI-2-003 |
| IT-10 / UC-10 | Xuất teacher/student Word/PDF/HTML→mở thật→share→revoke | Không lộ answer/chat/key trong student; công thức sửa được khi hỗ trợ; owner khác/link thu hồi không đọc được | BE-4/2/3, UI-1/2; BE-4-003, BE-2-003 |
| IT-11 / UC-11 | Cancel sát commit, retry/trùng event, disconnect/offline; backup→restore bản sao | Một terminal state, không ghi muộn/lặp; snapshot/ID/checksum còn; thiếu file/rollback lỗi được phát hiện | BE-5/3/1/2, UI-3; BE-3-003, BE-5-003 |

## Kiểm bổ sung trước đề nghị phát hành

1. Tắt Node API, chạy các hành trình trên với Python thật; ghi request/route đã chuyển, không chỉ ảnh UI hoặc mock.
2. Kiểm bàn phím/focus/IME và mobile/desktop trên luồng chính; ghi viewport, trình duyệt và lỗi thực. Chưa có screen reader/usability với giáo viên thì vẫn ghi chưa kiểm.
3. Chạy trong giới hạn tài nguyên đã chốt; khi quá ngưỡng phải từ chối/hàng đợi/timeout theo contract, không treo vô hạn hoặc mất draft. Log đo là dữ liệu, chưa là SLA.
4. Chạy source chứa lệnh giả, tài nguyên sai owner và download/export qua đường dẫn trực tiếp; server vẫn enforce quyền và không lộ secret. Test red-team bằng fixture, không tấn công server thật.
5. Người khác chạy từ clone sạch bằng hướng dẫn; mở bản xuất thực và so artifact. Sai số/giới hạn Word/OCR phải ghi rõ.

## Kiểm lại IT-08 trên FastAPI

Ngày 19/11/2026, với mã bàn soạn tại `5a48a76`, Chrome desktop đã đổi dữ kiện khu vực B trong đề Địa lí mẫu từ 240 lên 300 người. Màn hình xem trước giữ kho cũ. Sau xác nhận, bảng, biểu đồ và bản HTML cùng hiện 300 người. Các câu liên quan giữ ID, tăng phiên bản và bỏ duyệt cũ. Câu ngoài phạm vi giữ nguyên. Sau tải lại, Hoàn tác khôi phục dữ kiện và câu. Một phiên khác ghi trước làm lượt xác nhận bị từ chối bằng HTTP 409 và dữ liệu mới hơn được giữ.

Trong một ca riêng, pytest gây lỗi SQLite ngay sau câu lệnh cập nhật kho. FastAPI trả HTTP 500, rồi lần đọc tiếp theo xác nhận dữ kiện, câu và revision vẫn là bản cũ. Sau khi bỏ lỗi giả lập, gửi lại cùng revision lưu thành công một lần.

Đây là kiểm trên fixture có kho riêng. Phép tính xem trước diễn ra trong trình duyệt, còn FastAPI lưu snapshot theo giao dịch và phiên bản. Chưa có người khác nghiệm thu bản cài. [Script kiểm Chrome](../../scripts/kiem-ui-du-kien.mjs) · [Kiểm rollback FastAPI](../../backend/tests/test_workspace_connection.py)

## Kiểm lại IT-09 trên FastAPI

Ngày 19/11/2026, Chrome so sánh hai bản ngữ liệu tự viết. Mở xem trước giữ kho cũ. Sau xác nhận bản B, nút mở nguồn dẫn đến trang 2 của cùng tài liệu. Câu liên quan giữ ID, đáp án và mất duyệt cũ. Câu ngoài phạm vi giữ nguyên. Sửa phần văn bản trích ở trang 2 làm tài liệu tăng phiên bản, trong khi phần ngữ liệu đã chọn và nội dung trang 1 vẫn giữ nguyên khi tải lại ở khung 390 × 844.

Ca FastAPI kiểm ba yêu cầu với cùng ID nguồn. Phiên bản cũ trả 409. Trang không tồn tại trả 404. Cả hai lượt đều dừng trước model. Yêu cầu đúng phiên bản và trang 2 nhận trích dẫn từ trang 2 của fixture.

Lượt kiểm dùng Chrome mô phỏng kích thước điện thoại và phản hồi model mẫu. [Script kiểm Chrome](../../scripts/kiem-ui-nguon-ab.mjs) · [Kiểm trang và phiên bản trên FastAPI](../../backend/tests/test_workspace_check.py)

## Kiểm lại phần khôi phục của IT-11

Ngày 19/11/2026, Chrome và FastAPI chạy ở chế độ tài khoản với kho thử riêng. Tải bản sao bằng giao diện, tạo thêm đề rồi khôi phục. Lần tải lại giữ đúng ID, lịch sử và nội dung tệp nguồn theo từng byte. Xem trước hoặc đóng hộp xác nhận trước lúc gửi yêu cầu đều giữ nguyên kho. Một cửa sổ khác ghi sau bước xem trước làm FastAPI từ chối khôi phục với 409. Bản sao thiếu tệp tham chiếu dừng ngay khi kiểm bản sao. JSON hỏng được báo lỗi trước khi gửi.

Ở viewport 390 × 844, nút xác nhận lấy được focus bằng bàn phím và nằm trong khung. Escape đóng bản xem trước và giữ kho. Kiểm hồi quy Python riêng bao gồm rollback lỗi ghi, chủ sở hữu, đề xuất cũ sau khôi phục, hủy khi trình duyệt ngắt và phát lại xác nhận sinh. Ca này dùng model mẫu và chưa kiểm toàn bộ IT-11 trên một gói cài. [Script kiểm Chrome](../../scripts/kiem-ui-khoi-phuc.mjs) · [Kiểm rollback khôi phục](../../backend/tests/test_workspace_backup.py)

## Kiểm lại IT-01 với hai tab và hai tài khoản

Ngày 19/11/2026, Chrome tạo, đổi tên, tìm và mở đề với tài khoản A. Tab khác trong cùng hồ sơ trình duyệt đăng nhập B và không tìm thấy đề của A. Lệnh đăng xuất hoặc lưu nháp từ tab A cũ nhận 409. Kho và phiên B còn nguyên sau tải lại. Khách bị từ chối mở kho.

Giao diện gắn mã kho vào các yêu cầu API của bàn soạn. FastAPI kiểm mã kho trước khi chuyển tới route tài khoản, kho, AI, xuất đề hoặc chia sẻ. Pytest riêng kiểm thêm phiên hết hạn và quyền của từng tài khoản. Lượt Chrome dùng kho thử tại máy. [Script kiểm hai tab](../../scripts/kiem-ui-kho-nhom.mjs) · [Kiểm quyền và phiên](../../backend/tests/test_team_workspace.py)

Ở viewport 390 × 844, ca IT-01 còn kiểm nút mở kho, ô tìm và nút tạo đề bằng Tab. Khi không có đề khớp, kho hiển thị thông báo trong vùng trạng thái. Dùng Escape trả tiêu điểm về nút mở kho. Tìm với chữ hoa và khoảng trắng ở hai đầu vẫn nhận đúng đề. Ca này chạy bằng Chrome với tài khoản và kho thử.

## Kiểm lại IT-02 khi nhập nguồn và ma trận

FastAPI kiểm được định dạng và dữ liệu ảnh trước bước xin phép OCR. Ảnh hỏng, JPEG mang đuôi PNG và JPEG bị cắt đều dừng trước model, kể cả khi yêu cầu đã đánh dấu cho phép. Tệp vượt 15 MiB bị từ chối và kho giữ nguyên. Ca PPTX qua API giữ số slide và thứ tự 1, 2, 10. Quyền đọc nguồn theo tài khoản được kiểm riêng.

Trong Chrome, PDF hai trang tự tạo đọc tại máy. Chọn trang 2 mở đúng văn bản, tài liệu có phiên bản 1 và tệp gốc khớp từng byte khi tải lại. PNG hỏng báo lỗi, giữ nguyên đề và không mở hộp xin phép OCR. Script dùng tệp `nguon-2-trang.pdf` trong thư mục đầu ra, tạo bằng hàm `pdf("Nguon trang mot", "Nguon trang hai")` trong bộ test. Chất lượng nhận dạng trên ảnh thật chưa được đánh giá trong lượt này. [Ca Chrome](../../scripts/kiem-ui-nhap-nguon.mjs) · [Ca API và ảnh mẫu](../../backend/tests/test_source_documents.py)

## Kiểm lại IT-03 khi gợi ý cơ cấu đề

Chrome gửi yêu cầu Toán lớp 5 mà không điền số câu hoặc thời gian. Khi sửa nội dung yêu cầu, FastAPI nhận bản đã sửa. Bản xem trước có 4 câu và 10 điểm, giữ đề đang soạn. Sau khi bấm dùng gợi ý, kho chỉ cập nhật cơ cấu và yêu cầu làm căn cứ cho lượt sinh. Câu hiện có giữ nguyên.

Pytest kiểm phần hướng dẫn lượt sinh giữ quy tắc có xác nhận, bỏ quy tắc còn nháp và phân đúng 10 điểm. Ca Chrome dùng phản hồi mẫu từ `scripts/chay-fixture-poc.py`. Chưa đánh giá mức phù hợp với bộ sách bằng model thật. [Ca Chrome](../../scripts/kiem-ui-co-cau.mjs) · [Ca FastAPI](../../backend/tests/test_exam_planning.py)

## Kiểm lại IT-04 sinh đề và nối lại trạng thái

Chrome kiểm chat → xác nhận ma trận → đồng ý gửi nguồn → sinh → xem đề xuất. Lượt thử làm mất một phản hồi trạng thái và một phản hồi audit. Nút tải lại tiếp tục theo cùng job, không yêu cầu sinh thêm. Đề xuất giữ được qua tải lại. Bỏ đề xuất giữ kho, còn bấm chấp nhận hai lần chỉ gửi một lần xác nhận.

FastAPI chạy riêng ca **6 câu, 4 dạng, 10 điểm** từ ngữ liệu tự viết. Trace có một vòng không đạt rồi một vòng đạt. Sáu câu có căn cứ trỏ về đúng ID nguồn. Đề cũ giữ nguyên tới khi xác nhận; lần xác nhận tăng một revision. Bộ kiểm riêng còn qua xác nhận SSE phát lại, thiếu quyền, hạn mức, hủy và kết quả đến muộn. Dùng model mẫu và mô phỏng lỗi mạng trong Chrome. Chưa đối chiếu chất lượng model thật trên ứng viên này. [Ca Chrome](../../scripts/kiem-ui-matrix-chat.mjs) · [Ca sáu câu](../../backend/tests/test_exam_planning.py)

## Kiểm lại IT-05 trên bàn soạn

Chrome và FastAPI giữ đúng ID khối, bảng và ảnh khi sửa nội dung, tải lại và hoàn tác trên đề mẫu nhiều trang. Sửa chú thích ảnh làm tăng phiên bản câu và bỏ dấu duyệt cũ. Hoàn tác khôi phục cả ảnh và trạng thái duyệt. Bàn soạn chặn một thao tác sửa cắt ngang ranh giới bảng và chọn đúng công thức thứ hai khi hai công thức giống chữ.

Cũng đã kiểm hai tab lưu cạnh tranh, sửa rồi chuyển chế độ xem, hoàn tác ngay sau gõ và ghép dấu bằng Chrome DevTools Protocol. Ngữ liệu tự tạo và màn hình mobile mô phỏng. Chưa chạy bằng bộ gõ tiếng Việt của người dùng hoặc điện thoại thật. [Ca Chrome](../../tests/ui2-baseline-browser.mjs)

## Kiểm lại IT-06 khi xác nhận sửa qua trợ lý

Chrome dùng chế độ Chỉ hỏi, rồi bôi đen chữ trong câu tự luận có công thức. Xem khác biệt và bỏ đề xuất giữ nguyên câu. Bấm xác nhận hai lần chỉ tăng một phiên bản câu, không đổi công thức, định dạng hoặc các câu khác. Chọn một cụm từ trong bước chấm thứ hai chỉ đổi chữ của bước đó, giữ điểm và bước còn lại. Hoàn tác khôi phục các câu sau cả hai thao tác.

Khi một phiên khác ghi sau bước xem khác biệt, FastAPI trả 409 và giữ nguyên dữ liệu của phiên đã lưu. Giao diện báo chưa đồng bộ và giữ bản nháp cục bộ. Lời nhắn xác nhận và nút hoàn tác riêng chỉ xuất hiện sau khi máy chủ nhận lưu. Bàn soạn chờ kết thúc thao tác nhập dở trước khi gửi, xem hoặc xác nhận đề xuất. Pytest riêng kiểm scope/version sai, hủy kết nối và kiểm đáp án độc lập với phản hồi mẫu. Lượt này chưa thử qua model thật hoặc thiết bị di động thật. [Ca Chrome](../../scripts/kiem-ui-de-xuat-sua.mjs) · [Ca FastAPI](../../backend/tests/test_poc_scoped_patch.py)

Với các trường Python giữ được tài liệu định dạng, ca Chrome xác nhận qua `/api/exams/{exam_id}/edits/{proposal_id}/confirm`. Pytest gửi lại xác nhận, bỏ rồi thử xác nhận, và giả lập lỗi khi lưu biên nhận để kiểm rollback. Chrome cũng bôi đen qua hai đoạn, cả ở cấp ngoài và trong cùng một ô bảng, rồi sửa khu vực có cả chữ và công thức. Công thức, chữ in nghiêng, ID và ô bên cạnh được giữ khi nằm ngoài phần thực sự đổi. Hoàn tác khôi phục bản gốc. Pytest kiểm từ chối ghép qua hai ô, bảo toàn node công thức và áp đúng run đã bôi đen khi chữ trùng.

## Kiểm lại IT-07 khi giải độc lập và duyệt câu

Chrome mở đề Ngữ văn với đáp án lưu B. Bộ giải mẫu trả A. Kết quả ghi bất đồng và thiếu trích dẫn, giữ nguyên nội dung câu và để trống dấu duyệt. Thao tác duyệt của giáo viên gắn với phiên bản hiện tại và giữ báo cáo bất đồng. Khi người dùng chủ động áp dụng kết quả giải lại, câu tăng phiên bản và mất dấu duyệt cũ.

Khi chọn nguồn nhưng bộ giải bỏ trích dẫn, FastAPI trả lỗi `missing_evidence` và giữ nguyên câu. Lỗi này đến trễ cũng giữ hộp Thông tin đề đang mở và hiện thông báo trong hộp. Bàn soạn chờ kết thúc nhập dở trước khi mở kiểm, gửi, áp dụng hoặc duyệt. Pytest đối chiếu dữ liệu gửi đi và xác nhận bộ giải không nhận đáp án, lời giải hoặc barem đang lưu. Lượt Chrome dùng đáp án dựng sẵn. [Ca Chrome](../../scripts/kiem-ui-giai-doc-lap.mjs) · [Ca FastAPI](../../backend/tests/test_workspace_check.py)

## Kiểm lại IT-10 khi xuất và chia sẻ đề

Chrome xuất sáu tệp qua giao diện, gồm Word, PDF và HTML cho hai đối tượng. Mở HTML trong Chrome, đọc và dựng ảnh trang đầu của PDF, mở hai Word trong Microsoft Word và xác nhận mỗi tệp có một công thức chỉnh sửa được. Đối chiếu dấu thử tổng hợp trong nội dung: lời giải và barem chỉ có trong bản giáo viên, hội thoại vắng ở cả sáu bản.

Khóa lựa chọn chia sẻ tại thời điểm bấm tạo. Nếu đóng hộp trước khi máy chủ nhận yêu cầu tạo liên kết, app dừng thao tác. Chrome trì hoãn lần lưu để kiểm cả hai trường hợp. Một phiên Chrome tách riêng mở được bản học sinh chỉ xem và nhận 404 sau khi chủ đề thu hồi. Kết quả xuất trả muộn giữ hộp Thông tin đề đang mở. Pytest kiểm thêm khách, owner khác, nội dung bàn soạn thay đổi khi dựng bản chia sẻ và quyền tải dữ liệu bản sao. [Ca Chrome](../../scripts/kiem-ui-xuat-chia-se.mjs) · [Ca xuất Word](../../backend/tests/test_word_export.py) · [Ca chia sẻ](../../backend/tests/test_workspace_shares.py)

## Chạy lại 11 ca Chrome trên cùng commit

Từ thư mục repo trên Windows, với Chrome và Node đã cài, chạy:

```powershell
npm ci
uv sync --project backend --frozen
uv run --project backend --frozen python -X utf8 scripts/kiem-ung-vien.py outputs/kiem-ung-vien
```

Dùng worktree sạch và chọn thư mục kết quả mới dưới `outputs/` cho mỗi lần chạy. Có thể chạy riêng từng ca bằng `--case 06`. Lệnh khởi động FastAPI và tạo kho riêng cho từng ca trên cổng loopback, kèm tài khoản thử cho ca nhóm. Node chạy bộ kiểm Chrome. Xem SHA và kết quả tại `result.json`, cùng log và báo cáo trong từng thư mục IT.

Bộ Chrome dùng ngữ liệu tự tạo và phản hồi mẫu. Kiểm Word bằng Microsoft Word, đối chiếu nhiều trang, model thật và nghiệm thu độc lập vẫn cần bằng chứng riêng theo checklist.

## Kết luận và mức độ lỗi

Lỗi mất dữ liệu, đọc/sửa chéo tài khoản, lộ đáp án/key, áp sai scope/version hoặc không thể tái lập luồng chính là **blocker trong phạm vi candidate**. Các lỗi khác xếp ảnh hưởng/tần suất/cách tránh trong issue, owner + reviewer chốt mức; không tự hạ severity để đóng task.

Một ca chưa chạy là chưa chạy; không đổi thành đạt vì task phụ thuộc đóng hoặc CI xanh. Nhóm ghi vòng trước/sau cho ít nhất một cải tiến sản phẩm theo CT-06 và [đề bài R8](../course/DE_BAI_GOC.md). Kết quả model thật, khảo sát và đánh giá giáo viên phải tách khỏi fixture kỹ thuật.
