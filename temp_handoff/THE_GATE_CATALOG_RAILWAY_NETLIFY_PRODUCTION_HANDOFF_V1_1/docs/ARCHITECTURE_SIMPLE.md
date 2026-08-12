# Architecture — one Railway service, no Netlify Function

```text
KiotViet read-only -> immutable SQLite generations ----+
                                                       +-> exact-SKU merge -> atomic website_catalog.json LKG
Google Sheets read-only WEBSITE_PRODUCTS --------------+                         |
                                                                                 v
Netlify browser /api/catalog -> exact 200 rewrite -> Railway GET /v1/website/catalog
```

Railway runs one long-lived Python container and mounts one volume at `/runtime`. The same process owns the HTTP server and one non-overlapping worker. Deployment defaults to `KIOT_CATALOG_SYNC_ENABLED=false`; while disabled, startup makes zero Kiot sync and zero Google Sheet build/read calls but may serve an existing still-valid LKG. After manual read-only activation passes, IT enables the worker. It targets 3600 seconds, uses the existing KiotViet lock, then reads the fixed Google range and atomically replaces the website LKG only after full validation. Data, logs and the runtime Kiot secret are separated under `/runtime/data`, `/runtime/logs`, and `/runtime/secrets`.

No Netlify Function is needed: the merged payload is already intentionally public, contains no exact inventory or secret, supports ETag/cache headers, and is reached through one exact same-origin rewrite. A Function would add another runtime and secret boundary without adding authorization value.

`/livez` only proves that the process accepts HTTP and is the Railway deployment healthcheck. `/health` proves source-cache usability and may return 503 on first boot. `/v1/website/catalog` proves website LKG readiness and returns 503 until a valid LKG exists, when `generated_at` is too old, or when the embedded Kiot `source_data_as_of` exceeds 10800 seconds. A rebuild can update `generated_at` but never the Kiot cutoff, so it cannot extend source freshness. A real empty editorial selection is a valid `total: 0`; upstream failure never overwrites LKG with partial/empty data.

The public website endpoint has no API key. Protected `/v1/catalog/*` and `/v1/internal/*` retain V2 API-key rules. Browsers receive neither protected key nor Google/KiotViet credential. CORS wildcard is absent; Netlify supplies same-origin access.

Supported deployment topology is exactly one Railway instance/replica/service with one attached volume. Do not add a separate Cron service or scale horizontally without a new design review. A redeploy may have a short availability gap. Railway volumes mount only at runtime, so directory/secret preflight is part of the start command, not build/pre-deploy.
