# Soạn đề thi

Trợ lý soạn đề thi tiếng Việt. Hệ thống dùng FastAPI/Python cho backend & nghiệp vụ chính và JavaScript cho trình soạn thảo giao diện.

**Tester** · [Tải ZIP trong Releases](https://github.com/ngocthuan1505/proj_VA_soandethi/releases) → [Mở app, chọn ca và báo kết quả ở #47](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/47).

**Người sửa app** · [Xem lỗi nhóm đã báo](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+is%3Aopen+label%3Atype%3Abug) → [Sửa qua PR và gửi bản mới cho tester](docs/team/KIEM_THU_NHOM.md#người-sửa-app).

## Tải và thử nhanh tại máy

1. Chọn bản phát hành mới nhất trong [Releases](https://github.com/ngocthuan1505/proj_VA_soandethi/releases) hoặc [bản thử 13](https://github.com/ngocthuan1505/proj_VA_soandethi/releases/tag/ban-thu-13), tải ZIP và giải nén vào thư mục mới.
2. Cài [uv](https://docs.astral.sh/uv/getting-started/installation/) nếu máy chưa có. Giải nén ZIP app (hoặc mở thẳng trong thư mục bản thử) rồi chạy `CHAY_THU_NHOM.cmd`. Mở `CHAY_DEMO_VA_LOG.cmd` nếu muốn demo quá trình AI và lưu log JSON.
3. Soạn và lưu một đề, tải lại trang, rồi xuất và mở Word/PDF của học sinh và giáo viên. Thử AI bằng khóa riêng đã được phép và ngữ liệu mẫu đi kèm.
4. Nếu gặp lỗi, [mở issue báo lỗi](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=bug.md). Ghi rõ số bản, hệ điều hành, bước tái hiện, kết quả mong đợi và kết quả thực tế. Dùng ảnh hoặc log đã bỏ khóa API và nội dung riêng.

[Xem hướng dẫn chạy, demo và log](HUONG_DAN_TEST_NHOM.md) · [Bảng kiểm thử bản 13](docs/testing/NGHIEM_THU_BAN_13.md) · [Nghiệm thu ứng viên 48](docs/testing/NGHIEM_THU_UNG_VIEN_48.md) · [Bảng tiến độ nhóm](https://github.com/users/ngocthuan1505/projects/1/views/1)

## Sửa app từ source

Mới đọc mã nguồn? Mở [bản tóm tắt repo trong 5 phút](DOC_REPO_TRONG_5_PHUT.md).

**Thành viên mới:** [Cẩm nang có link task và cách bật app](docs/team/HUONG_DAN_GUI_DISCORD.md) · [PDF để gửi Discord](docs/team/HUONG_DAN_NHOM_SOAN_DE_THI.pdf).

Nhận issue trước khi sửa, tạo nhánh từ phiên bản chứa lỗi, thêm kiểm thử hồi quy và mở PR có liên kết issue. [Hướng dẫn đóng góp](CONTRIBUTING.md) · [Báo tiến độ và nghiệm thu](docs/team/BAO_CAO.md).

- Backend nằm trong `backend/`. Từ thư mục đó chạy `uv sync --frozen`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` và `uv run ty check src`.
- Giao diện và kiểm hồi quy Node dùng `npm ci`, `npm test` và `npm run check:team` ở thư mục gốc. Backend Node cũ dùng để đối chiếu.
- Xem số đo GitHub Languages của `main`, kích thước mã của nhánh tích hợp và bằng chứng chạy API Python. [Đối chiếu Python](docs/testing/DOI_CHIEU_PYTHON.md)
- [Yêu cầu môn học](docs/course/README.md) và [kế hoạch tích hợp](docs/testing/KIEM_THU_TICH_HOP.md) lưu các tiêu chí nghiệm thu. Chỉ Thuận vận hành GreenNode.
