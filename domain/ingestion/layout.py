"""Page geometry: spans in, rows of cells out. Knows nothing about papers.

Four facts about how PDFs store text. Each one caused a bug:

    no lines, no words      only glyph runs at coordinates
    two sizes on one line   share a baseline, not a bbox top
    font change mid-word    two runs, zero gap between them
    a wide gap              a new entry; a narrow one is a space

What a title or an author is belongs to `layout_metadata`, not here.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from domain.ingestion.models import PageLayout, TextSpan

# Gap/font-size ratios. Measured over 18 published papers:
#   word space      ~0.25   the space between "Ashish" and "Vaswani"
#   entry divider    0.59   tightest real one, llama2's 68 justified authors
COLUMN_GAP = 0.45
WORD_GAP = 0.12

# TeX writes an accent as its own glyph, BEFORE its letter: "Dollár" is stored
# "Doll" + U+00B4 + "ar". Unicode wants it after, and combining, or NFC cannot
# compose it.
_LOOSE_ACCENTS = {
    "´": "́", "ˊ": "́",
    "`": "̀", "ˋ": "̀",
    "ˆ": "̂", "^": "̂",
    "˜": "̃", "~": "̃",
    "¨": "̈",
    "ˇ": "̌",
    "˘": "̆",
    "¸": "̧",
}
# Leading \s* is required: NFKC expands U+00B4 to space + U+0301.
_ACCENT_BEFORE_LETTER = re.compile(
    r"\s*([" + "".join(_LOOSE_ACCENTS) + "̀-ͯ])" + r"\s*([^\W\d_])"
)


def normalise(text: str) -> str:
    """Ligatures expanded, accents reattached.

        NFKC     "Efficient" is the single glyph U+FB01
        accents  "Doll" + loose acute + "ar" prints as "Doll ´ar"
        NFC      recomposes what the first two leave apart

    Skip it and both reach the search index in that state.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _ACCENT_BEFORE_LETTER.sub(
        lambda m: m.group(2) + _LOOSE_ACCENTS.get(m.group(1), m.group(1)), text
    )
    return unicodedata.normalize("NFC", text)


@dataclass
class Cell:
    """One entry on a row: a name, a heading, a column of body text."""
    text: str = ""
    x0: float = 0.0
    x1: float = 0.0


@dataclass
class Row:
    """One typeset line, divided at its column gaps.

    PyMuPDF reports resnet's four-column author row as ONE line. As text that
    is an eight-word phrase; as positions it is four names. No filter
    downstream can undo the merge.
    """
    baseline: float = 0.0
    size: float = 0.0
    cells: list[Cell] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(c.text for c in self.cells)

    @property
    def x0(self) -> float:
        return min((c.x0 for c in self.cells), default=0.0)


def _join(spans: list[TextSpan], size: float) -> list[Cell]:
    """Merge spans left to right, breaking at column gaps."""
    cells: list[Cell] = []
    text, x0, prev_x1 = "", 0.0, None

    for span in spans:
        if prev_x1 is None:
            text, x0 = span.text, span.x0
        elif span.x0 - prev_x1 > size * COLUMN_GAP:
            cells.append(Cell(text, x0, prev_x1))
            text, x0 = span.text, span.x0
        else:
            # No gap means one word split by a font change: "A"+"DAM",
            # "Doll"+accent+"ar". A space here gives "A DAM", and strands the
            # accent from the letter NFC would have composed it with.
            glued = (text.endswith(" ") or span.text.startswith(" ")
                     or span.x0 - prev_x1 < size * WORD_GAP)
            text += ("" if glued else " ") + span.text
        prev_x1 = span.x1

    if prev_x1 is not None:
        cells.append(Cell(text, x0, prev_x1))

    for cell in cells:
        cell.text = re.sub(r"\s+", " ", normalise(cell.text)).strip()
    return [c for c in cells if c.text]


def rows(spans: list[TextSpan]) -> list[Row]:
    """Spans grouped by baseline, top to bottom, each row split into cells.

    Baseline, not bbox top. Small caps are one line in two sizes -- "A" 17.2pt
    beside "DAM" 13.8pt -- and their tops differ. Grouped by top, adam's title
    came out `A : A M S O`.
    """
    by_baseline: dict[int, list[TextSpan]] = {}
    for span in spans:
        by_baseline.setdefault(round(span.baseline or span.y0), []).append(span)

    out = []
    for baseline in sorted(by_baseline):
        ordered = sorted(by_baseline[baseline], key=lambda s: s.x0)
        size = max(s.size for s in ordered)
        cells = _join(ordered, size)
        if cells:
            out.append(Row(baseline=float(baseline), size=size, cells=cells))
    return out


def content_rows(page: PageLayout, margin_fraction: float) -> list[Row]:
    """Horizontal rows outside the left margin.

    arXiv stamps its id down the margin, rotated, at 20pt -- larger than
    attention.pdf's 17.2pt title. Either test removes it; both are kept
    because horizontal margin stamps exist too.
    """
    margin = page.width * margin_fraction
    return rows([s for s in page.spans if s.horizontal and s.x0 >= margin])
