"""Metadata extraction: year, plausibility, and which source gets used.

The regex title/author functions are still tested here because they remain
the fallback when a page has no readable layout (a scan, a PDF PyMuPDF cannot
walk). Layout extraction has its own file.
"""

import pytest

from domain.ingestion import metadata_extractor as M
from domain.ingestion.metadata_extractor import (
    _extract_authors,
    _extract_title,
    _extract_year,
    extract_metadata,
    find_arxiv_id,
    find_doi,
    metadata_is_plausible,
    title_is_plausible,
)
from domain.ingestion.models import DocumentMetadata, PageLayout, TextSpan


class TestExtractTitle:
    def test_title_is_first_block(self):
        text = "Deep Learning for Medical Imaging\n\nAbstract\nThis paper..."
        assert _extract_title(text) == "Deep Learning for Medical Imaging"

    def test_stops_at_abstract_keyword(self):
        text = "A Survey of Transformers\nAbstract: we review..."
        assert "Abstract" not in _extract_title(text)

    def test_skips_short_leading_lines(self):
        text = "p. 1\nOptimization Methods for Neural Networks\n\nAbstract"
        assert _extract_title(text) == "Optimization Methods for Neural Networks"

    def test_empty_text(self):
        assert _extract_title("") == ""


class TestExtractAuthors:
    def test_extracts_first_last_names(self):
        text = "NEURAL NETWORKS: A SURVEY\nJohn Smith and Jane Doe\nAbstract"
        authors = _extract_authors(text)
        assert "John Smith" in authors and "Jane Doe" in authors

    def test_skips_email_lines(self):
        text = "TITLE HERE\nj.smith@university.edu\nAbstract"
        assert _extract_authors(text) == []

    def test_empty_text(self):
        assert _extract_authors("") == []


class TestIdentifiers:
    def test_finds_an_arxiv_id(self):
        assert find_arxiv_id("arXiv:1706.03762v7 [cs.CL] 2 Aug 2023") == "1706.03762"

    def test_finds_a_doi_without_trailing_punctuation(self):
        assert find_doi("see doi:10.1145/3292500.3330701.") == "10.1145/3292500.3330701"

    def test_absent(self):
        assert find_arxiv_id("no identifier here") == ""
        assert find_doi("no identifier here") == ""


class TestExtractYear:
    def test_arxiv_id_beats_stray_four_digit_numbers(self):
        """attention.pdf, verbatim, and the bug it caused.

        The old rule was "first four-digit number in the first 3000
        characters", which is 2014 -- part of Google's licence boilerplate
        and three years before the paper. The arXiv id encodes YYMM, so
        1706 is June 2017 and is not a guess.
        """
        text = (
            "Provided proper attribution is provided, Google hereby grants "
            "permission to reproduce the tables and figures in this paper "
            "solely for use in journalistic or scholarly works. 2014 "
            "arXiv:1706.03762v7 [cs.CL] 2 Aug 2023"
        )
        assert _extract_year(text) == "2017"

    def test_arxiv_id_is_found_beyond_the_front_matter_window(self):
        """PyMuPDF emits the rotated margin stamp after the page body: past
        character 3000 on two of the three papers first measured."""
        text = "x" * 4000 + " arXiv:1810.04805v2 [cs.CL] 24 May 2019"
        assert _extract_year(text) == "2018"

    def test_falls_back_to_a_stated_year(self):
        assert _extract_year("Published as a conference paper at ICLR 2019") == "2019"
        assert _extract_year("Copyright 2021 by the authors") == "2021"

    def test_no_year_stated_yields_empty(self):
        """An empty year is a fact. A wrong one becomes a wrong bibliography
        entry, which is exactly where a reviewer looks."""
        assert _extract_year("A paper with 512 tokens and 16 heads.") == ""

    def test_implausible_years_are_refused(self):
        assert _extract_year("arXiv:9912.01234") == ""


