#!/usr/bin/env python3
"""
Where does the app think the backend is?

One function decides, and it has to serve two situations that want opposite
defaults:

    192.168.1.5                 a laptop on the WiFi   -> http,  port 8001
    laptop.tail1a2b3c.ts.net    a tunnel               -> https, port 443

The old rule applied the first to both, so pasting a tunnel hostname produced
`http://laptop.tail1a2b3c.ts.net:8001` - wrong scheme, wrong port, and a port
that is not open to the internet at all. The request hung until it timed out
and the app reported that the server could not be reached, which sent everyone
looking at the server.

These run the real module through node rather than reimplementing it, because
a Python copy of the rules would only prove the copy agrees with itself.

    python scripts/test_api_base.py
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"

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


# ---------------------------------------------------------------------------
# apiBase.js is an ES module with no imports, so stripping the export keyword
# turns it into a plain script. `process.env` is referenced at load time, so it
# needs to exist - node provides it.
# ---------------------------------------------------------------------------

HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export /gm, '');

// localStorage does not exist in node. The module already guards every access
// with try/catch, but stubbing it keeps the failure path out of these results.
global.localStorage = {
  _v: {},
  getItem(k) { return this._v[k] ?? null; },
  setItem(k, v) { this._v[k] = String(v); },
  removeItem(k) { delete this._v[k]; },
};

// The call has to happen INSIDE the same eval as the source.
//
// A direct eval leaks `var` and `function` declarations into the enclosing
// scope, but NOT `let`, `const` or `class` - those stay in the eval's own
// scope and vanish the moment it returns. normaliseBase is a const arrow, so
// evaluating the module and then calling the function from outside throws
// ReferenceError. Concatenating the caller keeps both in one scope.
const inputs = JSON.parse(process.argv[3]);
const out = eval(
  src +
  '\n;(function () {\n' +
  '  const result = {};\n' +
  '  for (const value of ' + JSON.stringify(inputs) + ') {\n' +
  '    result[value] = normaliseBase(value);\n' +
  '  }\n' +
  '  return result;\n' +
  '})()'
);
console.log(JSON.stringify(out));
"""


def normalise_all(inputs):
    node = shutil.which("node")
    if not node:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        harness = Path(tmp) / "h.js"
        harness.write_text(HARNESS)
        result = subprocess.run(
            [node, str(harness), str(SRC / "apiBase.js"), json.dumps(inputs)],
            capture_output=True, text=True, timeout=30,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:])
    return json.loads(result.stdout)


# Input -> what it must become. Every one of these is something a person
# actually types or pastes.
CASES = {
    # --- tunnels: https, no port. The case that was broken. ---
    "laptop.tail1a2b3c.ts.net": "https://laptop.tail1a2b3c.ts.net/api",
    "https://laptop.tail1a2b3c.ts.net": "https://laptop.tail1a2b3c.ts.net/api",
    "https://laptop.tail1a2b3c.ts.net/": "https://laptop.tail1a2b3c.ts.net/api",
    "https://laptop.tail1a2b3c.ts.net/api": "https://laptop.tail1a2b3c.ts.net/api",
    "  laptop.tail1a2b3c.ts.net  ": "https://laptop.tail1a2b3c.ts.net/api",
    # A quick tunnel, for as long as those are still in use.
    "brave-fox-runs.trycloudflare.com": "https://brave-fox-runs.trycloudflare.com/api",
    # Any other host someone might deploy to.
    "nutriplan.onrender.com": "https://nutriplan.onrender.com/api",

    # --- the LAN: http, port 8001. Must not regress. ---
    "192.168.1.5": "http://192.168.1.5:8001/api",
    "192.168.1.5:8001": "http://192.168.1.5:8001/api",
    "http://192.168.1.5": "http://192.168.1.5:8001/api",
    "http://192.168.1.5:8001": "http://192.168.1.5:8001/api",
    "http://192.168.1.5:8001/": "http://192.168.1.5:8001/api",
    "http://192.168.1.5:8001/api": "http://192.168.1.5:8001/api",
    "10.0.0.7": "http://10.0.0.7:8001/api",
    "localhost": "http://localhost:8001/api",
    "localhost:8001": "http://localhost:8001/api",
    "127.0.0.1:8001": "http://127.0.0.1:8001/api",
    "macbook.local": "http://macbook.local:8001/api",

    # --- explicit beats inferred, always ---
    # Someone running the tunnel on an alternate Funnel port.
    "https://laptop.tail1a2b3c.ts.net:8443": "https://laptop.tail1a2b3c.ts.net:8443/api",
    # Deliberately plain http to a public host - unusual, but they said so.
    "http://example.com": "http://example.com/api",

    # --- nothing in, nothing out ---
    "": "",
    "   ": "",
}


