#!/usr/bin/env python3
"""
Lyrisee -> Vercel production deploy (headless, no Vercel CLI required).

Why curl: this sandbox routes egress through an HTTPS MITM proxy whose CA is
trusted at the system level but NOT by Python's ssl module, so requests/urllib
fail handshake. curl honours HTTPS_PROXY + the system CA, so every HTTP call
shells out to curl (same transport Lyrisee's Director uses for Gemini).

Flow (Vercel REST API):
  1. collect static files (respect .vercelignore: skip backend/, *.md, *.mp4, .git)
  2. sha1 each file -> upload raw bytes to POST /v2/files (x-vercel-digest header)
  3. POST /v13/deployments  target=production, framework=null (pure static)
  4. poll GET /v13/deployments/{id} until READY, print the production URL

Secrets: VERCEL_TOKEN is read from the environment ONLY. Never written to disk,
never logged. Optional VERCEL_TEAM_ID for team-scoped tokens.
"""
import os, sys, json, hashlib, subprocess, tempfile, time, fnmatch

API = "https://api.vercel.com"
ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.environ.get("VERCEL_PROJECT", "lyrisee")
TOKEN = os.environ.get("VERCEL_TOKEN", "").strip()
TEAM = os.environ.get("VERCEL_TEAM_ID", "").strip()

# Files/dirs that must never ship to the static host.
IGNORE_DIRS = {".git", "backend", "node_modules", "__pycache__", ".vercel"}
IGNORE_GLOBS = ["*.md", "*.mp4", "*.zip", "*.pyc", ".DS_Store",
                "deploy_vercel.py", ".gitignore", ".vercelignore"]


def q(url):
    return f"{url}{'&' if '?' in url else '?'}teamId={TEAM}" if TEAM else url


def curl(args, timeout=180):
    r = subprocess.run(["curl", "-sS", "--max-time", str(timeout)] + args,
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def collect():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if any(fnmatch.fnmatch(fn, g) for g in IGNORE_GLOBS):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            out.append((rel, full))
    return sorted(out)


def upload(rel, full):
    data = open(full, "rb").read()
    sha = hashlib.sha1(data).hexdigest()
    size = len(data)
    code, sout, serr = curl([
        "-X", "POST", q(f"{API}/v2/files"),
        "-H", f"Authorization: Bearer {TOKEN}",
        "-H", "Content-Type: application/octet-stream",
        "-H", f"x-vercel-digest: {sha}",
        "--data-binary", f"@{full}",
    ])
    ok = code == 0 and ('"urls"' in sout or sout.strip() in ("", "{}") or '"error"' not in sout)
    print(f"  {'OK ' if ok else 'ERR'} {rel:28s} {size:>9,d} b  sha={sha[:10]}")
    if not ok:
        print("      ->", (sout or serr)[:300])
    return {"file": rel, "sha": sha, "size": size}, ok


def main():
    if not TOKEN:
        sys.exit("VERCEL_TOKEN not set in environment. Aborting (no token, no deploy).")

    print(f"[1/4] Verifying token ...")
    code, sout, _ = curl(["-H", f"Authorization: Bearer {TOKEN}", q(f"{API}/v2/user")])
    if code != 0 or '"error"' in sout:
        sys.exit(f"Token check failed: {sout[:300]}")
    try:
        who = json.loads(sout).get("user", {}).get("username") or json.loads(sout).get("user", {}).get("email")
        print(f"      authenticated as: {who}")
    except Exception:
        pass

    print("[2/4] Uploading static files ...")
    files = collect()
    manifest, all_ok = [], True
    for rel, full in files:
        meta, ok = upload(rel, full)
        manifest.append(meta)
        all_ok = all_ok and ok
    if not all_ok:
        sys.exit("One or more uploads failed; not creating deployment.")

    print(f"[3/4] Creating PRODUCTION deployment ({len(manifest)} files) ...")
    body = {
        "name": PROJECT,
        "files": manifest,
        "target": "production",
        "projectSettings": {
            "framework": None,
            "buildCommand": None,
            "installCommand": None,
            "devCommand": None,
            "outputDirectory": None,
        },
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(body, tf)
        bodyfile = tf.name
    code, sout, serr = curl([
        "-X", "POST", q(f"{API}/v13/deployments?skipAutoDetectionConfirmation=1"),
        "-H", f"Authorization: Bearer {TOKEN}",
        "-H", "Content-Type: application/json",
        "--data-binary", f"@{bodyfile}",
    ])
    os.unlink(bodyfile)
    try:
        dep = json.loads(sout)
    except Exception:
        sys.exit(f"Deployment create returned non-JSON: {sout[:400]}")
    if "error" in dep:
        sys.exit(f"Deployment error: {json.dumps(dep['error'])[:400]}")

    dep_id = dep.get("id") or dep.get("uid")
    url = dep.get("url")
    print(f"      deployment id: {dep_id}")
    print(f"      build url:     https://{url}")

    print("[4/4] Polling until READY ...")
    final = None
    for _ in range(120):  # up to ~10 min
        code, sout, _ = curl(["-H", f"Authorization: Bearer {TOKEN}", q(f"{API}/v13/deployments/{dep_id}")])
        try:
            st = json.loads(sout)
        except Exception:
            time.sleep(5); continue
        state = st.get("readyState") or st.get("status")
        print(f"      {state}")
        if state in ("READY", "ERROR", "CANCELED"):
            final = st; break
        time.sleep(5)

    if not final or (final.get("readyState") or final.get("status")) != "READY":
        sys.exit(f"Deployment did not reach READY: {(final or {}).get('readyState')}")

    aliases = final.get("alias") or []
    print("\n=== DEPLOYED (production) ===")
    print(f"  build url : https://{url}")
    for a in aliases:
        print(f"  alias     : https://{a}")
    print(f"  project   : https://{PROJECT}.vercel.app  (production domain)")
    print("============================")


if __name__ == "__main__":
    main()
