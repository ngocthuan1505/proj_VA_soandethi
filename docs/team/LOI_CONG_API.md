# API cổng 8000 không chạy, còn 8080 chạy được

Ảnh trao đổi của thành viên cho biết 8080 chạy được nhưng **không có log lỗi 8000 hoặc thông tin hệ điều hành/lệnh đầy đủ**. Chưa xác định nguyên nhân trên máy đó. App không buộc phải dùng 8000; cổng được truyền cho Uvicorn qua `--port`, không hardcode trong route Python.

## Chạy tiếp ở 8080

Từ thư mục `backend`, sau khi `uv sync --frozen --python 3.12`:

```sh
uv run uvicorn mach_backend.main:app --app-dir src --host 127.0.0.1 --port 8080 --reload
```

Mở **http://127.0.0.1:8080/docs** và **http://127.0.0.1:8080/api/health**. Không đổi lệnh sang 8080 rồi vẫn mở URL 8000. Ctrl+C dừng đúng server trong Terminal; không cần quyền admin hoặc mở firewall chỉ để dùng loopback.

`/api/readiness` trả **503** và `ready:false` hiện là chủ ý: Python mới foundation, chưa có auth/DB/core/jobs/tài liệu. Nó không chứng minh cổng lỗi. Muốn xem demo editor hiện tại dùng `npm start` và cổng **4173**, chưa phải nền FastAPI.

## Phân biệt lỗi bằng thông báo thật

| Triệu chứng / log | Khả năng và bước kiểm |
|---|---|
| `address already in use`, `WinError 10048` | Cổng/địa chỉ đã có listener hoặc đang được dùng. Xem PID, xác định đúng app rồi tự dừng server của mình hoặc chọn cổng khác; không kill mọi Python/Node |
| `permission denied`, `WinError 10013` | Lỗi quyền bind; có thể cổng bị Windows dành riêng hoặc ràng buộc phần mềm/mạng. Kiểm tra dải cổng, dùng cổng khác; chưa đủ bằng chứng để sửa firewall/chạy admin |
| `Could not import module`, thiếu `uvicorn`/module | Không phải lỗi cổng: kiểm đúng thư mục `backend`, sync lockfile và `--app-dir src` |
| Terminal báo đang chạy nhưng browser không vào | Kiểm đúng host/port, health URL, server còn sống; localhost của mỗi máy là riêng |
| Health 200, readiness 503 | Foundation đang chạy đúng, phần nghiệp vụ Python chưa hoàn thiện |

PowerShell trên **máy bị lỗi**, chỉ đọc:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress, LocalPort, OwningProcess
netsh interface ipv4 show excludedportrange protocol=tcp
netsh interface ipv6 show excludedportrange protocol=tcp
```

Nếu có PID, xem tên bằng `Get-Process -Id <PID-vừa-thấy>`; không gửi command line chứa token/password lên issue. Không có listener chưa đủ kết luận cổng chắc chắn dùng được: cần thử bind và xem lỗi thực tế. Linux/macOS có công cụ kiểm listener tương ứng; lệnh netsh/Get-NetTCPConnection chỉ cho Windows.

## Kết quả kiểm ở máy Thuận ngày 06/11/2026

Đã thử Uvicorn trên clone kiểm thử, lần lượt bind `127.0.0.1:8000` và `127.0.0.1:8080`, kiểm HTTP rồi dừng **đúng tiến trình vừa tạo**. Không dừng app 4173 hay tiến trình có sẵn; không đổi firewall/dải cổng. **Cả hai cổng đều chạy được:** `/api/health` 200, `/docs` 200 và `/api/readiness` 503 với `ready:false`. Không thấy listener hoặc dải cổng Windows dành riêng bao gồm 8000/8080 tại thời điểm kiểm tra. Đây chỉ là kết quả máy Thuận, không suy thành kết quả máy thành viên.

Nếu cần báo lại lỗi: ghi hệ điều hành, commit, thư mục đang đứng, lệnh chạy và nguyên đoạn log lỗi; che dữ liệu riêng. Chưa có log thì dùng 8080 để tiếp tục, giữ chẩn đoán “chưa xác định”.

Đối chiếu ý nghĩa mã socket trong [Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-error-codes-2). Tài liệu này giải thích cách phân biệt lỗi, không khẳng định thành viên gặp đúng lỗi nào.