def test_normalise():
    print(f"\n{BOLD}1. Every address a person might type{RESET}")

    if not shutil.which("node"):
        skip("normaliseBase behaves", "node not installed")
        return

    try:
        got = normalise_all(list(CASES))
    except RuntimeError as e:
        check("apiBase.js loads", False, e)
        return
    check("apiBase.js loads", True)

    for raw, expected in CASES.items():
        label = f"{raw!r} -> {expected or '(empty)'}"
        check(label, got.get(raw) == expected, f"got {got.get(raw)!r}")


def test_the_two_defaults_are_actually_different():
    """
    Guard the distinction itself, not just the current examples.

    If someone later simplifies this back to one rule, most cases above would
    still pass - the LAN ones, or the tunnel ones, depending which rule
    survived. This fails either way.
    """
    print(f"\n{BOLD}2. A name and an IP are not treated the same{RESET}")

    if not shutil.which("node"):
        skip("the two defaults differ", "node not installed")
        return

    got = normalise_all(["some-host.example.net", "192.168.1.5"])
    name, ip = got["some-host.example.net"], got["192.168.1.5"]

    check("a hostname gets https", name.startswith("https://"), name)
    check("...and no port", ":8001" not in name and ":443" not in name, name)
    check("an IP gets http", ip.startswith("http://"), ip)
    check("...and port 8001", ":8001" in ip, ip)


def test_built_in_address_can_be_escaped():
    """
    A stored address outranks the compiled-in one, forever.

    That is correct - an override has to win - but without a way back, a friend
    who typed a laptop's LAN IP once keeps pointing at it after everyone else
    has moved to the tunnel, and the app simply stops working away from home
    with no indication why.
    """
    print(f"\n{BOLD}3. A manual override is reversible{RESET}")

    api = (SRC / "apiBase.js").read_text()
    for name in ("builtInBase", "isOverridden", "resetToBuiltIn"):
        check(f"apiBase exports {name}", f"export const {name}" in api)

    check("apiBase prefers the stored address over the built-in one",
          re.search(r"getStoredBase\(\)\s*\|\|\s*builtInBase\(\)", api) is not None,
          "an override that does not override is not an override")

    setup = (SRC / "components" / "ServerSetup.jsx").read_text()
    check("the setup screen offers a way back",
          "resetToBuiltIn" in setup and "isOverridden" in setup)
    check("...and only when there is something to go back to",
          "builtInBase()" in setup,
          "showing the button with no built-in address would clear to nothing")


def test_backend_accepts_the_tunnel():
    print(f"\n{BOLD}4. The server allows the origins that will reach it{RESET}")

    main = (ROOT / "main.py").read_text()
    block = main.split("CORSMiddleware", 1)[-1].split(")", 1)[0]
    regex_match = re.search(r"allow_origin_regex=\(?\s*(.+?)\n\s*allow_credentials",
                            main, re.S)
    check("there is an origin regex", regex_match is not None)

    # The APK's own origin. Capacitor is configured with androidScheme http,
    # so the webview reports http://localhost - not capacitor://.
    check("the APK's webview origin is allowed",
          '"http://localhost"' in main,
          "androidScheme is http in capacitor.config.json")

    pattern = "".join(re.findall(r'r?"([^"]*)"', regex_match.group(1))) if regex_match else ""
    check("ts.net hostnames are allowed", "ts\\.net" in pattern, pattern)

    # The classic mistake: an unanchored pattern matches a hostile lookalike.
    check("the pattern is anchored at both ends",
          pattern.startswith("^") and pattern.endswith("$"), pattern)
    if pattern:
        compiled = re.compile(pattern)
        good = "https://laptop.tail1a2b3c.ts.net"
        check(f"...{good} matches", compiled.match(good) is not None)
        for hostile in ("https://ts.net.attacker.com",
                        "https://laptop.tail1a2b3c.ts.net.evil.com"):
            check(f"...{hostile} does not", compiled.match(hostile) is None)
        check("...and the LAN range still matches",
              compiled.match("http://192.168.1.5:8001") is not None)


