# Kiểm thử và đánh giá phản biện

**Baseline kỹ thuật đã chạy 05/11/2026.** Xem [kết quả demo kế thừa](../testing/BASELINE_2026_11_05.md), [chức năng và giới hạn](../product/DEMO_DA_CO.md) và [cách thành viên tự test](../team/CHAY_VA_TEST_DEMO.md). Phần đánh giá với giáo viên vẫn chờ quan sát trực tiếp.

Nguồn phương pháp là Topic 6 trang 17–24, 26–30, 32. Phần dưới lưu một vòng đo kỹ thuật với Qwen3 cục bộ và kế hoạch đánh giá người dùng. BE-5 tổng hợp, các mảng kiểm phần mình và người đánh giá độc lập rà kết luận.

## Bốn loại bằng chứng

| Loại | Câu hỏi với Soạn đề thi | Cách thu thập dự kiến |
|---|---|---|
| Giá trị/khái niệm | Giáo viên có tiết kiệm công sức ở bước họ thực sự gặp khó không? | Phỏng vấn + tác vụ trước/sau bằng nội dung tự tạo, không chỉ hỏi thích UI |
| Chức năng | Tạo/sửa/lưu/reload/xuất có đúng, giữ công thức/ownership/version không? | Pytest/contract/golden fixture/UI, gồm input rỗng/hỏng/quá lớn, stale/cancel |
| Usability | Người dùng làm được mà không cần nhớ LaTeX hoặc đoán vùng AI sẽ sửa không? | Quan sát tác vụ, thời gian, lỗi, lần cần trợ giúp; xin phép trước think-aloud |
| Accessibility | Tab/focus/label/contrast/text thay màu có dùng được không? | Bàn phím và kiểm nhãn trên desktop/mobile; ghi phạm vi kiểm, không tự chứng nhận WCAG |

Tác vụ người dùng đề xuất: chèn phân số/hệ mà không gõ lệnh; sửa một câu bằng chat rồi hoàn tác; lưu/reload đề có bảng; xuất bản học sinh không có đáp án. Chốt bộ task, cỡ mẫu, điều kiện môi trường, thứ tự/bias và ngưỡng trước chạy. Không giả kết quả từ CI là quan sát giáo viên thật.

## Trước và sau trên cùng mẫu Toán lớp 5

Mẫu nhóm tự viết gồm năm câu, bốn dạng và tổng 10 điểm. Các lượt dưới dùng Qwen3 4B qua Ollama cục bộ với Chrome và kho SQLite thử. Transport QA chạy Vulkan và tắt chế độ suy nghĩ. Thời hạn tác vụ là 900 giây.

| Chủ đề | Dạng | Mức yêu cầu | Điểm |
|---|---|---|---|
| Số sách theo thể loại | Trắc nghiệm | 1 Nhận biết, 1 Thông hiểu | 2 mỗi câu |
| Lịch đọc tại thư viện | Đúng/Sai | 1 Nhận biết | 2 |
| Số sách trên kệ | Trả lời ngắn | 1 Thông hiểu | 2 |
| Tính tiền mua bút | Tự luận | 1 Vận dụng | 2 |

> Thư viện trường có 24 sách truyện và 16 sách khoa học. Ngày đọc sách diễn ra vào thứ sáu. Buổi sáng thư viện mở lúc 8 giờ, buổi chiều mở lúc 14 giờ. Mỗi buổi đọc kéo dài 45 phút. Trên kệ A có 12 cuốn, trên kệ B có 18 cuốn. Cửa hàng bán mỗi cây bút với giá 5.000 đồng. Nếu mua từ 10 cây bút trở lên, cửa hàng giảm 5.000 đồng trên tổng hóa đơn.

Trong kho thử trống, tạo đề Toán lớp 5, nhập nguồn và ma trận trên rồi gõ **Soạn đề theo ma trận này**. Đối chiếu lần nộp, `candidateHash`, phản hồi lỗi của lần trước, trạng thái lượt kiểm nội dung và revision trước/sau. Mở đề xuất và xác nhận chỉ khi toàn bộ bộ kiểm đạt. [Mở app và xem nhật ký](../testing/THEO_DOI_LOG_POC.md)

| Commit runtime | Thay đổi đang đo | Quan sát trên một lượt |
|---|---|---|
| `c1dc33a` | Trả lỗi cho Ollama bằng đối tượng JSON | Nộp bốn lần, ba lần sau lặp bộ đầu. Không có đề xuất qua kiểm. |
| `c02daca` | Sau lần nộp trùng, rút bộ cũ khỏi ngữ cảnh và giữ ma trận, nguồn, lỗi | Lần ba viết lại cả năm câu, qua cấu trúc rồi trượt rà nội dung. Bộ giải từng tính được 40 nhưng chỉ phương án ghi 30. |
| `20201ea` | Bộ giải trả nội dung phương án, Python tìm vị trí | Ánh xạ đúng 6/6 lần ở ba lượt rà. Sai Đúng/Sai, lệch mức và bất đồng bảng đánh giá vẫn bị chặn. |

