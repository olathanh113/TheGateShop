# The Gate KiotViet Read-Only Catalog API

Read-only catalog service that publishes a deliberately small contract from a clean SQLite cache. Local mode remains loopback-only. The packaged Railway mode is explicit, uses one long-running container plus one persistent `/runtime` volume, and never proxies caller parameters to KiotViet or Google Sheets.

## Verified Python runtime

This candidate was replayed on CPython `3.14.5` only. Other Python minor versions are unverified in the current evidence and are not claimed as supported by this handoff.

## Data flow and hard boundary

```text
KiotViet GET-only business API
  -> manual guarded sync
  -> immutable allowlisted SQLite generation (0600)
  -> atomic authoritative status pointer
  -> exact public catalog API + protected source/internal APIs
  -> exact Netlify same-origin rewrite /api/catalog
  -> static website browser

Google Sheets GET-only WEBSITE_PRODUCTS
  -> exact-SKU editorial merge
  -> atomic website_catalog.json last-known-good
```

The only non-GET request allowed by the transport is OAuth issuance at the exact URL `POST https://id.kiotviet.vn/connect/token`. Redirects are disabled. The token stays in process memory and is never logged or written to disk. Business calls are restricted to `GET /branches`, `GET /pricebooks`, `GET /pricebooks/{id}`, and `GET /products`.

The sync always resolves the exact active pricebook name `SALE` from the live API. The currently approved ID is `18892`; a changed ID fails with `PRICEBOOK_ID_DRIFT`. The three approved branches are also resolved live and compared with the Owner-approved ID/name contract on every run.

`BranchIds` is sent on every inventory-bearing product request. A response containing another branch ID aborts the entire run. Raw KiotViet responses are held only long enough to transform each page and are never persisted.

## Cache contract

The SQLite cache stores only:

- product/variant code and name;
- normalized `color` and `size` from KiotViet standard attributes;
- source image URLs;
- price from the exact `SALE` pricebook, or `price_status: unavailable` with no fallback;
- KiotViet product activity as the normalized internal field `active_status` (`active`, `inactive`, or `unknown`);
- availability and exact inventory for only the three approved branches;
- a non-public generation ID, product modification time, cache cutoff and stale flag.

Color and size are never inferred from the product name. Missing standard attributes remain `null`. Missing images remain `[]`. Missing branch inventory remains `null`/`unavailable`; it is not silently changed to zero. A failed source sync preserves the prior valid generation and marks its status stale.

## Generation coherence and commit protocol

Each successful snapshot receives a unique 32-character generation ID. The sync writes and fsyncs a new immutable `catalog.<generation>.sqlite3` file first. That file is not visible to readers until an atomically replaced status v2 pointer publishes the same generation ID, cutoff, cache schema version and record count. The status rename is the single commit point.

`CacheReader` derives the database filename from the validated status generation. Before serving it verifies SQLite integrity and requires exact agreement across status, database metadata, actual row count, denormalized record generation/cutoff columns and every JSON payload generation/cutoff. It never replaces a record cutoff while reading. Any missing file or generation, cutoff, schema, count or record mismatch fails closed; catalog/internal and health return `503`.

Faults before the status commit leave the old status pointing to the old immutable database; the uncommitted generation is removed. A fault after the status commit leaves the new coherent generation authoritative.

The sync lock serializes both successful commits and source-failure status writes. A source or contract failure is marked while that same lock is still held, so an older run cannot overwrite a newer authoritative pointer. `SYNC_LOCK_BUSY` means another sync owns the critical section: the run is skipped and may emit only the sanitized event `sync_skipped code=SYNC_LOCK_BUSY`. It does not write cache or status, change `stale`, `last_attempt_at`, `last_error_code`, generation/cutoff, or create an uninitialized status file.

## Generation retention

`KIOT_CATALOG_RETAIN_GENERATIONS` is mandatory for sync and cleanup. The Owner-approved target is `3`; values must be integers from `2` through the hard safety ceiling `10`. Missing, blank, non-integer or out-of-range values fail closed before lock acquisition, source sync or cleanup.

After a new immutable database and authoritative status have committed successfully, retention runs while the same `SyncLock` remains held. It always protects the authoritative generation plus the two newest valid predecessors. Ordering comes from validated, timezone-aware database `data_as_of` metadata—not filename order or mtime. A candidate must be a direct regular non-symlink file in the canonical cache directory, match `catalog.<32 lowercase hex>.sqlite3`, and pass module schema, generation, cutoff, record-count and record-coherence checks before individual unlink and directory fsync.

Unknown files, symlinks, malformed databases, ambiguous/tied cutoffs and candidates newer than the authoritative cutoff are preserved with sanitized warnings. Cleanup never uses recursive deletion or globs. A cleanup failure after commit does not roll back the pointer or mark catalog data stale; sync returns `RETENTION_CLEANUP_FAILED`, and the next successful sync retries cleanup.

## Freshness guard

`KIOT_CATALOG_MAX_CACHE_AGE_SECONDS` is mandatory for API serving, audit and publication-funnel reads. Missing, blank, non-numeric, non-finite, zero or negative values fail closed. The Owner-approved production target is:

```text
KIOT_CATALOG_MAX_CACHE_AGE_SECONDS=10800
```

