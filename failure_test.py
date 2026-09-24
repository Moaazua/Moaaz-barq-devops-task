#!/usr/bin/env python3
"""Stop one backend, measure traffic/errors during the outage, restore it,
and verify recovery. Exits 0 on PASS, 1 on FAIL."""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8080"
PROJECT = "barq-assessment"
TARGET_SERVICE = "app-01"
TIMEOUT = 3
REQUESTS_DURING_OUTAGE = 10
REQUEST_DELAY = 0.5
RESTART_WAIT = 8

results = []

def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((name, ok, detail))
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    return ok

def safe_json(raw_bytes):
    try:
        return json.loads(raw_bytes.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"_non_json_body": raw_bytes[:200].decode(errors="replace")}

def http_get(path):
    url = BASE_URL + path
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return resp.status, safe_json(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, safe_json(e.read())
    except Exception as e:
        return None, str(e)

def compose(*args):
    cmd = ["docker", "compose", "-p", PROJECT] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

def probe_instance():
    return http_get("/instance")

def main():
    print(f"=== failure_test: stopping {TARGET_SERVICE} ===")

    # 1. Baseline: confirm both backends respond before the test
    seen_before = set()
    for _ in range(6):
        status, body = probe_instance()
        if status == 200 and isinstance(body, dict):
            seen_before.add(body.get("instance_id"))
    check("baseline: both backends visible before outage", len(seen_before) >= 2,
          f"seen={seen_before}")

    # 2. Stop the target backend
    stop_result = compose("stop", TARGET_SERVICE)
    check(f"{TARGET_SERVICE} stopped", stop_result.returncode == 0, stop_result.stderr.strip())
    time.sleep(2)

    # 3. Send requests during the outage, count status codes
    print(f"--- sending {REQUESTS_DURING_OUTAGE} requests during outage ---")
    status_counts = {}
    surviving_instances = set()
    for i in range(REQUESTS_DURING_OUTAGE):
        status, body = http_get("/instance")
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == 200 and isinstance(body, dict):
            surviving_instances.add(body.get("instance_id"))
        time.sleep(REQUEST_DELAY)
    print(f"status counts during outage: {status_counts}")
    ok_count = status_counts.get(200, 0)
    check("service remained partially available during outage", ok_count > 0,
          f"{ok_count}/{REQUESTS_DURING_OUTAGE} requests succeeded, statuses={status_counts}")
    check("surviving backend served requests during outage",
          surviving_instances == {"app-02"}, f"served by={surviving_instances}")

    # 4. Restore the backend
    start_result = compose("start", TARGET_SERVICE)
    check(f"{TARGET_SERVICE} restarted", start_result.returncode == 0, start_result.stderr.strip())
    print(f"--- waiting {RESTART_WAIT}s for {TARGET_SERVICE} to become healthy ---")
    time.sleep(RESTART_WAIT)

    # 5. Verify recovery: both backends visible again
    seen_after = set()
    for _ in range(8):
        status, body = probe_instance()
        if status == 200 and isinstance(body, dict):
            seen_after.add(body.get("instance_id"))
        time.sleep(0.3)
    check("recovery: both backends visible after restart", len(seen_after) >= 2,
          f"seen={seen_after}")

    print("=== Summary ===")
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"{passed}/{total} checks passed")

    if passed < total:
        print("FAILURE TEST FAILED")
        sys.exit(1)
    print("FAILURE TEST PASSED")
    sys.exit(0)

if __name__ == "__main__":
    main()