Ba lượt trên đều hết thời gian, revision giữ ở 1 và lưu 0 câu. Kết quả 6/6 đo riêng ánh xạ đáp án của Python.

| Commit runtime | Thay đổi đang đo | Quan sát trên một lượt Qwen3 thật |
| --- | --- | --- |
| `1fadef7` | Giới hạn câu cần sửa theo mã lỗi | Lượt sửa hai câu giữ nguyên ba câu còn lại. Lỗi trùng chưa có mã câu nên lượt sau phải soạn lại cả bộ. Hết giờ khi rà lần nộp thứ năm. |
| `6ea407e` | Gắn mã câu vào lỗi trùng | 19/20 lượt nộp sửa theo phạm vi. Sau lỗi trùng, lần nộp tiếp chỉ thay câu thứ hai nhưng quay về cách hỏi bị đánh giá lệch mức. Chạm 24 lần gọi model. |

Hai lượt trên giữ revision 1 và lưu 0 câu. Đây là cùng một đề với một lượt chạy trên mỗi commit. Cần thêm dữ liệu để so tốc độ, độ đúng và tỷ lệ hội tụ giữa các bản. Nhật ký kỹ thuật gồm mã commit, đầu vào tự tạo và kết quả theo từng phép kiểm. [Thuật toán và dry run](ALGORITHM.md) · [Nhánh tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/46)

### Vòng cải tiến Pha 2 (`47c40f8`) & đo trước/sau trên `codex/ban-thu-13` (`8d37a0f`)

Trên cùng mẫu Toán lớp 5 (5 câu, 4 dạng, 10 điểm, nguồn tự viết) chạy bằng `qwen3:4b` qua Ollama Vulkan cục bộ (tắt chế độ suy nghĩ, trần `900s`), so sánh trực tiếp lượt trước và lượt sau tinh chỉnh Pha 2 (`passed_blind_cache`, `skip_explanation_on_blind_fail`, chuẩn hóa `propose_repair_stem`, kiểm `invalid_rubric`):

| Lượt đo (`[Model thật cục bộ]`) | Thời lượng & trạng thái kết thúc | Kết quả kiểm chứng trace & cấu trúc | Hành vi kiểm mù & thay đổi kho |
| --- | --- | --- | --- |
| **Lượt v1** (`outputs/qa-antigravity-qwen3`) | `900.707s`, `status="failed"`, `errorCode="timeout"`, `checkedAttempts=8` | `traceVerified=true`, `evidenceIssues=[]`; phát sinh lỗi cấu trúc `duplicate_question` (lần 3) và `invalid_rubric` (lần 8) giữa vòng | `ordinal 1` trượt cả 6 lần `blind_content_check`; `beforeRevision == afterRevision == 2` (`0` câu lưu). |
| **Lượt v2 sau `47c40f8`** (`outputs/qa-antigravity-qwen3-v2`) | `901.081s`, `status="failed"`, `errorCode="timeout"`, `checkedAttempts=7` (`19` lượt gọi model / `894.01s`) | `traceVerified=true`, `evidenceIssues=[]`; **`7/7` lần `structure_check` đạt** (hết `duplicate_question` và `invalid_rubric`) | **4/5 câu (`ordinal` `0, 2, 3, 4`) pass `blind_content_check` và cache ổn định (`24.0s`–`45.4s`/lượt)**; duy nhất `ordinal 1` vượt khả năng model 4B trên câu suy diễn từ nguồn 1 câu 2 số; `beforeRevision == afterRevision == 2`. |

> **Giới hạn kết luận:** Số đo trên là bằng chứng kỹ thuật trước/sau cho vòng cải tiến `R8` (`[Model thật cục bộ]`), cho thấy tối ưu cache và kiểm cấu trúc hoạt động ổn định và giữ an toàn dữ liệu khi timeout; nhưng **chưa chứng minh model `4B` tự sinh đạt 100% bộ câu hỏi hỗn hợp trong `900s`** và không thay thế đánh giá sư phạm hay quan sát giáo viên thật.

### Tổng hợp bằng chứng kỹ thuật trên ứng viên sạch `8d37a0f`

