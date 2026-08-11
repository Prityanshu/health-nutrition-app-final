#!/usr/bin/env python3
"""
The colour system, and the guarantee that extracting it changed nothing.

WHAT THIS REPLACED
------------------
Every colour in the app used to be a literal: 53 distinct hex values over 693
occurrences, plus 256 rgba() tints repeating the same numbers in decimal.
Changing an accent meant a project-wide find and replace, and any component
written afterwards drifted immediately.

THE ONE THING THAT MATTERS
--------------------------
This was plumbing. The app is supposed to look identical afterwards, so the
central check is that no colour VALUE appeared which was not already there -
the set of colours the app can render must be a subset of the original 53.

Comparing occurrence COUNTS was the first attempt and had to be abandoned:
some colours now travel as an RGB triple name in a data structure
(`colour: '--cyan-rgb'`) and only become a colour when solid() or tint() wraps
them at render time. A static scan cannot see through that, so the counts drop
while the output is unchanged. The counting test went red describing nothing,
which is the worst kind of test.

THE TRAP THIS ALMOST SHIPPED WITH
---------------------------------
Several components build a translucent colour by appending a two-digit hex
alpha:

    boxShadow: `0 0 10px ${color}55`

That works when `color` is "#22D3EE" and breaks SILENTLY when it becomes
"var(--cyan)", because `var(--cyan)55` is not a colour - the browser drops the
declaration and the glow simply vanishes. Nothing throws and nothing warns.
Ten sites did this. They now carry an RGB triple name and use tint(); the
checks below make sure none of them come back.

    python scripts/test_theme.py
"""

import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
CSS = SRC / "index.css"

GREEN, RED, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
)
passed = failed = 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}pass{RESET}  {label}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {label}")
        for line in str(detail).splitlines()[:10]:
            print(f"        {DIM}{line}{RESET}")


def source_files():
    return [p for p in SRC.rglob("*")
            if p.suffix in (".css", ".js", ".jsx") and "node_modules" not in str(p)]


