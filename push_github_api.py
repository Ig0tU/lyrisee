#!/usr/bin/env python3
"""
Push the working tree to GitHub via the Git Data API (curl transport).

Why not `git push`: this image's git links libcurl-gnutls, and GnuTLS refuses the
sandbox proxy's MITM cert (openssl-backed curl accepts it fine). So we recreate the
commit through the REST API over curl: blobs -> tree -> commit -> ref.

Creates ONE clean initial commit on refs/heads/main containing every tracked file.
Token is read from GH_TOKEN env ONLY; never written to disk or logged.
"""
import os, sys, json, base64, subprocess, tempfile

OWNER = os.environ.get("GH_OWNER", "Ig0tU")
REPO = os.environ.get("GH_REPO", "lyrisee")
TOKEN = os.environ.get("GH_TOKEN", "").strip()
BRANCH = os.environ.get("GH_BRANCH", "main")
API = "https://api.github.com"
ROOT = os.path.dirname(os.path.abspath(__file__))


def curl_json(method, url, payload=None, timeout=120):
    args = ["curl", "-sS", "--max-time", str(timeout), "-X", method,
            "-H", f"Authorization: token {TOKEN}",
            "-H", "Accept: application/vnd.github+json",
            "-H", "Content-Type: application/json", url]
    tmp = None
    if payload is not None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(payload, tmp); tmp.close()
        args[ -1:-1] = ["--data-binary", f"@{tmp.name}"]  # insert before url
    r = subprocess.run(args, capture_output=True, text=True)
    if tmp:
        os.unlink(tmp.name)
    try:
        return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return r.returncode, {"_raw": r.stdout[:500], "_err": r.stderr[:300]}


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-s"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    files = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        mode = meta.split()[0]           # 100644 / 100755
        files.append((mode, path))
    return files


def get_parent():
    code, resp = curl_json("GET", f"{API}/repos/{OWNER}/{REPO}/git/ref/heads/{BRANCH}")
    return resp.get("object", {}).get("sha")


def bootstrap():
    """Empty repos reject the blobs API; create one file via Contents API to init."""
    path = ".gitignore"
    data = open(os.path.join(ROOT, path), "rb").read()
    code, resp = curl_json("PUT", f"{API}/repos/{OWNER}/{REPO}/contents/{path}",
                           {"message": "Initialize repository",
                            "content": base64.b64encode(data).decode(), "branch": BRANCH})
    sha = resp.get("commit", {}).get("sha")
    if not sha:
        sys.exit(f"  bootstrap failed: {json.dumps(resp)[:300]}")
    return sha


def main():
    if not TOKEN:
        sys.exit("GH_TOKEN not set. Aborting.")

    parent = get_parent()
    if not parent:
        print("[0/4] Repo empty -> bootstrapping initial commit via Contents API ...")
        parent = bootstrap()
        print(f"  bootstrap commit: {parent}")

    files = tracked_files()
    print(f"[1/4] Creating {len(files)} blobs ...")
    tree = []
    for mode, path in files:
        data = open(os.path.join(ROOT, path), "rb").read()
        code, resp = curl_json("POST", f"{API}/repos/{OWNER}/{REPO}/git/blobs",
                               {"content": base64.b64encode(data).decode(), "encoding": "base64"})
        sha = resp.get("sha")
        if not sha:
            sys.exit(f"  blob failed for {path}: {json.dumps(resp)[:300]}")
        tree.append({"path": path, "mode": mode, "type": "blob", "sha": sha})
        print(f"  ok {path:34s} {len(data):>9,d} b")

    print("[2/4] Creating tree ...")
    code, resp = curl_json("POST", f"{API}/repos/{OWNER}/{REPO}/git/trees", {"tree": tree})
    tree_sha = resp.get("sha")
    if not tree_sha:
        sys.exit(f"  tree failed: {json.dumps(resp)[:400]}")
    print(f"  tree sha: {tree_sha}")

    print("[3/4] Creating commit ...")
    msg = ("Lyrisee — AI kinetic-typography lyric-video engine + Director pipeline\n\n"
           "Static engine (index/dark-nights/80k/rhyme) deploys to Vercel; the Python\n"
           "Director pipeline lives under backend/ (not part of the web deploy).")
    parents = [parent] if parent else []
    code, resp = curl_json("POST", f"{API}/repos/{OWNER}/{REPO}/git/commits",
                           {"message": msg, "tree": tree_sha, "parents": parents})
    commit_sha = resp.get("sha")
    if not commit_sha:
        sys.exit(f"  commit failed: {json.dumps(resp)[:400]}")
    print(f"  commit sha: {commit_sha}")

    print(f"[4/4] Pointing refs/heads/{BRANCH} at commit ...")
    code, resp = curl_json("PATCH", f"{API}/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
                           {"sha": commit_sha, "force": True})
    if "ref" not in resp:  # ref didn't exist yet (no bootstrap) -> create it
        code, resp = curl_json("POST", f"{API}/repos/{OWNER}/{REPO}/git/refs",
                               {"ref": f"refs/heads/{BRANCH}", "sha": commit_sha})
    if "ref" not in resp and resp.get("object", {}).get("sha") != commit_sha:
        sys.exit(f"  ref failed: {json.dumps(resp)[:400]}")
    print(f"  ref -> {commit_sha}")
    print(f"\n=== PUSHED ===\n  https://github.com/{OWNER}/{REPO}  (branch {BRANCH})")


if __name__ == "__main__":
    main()
