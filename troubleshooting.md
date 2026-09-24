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



## Entry 1 / 2026-09-21 00:25 EEST / app-01 and app-02 unhealthy

- Symptom:
I started the stack with `docker compose -p barq-assessment up --build -d`. The build worked, but app-01 and app-02 showed `unhealthy`. postgres and redis were `healthy`.

- Hypothesis:
The healthcheck calls a URL that the app does not have.

- Command or test:
`docker compose -p barq-assessment ps -a`
`docker logs app-01`
Then I compared the healthcheck in docker-compose.yml with the routes in app/server.py.

- Actual output:
```
app-01   Up 2 minutes (unhealthy)
app-02   Up 2 minutes (unhealthy)

127.0.0.1 - - [20/Sep/2026 21:25:12] "GET /healthz HTTP/1.1" 404 -
127.0.0.1 - - [20/Sep/2026 21:25:17] "GET /healthz HTTP/1.1" 404 -
127.0.0.1 - - [20/Sep/2026 21:25:22] "GET /healthz HTTP/1.1" 404 -
```
(log times are UTC). server.py only has the route `/health`.

- Failed attempt and what changed your thinking:
None for this issue.

- Root cause:
The healthcheck asks for `/healthz`, but the app route is `/health`. The 404 repeats every 5 seconds, same as the healthcheck interval.

- Fix:
Changed `/healthz` to `/health` in the healthcheck in docker-compose.yml.

- Retest evidence:
Retested after the change, before committing. The fix commit is dated 2026-09-21 06:39 EEST. I did not write down the exact retest time.
```
$ docker compose -p barq-assessment up -d
$ docker inspect --format '{{.Name}} {{.State.Health.Status}}' app-01 app-02
/app-01 healthy
/app-02 healthy
```

- Related commit:
e02618b

- Remaining uncertainty:
`healthy` only means the app answers inside its own container. `curl` through nginx still fails, so that is the next issue.

##########################################################################
##########################################################################

## Entry 2 / Mon Sep 21 01:44:57 PM EEST 2026 / port 8080 does not reach nginx

- Symptom:
After Entry 1, both apps were `healthy`, but `curl` to port 8080 still failed. With `-sS` it showed `curl: (52) Empty reply from server`. The nginx log had only startup lines and no requests.

- Hypothesis:
The compose file publishes host port 8080 to container port 81, but nginx listens on port 80.

- Command or test:
`curl -sS -i --max-time 5 http://127.0.0.1:8080/health`
`docker exec nginx nginx -T | grep -n listen`
`docker exec nginx wget -S -O- -T 3 http://127.0.0.1:80/health`
`docker exec nginx wget -S -O- -T 3 http://127.0.0.1:81/health`

- Actual output:
```
$ curl -sS -i --max-time 5 http://127.0.0.1:8080/health
curl: (52) Empty reply from server

nginx   ...   80/tcp, 127.0.0.1:8080->81/tcp

$ docker exec nginx nginx -T | grep -n listen
17:        listen 80;

$ docker exec nginx wget -S -O- -T 3 http://127.0.0.1:80/health
  HTTP/1.1 502 Bad Gateway

$ docker exec nginx wget -S -O- -T 3 http://127.0.0.1:81/health
wget: can't connect to remote host (127.0.0.1): Connection refused
```

- Failed attempt and what changed your thinking:
My first `curl` used `-s`, so it printed nothing and I could not see the error. I ran it again with `-sS` and got `Empty reply from server`.

- Root cause:
Compose sends host port 8080 to container port 81, but nothing listens on 81 inside nginx (connection refused). nginx listens on 80 and answers there.

- Fix:
In docker-compose.yml, in the ports line of nginx, I changed the container port from 81 to 80 (`${PUBLIC_PORT:-8080}:80`). The fix commit was made on 2026-09-21 at about 14:49 EEST.

- Retest evidence:
Ran `docker compose -p barq-assessment up -d`, then `ps` and `curl`. The time is from the Date header of the curl response (12:13:11 GMT = 15:13:11 EEST).
```
nginx   ...   Up 54 seconds   127.0.0.1:8080->80/tcp

$ curl -sS -i --max-time 5 http://127.0.0.1:8080/health
HTTP/1.1 502 Bad Gateway
Server: nginx/1.28.3
Date: Mon, 21 Sep 2026 12:13:11 GMT
```
nginx now answers on 8080 (before: `Empty reply from server`). It returns 502, which is a different problem.

- Related commit:
7c314a3
##########################################################################
##########################################################################
## Entry 3 / 2026-09-23 09:58 EEST / apps unreachable from other containers (502)
Note: work paused after Entry 2 (network/VM issues), resumed on 2026-09-23.
- Symptom:
After fixing the port mapping (Entry 2), nginx answered on 8080 but returned 502. Both apps were `healthy`.

- Hypothesis:
The apps only accept connections from inside their own container (APP_HOST is 127.0.0.1), so nginx cannot reach them even though the healthcheck (which runs inside the container) succeeds.

- Command or test:
`docker logs nginx`
`docker exec nginx wget -S -O- -T 3 http://app-02:8080/health`
`docker inspect app-02 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^APP_(HOST|PORT)='`

