"""Title and authors, read from page geometry.

A PDF has no title field -- 18 papers checked, all carry only a creation date.
It has glyphs with sizes and positions, and the title is the biggest text at
the top of page 1 with the authors directly under it.

Every judgement is a named rule in NAME_RULES or ROW_RULES. One traversal,
`walk()`, returns the answer and the reasons together, so the demo shows what
actually ran rather than a second copy of it.

Pure functions over `PageLayout`; tests build spans by hand.
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from domain.ingestion.layout import Row, content_rows
from domain.ingestion.models import PageLayout

# Left of this is margin furniture. Kept small on purpose: rotation already
# excludes the arXiv stamp, and a centred title's first line is its widest, so
# 0.08 was cutting the top line off titles that start at x0=43.8 on a 595pt page.
MARGIN_FRACTION = 0.04
TITLE_ZONE = 0.45        # below this, the biggest text is a section heading
SIZE_TOLERANCE = 0.6     # points; within it, one visual block
AUTHOR_ZONE = 0.6        # below this, body text -- backstop when "Abstract" is absent
PROSE_WORDS = 12         # a nameless row this long, after the authors, is the abstract

# Words that make a ROW an affiliation. Structural only: what an institution's
# name is BUILT from, never an employer's name. Google/Tsinghua/Mistral is an
# endless list that dates, and the row is identifiable without it.
AFFILIATION_WORDS = {
    "university", "universite", "universität", "universidad", "universita",
    "institute", "institut", "college", "school", "department", "dept",
    "faculty", "laboratory", "laboratories", "lab", "labs", "research",
    "center", "centre", "academy", "academia", "hospital", "clinic",
    "corporation", "corp", "inc", "ltd", "gmbh", "llc",
}

# Footnote markers that glue onto a surname: "Ashish Vaswani∗".
FOOTNOTE_MARKERS = "*∗†‡§¶#0123456789,;. "

# What divides two names inside one cell. Note the absence of ".": "Aidan N.
# Gomez" and "Quoc V. Le" carry an initial mid-name.
NAME_SEPARATOR = re.compile(r",|;|·|\||\band\b|&", re.IGNORECASE)

_WORDS = re.compile(r"[^\W\d_]+")


def _not_an_acronym(name: str) -> bool:
    """A short all-caps token beside ordinary words is an acronym.

    Acronyms are institutions: "Google AI Language", "MIT CSAIL", "NAVER Labs".
    This is what replaces naming employers.

    Only applies to mixed-case text. A wholly capitalised candidate is a
    typesetting choice, not an abbreviation -- acmart sets every byline that
    way, and "ANDREW CHU" was being read as an acronym.
    """
    if name.isupper():
        return True
    tokens = name.split()
    acronyms = [t for t in tokens if t.isalpha() and t.isupper() and 2 <= len(t) <= 4]
    return not acronyms or len(acronyms) == len(tokens)


def _name_shaped(name: str) -> bool:
    """Two to four parts, each capitalised or a particle like "van" / "de"."""
    words = _WORDS.findall(name)
    return 1 < len(words) <= 4 and all(w[0].isupper() or len(w) <= 3 for w in words)


# Orthography only, no vocabulary. The last three came from running it, not
# from reasoning: bert writes emails as {a,b,c}@google.com, so splitting on
# commas leaves the cells "{", "}", and a run of usernames with no "@" left in
# it to give itself away.
NAME_RULES: list[tuple[str, object]] = [
    ("too short or too long", lambda n: 3 < len(n) < 50),
    ("is an address", lambda n: "@" not in n),
    ("contains digits", lambda n: not any(c.isdigit() for c in n)),
    ("no letters", lambda n: bool(_WORDS.search(n))),
    ("single word", lambda n: " " in n),
    ("not capitalised", lambda n: n[:1].isupper()),
    ("acronym -- an institution", _not_an_acronym),
    ("not shaped like a name", _name_shaped),
]


def clean_name(candidate: str) -> str:
    return re.sub(r"\s+", " ", candidate.strip().strip(FOOTNOTE_MARKERS)).strip()


def name_rejection(candidate: str) -> str | None:
    """The first rule the candidate fails, or None if it passes them all."""
    name = clean_name(candidate)
    for reason, rule in NAME_RULES:
        if not rule(name):
            return reason
    return None


def looks_like_name(candidate: str) -> bool:
    return name_rejection(candidate) is None


def _fold(word: str) -> str:
    """Accents removed, so one spelling matches all of them.

    The list holds "universite"; the page says "Université", and gan's
    affiliation reached the author list because those are different strings.
    """
    return "".join(c for c in unicodedata.normalize("NFD", word)
                   if not unicodedata.combining(c))


def _names_an_institution(text: str) -> bool:
    # Tried and reverted: treating a bare acronym ("IEEE") as an institution
    # too. It fixes "Wang, Senior Member, IEEE" and costs more elsewhere --
    # 85.7% -> 83.9% exact author lists over the 56-paper sample.
    return any(_fold(w) in AFFILIATION_WORDS for w in _WORDS.findall(text.lower()))


def _parts(cell_text: str) -> list[str]:
    return [p for p in (clean_name(p) for p in NAME_SEPARATOR.split(cell_text)) if p]


def _is_byline(parts: list[str]) -> bool:
    """`NAME, Institution, Country` -- one author per row, ACM style.

    The first part must be a person. Without that test mamba's affiliation
    row, "Machine Learning Department, Department of Computer Science", reads
    as a byline and the department becomes the author.
    """
    return (len(parts) > 1
            and looks_like_name(parts[0])
            and not _names_an_institution(parts[0])
            and any(_names_an_institution(p) for p in parts[1:]))


def _names_among(texts: list[str]) -> list[str]:
    found = []
    for text in texts:
        parts = _parts(text)
        if _is_byline(parts):
            found.append(parts[0])
            continue
        found.extend(p for p in parts
                     if looks_like_name(p) and not _names_an_institution(p))
    return found


def _names_in(row: Row) -> list[str]:
    """Every name on a row, whichever way that row separates them.

        Name | Name | Name        columns             resnet, llama2
        Name, Name, Name          one centred cell    ieee_a
        NAME, Institution, USA    one per row         acmart
        Name and Name             wide word spacing   RevTeX

    The last one is why both readings are tried. RevTeX sets a centred author
    line with spacing wide enough to look like columns, so "Roo Dunnill and
    Mina Doosti" arrives as five cells and no cell is a name. Read as one
    string it splits on "and" into two. Whichever finds more names wins, and
    no gap threshold has to be right for every template.
    """
    by_cell = _names_among([c.text for c in row.cells])
    by_line = _names_among([row.text])
    return by_line if len(by_line) > len(by_cell) else by_cell


def _is_affiliation(row: Row) -> bool:
    """A row of nothing but institutions.

    attention.pdf's is "Google Brain | Google Brain | Google Research | Google
    Research". Only two cells carry a listed word -- "Brain" is not in the
    list and never will be -- so the row has to be judged whole.

    Except when a cell is a byline, where name and institution share the row
    on purpose. Condemning those loses the author, which is how acmart papers
    came back with one author out of four.
    """
    if any(_is_byline(_parts(c.text)) for c in row.cells):
        return False
    return _names_an_institution(row.text)


ROW_RULES: list[tuple[str, object]] = [
    ("names an institution", _is_affiliation),
]


def row_rejection(row: Row) -> str | None:
    for reason, rule in ROW_RULES:
        if rule(row):
            return reason
    return None


@dataclass
class Title:
    text: str = ""
    baseline: float = 0.0          # of its last line; the author band starts below
    size: float = 0.0


def title_block(page: PageLayout) -> Title:
    """The largest horizontal text in the top of page 1.

    An empty result is the honest answer for a scanned page, and the signal
    for the caller to try something else.
    """
    zone = [r for r in content_rows(page, MARGIN_FRACTION)
            if r.baseline <= page.height * TITLE_ZONE]
    if not zone:
        return Title()

    biggest = max(r.size for r in zone)
    lines = [r for r in zone if r.size >= biggest - SIZE_TOLERANCE]
    if not lines:
        return Title()

    # A wrapped title continues on the next line; the same font reused further
    # down the page is a section heading. Consecutive baselines sit about one
    # font size apart.
    kept = [lines[0]]
    for row in lines[1:]:
        if row.baseline - kept[-1].baseline > biggest * 2.5:
            break
        kept.append(row)

    text = ""
    for row in kept:
        # LaTeX hyphenates across a line break: lora's title wraps as
        # "LARGE LAN-" / "GUAGE MODELS". Joined with a space that becomes
        # "LAN- GUAGE" in the stored title and in every search for it.
        if text.endswith("-"):
            text = text[:-1] + row.text
        else:
            text = f"{text} {row.text}" if text else row.text

    return Title(re.sub(r"\s+", " ", text).strip(), kept[-1].baseline, biggest)


def title_from_layout(page: PageLayout) -> str:
    return title_block(page).text


@dataclass
class RowTrace:
    """What the extractor decided about one row, and why."""
    row: Row
    role: str                       # title | authors | skipped | stop | body
    reason: str = ""
    names: list[str] = field(default_factory=list)


def walk(page: PageLayout) -> list[RowTrace]:
    """Every row of page 1, labelled with the decision made about it.

    The single traversal behind both `authors_from_layout` and the demo. Two
    implementations would drift, and the one being looked at would stop being
    the one that runs.
    """
    title = title_block(page)
    trace: list[RowTrace] = []
    band_size: float | None = None
    stopped = False

    for row in content_rows(page, MARGIN_FRACTION):
        if row.baseline <= title.baseline:
            is_title = bool(title.text) and row.size >= title.size - SIZE_TOLERANCE
            trace.append(RowTrace(row, "title" if is_title else "skipped",
                                  "" if is_title else "smaller than the title"))
            continue
        if stopped:
            trace.append(RowTrace(row, "body", "past the abstract"))
            continue
        if re.match(r"^abstract\b", row.text.lower()):
            stopped = True
            trace.append(RowTrace(row, "stop", "the abstract begins"))
            continue
        if row.baseline > page.height * AUTHOR_ZONE:
            stopped = True
            trace.append(RowTrace(row, "stop", "too far down to be an author"))
            continue

        reason = row_rejection(row)
        if reason:
            trace.append(RowTrace(row, "skipped", reason))
            continue

        names = _names_in(row)
        if not names:
            # Prose after the authors is the abstract, whether or not the word
            # is printed. RevTeX and APS templates run straight from the
            # affiliations into the text, so waiting for an "Abstract" heading
            # meant scanning down into the section headings and collecting
            # "I. Introduction" as an author.
            if band_size is not None and len(row.text.split()) > PROSE_WORDS:
                stopped = True
                trace.append(RowTrace(row, "stop", "prose -- the abstract, unlabelled"))
            else:
                trace.append(RowTrace(row, "skipped", "no cell is shaped like a name"))
            continue

        # The author row sets the size; a later row at another size is prose.
        if band_size is None:
            band_size = row.size
        elif abs(row.size - band_size) > SIZE_TOLERANCE:
            trace.append(RowTrace(row, "skipped",
                                  f"{row.size}pt, not the {band_size}pt author band"))
            continue

        trace.append(RowTrace(row, "authors", names=names))

    return _drop_repeats(trace)


def _drop_repeats(trace: list[RowTrace]) -> list[RowTrace]:
    """A phrase appearing twice in the author band is not a person.

    Orthography cannot separate "United Kingdom" from "Kaiming He" -- both are
    two capitalised words -- but a shared address is printed once per author
    and a name is printed once per paper. No vocabulary needed, and no list of
    countries to keep up to date.
    """
    seen = Counter(n for step in trace for n in step.names)
    repeated = {n for n, count in seen.items() if count > 1}
    if not repeated:
        return trace

    for step in trace:
        if not step.names:
            continue
        kept = [n for n in step.names if n not in repeated]
        if not kept:
            step.role, step.reason = "skipped", "repeats -- an address, not a person"
        step.names = kept
    return trace


def authors_from_layout(page: PageLayout, limit: int = 60) -> list[str]:
    """Author names, in reading order, without duplicates."""
    authors: list[str] = []
    for step in walk(page):
        for name in step.names:
            if name not in authors:
                authors.append(name)
    return authors[:limit]


def layout_digest(page: PageLayout, limit: int = 30) -> str:
    """Page 1 as `<font size> | <row text>` lines, for a prompt.

    A model handed the flat text of attention.pdf reads Google's licence
    notice first and answers with it -- the same trap the regex fell into,
    because it is the same evidence. Font size is what makes a title
    identifiable, so a model asked to find one should be shown it.
    """
    return "\n".join(
        f"{r.size:>5.1f} | {r.text[:120]}"
        for r in content_rows(page, MARGIN_FRACTION)[:limit]
    )
