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