"""citation keys, BibTeX entries, and the author list that survives the store.

Two failures are worth more than the rest here, and both are silent.

The first is the comma. `", ".join(authors)` is the obvious way to put a list
into a store that only holds strings, and in BibTeX the comma is syntax --
`Vaswani, Ashish and Shazeer, Noam` is two people. Round-tripping through the
old encoding turned eight authors into sixteen half-names, and a bibliography
does not raise, it just prints them.

The second is key stability. A key is written into the author's source the
moment they cite something; recomputing it later against a library that has
since grown would break every `\\cite` already typed. So the file wins.
"""

from __future__ import annotations

import pytest

from domain.knowledge_base.author_codec import (
    authors_display, decode_authors, encode_authors,
)
from domain.paper_writer import bibliography as B
from domain.paper_writer.bibliography import Citable


VASWANI = Citable(
    doc_id="d1",
    title="Attention Is All You Need",
    authors=["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
    year="2017",
    arxiv_id="1706.03762",
)
DEVLIN = Citable(
    doc_id="d2",
    title="BERT: Pre-training of Deep Bidirectional Transformers",
    authors=["Jacob Devlin", "Ming-Wei Chang"],
    year="2019",
)


# ────────────────────────── the author codec ──────────────────────────

def test_authors_round_trip_keeps_the_boundaries():
    names = ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"]
    assert decode_authors(encode_authors(names)) == names


def test_a_surname_first_name_is_not_split_in_two():
    """The bug the codec exists for: one person, not two."""
    assert decode_authors(encode_authors(["Vaswani, Ashish"])) == ["Vaswani, Ashish"]


def test_legacy_comma_rows_still_read():
    """Documents ingested before this change are stored comma-joined."""
    assert decode_authors("Ashish Vaswani, Noam Shazeer") == ["Ashish Vaswani", "Noam Shazeer"]


def test_empty_stays_empty():
    assert encode_authors([]) == ""
    assert decode_authors("") == []
    assert decode_authors(None) == []


def test_blank_names_are_dropped_not_stored():
    assert decode_authors(encode_authors(["Ada Lovelace", "  ", ""])) == ["Ada Lovelace"]


def test_display_is_one_line():
    assert authors_display(encode_authors(["A B", "C D"])) == "A B, C D"


def test_a_corrupt_value_reads_as_written_rather_than_raising():
    """A store row is not trusted input; a broken one must not 500 the library."""
    assert decode_authors("[not json") == ["[not json"]


# ──────────────────────────── citation keys ────────────────────────────

def test_the_key_is_surname_year_and_the_first_real_title_word():
    assert B.bibkey(VASWANI) == "vaswani2017attention"


def test_stopwords_are_skipped_so_the_key_identifies_something():
    doc = Citable("x", "Towards a Theory of Everything", ["Jane Smith"], "2019")
    assert B.bibkey(doc) == "smith2019theory"


def test_accents_are_folded_because_a_key_gets_typed():
    doc = Citable("x", "Deep Learning", ["Jürgen Müller"], "2020")
    assert B.bibkey(doc) == "muller2020deep"


def test_a_missing_year_just_leaves_it_out():
    doc = Citable("x", "Deep Learning", ["Jane Smith"], "")
    assert B.bibkey(doc) == "smithdeep"


def test_a_document_with_no_metadata_is_still_citable():
    assert B.bibkey(Citable("x")) == "ref"


def test_collisions_take_a_letter_the_way_bibtex_does():
    doc = Citable("x", "Deep Learning", ["Jane Smith"], "2019")
    assert B.bibkey(doc, taken={"smith2019deep"}) == "smith2019deepa"
    assert B.bibkey(doc, taken={"smith2019deep", "smith2019deepa"}) == "smith2019deepb"


# ───────────────────────────── the entry ─────────────────────────────

def test_authors_are_and_separated_and_otherwise_untouched():
    """BibTeX's own parser handles `van den Berg`; reordering here would not."""
    doc = Citable("x", "T", ["Jan van den Berg", "Ada Lovelace"], "2020")
    entry = B.to_bibtex(doc, "k")
    assert "author       = {Jan van den Berg and Ada Lovelace}," in entry


def test_tex_specials_in_a_title_cannot_break_the_file():
    doc = Citable("x", "Cost & Benefit: 100% of $x_1$", ["A B"], "2020")
    entry = B.to_bibtex(doc, "k")
    assert r"\&" in entry and r"\%" in entry and r"\$" in entry
    assert "%" not in entry.replace(r"\%", "")   # a bare % comments out the brace


def test_the_title_is_braced_so_plain_bst_cannot_lowercase_it():
    entry = B.to_bibtex(DEVLIN, "k")
    assert "title        = {{BERT: Pre-training of Deep Bidirectional Transformers}}," in entry


def test_an_arxiv_paper_is_an_article_with_the_preprint_as_its_journal():
    entry = B.to_bibtex(VASWANI, "k")
    assert entry.startswith("@article{k,")
    assert "journal      = {arXiv preprint arXiv:1706.03762}," in entry


def test_without_an_identifier_it_is_a_misc_rather_than_a_journal_we_invented():
    assert B.to_bibtex(DEVLIN, "k").startswith("@misc{k,")


def test_empty_fields_are_omitted_not_written_blank():
    entry = B.to_bibtex(Citable("x", "T", ["A B"], ""), "k")
    assert "year" not in entry
    assert "doi" not in entry


# ─────────────────────── the file is the authority ───────────────────────

def test_citing_writes_an_entry_and_returns_its_key(tmp_path):
    key, added = B.cite(tmp_path, VASWANI)
    assert (key, added) == ("vaswani2017attention", True)
    assert "@article{vaswani2017attention," in B.read_bib(tmp_path)


def test_citing_the_same_paper_twice_writes_one_entry(tmp_path):
    B.cite(tmp_path, VASWANI)
    key, added = B.cite(tmp_path, VASWANI)
    assert (key, added) == ("vaswani2017attention", False)
    assert B.read_bib(tmp_path).count("@article{") == 1


def test_a_key_already_in_the_file_is_never_recomputed(tmp_path):
    """The point of the whole design: `\\cite{}` already typed must keep working."""
    B.cite(tmp_path, VASWANI)
    # the same paper, re-extracted with a better title after a re-ingest
    improved = Citable(
        doc_id="d1", title="Attention Is All You Need (v5)",
        authors=["Ashish Vaswani"], year="2017", arxiv_id="1706.03762",
    )
    assert B.cite(tmp_path, improved)[0] == "vaswani2017attention"


def test_an_entry_the_author_wrote_by_hand_survives_a_citation(tmp_path):
    (tmp_path / B.BIB_FILENAME).write_text("@book{knuth1984,\n  title = {The TeXbook},\n}\n")
    B.cite(tmp_path, VASWANI)
    text = B.read_bib(tmp_path)
    assert "@book{knuth1984," in text and "@article{vaswani2017attention," in text


def test_a_hand_written_key_still_counts_as_taken(tmp_path):
    (tmp_path / B.BIB_FILENAME).write_text("@book{vaswani2017attention,\n  title = {Mine},\n}\n")
    key, _ = B.cite(tmp_path, VASWANI)
    assert key == "vaswani2017attention" + "a"


def test_assign_keys_honours_the_file_and_invents_only_the_rest(tmp_path):
    B.cite(tmp_path, DEVLIN)
    keys = B.assign_keys([VASWANI, DEVLIN], B.read_bib(tmp_path))
    assert keys == {"d1": "vaswani2017attention", "d2": "devlin2019bert"}


def test_parse_entries_ignores_entries_that_are_not_ours(tmp_path):
    (tmp_path / B.BIB_FILENAME).write_text("@book{knuth1984,\n  title = {The TeXbook},\n}\n")
    B.cite(tmp_path, VASWANI)
    assert B.parse_entries(B.read_bib(tmp_path)) == {"d1": "vaswani2017attention"}
    assert B.taken_keys(B.read_bib(tmp_path)) == {"knuth1984", "vaswani2017attention"}


@pytest.mark.parametrize("first,second", [
    (VASWANI, DEVLIN),
    (DEVLIN, VASWANI),
])
def test_the_file_stays_parseable_whatever_order_things_arrive_in(tmp_path, first, second):
    B.cite(tmp_path, first)
    B.cite(tmp_path, second)
    assert len(B.parse_entries(B.read_bib(tmp_path))) == 2


# ─────────────── a citing document needs somewhere to print ───────────────
#
# `\cite{key}` alone renders `[?]` and no reference list, because BibTeX is
# only invoked at all by the `\bibdata` line that `\bibliography` writes into
# the .aux. To an author that looks exactly like the citation not working.

from domain.paper_writer.compiler import _ensure_bibliography

CITING = "\\documentclass{article}\n\\begin{document}\n\\cite{a}\n\\end{document}\n"


def _with_bib(tmp_path, source=CITING):
    (tmp_path / B.BIB_FILENAME).write_text("@misc{a, title={T},}\n")
    return _ensure_bibliography(source, tmp_path)


def test_a_citing_document_gets_a_bibliography(tmp_path):
    out = _with_bib(tmp_path)
    assert "\\bibliographystyle{plain}" in out
    assert "\\bibliography{references}" in out


def test_it_goes_before_end_document_where_references_belong(tmp_path):
    out = _with_bib(tmp_path)
    assert out.index("\\bibliography{references}") < out.index("\\end{document}")


def test_a_document_that_cites_nothing_is_left_alone(tmp_path):
    plain = "\\documentclass{article}\n\\begin{document}\nhello\n\\end{document}\n"
    assert _with_bib(tmp_path, plain) == plain


def test_an_existing_bibliography_is_not_duplicated(tmp_path):
    already = CITING.replace("\\end{document}", "\\bibliography{refs}\n\\end{document}")
    assert _with_bib(tmp_path, already) == already


def test_a_hand_written_thebibliography_is_respected(tmp_path):
    manual = CITING.replace(
        "\\end{document}",
        "\\begin{thebibliography}{9}\n\\bibitem{a} Mine.\n\\end{thebibliography}\n\\end{document}",
    )
    assert _with_bib(tmp_path, manual) == manual


def test_nothing_is_added_without_a_bib_file(tmp_path):
    """Pointing at a file that is not there turns a compile into a failure."""
    assert _ensure_bibliography(CITING, tmp_path) == CITING


@pytest.mark.parametrize("command", [
    "\\cite{a}", "\\citep{a}", "\\citet{a}", "\\nocite{a}", "\\cite[p. 3]{a}",
])
def test_every_form_of_citation_counts(tmp_path, command):
    source = CITING.replace("\\cite{a}", command)
    assert "\\bibliography{references}" in _with_bib(tmp_path, source)
