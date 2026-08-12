# Troubleshooting by sanitized error code

| Code/status | Meaning | Safe action |
|---|---|---|
| `/livez` non-200 | Process/build/bind problem | Inspect sanitized startup log; verify `PORT`, Railway mode and volume; rollback release. |
| `/health` 503 | Source cache absent, incoherent or older than 10800s | Run offline preflight, then authorized read-only preflight/sync. Never fake an empty cache. |
| `website_catalog_unavailable` | Website LKG absent/invalid/too old | Inspect `service-status`; fix source/Sheet issue and run `--build-once`. Existing file is not cleared. |
| `GOOGLE_SHEET_ID_MISMATCH` | Wrong target ID | Restore the exact approved ID; do not select another Sheet. |
| `SHEET_HEADER_CONTRACT_MISMATCH` | 21 headers changed/order differs | Restore approved header contract; do not guess mapping. |
| `SHEET_PRODUCT_CODE_BLANK` / `SHEET_DUPLICATE_PRODUCT_CODE` | Unsafe editorial key | Owner fixes row; rebuild retains old LKG until resolved. |
| `SHEET_PUBLISH_VALUE_INVALID` | Publish is not exact TRUE/FALSE | Set a real Sheet checkbox/boolean; do not use yes/1/whitespace. |
| `SHEET_HTTP_403` | Service account lacks Viewer access or credential wrong | Verify exact file share and account identity; do not broaden Drive permission. |
| `SHEET_HTTP_429` / `SHEET_HTTP_5xx` | Temporary Google issue | Bounded retry occurs; LKG remains. Wait and retry one build. |
| `PRICEBOOK_ID_DRIFT` / branch drift | Kiot contract changed | STOP; Owner verifies contract. Never select a plausible alternative. |
| `SYNC_LOCK_BUSY` | Another sync holds lock | Safe skip; no status/cache mutation. Do not start parallel workers. |
| `WEBSITE_CATALOG_PRODUCT_LIMIT_EXCEEDED` | More than configured published candidates | Owner reduces selection or separately approves limit change; no truncation. |
| `WEBSITE_CATALOG_DUPLICATE_SLUG` / `SHEET_SLUG_INVALID` | URL identity unsafe | Fix explicit slug; LKG stays unchanged. |
| `WEBSITE_CATALOG_RESPONSE_TOO_LARGE` | Payload exceeds bounded bytes | STOP and review catalog/limit; do not bypass guard. |
| `KIOT_RUNTIME_SECRET_INVALID` / Google secret error | Missing/placeholder/malformed secret | Re-enter in Railway UI; never log or email the value. |
