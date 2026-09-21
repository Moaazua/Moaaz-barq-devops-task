# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.

## Entry 1 / <date and time of the run> / first start of the untouched starter
- Symptom: after `docker compose -p barq-assessment up --build -d` the build succeeded, but app-01 and app-02 were `unhealthy` and `curl http://127.0.0.1:8080/health` returned nothing. Later, with `-sS`: `curl: (52) Empty reply from server`. nginx logged no request.
- Hypothesis: (H1) healthcheck path /healthz does not exist in the app; (H2) compose publishes host 8080 to container port 81 but nginx listens on 80; (H3) APP_HOST=127.0.0.1 keeps the app unreachable from other containers; (H4) the nginx upstream points to port 8081 while the app uses 8080.
- Command or test: `docker compose ps -a`; `docker logs app-01`; `curl -sS -i http://127.0.0.1:8080/health`; `docker exec nginx nginx -T | grep listen`; `docker exec nginx wget http://app-01:8080/health`.
- Actual output: app-01 log shows `GET /healthz` -> 404 every ~5 s; `nginx -T` shows `listen 80;`; wget from nginx to app-01:8080 -> "Connection refused" (name resolves to 172.19.0.3). Raw output is in evidence/local/ (git-ignored).
- Failed attempt and what changed your thinking: my first curl used `-s`, which hid the error, so the output was empty and I could not tell what failed. I re-ran it with `-sS` and got the empty-reply error.
- Root cause: not proven yet for the connection failure. The 404 in the log proves H1 (see Entry 2).
- Fix: none in this entry (investigation only).
- Retest evidence: n/a
- Related commit: n/a
- Remaining uncertainty: H2, H3 and H4 are supported by the outputs above but not fixed or retested yet.

## Entry 2 / <date and time> / app-01 and app-02 unhealthy
- Symptom: `docker compose ps -a` showed app-01 and app-02 `unhealthy`; postgres and redis were `healthy`.
- Hypothesis: the healthcheck probes a path the app does not have.
- Command or test: `docker logs app-01`; read the healthcheck in docker-compose.yml and the routes in app/server.py.
- Actual output: `GET /healthz` returned 404 every ~5 s from 127.0.0.1, matching the healthcheck interval. server.py only defines /health.
- Failed attempt and what changed your thinking: none for this issue.
- Root cause: the healthcheck requested /healthz, which the app does not define.
- Fix: changed the healthcheck path to /health in docker-compose.yml.
- Retest evidence: after `docker compose -p barq-assessment up -d`, `docker inspect` shows app-01 and app-02 `healthy`.
- Related commit: <hash of the fix commit>
- Remaining uncertainty: healthy only proves the app answers inside its own container. Requests through nginx still fail (empty reply), so that is the next issue.