Age is calculated only from the successful snapshot `data_as_of`, never `last_attempt_at`. A timezone-aware cutoff is required. Any future cutoff is rejected. A cache is usable when `age <= 10800`; the exact boundary is therefore usable. When `age > 10800`, catalog/internal and health return `503`/`unavailable`, even if status says `stale: false`. The merged website LKG independently validates both its own `generated_at` and the embedded Kiot `source_data_as_of`; the latter uses this same `KIOT_CATALOG_MAX_CACHE_AGE_SECONDS=10800` limit. Rebuild/restart cannot extend source freshness because it never changes `source_data_as_of`.

The Owner-approved target cadence is one sync every `3600` seconds, 24/7. The Railway entrypoint implements this as one non-overlapping worker thread inside the same container as the API; it creates no Railway Cron service, launchd, cron, n8n or external scheduler. The packaged Railway environment defaults `KIOT_CATALOG_SYNC_ENABLED=false`: disabled startup performs no Kiot sync and no Google Sheet build/read, while an existing LKG may be served only within its real source freshness. IT enables the worker only after the manual activation sequence passes.

## Publication eligibility

The website catalog is a strict subset selected in the SQLite repository query. It is not filtered by the frontend and the API does not load the full internal snapshot before filtering. A public record must have a unique non-empty code, `price_status: available`, a numeric `sale_price > 0`, and `active_status: active`. Missing, zero, negative, non-numeric and non-finite `SALE` prices are excluded. Inactive and unknown-status products are excluded. There is never a fallback to `basePrice` or any default price.

The internal endpoints retain every valid cached record, including missing `SALE` prices as `sale_price: null` and `price_status: unavailable`. Duplicate product codes abort the atomic sync; the previous snapshot remains available and becomes stale. Missing images do not prevent publication and are counted separately in the publication funnel.

The current implementation uses a full product snapshot because KiotViet's documented `lastModifiedFrom` semantics have not been proven to capture every inventory-only change and pricebook deletion safely. This is a deliberate fail-closed limitation; no scheduler is created in this build.

## Manual commands

The module does not automatically load `.env`. Export configuration in the shell or inject it with an approved service manager. Use absolute private paths outside the source checkout/web root for data, logs and the KiotViet secret file:

```bash
export KIOT_CATALOG_DATA_DIR='/absolute/private/path/to/catalog-data'
export KIOT_CATALOG_LOG_DIR='/absolute/private/path/to/catalog-logs'
export KIOT_CATALOG_SECRETS_PATH='/absolute/private/path/to/kiot_secret.env'
```

Create data/log directories with mode `0700`; create the external secret file with mode `0600`. Its supported format is exactly the three names shown in `kiot_secret.env.example`: `KV_RETAILER`, `KV_CLIENT_ID`, and `KV_CLIENT_SECRET`. Never put the real file in this source checkout, a web root, Git, Sheet, frontend or handoff ZIP.

Before any network preflight, validate the deployment metadata and secret-file structure offline:

```bash
python3 -m integrations.kiot_public_catalog.deployment_check
```

This check performs no network request and prints no credential value. Then run from the repository root:

```bash
KIOT_CATALOG_RETAIN_GENERATIONS=3 \
  python3 -m integrations.kiot_public_catalog preflight
KIOT_CATALOG_RETAIN_GENERATIONS=3 \
  python3 -m integrations.kiot_public_catalog sync
```

Sync requires explicit retention. Audit, publication-funnel and API serving additionally require the approved maximum age:

```bash
KIOT_CATALOG_RETAIN_GENERATIONS=3 \
KIOT_CATALOG_MAX_CACHE_AGE_SECONDS=10800 \
  python3 -m integrations.kiot_public_catalog audit
```

Set two different random keys in the process environment before serving. Do not put either key in public JavaScript:

```bash
export KIOT_CATALOG_WEBSITE_API_KEY='replace-with-random-secret'
export KIOT_CATALOG_INTERNAL_API_KEY='replace-with-another-random-secret'
export KIOT_CATALOG_MAX_CACHE_AGE_SECONDS='10800'
export KIOT_CATALOG_RETAIN_GENERATIONS='3'
python3 -m integrations.kiot_public_catalog serve
```

Default local bind is `127.0.0.1:8787`. `0.0.0.0:$PORT` is accepted only when `KIOT_CATALOG_DEPLOYMENT_MODE=railway`; every other non-loopback combination fails closed. CORS is disabled because no CORS response header is emitted. The static site uses the exact same-origin Netlify rewrite rather than receiving a secret.

## Endpoints

- `GET /health` — generic status only; no path, count, credential or system detail.
- `GET /livez` — liveness only; always independent of catalog readiness.
- `GET /v1/website/catalog` — public, pre-merged website-safe LKG with ETag; no API key.
- `GET /v1/catalog/products?page=1&page_size=50`
- `GET /v1/catalog/products/{code}`
- `GET /v1/internal/products?page=1&page_size=50`
- `GET /v1/internal/products/{code}`

All catalog/internal endpoints require `X-API-Key`. The website key cannot access internal endpoints. The internal key can access both tiers. Catalog responses never contain exact inventory. A public product-detail lookup returns `404` when a code exists only in the internal snapshot. Page size is capped at 100. A process-local rate limiter defaults to 120 requests per minute per client/role and returns `429` after the threshold. `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, and `HEAD` return `405`.

When no successful coherent cache exists, or when the cache is too old, catalog/internal endpoints return `503` rather than an empty dataset. Health returns only `ok`, `degraded`, or `unavailable`.

## Tests

```bash
python3 -m unittest discover -s integrations/kiot_public_catalog/tests -v
```

The Railway/Netlify package contains deployable configuration, but this working tree has not been deployed, exposed, connected to live Google/KiotViet, scheduled externally or given production secrets.
