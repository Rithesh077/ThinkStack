"""Moving a file from one paper into another.

Separate from move_path because the safety argument is different: there are two
roots and each end has to be checked against its own. A single function taking
one root and two paths would mean a call site deciding which root applies to
which path, and that is the decision that gets made wrongly later.
"""

from __future__ import annotations

import pytest

from domain.paper_writer import files as F
from domain.paper_writer.files import FileError


@pytest.fixture
def two(tmp_path):
    a, b = tmp_path / "paper-a", tmp_path / "paper-b"
    a.mkdir()
    b.mkdir()
    return a, b


class TestMovingBetweenPapers:
    def test_a_file_arrives_and_leaves(self, two):
        a, b = two
        (a / "chapter.tex").write_text("body", encoding="utf-8")

        entry = F.move_between(a, "chapter.tex", b, "chapter.tex")

        assert entry.path == "chapter.tex"
        assert (b / "chapter.tex").read_text() == "body"
        assert not (a / "chapter.tex").exists(), "a move is not a copy"

    def test_it_can_land_in_a_folder(self, two):
        a, b = two
        (a / "plot.png").write_bytes(b"x")
        (b / "figures").mkdir()

        F.move_between(a, "plot.png", b, "figures/plot.png")
        assert (b / "figures" / "plot.png").exists()

    def test_it_will_not_overwrite(self, two):
        a, b = two
        (a / "refs.bib").write_text("new", encoding="utf-8")
        (b / "refs.bib").write_text("existing", encoding="utf-8")

        with pytest.raises(FileError):
            F.move_between(a, "refs.bib", b, "refs.bib")
        assert (b / "refs.bib").read_text() == "existing"
        assert (a / "refs.bib").exists(), "a refused move leaves the source alone"


class TestWhatItRefuses:
    def test_a_folder_cannot_be_dragged_across(self, two):
        """An unbounded subtree with a size cap to honour at the far end.

        The folder is named with an ALLOWED suffix on purpose. A folder called
        "chapters" is refused by the suffix check whether or not anything looks
        at is_dir, so a test using one would pass with the directory check
        removed -- which is exactly what it is here to catch.
        """
        a, b = two
        (a / "figures.tex").mkdir()
        (a / "figures.tex" / "inner.tex").write_text("x", encoding="utf-8")

        with pytest.raises(FileError):
            F.move_between(a, "figures.tex", b, "figures.tex")
        assert (a / "figures.tex").is_dir(), "the folder is untouched"

    @pytest.mark.parametrize(
        "src,dst",
        [
            ("../../../etc/passwd", "stolen.tex"),
            ("ok.tex", "../../../tmp/escaped.tex"),
            ("ok.tex", "/etc/planted.tex"),
        ],
    )
    def test_neither_end_can_leave_its_project(self, two, src, dst):
        a, b = two
        (a / "ok.tex").write_text("x", encoding="utf-8")
        with pytest.raises(FileError):
            F.move_between(a, src, b, dst)

    def test_crossing_projects_is_not_a_way_out_of_the_destination(self, two):
        """The boundary is what crossing must not evade.

        This asserted the destination SUFFIX until the type allowlist was
        removed. Type was never the thing that made a two-root move dangerous
        -- landing outside the destination project is -- and that is what each
        end being resolved against its own root prevents.
        """
        a, b = two
        (a / "ok.tex").write_text("x", encoding="utf-8")
        with pytest.raises(FileError):
            F.move_between(a, "ok.tex", b, "../escaped.tex")

    def test_any_file_type_may_cross(self, two):
        # Moving a dataset from one paper to another is an ordinary thing to
        # want, and was refused while type was the test.
        a, b = two
        (a / "data.parquet").write_text("x", encoding="utf-8")
        F.move_between(a, "data.parquet", b, "data.parquet")
        assert (b / "data.parquet").exists()
        assert not (a / "data.parquet").exists()

    def test_a_missing_source_is_refused(self, two):
        a, b = two
        with pytest.raises(FileError):
            F.move_between(a, "nothing.tex", b, "nothing.tex")

    def test_the_destination_size_cap_applies(self, two, monkeypatch):
        """The cap belongs to the paper receiving it, not the one sending."""
        a, b = two
        monkeypatch.setattr(F, "MAX_PROJECT_BYTES", 100)
        (b / "filler.tex").write_bytes(b"y" * 90)
        (a / "big.tex").write_bytes(b"x" * 50)

        with pytest.raises(FileError):
            F.move_between(a, "big.tex", b, "big.tex")
        assert (a / "big.tex").exists()
