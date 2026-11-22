# Project instructions

- Mỗi lượt làm việc, đọc `docs/context/README.md`, `docs/context/LY_THUYET.md` và `docs/context/THUC_HANH.md` trước khi làm phần liên quan dự án. Hai chat nghiên cứu/thuyết trình và thực hành dùng các file này làm bản bàn giao chung; không mặc định đọc lại toàn bộ lịch sử chat bên kia.
- Trước khi kết thúc lượt có thay đổi đáng kể, cập nhật bản bàn giao đúng mảng bằng kết quả, bằng chứng, tác động tới bên kia và việc còn thiếu. Phân biệt đề xuất/thiết kế với tính năng đã chạy; không ghi đè phần bên kia chưa kiểm chứng, không lưu toàn bộ hội thoại hoặc bí mật. Không tự gửi prompt qua lại giữa chat.
- Viết commit, tiêu đề/mô tả PR, task và tài liệu hướng dẫn bằng tiếng Việt. Chỉ giữ tiếng Anh khi cần cho tên kỹ thuật, định danh, lệnh hoặc thông báo tương thích công cụ. Không viết lại lịch sử commit đã đẩy chỉ để đổi ngôn ngữ.
- Read `docs/team/README.md`, `docs/team/ROLES.md` and `docs/architecture/PYTHON_MIGRATION.md` before changing architecture.
- Đọc `docs/course/README.md` khi lập task/đánh giá đồ án; truy vết nguồn slide và bằng chứng CT-01…06. Báo tiến độ/vướng/nghiệm thu theo `docs/team/BAO_CAO.md`. Không bịa phỏng vấn, số đo, kết quả PoC hoặc deadline chưa xác nhận; giữ trạng thái/assignee/checklist người khác đã cập nhật.
- Python is the primary language required by the course. Implement backend/core/auth/database/jobs/AI validation in `backend/`; JavaScript supports the browser/editor and build tooling.
- Existing root Node API files are legacy references. Do not satisfy the Python requirement with a Python proxy that delegates core business logic to Node. Do not claim the FastAPI foundation has migrated features it does not implement.
- Preserve user data, UUIDs, revision conflicts, formulas and rich documents when porting behavior. Add focused pytest/contract tests for migrated slices and compare with legacy fixtures.
- Only the human project owner Thuận (`ngocthuan1505`, BE-1) operates GreenNode. Prepare code, tests and runbooks for review; do not log into or modify that server, start/stop services, or deploy from CI as part of ordinary development.
- Keep repo Private. Never commit real server URLs, keys, invitation codes, `.env`, `.data`, `.runtime`, model weights or teacher documents. Do not send real data to paid AI services without authorization.
- Do not invent usernames or invite collaborators without the owner's specified recipients. Update `docs/team/roster.json` only from known team identities.
- Coordinate shared files through the task issue; use small PRs with criteria and validation. Do not add frameworks or move all source merely to split ownership.
- UI/UX được phép học hỏi và áp dụng các mô hình bố cục, phân cấp thao tác và trải nghiệm tốt hơn từ công cụ tham chiếu (như luồng soandethi) rồi tinh chỉnh theo hướng của đồ án; tự triển khai sạch trên nền HTML/CSS/JS hiện có (không thêm framework, không chép mã nguồn/logo/thương hiệu có bản quyền, không gắn cơ chế nạp tiền) và giữ xanh toàn bộ test/E2E hiện hành.
- Python: from `backend`, run `uv sync --frozen`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- Legacy/UI regression: `npm ci`, `npm test`, `npm run check:team`; rebuild editor with `npm run build-editor` when needed. CI uses fixtures only.
- GitHub synchronization mutates issues/labels/milestones only with explicit `--apply` and verified Private/admin access. Preserve existing human edits, status and assignees.
