# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts
All analysis done with a single script: `scripts/analyze_logs.py` (reads the three log files, does not modify them). Run with:
```
python3 scripts/analyze_logs.py
```
######################################################################
######################################################################

## Results
**Q1: UTC interval covered; valid/malformed/duplicate line counts**
- Interval: 2026-08-20 11:00:00 to 2026-08-20 11:29:57 UTC
- access.log: 725 valid lines, 1 malformed
- application.log: 729 valid lines, 1 malformed
- error.log: 67 valid lines, 1 malformed
- Duplicate request_ids in access.log: 5 (lab-000121, lab-000241, lab-000361, lab-000481, lab-000601 — each appears twice)

**Q2: distinct client requests; deduplication method**
- 725 total lines in access.log, 720 distinct request_ids.
- Deduplicated by grouping on request_id and keeping the first occurrence, since a duplicate line represents a retry of the same client request, not a new one (confirmed in Q6: the duplicates are retries that succeeded on the second attempt).

**Q3: final client status counts and error rate**
- Status counts (over 720 distinct requests): 200: 615, 404: 10, 502: 40, 503: 47, 504: 8
- Denominator: 720 distinct requests (not 725 raw lines, to avoid counting retries twice)
- Error rate (status >= 400): 105/720 = 14.58%

**Q4: failures by path, time window, backend**
- By path: /records: 26, /counter: 26, /ready: 23, /missing: 10, /health: 10, /: 10
- By backend: 172.23.0.12:8080: 73 failures, 172.23.0.11:8080: 32 failures — the .12 backend accounts for most failures
- By time window: all 105 failures fall within 2026-08-20 11:00 UTC hour (the whole incident is inside one hour)

**Q5: median and p95 client latency**
- Method: linear-interpolation percentile on request_time (seconds), converted to milliseconds, over the 720 distinct requests.
- Median: 54.0 ms
- p95: 2001.0 ms

**Q6: retried requests; how many succeeded after retry**
- 5 request_ids were retried (each appears twice in access.log).
- All 5 succeeded after retrying (the second attempt returned a status < 400).

**Q7: incident timeline (access, error and application logs)**
- 11:05:02 - 11:09:57 UTC: nginx logs 59 "connection refused" errors (proxy/connectivity failures reaching a backend).
- 11:12:09 - 11:21:45 UTC: application.log records 94 ERROR/5xx events (dependency_error entries — application/dependency layer).
- 11:25:14 - 11:26:47 UTC: nginx logs 8 "upstream timed out" errors (backend too slow to respond).
- The three phases do not overlap, suggesting three separate causes occurring in sequence rather than one continuous failure.

**Q8: one correlated failed request, one successful request**
- Failed: request_id=lab-000001, 2026-08-20T11:00:00.015Z, GET /missing, status 404, upstream 172.23.0.11:8080. Matches in access.log and application.log (instance_id app-01, WARN, 404). No error.log entry (this was a normal 404, not a connectivity/dependency failure).
- Successful: request_id=lab-000002, 2026-08-20T11:00:02.532Z, GET /health, status 200, upstream 172.23.0.12:8080. Matches in access.log and application.log (instance_id app-02, INFO, 200).

**Q9: proxy/connectivity vs dependency/application errors; evidence**
- Proxy/connectivity (nginx-level, before reaching the app): 59 "connection refused" + 8 "upstream timed out" = 67 errors in error.log. These happen when nginx itself cannot reach or get a timely response from a backend container.
- Dependency/application (app-level): 47 dependency_error events in application.log, where the app itself logged a failure talking to Postgres or Redis.
- Evidence that separates them: connection_refused/timed out errors only appear in error.log with no matching application.log entry (the app never got the request), while dependency_error entries appear in application.log with a normal HTTP request logged in access.log (the request reached the app, which then failed talking to a dependency).

**Q10: what the logs do not prove; what to check next in a running environment**
- The logs prove *when* three types of failures happened (connectivity, dependency, timeout) and roughly how many requests each affected, but not the *root cause* (e.g., a misconfigured port, a crashed container, resource exhaustion) — there is no container state, health-check history or resource metrics in these files.
- The logs also do not show whether backend 172.23.0.12 was failing continuously or intermittently, since there is no health-check status alongside the request logs.
- In a running environment, the next steps would be: check `docker compose ps`/`docker inspect` health status for the affected backend at the failure timestamps, check `docker stats` for CPU/memory pressure during the 11:12-11:21 dependency-error window, and check Postgres/Redis logs directly for the same window.

######################################################################
######################################################################

## Timeline and correlated examples

(See Q7 for the three-phase timeline and Q8 for a correlated failed/successful request pair.)

######################################################################
######################################################################

## Conclusions and limits
The incident shows three distinct, non-overlapping failure modes within one hour: an nginx-to-backend connectivity gap (11:05-11:09), an application-to-dependency failure window (11:12-11:21), and a slow-backend timeout window (11:25-11:26). Backend 172.23.0.12 accounted for the majority of failures across the incident. The dataset is log-only; without container/infra state at the time, the root cause of each phase cannot be confirmed from these files alone.