- **Python (`[Hiện có / Đã chạy bằng Python]`):** `uv sync --frozen`, `ruff format --check .` (`94` tệp), `ruff check .`, `ty check src` đạt toàn bộ; `uv run pytest -q` đạt **`710 passed, 5 skipped, 1 warning, 3 subtests passed`** (`110.66s`, bổ sung `test_sample_exam_8b.py`, `test_be3_workspace_bridge.py`, `test_security_and_contracts.py`; riêng `test_check_routes.py` đạt `40 passed, 1 skipped` khi chạy đơn lẻ và `45 passed, 1 skipped` khi cộng với 5 ca bảo mật không tranh chấp GPU); lượt chạy **tắt `node`/`npm` khỏi `PATH`** đạt **`167 passed`** (`51.99s`). Chi tiết tỷ lệ mã nguồn (`48,73%` Python `1.239.067 B` vs `44,09%` JS tự viết `1.121.180 B` sau `.gitattributes`) xem [DOI_CHIEU_PYTHON.md](../testing/DOI_CHIEU_PYTHON.md).
- **JS/UI & 11 kịch bản Chrome (`[Fixture / Mock]`):** `npm test` đạt **`139 passed`** (`0` failed); `npm run check:team` đạt **`14 passed` + `Team plan OK`**; `npm run build-editor` sinh `assets/editor-engine.js` (`436.8kb`) sạch worktree. Với [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py) trên `8d37a0f`: lượt 1 (`outputs/qa-antigravity-it`) đạt **`10/11`** (`IT-11` lỗi timing `networkidle` tại `kiem-ui-khoi-phuc.mjs:37`, rerun `--case 11` đạt); lượt 2 (`outputs/qa-antigravity-it-final`) đạt **`10/11`** (`IT-05` lỗi `.fill()` trên `contenteditable` TipTap tại `ui2-baseline-browser.mjs:188`, rerun `--case 05` đạt). Chi tiết tại [KIEM_THU_TICH_HOP.md](../testing/KIEM_THU_TICH_HOP.md).
- **Đóng gói sạch `ung-vien-48` (`[Hiện có / Đã chạy bằng Python]`):** `outputs/ung-vien-48/SoanDeThi-UngVien-48.zip` (`215` tệp / `216` mục zip, `SHA-256: 1a28c3c62d77fcc9eec1531e8222284b174bff5844c7e1c4a5813614f4e92f06`), giải nén sạch và chạy Uvicorn không có Node trong `PATH`, xuất kiểm thật 4 tệp: Word HS (`36.987 B`, `1 m:oMath`, 0 rò), Word GV (`37.329 B`, `1 m:oMath`, đủ đáp án/barem), PDF HS (`53.436 B`, `%PDF-`, 0 rò), PDF GV (`69.026 B`, `%PDF-`, đủ đáp án/barem).
- **Hồ sơ thiết kế/contract & phần còn chờ (`[Chờ review nhóm / Thành viên xác nhận]`):** dẫn chiếu [Luồng màn hình](../design/luong-man-hinh.md), [Trợ lý và job](../design/tro-ly-va-job.md), [Hợp đồng AI](../contracts/ai.md), [Hợp đồng HTTP](../contracts/http.md), [Hợp đồng tài liệu](../contracts/tai-lieu.md), [Hợp đồng Job & SSE](../contracts/job-va-sse.md). Các bảng người dùng thật (`CT-01`/`CT-06`) bên dưới vẫn **`Chưa chạy`**; review chéo giữa thành viên, thẩm định sư phạm và diễn tập GreenNode vẫn chờ con người và `ngocthuan1505` theo [ops/greennode/README.md](../../ops/greennode/README.md).

### Ca tích hợp Chrome với phản hồi mẫu

Ở `21377e1`, bài kiểm dùng cùng năm câu và thay phản hồi HTTP Ollama bằng dữ liệu kiểm soát. Lượt một bị báo câu thứ hai lệch mức. Lượt hai gửi một câu thay thế, giữ bốn câu còn lại, qua bộ kiểm và hiện bản xem trước. Đề đang lưu giữ revision 1 cho tới khi người thử bấm xác nhận. Sau tải lại, có đủ năm câu, bốn dạng, 10 điểm và revision 2. Kết quả này đo luồng tích hợp, phạm vi sửa và lưu dữ liệu. Độ chính xác sư phạm của model thật được đánh giá riêng. [Kế hoạch kiểm tích hợp](../testing/KIEM_THU_TICH_HOP.md)

Quyết định sau thử nghiệm là giữ kiểm độc lập và chặn khi bộ kiểm mâu thuẫn. Khi đề xuất chưa đạt trong ngân sách, giáo viên giữ bản đang soạn và có thể soạn tiếp thủ công. Phần cần xác nhận tiếp là model thật sửa qua kiểm, sau đó người rà độc lập kiểm nội dung và mức nhận thức.

## Nhật ký dữ liệu mẫu

### Cách ghi một lượt người dùng thử

