# Adversarial self-audit V1.1

- A new `generated_at` cannot make an old Kiot cutoff fresh; public website endpoint returns 503 on either expired clock.
- Disabled startup logs only the disabled worker state and serves no missing data as success. Docker evidence shows zero sync/build and uninitialized 503.
- Manual `--build-once` retains source cutoff. The worker is enabled only after Owner-authorized manual sync/build and three-SKU comparison.
- Netlify helper rejects non-HTTPS/path/query/credential origins, symlink/non-absolute targets, replaces only an existing exact catalog rule, preserves unrelated rules and inserts before SPA catch-all.
- No wildcard proxy, internal route, API key or upstream credential enters browser assets.
- One Railway instance/replica is the supported persistent-volume topology; rollback never deletes `/runtime`.
- Source, staging, Docker image and package contain no live DB/log/raw response/credential. No live upstream was contacted.

External production deployment and real credentials/upstream remain intentionally unverified.
