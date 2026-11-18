# Đặc tả Kỹ thuật Editor, `richDoc` & Hợp đồng Baseline (`UI-2-001`)

**Ngày lập:** 16/11/2026  
**Mảng / Task:** `UI-2` — `UI-2-001` ([Issue #2](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/2))  
**Nhánh Git:** `feat/UI-2-001-editor-spec` (tách độc lập từ `origin/main` tại `cecfd3d`)  
**Phạm vi M1:** Đặc tả hiện trạng kế thừa, lập bộ golden fixture (`tests/fixtures/ui2-editor-golden.json`), kiểm chứng `T01`–`T03` và ghi nhận bằng chứng 4 lỗi/điểm yếu nền. **Không sửa mã nguồn production** (`editor.js`, `composer.js`, `pages.js`, `storage.js`, `app.js`, `composer.css`, …) trong PR này; toàn bộ phần sửa code và tinh gọn CSS thuộc `UI-2-002` ([Issue #10](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/10)).  
**Vai trò kiến trúc:** Theo [kế hoạch chuyển Python](../architecture/PYTHON_MIGRATION.md), Python (`backend/`) là ngôn ngữ chính cho API, lưu trữ, kiểm tra nghiệp vụ/version và validation phía server; bộ editor JavaScript (`TipTap 3 + MathLive + KaTeX`) là lớp giao diện trình duyệt hỗ trợ.

---

## 1. `W01` — Bộ mẫu đa môn & đề dài ([`ui2-editor-golden.json`](../../tests/fixtures/ui2-editor-golden.json))

Toàn bộ dữ liệu kiểm chứng là **dữ liệu tổng hợp tự soạn (`synthetic`)**, không sử dụng tài liệu đề thi thật của giáo viên và không gọi AI thật. Tệp [`tests/fixtures/ui2-editor-golden.json`](../../tests/fixtures/ui2-editor-golden.json) gồm 3 khóa gốc:

1. **`multiSubjectExam`** (`id: cc62f9d2-918f-4ef7-a5e7-437ed5e603f6`, `revision: 1`, 3 câu hỏi đa môn):
   - **Câu 1 — Toán (`essay`, 4 điểm, `id: d74903bf-7c45-4f04-8205-8ac237a478de`):**
     - `richDoc` chứa hệ phương trình `\begin{cases}x+y=9\\xy=20\end{cases}`, phân thức `\frac{x+3}{2}`, bảng 3×3 (`table` / `tableRow` / `tableCell`), kèm `figure` dựng từ tọa độ (`triangleFigure()` — tam giác `ABC`, chân đường cao `D=foot(A,B,C)`, `O=circumcenter(A,B,C)`, `H=orthocenter(A,B,C)`).
     - Có `explanationDoc` và 2 bước `rubric[].richDoc` (2 + 2 điểm).
   - **Câu 2 — Hoá học (`mcq`, 3 điểm, `id: 73ab288e-285a-46b9-8223-693e355b6868`):**
     - `richDoc` và 4 `optionDocs` dùng `mhchem`: `\ce{2H2 + O2 ->[nhiệt] 2H2O}` cùng các phương án nhiễu, kèm `explanationDoc`.
   - **Câu 3 — Ngữ văn (`essay`, 3 điểm, `id: 377daef0-96f0-4006-bce7-005d09a5a10d`):**
     - `richDoc` đa đoạn tiếng Việt có dấu đầy đủ, gắn `quote` (`quote-ver-01`) đối chiếu ngữ liệu minh họa, kèm `explanationDoc` và 2 bước `rubric[].richDoc` (1.5 + 1.5 điểm).
   - Bảo toàn đủ `blockIds` cấp đề (`heading`, `general`, `marking`) và 8 `blockIds` mỗi câu (`stem`, `explanation`, `rubric`, `figure`, `options`, `answer`, `answerText`, `truthValues`).

2. **`longPaginatedExam`** (`id: 46473f2e-a903-49fc-a996-6d2cf9896ce7`, `revision: 1`, 10 câu hỏi):
   - Gồm 8 câu trắc nghiệm (`mcq`, mỗi câu 0.75 điểm), 1 câu tự luận Toán (Vi-ét, 2 điểm) và 1 câu tự luận dài (2 điểm) có **bảng thống kê 18 dòng + 4 đoạn phân tích**.
   - Khi mở trên giao diện thật ([`pages.js`](../../pages.js)), câu cuối đạt chiều cao ~`1230.34px` vượt ngưỡng `--page-content-height: 1113px`, tạo ra **5 trang `.document-page`** và **1 trang `.oversize-page`**.

3. **`edgeCases` (Biên & Từ chối):**
   - `duplicateFormulaDoc`: 1 đoạn văn tiếng Việt nhiều dấu chứa **2 node `mathInline` giống hệt nhau** (`latex: "x+1"`, `display: false`).
   - `crossTableTextEdit`: cặp `(doc, before, after)` mô tả thay đổi text xóa ký tự ngăn cột ` | ` cắt ngang ranh giới ô bảng 3×3 của Câu 1.

---

## 2. `W02` — Đặc tả kiến trúc đang kế thừa & 4 Lỗi/Điểm yếu đã kiểm chứng

### 2.1. Kiến trúc editor hiện hành (`TipTap 3 + MathLive + pages.js`)

| Thành phần | Tệp nguồn | Cơ chế kế thừa chính |
|---|---|---|
| Lõi soạn thảo `TipTap 3` | [`editor.js`](../../editor.js) | Dùng bundle [`assets/editor-engine.js`](../../assets/editor-engine.js) gồm `StarterKit({undoRedo:false, link:{openOnClick:false}})`, `StyledText` (`fontFamily`, `fontSize`), `Color`, `Highlight`, `TextAlign`, `Table`/`TableRow`/`TableHeader`/`TableCell`, `UniqueID({updateDocument:false, types:['paragraph','heading','table','mathInline']})` và node nguyên tử `InlineMath` render bằng KaTeX + `mhchem`. |
| Ánh xạ vị trí & render `richDoc` | [`rich-document.js`](../../rich-document.js) | `documentPlain(doc)` tuần tự hóa `mathInline` thành `$...$` hoặc `$$...$$`, nối các ô trong `tableRow` bằng `' | '` và các block bằng `'\n'`. `richPositionMap(doc)` ánh xạ vị trí ProseMirror (mỗi `mathInline`/`hardBreak`/`horizontalRule` chiếm size `1`) sang offset ký tự trong `documentPlain`. `richSelection(doc, from, to)` trả `{start, end, text}` hoặc `null`. |
| Định vị công thức & sửa cục bộ | [`editor.js#L35-L37`](../../editor.js#L35-L37) | `scopeForFormula(key, latex, position)` đối chiếu `node.type.name === 'mathInline' && node.attrs.latex === latex` và `pos === Number(position)` (hoặc duy nhất 1 match), rồi gọi `richSelection`. `reconcileEditorRich(doc, before, after)` tìm vùng chênh prefix/suffix trên `before`/`after`, nới biên ra ngoài `mathInline` nếu cắt ngang công thức, ánh xạ `from`/`to` qua `richPositionMap`, thay thế bằng `pm.replace(from, to, slice)` và giữ `attrs.id` của mọi node không đổi qua `retainUnchangedRichNodes`. Nếu `from === null || to === null` hoặc `documentPlain(result) !== after` thì ném lỗi giữ nguyên `doc`. |
| Lịch sử & `blockIds` | [`core.js#L51-L54`](../../core.js#L51-L54), [`blocks.js#L16-L33`](../../blocks.js#L16-L33) | `commit` / `commitTyping` (gom thao tác gõ trong `2000ms` theo `coalesceKey`), `undo` (tối đa `60` bước), `redo`, `history` (tối đa `100` mốc). `ensureBlocks` bảo đảm 3 UUID cấp đề + 8 UUID/câu. `applyEdits` thực hiện theo kiểu nguyên tử (nếu `richTransform` ném lỗi ở câu sau thì không ghi vào `exam` gốc). |
| Thư viện giảng dạy & `MathLive` | [`composer.js`](../../composer.js), [`authoring-catalog.js`](../../authoring-catalog.js) | `19` nhóm môn (`SUBJECTS`), `485` mẫu (`CATALOG`). Nạp động `assets/mathlive/mathlive.min.mjs` khi mở panel; tự nhận diện cấu trúc `cases` / `\ce{...}` qua `inferBuilder(latex)`. |
| Phân trang DOM A4 | [`pages.js`](../../pages.js) | `mountPages` tính `--page-content-height = (1301 - margin*2 - 32)px` (mặc định `margin = 78px` $\rightarrow$ `1113px`; fallback CSS `1040`). Khi `editor-content-changed` hoặc `resize` nổ, `schedulePages` chạy `layoutPages()` trong `requestAnimationFrame`: di chuyển các node con thật của `.paper` vào các `.document-page`, giữ focus/selection trong `.ProseMirror` và neo vị trí cuộn. |

### 2.2. Rà soát selector an toàn trước khi thiết kế lại `composer`

Kiểm tra toàn bộ `tests/*.mjs` và `tests/*.test.mjs` bằng `Select-String -Pattern "composer-subject"` ghi nhận:
- **0 match** trong tất cả các bộ test nền hiện có (`selection-browser.mjs`, `authoring-browser.mjs`, `curriculum-browser.mjs`, `studio-browser.mjs`, …).
- Duy nhất **1** dòng trong script đo baseline mới [`tests/ui2-baseline-browser.mjs#L366`](../../tests/ui2-baseline-browser.mjs#L366) dùng `document.querySelector('.composer-subjects')` chỉ để đo chiều cao tầng nút môn trong Bug C.
- Ngược lại, [`tests/curriculum-browser.mjs`](../../tests/curriculum-browser.mjs) và [`tests/authoring-browser.mjs`](../../tests/authoring-browser.mjs) thao tác trực tiếp vào `#catalog-subject` (kiểm đủ 19 môn), `#catalog-grade`, `#catalog-topic`, `#catalog-type`, `#catalog-earlier`, `#catalog-global`, `#catalog-search`. Do đó ở `UI-2-002` **tuyệt đối phải giữ nguyên các ID `#catalog-*` này**.

### 2.3. Danh mục 4 lỗi / điểm yếu đã kiểm chứng

| Mã | Tên vấn đề | Vị trí mã nguồn | Cách kiểm chứng & Bằng chứng thực tế (`ui2-baseline-report.json`) |
|---|---|---|---|
| **Bug A** | Lazy-mount `.rich-pending` ép con trỏ xuống cuối đoạn ở lần click đầu | [`editor.js#L23`](../../editor.js#L23) | **Tái hiện động (Playwright):** Trên `longPaginatedExam` (`qid: 440d965c-c41b-4e66-a018-a49a0c37cdec`, `field: "option"`), trước `pointerdown` ô có `isPending: true, editorMounted: false, hasTipTap: false`. Khi nhận `pointerdown`, listener gọi `createEditor(container)` rồi chạy thẳng `editor?.commands.focus('end')`, chuyển sang `isPending: false, editorMounted: true, hasTipTap: true` nhưng ép vùng chọn xuống cuối thay vì vị trí click của người dùng. |
| **Bug B** | Nuốt lỗi `409 Conflict` khi lưu `PUT /api/kv` | [`storage.js#L13`](../../storage.js#L13), [`app.js#L21-L23`](../../app.js#L21-L23) | **Tái hiện động (Playwright):** `storage.js` gửi `If-Match: String(stateRevision)` và ném lỗi khi `!response.ok`, nhưng `app.js:23` bọc `persist().catch(()=>{})` còn `app.js:21` chỉ đổi `[data-save-status]` thành `'Đã lưu tạm · chờ đồng bộ'`. Khi chặn `PUT /api/kv` trả `409 {error: "Phiên bản thay đổi"}`, `ui2-baseline-report.json` ghi nhận `interceptedStatus: 409`, `saveStatusText: "Đã lưu tạm · chờ đồng bộ"`, `dialogOpen: false`, `conflictModalPresented: false`. |
| **Bug C** | Mật độ chật & lặp chọn môn trong Thư viện công thức ở `1366×768` | [`composer.js#L9`](../../composer.js#L9), [`composer.css#L8-L9`](../../composer.css#L8-L9) | **Đo đạc động (Playwright `1366×768`):** `.composer-shell` có `width: 1080px, height: 720px` (`maxHeight: 720px`, `overflow: hidden`, `scrollHeight: 3138`). Tổng chiều cao 3 tầng phần đầu (`heading: 123px` + `subjects: 54px` + `filters: 112px` = `289px`) cộng `foot: 74px` chiếm `363px` (> 50% chiều cao khung). Hai khung làm việc chỉ còn `library: 357px` (`libraryScrollHeight: 3056`) và `work: 357px` (`workScrollHeight: 598`). Thanh `.composer-subjects` (6 nút) lặp chức năng của `#catalog-subject` (19 môn). |
| **Bug D** | Debounce `550ms` & thao tác toolbar trước `550ms` thiếu `flushEditor()` + chưa khóa IME | [`editor.js#L22`](../../editor.js#L22), [`app.js#L87,L100-L101,L125`](../../app.js#L87), [`studio.js#L38`](../../studio.js#L38) | **Kiểm chứng tĩnh trong mã nguồn (chưa đo race `< 550ms` bằng Playwright):** `onUpdate` đặt `timers.set(key, setTimeout(() => flush(editor), 550))`. Phím tắt `Ctrl+Z` (`editor.js:22`) gọi `flushEditor()` trước `ctx.act('undo')`, còn nhánh `handleAction` (`app.js:87`) cho các nút toolbar `[data-action="undo"]` (`app.js:125`) hay `[data-action="view-student"]`/`[data-action="view-teacher"]` (`app.js:100-101`) **không** gọi `flushEditor()`. Ngoài ra `editor.js` chưa có cờ `compositionstart` / `compositionend` cho bộ gõ tiếng Việt (Telex/VNI). *(Trong `ui2-baseline-browser.mjs`, helper `saved()` chờ `> 600ms` để debounce kịp xả nên Bug D được ghi nhận theo kiểm chứng tĩnh cấu trúc code).* |

---

## 3. `W03` — Kết quả chạy Golden Round-trip (`T01`–`T03`) & Các bộ kiểm thử nền

Tất cả lệnh chạy cục bộ không gọi AI thật, dùng dữ liệu tổng hợp và xuất ảnh đối chiếu ra thư mục ngoài repo (`$env:TEMP\ui2-001-baseline`).

| Bộ kiểm / Ca | Lệnh chạy | Kết quả kỳ vọng (Expected) | Kết quả thực chạy (Actual) |
|---|---|---|---|
| Kiểm tra kế hoạch & liên kết | `npm run check:team` | `team.test.mjs`, `github-bootstrap.test.mjs`, `task-details.test.mjs` và `scripts/check-team.mjs` pass 100% | **14/14 PASS** + `Team plan OK: 8 roles (3 UI + 5 backend), 24 tasks, 3 milestones...` |
| Unit test Node nền | `npm test` | Toàn bộ 98 test Node pass | **98/98 PASS** |
| Golden Node (`T01`, `T03`) | `node --test tests/ui2-golden.test.mjs` | 3 ca pass: fixture + `undo`/`redo` giữ `richDoc`, xuất Word OMML (`<m:m>`) & PDF (`%PDF-`) tách bản HS/GV, `richPositionMap`/`richSelection` chọn đúng `$x+1$` thứ hai | **3/3 PASS** |
| Baseline Playwright (`T01`–`T03` + Bug A–D) | `node tests/ui2-baseline-browser.mjs` | `T01` tạo `>= 3` `.document-page` & `>= 1` `.oversize-page`, sửa/reload giữ 8 `blockIds`, `undo` khôi phục `richDoc`; `T02` từ chối sửa cắt bảng giữ nguyên `doc`; `T03` `scopeForFormula` chọn offset thứ 2; 0 page errors | **PASS (8/8 báo cáo)** — `T01`: `documentPageCount: 5`, `oversizePageCount: 1`, `blockIdsCount: 8`, `blockIdsPreservedAcrossReload: true`, `undoRestoredRichDoc: true`; `T02`: ném `"Chọn riêng một đoạn văn hoặc một ô bảng để giữ định dạng khi sửa."`, `docUntouched: true`; `T03`: `expectedStartIndex: 127`, `actualStartIndex: 127`, `selectedSecondOccurrence: true`; `errors: []`. |
| 4 bộ browser nền (Task 1 baseline) | `node tests/selection-browser.mjs`, `authoring-browser.mjs`, `curriculum-browser.mjs`, `studio-browser.mjs` | Tất cả kịch bản hiện có đều pass khi chưa sửa code production | **45/45 PASS** (`selection`: 9 PASS; `authoring`: 12 PASS; `curriculum`: 13 PASS; `studio`: 11 PASS) |
| Kiểm soát file ảnh trong git | `git ls-files *.png` | Rỗng (không commit `.png` vào repo) | **Rỗng (0 file)**; 3 ảnh (`UI2_Baseline_Da_Mon.png`, `UI2_Baseline_De_Dai.png`, `UI2_Baseline_Composer_1366.png`) xuất ra `$env:TEMP\ui2-001-baseline`. |

---

## 4. `W04` — Hợp đồng DTO lưu/patch & Ma trận `409 Conflict` (`UI-2 <-> BE-3 / BE-1 / BE-2`)

### 4.1. Hợp đồng trường JSON bất biến cần bảo toàn

- **Cấp đề:** `id`, `revision`, `title`, `subject`, `grade`, `minutes`, `layout`, `blockIds` (`{heading, general, marking}`), `draftStatus` (nếu bổ sung ở pha sau).
- **Cấp câu hỏi:** `id` (UUID bất biến), `v` (version `>= 1`), `stem`, `richDoc` (không đổi thành `stemDoc`), `runs`, `options`, `optionDocs` (không đổi thành `optionsDoc`), `explanation`, `explanationDoc`, `rubric` (`[{text, points, richDoc?}]`), `figure`, `figureDoc`, `formulas`, `tables`, `images`, `pageBreak`, `source`, `check`, `blockIds` (8 khóa: `stem`, `explanation`, `rubric`, `figure`, `options`, `answer`, `answerText`, `truthValues`).
- **Bất biến đồng bộ plain-text & rich-text:** `documentPlain(q.richDoc) === q.stem`, `documentPlain(q.explanationDoc) === q.explanation`, `documentPlain(q.optionDocs[j]) === q.options[j]`, `documentPlain(q.rubric[k].richDoc) === q.rubric[k].text`. Không được làm phẳng `richDoc` thành chuỗi thuần khi lưu hoặc patch.

### 4.2. Trạng thái thực tế ở các PR mở & Ma trận xử lý `409 Conflict`

> **Lưu ý tham chiếu liên PR:** Nhánh `feat/UI-2-001-editor-spec` tách từ `origin/main` chưa merge các PR hợp đồng bên dưới, nên mọi tham chiếu dẫn trực tiếp bằng liên kết GitHub PR để tránh link 404 trên `main`:
> - `BE-3-001`: [PR #38](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/38) (`docs/contracts/du-lieu.md`, `be3_schema_migration.py`)
> - `BE-1-001`: [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) (`docs/contracts/ai.md`, `ai_contract.py`, `patch_confirmation.py`)
> - `BE-2-001`: [PR #41](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/41) (`docs/contracts/http.md`)

| Tình huống HTTP / Lỗi | Nguồn phát sinh hiện trạng | Payload quan sát được | Hành vi kỳ vọng phía `UI-2` ở M2 (`UI-2-002`) |
|---|---|---|---|
| Mất mạng / timeout | Lỗi mạng trình duyệt / `fetch` ném lỗi | `TypeError` / `!navigator.onLine` | Giữ hàng đợi `__pending:state` trong IndexedDB ([`storage.js#L12-L13`](../../storage.js#L12-L13)), hiển thị `'Đã lưu tạm · chờ đồng bộ'`, tự thử lại khi có sự kiện `online`. |
| Xung đột phiên bản (Node legacy) | [`mvp-server.mjs#L42`](../../mvp-server.mjs#L42), [`backend-store.mjs#L8`](../../backend-store.mjs#L8) | `409 {error: "Dữ liệu đã được thay đổi ở cửa sổ khác. Hãy tải lại trước khi tiếp tục."}` | **Không** gán nhãn `'Đã lưu tạm'`; mở modal xung đột cho giáo viên chọn **Tải lại bản mới** hoặc **Nhân bản bản đang sửa thành đề riêng**. |
| Xung đột phiên bản (Python BE-3/BE-2) | [PR #38](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/38) & [PR #41](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/41) | `du-lieu.md` ghi `409 REVISION_CONFLICT`; `be3_schema_migration.py` mặc định `code="stale_snapshot"` kèm `current_revision`; `http.md` chờ chốt chuẩn biểu diễn `If-Match` | Đề xuất chuẩn hóa envelope đọc được cả `code` (`REVISION_CONFLICT` / `stale_snapshot`), `message` tiếng Việt và `current_revision`; hiển thị 3 tầng phiên bản (`workspace_revision`, `exams.revision`, `questions.version`) tương ứng và chặn ghi đè mù. |
| Công thức AI không hợp lệ | [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39) (`/proposals/{job_id}/confirm`) | `409 {"detail": {"code": "invalid_math", "message": "..."}}` *(hiện **chưa có** `field`, `blockId` hay vị trí offset)* | **Giữ nguyên toàn bộ trạng thái editor/composer hiện tại** (không đóng hộp thoại hoặc xóa bản nháp), hiển thị rõ `detail.message` để sửa lại; nếu sau này BE-1/BE-2 bổ sung `blockId`/`field` thì UI sẽ highlight đúng khối. |

---

## 5. `W05` — Trường hợp chưa hỗ trợ, Đề xuất `UI-SPEC` (`UI-2-002`) & Bàn giao

### 5.1. Giới hạn & trường hợp chưa hỗ trợ quan sát được ở baseline

1. **Phân trang bảng/câu dài ([`pages.js#L9`](../../pages.js#L9)):** Nếu một `.question` (ví dụ có bảng thống kê 18 dòng như Câu 10 trong `longPaginatedExam`) cao hơn `--page-content-height`, `layoutPages()` chỉ gắn lớp `.oversize-page` lên `.document-page` chứa câu đó mà **chưa tách nhỏ bảng nội bộ trong `stem`** qua nhiều trang (chỉ bảng barem `#marking-guide .full-rubric-table` được tách theo từng `<tr>`).
2. **Xuất Word OMML / hình vẽ ([`exports.mjs#L20-L46`](../../exports.mjs#L20-L46), [`math-word.mjs`](../../math-word.mjs)):**
   - Lệnh LaTeX ngoài danh sách ánh xạ chuẩn hoặc ngoài nhánh `extendedMathNodes` (`\binom`, `\underbrace`, `\begin{vmatrix}`, `\ce{...{...}`, …) sẽ rơi về văn bản thuần `MathRun('\\' + name)`.
   - `figure` dựng từ tọa độ SVG được raster hóa qua `@napi-rs/canvas` thành ảnh PNG (`width: 400`, canvas `1200px`) khi xuất `.docx`, không phải đối tượng hình vẽ chỉnh sửa được trong Word.
3. **Sửa cục bộ cắt ngang bảng ([`editor.js#L37`](../../editor.js#L37)):** `reconcileEditorRich` từ chối mọi thay đổi làm lệch ranh giới ô/hàng bảng (`documentPlain(result) !== after` hoặc `from`/`to` trả `null`), trả lỗi yêu cầu chọn một đoạn hoặc một ô nhỏ hơn.
4. **Thư viện công thức (`composer.js` / `authoring-catalog.js`):** Chưa dựng cấu trúc phân tử Hóa học 2D/3D, chưa kiểm thứ nguyên Vật lí tổng quát và `reactionBalance` chỉ kiểm các phương trình dạng `coeff Formula + ...` cơ bản.

### 5.2. Đề xuất `UI-SPEC` tinh gọn `composer.css` cho `UI-2-002` (An toàn selector)

Mục tiêu ở màn hình laptop `1366×768` (`max-height: 720px`) là giảm chiều cao phần đầu từ `289px` (`heading 123px + subjects 54px + filters 112px`) xuống dưới `~140–150px` để trả không gian cho `.composer-library` và `.composer-work`:

```text
+-------------------------------------------------------------------------+
| THƯ VIỆN GIẢNG DẠY · Chèn nội dung theo môn                         [×] |
+-------------------------------------------------------------------------+
| Môn học [Toán ▾] | Lớp [Tất cả ▾] | Chủ đề [Tất cả ▾] | Loại [Tất cả ▾] |
| [ ] Gồm kiến thức lớp trước                                             |
+-----------------------+-------------------------------------------------+
| [Tìm mẫu...]          | NỘI DUNG ĐANG SOẠN         [Trong dòng ▾]      |
| [ ] Tìm tất cả môn    | +---------------------------------------------+ |
| +-------------------+ | | Ô điền theo mẫu / MathLive trực quan        | |
| | Phân số (A/B)     | | +---------------------------------------------+ |
| | Hệ 2 phương trình | | KẾT QUẢ TRÊN TRANG                              | |
| | Phản ứng hóa học  | | +---------------------------------------------+ |
| +-------------------+ | |               (Render KaTeX)                | |
| [Hiện thêm 30 mẫu]    | +---------------------------------------------+ |
|                       | ▸ Mã công thức · Nâng cao (LaTeX)               |
+-----------------------+-------------------------------------------------+
| ◇ Xử lý tại máy                         [Xóa]   [Hủy]   [Chèn vào trang]|
+-------------------------------------------------------------------------+
```

- **Quy tắc bắt buộc khi triển khai ở `UI-2-002`:** Giữ nguyên toàn bộ ID DOM `#catalog-subject`, `#catalog-grade`, `#catalog-topic`, `#catalog-type`, `#catalog-earlier`, `#catalog-global`, `#catalog-search`, `#visual-math-input`, `#inline-math-input`, `#composer-save` hiển thị trực tiếp để `curriculum-browser.mjs` và `authoring-browser.mjs` không bị gãy. Có thể thu gọn/ẩn thanh `.composer-subjects` (vì đã kiểm chứng **0 match** trong các bộ test nền hiện có) và cập nhật lại phép đo ở `tests/ui2-baseline-browser.mjs` tương ứng.

### 5.3. Ghi chú bàn giao giữa các mảng

- **Gửi `UI-3`:** Mọi thao tác hỏi/sửa theo vùng chọn và công thức phải đi qua `scopeForFormula` ([`editor.js#L35`](../../editor.js#L35)), `reconcileEditorRich` ([`editor.js#L37`](../../editor.js#L37)) và `retainUnchangedRichNodes` ([`editor.js#L36`](../../editor.js#L36)) để bảo toàn `attrs.id` và 8 `blockIds`.
- **Gửi `BE-4`:** Bộ [`tests/fixtures/ui2-editor-golden.json`](../../tests/fixtures/ui2-editor-golden.json) đã kiểm tra round-trip `makeDocx` (OMML `<m:m>`) và `makePDF` (`%PDF-`) trên máy Node; khi port export sang Python ở M2/M3 cần đối chiếu parity trực quan với `multiSubjectExam` (bảng 3×3 + `figure` + `mhchem`) và `longPaginatedExam` (bảng 18 dòng `.oversize-page`).
- **Gửi `BE-3` / `BE-2` / `UI-1`:** Phối hợp chốt envelope lỗi `409` (`code`, `message`, `current_revision`) và cách truyền `If-Match` trước khi nối `UI-2-002`; riêng phần modal hiển thị lỗi `409` trong [`app.js`](../../app.js) sẽ hẹn đồng bộ với `UI-1-002` ([Issue #9](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/9)).

## Kiểm lại trên bàn soạn FastAPI

Đã chạy T01–T03 trên Chrome với FastAPI và kho tạm. Đề dài có 5 trang, trong đó 1 trang chứa khối lớn. Sửa và tải lại giữ 8 block ID. Hoàn tác khôi phục richDoc. Thao tác cắt qua bảng bị từ chối và công thức trùng thứ hai được chọn đúng. Bộ kiểm Word OMML/PDF riêng hiện chạy trong `npm test`.

Từ thư mục gốc, dùng PowerShell để chạy T01–T03 trên FastAPI sau khi đã cài Python theo [hướng dẫn backend](../../backend/README.md):

```powershell
$env:QA_PYTHON = (Resolve-Path backend/.venv/Scripts/python.exe).Path
$env:QA_OUTPUT = "outputs/ui2-fastapi"
node tests/ui2-baseline-browser.mjs
```

Đặt `QA_PYTHON` thành đường dẫn `backend/.venv/bin/python` trên Linux/macOS. Script tự chọn cổng loopback và tạo kho thử riêng. Báo cáo lỗi A–D ở trên thuộc baseline Node ban đầu. Đợt FastAPI này dùng các ca T01–T03 để xác nhận trình soạn và lưu đề.
