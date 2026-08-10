#!/usr/bin/env python3
"""
One address serves the website AND the API.

Friends should be able to open a link rather than install an APK - which also
means anyone on an iPhone can use the app at all. The built React app is
therefore served by the same FastAPI process, so:

    https://your-host/            the site
    https://your-host/api/...     the API it calls
    https://your-host/health      the check the tunnel script uses

Same origin, so no CORS, no cookie problems, no mixed content, and no second
Funnel port (Funnel only allows 443, 8443 and 10000, so a second one would put
an ugly :8443 in the URL).

THE ONE THING THAT CAN GO WRONG
-------------------------------
`app.mount("/", StaticFiles(...))` matches EVERY path. Registered before the
routers, it swallows the entire API and every endpoint returns index.html or
404 - which looks like the routes disappeared rather than like an ordering
mistake. These tests make real requests against the real app, so that failure
cannot pass quietly.

    python scripts/test_web_serving.py
"""

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
)
passed = failed = skipped = 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}pass{RESET}  {label}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {label}")
        for line in str(detail).splitlines()[:8]:
            print(f"        {DIM}{line}{RESET}")


def skip(label, why):
    global skipped
    skipped += 1
    print(f"  {YELLOW}skip{RESET}  {label} {DIM}({why}){RESET}")


BUILD = ROOT / "frontend" / "build"


def client():
    """The real app, or None if its dependencies are not installed here."""
    try:
        import logging
        logging.disable(logging.INFO)
        from fastapi.testclient import TestClient
        import main
        return TestClient(main.app)
    except Exception as e:
        print(f"  {DIM}{type(e).__name__}: {e}{RESET}")
        return None


# ---------------------------------------------------------------------------

def test_source_ordering():
    """
    The invariant, stated where a reader will see it.

    The runtime tests below would also catch this, but only as "the API is
    404ing" - which sends you looking at routers. Naming the cause here turns
    twenty minutes of confusion into one line.
    """
    print(f"\n{BOLD}1. The static mount is registered after every router{RESET}")

    lines = (ROOT / "main.py").read_text().splitlines()
    routers = [i for i, l in enumerate(lines) if "app.include_router" in l]
    mounts = [i for i, l in enumerate(lines)
              if re.search(r"app\.mount\(\s*['\"]/['\"]", l)]

    check("there is at least one router", bool(routers))
    check("there is a mount at /", bool(mounts), "no app.mount('/') found")
    if routers and mounts:
        check("the mount comes after the last router",
              min(mounts) > max(routers),
              f"last include_router on line {max(routers)+1}, "
              f"mount on line {min(mounts)+1} - a mount at / matches "
              f"everything, so this order is load-bearing")


def test_build_exists():
    print(f"\n{BOLD}2. There is a build to serve{RESET}")
    check("frontend/build exists", BUILD.is_dir(),
          "run: cd frontend && npm run build")
    check("...with an index.html", (BUILD / "index.html").is_file())
    bundles = glob.glob(str(BUILD / "static" / "js" / "main.*.js"))
    check("...and a main bundle", bool(bundles), bundles)


def test_website_is_served():
    print(f"\n{BOLD}3. The website{RESET}")
    c = client()
    if c is None:
        skip("the app serves the site", "app dependencies not installed here")
        return

    r = c.get("/")
    check("GET / returns 200", r.status_code == 200, r.status_code)
    check("...and it is the React page, not JSON",
          "<!doctype html" in r.text[:200].lower(),
          r.text[:120])

    bundles = glob.glob(str(BUILD / "static" / "js" / "main.*.js"))
    if bundles:
        path = "/" + str(Path(bundles[0]).relative_to(BUILD))
        r = c.get(path)
        check(f"the JS bundle is served ({len(r.content)//1024} KB)",
              r.status_code == 200, r.status_code)

    r = c.get("/manifest.json")
    check("root-level assets are served too", r.status_code == 200, r.status_code)


def test_the_api_still_works():
    """The failure mode that matters: a mount at / swallowing everything."""
    print(f"\n{BOLD}4. The API is not swallowed by the mount{RESET}")
    c = client()
    if c is None:
        skip("the API still routes", "app dependencies not installed here")
        return

    r = c.get("/health")
    check("GET /health is still JSON",
          r.status_code == 200 and r.json().get("status") == "healthy",
          f"{r.status_code} {r.text[:80]}")

    # 401 means the router was reached and rejected the request. 404 would mean
    # the static mount answered instead, which is the bug.
    #
    # These must be paths that really exist. An earlier version asserted
    # /api/profile/me, which the profile router does not define - so the test
    # reported the mount swallowing the API when the path was simply invented.
    # A test that fails for its own reasons is worse than no test.
    for method, path in [("GET", "/api/auth/me"),
                         ("POST", "/api/nutrient/log-meal"),
                         ("GET", "/api/profile/points"),
                         ("GET", "/api/profile/leaderboard")]:
        r = c.request(method, path, json={})
        check(f"{method} {path} reaches its router",
              r.status_code != 404,
              "got 404 - either the mount at / answered instead of the API, "
              "or this path does not exist and the test is wrong")

    r = c.get("/docs")
    check("the API docs still load", r.status_code == 200, r.status_code)

    r = c.get("/no-such-page-anywhere")
    check("an unknown path is a clean 404", r.status_code == 404, r.status_code)


def test_the_page_knows_where_the_api_is():
    print(f"\n{BOLD}5. The page calls the right backend{RESET}")

    bundles = glob.glob(str(BUILD / "static" / "js" / "main.*.js"))
    if not bundles:
        skip("the bundle has an API address", "no build")
        return

    text = Path(bundles[0]).read_text(errors="ignore")
    urls = sorted(set(re.findall(r"https://[a-z0-9.-]+\.ts\.net/api", text)))

    check("an absolute tunnel URL is compiled in", bool(urls),
          "REACT_APP_API_URL was not picked up - check "
          "frontend/.env.production.local, then rebuild")
    if urls:
        check(f"...exactly one of them: {urls[0]}", len(urls) == 1, urls)

    # Same origin as the site, so the browser makes a plain same-origin request
    # and CORS never enters into it.
    env = ROOT / "frontend" / ".env.production.local"
    if env.is_file():
        declared = env.read_text().strip().split("=", 1)[-1]
        check("the bundle matches .env.production.local",
              not urls or declared.rstrip("/") == urls[0],
              f"env says {declared!r}, bundle has {urls}")
    else:
        skip("the bundle matches .env.production.local", "file not present")


def test_no_orphan_tests():
    print(f"\n{BOLD}6. No test is defined and then forgotten{RESET}")
    import inspect
    body = inspect.getsource(main_fn)
    defined = {n for n, o in globals().items()
               if n.startswith("test_") and inspect.isfunction(o)}
    missing = sorted(n for n in defined if f"{n}()" not in body)
    check(f"all {len(defined)} test functions are called", not missing, missing)


def main_fn():
    test_source_ordering()
    test_build_exists()
    test_website_is_served()
    test_the_api_still_works()
    test_the_page_knows_where_the_api_is()
    test_no_orphan_tests()

    print(f"\n{BOLD}{'-' * 62}{RESET}")
    tail = f", {YELLOW}{skipped} skipped{RESET}" if skipped else ""
    print(f"{GREEN}{passed} passed{RESET}, "
          f"{RED if failed else DIM}{failed} failed{RESET}{tail}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main_fn())
