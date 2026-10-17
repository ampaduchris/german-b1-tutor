"""Render docs/og.png, the 1200x630 link-preview image for the Pages walkthrough.

Run:  uv run --with pillow scripts/make_og_image.py

Pillow is pulled in for this one run rather than added to the project, so the
spec's "external dependency count: 2" stays literally true. The image reuses
the walkthrough's own headline and palette, including its colour semantics:
teal is a plain function, purple is a model call. Fonts are fetched from a
pinned google/fonts commit (all three are SIL OFL), so a re-run reproduces the
same file rather than whatever the font repository looks like that day.
"""

import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "docs" / "og.png"
W, H = 1200, 630

FONTS_COMMIT = "47d54ca1ebb14fd864695f1d39dc734f39017c33"
FONT_URLS = {
    "display": "ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf",
    "body": "ofl/sourceserif4/SourceSerif4%5Bopsz%2Cwght%5D.ttf",
    "mono": "ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
}

# docs/explainer.html :root
PAPER, INK, INK2, RULE = "#F4F4EF", "#15181C", "#5A6069", "#D6D6CB"
FN, LLM = "#165C56", "#5B45A0"


def font(path: Path, size: int, **axes: float) -> ImageFont.FreeTypeFont:
    """Load a variable font at `size`, setting named axes (wght, wdth, opsz)."""
    f = ImageFont.truetype(str(path), size)
    names = [a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
             for a in f.get_variation_axes()]
    current = {"Weight": 400, "Width": 100, "Optical size": size}
    lookup = {"Weight": "wght", "Width": "wdth", "Optical size": "opsz"}
    f.set_variation_by_axes([axes.get(lookup.get(n, n), current.get(n, 400)) for n in names])
    return f


def main() -> None:
    cache = Path(tempfile.mkdtemp(prefix="og-fonts-"))
    paths = {}
    for key, rel in FONT_URLS.items():
        paths[key] = cache / f"{key}.ttf"
        url = f"https://raw.githubusercontent.com/google/fonts/{FONTS_COMMIT}/{rel}"
        urllib.request.urlretrieve(url, paths[key])

    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    x = 80

    eyebrow = font(paths["display"], 22, wght=700)
    d.text((x, 92), "A2 → B1  ·  GOETHE-ZERTIFIKAT  ·  V1 ARCHITECTURE", font=eyebrow, fill=FN)

    # 76 px leaves a safe right margin; some sites crop large previews slightly.
    head = font(paths["display"], 76, wght=850, wdth=100)
    y = 140
    d.text((x, y), "Two thirds of this agent is", font=head, fill=INK)
    y += 88
    d.text((x, y), "not an agent", font=head, fill=LLM)
    d.text((x + d.textlength("not an agent", font=head), y), ".", font=head, fill=INK)

    # One sentence per line, broken where the meaning breaks.
    lede = font(paths["body"], 32, wght=400, opsz=24)
    y += 124
    for line in ("One model call decides what is wrong with your German.",
                 "Everything after that is file writes and arithmetic."):
        d.text((x, y), line, font=lede, fill=INK2)
        y += 46

    d.line([(x, 524), (W - x, 524)], fill=RULE, width=2)
    mono = font(paths["mono"], 22, wght=500)
    d.text((x, 546), "github.com/ampaduchris/german-b1-tutor", font=mono, fill=INK2)

    legend = [("model call", LLM), ("plain function", FN)]
    lx = W - x
    for label, colour in legend:
        lx -= d.textlength(label, font=mono)
        d.text((lx, 546), label, font=mono, fill=INK2)
        lx -= 30
        d.rounded_rectangle([lx, 551, lx + 18, 569], radius=4, fill=colour)
        lx -= 34

    img.save(OUT, optimize=True)
    print(f"wrote {OUT.relative_to(OUT.parent.parent)} ({W}x{H}, {OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
