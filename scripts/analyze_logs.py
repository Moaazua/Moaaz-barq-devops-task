#!/usr/bin/env python3
"""Analyze the three historical logs and answer log_analysis.md questions."""
import json
import re
import statistics
from collections import defaultdict, Counter
from datetime import datetime

LOG_DIR = "logs"

def parse_access():
    valid, malformed = [], 0
    seen_ids = Counter()
    with open(f"{LOG_DIR}/access.log") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rec["_ts"] = datetime.fromisoformat(rec["timestamp"].replace("Z", "")).replace(microsecond=0) if "." not in rec["timestamp"] else datetime.strptime(rec["timestamp"].split(".")[0], "%Y-%m-%dT%H:%M:%S")
                valid.append(rec)
                seen_ids[rec["request_id"]] += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                malformed += 1
    dup_ids = {k: v for k, v in seen_ids.items() if v > 1}
    return valid, malformed, dup_ids

def parse_application():
    valid, malformed = [], 0
    with open(f"{LOG_DIR}/application.log") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rec["_ts"] = datetime.fromisoformat(rec["timestamp"].replace("Z", "")).replace(microsecond=0) if "." not in rec["timestamp"] else datetime.strptime(rec["timestamp"].split(".")[0], "%Y-%m-%dT%H:%M:%S")
                valid.append(rec)
            except (json.JSONDecodeError, KeyError, ValueError):
                malformed += 1
    return valid, malformed

ERROR_RE = re.compile(
    r"^(?P<date>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[error\].*?"
    r"(?P<msg>connect\(\) failed.*?|upstream timed out.*?), "
    r"request_id=(?P<rid>\S+), request: \"(?P<req>[^\"]+)\", upstream: \"(?P<upstream>[^\"]+)\""
)

def parse_error():
    valid, malformed = [], 0
    with open(f"{LOG_DIR}/error.log") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = ERROR_RE.search(line)
            if m:
                d = m.groupdict()
                d["_ts"] = datetime.strptime(d["date"], "%Y/%m/%d %H:%M:%S")
                d["kind"] = "connection_refused" if "connect() failed" in d["msg"] else "upstream_timeout"
                valid.append(d)
            else:
                malformed += 1
    return valid, malformed

def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

def main():
    access, access_bad, dup_ids = parse_access()
    app, app_bad = parse_application()
    err, err_bad = parse_error()

    print("=" * 60)
    print("Q1: coverage and line counts")
    all_ts = [r["_ts"] for r in access] + [r["_ts"] for r in app] + [r["_ts"] for r in err]
    print(f"access.log: valid={len(access)} malformed={access_bad}")
    print(f"application.log: valid={len(app)} malformed={app_bad}")
    print(f"error.log: valid={len(err)} malformed={err_bad}")
    print(f"UTC interval: {min(all_ts)} .. {max(all_ts)}")
    print(f"Duplicate request_ids in access.log: {len(dup_ids)} -> {dict(list(dup_ids.items())[:5])} ...")

    print("=" * 60)
    print("Q2: distinct client requests (dedup by request_id, keep first occurrence)")
    distinct = {}
    for r in access:
        distinct.setdefault(r["request_id"], r)
    print(f"Total access lines: {len(access)}; distinct request_ids: {len(distinct)}")

    print("=" * 60)
    print("Q3: final client status counts and error rate")
    statuses = Counter(r["status"] for r in distinct.values())
    total = len(distinct)
    errors = sum(v for k, v in statuses.items() if k >= 400)
    print(f"Status counts: {dict(sorted(statuses.items()))}")
    print(f"Denominator (distinct requests): {total}")
    print(f"Error rate (status>=400 / total): {errors}/{total} = {errors/total:.4f}")

    print("=" * 60)
    print("Q4: failures by path, time window, backend")
    fails = [r for r in distinct.values() if r["status"] >= 400]
    by_path = Counter(r["path"] for r in fails)
    by_backend = Counter(r["upstream"] for r in fails)
    by_hour = Counter(r["_ts"].strftime("%Y-%m-%d %H:00") for r in fails)
    print(f"By path: {dict(by_path)}")
    print(f"By backend: {dict(by_backend)}")
    print(f"By hour: {dict(sorted(by_hour.items()))}")

    print("=" * 60)
    print("Q5: latency percentiles (request_time, seconds -> ms)")
    times_ms = sorted(r["request_time"] * 1000 for r in distinct.values())
    print(f"n={len(times_ms)} median={statistics.median(times_ms):.1f}ms p95={pct(times_ms, 0.95):.1f}ms")

    print("=" * 60)
    print("Q6: retried requests (same request_id appears >1 time in access.log)")
    retried = {k: v for k, v in seen_ids.items() if v > 1} if (seen_ids := Counter(r["request_id"] for r in access)) else {}
    succeeded_after_retry = 0
    for rid, count in retried.items():
        lines = [r for r in access if r["request_id"] == rid]
        if any(r["status"] < 400 for r in lines):
            succeeded_after_retry += 1
    print(f"Retried request_ids: {len(retried)}; succeeded after retry: {succeeded_after_retry}")

    print("=" * 60)
    print("Q7: incident timeline (first and last error per kind, per source)")
    if err:
        by_kind = defaultdict(list)
        for e in err:
            by_kind[e["kind"]].append(e["_ts"])
        for kind, ts_list in by_kind.items():
            print(f"{kind}: first={min(ts_list)} last={max(ts_list)} count={len(ts_list)}")
    app_errors = [a for a in app if a.get("level") == "ERROR" or a.get("status", 0) >= 500]
    if app_errors:
        print(f"application.log errors/500s: first={min(a['_ts'] for a in app_errors)} "
              f"last={max(a['_ts'] for a in app_errors)} count={len(app_errors)}")

    print("=" * 60)
    print("Q8: one correlated failed request, one successful request")
    failed_ids = set(r["request_id"] for r in fails)
    if failed_ids:
        fid = sorted(failed_ids)[0]
        print(f"FAILED example request_id={fid}")
        print("  access:", [r for r in access if r["request_id"] == fid])
        print("  application:", [r for r in app if r.get("request_id") == fid])
        print("  error:", [r for r in err if r["rid"] == fid])
    ok_ids = [r["request_id"] for r in distinct.values() if r["status"] < 400]
    if ok_ids:
        oid = ok_ids[0]
        print(f"OK example request_id={oid}")
        print("  access:", [r for r in access if r["request_id"] == oid])
        print("  application:", [r for r in app if r.get("request_id") == oid])

    print("=" * 60)
    print("Q9: proxy/connectivity vs dependency/application errors")
    conn_errors = [e for e in err if e["kind"] == "connection_refused"]
    timeout_errors = [e for e in err if e["kind"] == "upstream_timeout"]
    app_dep_errors = [a for a in app if a.get("event") == "dependency_error"]
    print(f"nginx connection_refused (proxy/connectivity): {len(conn_errors)}")
    print(f"nginx upstream_timeout (proxy/connectivity, could also be slow backend): {len(timeout_errors)}")
    print(f"application dependency_error (app/dependency layer): {len(app_dep_errors)}")

if __name__ == "__main__":
    main()
