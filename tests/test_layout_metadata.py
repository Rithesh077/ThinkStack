"""Title and author extraction from page geometry.

Spans are built by hand so every case is legible and no PDF is needed. The
numbers are not invented -- font sizes and coordinates are copied from the
papers in `local/testpapers/`, and each test names the paper it came from.

Ground truth against the real files lives in `test_metadata_ground_truth.py`.
"""

import pytest

from domain.ingestion.layout import rows
from domain.ingestion.layout_metadata import (
    authors_from_layout,
    layout_digest,
    looks_like_name,
    name_rejection,
    title_from_layout,
    walk,
)
from domain.ingestion.models import PageLayout, TextSpan


def span(text, size, x0, y0, horizontal=True):
    return TextSpan(text=text, size=size, x0=x0, y0=y0,
                    x1=x0 + len(text) * size * 0.5, y1=y0 + size,
                    horizontal=horizontal, baseline=y0 + size)


def page(*spans, width=612.0, height=792.0):
    return PageLayout(page_number=1, width=width, height=height, spans=list(spans))


class TestTitle:
    def test_largest_text_near_the_top_wins(self):
        p = page(
            span("Deep Residual Learning for Image Recognition", 14.3, 136, 106),
            span("Kaiming He", 12.0, 136, 152),
            span("Deeper neural networks are hard to train.", 10.0, 136, 246),
        )
        assert title_from_layout(p) == "Deep Residual Learning for Image Recognition"

    def test_rotated_margin_stamp_does_not_win(self):
        """attention.pdf: the arXiv stamp is 20pt, the title only 17.2pt.

        It loses on two independent counts -- it is rotated, and it sits in
        the left margin. Either alone would be enough; both is deliberate,
        because a horizontal stamp in the margin exists too.
        """
        p = page(
            span("arXiv:1706.03762v7 [cs.CL] 2 Aug 2023", 20.0, 20, 300, horizontal=False),
            span("Attention Is All You Need", 17.2, 200, 149),
        )
        assert title_from_layout(p) == "Attention Is All You Need"

    def test_horizontal_margin_furniture_is_skipped(self):
        p = page(
            span("JOURNAL OF THINGS, VOL 4", 22.0, 10, 60),
            span("A Real Title Here", 17.0, 200, 149),
        )
        assert title_from_layout(p) == "A Real Title Here"

    def test_wrapped_title_joins_its_second_line(self):
        """bert.pdf wraps at 14.3pt across y=71 and y=87."""
        p = page(
            span("BERT: Pre-training of Deep Bidirectional Transformers for", 14.3, 122, 71),
            span("Language Understanding", 14.3, 122, 87),
            height=842.0,
        )
        assert title_from_layout(p) == (
            "BERT: Pre-training of Deep Bidirectional Transformers for "
            "Language Understanding"
        )

    def test_same_font_reused_further_down_is_not_part_of_the_title(self):
        p = page(
            span("The Actual Title", 14.3, 136, 106),
            span("1. Introduction", 14.3, 136, 400),
        )
        assert title_from_layout(p) == "The Actual Title"

    def test_no_spans_yields_empty_not_a_guess(self):
        assert title_from_layout(page()) == ""

    def test_ligatures_are_expanded(self):
        """effnet.pdf stores "Efficient" with U+FB01. Left alone it travels
        into the title, the citation key and every search over it."""
        p = page(span("EﬁcientNet: Rethinking Model Scaling", 14.3, 136, 106))
        assert title_from_layout(p) == "EficientNet: Rethinking Model Scaling"


