# IT deployment — step by step

This package is the deployable source. No Python or merge logic needs to be written.

## 1. Railway

1. Create one Railway project and one long-running service from the unpacked root.
2. Attach exactly one persistent volume to that service at `/runtime`. Keep one replica.
3. Import variable names from `deployment/railway/.env.railway.example` into Railway Variables and replace placeholders only in the Railway UI.
4. Keep `KIOT_CATALOG_DEPLOYMENT_MODE=railway`, `KIOT_CATALOG_HOST=0.0.0.0`, cadence `3600`, source freshness `10800`, retention `3`, maximum products `1000`, and the initial activation guard `KIOT_CATALOG_SYNC_ENABLED=false`.
5. Set `RAILWAY_RUN_UID=0`: Railway documents that volumes mount as root. Do not store secrets in the repository.
6. Generate two keys privately with `python deployment/railway/generate_api_keys.py --output /absolute/private/new/api_keys.env`, copy them to Railway UI, then protect/delete the local temporary file per company policy. The command prints no key value.
7. Convert the Google service-account JSON to base64 locally without terminal output (on macOS: `base64 < service-account.json | pbcopy`) and paste only into Railway UI as `GOOGLE_SERVICE_ACCOUNT_JSON_B64`.
8. Share the exact Catalog Master Sheet with the service-account email as Viewer. Do not grant Drive-wide access.

## 2. Validate and deploy

Railway uses root `railway.toml`, builds `deployment/railway/Dockerfile`, starts the Python supervisor and checks `/livez`. The volume is unavailable during build/pre-deploy; do not move preflight there.

Activation order is mandatory:

1. Deploy with `KIOT_CATALOG_SYNC_ENABLED=false`. Disabled startup performs zero Kiot sync and zero Google Sheet build/read; it may serve only an existing LKG that still passes both generated and source-cutoff freshness.
2. Check `/livez`, then run the offline preflight below. Do not interpret `/livez` as data readiness.
3. Obtain Owner approval for read-only activation.
4. Run the manual Kiot preflight/sync and Google Sheet website build commands below.
5. Compare item count and at least three Owner-selected SKUs.
6. Only after every check passes, set `KIOT_CATALOG_SYNC_ENABLED=true` and redeploy to start the 3600-second worker.

In a Railway shell:

```bash
python -m integrations.kiot_public_catalog.railway_runtime --preflight-only
python -m integrations.kiot_public_catalog preflight
python -m integrations.kiot_public_catalog sync
python -m integrations.kiot_public_catalog.railway_runtime --build-once
python -m integrations.kiot_public_catalog service-status
```

The first command is offline and prints no secret. The next three are explicitly read-only network operations for activation: OAuth token issuance, KiotViet business GETs and one Google Sheets values GET. They must only run after Owner authorization. `--build-once` preserves the source `data_as_of`; it cannot refresh or extend the Kiot freshness window. The always-on worker starts only after the explicit `sync=true` redeploy.

Expected endpoints:

- `GET /livez` -> 200 `alive` even before data exists.
- `GET /health` -> 200 only with usable coherent Kiot cache; otherwise 503.
- `GET /v1/website/catalog` -> 200 only when both LKG `generated_at` and Kiot `source_data_as_of` pass their configured ages; otherwise 503.
- Protected source/internal endpoints still require server-side keys.

## 3. Netlify

Follow `deployment/netlify_dropin/NETLIFY_INSTALL_10_MINUTES.md`. Backup and read existing `_redirects`/`netlify.toml`; merge only the exact catalog rule before any SPA catch-all. Never overwrite routing files or add `/api/*`. Deploy Preview before promotion.

## 4. Stop and rollback

- Sync-only kill switch: set `KIOT_CATALOG_SYNC_ENABLED=false` and redeploy, or create `/runtime/data/SYNC_DISABLED`; API continues serving a still-fresh LKG.
- Full kill switch: stop the Railway service and roll Netlify back/removes the exact rewrite/drop-in.
- Railway rollback redeploys a prior release if still retained by the selected plan. Never wipe/delete the volume during rollback.
- Railway sends SIGTERM during deployment; `drainingSeconds=30` lets the supervisor stop HTTP/worker cleanly. The service spawns no child process, so there is no orphan child to reap.
- The supported volume topology is exactly one Railway service instance/replica. A redeploy may cause a short availability gap; the same-origin client must keep its degraded state rather than inventing empty data.

Official references: Railway config/health/volumes/deployments (`docs.railway.com`), Netlify rewrite/proxy (`docs.netlify.com/manage/routing/redirects/rewrites-proxies/`), and Google Sheets `spreadsheets.values.get` plus read-only scope (`developers.google.com/workspace/sheets/api/`).
