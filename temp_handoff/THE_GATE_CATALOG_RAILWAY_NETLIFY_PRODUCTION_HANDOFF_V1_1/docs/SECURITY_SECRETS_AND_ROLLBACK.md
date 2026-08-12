# Security, secrets and rollback

Railway-only secrets: `KV_RETAILER`, `KV_CLIENT_ID`, `KV_CLIENT_SECRET`, `GOOGLE_SERVICE_ACCOUNT_JSON_B64`, `KIOT_CATALOG_WEBSITE_API_KEY`, and `KIOT_CATALOG_INTERNAL_API_KEY`. The first three become `/runtime/secrets/kiot.env` mode 0600 at start; Google JSON is decoded in memory. Values are never logged. API keys protect legacy source/internal APIs and are never required by `/v1/website/catalog` or browser JavaScript.

The Google credential uses only `spreadsheets.readonly`. The adapter hard-codes one spreadsheet ID and `WEBSITE_PRODUCTS!A1:U1002`, issues GET only, rejects redirects and retries only 429/5xx/network failures within configured bounds. Owner narrows effective file access by sharing only the target Sheet as Viewer.

Runtime directories are absolute and separate: `/runtime/data`, `/runtime/logs`, `/runtime/secrets`, mode 0700. Runtime files are mode 0600. Docker context excludes `.env`, service-account files, keys, databases, logs, evidence, Git, bytecode and archives. Logs contain stable error codes/counts only—not payloads, URLs with auth, product rows or credentials.

The public payload excludes inventory, generation IDs, filesystem paths, notes, credentials and raw upstream responses. CORS wildcard is absent. Netlify provides HTTPS/same-origin proxying; TLS termination is not implemented in Python.

Rollback never deletes the volume. Netlify rollback restores the prior deploy. Railway rollback reuses a retained prior source release where the platform/plan offers it; confirm availability in the UI rather than assuming. The immutable generations and website LKG remain on `/runtime`. Use `KIOT_CATALOG_SYNC_ENABLED=false` or `/runtime/data/SYNC_DISABLED` to stop sync while serving a still-fresh LKG; stop the Railway service for a full kill switch.
