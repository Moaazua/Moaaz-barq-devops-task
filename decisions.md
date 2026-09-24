# Decisions

1. **Non-root container user**: Changed Dockerfile from `USER root` to `USER app` (uid 10001, already defined but unused). Alternative: leave as root (simpler, but violates least-privilege and the task's explicit requirement). Trade-off: none significant; the app never needed root.

2. **Restart policy**: Changed all services from `restart: "no"` to `restart: unless-stopped`. Alternative: `on-failure` (only restarts on non-zero exit, not on manual stop or host reboot). Chose `unless-stopped` so the stack survives VM reboots automatically, matching a real deployment expectation. Trade-off: masks crash-loops slightly (container keeps retrying instead of staying down for inspection); acceptable for this assessment scope.

3. **Resource limits**: Added `mem_limit`/`cpus` per service (app: 256m/0.5, postgres: 256m/0.5, redis/nginx: 128m/0.3) based on the lab's light synthetic load. Alternative: no limits (starter default) risks one runaway container starving the host. Limitation: values are estimates, not load-tested; production would need real traffic profiling.

4. **Postgres persistence path**: Fixed volume to mount on `/var/lib/postgresql/data` (removed a `tmpfs` override and wrong mount path `.../backup`). Alternative considered: bind mount to host directory instead of a named volume — rejected because named volumes are more portable across hosts and don't depend on host filesystem permissions (relevant given the SELinux-enforcing VM used here).

5. **nginx network isolation**: Removed nginx from the `backend` network so only `frontend` remains, blocking any direct path from nginx to postgres/redis. Alternative: keep nginx on both networks but rely on application-level access control — rejected, network-level isolation is stronger and required explicitly by the task.

6. **Backup format**: Used `pg_dump -F custom` + `pg_restore --clean --if-exists` instead of plain-SQL dump. Custom format supports selective restore and is Postgres's recommended format for anything beyond trivial dumps. Trade-off: not human-readable without pg_restore, but plain SQL was not needed here.

7. **CI readiness wait**: Implemented a bounded polling loop (15 attempts x 2s = 30s max) against `/ready` instead of a fixed `sleep`. A fixed sleep either wastes time (too long) or flakes intermittently (too short); bounded polling fails fast and deterministically once the real timeout is reached.

Limitations / assumptions: environment sized for a single developer VM (4GB RAM), not load-tested at scale; app-only unit tests use fakes and do not prove environment health (documented explicitly in APPLICATION.md and mirrored in the CI step name).
