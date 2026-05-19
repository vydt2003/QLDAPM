# ProjectManagementOrderFood

Nền tảng trung gian kết nối khách hàng với nhà hàng/quán ăn. Hệ thống cho phép khách hàng tìm kiếm nhà hàng, xem thực đơn, thêm món vào giỏ hàng, đặt hàng và thanh toán; đồng thời cung cấp cho nhà hàng công cụ quản lý món ăn, tiếp nhận và xử lý đơn hàng.

## 1. Tổng quan

Project được xây dựng theo hướng ứng dụng web với Flask. Phần lõi hiện tại tập trung vào các luồng nghiệp vụ chính:

- Khách hàng:
  - Tìm kiếm nhà hàng và món ăn
  - Xem thực đơn, chi tiết món ăn
  - Thêm món vào giỏ hàng
  - Quản lý số lượng món trong giỏ
  - Đặt hàng và thanh toán
  - Theo dõi lịch sử đơn hàng
  - Đánh giá món ăn

- Nhà hàng:
  - Quản lý thông tin nhà hàng
  - Thêm/sửa/cập nhật trạng thái món ăn
  - Tiếp nhận đơn hàng
  - Xác nhận và hoàn tất đơn hàng
  - Xem thống kê doanh thu

- Quản trị viên:
  - Quản lý dữ liệu qua Flask-Admin
  - Theo dõi thống kê tổng quan

Ngoài ra, hệ thống có các tính năng hỗ trợ:

- Thông báo thời gian thực bằng Socket.IO
- Tạo hóa đơn PDF
- Tích hợp PayPal Sandbox cho thanh toán thử nghiệm
- Gợi ý món ăn dựa trên lịch sử đặt hàng và món thường đi kèm
- Phân tích đánh giá món ăn ở mức rule-based

## 2. Công nghệ sử dụng

- Backend: Flask, Flask-Login, Flask-SQLAlchemy, Flask-SocketIO
- Frontend: Jinja2, Bootstrap, JavaScript
- Cơ sở dữ liệu: MySQL
- Realtime: Socket.IO + Eventlet
- Upload ảnh: Cloudinary
- Gửi email: Flask-Mail
- PDF hóa đơn: xhtml2pdf
- Thanh toán thử nghiệm: PayPal Sandbox REST API

## 3. Cấu trúc thư mục

```text
ProjectManagementOrderFood/
├─ README.md
└─ OrderApp/
   ├─ app/
   │  ├─ __init__.py
   │  ├─ index.py
   │  ├─ models.py
   │  ├─ dao.py
   │  ├─ admin_view.py
   │  ├─ custom_admin.py
   │  ├─ static/
   │  └─ templates/
   ├─ .env
   ├─ .gitignore
   └─ requirement.txt
```

## 4. Chức năng chính

### 4.1. Khách hàng

- Đăng ký, đăng nhập, đăng xuất
- Tìm kiếm món ăn theo:
  - từ khóa
  - danh mục
  - nhà hàng
  - khoảng giá
  - trạng thái còn món
- Xem chi tiết món ăn
- Thêm món vào giỏ hàng
- Tăng/giảm số lượng món trong giỏ
- Thanh toán qua:
  - COD
  - MoMo mô phỏng
  - Chuyển khoản mô phỏng
  - PayPal Sandbox
- Xem danh sách đơn hàng đã đặt
- Xem chi tiết đơn hàng
- Gửi đánh giá món ăn

### 4.2. Nhà hàng

- Xem trang nhà hàng
- Cập nhật thông tin nhà hàng
- Thêm món ăn mới
- Chỉnh sửa món ăn
- Bật/tắt trạng thái bán món ăn
- Xem danh sách đơn hàng của nhà hàng
- Xác nhận đơn hàng
- Hoàn tất đơn hàng
- Xem thống kê doanh thu

### 4.3. Quản trị viên

- Quản lý người dùng
- Quản lý nhà hàng
- Quản lý món ăn
- Quản lý đơn hàng
- Quản lý đánh giá
- Xem thống kê từ trang quản trị