class TestRows:
    def test_column_gap_splits_one_line_into_cells(self):
        """The single highest-value rule here.

        PyMuPDF reports resnet's four-column author row as one line, so as
        text it is the eight-word phrase "Kaiming He Xiangyu Zhang Shaoqing
        Ren Jian Sun" and no name filter can rescue it. The x gaps are 26.9pt
        against a 12pt font.
        """
        row = rows([
            span("Kaiming He", 12.0, 136.4, 152),
            span("Xiangyu Zhang", 12.0, 222.1, 152),
            span("Shaoqing Ren", 12.0, 323.7, 152),
            span("Jian Sun", 12.0, 418.0, 152),
        ])[0]
        assert [c.text for c in row.cells] == ["Kaiming He", "Xiangyu Zhang", "Shaoqing Ren", "Jian Sun"]

    def test_word_spacing_does_not_split(self):
        """A word space is about 0.25x the font size. The threshold is 0.45x,
        below the 0.59x that really does divide two names in llama2."""
        row = rows([
            TextSpan(text="Ashish", size=10.0, x0=132.9, x1=163.4,
                     y0=235, y1=245, baseline=245),
            TextSpan(text="Vaswani", size=10.0, x0=166.0, x1=199.8,
                     y0=235, y1=245, baseline=245),
        ])[0]
        assert [c.text for c in row.cells] == ["Ashish Vaswani"]

    def test_a_font_change_mid_word_does_not_insert_a_space(self):
        """adam.pdf sets its title in small caps: "A" at 17.2pt butted
        directly against "DAM" at 13.8pt, sharing a baseline. Grouped by
        bounding-box top instead, the title came out "A : A M S O"."""
        row = rows([
            TextSpan(text="A", size=17.2, x0=100.0, x1=112.0,
                     y0=100, y1=117, baseline=117),
            TextSpan(text="DAM", size=13.8, x0=112.0, x1=145.0,
                     y0=103, y1=117, baseline=117),
        ])[0]
        assert [c.text for c in row.cells] == ["ADAM"]

    def test_a_loose_accent_is_reattached(self):
        """sam.pdf stores "Dollár" as "Doll" + U+00B4 + "ar". Left alone it
        prints as "Doll ´ar" and the surname cannot be searched for."""
        row = rows([
            TextSpan(text="Piotr Doll´ar", size=10.0, x0=100.0, x1=160.0,
                     y0=100, y1=110, baseline=110),
        ])[0]
        assert [c.text for c in row.cells] == ["Piotr Dollár"]


class TestLooksLikeName:
    @pytest.mark.parametrize("name", [
        "Kaiming He",
        "Aidan N. Gomez",          # an initial mid-name
        "Łukasz Kaiser",           # Ł is outside Latin-1
        "Ming-Wei Chang",
        "Quoc V. Le",
        "Yann LECUN",              # caps surname, 5 letters -- not an acronym
    ])
    def test_accepts(self, name):
        assert looks_like_name(name)

    def test_an_affiliation_is_rejected_by_its_row_not_by_this(self):
        """The two filters answer different questions, on purpose.

        This one asks "is this shaped like a name" -- orthography, no
        vocabulary. "University of Toronto" is shaped exactly like one and
        passes here; it is the ROW carrying a structural word that removes it.
        Keeping vocabulary out of the cell test is what stops this function
        from growing into a list of employers.
        """
        assert looks_like_name("University of Toronto")

    @pytest.mark.parametrize("name, why", [
        ("Google AI Language", "short all-caps token beside words is an acronym"),
        ("jacobdevlin,mingweichang,kentonl", "no space -- bert's brace-form emails"),
        ("{", "pure punctuation, also from bert's emails"),
        ("avaswani@google.com", "an address"),
        ("Vaswani 2017", "digits"),
        ("Vaswani", "one word"),
        ("kaiming he", "no leading capital"),
        ("Attention Is All You Need Now Please", "too many parts to be a name"),
    ])
    def test_rejects(self, name, why):
        assert not looks_like_name(name), why


