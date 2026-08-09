#!/usr/bin/env python3
"""
Can any screen be wider than a phone?

A page wider than the viewport is the cheapest-feeling bug there is: the whole
app slides sideways under your thumb, the fixed header slips out of frame, and
every card looks cut off. It shipped because of one CSS subtlety -

    repeat(4, 1fr)   ==   repeat(4, minmax(auto, 1fr))

and `auto` resolves to MIN-CONTENT. A tile containing the word "Intermediate"
cannot shrink below that word, so four of them overflow a 360px screen.

These checks read the source rather than a browser, so they run anywhere and
in under a second. They cannot prove a layout looks good; they can prove the
specific mistakes that made it look cheap are gone and stay gone.

    python scripts/test_mobile_layout.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "src"
CSS = SRC / "index.css"

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"
passed = failed = 0

# A 360px phone (the narrowest in common use) minus the shell's 1rem side
# padding on each side.
USABLE_WIDTH = 360 - 32


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


def jsx_files():
    return sorted(SRC.rglob("*.jsx")) + sorted(SRC.glob("*.js"))


# ---------------------------------------------------------------------------

def test_no_bare_fr_columns():
    """The bug that caused the sideways swipe."""
    print(f"\n{BOLD}1. No grid column can be pushed wider than its share{RESET}")

    # repeat(N, 1fr) and repeat(${x}, 1fr) - both overflow, because 1fr floors
    # at min-content.
    bare = re.compile(r"repeat\(\s*(?:\d+|\$\{[^}]+\})\s*,\s*1fr\s*\)")
    offenders = []
    for path in jsx_files():
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if bare.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()[:88]}")

    check("no `repeat(N, 1fr)` anywhere - it floors at min-content",
          not offenders, "\n".join(offenders))

    # The same trap written out longhand.
    longhand = re.compile(r"gridTemplateColumns:\s*['\"`](?:1fr\s+)+1fr['\"`]")
    long_offenders = []
    for path in jsx_files():
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if longhand.search(line):
                long_offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()[:88]}")
    check("no `'1fr 1fr'` longhand either", not long_offenders,
          "\n".join(long_offenders))


def test_autofit_minimums_fit():
    """auto-fit collapses to one column only if its minimum actually fits."""
    print(f"\n{BOLD}2. Every auto-fit grid collapses on a 360px screen{RESET}")

    rx = re.compile(r"minmax\((\d+)px\s*,\s*1fr\)")
    too_wide = []
    seen = 0
    for path in jsx_files():
        text = path.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            for m in rx.finditer(line):
                seen += 1
                if int(m.group(1)) > USABLE_WIDTH:
                    too_wide.append(
                        f"{path.relative_to(ROOT)}:{i}: minmax({m.group(1)}px) "
                        f"> {USABLE_WIDTH}px usable"
                    )
    check(f"all {seen} minmax minimums fit in {USABLE_WIDTH}px",
          not too_wide, "\n".join(too_wide))


def test_overflow_backstop():
    """Belt and braces, so a future mistake cannot reach a user."""
    print(f"\n{BOLD}3. The stylesheet backstop{RESET}")
    css = CSS.read_text()

    check("html/body clip horizontal overflow",
          re.search(r"html,\s*body\s*\{[^}]*overflow-x:\s*clip", css, re.S) is not None)
    # `hidden` would make the element a scroll container and silently break
    # position:sticky elsewhere, so `clip` is the correct tool and the
    # fallback is only for browsers without it.
    check("...with a fallback for browsers lacking `clip`",
          "@supports not (overflow: clip)" in css)
    check("cards cannot exceed their column",
          re.search(r"\.surface[^{]*\{[^}]*max-width:\s*100%", css, re.S) is not None)
    check("long unbroken strings wrap instead of pushing wide",
          "overflow-wrap: anywhere" in css)


def test_fixed_chrome_is_accounted_for():
    """
    Content has to clear the header and the tab bar.

    Both are fixed, so they do not take part in layout - anything not
    explicitly padded around them ends up underneath, which is how the last
    card on every screen was half-hidden.
    """
    print(f"\n{BOLD}4. Content clears the fixed header and tab bar{RESET}")
    css = CSS.read_text()

    for name in ("--tabbar-h", "--topbar-h"):
        check(f"{name} is declared once as a variable", css.count(f"{name}:") == 1)

    main = re.search(r"\.shell-main\s*\{[^}]*\}(?![^{]*\})", css)
    check("the mobile .shell-main padding uses both variables",
          "var(--topbar-h)" in css and "var(--tabbar-h)" in css)
    check("...and the safe-area insets",
          css.count("env(safe-area-inset-bottom)") >= 2
          and "env(safe-area-inset-top)" in css)

    # The header must be fixed, not sticky: sticky pins vertically only, so it
    # slid out of frame while the page could still scroll sideways.
    # Again the last rule wins: the base declaration is `display: none`, and
    # the one that matters is the override inside the mobile media query.
    topbars = re.findall(r"\.mobile-topbar\s*\{[^}]*\}", css, re.S)
    mobile_bar = next((b for b in reversed(topbars) if "position" in b), "")
    check("the mobile header is position:fixed, not sticky",
          "position: fixed" in mobile_bar,
          mobile_bar[:200] or "no .mobile-topbar rule with a position")
    check("...and is not the old sticky version",
          "position: sticky" not in mobile_bar)


def media_context():
    """
    Which media query is each rule ACTUALLY inside?

    Brace counting cannot answer this - a file with balanced braces can still
    have a rule in entirely the wrong block. That is not hypothetical: an edit
    closed the mobile media query early and reopened a `min-width: 901px` one,
    which silently moved `.shell-main { margin-left: 0 }` and the whole bottom
    nav into the DESKTOP query. On a phone the rail's 15rem margin kept
    applying and the app was squeezed into the strip beside it.

    Balanced braces reported fine. Only the nesting told the truth.
    """
    css = CSS.read_text()
    depth, stack, out = 0, [], []
    for line in css.split("\n"):
        opened = re.match(r"\s*@media ([^{]+)\{", line)
        if opened:
            stack.append((opened.group(1).strip(), depth))
        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if stack and depth == stack[-1][1]:
                    stack.pop()
        sel = re.match(r"\s*([.#][\w.-]+|body\.[\w-]+)\s*\{", line)
        if sel:
            out.append((sel.group(1), stack[-1][0] if stack else None))
    return out


def test_mobile_rules_are_in_the_mobile_query():
    """The structural check that brace balance cannot make."""
    print(f"\n{BOLD}5. Mobile rules live in the mobile media query{RESET}")

    context = media_context()

    def queries_for(selector):
        return [q for sel, q in context if sel == selector]

    # Each of these MUST have a declaration inside a max-width query, or the
    # phone falls back to the desktop rule.
    for selector, why in [
        (".shell-main", "otherwise the 15rem rail margin squeezes the app right"),
        (".bottom-nav", "otherwise there is no tab bar on a phone"),
        (".nav-rail", "otherwise the drawer is permanently open"),
        (".mobile-topbar", "otherwise there is no header"),
    ]:
        qs = queries_for(selector)
        mobile = [q for q in qs if q and "max-width" in q]
        check(f"{selector} has a max-width rule - {why}",
              bool(mobile), f"found in: {qs}")

    # And the inverse: nothing mobile-only should be hiding in a min-width
    # query, which is the exact shape of the bug.
    for selector in (".shell-main", ".bottom-nav", ".nav-rail", ".mobile-topbar"):
        stray = [q for sel, q in context
                 if sel == selector and q and "min-width" in q]
        check(f"{selector} is not stranded in a min-width query",
              not stray, f"found in: {stray}")


def resolve_at(width, selector, prop):
    """
    What value would `selector { prop }` actually compute to at this viewport?

    A miniature cascade: walk the stylesheet in source order, keep every
    declaration whose media query matches `width`, and return the last one -
    which for equal specificity is what the browser uses.

    This is not a browser and it does not do layout. It answers exactly one
    question, and it is the question that went wrong twice: is the phone
    getting the phone rule, or is it silently falling back to the desktop one?
    """
    css = CSS.read_text()
    depth, stack = 0, []
    winner = None
    lines = css.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        opened = re.match(r"\s*@media ([^{]+)\{", line)
        if opened:
            stack.append((opened.group(1).strip(), depth))

        # Both shapes must be handled. Requiring the brace at end of line
        # missed every single-line rule - including `.bottom-nav {display:none}`
        # - and the resolver silently reported "no value" rather than "none",
        # which is a false pass waiting to happen.
        rule = re.match(r"\s*([^{@]+?)\s*\{(.*)$", line)
        if rule and not opened:
            selectors = [s.strip() for s in rule.group(1).split(",")]
            if selector in selectors:
                # Does every enclosing media query match this width?
                applies = True
                for query, _ in stack:
                    lo = re.search(r"min-width:\s*(\d+)px", query)
                    hi = re.search(r"max-width:\s*(\d+)px", query)
                    if lo and width < int(lo.group(1)):
                        applies = False
                    if hi and width > int(hi.group(1)):
                        applies = False
                    if "prefers-" in query or "pointer:" in query:
                        applies = False      # not a width condition
                if applies:
                    inline = rule.group(2)
                    if "}" in inline:
                        # Single-line rule: the whole body is on this line.
                        body = [inline.split("}")[0]]
                    else:
                        body, d, j = [inline], 1, i + 1
                        while j < len(lines) and d > 0:
                            d += lines[j].count("{") - lines[j].count("}")
                            if d > 0:
                                body.append(lines[j])
                            j += 1
                    for decl in body:
                        for m in re.finditer(
                                rf"(?:^|;)\s*{re.escape(prop)}:\s*([^;}}]+)", decl):
                            winner = m.group(1).strip()

        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if stack and depth == stack[-1][1]:
                    stack.pop()
        i += 1
    return winner


def test_cascade_at_phone_width():
    """
    Simulate what a 360px screen actually gets.

    The bug this catches: `.shell-main { margin-left: 0 }` ended up inside a
    `min-width: 901px` query, so a phone kept the desktop rail's 15rem margin
    and the entire app was squeezed into the strip beside it. Every regex
    check passed, because the rule existed - just in the wrong place.
    """
    print(f"\n{BOLD}6. The cascade, resolved at 360px{RESET}")

    margin = resolve_at(360, ".shell-main", "margin-left")
    check("a phone gets .shell-main margin-left: 0, not the 15rem rail offset",
          margin == "0", f"resolved to {margin!r}")

    desktop_margin = resolve_at(1400, ".shell-main", "margin-left")
    check("a desktop still gets the 15rem rail offset",
          desktop_margin == "15rem", f"resolved to {desktop_margin!r}")

    nav = resolve_at(360, ".bottom-nav", "display")
    check("a phone gets the tab bar", nav == "flex", f"resolved to {nav!r}")

    desktop_nav = resolve_at(1400, ".bottom-nav", "display")
    check("a desktop does not", desktop_nav == "none", f"resolved to {desktop_nav!r}")

    bar = resolve_at(360, ".mobile-topbar", "display")
    check("a phone gets the header", bar == "flex", f"resolved to {bar!r}")
    check("a desktop does not",
          resolve_at(1400, ".mobile-topbar", "display") == "none")

    rail_z = resolve_at(360, ".nav-rail", "z-index")
    nav_z = resolve_at(360, ".bottom-nav", "z-index")
    check("at 360px the drawer outranks the tab bar",
          rail_z and nav_z and int(rail_z) > int(nav_z),
          f"rail {rail_z} vs tab bar {nav_z}")


def test_one_breakpoint_not_two():
    """
    The CSS and the JS must agree on what counts as a phone.

    They did not. The stylesheet swapped the whole shell at 900px while
    useIsPhone.js swapped grid column counts at 760px, so every viewport
    between 761 and 900 rendered the PHONE shell around DESKTOP grids - a
    combination nobody designed and nobody had ever looked at.

    900px also catches a desktop browser. A half-width window, or a normal
    window at 150% zoom, is under 900 CSS pixels - and the website turned into
    a phone: sidebar collapsed to a drawer, tab bar along the bottom. That is
    a website behaving like an app on a machine that is not one.

    Neither number is meaningful on its own. What matters is that there is
    exactly ONE of them.
    """
    print(f"\n{BOLD}7. One breakpoint, shared by the CSS and the JS{RESET}")

    hook = (SRC / "useIsPhone.js").read_text()
    m = re.search(r"PHONE_MAX\s*=\s*(\d+)", hook)
    check("useIsPhone declares PHONE_MAX", m is not None, hook[:300])
    if not m:
        return
    phone_max = int(m.group(1))

    # Every query that switches a shell element has to use that number.
    shell = (".shell-main", ".bottom-nav", ".nav-rail", ".mobile-topbar", ".nav-scrim")
    wrong = []
    for selector, query in media_context():
        if selector not in shell or not query:
            continue
        lows = [int(v) for v in re.findall(r"min-width:\s*(\d+)px", query)]
        highs = [int(v) for v in re.findall(r"max-width:\s*(\d+)px", query)]

        # A query that starts above the breakpoint is a refinement WITHIN the
        # desktop shell - narrower gutters on a half-width window, say - not a
        # switch between the two shells. Its max-width is a different kind of
        # number and must not be forced to match.
        if lows and min(lows) > phone_max:
            continue

        for value in highs:
            if value != phone_max:
                wrong.append(f"{selector} switches at max-width {value}px")
        for value in lows:
            # The desktop side is the first pixel above the phone side.
            if value != phone_max + 1:
                wrong.append(f"{selector} switches at min-width {value}px")

    check(f"every shell media query uses {phone_max}px, the same as PHONE_MAX",
          not wrong, "\n".join(sorted(set(wrong))))

    # And the resolved behaviour, either side of the line. A desktop browser
    # window narrowed to 800px is still a desktop browser.
    check("at 800px the sidebar is still a sidebar",
          resolve_at(800, ".shell-main", "margin-left") == "15rem",
          f"resolved to {resolve_at(800, '.shell-main', 'margin-left')!r}")
    check("...and there is no tab bar",
          resolve_at(800, ".bottom-nav", "display") == "none",
          f"resolved to {resolve_at(800, '.bottom-nav', 'display')!r}")
    check("...and no mobile header",
          resolve_at(800, ".mobile-topbar", "display") == "none")
    check(f"but at {phone_max}px it is the phone shell",
          resolve_at(phone_max, ".bottom-nav", "display") == "flex",
          f"resolved to {resolve_at(phone_max, '.bottom-nav', 'display')!r}")
    check(f"...and at {phone_max + 1}px it is not",
          resolve_at(phone_max + 1, ".bottom-nav", "display") == "none")


def test_drawer_stacking():
    """The drawer must sit above the tab bar, or it buries its own content."""
    print(f"\n{BOLD}5. Drawer stacking order{RESET}")
    css = CSS.read_text()

    def z_of(selector):
        """
        The LAST declared z-index for a selector, not the first.

        Both .nav-rail and .mobile-topbar are declared twice: a desktop base
        rule and a mobile override inside a media query. Reading the first
        match tests the rule that does not apply on a phone - which is how an
        earlier version of this test reported a bug that had already been
        fixed.
        """
        matches = re.findall(
            rf"{re.escape(selector)}\s*\{{[^}}]*?z-index:\s*(\d+)", css, re.S)
        return int(matches[-1]) if matches else None

    rail = z_of(".nav-rail")          # inside the mobile media query
    scrim = z_of(".nav-scrim")
    tabbar = z_of(".bottom-nav")

    check("all three z-indexes are declared",
          None not in (rail, scrim, tabbar), f"rail={rail} scrim={scrim} tab={tabbar}")
    if None not in (rail, scrim, tabbar):
        # This was the bug: rail 40, tab bar 45, so the tab bar rendered over
        # the open drawer and buried the profile row.
        check("the drawer is above the tab bar", rail > tabbar, f"{rail} vs {tabbar}")
        check("the scrim is above the tab bar too", scrim > tabbar, f"{scrim} vs {tabbar}")
        check("the drawer is above its own scrim", rail > scrim, f"{rail} vs {scrim}")


def test_touch_targets():
    print(f"\n{BOLD}6. Touch targets{RESET}")
    css = CSS.read_text()

    check("controls have a 44px minimum on coarse pointers",
          re.search(r"@media \(pointer: coarse\)[\s\S]{0,600}?min-height:\s*44px", css)
          is not None)
    check("the menu button is a 44px surface, not a bare icon",
          re.search(r"\.topbar-menu\s*\{[^}]*width:\s*44px", css, re.S) is not None)
    check("inputs are >=16px so the OS does not zoom on focus",
          re.search(r"input,\s*select,\s*textarea\s*\{\s*font-size:\s*16px", css)
          is not None)
    check("a tap gets a visible press state",
          ":active" in css and "scale(0.97)" in css)


def test_reduced_motion():
    """Animation is a preference, not a decision the app gets to make."""
    print(f"\n{BOLD}7. Motion respects the system setting{RESET}")
    css = CSS.read_text()

    blocks = re.findall(r"@media \(prefers-reduced-motion: reduce\)\s*\{([^@]*)\}", css, re.S)
    check("there is a reduced-motion block", bool(blocks))
    joined = " ".join(blocks)
    for thing in ("animation", "transition"):
        check(f"...it disables {thing}", thing in joined, joined[:200])


def test_phone_layout_decided_in_js():
    """
    Inline styles beat media queries, so phone layout has to be a JS decision.

    This is the lesson from the whole episode: `style={{gridTemplateColumns}}`
    cannot be overridden by any stylesheet rule, at any specificity.
    """
    print(f"\n{BOLD}8. Inline layouts respond in JS{RESET}")

    hook = SRC / "useIsPhone.js"
    check("useIsPhone exists", hook.exists())
    if hook.exists():
        text = hook.read_text()
        check("it listens for changes rather than reading once",
              "addEventListener" in text or "addListener" in text)
        check("...with a fallback for older webviews",
              "addListener" in text and "addEventListener" in text)

    # The components whose inline grids overflowed.
    for name in ("Dashboard.jsx", "SpecialistUI.jsx"):
        text = (SRC / "components" / name).read_text()
        check(f"{name} uses the hook", "useIsPhone" in text)


def main():
    test_no_bare_fr_columns()
    test_autofit_minimums_fit()
    test_overflow_backstop()
    test_fixed_chrome_is_accounted_for()
    test_mobile_rules_are_in_the_mobile_query()
    test_cascade_at_phone_width()
    test_one_breakpoint_not_two()
    test_drawer_stacking()
    test_touch_targets()
    test_reduced_motion()
    test_phone_layout_decided_in_js()

    print(f"\n{BOLD}{GREEN if not failed else RED}"
          f"{passed} passed, {failed} failed{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