## 5. Mô hình dữ liệu chính

Các entity chính trong project:

- `User`
- `NhaHang`
- `DanhMucMonAn`
- `MonAn`
- `GioHang`
- `ChiTietGioHang`
- `DonHang`
- `ChiTietDonHang`
- `DanhGia`
- `ThongBao`

Một số trường đáng chú ý trong `DonHang`:

- `trangThai`
- `tongGia`
- `paymentMethod`
- `paymentStatus`
- `paypalOrderId`

## 6. Yêu cầu môi trường

- Windows
- Python 3.12
- MySQL
- Kết nối Internet nếu muốn:
  - upload ảnh qua Cloudinary
  - thanh toán thử nghiệm bằng PayPal Sandbox

## 7. Cài đặt project

### Bước 1: Di chuyển vào thư mục ứng dụng

```powershell
cd D:\BTLQLDAPM\ProjectManagementOrderFood\OrderApp
```

### Bước 2: Tạo môi trường ảo

```powershell
C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv
```

### Bước 3: Kích hoạt môi trường ảo

```powershell
.\.venv\Scripts\Activate.ps1
```

Nếu PowerShell chặn script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Bước 4: Cài dependencies

```powershell
pip install -r requirement.txt
```

## 8. Cấu hình cơ sở dữ liệu

Project hiện đang trỏ tới MySQL trong file:

- [app/__init__.py](D:/BTLQLDAPM/ProjectManagementOrderFood/OrderApp/app/__init__.py)

Chuỗi kết nối đang dùng:

```python
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:%s@localhost/fooddb?charset=utf8mb4" % quote('chivy123@')
```

Bạn cần:

1. Đảm bảo MySQL đang chạy
2. Tạo database `fooddb`
3. Sửa lại password nếu máy bạn không dùng `chivy123@`

Tạo database:

```sql
CREATE DATABASE fooddb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 9. Khởi tạo dữ liệu mẫu

Chạy file models theo module:

```powershell
C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe -m app.models
```

Lệnh này sẽ:

- tạo bảng nếu chưa tồn tại
- seed dữ liệu mẫu ban đầu nếu database đang rỗng

## 10. Lưu ý quan trọng về schema

Project hiện **không dùng migration**. `db.create_all()` chỉ tạo bảng mới, **không tự cập nhật bảng cũ** khi model thay đổi.

Nếu bạn đã tạo database từ trước, cần kiểm tra thủ công các cột mới.

### 10.1. Bảng `thong_bao`

Nếu gặp lỗi thiếu `mon_an_id` hoặc `url`, chạy:

```sql
USE fooddb;

ALTER TABLE thong_bao ADD COLUMN mon_an_id INT NULL;
ALTER TABLE thong_bao ADD COLUMN url VARCHAR(255) NULL;
```

Nếu muốn thêm khóa ngoại:

```sql
ALTER TABLE thong_bao
ADD CONSTRAINT fk_thong_bao_mon_an
FOREIGN KEY (mon_an_id) REFERENCES monAn(id);
```

### 10.2. Bảng `donHang`

Nếu gặp lỗi thiếu các cột thanh toán, chạy:

```sql
USE fooddb;

