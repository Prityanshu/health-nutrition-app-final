#!/usr/bin/env python3
"""
Generate every launcher icon and favicon from the Kayosha logo.

WHY THIS IS A SCRIPT AND NOT A FOLDER OF PNGS
---------------------------------------------
Android wants the same icon at five densities, plus a foreground layer for
adaptive icons, plus a round variant; the web wants a favicon, an
apple-touch-icon and two PWA sizes. That is nineteen files which must all be
the same drawing. Exported by hand they drift - someone tweaks the artwork,
updates four of them, and the app ends up with two subtly different logos
depending on which launcher grid you happen to look at.

Everything here derives from ONE source file:

    frontend/src/assets/kayosha-icon-1024.png

which is the real logo artwork, not a redrawing of it. Replace that file and
re-run; nothing else needs touching.

    python scripts/make_icons.py

Requires Pillow and nothing else - no SVG renderer, no ImageMagick delegates.
Those are precisely the dependencies that turn out to be missing on whichever
machine you next try this on.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "frontend" / "src" / "assets" / "kayosha-icon-1024.png"
MARK = ROOT / "frontend" / "src" / "assets" / "kayosha-mark.png"
ANDROID_RES = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"
PUBLIC = ROOT / "frontend" / "public"

try:
    from PIL import Image
except ImportError:
    print("Pillow is needed:  pip install Pillow")
    sys.exit(1)

GREEN, RED, DIM, BOLD, RESET = "\033[92m", "\033[91m", "\033[2m", "\033[1m", "\033[0m"

# The logo's own background, so the icon matches the artwork rather than the
# app chrome - a launcher icon is seen next to other icons, not next to the app.
BACKDROP = (26, 20, 48, 255)

# density bucket -> launcher icon size in px
MIPMAPS = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def square_icon(size):
    """The logo on its backdrop, filling a square."""
    base = Image.open(SOURCE).convert("RGBA")
    return base.resize((size, size), Image.LANCZOS)


def adaptive_foreground(size, coverage=0.60):
    """
    The mark alone on transparency, for Android's adaptive icons.

    The launcher masks this to a circle, squircle or whatever the device
    prefers, and only the central 66dp of the 108dp canvas is guaranteed to
    survive - about 61%. Anything outside that can be cropped, so the mark is
    scaled to sit inside it. An earlier attempt used a 40% coverage and the
    lotus looked lost in the middle of its own tile.
    """
    mark = Image.open(MARK).convert("RGBA")
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    target = int(size * coverage)
    scale = target / max(mark.size)
    resized = mark.resize(
        (max(1, int(mark.width * scale)), max(1, int(mark.height * scale))),
        Image.LANCZOS,
    )
    canvas.alpha_composite(
        resized, ((size - resized.width) // 2, (size - resized.height) // 2)
    )
    return canvas


def main() -> int:
    for path in (SOURCE, MARK):
        if not path.exists():
            print(f"{RED}Missing {path.relative_to(ROOT)}{RESET}")
            print("This script derives everything from the logo artwork; put it back.")
            return 1

    written = []

    if ANDROID_RES.is_dir():
        for bucket, px in MIPMAPS.items():
            folder = ANDROID_RES / f"mipmap-{bucket}"
            folder.mkdir(parents=True, exist_ok=True)

            icon = square_icon(px)
            icon.save(folder / "ic_launcher.png")
            icon.save(folder / "ic_launcher_round.png")
            adaptive_foreground(px * 2).save(folder / "ic_launcher_foreground.png")
            written += [
                folder / "ic_launcher.png",
                folder / "ic_launcher_round.png",
                folder / "ic_launcher_foreground.png",
            ]
    else:
        print(f"{DIM}No android res folder - skipping launcher icons.{RESET}")

    if PUBLIC.is_dir():
        square_icon(64).save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (64, 64)])
        square_icon(192).save(PUBLIC / "logo192.png")
        square_icon(512).save(PUBLIC / "logo512.png")
        square_icon(180).save(PUBLIC / "apple-touch-icon.png")
        written += [
            PUBLIC / "favicon.ico", PUBLIC / "logo192.png",
            PUBLIC / "logo512.png", PUBLIC / "apple-touch-icon.png",
        ]

    print(f"{GREEN}Wrote {len(written)} files{RESET} from "
          f"{DIM}{SOURCE.relative_to(ROOT)}{RESET}")
    print()
    print(f"{BOLD}Android needs a sync to pick these up:{RESET}")
    print("  cd frontend && npx cap sync android")
    return 0


if __name__ == "__main__":
    sys.exit(main())
