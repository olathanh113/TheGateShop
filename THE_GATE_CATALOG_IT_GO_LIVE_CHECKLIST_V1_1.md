# THE GATE CATALOG — IT GO-LIVE CHECKLIST V1.1

1. **Railway service + volume.** Tạo một service, đúng một instance/replica, mount volume `/runtime`. Redeploy có thể có downtime ngắn. **Expected:** volume gắn đúng single instance. **STOP/ROLLBACK:** mount/replica sai hoặc service khác dùng chung.
2. **Secrets qua Railway UI.** Nhập toàn bộ biến từ `.env.railway.example`, giữ `KIOT_CATALOG_SYNC_ENABLED=false`; API keys khác nhau. **Expected:** offline preflight PASS. **STOP:** không dán secret vào chat, Git, Netlify hoặc HTML.
3. **Google Viewer.** Share đúng Sheet `1kWGZy7Stnrs842lnt36Y_3ROO-t_pfNvRcz-cVwU1Eg` cho service-account email ở Viewer. **Expected:** chỉ đọc `WEBSITE_PRODUCTS`. **STOP:** sai file hoặc quyền Editor.
4. **Deploy disabled.** Deploy, kiểm `/livez`, chạy `--preflight-only`. **Expected:** `/livez` 200; 0 Kiot sync và 0 Sheet build/read. Catalog chưa có LKG hoặc source quá tuổi phải 503. **ROLLBACK:** release trước, không xóa volume.
5. **Owner duyệt activation read-only.** Sau duyệt, chạy Kiot preflight, initial sync và `--build-once`. **Expected:** business methods GET only; LKG tạo atomically; `source_data_as_of` không bị đổi thành build time. **STOP:** drift/write/partial/Google error.
6. **Đối chiếu dữ liệu trước worker.** Kiểm `/health`, `service-status`, item count và ít nhất ba SKU Owner chọn. **Expected:** đúng SALE price/ảnh/tên/availability, source age ≤10.800 giây, không exact inventory. **STOP:** mismatch/stale/503/count chưa xác minh.
7. **Bật worker sau PASS.** Đặt `KIOT_CATALOG_SYNC_ENABLED=true` rồi redeploy. **Expected:** cadence 3.600 giây, một worker, timestamp thành công tiến triển. **ROLLBACK:** đặt false/redeploy hoặc dùng kill switch; giữ volume.
8. **Netlify safe merge.** Backup và đọc `_redirects`/`netlify.toml`; merge duy nhất `/api/catalog https://APPROVED_DOMAIN/v1/website/catalog 200!` trước SPA catch-all. **Expected:** rule cũ giữ nguyên; không `/api/*`. **STOP:** không ghi đè routing file.
9. **Assets + Deploy Preview.** Copy JS/CSS/markup catalog, deploy Preview, kiểm DevTools chỉ gọi same-origin `/api/catalog`. **Expected:** không secret/internal route, lỗi thành degraded state. **ROLLBACK:** restore `_redirects` backup và bỏ riêng catalog assets/markup.
10. **Promote.** Chỉ promote khi 1–9 PASS. **Expected:** catalog hợp lệ, ETag/304 hoạt động. **ROLLBACK:** restore Netlify deploy và Railway release trước; tuyệt đối không xóa `/runtime`.

Trạng thái artifact: local/offline verified; production chưa deploy; live credential/upstream chưa kiểm.
