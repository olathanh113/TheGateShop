# THE GATE CATALOG — START HERE

This handoff deploys one Python container on Railway and one static Netlify drop-in. It contains no production secret, live database, product dump or deployed service.

Start with:

1. `docs/ARCHITECTURE_SIMPLE.md` — data and trust boundaries.
2. `docs/IT_DEPLOYMENT_STEP_BY_STEP.md` — exact Railway/Netlify procedure.
3. `docs/GO_LIVE_CHECKLIST_1_PAGE.md` — stop/rollback acceptance.
4. `deployment/railway/.env.railway.example` — variable names/placeholders.
5. `deployment/netlify_dropin/NETLIFY_INSTALL_10_MINUTES.md` — static-site install.

Quick offline acceptance from the unpacked root:

```bash
python3 -m unittest discover -s api/integrations/kiot_public_catalog/tests -v
node deployment/netlify_dropin/tests/catalog-client.test.js
```

Railway uses the root `railway.toml` and `deployment/railway/Dockerfile`. Attach one volume at `/runtime`, keep exactly one replica, enter secrets through Railway UI, and deploy first with `KIOT_CATALOG_SYNC_ENABLED=false`. Netlify needs a safe merge of one exact rewrite plus static assets; do not overwrite existing `_redirects`/`netlify.toml`. No Function is included.

Do not deploy until Owner has approved the Railway target, Sheet Viewer share, secrets and go-live SKUs. Do not expose protected API keys to browser JavaScript.