class TestPlausibility:
    @pytest.mark.parametrize("title", [
        "Attention Is All You Need",
        "BERT: Pre-training of Deep Bidirectional Transformers",
    ])
    def test_accepts_real_titles(self, title):
        assert title_is_plausible(title)

    @pytest.mark.parametrize("title, why", [
        ("Provided proper attribution is provided, Google hereby grants "
         "permission to reproduce the tables", "licence boilerplate"),
        ("Abstract", "a section heading"),
        ("", "nothing"),
        ("Introduction", "a section heading"),
        ("Transformers", "one word"),
        ("1. 2. 3. 4. 5. 6.", "mostly not letters"),
        ("x" * 400, "far too long to be a title"),
    ])
    def test_rejects(self, title, why):
        assert not title_is_plausible(title), why

    def test_a_wrong_title_with_no_authors_is_implausible(self):
        """The shipped bug, pinned.

        The old guard was `not metadata.title` -- it asked whether extraction
        had gone SILENT. The failure mode was never silence; it was confident
        wrongness, so the guard never fired and the model path that existed to
        rescue these papers was unreachable on every one of them.
        """
        bad = DocumentMetadata(
            title="Provided proper attribution is provided, Google hereby grants",
            authors=[],
        )
        assert bad.title, "not empty -- which is precisely why the old guard passed it"
        assert not metadata_is_plausible(bad)

    def test_a_plausible_title_with_no_authors_is_still_implausible(self):
        """Our own synopsis is this case: a cover page whose largest text is
        genuinely the university name, with no author row under it."""
        assert not metadata_is_plausible(
            DocumentMetadata(title="Project Synopsis Report", authors=[]))


def _page(title="Attention Is All You Need", author="Ashish Vaswani"):
    return PageLayout(page_number=1, width=612.0, height=792.0, spans=[
        TextSpan(text=title, size=17.2, x0=200, y0=149, x1=400, y1=166),
        TextSpan(text=author, size=10.0, x0=200, y0=235, x1=300, y1=245),
        TextSpan(text="Abstract", size=10.0, x0=200, y0=300, x1=250, y1=310),
    ])


class TestSourceSelection:
    async def test_good_layout_never_reaches_the_model(self, monkeypatch):
        """The model costs seconds and this runs on every upload."""
        async def boom(*a, **k):
            raise AssertionError("the model must not be called for a good page")
        monkeypatch.setattr(M, "extract_metadata_slm", boom)

        meta = await extract_metadata("body text", page=_page())

        assert meta.title == "Attention Is All You Need"
        assert meta.authors == ["Ashish Vaswani"]

    async def test_implausible_layout_reaches_the_model(self, monkeypatch):
        called = []

        async def fake(text, page=None):
            called.append(page is not None)
            return DocumentMetadata(title="The Real Title", authors=["A Person"])
        monkeypatch.setattr(M, "extract_metadata_slm", fake)

        meta = await extract_metadata("body", page=_page(title="Abstract", author="x"))

        assert called == [True], "the page must be passed on, not just the flat text"
        assert meta.title == "The Real Title"

    async def test_the_model_may_not_erase_what_layout_found(self, monkeypatch):
        """A second opinion, not an override.

        A 0.5B model returning "" for a field it did not understand must not
        blank a title the geometry read correctly.
        """
        async def empty(text, page=None):
            return DocumentMetadata(title="", authors=[], abstract="", year="")
        monkeypatch.setattr(M, "extract_metadata_slm", empty)

        page = _page(author="Google Research")   # affiliation row -> no authors
        meta = await extract_metadata("body", page=page)

        assert meta.title == "Attention Is All You Need"

    async def test_use_slm_false_returns_the_implausible_result_unchanged(self, monkeypatch):
        async def boom(*a, **k):
            raise AssertionError("use_slm=False must mean no model call")
        monkeypatch.setattr(M, "extract_metadata_slm", boom)

        meta = await extract_metadata("body", page=_page(title="Abstract"), use_slm=False)

        assert meta.title == "Abstract"

    async def test_no_page_falls_back_to_the_flat_text_path(self, monkeypatch):
        """A scanned PDF, or one whose page tree cannot be walked."""
        async def boom(*a, **k):
            raise AssertionError("regex result was plausible; no model needed")
        monkeypatch.setattr(M, "extract_metadata_slm", boom)

        text = "Neural Networks for Everything\nJohn Smith and Jane Doe\nAbstract"
        meta = await extract_metadata(text, page=None)

        assert meta.title == "Neural Networks for Everything"
        assert "John Smith" in meta.authors
