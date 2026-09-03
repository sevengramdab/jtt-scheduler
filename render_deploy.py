"""One-shot Render deploy for the AUTO_SCHEDULER demo.

Needs exactly one thing: a Render API key (dashboard.render.com -> avatar ->
Account Settings -> API Keys -> Create API Key).

Run:
    set RENDER_API_KEY=<paste>
    ../../.venv/Scripts/python.exe render_deploy.py

It will:
  1. verify the key (lists your existing services)
  2. create web service "jtt-scheduler" from the private GitHub repo
  3. poll the first deploy until it is live (or print the failure)
  4. print the permanent https://*.onrender.com URL and health-check it

Idempotent: if the service already exists it just prints the URL.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

API = "https://api.render.com/v1"
REPO = "https://github.com/sevengramdab/jtt-scheduler"
NAME = "jtt-scheduler"

KEY = os.environ.get("RENDER_API_KEY", "").strip()
if not KEY:
    sys.exit("Set RENDER_API_KEY first (see header comment).")


def call(method, path, body=None):
    req = urllib.request.Request(
        API + path,
        method=method,
        headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json",
                 "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def service_url(svc):
    sd = svc.get("serviceDetails") or {}
    return sd.get("url") or svc.get("url")


# 1. Verify key + find existing service
status, data = call("GET", "/services?limit=50")
if status == 401:
    sys.exit("API key rejected (401). Double-check the paste.")
if status != 200:
    sys.exit(f"Unexpected {status}: {data}")

existing = None
print("Key OK. Existing services:")
for item in data:
    s = item.get("service", {})
    print(f"  - {s.get('name')}  {service_url(s) or ''}")
    if s.get("name") == NAME:
        existing = s

if existing:
    svc_id = existing["id"]
    print(f"\nService '{NAME}' already exists: {service_url(existing)}")
else:
    # 2. Create the service
    body = {
        "type": "web_service",
        "name": NAME,
        "ownerId": "tea-cspa7nrgbbvc73babong",
        "repo": REPO,
        "branch": "main",
        "autoDeploy": "yes",
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt",
                "startCommand": "streamlit run app.py --server.port $PORT "
                                "--server.address 0.0.0.0 --server.headless true",
            },
        },
    }
    status, data = call("POST", "/services", body)
    if status not in (200, 201):
        msg = json.dumps(data)
        print(f"\nCreate failed ({status}): {msg}")
        if "repo" in msg.lower() or "not found" in msg.lower():
            print("\nRender cannot see the private repo. One-time fix:")
            print("  dashboard.render.com -> New + -> Web Service -> Connect a GitHub")
            print("  account -> grant access to 'jtt-scheduler'. Then rerun this script.")
        sys.exit(1)
    svc = data.get("service", data)
    svc_id = svc["id"]
    print(f"\nCreated service {NAME} (id {svc_id}). First deploy is building...")

# 3. Poll the deploy
url = None
for i in range(60):  # up to ~15 min
    time.sleep(15)
    status, deploys = call("GET", f"/services/{svc_id}/deploys?limit=1")
    if status == 200 and deploys:
        d = deploys[0].get("deploy", {})
        dstatus = d.get("status")
        print(f"  deploy {d.get('id','?')[:12]}... status: {dstatus}")
        if dstatus == "live":
            break
        if dstatus in ("build_failed", "canceled", "deactivated"):
            sys.exit(f"Deploy failed: {dstatus}. Check the Render dashboard logs.")
    status, sdata = call("GET", f"/services/{svc_id}")
    if status == 200:
        s = sdata.get("service", sdata)
        url = service_url(s) or url
else:
    sys.exit("Timed out waiting for deploy (15 min). Check the dashboard.")

# 4. Report + health check
if not url:
    url = f"https://{NAME}.onrender.com"
print(f"\nLIVE: {url}")
health = urllib.request.urlopen(url + "/_stcore/health", timeout=60).read().decode()
print(f"health check: {health.strip()}")
print("\nNext: rebuild the APK with this URL as DEFAULT_URL and regenerate the QR.")