def code_only(text):
    """
    The file with comments removed.

    Not cosmetic. The first version of these checks scanned raw text and
    reported failures against its own documentation - theme.js explains the
    bug using `${color}55` and "#22D3EE" as examples, and the scanner
    dutifully flagged both. A checker that cannot tell code from prose reports
    problems that do not exist, which is worse than reporting none.

    The `(?<!:)` guard keeps `https://` from being read as a line comment.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(?<!:)//[^\n]*", "", text)
    return text


def root_block():
    """The text of the :root { ... } declaration, by brace matching."""
    text = CSS.read_text()
    start = text.index(":root")
    depth, i = 0, text.index("{", start)
    opened = i
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[opened:i + 1]
        i += 1
    return ""


def palette():
    """Every colour variable and its literal value."""
    block = root_block()
    hexes = dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;", block))
    triples = dict(re.findall(r"(--[a-z0-9-]+-rgb):\s*(\d+\s*,\s*\d+\s*,\s*\d+)\s*;", block))
    return {k: v.upper() for k, v in hexes.items()}, triples


# ---------------------------------------------------------------------------

def test_palette_exists():
    print(f"\n{BOLD}1. There is a palette{RESET}")
    hexes, triples = palette()
    check(f"{len(hexes)} colour variables are defined", len(hexes) >= 15, sorted(hexes))
    check(f"{len(triples)} rgb triples for tints", len(triples) >= 5, sorted(triples))

    # The names have to mean something, or this is a lookup table with extra
    # steps. Roles, not values: --accent, never --violet-2.
    for role in ("--bg", "--surface", "--border", "--text", "--accent",
                 "--success", "--warning", "--danger"):
        check(f"{role} exists", role in hexes, sorted(hexes))

    banned = [k for k in hexes if re.search(r"(purple|violet|blue|pink|green|red|yellow)\d", k)]
    check("no numbered colour names", not banned, banned)


def test_no_new_colours_appeared():
    """
    The guarantee that matters: extracting the palette was not a redesign.

    Counting occurrences turned out to be the wrong test. Some colours now
    travel as an RGB TRIPLE NAME in a data structure - `colour: '--cyan-rgb'` -
    and become a colour only when solid() or tint() wraps them at render time.
    A static scan cannot see those, so the counts legitimately drop while the
    rendered output is identical. Asserting on them produced a red suite that
    was describing nothing.

    What IS checkable, and is the actual promise: the set of colour values the
    app can produce must be a subset of the values it produced before. Nothing
    new, nothing invented.
    """
    print(f"\n{BOLD}2. No colour appeared that was not there before{RESET}")
    hexes, _ = palette()

    # The 53 distinct hex values present before the extraction.
    BEFORE = {
        "#667085", "#98A2B3", "#A78BFA", "#34D399", "#2A3240", "#FBBF24",
        "#8B5CF6", "#22D3EE", "#F87171", "#EEF2F7", "#12151B", "#FFFFFF",
        "#3A4453", "#1A1A1A", "#8A2BE2", "#A66BFF", "#C6CEDA", "#5A5A5A",
        "#171B23", "#1E242E", "#F472B6", "#0B0E14", "#556070", "#FCA5A5",
        "#4ADE80", "#FACC15", "#EF4444", "#0B0D11", "#6D28D9", "#7D8899",
        "#C05BC7", "#E0D9FF", "#D6E4FF", "#F3E8FF", "#22C55E", "#EAB308",
        "#DC2626", "#F0F0F0", "#C4B5FD", "#6366F1", "#232A35", "#6B7280",
        "#E0E0E0", "#A9B4C4", "#6EE7B7", "#7C3AED", "#DCE3EC", "#262E3A",
        "#05070A", "#67E8F9", "#161A22", "#D264C8", "#FB923C",
    }

    now = set()
    for path in source_files():
        text = code_only(path.read_text(errors="ignore"))
        now |= {m.upper() for m in re.findall(r"#[0-9A-Fa-f]{6}\b", text)}

    invented = sorted(now - BEFORE)
    check("every colour in the codebase existed before the change",
          not invented, invented)

    # And every palette variable holds one of the original values - so naming
    # them did not quietly adjust any of them.
    drifted = {k: v for k, v in hexes.items() if v not in BEFORE}
    check(f"all {len(hexes)} palette values are original values",
          not drifted, drifted)

    # The rgb triples must match their hex twin exactly, or a tint would be a
    # different hue from the solid colour it is supposed to be a fade of.
    _, triples = palette()
    mismatched = []
    for name, triple in triples.items():
        twin = hexes.get(name.replace("-rgb", ""))
        if not twin:
            continue
        r, g, b = (int(x) for x in triple.split(","))
        if f"#{r:02X}{g:02X}{b:02X}" != twin:
            mismatched.append(f"{name} = {triple} but {name[:-4]} = {twin}")
    check("every rgb triple matches its hex twin", not mismatched, mismatched)


def test_no_broken_concatenation():
    """
    A var() with characters glued to it is not a colour.

    This is the failure that does not announce itself: the browser drops the
    declaration, the glow disappears, and everything else keeps working.
    """
    print(f"\n{BOLD}3. No colour has an alpha glued onto it{RESET}")

    glued, appended = [], []
    for path in source_files():
        for i, line in enumerate(code_only(path.read_text(errors="ignore")).splitlines(), 1):
            if re.search(r"var\(--[a-z0-9-]+\)[0-9a-zA-Z]", line):
                glued.append(f"{path.name}:{i}: {line.strip()[:90]}")
            # `${something}55` inside a template literal - the runtime version
            # of the same mistake, which a source scan for var() would miss.
            if re.search(r"\$\{[^}]+\}[0-9a-fA-F]{2}\b", line):
                appended.append(f"{path.name}:{i}: {line.strip()[:90]}")

    check("no var() with characters appended", not glued, "\n".join(glued))
    check("no template literal appends a hex alpha to a colour",
          not appended,
          "\n".join(appended) + "\n use tint('--x-rgb', 0.33) from src/theme.js")


def test_tint_helper():
    print(f"\n{BOLD}4. Tints come from the same source of truth{RESET}")
    theme = (SRC / "theme.js")
    check("src/theme.js exists", theme.exists())
    if not theme.exists():
        return
    text = theme.read_text()
    check("it exports solid()", "export const solid" in text)
    check("it exports tint()", "export const tint" in text)

    # The modern space-separated syntax needs a recent Chrome; this ships in an
    # Android WebView that can be years old.
    check("tints use the comma syntax, not rgb(r g b / a)",
          "rgba(var(" in text and "/ ${" not in text, text)

    users = [p.name for p in source_files()
             if re.search(r"\b(solid|tint)\(", p.read_text(errors="ignore"))
             and p.name not in ("theme.js", "severity.js")]
    check(f"{len(users)} components use the helpers", len(users) >= 4, users)

    missing = [p.name for p in source_files()
               if re.search(r"[^a-zA-Z](solid|tint)\(", p.read_text(errors="ignore"))
               and "from '../theme'" not in p.read_text(errors="ignore")
               and "from './theme'" not in p.read_text(errors="ignore")
               and p.name != "theme.js"
               and re.search(r"[^*] (solid|tint)\(", p.read_text(errors="ignore")) is None]
    check("every user imports them", not missing, missing)


def test_literals_are_rare_now():
    print(f"\n{BOLD}5. Literals are the exception, not the rule{RESET}")

    remaining = collections.Counter()
    for path in source_files():
        text = code_only(path.read_text(errors="ignore"))
        if path.name == "index.css":
            text = text.replace(code_only(root_block()), "")
        for m in re.findall(r"#[0-9A-Fa-f]{6}\b", text):
            remaining[m.upper()] += 1

    # 53 distinct values over 693 occurrences before. What is left is the long
    # tail of one-offs - naming a colour used twice makes a worse system, not a
    # better one - so this is a ceiling rather than zero.
    check(f"{sum(remaining.values())} hex literals remain (was 693)",
          sum(remaining.values()) < 120,
          "\n".join(f"{c} x{n}" for c, n in remaining.most_common(12)))
    check(f"{len(remaining)} distinct literals remain (was 53)",
          len(remaining) < 40, sorted(remaining))

    # The colours that carry meaning must NOT be sitting around as literals.
    hexes, _ = palette()
    leaked = {c: n for c, n in remaining.items() if c in set(hexes.values())}
    check("no palette colour is still hardcoded anywhere",
          not leaked, leaked)


def test_no_orphan_tests():
    print(f"\n{BOLD}6. No test is defined and then forgotten{RESET}")
    import inspect
    body = inspect.getsource(main)
    defined = {n for n, o in globals().items()
               if n.startswith("test_") and inspect.isfunction(o)}
    missing = sorted(n for n in defined if f"{n}()" not in body)
    check(f"all {len(defined)} test functions are called", not missing, missing)


def main():
    test_palette_exists()
    test_no_new_colours_appeared()
    test_no_broken_concatenation()
    test_tint_helper()
    test_literals_are_rare_now()
    test_no_orphan_tests()

    print(f"\n{BOLD}{'-' * 62}{RESET}")
    print(f"{GREEN}{passed} passed{RESET}, {RED if failed else DIM}{failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
