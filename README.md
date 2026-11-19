# Soạn đề thi

Trợ lý soạn đề thi tiếng Việt. Bản thử hiện dùng FastAPI cho backend và JavaScript cho giao diện.

**Muốn thử app?** Mở [trang kiểm thử #47](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/47) để tải bản mới, chọn ca thử và báo lỗi. Bản ZIP có tệp `CHAY_THU_NHOM.cmd` và hướng dẫn cài uv. Dùng `CHAY_DEMO_VA_LOG.cmd` nếu cần demo và ghi log JSON.

**Vừa sửa xong app?** Xem [cách phát hành bản thử](docs/team/KIEM_THU_NHOM.md#người-sửa-app). Từ một commit có CI xanh, người phụ trách có thể dùng [Actions → Phát hành bản thử](https://github.com/ngocthuan1505/proj_VA_soandethi/actions/workflows/phat-hanh-ban-thu.yml) để đóng ZIP và báo bản mới ở #47.

[Hướng dẫn chạy, demo và log](HUONG_DAN_TEST_NHOM.md) · [Bảng kiểm thử bản 13](docs/testing/NGHIEM_THU_BAN_13.md) · [Bảng tiến độ nhóm](https://github.com/users/ngocthuan1505/projects/1/views/1)

## Sửa app từ source

Nhận issue trước khi sửa, tạo nhánh từ phiên bản chứa lỗi, thêm kiểm thử hồi quy và mở PR có liên kết issue. [Hướng dẫn đóng góp](CONTRIBUTING.md) · [Tóm tắt repo](DOC_REPO_TRONG_5_PHUT.md) · [Báo tiến độ và nghiệm thu](docs/team/BAO_CAO.md).

- Backend nằm trong `backend/`. Từ thư mục đó chạy `uv sync --frozen`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` và `uv run ty check src`.
- Giao diện và kiểm hồi quy Node dùng `npm ci`, `npm test` và `npm run check:team` ở thư mục gốc. Backend Node cũ dùng để đối chiếu.
- Xem số đo GitHub Languages của `main`, kích thước mã của nhánh tích hợp và bằng chứng chạy API Python. [Đối chiếu Python](docs/testing/DOI_CHIEU_PYTHON.md)
- [Yêu cầu môn học](docs/course/README.md) và [kế hoạch tích hợp](docs/testing/KIEM_THU_TICH_HOP.md) lưu các tiêu chí nghiệm thu. Chỉ Thuận vận hành GreenNode.
