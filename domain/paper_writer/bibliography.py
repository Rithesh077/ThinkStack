"""Turning library documents into a `references.bib` the project can cite.

One `references.bib` per project, which is what makes a project an isolated
session: two papers being written at once do not share a bibliography, and
deleting a project takes its references with it.

── Why the file is the source of truth ──

Keys are computed from metadata, so the same library could produce a different
key for a document after another paper is ingested -- a collision resolved one
way today and the other way tomorrow. That would silently break every
`\\cite{}` already typed into the source.

So the assignment is one-directional: a key already written into
`references.bib` is never recomputed. `assign_keys` reads what is there,
honours it, and only invents keys for documents the file has not seen. The
document id travels in a `thinkstackid` field, which BibTeX styles ignore
because they only read the fields they declare.

── What BibTeX does for free ──

Numbering. `\\cite{vaswani2017attention}` becomes `[3]`, renumbered on every
recompile as citations move, and the reference list is generated in whatever
order the style wants. Tectonic runs BibTeX as part of its own driver, so
nothing here has to schedule the extra passes.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

BIB_FILENAME = "references.bib"

# The field that maps an entry back to the library document it came from.
# Unknown to every .bst, and therefore invisible in the rendered bibliography.
ID_FIELD = "thinkstackid"

_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s}]+)\s*,", re.IGNORECASE)
_ID_FIELD_RE = re.compile(
    rf"{ID_FIELD}\s*=\s*[{{\"]([^}}\"]*)[}}\"]", re.IGNORECASE
)

# Title words that identify nothing. A key built from the first word alone
# gives `smith2019towards` and `smith2019towards a` for two unrelated papers.
_TITLE_STOPWORDS = {
    "a", "an", "the", "on", "in", "of", "for", "to", "and", "or", "with",
    "from", "into", "via", "using", "towards", "toward", "new", "novel",
    "some", "about", "over", "under", "at", "by", "is", "are", "be",
}

# Characters that mean something to TeX and must be escaped before they reach
# the compiler. Backslash is handled separately -- it is the escape character,
# so replacing it after the others would double-escape everything they wrote.
_TEX_ESCAPES = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


@dataclass
class Citable:
    """One library document, as much of it as a bibliography needs."""
    doc_id: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    arxiv_id: str = ""
    doi: str = ""


def _fold(text: str) -> str:
    """`Müller` -> `muller`. Accents are decoration in an identifier."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", stripped.lower())


def _surname(name: str) -> str:
    """The last word of a name, which is the surname often enough to key on.

    Wrong for `Wang Wei` written surname-first and for compound names, and
    that is tolerable: a key is an identifier the author types, not a citation
    the reader sees. What BibTeX prints comes from the author field, where the
    name is passed through untouched and its own von/last parser handles
    `van den Berg` properly.
    """
    parts = name.strip().rstrip(",").split()
    return _fold(parts[-1]) if parts else ""


def _title_word(title: str) -> str:
    """The first title word that carries meaning."""
    for word in re.findall(r"[A-Za-z][A-Za-z0-9-]*", title):
        folded = _fold(word)
        if len(folded) > 2 and folded not in _TITLE_STOPWORDS:
            return folded
    return ""


def bibkey(doc: Citable, taken=()) -> str:
    """The citation key for one document: `vaswani2017attention`.

    Surname of the first author, the year, and the first meaningful word of
    the title -- the convention BibTeX users already have in their fingers,
    which matters because the whole point of a key is that a human types it.

    Every part is optional, because the extractor is honest about what it
    could not find and an empty year is a fact rather than a failure. A
    document with no usable metadata at all still gets a key: `ref`, then
    `refa`, `refb`. Uncitable is worse than ugly.

    Collisions take a letter suffix -- `smith2019bert`, `smith2019berta` --
    which is what BibTeX's own author-year styles do, so it reads as normal.
    """
    surname = _surname(doc.authors[0]) if doc.authors else ""
    year = doc.year.strip() if doc.year else ""
    word = _title_word(doc.title or "")

    stem = f"{surname}{year}{word}" or "ref"

    if stem not in taken:
        return stem
    for suffix in _letter_suffixes():
        candidate = f"{stem}{suffix}"
        if candidate not in taken:
            return candidate
    raise ValueError(f"could not find a free citation key for {stem}")


