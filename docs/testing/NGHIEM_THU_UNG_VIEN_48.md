# Nghiệm thu kỹ thuật & bảng truy vết · Ứng viên 48 (PR #46)

**Ngày cập nhật:** 19/11/2026  
**Nhánh làm việc:** `codex/ban-thu-13` ([PR #46](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/46) → `main`)  
**Nhánh sao lưu gốc:** tag `luu-nhanh-2026-11-19`  
**Trạng thái chốt:** **Chưa đề nghị đóng Final** vì còn các cổng bắt buộc thuộc người dùng thật, peer review chéo, thành viên cài độc lập trên máy khác và diễn tập vận hành GreenNode của Thuận.

## 1. Chuỗi commit triển khai trên `codex/ban-thu-13`

| Thứ tự | Commit SHA | Nội dung chính |
| --- | --- | --- |
| Kế thừa nền | [`269cd6a63120ea97fc2fbb612bdf075b60ef27a4`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/269cd6a63120ea97fc2fbb612bdf075b60ef27a4) | Ứng viên 47 từ PR #46 (*Chỉ gửi các ô cần sửa trong yêu cầu Ollama*) |
| Pha 2 | [`47c40f8`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/47c40f8) | Tối ưu vòng tự kiểm/sửa model local: thêm `passed_blind_cache` (`reuse_passed_reviews`), `skip_explanation_on_blind_fail`, gắn `ordinal` vào lỗi barem, chuẩn hóa `\u061f`/`\uff1f` → `?`, chặn lặp tiền/hậu tố của `avoid` (`_normalize_stem_compare`) trong [`matrix_agent.py`](../../backend/src/mach_backend/matrix_agent.py) và [`workspace_agent.py`](../../backend/src/mach_backend/workspace_agent.py). |
| Pha 3 | [`8d37a0f`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/8d37a0f) | Hoàn thiện 6 đặc tả/contract M1 ([luong-man-hinh.md](../design/luong-man-hinh.md), [tro-ly-va-job.md](../design/tro-ly-va-job.md), [ai.md](../contracts/ai.md), [http.md](../contracts/http.md), [tai-lieu.md](../contracts/tai-lieu.md), [job-va-sse.md](../contracts/job-va-sse.md)) và 3 bộ kiểm thử Python M2/M3 ([test_sample_exam_8b.py](../../backend/tests/test_sample_exam_8b.py), [test_be3_workspace_bridge.py](../../backend/tests/test_be3_workspace_bridge.py), [test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py)). |
| Pha 5 | [`5e70450`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/5e70450) | Đồng bộ hồ sơ `CT-01..06`, báo cáo `R1..R8`, [BAO_CAO_DO_AN.md](../reports/BAO_CAO_DO_AN.md), [THUC_HANH.md](../context/THUC_HANH.md) và tài liệu nghiệm thu này. |
| Hợp nhất `main` + CI Public | [`a6046fc`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/a6046fc), [`958fad9`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/958fad9) | Merge `origin/main` (`2ecf411`, PR #48/#49) gỡ xung đột `README.md`, sửa `.github/workflows/phat-hanh-ban-thu.yml` cho repo Public kèm kiểm tra tệp cấm ZIP; đạt CI xanh [44573569423](https://github.com/ngocthuan1505/proj_VA_soandethi/actions/runs/44573569423). |
| Ứng viên 49 — Mở rộng Python | [`69eb1e3`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/69eb1e3) → [`0792542`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/0792542) | Mở rộng nguồn phân cấp ([curriculum_sources.py](../../backend/src/mach_backend/curriculum_sources.py)), kho cộng đồng (`community_library.py`, từ Ứng viên 50 hợp nhất vào [workspace_shares.py](../../backend/src/mach_backend/workspace_shares.py)), OCR giữ công thức/hình & xuất A4/DOCX ([ocr_structured.py](../../backend/src/mach_backend/ocr_structured.py), [exam_spec_export.py](../../backend/src/mach_backend/exam_spec_export.py)), đối chiếu Keep/Defer/Drop ([MO_RONG_THAM_KHAO.md](../product/MO_RONG_THAM_KHAO.md)) và nối vào [local_workspace.py](../../backend/src/mach_backend/local_workspace.py) + [team_workspace.py](../../backend/src/mach_backend/team_workspace.py) kèm [test_extended_workspace_integration.py](../../backend/tests/test_extended_workspace_integration.py). |

## 2. Ranh giới bảo toàn và tách vai

- **Đồng bộ kênh kiểm thử và phần riêng Codex:** [PR #48](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/48) và [PR #49](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/49) đã merge vào `main` (`2ecf411`), issue `#2` và `#6` đã đóng. Repo hiện chuyển sang trạng thái **Public** (theo xác nhận Thuận ngày 19/11/2026); `codex/ban-thu-13` đồng bộ sạch với `main` và Codex giữ nhánh tính năng mở rộng `codex/ma-de-ban-thu` trên worktree riêng theo mục *Điều phối cập nhật ngày 19/11/2026*.
- **Hồ sơ lý thuyết giữ nguyên:** Không ghi đè [LY_THUYET.md](../context/LY_THUYET.md); chỉ cập nhật bản bàn giao thực hành [THUC_HANH.md](../context/THUC_HANH.md).
- **An toàn hạ tầng & kho thật:** Không thao tác GreenNode, không chạm kho port `4182`, không đưa khóa, URL thật, `.zip`, `outputs/` hoặc dữ liệu cá nhân lên GitHub Public.

## 3. Đo ngôn ngữ lập trình & chứng minh runtime Python-chính

| Chỉ tiêu đo | Trên `main` (`cecfd3de`) | Ứng viên 48 (`8d37a0f`) | Ứng viên 49 (`0792542`, `git ls-tree -rl HEAD`) |
| --- | --- | --- | --- |
| Python (mã nguồn + test) | `42,188 B` (`1,54%`) | `1,239,067 B` (`48,73%`) | **`1,488,000 B`** (**`53,56%`**; `backend/src` **`737,790 B`**, `scripts/` & gốc `106,315 B`, `backend/tests` **`643,895 B`**; chưa tính test vẫn `844,105 B`) |
| JavaScript tự viết (UI/editor/test/legacy) | `2,642,845 B` (`96,72%`) | `1,121,180 B` (`44,09%`) | `1,120,990 B` (`40,35%`, chưa tính test: `857,159 B`; không ẩn mã tự viết, không thêm mã đệm) |
| CSS tự viết | — | `169,091 B` (`6,65%`) | `169,091 B` (`6,09%`) |
| Tài nguyên gán `.gitattributes` | — | `linguist-vendored`: `assets/katex/**` + `assets/mathlive/**` (`2,630,140 B` JS) · `linguist-generated`: [editor-engine.js](../../assets/editor-engine.js) (`447,254 B`) | Giữ nguyên |

**Bằng chứng nghiệp vụ Python chạy độc lập khi Node API tắt (`shutil.which("node") is None`, `shutil.which("npm") is None`):**
1. Trên `0792542`: chạy 16 bộ kiểm thử lõi + 4 bộ mở rộng (`test_foundation`, `test_local_workspace`, `test_team_workspace`, `test_workspace_transactions`, `test_workspace_shares`, `test_workspace_backup`, `test_patch_confirmation`, `test_poc_scoped_patch`, `test_matrix_agent`, `test_source_documents`, `test_word_export`, `test_security_and_contracts`, `test_curriculum_sources`, `test_community_library`, `test_extended_ocr_and_exports`, `test_extended_workspace_integration`) khi tước hoàn toàn Node/npm khỏi `PATH` đạt **`292 passed, 2 skipped, 1 warning in 75.11s`** (trên `8d37a0f` 12 tệp lõi đạt `167 passed`).
2. Giải nén `SoanDeThi-UngVien-49.zip` (`SHA-256: b7eb24c53180088111d6f94dda3d1757863c9f860ab914eae98da54a4c7a363a`) ra thư mục `%TEMP%` sạch ngoài repo, cài `uv sync --frozen --no-dev`, khởi động `uvicorn mach_backend.local_workspace:app --app-dir backend/src` với PATH không Node/npm: lưu/tải lại đề có công thức, xuất kiểm 4 tệp Word/PDF thật và gọi thông suốt 3 nhóm API mở rộng (`/api/curriculum/sources`, `/api/community/*`, `/api/ocr/structure` + `/api/exports/*`).

## 4. Tổng hợp kết quả kiểm thử trên `0792542` (và đối chiếu `8d37a0f`)

| Hạng mục kiểm | Ngữ liệu | Kết quả thực đo | Ghi chú trung thực |
| --- | --- | --- | --- |
| `uv sync --frozen`, `ruff format --check .`, `ruff check .`, `ty check src` | Tĩnh (Python) | **Đạt 100%** (`29` gói, `102` tệp format sạch) | Chạy từ `backend/` |
| `uv run pytest -q` (`0792542`) | Unit / Contract / Integration | **`751 passed, 5 skipped`**, `1 warning`, `3 subtests passed` (`122.49s`) | 5 ca skip là ca gọi AI thật tùy chọn (tăng từ `710 passed` ở `8d37a0f`) |
| `pytest` (16 tệp lõi + mở rộng, không Node/npm trên `PATH`) | Unit / Contract (không Node) | **`292 passed, 2 skipped, 1 warning`** (`75.11s`) | Chứng minh toàn bộ lõi + mở rộng chạy thuần Python |
| `npm test` / `npm run check:team` / `npm run build-editor` | Legacy JS / Kế hoạch / Bundle | `npm test`: **`139 passed`**; `check:team`: **`14 passed` (`Team plan OK`)**; `build-editor`: `436.8kb` | `git status` sạch sau build |
| Chrome [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py) (`IT-01..IT-11`, `0792542`) | Chrome + FastAPI (fixture) | Lượt `0792542`: `IT-01..IT-10` **đạt** (`10/11`), `IT-11` gặp race `PUT /api/kv` tại `kiem-ui-khoi-phuc.mjs:37`, chạy đơn lẻ `--case 11` **đạt** (trên `8d37a0f` 2 lượt + chạy lẻ `--case 11`, `--case 05` cũng đạt đủ 11/11) | Toàn bộ `IT-01..IT-11` đều đã đạt trên `0792542`; flake timing Windows khi chạy nối tiếp được ghi nguyên trạng |
| ZIP `SoanDeThi-UngVien-49.zip` ([dong-goi-ban-thu.py](../../scripts/dong-goi-ban-thu.py)) | Cài sạch ngoài repo + xuất thật + 3 API mở rộng | `219` tệp (`220` mục ZIP), **`SHA-256: b7eb24c53180088111d6f94dda3d1757863c9f860ab914eae98da54a4c7a363a`**, 0 tệp cấm. Xuất kiểm 4 tệp với công thức `` `$\frac{12}{4} + \sqrt{9}$` ``: `docx_student` `37,089 B` (`2 m:oMath`, 0 rò), `docx_teacher` `37,482 B` (`2 m:oMath`, đủ đáp án/rubric), `pdf_student` `65,366 B` (0 rò), `pdf_teacher` `81,815 B` (đủ đáp án/rubric), đồng thời qua kiểm sống 3 cụm API mở rộng (kế thừa bản 48 `1a28c3...`) | Thư mục `%TEMP%` và server thử đã dọn sạch |
| Model thật cục bộ Ollama `qwen3:4b` (Vulkan) | Model cục bộ (ngữ liệu tự tạo) | **v1** (`269cd6a`): `900.707s`, `timeout`, `8` lần kiểm, `traceVerified=true`. **v2** (sau `47c40f8`): `901.081s`, `status="failed"`, `errorCode="timeout"`, `checkedAttempts=7` (`19` lượt gọi `894.01s`), `traceVerified=true`, `evidenceIssues=[]`, `beforeRevision == afterRevision == 2`. **4/5 câu (`ordinal 0, 2, 3, 4`) qua `blind_content_check` và dùng lại cache** (`24.0s–45.4s`/vòng thay ~`121s`), còn `ordinal 1` thất bại | Giới hạn suy luận model 4B trên câu có hai số liệu (`24 sách truyện và 16 sách khoa học`) |

## 5. Bảng truy vết 30 issue (`#1–#24`, `#26–#31`) và phần còn mở

Tổng độ phủ bằng chứng đã xác minh tới phiên bản này (đồng bộ với `BAN_GIAO_QA/truy-vet-final.json`): **Nghiệm thu `99/146` · Công việc `132/150` · Ca kiểm `85/90`**. Mọi mục phụ thuộc con người, người dùng thật, peer review chéo hoặc GreenNode vẫn giữ rỗng trung thực.

| Issue | Mảng / CT | Acc | Work | Cases | Bằng chứng kỹ thuật chính trên Git | Phần còn chờ (Blocker giữ chưa đóng) |
| --- | --- | --- | --- | --- | --- | --- |
| [#1](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/1) | UI-1 M1 | 3/5 | 4/5 | 3/3 | [luong-man-hinh.md](../design/luong-man-hinh.md), [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py), [test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py) | Review chéo UI-2/UI-3/BE-2 (`W05`, `ACC3`, `ACC5`) |
| [#2](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/2) | UI-2 M1 | 3/5 | 5/5 | 3/3 | [editor-va-richdoc.md](../design/editor-va-richdoc.md), [ui2-baseline-browser.mjs](../../tests/ui2-baseline-browser.mjs), [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py) | Chốt liên mảng với BE-3 (`ACC3`, `ACC5`) |
| [#3](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/3) | UI-3 M1 | 4/5 | 4/5 | 3/3 | [tro-ly-va-job.md](../design/tro-ly-va-job.md), [test_check_routes.py](../../backend/tests/test_check_routes.py), [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py) | Review keyboard/mobile/PoC với backend (`W05`, `ACC5`) |
| [#4](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/4) | BE-1 M1 | 4/5 | 5/5 | 3/3 | [ai.md](../contracts/ai.md), [matrix_agent.py](../../backend/src/mach_backend/matrix_agent.py), [test_matrix_agent.py](../../backend/tests/test_matrix_agent.py) | Review nghiệm thu nhóm (`ACC5`) |
| [#5](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/5) | BE-2 M1 | 3/5 | 4/5 | 3/3 | [http.md](../contracts/http.md), [team_workspace.py](../../backend/src/mach_backend/team_workspace.py), [test_team_workspace.py](../../backend/tests/test_team_workspace.py) | Review đa vai trò và chốt recovery trước public (`W05`, `ACC3`, `ACC5`) |
| [#6](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/6) | BE-3 M1 | 4/5 | 5/5 | 3/3 | [du-lieu.md](../contracts/du-lieu.md), [be3_schema_migration.py](../../backend/src/mach_backend/be3_schema_migration.py), [test_be3_workspace_bridge.py](../../backend/tests/test_be3_workspace_bridge.py) | Báo cáo nghiệm thu nhóm (`ACC5`) |
| [#7](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/7) | BE-4 M1 | 3/5 | 4/5 | 3/3 | [tai-lieu.md](../contracts/tai-lieu.md), [test_source_documents.py](../../backend/tests/test_source_documents.py), [test_word_export.py](../../backend/tests/test_word_export.py) | Review trực quan học sinh/giáo viên cùng UI-2 (`W05`, `ACC3`, `ACC5`) |
| [#8](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/8) | BE-5 M1 | 4/5 | 4/5 | 3/3 | [job-va-sse.md](../contracts/job-va-sse.md), [ci.yml](../../.github/workflows/ci.yml), [test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py) | Review gates M1/M2/M3 liên nhóm (`W05`, `ACC5`) |
| [#9](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/9) | UI-1 M2 | 4/5 | 5/5 | 3/3 | [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py), [kiem-ui-khoi-phuc.mjs](../../scripts/kiem-ui-khoi-phuc.mjs), [test_team_workspace.py](../../backend/tests/test_team_workspace.py) | Nghiệm thu nhóm (`ACC5`) |
| [#10](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/10) | UI-2 M2 | 4/5 | 5/5 | 3/3 | [ui2-baseline-browser.mjs](../../tests/ui2-baseline-browser.mjs), [test_sample_exam_8b.py](../../backend/tests/test_sample_exam_8b.py), [KIEM_THU_TICH_HOP.md](KIEM_THU_TICH_HOP.md) | Nghiệm thu nhóm (`ACC5`) |
| [#11](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/11) | UI-3 M2 | 4/5 | 5/5 | 3/3 | [kiem-ui-de-xuat-sua.mjs](../../scripts/kiem-ui-de-xuat-sua.mjs), [test_poc_scoped_patch.py](../../backend/tests/test_poc_scoped_patch.py) | Nghiệm thu nhóm (`ACC5`) |
| [#12](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/12) | BE-1 M2 | 4/5 | 5/5 | 3/3 | [workspace_agent.py](../../backend/src/mach_backend/workspace_agent.py), [matrix_agent.py](../../backend/src/mach_backend/matrix_agent.py), [test_workspace_agent.py](../../backend/tests/test_workspace_agent.py) | Nghiệm thu nhóm (`ACC5`) |
| [#13](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/13) | BE-2 M2 | 4/6 | 5/5 | 3/3 | [team_workspace.py](../../backend/src/mach_backend/team_workspace.py), [DOI_CHIEU_PYTHON.md](DOI_CHIEU_PYTHON.md), [test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py) | Chốt invite-only vs email recovery (`ACC3`) và nghiệm thu nhóm (`ACC6`) |
| [#14](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/14) | BE-3 M2 | 4/5 | 5/5 | 3/3 | [be3_schema_migration.py](../../backend/src/mach_backend/be3_schema_migration.py), [test_be3_workspace_bridge.py](../../backend/tests/test_be3_workspace_bridge.py), [test_workspace_backup.py](../../backend/tests/test_workspace_backup.py) | Nghiệm thu nhóm (`ACC5`) |
| [#15](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/15) | BE-4 M2 | 5/6 | 5/5 | 3/3 | [word_export.py](../../backend/src/mach_backend/word_export.py), [tai-lieu.md](../contracts/tai-lieu.md), [test_word_export.py](../../backend/tests/test_word_export.py) | Nghiệm thu nhóm (`ACC6`) |
| [#16](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/16) | BE-5 M2 | 4/5 | 5/5 | 3/3 | [patch_jobs.py](../../backend/src/mach_backend/patch_jobs.py), [test_check_routes.py](../../backend/tests/test_check_routes.py), [job-va-sse.md](../contracts/job-va-sse.md) | Nghiệm thu nhóm (`ACC5`) |
| [#17](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/17) | UI-1 M3 | 4/5 | 4/5 | 3/3 | [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py), [luong-man-hinh.md](../design/luong-man-hinh.md) | User study có consent & peer review BE-2/BE-5 (`W05`, `ACC5`) |
| [#18](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/18) | UI-2 M3 | 3/5 | 4/5 | 3/3 | [ui2-baseline-browser.mjs](../../tests/ui2-baseline-browser.mjs), [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py) | Đối chiếu trực quan Word/PDF cùng BE-4 & reviewer (`W05`, `ACC3`, `ACC5`) |
| [#19](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/19) | UI-3 M3 | 4/5 | 5/5 | 3/3 | [kiem-ung-vien.py](../../scripts/kiem-ung-vien.py), [test_poc_scoped_patch.py](../../backend/tests/test_poc_scoped_patch.py), [KIEM_THU_TICH_HOP.md](KIEM_THU_TICH_HOP.md) | Reviewer tái lập & nghiệm thu nhóm (`ACC5`) |
| [#20](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/20) | BE-1 M3 | 1/5 | 3/5 | 3/3 | [ai.md](../contracts/ai.md), [KIEM_THU_TICH_HOP.md](KIEM_THU_TICH_HOP.md), tài liệu này (`qwen3:4b` v1/v2) | Thuận kiểm Jupyter/GreenNode, diễn tập rollback server & duyệt sư phạm bộ câu thật (`W04`, `W05`, `ACC1..3`, `ACC5`) |
| [#21](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/21) | BE-2 M3 | 3/5 | 4/5 | 3/3 | [test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py), [test_team_workspace.py](../../backend/tests/test_team_workspace.py), [http.md](../contracts/http.md) | Chốt rủi ro trước public & review OpenAPI parity (`W05`, `ACC3`, `ACC5`) |
| [#22](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/22) | BE-3 M3 | 3/5 | 5/5 | 3/3 | [test_be3_workspace_bridge.py](../../backend/tests/test_be3_workspace_bridge.py), [test_workspace_backup.py](../../backend/tests/test_workspace_backup.py) | Thuận review lệnh khôi phục trên bản sao trước chạm GreenNode (`ACC3`, `ACC5`) |
| [#23](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/23) | BE-4 M3 | 3/5 | 5/5 | 3/3 | [test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py), [tai-lieu.md](../contracts/tai-lieu.md), tài liệu này (4 file Word/PDF ZIP 48) | Kiểm tra bằng mắt đa môn bởi thành viên/giáo viên (`ACC1`, `ACC5`) |
| [#24](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/24) | BE-5 M3 | 3/5 | 5/5 | 3/3 | [BAO_CAO_DO_AN.md](../reports/BAO_CAO_DO_AN.md), [DOI_CHIEU_PYTHON.md](DOI_CHIEU_PYTHON.md), tài liệu này (ZIP 48 SHA-256) | Thành viên khác tự cài ZIP 48 kiểm Word/PDF, CI xanh bản đẩy mới, Thuận duyệt `BE-1-003` (`ACC3`, `ACC5`) |
| [#26](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/26) | CT-01 | **0/4** | **0/5** | **0/3** | [PROBLEM_BRIEF.md](../course/PROBLEM_BRIEF.md) (khung chờ dữ liệu) | Phỏng vấn >=3 người dùng thật có consent, benchmark 2–3 công cụ cùng tác vụ, Thuận chốt lịch lớp |
| [#27](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/27) | CT-02 | 2/4 | 4/5 | 1/3 | [WBS.md](../course/WBS.md), [BACKLOG.md](../team/BACKLOG.md) | Chia issue con thực tế khi vượt 1 ngày, cập nhật Kanban và Thuận chốt lịch môn (`W03`, `T02`, `T03`, `ACC3`, `ACC4`) |
| [#28](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/28) | CT-03 | 3/4 | 4/5 | 3/3 | [CONTRACTS.md](../course/CONTRACTS.md), 5 tệp `docs/contracts/*.md` | Peer review đối chiếu model ↔ OpenAPI ↔ repository ↔ slide (`W05`, `ACC4`) |
| [#29](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/29) | CT-04 | 3/4 | 5/5 | 3/3 | [POC.md](../course/POC.md), [test_poc_scoped_patch.py](../../backend/tests/test_poc_scoped_patch.py), tài liệu này | Reviewer độc lập và kết luận model thật sau duyệt sư phạm (`ACC4`) |
| [#30](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/30) | CT-05 | 4/4 | 5/5 | 3/3 | [ALGORITHM.md](../course/ALGORITHM.md), [test_poc_scoped_patch.py](../../backend/tests/test_poc_scoped_patch.py), [test_matrix_agent.py](../../backend/tests/test_matrix_agent.py) | Phần lớn đạt; `W05` sẵn sàng cho review độc lập trước bảo vệ |
| [#31](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/31) | CT-06 | 2/4 | 4/5 | 3/3 | [EVALUATION.md](../course/EVALUATION.md), [BAO_CAO_DO_AN.md](../reports/BAO_CAO_DO_AN.md), tài liệu này | Bằng chứng usability/a11y có người dùng thật, review từ máy thành viên khác & lịch nộp lớp (`W05`, `ACC1`, `ACC4`) |

## 6. Lệnh tái lập sạch

```powershell
# Từ thư mục backend/
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run ty check src
uv run pytest -q

# Từ gốc repo
npm ci
npm run check:team
npm test
npm run build-editor

# Tích hợp trình duyệt IT-01..IT-11 (fixture) và đóng gói ZIP sạch
uv run --project backend python scripts/kiem-ung-vien.py outputs/qa-ung-vien-49
uv run --project backend python scripts/dong-goi-ban-thu.py --ung-vien 49
```
