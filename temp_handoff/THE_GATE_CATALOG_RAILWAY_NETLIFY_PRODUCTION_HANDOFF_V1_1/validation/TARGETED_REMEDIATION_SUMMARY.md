# V1.1 targeted remediation

## 1. Source freshness

- `WebsiteCatalogStore` now measures both `generated_at` and `source_data_as_of`.
- The source cutoff uses `KIOT_CATALOG_MAX_CACHE_AGE_SECONDS`, independently of the website-build age.
- Exact 10,800-second source age is usable; 10,801 seconds fails closed.
- Fresh build time cannot mask a 21,480-second-old source cutoff.
- Rebuild/restart preserves the Kiot cutoff and cannot extend freshness.
- Failed build continues to preserve byte-identical LKG.

## 2. Activation guard

- Railway example and missing-value default are `sync=false`.
- Disabled startup makes zero sync and zero Google-backed build/read calls.
- API may serve only an existing LKG that passes real generated/source ages.
- Go-live docs require manual read-only activation and validation before `sync=true`.

## 3. Netlify safe merge

- Existing `_redirects` and `netlify.toml` must be read/backed up, never overwritten.
- The helper backs up and atomically merges only `/api/catalog` before SPA catch-all.
- Fixture proves existing redirects remain byte-for-byte represented around the inserted rule.
- No `/api/*` wildcard is created. Rollback restores only catalog routing/assets.

## 4. Metadata/operations note

- OpenAPI distinguishes local loopback, Railway origin template and Netlify same-origin path.
- Checklist states one instance/replica for the volume topology and possible short redeploy downtime.

No TTL, publication rule, auth rule, retention/coherence fence or existing assertion was weakened.
