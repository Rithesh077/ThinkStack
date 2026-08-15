#!/bin/bash
# thinkstack: rebuild the landing page's self-hosted fonts.
#
# The page used to pull three families in nine weights from
# fonts.googleapis.com with a <link rel="stylesheet"> in <head>. That is
# RENDER-BLOCKING -- the browser paints nothing until Google answers -- so on
# any network where Google is slow or filtered, the page sat blank while its
# own HTML had arrived in about 200 ms.
#
# It also contradicted the product: an application whose premise is that
# nothing leaves your machine had a download page that could not draw itself
# without contacting Google.
#
# Two things worth knowing before changing this:
#
#   * Inter and Outfit are VARIABLE fonts. Google serves ONE file per family
#     covering every weight, so the nine URLs in the old stylesheet were nine
#     references to three files. One @font-face with `font-weight: 100 900` is
#     the correct declaration, not one per weight.
#
#   * The fonts are SUBSET to the characters the page actually renders. That is
#     what takes them from 364 KB to 44 KB. Add prose in a new script and the
#     glyphs are still covered (the subset is all of printable ASCII plus the
#     punctuation in use), but add another language and they will not be.
#
# usage: scripts/fetch-landing-fonts.sh [dest]     (default: assets/fonts)
set -euo pipefail

cd "$(dirname "$0")/.."

DEST="${1:-assets/fonts}"
GREEN='\033[0;32m'; NC='\033[0m'

python3 - "$DEST" <<'PY'
import pathlib, re, subprocess, sys, urllib.request

dest = pathlib.Path(sys.argv[1])
dest.mkdir(parents=True, exist_ok=True)

# A woff2-capable UA, or Google serves ttf.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")

# Printable ASCII plus the marks the page uses. Deliberately wider than what is
# on the page today so ordinary copy edits do not silently lose a glyph.
CHARS = "".join(chr(c) for c in range(0x20, 0x7f)) + "—–‘’“”…·●→✓×"

FAMILIES = {
    # family:   (google spec,        output file,        variable?)
    "Inter":    ("Inter:wght@100..900",  "inter-var.woff2",  True),
    "Outfit":   ("Outfit:wght@100..900", "outfit-var.woff2", True),
    "Caveat":   ("Caveat:wght@700",      "caveat-700.woff2", False),
}

chars_file = dest / ".subset-chars.txt"
chars_file.write_text(CHARS, encoding="utf-8")

total = 0
try:
    for family, (spec, out, variable) in FAMILIES.items():
        url = f"https://fonts.googleapis.com/css2?family={spec}&display=swap"
        css = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60
        ).read().decode()

        # the latin subset only; the page is English
        block = None
        for m in re.finditer(r"/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{(.*?)\}", css, re.S):
            if m.group(1) == "latin":
                block = m.group(2)
                break
        if block is None:
            raise SystemExit(f"no latin subset for {family}")

        src_url = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
        raw = dest / f".{family}.orig.woff2"
        raw.write_bytes(urllib.request.urlopen(
            urllib.request.Request(src_url, headers={"User-Agent": UA}), timeout=60).read())

        target = dest / out
        subprocess.run([
            sys.executable, "-m", "fontTools.subset", str(raw),
            f"--text-file={chars_file}", "--flavor=woff2",
            "--no-hinting", "--desubroutinize", "--layout-features=",
            "--drop-tables+=GSUB,GPOS,GDEF,DSIG,MATH,BASE,JSTF",
            f"--output-file={target}",
        ], check=True, capture_output=True)
        raw.unlink()

        # A dropped fvar table turns every weight into one, and the page would
        # render its headings at the wrong weight with nothing reporting it.
        if variable:
            from fontTools.ttLib import TTFont
            if "fvar" not in TTFont(target):
                raise SystemExit(f"{out} lost its variable axes -- check the subset flags")

        total += target.stat().st_size
        print(f"  {family:8} -> {out:18} {target.stat().st_size // 1024:>3} KB")
finally:
    chars_file.unlink(missing_ok=True)

print(f"\n  {total // 1024} KB total, served from this origin")
PY

echo -e "  ${GREEN}done${NC} - fonts in ${DEST}/"