def _letter_suffixes():
    """`a`..`z`, then `aa`..`zz`. 702 papers sharing one key is not a case."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    yield from letters
    for first in letters:
        for second in letters:
            yield first + second


def escape_tex(text: str) -> str:
    """Make a metadata string safe to paste into a .bib file.

    A title containing `%` comments out the rest of the line and takes the
    closing brace with it, so an unescaped one does not corrupt the entry, it
    corrupts the file.
    """
    out = (text or "").replace("\\", r"\textbackslash{}")
    for char, replacement in _TEX_ESCAPES.items():
        out = out.replace(char, replacement)
    return " ".join(out.split())


def _authors_field(authors: list[str]) -> str:
    """`and`-separated, each name left exactly as extracted.

    BibTeX's own name parser handles `First von Last` and `Last, First`; any
    reordering here would be a guess layered on top of something that already
    works.
    """
    return " and ".join(escape_tex(a.rstrip(",")) for a in authors if a and a.strip())


def to_bibtex(doc: Citable, key: str) -> str:
    """One entry, formatted.

    The title is double-braced. `plain.bst` lowercases titles, which turns
    `BERT` into `bert` in the reference list; the extra braces tell BibTeX the
    capitalisation is the author's and not its to change.
    """
    if doc.arxiv_id:
        kind = "article"
        extra = [("journal", f"arXiv preprint arXiv:{escape_tex(doc.arxiv_id)}")]
    else:
        kind = "misc"
        extra = []

    fields = [
        ("author", _authors_field(doc.authors)),
        ("title", "{" + escape_tex(doc.title) + "}"),
        ("year", escape_tex(doc.year)),
        *extra,
        ("doi", escape_tex(doc.doi)),
        (ID_FIELD, escape_tex(doc.doc_id)),
    ]

    lines = [f"@{kind}{{{key},"]
    lines += [f"  {name:<12} = {{{value}}}," for name, value in fields if value]
    lines.append("}")
    return "\n".join(lines)


def read_bib(project_dir: Path) -> str:
    path = Path(project_dir) / BIB_FILENAME
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_entries(bib_text: str) -> dict[str, str]:
    """`{doc_id: key}` for the entries ThinkStack wrote.

    Entries the author added by hand have no `thinkstackid` and are not in the
    result, but their keys still count as taken -- see `taken_keys`.
    """
    found: dict[str, str] = {}
    for match in _ENTRY_RE.finditer(bib_text):
        key = match.group(2)
        # the entry runs to the start of the next one, or to the end of file
        next_match = _ENTRY_RE.search(bib_text, match.end())
        body = bib_text[match.end(): next_match.start() if next_match else len(bib_text)]
        id_match = _ID_FIELD_RE.search(body)
        if id_match and id_match.group(1).strip():
            found[id_match.group(1).strip()] = key
    return found


def taken_keys(bib_text: str) -> set[str]:
    """Every key in the file, ThinkStack's and the author's alike."""
    return {m.group(2) for m in _ENTRY_RE.finditer(bib_text)}


def assign_keys(docs: list[Citable], bib_text: str = "") -> dict[str, str]:
    """`{doc_id: key}` for every document, honouring the file first.

    Documents are keyed in the order given, so the caller's sort decides who
    wins an unsuffixed key among documents the file has never seen. Anything
    already written keeps what it has regardless.
    """
    existing = parse_entries(bib_text)
    taken = taken_keys(bib_text)

    keys: dict[str, str] = {}
    for doc in docs:
        if doc.doc_id in existing:
            keys[doc.doc_id] = existing[doc.doc_id]
            continue
        key = bibkey(doc, taken)
        taken.add(key)
        keys[doc.doc_id] = key
    return keys


def cite(project_dir: Path, doc: Citable) -> tuple[str, bool]:
    """Make sure `doc` is citable from this project. Returns `(key, added)`.

    Appending rather than rewriting is deliberate: the file is the author's,
    they may have pasted entries into it by hand, and a citation should never
    be the reason those disappear.
    """
    path = Path(project_dir) / BIB_FILENAME
    bib_text = read_bib(project_dir)

    existing = parse_entries(bib_text)
    if doc.doc_id in existing:
        return existing[doc.doc_id], False

    key = bibkey(doc, taken_keys(bib_text))
    entry = to_bibtex(doc, key)

    separator = "" if not bib_text else ("\n" if bib_text.endswith("\n") else "\n\n")
    path.write_text(f"{bib_text}{separator}{entry}\n", encoding="utf-8")
    return key, True