ALTER TABLE donHang
ADD COLUMN paymentMethod VARCHAR(50) DEFAULT 'cod',
ADD COLUMN paymentStatus VARCHAR(50) DEFAULT 'PENDING',
ADD COLUMN paypalOrderId VARCHAR(100) NULL;
```

## 11. Cấu hình PayPal Sandbox

Project đã hỗ trợ đọc biến môi trường từ file:

- [OrderApp/.env](D:/BTLQLDAPM/ProjectManagementOrderFood/OrderApp/.env)

Các biến cần có:

```env
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CURRENCY=USD
PAYPAL_VND_RATE=25000
```

Lưu ý:

- Dùng **PayPal Sandbox**, không dùng tài khoản PayPal thật
- Cần 2 loại tài khoản sandbox:
  - `Business` account: tài khoản người bán
  - `Personal` account: tài khoản người mua để test checkout

## 12. Chạy ứng dụng

Từ thư mục `OrderApp`, chạy:

```powershell
C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe -m app.index
```

Sau đó mở:

```text
http://127.0.0.1:5000
```

## 13. Tài khoản mẫu

Tài khoản được seed trong `models.py`:

- Admin
  - `admin / 123456`

- Nhà hàng
  - `shop1 / 123456`
  - `shop2 / 123456`

- Khách hàng
  - `kh01 / 123456`

## 14. Các route tiêu biểu

### Giao diện người dùng

- `/` - Trang chủ
- `/login` - Đăng nhập
- `/register` - Đăng ký khách hàng
- `/register-nhahang` - Đăng ký nhà hàng
- `/nha-hang` - Danh sách nhà hàng
- `/nha-hang/<id>` - Chi tiết nhà hàng
- `/mon-an/<id>` - Chi tiết món ăn

### Giỏ hàng và thanh toán

- `/gio-hang` - Xem giỏ hàng
- `/gio-hang/them/<id>` - Thêm món vào giỏ
- `/gio-hang/<chi_tiet_id>/tang` - Tăng số lượng món
- `/gio-hang/<chi_tiet_id>/giam` - Giảm số lượng món
- `/gio-hang/thanh-toan/<gio_hang_id>` - Trang thanh toán
- `/thanh-toan/paypal/<gio_hang_id>` - Checkout PayPal Sandbox
- `/api/paypal/orders/<gio_hang_id>` - Tạo PayPal order
- `/api/paypal/orders/<order_id>/capture` - Capture PayPal order

### Đơn hàng

- `/don-hang-cua-toi` - Danh sách đơn của khách hàng
- `/don-hang/<id>` - Chi tiết đơn hàng của khách hàng
- `/nha-hang/don-hang` - Quản lý đơn hàng của nhà hàng
- `/nha-hang/don-hang/<id>` - Chi tiết đơn hàng của nhà hàng
- `/nha-hang/don-hang/<id>/xac-nhan` - Xác nhận đơn
- `/nha-hang/don-hang/<id>/hoan-tat` - Hoàn tất đơn

### Khác

- `/xuat-bill/<id>` - Xuất hóa đơn PDF
- `/admin` - Trang quản trị

## 15. Gợi ý và phân tích đánh giá

Project hiện có các tính năng hỗ trợ mức cơ bản:

- Gợi ý món ăn cho khách hàng dựa trên lịch sử đặt hàng
- Gợi ý món ăn đi kèm
- Phân tích đánh giá món ăn theo từ khóa và số sao

Đây là hướng rule-based, chưa phải mô hình machine learning hoàn chỉnh.

## 16. Điểm mạnh hiện tại

- Luồng nghiệp vụ đặt hàng đã tương đối đầy đủ
- Có phân vai khách hàng / nhà hàng / quản trị viên
- Có giỏ hàng và thanh toán
- Có realtime notification
- Có PDF hóa đơn
- Có trang quản trị dữ liệu

## 17. Hạn chế hiện tại

- Chưa dùng migration để quản lý schema database
- Một số cấu hình nhạy cảm đang đặt trực tiếp trong mã nguồn
- Thanh toán MoMo và chuyển khoản mới ở mức mô phỏng
- `ChiTietDonHang` chưa lưu snapshot giá món tại thời điểm đặt
- Một số chuỗi tiếng Việt trong source đang bị lỗi encoding

## 18. Hướng phát triển tiếp theo

- Tích hợp Flask-Migrate / Alembic
- Tách cấu hình nhạy cảm hoàn toàn sang `.env`
- Lưu đơn giá món tại thời điểm đặt hàng
- Bổ sung hủy đơn từ phía khách hàng
- Bổ sung dashboard thống kê món bán chạy
- Chuẩn hóa encoding UTF-8 cho toàn bộ mã nguồn
- Nâng cấp gợi ý món ăn sang mô hình dữ liệu tốt hơn

## 19. Tác giả

Project được phát triển cho bài tập/đồ án quản lý dự án phần mềm về nền tảng đặt đồ ăn trực tuyến.

