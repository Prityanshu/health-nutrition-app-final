#!/usr/bin/env python3
"""
Check nutrition lookups against the real databases.

Every number this app shows should be traceable. This script makes that
visible: for each food it prints which source answered, how confident the match
was, what product it actually matched, and the resulting figures - so you can
see at a glance whether a value is label data or a guess.

    python scripts/test_food_lookup.py                 # the standard set
    python scripts/test_food_lookup.py "amul paneer"   # one food
    python scripts/test_food_lookup.py --barcode 8901052001148

Needs a network connection. USDA results only appear if USDA_API_KEY is set
(free from https://fdc.nal.usda.gov/api-key-signup.html); without it the ladder
still works, it just skips that rung.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN, RED, YELLOW, CYAN, DIM, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[2m", "\033[1m", "\033[0m"
)

# Chosen to exercise every rung of the ladder, including the ones that should
# deliberately fail to match.
STANDARD = [
    # (query, what we expect to happen)
    ("amul paneer",              "branded - should hit a product label"),
    ("fru bon low fat paneer",   "branded, specific - label or nothing"),
    ("chicken breast",           "generic - USDA territory"),
    ("brown rice",               "generic - USDA territory"),
    ("banana",                   "generic - USDA territory"),
    ("greek yogurt",             "could go either way"),
    ("maggi noodles",            "branded - product label"),
    ("dal",                      "too vague - expect an estimate"),
    ("homemade rajma",           "homemade - must skip lookups entirely"),
    ("my mum's biryani",         "homemade - must skip lookups entirely"),
    ("vegetarian sandwich",      "composite - expect an estimate"),
]


def show(query, note, barcode=None):
    from app.services import food_lookup

    print(f"\n{BOLD}{query}{RESET}  {DIM}{note}{RESET}")

    try:
        facts = food_lookup.lookup(query, barcode=barcode)
    except Exception as e:
        print(f"  {RED}lookup raised {type(e).__name__}: {e}{RESET}")
        return

    if facts is None:
        print(f"  {YELLOW}no database match{RESET} "
              f"{DIM}→ falls back to an AI estimate, labelled as one{RESET}")
        return

    tick = f"{GREEN}verified{RESET}" if facts.verified else f"{YELLOW}estimate{RESET}"
    confidence_colour = (
        GREEN if facts.confidence >= 0.75
        else YELLOW if facts.confidence >= 0.55
        else RED
    )

    print(f"  {tick}  {CYAN}{facts.source_label}{RESET}")
    print(f"  matched : {facts.matched_name!r}"
          + (f"  {DIM}({facts.brand}){RESET}" if facts.brand else ""))
    print(f"  match   : {confidence_colour}{facts.confidence:.2f}{RESET}")
    print(f"  per {facts.basis:5}: {facts.calories:.0f} kcal · "
          f"P {facts.protein:.1f}g · C {facts.carbohydrates:.1f}g · F {facts.fat:.1f}g"
          + (f" · fibre {facts.fiber:.1f}g" if facts.fiber else ""))
    if facts.source_url:
        print(f"  {DIM}{facts.source_url}{RESET}")

    # The check that matters: does this figure pass a sanity test? Nothing
    # edible has more protein than a protein isolate, and few whole foods
    # exceed ~900 kcal/100g (pure fat is 900).
    warnings = []
    if facts.protein > 45:
        warnings.append(f"protein {facts.protein:.0f}g/100g is implausibly high")
    if facts.calories > 900:
        warnings.append(f"{facts.calories:.0f} kcal/100g exceeds pure fat")
    macro_kcal = facts.protein * 4 + facts.carbohydrates * 4 + facts.fat * 9
    if facts.calories and macro_kcal and abs(macro_kcal - facts.calories) > facts.calories * 0.35:
        warnings.append(
            f"macros imply {macro_kcal:.0f} kcal but the entry says {facts.calories:.0f}"
        )
    for w in warnings:
        print(f"  {RED}⚠ {w}{RESET}")


def raw_off(query):
    """
    Show what Open Food Facts actually returned, and why each was accepted or
    rejected.

    "No match" is ambiguous on its own - it could mean the database has nothing,
    or that everything it had was correctly thrown out. Those need different
    fixes, so this makes the difference visible.
    """
    import requests
    from app.services import food_lookup as fl

    print(f"\n{BOLD}Raw Open Food Facts results for {query!r}{RESET}")
    try:
        response = requests.get(
            fl.OFF_SEARCH_URL,
            params={
                "search_terms": query, "search_simple": 1,
                "action": "process", "json": 1, "page_size": 12,
            },
            headers={"User-Agent": fl.USER_AGENT},
            timeout=15,
        )
    except Exception as e:
        print(f"  {RED}request failed: {type(e).__name__}: {e}{RESET}")
        return

    if not response.ok:
        print(f"  {RED}HTTP {response.status_code}{RESET}")
        return

    payload = response.json()
    products = payload.get("products", []) or []
    print(f"  {DIM}{payload.get('count', 0)} total hits, showing {len(products)}{RESET}\n")

    if not products:
        print(f"  {YELLOW}The database genuinely has nothing for this term.{RESET}")
        return

    for product in products:
        name = product.get("product_name") or "(no name)"
        brand = (product.get("brands") or "").split(",")[0].strip()
        nutriments = product.get("nutriments") or {}
        kcal = nutriments.get("energy-kcal_100g")

        score = fl.match_score(query, name, brand)
        reasons = []
        if not kcal:
            reasons.append("no calorie data")
        if fl.introduces_different_food(query, name):
            reasons.append("different kind of food")
        if score < fl.OFF_MIN_SCORE:
            reasons.append(f"score {score:.2f} < {fl.OFF_MIN_SCORE}")
        if kcal:
            p = nutriments.get("proteins_100g") or 0
            c = nutriments.get("carbohydrates_100g") or 0
            f = nutriments.get("fat_100g") or 0
            if not fl.macros_are_consistent(float(kcal), float(p), float(c), float(f)):
                reasons.append("macros contradict the calories")

        mark = f"{RED}reject{RESET}" if reasons else f"{GREEN}ACCEPT{RESET}"
        print(f"  [{mark}] {score:.2f}  {name!r}" + (f" {DIM}({brand}){RESET}" if brand else ""))
        if kcal:
            print(f"           {DIM}{float(kcal):.0f} kcal/100g{RESET}")
        if reasons:
            print(f"           {DIM}→ {'; '.join(reasons)}{RESET}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("food", nargs="*", help="food to look up (default: the standard set)")
    ap.add_argument("--barcode", help="look up an exact product by barcode")
    ap.add_argument("--raw", action="store_true",
                    help="show every candidate the database returned and why it was rejected")
    args = ap.parse_args()

    if args.raw:
        for query in ([" ".join(args.food)] if args.food
                      else ["amul paneer", "maggi noodles", "brown rice"]):
            raw_off(query)
        print()
        return 0

    print(f"\n{BOLD}Food lookup{RESET}")
    if os.getenv("USDA_API_KEY", "").strip():
        print(f"{DIM}USDA key present - generic foods will use FoodData Central.{RESET}")
    else:
        print(f"{YELLOW}No USDA_API_KEY set{RESET} {DIM}- generic foods will fall through "
              f"to estimates.\n  Free key: https://fdc.nal.usda.gov/api-key-signup.html{RESET}")

    if args.barcode:
        show(" ".join(args.food) or "barcode lookup", "exact product", barcode=args.barcode)
    elif args.food:
        show(" ".join(args.food), "requested")
    else:
        for query, note in STANDARD:
            show(query, note)

    print(f"\n{DIM}'verified' means the numbers came from a product label or a government")
    print(f"food table. 'no database match' means the app will estimate and say so.{RESET}\n")


if __name__ == "__main__":
    sys.exit(main() or 0)
