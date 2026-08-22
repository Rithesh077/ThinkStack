"""Files a project uses that live somewhere else.

The feature is "reference it where it is", so the whole risk is that the file
moves. These tests are mostly about that: what survives a rename, what survives
a move, what does not, and that the failures are admitted rather than guessed
at.
"""

from __future__ import annotations

import pathlib

import pytest

from domain.paper_writer import links as L
from domain.paper_writer.files import FileError


@pytest.fixture
def project(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    return d


@pytest.fixture
def outside(tmp_path):
    d = tmp_path / "elsewhere"
    d.mkdir()
    return d


def _tex(d: pathlib.Path, name: str, body: str = "hello") -> pathlib.Path:
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


class TestLinking:
    def test_a_file_is_referenced_not_copied(self, project, outside):
        src = _tex(outside, "chapter.tex")
        link = L.add_link(project, src)

        assert link.path == str(src)
        # nothing was written into the project except the index itself
        assert [p.name for p in project.iterdir()] == ["links.json"]
        assert src.exists()

    def test_only_suffixes_a_latex_project_can_use(self, project, outside):
        for name in ("id_rsa", "passwd", "notes.docx", "script.sh"):
            p = outside / name
            p.write_text("x")
            with pytest.raises(FileError):
                L.add_link(project, p)

    def test_a_relative_path_is_refused(self, project):
        with pytest.raises(FileError):
            L.add_link(project, "chapter.tex")

    def test_a_missing_file_is_refused(self, project, outside):
        with pytest.raises(FileError):
            L.add_link(project, outside / "nope.tex")

    def test_linking_the_same_file_twice_updates_rather_than_duplicates(
        self, project, outside
    ):
        src = _tex(outside, "refs.bib")
        a = L.add_link(project, src)
        b = L.add_link(project, src)
        assert a.id == b.id
        assert len(L.list_links(project)) == 1


class TestSurvivingAMove:
    """The identity is st_dev + st_ino, which a rename and a move preserve."""

    def test_a_rename_is_followed(self, project, outside):
        src = _tex(outside, "before.tex")
        L.add_link(project, src)
        src.rename(outside / "after.tex")

        resolved = L.list_links(project)
        assert len(resolved) == 1
        assert resolved[0].status == "moved"
        assert resolved[0].resolved.name == "after.tex"

    def test_a_move_into_a_subfolder_is_followed(self, project, outside):
        """Dropping a figure into `figures/` is the commonest real move."""
        src = _tex(outside, "figure.tex")
        L.add_link(project, src)
        sub = outside / "chapters"
        sub.mkdir()
        src.rename(sub / "figure.tex")

        r = L.list_links(project)[0]
        assert r.status == "moved"
        assert r.resolved == sub / "figure.tex"

    def test_a_move_somewhere_unrelated_is_admitted_not_guessed(
        self, project, outside, tmp_path
    ):
        """The search is deliberately small, and says so rather than hunting.

        A file moved somewhere the project has never referred to is reported
        missing, which is the honest answer -- the alternative is walking the
        user's home directory while they wait.
        """
        src = _tex(outside, "wandered.tex")
        L.add_link(project, src)
        far = tmp_path / "somewhere" / "else"
        far.mkdir(parents=True)
        src.rename(far / "wandered.tex")

        r = L.list_links(project)[0]
        assert r.status == "missing"

    def test_the_index_remembers_where_it_went(self, project, outside):
        src = _tex(outside, "one.tex")
        L.add_link(project, src)
        src.rename(outside / "two.tex")

        L.list_links(project)                    # first look repairs the path
        again = L.list_links(project)            # second must not need to search
        assert again[0].status == "ok"
        assert again[0].link.name == "two.tex"

    def test_a_deleted_file_is_reported_missing_not_guessed(self, project, outside):
        src = _tex(outside, "gone.tex")
        L.add_link(project, src)
        src.unlink()

        r = L.list_links(project)[0]
        assert r.status == "missing"
        assert r.resolved is None

    def test_saved_over_in_place_is_still_the_same_document(self, project, outside):
        """An editor that writes a temp file and renames it changes the inode.

        The path is tried before the identity precisely so this reads as the
        same document rather than a missing one.
        """
        src = _tex(outside, "draft.tex", "first")
        link = L.add_link(project, src)
        old_ino = link.ino

        tmp = outside / "draft.tex.tmp"
        tmp.write_text("second", encoding="utf-8")
        tmp.replace(src)                          # atomic save: new inode, same path

        r = L.list_links(project)[0]
        assert r.status == "ok"
        assert r.resolved.read_text() == "second"
        assert L.get(project, link.id).ino != old_ino   # index caught up


class TestRepairAndRemoval:
    def test_the_user_can_point_it_somewhere_new(self, project, outside, tmp_path):
        src = _tex(outside, "lost.tex")
        link = L.add_link(project, src)
        src.unlink()

        far = tmp_path / "far"
        far.mkdir()
        moved = _tex(far, "lost.tex")
        L.relink(project, link.id, moved)

        r = L.list_links(project)[0]
        assert r.status == "ok"
        assert r.resolved == moved
        assert len(L.list_links(project)) == 1      # not a second row

    def test_removing_a_link_never_deletes_the_file(self, project, outside):
        src = _tex(outside, "keep.tex")
        link = L.add_link(project, src)
        L.remove(project, link.id)

        assert L.list_links(project) == []
        assert src.exists(), "the file is not ours to delete"

    def test_copying_in_is_a_deliberate_act(self, project, outside):
        src = _tex(outside, "wanted.bib", "@book{x}")
        link = L.add_link(project, src)

        rel = L.copy_into_project(project, link.id)
        assert (project / rel).read_text() == "@book{x}"
        assert src.exists()                          # the original stays put
        # and the link is still a link; copying does not consume it
        assert len(L.list_links(project)) == 1

    def test_copying_a_missing_file_says_so(self, project, outside):
        src = _tex(outside, "vanish.tex")
        link = L.add_link(project, src)
        src.unlink()
        with pytest.raises(FileError):
            L.copy_into_project(project, link.id)


class TestTheIndexItself:
    def test_a_corrupt_index_does_not_break_the_project(self, project):
        (project / "links.json").write_text("{ not json", encoding="utf-8")
        assert L.list_links(project) == []          # degraded, not broken

    def test_the_index_is_hidden_from_the_file_tree(self, project, outside):
        from domain.paper_writer import files as F

        L.add_link(project, _tex(outside, "a.tex"))
        assert "links.json" not in [e.name for e in F.list_files(project)]


class TestLinkingAFolder:
    """A shared `figures/` directory is the case this exists for.

    A folder cannot be filtered by suffix -- directories have no extension --
    so it earns its safety differently: nothing ever reads or serves the
    contents of a linked folder. It is a remembered location, and copying it in
    is the only thing that touches what is inside.
    """

    def test_a_folder_can_be_linked(self, project, outside):
        figures = outside / "figures"
        figures.mkdir()
        _tex(figures, "plot.tex")

        link = L.add_link(project, figures)
        assert link.kind == "dir"
        assert link.name == "figures"
        assert L.list_links(project)[0].status == "ok"

    def test_a_renamed_folder_is_followed(self, project, outside):
        figures = outside / "figures"
        figures.mkdir()
        _tex(figures, "plot.tex")
        L.add_link(project, figures)

        figures.rename(outside / "images")
        r = L.list_links(project)[0]
        assert r.status == "moved"
        assert r.resolved.name == "images"

    def test_copying_a_folder_in_is_recursive_and_filtered(self, project, outside):
        figures = outside / "figures"
        (figures / "nested").mkdir(parents=True)
        _tex(figures, "one.tex", "a")
        _tex(figures / "nested", "two.tex", "b")
        (figures / "notes.docx").write_text("not for us")

        link = L.add_link(project, figures)
        rel = L.copy_into_project(project, link.id)

        assert (project / rel / "one.tex").read_text() == "a"
        assert (project / rel / "nested" / "two.tex").read_text() == "b"
        # the same rule as linking a file: only what a paper can use
        assert not (project / rel / "notes.docx").exists()

    def test_a_folder_is_not_served_as_a_file(self, tmp_path, monkeypatch):
        """The raw endpoint refuses a folder rather than trying to stream it.

        Driven through the real route, because the point is what an HTTP caller
        gets back -- a 400 saying it is a folder, not a 500 from FileResponse
        failing to open a directory.
        """
        from fastapi.testclient import TestClient

        import main
        from domain.paper_writer import compiler

        workspace = tmp_path / "papers"
        workspace.mkdir()
        monkeypatch.setattr(compiler, "PAPERS_DIR", workspace)
        proj = workspace / "abc123456789"
        proj.mkdir()

        figures = tmp_path / "figures"
        figures.mkdir()
        link = L.add_link(proj, figures)

        c = TestClient(main.app, raise_server_exceptions=False)
        r = c.get(f"/api/papers/projects/abc123456789/links/{link.id}/raw")
        assert r.status_code == 400
        assert "folder" in r.text

    def test_a_missing_folder_is_reported_not_guessed(self, project, outside):
        import shutil

        figures = outside / "figures"
        figures.mkdir()
        L.add_link(project, figures)
        shutil.rmtree(figures)

        assert L.list_links(project)[0].status == "missing"