- Actual output:
```
$ docker logs nginx (excerpt)
connect() failed (111: Connection refused) while connecting to upstream,
upstream: "http://172.19.0.2:8080/health"

$ docker exec nginx wget -S -O- -T 3 http://app-02:8080/health
wget: can't connect to remote host (172.19.0.2): Connection refused

APP_HOST=127.0.0.1
APP_PORT=8080
```

- Failed attempt and what changed your thinking:
I first tested by running the health check from inside app-02 itself (container calling its own loopback address). It returned 200, but that was misleading — a container can always reach its own loopback, so this did not prove nginx could reach it. The real test had to come from a different container (nginx).

- Root cause:
APP_HOST was set to 127.0.0.1 in docker-compose.yml, so Flask only accepted connections from inside its own container. nginx, calling from a different container, was refused.

- Fix:
Changed APP_HOST to 0.0.0.0 in docker-compose.yml (applies to both app-01 and app-02).

- Retest evidence:
`docker exec nginx wget http://app-02:8080/health` -> `200 OK` (was: connection refused).

- Related commit:
bd61938
- Remaining uncertainty:
After this fix, app-02 answered but its X-Instance-ID header said "app-01" — a separate identity bug. Also app-01 still failed (different cause: wrong upstream port), tracked in Entry 4.
##########################################################################
##########################################################################
## Entry 4 / 2026-09-23 / wrong upstream port and duplicate INSTANCE_ID

- Symptom:
After Entry 3, app-02 answered through nginx, but its X-Instance-ID header said "app-01". app-01 still failed with a refused connection.

- Hypothesis:
(1) nginx upstream for app-01 uses the wrong port (8081 instead of 8080).
(2) app-02's INSTANCE_ID in docker-compose.yml is a copy-paste duplicate of app-01's.

- Command or test:
`docker exec nginx wget -S -O- -T 3 http://app-01:8081/health`
Read nginx/nginx.conf upstream block and the app-02 environment in docker-compose.yml.

- Actual output:
```
$ docker exec nginx wget -S -O- -T 3 http://app-01:8081/health
Connecting to app-01:8081 (172.19.0.2:8081)
wget: can't connect to remote host (172.19.0.2): Connection refused

nginx.conf: server app-01:8081 max_fails=0;
docker-compose.yml (app-02): INSTANCE_ID: "app-01"
```

- Failed attempt and what changed your thinking:
None for this issue.

- Root cause:
nginx.conf pointed to app-01 on port 8081, but the app listens on 8080. Separately, app-02's INSTANCE_ID was copied from app-01 instead of being set to "app-02".

- Fix:
Changed the upstream port for app-01 from 8081 to 8080 in nginx/nginx.conf.
Changed INSTANCE_ID for app-02 from "app-01" to "app-02" in docker-compose.yml.

- Retest evidence:
After `docker compose up -d` and `docker compose restart nginx` (nginx needed a restart to reload the mounted config file, `up -d` alone did not reload it):
```
$ for i in 1 2 3 4 5 6; do curl -s http://127.0.0.1:8080/instance; echo; done
instance_id alternates between "app-01" and "app-02" across requests
$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/health
200
```

- Related commit:
a395982

- Remaining uncertainty:
None for this issue. Both apps now respond with distinct identities through nginx.
##########################################################################
##########################################################################
## Entry 5 / 2026-09-23 / /ready returns unavailable for postgres and redis
- Symptom: /ready returned postgres and redis both "unavailable".
- Cause: config/app.env had wrong ports (DATABASE_URL:5433 vs actual 5432, REDIS_URL:6380 vs actual 6379) and a mismatched postgres password (last char d vs c in compose).
- Evidence: postgres log showed "password authentication failed for user barq_app"; app log showed dependency_error postgres.
- Fix: corrected ports and password in config/app.env.
- Retest: /ready now returns "ready" for both. POST/GET /records and /counter work end to end.
- Related commit: e168f9e
##########################################################################
##########################################################################
## Entry 6 / 2026-09-23 / postgres data lost on container recreation (volume misconfigured)
- Symptom: postgres volume was mounted on /var/lib/postgresql/backup (wrong path) while /var/lib/postgresql/data (the real data dir) had tmpfs on top, so writes never persisted to the named volume.
- Also found: nginx was attached to the backend network, giving it direct access to postgres/redis (violates task requirement to block this).
- Fix: mounted postgres-data volume on /var/lib/postgresql/data, removed the tmpfs line; removed nginx from the backend network (frontend only).
- Retest: created a record (id 3), force-recreated app-01/app-02/postgres containers, GET /records still shows id 3. nginx cannot resolve "postgres" (bad address) confirming network isolation.
- Related commit: baeb073
##########################################################################
##########################################################################
## Entry 7 / 2026-09-23 / Dockerfile ran as root, no restart policy or resource limits
- Symptom: Dockerfile ended with USER root (app image ran as root despite a non-root user being created). No restart policy (restart: "no") and no memory/CPU limits on any service. An unused COPY config/app.env line copied secrets into the image layer.
- Cause: leftover from the starter; USER app was never applied, restart was disabled, limits were never set.
- Fix: changed USER root to USER app in Dockerfile, removed the COPY config/app.env line. Set restart: unless-stopped and mem_limit/cpus on every service in docker-compose.yml.
- Retest: `docker exec app-01 whoami` returns "app" (not root). All containers healthy after rebuild.
- Related commit: 8194fdb
