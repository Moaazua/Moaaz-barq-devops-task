# Security review

1. **Secrets in plaintext env file**: `config/app.env` and docker-compose.yml contain a synthetic Postgres password in plaintext, committed to a public repo. Risk: acceptable here (lab-only synthetic data per the brief), but in production this must move to a secrets manager (e.g. Docker secrets, Vault, cloud KMS) — never committed, even encrypted.

2. **No TLS**: nginx serves plain HTTP on 8080/8090. Risk: traffic (including any future auth tokens) is unencrypted. Production fix: TLS termination at nginx (or an upstream load balancer) with a real certificate.

3. **Postgres/Redis reachable from the host loopback**: ports 15432/16379 are bound to `127.0.0.1` for developer debugging. Risk: any process on the host (not just Docker) can reach them. Production fix: remove these host-port mappings entirely; use `docker exec` for admin access only.

4. **No authentication on the API**: any client reaching nginx can hit `/records` or `/counter` with no auth. Risk: open write access to the database. Production fix: add an API key or OAuth layer in front of the app.

5. **Single point of failure — nginx**: one nginx container fronts both app instances; if it fails, the whole service is down despite two healthy backends. Production fix: run nginx behind a load balancer or use multiple nginx replicas.

6. **Single point of failure — Postgres**: one Postgres instance, no replication. A crashed container or corrupted volume loses all data until a backup is restored (with a gap since the last backup). Production fix: managed Postgres with replication/PITR, or a documented backup schedule (this project only proved a manual, on-demand backup/restore).

7. **No log rotation/retention**: application and nginx logs go to stdout with no rotation configured at the Docker level. Risk: disk fill-up over time in a long-running host. Production fix: configure Docker's log driver (`max-size`/`max-file`) or ship logs to a centralized system.

8. **No image vulnerability scanning**: base images are pinned by digest (good — reproducible builds) but never scanned for CVEs in this pipeline. Production fix: add a scan step (e.g. `trivy image`) to CI, matching the task's optional "extra credit" item — not implemented here due to time.

9. **Resource limits are estimates, not enforced against real load**: a slow query or memory leak could still degrade the whole host if limits are set too high. Production fix: load-test and tune `mem_limit`/`cpus` before relying on them.

10. **Redis persistence disabled**: `--save "" --appendonly no` means all Redis data (the request counter) is lost on restart — currently accepted since it's non-critical demo data, but should be flagged if Redis is ever used for anything more important than a counter.
