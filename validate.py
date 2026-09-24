#!/usr/bin/env python3
"""Validate the BARQ assessment environment: endpoints, backends, dependencies,
network isolation and prohibited host ports. Exits 0 on PASS, 1 on FAIL."""
import json
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8080"
TIMEOUT = 3
RETRIES = 5
RETRY_DELAY = 2

results = []

def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((name, ok, detail))
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))
    return ok

def http_get(path, method="GET", body=None):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    def safe_json(raw_bytes):
        try:
            return json.loads(raw_bytes.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"_non_json_body": raw_bytes[:200].decode(errors="replace")}

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, safe_json(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, safe_json(e.read()), dict(e.headers)
    except (urllib.error.URLError, socket.timeout) as e:
        return None, str(e), {}

def wait_for_ready(max_attempts=RETRIES, delay=RETRY_DELAY):
    for attempt in range(1, max_attempts + 1):
        status, body, _ = http_get("/ready")
        if status == 200:
            return True, body
        print(f"  ... /ready attempt {attempt}/{max_attempts}: status={status}")
        time.sleep(delay)
    return False, body if 'body' in dir() else None

def port_is_open_on_all_interfaces(port):
    """Return True if something listens on 0.0.0.0:<port> (i.e. exposed beyond localhost)."""
    try:
        out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if f"0.0.0.0:{port}" in line or f"*:{port}" in line:
            return True
    return False

def main():
    print("=== BARQ assessment validation ===")

    # 1. Public access via nginx
    status, body, _ = http_get("/")
    check("GET / returns 200", status == 200, f"status={status}")

    # 2. /health liveness
    status, body, _ = http_get("/health")
    check("GET /health returns 200", status == 200, f"status={status}")

    # 3. /ready with bounded retries (dependencies may still be starting)
    ok, body = wait_for_ready()
    check("GET /ready returns 200 (postgres+redis)", ok, f"body={body}")
    if isinstance(body, dict):
        deps = body.get("dependencies", {})
        check("postgres dependency ready", deps.get("postgres") == "ready", f"deps={deps}")
        check("redis dependency ready", deps.get("redis") == "ready", f"deps={deps}")

    # 4. Both backends respond distinctly through nginx
    instance_ids = set()
    for _ in range(8):
        status, body, headers = http_get("/instance")
        if status == 200 and isinstance(body, dict):
            instance_ids.add(body.get("instance_id"))
    check("both backends visible via /instance", len(instance_ids) >= 2,
          f"seen instance_ids={instance_ids}")

    # 5. /records POST and GET (real Postgres write/read)
    status, body, _ = http_get("/records", method="POST", body={"title": "validate.py check"})
    check("POST /records returns 201", status == 201, f"status={status} body={body}")
    status, body, _ = http_get("/records")
    check("GET /records returns 200 with a list", status == 200 and "records" in (body or {}),
          f"status={status}")

    # 6. /counter increments (real Redis operation)
    status, body1, _ = http_get("/counter")
    status2, body2, _ = http_get("/counter")
    c1 = body1.get("counter") if isinstance(body1, dict) else None
    c2 = body2.get("counter") if isinstance(body2, dict) else None
    check("GET /counter increments", (c1 is not None and c2 is not None and c2 > c1),
          f"counter: {c1} -> {c2}")

    # 7. Unknown route returns 404
    status, body, _ = http_get("/this-route-does-not-exist")
    check("unknown route returns 404", status == 404, f"status={status}")

    # 8. Invalid record title returns 400
    status, body, _ = http_get("/records", method="POST", body={"title": ""})
    check("empty title returns 400", status == 400, f"status={status} body={body}")

    # 9. Prohibited host ports: postgres and redis must not be reachable on 0.0.0.0
    for name, port in [("postgres", 5432), ("redis", 6379)]:
        exposed = port_is_open_on_all_interfaces(port)
        if exposed is None:
            print(f"[SKIP] {name} port {port} exposure check (ss not available)")
        else:
            check(f"{name} port {port} not published on 0.0.0.0", not exposed,
                  f"0.0.0.0:{port} listening={exposed}")

    print("=== Summary ===")
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed
    print(f"{passed}/{total} checks passed, {failed} failed")

    if failed > 0:
        print("VALIDATION FAILED")
        sys.exit(1)
    print("VALIDATION PASSED")
    sys.exit(0)

if __name__ == "__main__":
    main()