class TestAuthors:
    def test_column_layout(self):
        p = page(
            span("Deep Residual Learning", 14.3, 136, 106),
            span("Kaiming He", 12.0, 136.4, 152),
            span("Xiangyu Zhang", 12.0, 222.1, 152),
            span("Microsoft Research", 12.0, 250, 169),
            span("Abstract", 12.0, 300, 225),
        )
        assert authors_from_layout(p) == ["Kaiming He", "Xiangyu Zhang"]

    def test_comma_layout_in_a_single_cell(self):
        """ieee_a.pdf centres its authors on one line instead of in columns."""
        p = page(
            span("Navigate Biopsy with Ultrasound", 17.2, 150, 135),
            span("Haowei Li , Wenqing Yan , Jiasheng Zhao ,", 12.0, 150, 219),
            span("Abstract", 12.0, 150, 400),
            height=842.0,
        )
        assert authors_from_layout(p) == ["Haowei Li", "Wenqing Yan", "Jiasheng Zhao"]

    def test_one_structural_word_condemns_the_whole_row(self):
        """attention.pdf's affiliation row is "Google Brain Google Brain
        Google Research Google Research".

        Only two of those four cells carry a listed word -- "Brain" is not in
        the list and never will be. Judging the row rather than the cell is
        what makes the list a tiebreaker instead of a directory of employers.
        """
        p = page(
            span("Attention Is All You Need", 17.2, 200, 149),
            span("Ashish Vaswani", 10.0, 132.9, 235),
            span("Noam Shazeer", 10.0, 239.1, 235),
            span("Google Brain", 10.0, 132.9, 246),
            span("Google Research", 10.0, 239.1, 246),
            span("Abstract", 12.0, 200, 400),
        )
        assert authors_from_layout(p) == ["Ashish Vaswani", "Noam Shazeer"]

    def test_scanning_stops_at_the_abstract(self):
        p = page(
            span("A Title", 17.2, 200, 149),
            span("Ashish Vaswani", 10.0, 200, 235),
            span("Abstract", 10.0, 200, 300),
            span("Neural Networks Are", 10.0, 200, 320),
        )
        assert authors_from_layout(p) == ["Ashish Vaswani"]

    def test_a_phrase_printed_twice_is_an_address_not_a_person(self):
        """From a paper with one address block per author.

        "United Kingdom" and "Kaiming He" are both two capitalised words --
        orthography cannot tell them apart. Repetition can: a shared address
        is printed once per author, a name once per paper. It is the only
        rule here that needs no vocabulary at all.
        """
        p = page(
            span("Bayesian Online Changepoint Detection", 17.2, 200, 100),
            span("Ryan Prescott Adams", 10.0, 132, 150),
            span("United Kingdom", 10.0, 132, 165),
            span("David J.C. MacKay", 10.0, 132, 180),
            span("United Kingdom", 10.0, 132, 195),
            span("Abstract", 10.0, 200, 400),
        )
        assert authors_from_layout(p) == ["Ryan Prescott Adams", "David J.C. MacKay"]

    def test_a_byline_keeps_its_name_and_drops_its_affiliation(self):
        """acmart sets one author per row, with the institution beside them.

        Condemning the whole row -- correct for attention.pdf, where a row is
        nothing but employers -- returned one author out of four here.
        """
        p = page(
            span("Less is More: Optimizing Probe Selection", 14.3, 150, 100),
            span("TAVEESH SHARMA, University of Chicago, USA", 10.9, 150, 150),
            span("ANDREW CHU, University of Chicago, USA", 10.9, 150, 165),
            span("Abstract", 10.9, 150, 400),
        )
        assert authors_from_layout(p) == ["TAVEESH SHARMA", "ANDREW CHU"]

    def test_an_accented_institution_is_still_an_institution(self):
        """The list holds "universite"; gan's page says "Université", and the
        affiliation reached the author list because those differ as strings."""
        p = page(
            span("Generative Adversarial Nets", 17.2, 200, 100),
            span("Ian J. Goodfellow", 10.0, 132, 150),
            span("Université de Montréal", 10.0, 132, 170),
            span("Abstract", 10.0, 200, 400),
        )
        assert authors_from_layout(p) == ["Ian J. Goodfellow"]

    def test_the_trace_says_why_a_row_was_dropped(self):
        """`walk` is the one traversal behind both the extractor and the demo,
        so what the demo shows is what actually ran."""
        p = page(
            span("A Title", 17.2, 200, 149),
            span("Kaiming He", 10.0, 132, 235),
            span("Microsoft Research", 10.0, 132, 250),
            span("Abstract", 10.0, 200, 400),
        )
        by_role = {t.role: t for t in walk(p)}
        assert by_role["authors"].names == ["Kaiming He"]
        assert by_role["skipped"].reason == "names an institution"
        assert by_role["stop"].reason == "the abstract begins"

    def test_a_rejected_name_reports_the_rule_it_failed(self):
        assert name_rejection("Kaiming He") is None
        assert name_rejection("Google AI Language") == "acronym -- an institution"
        assert name_rejection("avaswani@google.com") == "is an address"

    def test_no_title_means_no_author_band(self):
        assert authors_from_layout(page()) == []


class TestLayoutDigest:
    def test_carries_font_sizes_into_the_prompt(self):
        """The model gets sizes, not flat text.

        Handed attention.pdf as a string it reads Google's licence notice
        first and answers with it -- the exact trap the old regex fell into,
        because it is the same evidence.
        """
        p = page(
            span("Provided proper attribution is provided", 12.0, 200, 73),
            span("Attention Is All You Need", 17.2, 200, 149),
        )
        digest = layout_digest(p)
        assert " 17.2 | Attention Is All You Need" in digest
        assert " 12.0 | Provided proper attribution is provided" in digest
