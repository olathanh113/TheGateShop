THE GATE — BỘ FAVICON WEBSITE

Các file chính:
- favicon.ico: dùng cho hầu hết trình duyệt
- favicon-16x16.png và favicon-32x32.png: favicon PNG
- apple-touch-icon.png: biểu tượng khi lưu website trên iPhone/iPad
- android-chrome-192x192.png và android-chrome-512x512.png: Android/PWA
- site.webmanifest: cấu hình biểu tượng cho web app

Cách cài nhanh:
1. Tải toàn bộ các file lên thư mục gốc của website.
2. Thêm các dòng sau vào phần <head> của website:

<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">

Lưu ý: sau khi thay favicon, trình duyệt có thể còn giữ ảnh cũ trong bộ nhớ đệm.
Hãy tải lại mạnh trang hoặc mở cửa sổ ẩn danh để kiểm tra.
