# API reference — Railway/Netlify handoff

All routes are GET-only. POST/PUT/PATCH/DELETE/OPTIONS/HEAD return 405.

## Public process and website routes

- `GET /livez`: no key; 200 `{"status":"alive"}` when the process is accepting HTTP. Query parameters return 400.
- `GET /v1/website/catalog`: no key; no query parameters. Returns the strict `the_gate_website_catalog.v1` payload, `Content-Type: application/json`, bounded response, `Cache-Control`, and `ETag`. Matching `If-None-Match` returns 304 with no body. Rate limit returns 429. Missing/invalid LKG, over-age `generated_at`, or Kiot `source_data_as_of` older than `KIOT_CATALOG_MAX_CACHE_AGE_SECONDS` returns 503 `website_catalog_unavailable`. Restart/rebuild never replaces the source cutoff with build time.
- `GET /health`: no key; source-cache health only (`ok`, `degraded`, `unavailable`). This is readiness/data health, not Railway liveness.

No wildcard CORS header is emitted. OpenAPI distinguishes local loopback and Railway origins; the browser calls only the separate same-origin Netlify path `/api/catalog`, not Railway directly.

## Protected V2 routes (unchanged)

- `GET /v1/catalog/products?page=1&page_size=50`
- `GET /v1/catalog/products/{code}`
- `GET /v1/internal/products?page=1&page_size=50`
- `GET /v1/internal/products/{code}`

All require `X-API-Key`. The website-backend key can call source catalog routes but not internal. The internal key can call both. Neither belongs in browser code. Maximum page size is 100. Status behavior remains 400/401/403/404/429/503 as described by `openapi.yaml`.

The public website payload intentionally contains no exact inventory, internal generation ID, filesystem path, Sheet note, credential or raw upstream response. See `website_catalog.schema.json` for the machine-readable contract.