1. Ghi mã người tham gia ẩn danh, vai trò, SHA bản cài, hệ điều hành, trình duyệt, màn hình và chế độ AI. Dùng đề tự viết và hỏi có đồng ý ghi thao tác hay không. Nếu chạy hai phiên bản, dùng cùng kịch bản, cùng môi trường và ghi thứ tự thử.
2. Đọc nguyên yêu cầu tác vụ trước khi bấm giờ. Bắt đầu khi người dùng thực hiện thao tác đầu tiên, kết thúc khi đạt điều kiện bên dưới hoặc khi họ dừng. Ghi số lần họ cần trợ giúp, lỗi quan sát được và phần đã làm xong. Với tác vụ AI, ghi riêng thời gian chờ model để nhìn được thao tác của người dùng.
3. Dùng các trạng thái **tự hoàn thành**, **hoàn thành có trợ giúp**, **dừng vì không hoàn thành** hoặc **chưa thử**. Trình bày số ca trên mẫu số đã chạy. Các ca dừng được giữ trong bảng và ghi nguyên nhân.

| Tác vụ giao cho người thử | Dấu hiệu hoàn thành để người quan sát kiểm |
|---|---|
| Chèn phân số 3/4 vào Câu 1 bằng trình chọn mẫu. | Trình soạn hiển thị đúng 3/4. Sau khi lưu và mở lại, nút công thức vẫn sửa được. |
| Chọn một đoạn ở Câu 2, yêu cầu trợ lý sửa riêng đoạn đó, xem trước rồi áp dụng và hoàn tác. | Chỉ vùng đã chọn đổi sau khi áp dụng. Câu kế bên giữ nguyên và hoàn tác trả lại đoạn gốc. Ghi lại nếu không chạy được model được phép. |
| Lưu đề có bảng, đóng rồi mở lại từ kho đề. | Bảng giữ số hàng/cột và nội dung ô. Bản ghi mở lại đúng đề mà người thử vừa lưu. |
| Xuất Word học sinh và mở trong Word hoặc phần mềm tương thích. | Bản mở thành công, có đề và công thức. Đáp án và barem chỉ có trong bản giáo viên. Ghi công cụ thực tế dùng để mở. |
| Dùng Tab và Shift+Tab mở ô nhập công thức rồi quay lại trình soạn. | Thấy tiêu điểm, đọc được nhãn điều khiển và có đường quay lại vùng soạn bằng bàn phím. Ghi nơi bị kẹt nếu có. |

Thành viên có thể dùng bảng này để chạy thử nội bộ. Phần R1 và CT-01 vẫn cần phản hồi từ ít nhất ba người dùng thật thuộc nhóm mục tiêu. Các ngưỡng định lượng về thời gian và trợ giúp cần được nhóm chốt trước khi đo. [Problem Brief](PROBLEM_BRIEF.md)

| Mã ca/người ẩn danh | Commit/môi trường | Tác vụ/kỳ vọng | Thời gian/lỗi/trợ giúp | Kết quả và bằng chứng | Vấn đề cần sửa |
|---|---|---|---|---|---|
| Chưa chạy | — | — | — | — | — |

## Phản hồi → quyết định

Mỗi phát hiện ghi vấn đề quan sát, bằng chứng, mức nghiêm trọng, phương án sửa, issue phụ trách và kết quả kiểm lại. Phân loại: blocker (không hoàn thành/mất dữ liệu/sai quyền), nghiêm trọng nhưng có đường vòng, cải tiến tiện dụng. Số liệu từ mẫu nhỏ chỉ mô tả mẫu đó; ghi mẫu số, số ca bỏ dở và giới hạn.

Mỗi vòng nhóm trả lời: giữ gì, sửa gì, bỏ/defer gì, tại sao bằng chứng ủng hộ; đánh đổi tốc độ/độ đúng, ít bước/khả năng kiểm soát, phạm vi/thời gian. So sánh ít nhất một phương án khác cho rủi ro chính. Không chỉ liệt kê tính năng đẹp hoặc test xanh.

## Đề nghị nghiệm thu

Task hoàn thành khi có đầu ra theo acceptance, kết quả kiểm lại, PR/reviewer và giới hạn. Prototype/MVP còn cần giả thuyết cốt lõi được kiểm chứng, tác vụ chính ổn định, không còn blocker trong phạm vi demo, trade-off được chấp nhận và vòng cải tiến tiếp theo rõ. Xem [release checklist](../team/RELEASE.md) và [khung báo cáo](../reports/BAO_CAO_DO_AN.md).

Chưa có GreenNode thì đánh dấu phần model thật/deploy thật chưa kiểm; không chặn các test fixture/local độc lập. Chỉ Thuận quyết định mở web và test server; mọi nguồn dữ liệu phải được phép sử dụng.