def test_serve_script():
    print(f"\n{BOLD}5. One command to start it all{RESET}")

    script = ROOT / "scripts" / "serve-public.sh"
    check("scripts/serve-public.sh exists", script.exists())
    if not script.exists():
        return
    text = script.read_text()

    import os
    check("...and is executable", os.access(script, os.X_OK))
    check("...and is syntactically valid",
          subprocess.run(["bash", "-n", str(script)],
                         capture_output=True).returncode == 0)

    check("it checks tailscale is installed before using it", "command -v tailscale" in text)
    check("it checks you are logged in", "tailscale status" in text)
    check("it waits for the server before opening the tunnel",
          "/health" in text,
          "otherwise the first request lands on a port with nothing on it")

    # This assertion used to say the opposite - "it takes the funnel down on
    # exit" - and it kept passing after the behaviour was reversed, because it
    # only looked for the words "funnel" and "trap" somewhere in the file. A
    # test that passes for the wrong reason is worse than no test, so it now
    # names the actual invariant.
    cleanup = text.split("cleanup()", 1)[-1].split("trap cleanup", 1)[0]
    check("cleanup does NOT turn the funnel off",
          "funnel" not in cleanup or "off" not in cleanup,
          "the machine's public DNS record exists only while a funnel is "
          "configured, so tearing it down on exit un-publishes the address")
    check("...but it does stop the server", "kill" in cleanup, cleanup[:200])
    check("the funnel is configured with --bg so it survives a reboot",
          "funnel --bg" in text)

    check("it prints the website address", "Website" in text)
    check("...and the API address", "$API_URL" in text)
    check("it warns when there is no frontend build to serve",
          "frontend/build/index.html" in text,
          "otherwise the website silently 404s and the cause is not obvious")

    # Checking DNS with dig on a Tailscale machine answers from inside the
    # tailnet and reports success regardless of what the public internet sees.
    check("public DNS is checked over DoH, not dig",
          "dns.google" in text and "dig " not in text,
          "dig is split-routed to Tailscale's own resolver and cannot give "
          "an outside answer")
    check("...and 'could not check' is distinct from 'not published'",
          "return 2" in text,
          "folding them together blames Tailscale whenever you are offline")

    doc = ROOT / "TUNNEL.md"
    check("TUNNEL.md exists", doc.exists())
    if doc.exists():
        d = doc.read_text()
        check("...it says the laptop must be awake", "awake" in d.lower())
        check("...and that the URL is public",
              "public internet" in d.lower() or "anyone with the url" in d.lower())
        check("...and names the env file", ".env.production.local" in d)
        check("...and that file is gitignored",
              ".env.production.local" in (ROOT / ".gitignore").read_text(),
              "otherwise the address is published on GitHub")


def test_commands_survive_being_pasted():
    """
    Every shell block in the docs has to work when pasted into zsh.

    zsh does NOT treat `#` as a comment at an interactive prompt - the
    INTERACTIVE_COMMENTS option is off by default. So a line like

        tailscale funnel 8001        # approve in the browser page

    does not run `tailscale funnel 8001` with a note attached. It runs it with
    nine extra arguments and fails with "invalid number of arguments", which
    looks like the tool is broken rather than the instructions.

    Only explicitly tagged bash/shell/sh fences are checked. Untagged fences
    hold directory diagrams, which are full of # and are not commands.
    """
    print(f"\n{BOLD}6. Documented commands survive a copy-paste into zsh{RESET}")

    offenders = []
    checked = 0
    for path in sorted(ROOT.glob("*.md")):
        for block in re.findall(r"```(?:bash|shell|sh)\n(.*?)```", path.read_text(), re.S):
            for line in block.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue          # a whole-line comment is fine, it is obvious
                checked += 1
                if re.search(r"\S\s+#", stripped):
                    offenders.append(f"{path.name}: {stripped}")

    check(f"none of the {checked} documented commands has a trailing # comment",
          not offenders, "\n".join(offenders))


def test_no_orphan_tests():
    print(f"\n{BOLD}6. No test is defined and then forgotten{RESET}")
    import inspect
    body = inspect.getsource(main)
    defined = {n for n, o in globals().items()
               if n.startswith("test_") and inspect.isfunction(o)}
    missing = sorted(n for n in defined if f"{n}()" not in body)
    check(f"all {len(defined)} test functions are called", not missing, missing)


def main():
    test_normalise()
    test_the_two_defaults_are_actually_different()
    test_built_in_address_can_be_escaped()
    test_backend_accepts_the_tunnel()
    test_serve_script()
    test_commands_survive_being_pasted()
    test_no_orphan_tests()

    print(f"\n{BOLD}{'-' * 62}{RESET}")
    tail = f", {YELLOW}{skipped} skipped{RESET}" if skipped else ""
    print(f"{GREEN}{passed} passed{RESET}, "
          f"{RED if failed else DIM}{failed} failed{RESET}{tail}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
