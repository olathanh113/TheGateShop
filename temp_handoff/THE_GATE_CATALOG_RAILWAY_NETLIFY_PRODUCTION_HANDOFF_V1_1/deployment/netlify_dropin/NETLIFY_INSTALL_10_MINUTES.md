# Netlify drop-in — safe merge

Không có Netlify Function và không có secret trong browser. Không ghi đè `_redirects` hoặc `netlify.toml` hiện hữu.

## 1. Backup và đọc cấu hình hiện tại

1. Xác định đúng publish directory của site và mở cả `_redirects` lẫn `netlify.toml` nếu chúng tồn tại.
2. Lưu bản backup/revision của site trước thay đổi. Không copy `_redirects.template` đè lên file hiện hữu.
3. Kiểm tra catch-all SPA, thường là `/* /index.html 200`. Exact catalog rule phải đứng trước catch-all này.
4. Không thêm wildcard `/api/*`, không proxy route internal/source/keyed.

## 2. Merge duy nhất exact rule

Rule sau là thay đổi routing duy nhất được duyệt:

```text
/api/catalog  https://APPROVED_DOMAIN/v1/website/catalog  200!
```

Thay `APPROVED_DOMAIN` bằng Railway domain đã duyệt, không thêm path, query hoặc credential. Có hai cách an toàn:

- Merge thủ công đúng một dòng vào `_redirects`, giữ nguyên mọi dòng khác; hoặc
- Chạy helper đã đóng gói. Helper đọc file hiện hữu, tạo `_redirects.backup.<UTC timestamp>`, bảo toàn rule cũ và chèn catalog rule trước catch-all SPA:

```bash
python3 merge_redirects.py \
  --file /absolute/site/publish/_redirects \
  --railway-origin https://REPLACE_WITH_RAILWAY_DOMAIN
```

Sau merge, dùng diff kiểm tra: chỉ một exact `/api/catalog` rule được thêm/thay; mọi rule cũ còn nguyên. Helper không đọc hoặc sửa `netlify.toml`.

## 3. Assets và Preview

1. Sao chép `assets/thegate-catalog-client.js` và CSS tùy chọn vào thư mục `assets/` của site.
2. Ghép markup/script từ `examples/catalog-section.html`. Không đổi endpoint same-origin `/api/catalog`.
3. Deploy Netlify Preview trước. DevTools chỉ được gọi `/api/catalog`; không gọi Google, KiotViet, Railway internal hoặc `/v1/internal/*`.
4. Response 200 phải có schema `the_gate_website_catalog.v1`; 429/503/timeout phải hiện degraded state, không render list rỗng như thành công.

## 4. Rollback đúng phạm vi catalog

1. Khôi phục `_redirects` từ `_redirects.backup.<timestamp>` hoặc xóa đúng một dòng `/api/catalog ... 200!`; không thay các rule khác.
2. Xóa/revert đúng các file catalog vừa copy: `assets/thegate-catalog-client.js`, CSS catalog nếu mới thêm, và markup catalog đã chèn.
3. Deploy Preview rollback, kiểm rule/site cũ còn hoạt động, rồi mới restore production deploy nếu cần.
4. Không xóa Railway volume; Netlify rollback không sửa Railway.

Demo offline: chạy static file server cục bộ trong thư mục này và mở `demo.html`; fixture hoàn toàn synthetic.
