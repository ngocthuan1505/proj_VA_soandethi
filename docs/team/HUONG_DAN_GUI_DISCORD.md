# Soạn đề thi - Hướng dẫn vào nhóm và bắt đầu làm đồ án

Bản sửa 3 ngày 07/11/2026 - **tự chọn việc hoặc làm chung, thay bản phân công cứng trước đó**. Repo và Project giữ **Private**. Tài liệu này không có khóa API, mật khẩu, mã mời bí mật hoặc địa chỉ server GreenNode. Bản PDF đi kèm có link bấm được; tài liệu GitHub là bản cập nhật lâu dài.

Tên tạm của đồ án là **Soạn đề thi (Exam Maker)**; nhóm chưa chốt tên sản phẩm.

Đọc [bản tóm tắt repo trong 5 phút](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/DOC_REPO_TRONG_5_PHUT.md) trước khi mở tài liệu chi tiết.

## 1. Nhận quyền trước khi clone

1. Đăng nhập đúng tài khoản GitHub trong danh sách thành viên bên dưới.
2. Mở [lời mời repo](https://github.com/ngocthuan1505/proj_VA_soandethi/invitations), chọn **Accept invitation** nếu còn đang chờ; cũng có thể mở lời mời từ thông báo/email GitHub.
3. Mở [repo source](https://github.com/ngocthuan1505/proj_VA_soandethi) và [bảng tiến độ](https://github.com/users/ngocthuan1505/projects/1/views/1). Repo Write cho phép cộng tác code; Project Write cho phép cập nhật bảng, không phải quyền admin/server.
4. Nếu thấy 404/không mở được: kiểm tra đúng account, đã nhận lời mời chưa, rồi báo Thuận. Không tạo repo khác hoặc đổi công khai. Repo và Project là hai quyền riêng.

Lời mời đã được gửi theo danh sách chủ nhóm xác nhận. Chỉ sau khi người nhận chấp nhận thì mới có quyền repo; PDF không thay thao tác Accept. Username đúng là **lamngoc25032007-netizen** và **2512716757-source**; không dùng các username thiếu/sai trước đó. Đây là danh sách thành viên, không gán chuyên môn cho từng người.

## 2. Đọc định hướng rồi tự chọn hoặc làm chung

**Không gán từng người một mảng cố định.** Nhóm đã chốt:

| Nhóm | Thành viên |
|---|---|
| UI - 3 người | [@lamngoc25032007-netizen](https://github.com/lamngoc25032007-netizen), [@Mysthaps](https://github.com/Mysthaps), [@PhuQuang0307](https://github.com/PhuQuang0307) |
| Backend - 5 người | [@ngocthuan1505](https://github.com/ngocthuan1505), [@fiiwk21](https://github.com/fiiwk21), [@2512716757-source](https://github.com/2512716757-source), [@cyan-cpu](https://github.com/cyan-cpu), [@shin-hybrid](https://github.com/shin-hybrid) |

Cả ba bạn UI có thể cùng nghiên cứu/chọn/làm một mảng hoặc một luồng. Backend cũng có thể nhận chung và phối hợp giữa các mảng. Mã UI-1/UI-2/BE-2… dưới đây là **mã công việc, không phải tên người**. Chỉ việc vận hành GreenNode thuộc riêng Thuận.

Đầu tiên mở [menu chọn việc trên GitHub](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/CHON_VIEC.md), thử demo/source/fixture rồi đề xuất giữ/cải thiện và phương án. Đọc mục tiêu/đầu ra để chọn có căn cứ; chưa cần chốt công nghệ ngay.

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

**Cách đăng ký:** comment trong issue tên thành viên, mảng/luồng muốn nghiên cứu, task/Wxx định nhận, đầu ra, ai code/test/review và phụ thuộc. Trao đổi với người đang nhận rồi thêm Assignees một hoặc nhiều người thực sự làm; không tự gỡ người đã nhận thật. Có thể cùng nghiên cứu trước, chọn người thực hiện sau. Công cụ không tự gán theo roster.

**Ví dụ làm chung:** ba bạn UI chọn luồng sửa công thức bằng chat, tự chia phần editor/ngữ cảnh-diff/fixture-test hoặc luân phiên; ghi Wxx và đầu mối mỗi PR để không đè file. Ví dụ này không phải phân công mới; reviewer khác người viết.

001 là baseline/hợp đồng, 002 triển khai/tích hợp, 003 nghiệm thu; task có Wxx/Txx và expected result để nhóm tự chia. Chưa chọn vẫn để mở, không có nghĩa thiếu danh tính. Các mục chưa tick là kế hoạch, không phủ nhận demo/hồ sơ đã có.

## 3. Cài và bật demo trên máy mình

Chạy bản tích hợp Python theo [hướng dẫn bản 13](../../HUONG_DAN_TEST_NHOM.md). Các lệnh dưới đây phục vụ bản Node đối chiếu.

Cài [Git](https://git-scm.com/downloads), [Node.js 24+ kèm npm](https://nodejs.org/en/download), Chrome hoặc Edge. Mở Terminal mới, kiểm tra `git --version`, `node --version`, `npm --version`. Trong thư mục muốn lưu đồ án:

```sh
git clone https://github.com/ngocthuan1505/proj_VA_soandethi.git
cd proj_VA_soandethi
npm ci
npm run start:legacy
```

Mở **http://127.0.0.1:4173/**. Giữ Terminal chạy; **Ctrl+C** tại Terminal đó để dừng. Đóng tab trình duyệt không dừng server. Lần sau vào repo và chạy `npm run start:legacy`; Windows có `START-DEMO.cmd` sau khi cài phụ thuộc, nhưng cách Terminal dễ kiểm soát lúc dừng hơn.

Mỗi máy có `.data` riêng. Clone không mang đề, tài khoản, khóa AI hoặc model của Thuận. Không cần GreenNode/API để dùng editor, thư viện mẫu hoặc test fixture. Chỉ mở link localhost không tự bật app và không chia sẻ app máy mình cho người khác.

**Thử trong 15 phút:** tạo/mở đề mẫu → sửa chữ → chèn phân số/hệ bằng thư viện theo môn → undo/redo → reload → xuất bản học sinh/giáo viên. Tạo file synthetic để thử import; so bản xuất và ghi expected/actual. Không dùng tài liệu thật/nhạy cảm làm fixture.

Lỗi `refused to connect`: bật server và đọc Terminal. `npm` không nhận: kiểm cài Node/mở Terminal mới. Thiếu module: `npm ci` đúng thư mục. Trùng cổng: dừng đúng tiến trình của mình, không kill mọi Node. [Hướng dẫn mở app/test và xử lý lỗi đầy đủ](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/CHAY_VA_TEST_DEMO.md).

## 4. Backend Python và kiểm thử

Theo quy định môn, **Python là backend/core chính**, JavaScript hỗ trợ browser/editor/build. Demo đang kế thừa Node; Python hiện mới foundation health/readiness, chưa chuyển xong nghiệp vụ. Không proxy core sang Node rồi gọi là đã migrate.

Cài [Python 3.12+](https://www.python.org/downloads/) và [uv](https://docs.astral.sh/uv/getting-started/installation/). Từ repo:

```sh
cd backend
uv sync --frozen --python 3.12
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check src
uv run uvicorn mach_backend.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Mở **http://127.0.0.1:8000/docs**. Health 200, readiness 503 kèm phần còn thiếu là đúng hiện trạng; UI legacy chưa tự chuyển sang Python. [Kế hoạch Python](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/architecture/PYTHON_MIGRATION.md).

Từ root repo, kiểm baseline bằng:

```sh
npm test
npm run check:team
node tests/selection-browser.mjs
node tests/usability-browser.mjs
```

Browser suite tự bật server/DB tạm, dùng Chrome/Edge và fixture, không cần key thật. Không chạy hai bản cùng script/cổng. PDF/browser cần browser hợp lệ hoặc `BROWSER_PATH`; online fixture còn cần Python + cryptography theo hướng dẫn. Sửa editor-engine thì build lại editor. Không chạy setup model để mở editor.

Baseline đã có 98 test Node, 80 bước UI trong 7 bộ và 2 pytest nền; kế hoạch nhóm hiện có 14 test. Đây không phải độ chính xác AI hoặc nghiệm thu toàn app Python. [Kết quả/giới hạn baseline](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/BASELINE_2026_11_05.md), [kế hoạch test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md).

## 5. Nhận việc, làm PR và báo tiến độ

1. Mở menu định hướng, đọc/thử rồi comment đăng ký cá nhân hoặc nhóm vào task phù hợp. Ghi Wxx, đầu ra và ai thực hiện/test/review; hạn chế một việc đang làm mỗi người, không bắt một người giữ một chuyên môn.
2. Trước khi sửa: `git status`, cập nhật main khi sạch bằng `git pull --ff-only`; tạo nhánh riêng dạng `codex/UI-2-001-ten-viec`. Không sửa/force-push thẳng main, không reset/clean thay đổi người khác.
3. Giữ scope nhỏ, thống nhất file/contract dùng chung trong issue. Bước quá khoảng một ngày thì tạo issue con nối cha/Wxx, có đầu ra và test.
4. Commit/tiêu đề PR/mô tả tiếng Việt. PR dẫn task/Wxx và Txx, nêu phần kế thừa/phần mới, expected/actual, test đã/chưa chạy, ảnh UI hoặc log phù hợp và cách quay lui. Chờ review trước merge.
5. Status: Sẵn sàng → Đang làm → Chờ duyệt → Hoàn thành; vướng thì Bị chặn kèm đã thử gì/cần ai giúp. Label status và Project không tự đồng bộ; gửi form không tự đóng task. Reviewer chấp nhận mới nghiệm thu cả task.
6. Báo cuối buổi bằng comment hoặc một form; không cần chép đôi toàn bộ báo cáo. Dán link vào task. [Nhật ký nhóm #32](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/32) tổng hợp, không thay task cá nhân.

Mẫu ngắn để dán vào task:

```text
Cá nhân / nhóm và thành viên GitHub:
Mảng / luồng tự chọn và lý do:
Task / bước: UI-2-001 / W01
Đã làm / phần kế thừa / phần mới:
Bằng chứng: PR, commit, ảnh hoặc log fixture
Ca Txx: expected / actual / đạt-không đạt-chưa chạy
Bên nhận bàn giao / reviewer:
Vướng / đã thử / cần ai hỗ trợ:
Còn lại / bước tiếp:
```

## 6. Link cần lưu

| Việc cần mở | Đường dẫn |
|---|---|
| Bảng kéo thả / danh sách | [Kanban](https://github.com/users/ngocthuan1505/projects/1/views/1) · [Table](https://github.com/users/ngocthuan1505/projects/1/views/2) |
| 24 task kỹ thuật / 6 task hồ sơ | [Backlog kỹ thuật](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BACKLOG.md) · [Backlog CT](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/BACKLOG_CT.md) |
| Báo tiến độ / vướng / xin nghiệm thu | [Tiến độ](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=tien_do.yml) · [Vướng mắc](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=vuong_mac.yml) · [Nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=nghiem_thu.yml) |
| Đóng góp code / PR / kiểm CI | [Quy ước](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/CONTRIBUTING.md) · [Pull requests](https://github.com/ngocthuan1505/proj_VA_soandethi/pulls) · [Actions](https://github.com/ngocthuan1505/proj_VA_soandethi/actions) |
| Demo đã có và kế thừa theo vai trò | [16 nhóm chức năng](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/DEMO_DA_CO.md) |
| Phạm vi / hợp đồng / gates | [11 use case](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Bàn giao M1-M3](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md) |
| Bài môn / hồ sơ cũ / báo cáo | [Tài liệu môn](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md) · [Hồ sơ đã có](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/HO_SO_DA_CO.md) · [Khung báo cáo](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/reports/BAO_CAO_DO_AN.md) |
| Slide gốc môn học | [Google Drive do Thuận cung cấp](https://drive.google.com/drive/folders/1L_2gLfP4aXve4dcdobSJtAIqDeOoONcK) |
| Hai mảng lý thuyết / thực hành dùng chung | [Bản bàn giao chung](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/context/README.md) |

## 7. Quy tắc cần nhớ

Chỉ Thuận đăng nhập/thao tác GreenNode. Nhóm khác dùng local/fixture; thay đổi server qua PR/runbook để Thuận tự chạy. Không chia sẻ account, password/token/API key, `.env`, `.data`, `.runtime`, trọng số hoặc tài liệu giáo viên vào Discord/GitHub. Repo Private không thay quyền truy cập của Docs/Canva/Drive.

Chưa có deadline thật thì không tự bịa ngày. Không coi mẫu đa môn là AI đúng mọi chương trình; model thật cần dữ liệu được phép và quyền/quota hợp lệ, không tự dùng API trả phí. Đã có proposal/decomposition/abstraction và demo: đọc đầu vào để kế thừa, không nhận công cũ là phần mình vừa làm.

Mục tiêu buổi đầu: nhận lời mời, mở đủ repo/bảng, chạy được demo, test một luồng, tự chọn/đăng ký Wxx (cá nhân hoặc nhóm) và báo kết quả. Có vướng thì báo sớm bằng bằng chứng cụ thể.
