# Soạn đề thi

Trợ lý soạn đề thi tiếng Việt. Bản 13 dùng FastAPI cho backend và JavaScript cho giao diện.

## Tải và thử bản 13

1. Mở [bản thử 13](https://github.com/ngocthuan1505/proj_VA_soandethi/releases/tag/ban-thu-13), tải **Goi-nghiem-thu-nhom-13.zip** và giải nén. Mở `BAT_DAU.md` trong gói.
2. Cài [uv](https://docs.astral.sh/uv/getting-started/installation/) nếu máy chưa có. Giải nén ZIP app bên trong rồi mở `CHAY_THU_NHOM.cmd`. Mở `CHAY_DEMO_VA_LOG.cmd` nếu muốn demo quá trình AI và lưu log JSON.
3. Soạn và lưu một đề, tải lại trang, rồi xuất và mở Word/PDF của học sinh và giáo viên. Thử AI bằng khóa riêng đã được phép và ngữ liệu mẫu đi kèm.
4. Nếu gặp lỗi, [mở issue báo lỗi](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/new?template=bug.md). Ghi bản 13, hệ điều hành, bước tái hiện, kết quả mong đợi và kết quả thực tế. Dùng ảnh hoặc log đã bỏ khóa API và nội dung riêng.

[Xem hướng dẫn chạy, demo và log](HUONG_DAN_TEST_NHOM.md) · [Bảng kiểm thử và giới hạn bản 13](docs/testing/NGHIEM_THU_BAN_13.md) · [Bảng tiến độ nhóm](https://github.com/users/ngocthuan1505/projects/1/views/1)

## Sửa app từ source

Nhận issue trước khi sửa, tạo nhánh từ phiên bản chứa lỗi, thêm kiểm thử hồi quy và mở PR có liên kết issue. [Hướng dẫn đóng góp](CONTRIBUTING.md) · [Tóm tắt repo](DOC_REPO_TRONG_5_PHUT.md) · [Báo tiến độ và nghiệm thu](docs/team/BAO_CAO.md).

- Backend nằm trong `backend/`. Từ thư mục đó chạy `uv sync --frozen`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` và `uv run ty check src`.
- Giao diện và kiểm hồi quy Node dùng `npm ci`, `npm test` và `npm run check:team` ở thư mục gốc. Backend Node cũ dùng để đối chiếu.
- [Yêu cầu môn học](docs/course/README.md) và [kế hoạch tích hợp](docs/testing/KIEM_THU_TICH_HOP.md) lưu các tiêu chí nghiệm thu. Chỉ Thuận vận hành GreenNode.
