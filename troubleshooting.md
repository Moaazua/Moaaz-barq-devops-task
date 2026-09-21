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