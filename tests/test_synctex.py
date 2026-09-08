"""Reading the position map every compile has been writing and nobody read.

The two questions are "where did this line go" and "what put this here". Both
are answered from a file TeX wrote, so most of the risk is in parsing it and in
being honest when it cannot answer.
"""

from __future__ import annotations

import gzip

import pytest

from domain.paper_writer import synctex as SX

# A minimal but real-shaped file: header, one page, nested boxes on three lines.
SAMPLE = """SyncTeX Version:1
Input:1:/tmp/proj/main.tex
Input:2:/tmp/proj/chapter.tex
Output:pdf
Magnification:1000
Unit:1
X Offset:0
Y Offset:0
Content:
{1
[1,10:1000,50000:20000,3000,0
(1,12:2000,40000:5000,1000,0
x1,12:2000,40000:0
)
(1,20:2000,30000:8000,1200,200
x1,20:2000,30000:0
)
]
}1
Postamble:
"""


@pytest.fixture
def mapfile(tmp_path):
    p = tmp_path / "main.synctex.gz"
    with gzip.open(p, "wt") as fh:
        fh.write(SAMPLE)
    return p


class TestParsing:
    def test_it_reads_boxes_and_inputs(self, mapfile):
        m = SX.parse(mapfile)
        assert len(m.boxes) >= 3
        assert m.inputs[1].endswith("main.tex")
        assert m.inputs[2].endswith("chapter.tex")

    def test_a_file_is_matched_by_name_not_by_path(self, mapfile):
        """The recorded path is the compiler's; a moved project keeps its name."""
        m = SX.parse(mapfile)
        assert m.tag_for("main.tex") == 1
        assert m.tag_for("/somewhere/else/entirely/chapter.tex") == 2
        assert m.tag_for("nothing.tex") is None

    def test_every_box_belongs_to_a_page(self, mapfile):
        m = SX.parse(mapfile)
        assert all(b.page == 1 for b in m.boxes)

    def test_a_corrupt_file_is_empty_not_an_exception(self, tmp_path):
        """This answers a click. A traceback where a cursor move was expected
        is worse than the feature doing nothing that once."""
        bad = tmp_path / "bad.synctex.gz"
        bad.write_bytes(b"this is not gzip at all")
        m = SX.parse(bad)
        assert m.boxes == [] and m.inputs == {}

    def test_a_missing_file_is_empty_not_an_exception(self, tmp_path):
        assert SX.parse(tmp_path / "nope.synctex.gz").boxes == []


class TestForward:
    def test_a_line_finds_its_place(self, mapfile):
        box = SX.parse(mapfile).forward(12)
        assert box is not None
        assert box.line == 12 and box.page == 1

    def test_the_tightest_box_wins(self, mapfile):
        """Boxes nest; the smallest claiming a line is the tightest admission."""
        box = SX.parse(mapfile).forward(20)
        assert box.width == 8000        # the hbox, not the page-wide vbox

    def test_a_line_with_no_box_falls_forward(self, mapfile):
        """A comment or a blank produced nothing; the paragraph it sits in did."""
        box = SX.parse(mapfile).forward(11)
        assert box is not None and box.line == 12

    def test_a_line_past_the_end_has_no_answer(self, mapfile):
        assert SX.parse(mapfile).forward(9999) is None

    def test_it_can_be_restricted_to_one_file(self, mapfile):
        m = SX.parse(mapfile)
        assert m.forward(12, tag=1) is not None
        assert m.forward(12, tag=2) is None      # chapter.tex has no boxes here


class TestReverse:
    def test_a_point_inside_a_box_finds_its_line(self, mapfile):
        box = SX.parse(mapfile).reverse(1, 3000, 40000)
        assert box is not None and box.line == 12

    def test_the_innermost_box_wins(self, mapfile):
        """The specific thing, not the paragraph around it."""
        box = SX.parse(mapfile).reverse(1, 2500, 30000)
        assert box.line == 20

    def test_a_click_in_the_margin_still_answers(self, mapfile):
        """A click in a gap means "about here", not "nowhere"."""
        box = SX.parse(mapfile).reverse(1, 19000, 45000)
        assert box is not None

    def test_a_page_with_nothing_on_it_has_no_answer(self, mapfile):
        assert SX.parse(mapfile).reverse(7, 100, 100) is None


class TestRoundTrip:
    def test_a_line_survives_going_out_and_back(self, mapfile):
        m = SX.parse(mapfile)
        for line in (12, 20):
            box = m.forward(line)
            back = m.reverse(box.page, box.x + box.width // 2, box.y)
            assert back.line == line

    def test_the_real_file_this_project_produced(self):
        """Not a fixture: the map from an actual compile in this repository."""
        import pathlib

        real = pathlib.Path("data/papers_workspace/0040e3568858/main.synctex.gz")
        if not real.is_file():
            pytest.skip("no compiled project in the workspace")
        m = SX.parse(real)
        assert m.boxes, "a real synctex file parsed to nothing"
        assert m.tag_for("main.tex") is not None

        # Only lines that produced a box WITH EXTENT round-trip. A line whose
        # only record is a zero-size marker -- a kern, a glyph anchor -- has a
        # position but occupies no area, so a point at it lies inside whatever
        # real box surrounds it, and reverse correctly answers with that.
        with_extent = sorted({b.line for b in m.boxes if b.width and b.height})
        assert with_extent, "no box in the real file had any extent"
        for line in with_extent[:3]:
            box = m.forward(line)
            back = m.reverse(box.page, box.x + box.width // 2, box.y)
            assert back.line == line, f"line {line} did not survive the round trip"

    def test_a_marker_only_line_still_has_a_position(self):
        """It just has no area, so the reverse lands on the box around it."""
        import pathlib

        real = pathlib.Path("data/papers_workspace/0040e3568858/main.synctex.gz")
        if not real.is_file():
            pytest.skip("no compiled project in the workspace")
        m = SX.parse(real)
        marker_only = [
            b.line for b in m.boxes
            if not (b.width and b.height)
            and not any(o.line == b.line and o.width and o.height for o in m.boxes)
        ]
        if not marker_only:
            pytest.skip("this document produced no marker-only lines")

        line = marker_only[0]
        box = m.forward(line)
        assert box is not None and box.line == line     # it IS located
        assert not (box.width and box.height)           # with no area to highlight

        # and the point it names sits inside some real box, which is what
        # reverse will answer with -- the paragraph, not the marker
        back = m.reverse(box.page, box.x, box.y)
        assert back is not None
