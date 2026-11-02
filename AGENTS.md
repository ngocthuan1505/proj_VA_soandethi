# Project instructions

- Viết commit, tiêu đề/mô tả PR, task và tài liệu hướng dẫn bằng tiếng Việt. Chỉ giữ tiếng Anh khi cần cho tên kỹ thuật, định danh, lệnh hoặc thông báo tương thích công cụ. Không viết lại lịch sử commit đã đẩy chỉ để đổi ngôn ngữ.
- Read `docs/team/README.md`, `docs/team/ROLES.md` and `docs/architecture/PYTHON_MIGRATION.md` before changing architecture.
- Python is the primary language required by the course. Implement backend/core/auth/database/jobs/AI validation in `backend/`; JavaScript supports the browser/editor and build tooling.
- Existing root Node API files are legacy references. Do not satisfy the Python requirement with a Python proxy that delegates core business logic to Node. Do not claim the FastAPI foundation has migrated features it does not implement.
- Preserve user data, UUIDs, revision conflicts, formulas and rich documents when porting behavior. Add focused pytest/contract tests for migrated slices and compare with legacy fixtures.
- Only the human project owner Thuận (`ngocthuan1505`, BE-1) operates GreenNode. Prepare code, tests and runbooks for review; do not log into or modify that server, start/stop services, or deploy from CI as part of ordinary development.
- Keep repo Private. Never commit real server URLs, keys, invitation codes, `.env`, `.data`, `.runtime`, model weights or teacher documents. Do not send real data to paid AI services without authorization.
- Do not invent usernames or invite collaborators without the owner's specified recipients. Update `docs/team/roster.json` only from known team identities.
- Coordinate shared files through the task issue; use small PRs with criteria and validation. Do not add frameworks or move all source merely to split ownership.
- Python: from `backend`, run `uv sync --frozen`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- Legacy/UI regression: `npm ci`, `npm test`, `npm run check:team`; rebuild editor with `npm run build-editor` when needed. CI uses fixtures only.
- GitHub synchronization mutates issues/labels/milestones only with explicit `--apply` and verified Private/admin access. Preserve existing human edits, status and assignees.
