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

    def test_any_file_type_can_be_linked(self, project, outside):
        """Type is not the test any more.

        A suffix allowlist refused these until 2026-08-23. It was refusing
        datasets, notes and image formats people legitimately keep beside a
        paper, and the reason it was really there -- keeping an absolute-path
        endpoint away from things worth stealing -- is now carried by the
        same-origin check and the loopback bind, which is where an access
        question belongs. What a document can USE is still narrower than what
        it can link, and the picker says which is which.
        """
        for name in ("id_rsa", "passwd", "notes.docx", "script.sh", "data.parquet"):
            p = outside / name
            p.write_text("x")
            link = L.add_link(project, p)
            assert link.name == name

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

    def test_copying_a_folder_in_is_recursive_and_takes_everything(self, project, outside):
        figures = outside / "figures"
        (figures / "nested").mkdir(parents=True)
        _tex(figures, "one.tex", "a")
        _tex(figures / "nested", "two.tex", "b")
        (figures / "notes.docx").write_text("not for us")

        link = L.add_link(project, figures)
        rel = L.copy_into_project(project, link.id)

        assert (project / rel / "one.tex").read_text() == "a"
        assert (project / rel / "nested" / "two.tex").read_text() == "b"
        # Everything comes across. Thinning a copied folder to the files LaTeX
        # understands loses the author's own data silently -- they asked for
        # the folder, not for our opinion of which half of it counts.
        assert (project / rel / "notes.docx").read_text() == "not for us"

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


class TestBrowsing:
    """Listing a directory so the interface can draw a chooser.

    This exists because the native dialog is only available inside the desktop
    shell, and its absence left typing a path as the way through -- which is
    remembering, not choosing. It lists and nothing else: no content is read,
    nothing is opened, nothing is written.
    """

    def _client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app, raise_server_exceptions=False)

    def test_it_lists_folders_and_files(self, tmp_path):
        (tmp_path / "papers").mkdir()
        (tmp_path / "refs.bib").write_text("@book{x}")
        r = self._client().get("/api/papers/browse", params={"path": str(tmp_path)})
        assert r.status_code == 200
        names = [e["name"] for e in r.json()["entries"]]
        assert names == ["papers", "refs.bib"]          # folders first, then files

    def test_every_file_can_be_taken(self, tmp_path):
        (tmp_path / "refs.bib").write_text("x")
        (tmp_path / "notes.docx").write_text("x")
        entries = {e["name"]: e for e in
                   self._client().get("/api/papers/browse",
                                      params={"path": str(tmp_path)}).json()["entries"]}
        # Nothing is greyed out any more, because nothing would be refused.
        assert entries["refs.bib"]["linkable"] is True
        assert entries["notes.docx"]["linkable"] is True

    def test_it_still_says_which_files_latex_understands(self, tmp_path):
        (tmp_path / "refs.bib").write_text("x")
        (tmp_path / "notes.docx").write_text("x")
        entries = {e["name"]: e for e in
                   self._client().get("/api/papers/browse",
                                      params={"path": str(tmp_path)}).json()["entries"]}
        # A hint the chooser can show, not a gate. Someone linking notes.docx
        # beside a paper is doing something reasonable; someone expecting to
        # \input it is not, and this is what lets the interface say so.
        assert entries["refs.bib"]["latex"] is True
        assert entries["notes.docx"]["latex"] is False

    def test_dotfiles_are_left_out(self, tmp_path):
        """A chooser is not a file manager; dotfiles are noise in one."""
        (tmp_path / ".hidden.tex").write_text("x")
        (tmp_path / "shown.tex").write_text("x")
        body = self._client().get(
            "/api/papers/browse", params={"path": str(tmp_path)}
        ).json()
        assert [e["name"] for e in body["entries"]] == ["shown.tex"]

    def test_it_offers_the_way_back_up(self, tmp_path):
        sub = tmp_path / "deep"
        sub.mkdir()
        body = self._client().get("/api/papers/browse", params={"path": str(sub)}).json()
        assert body["parent"] == str(tmp_path)
        assert body["path"] == str(sub)

    def test_a_missing_folder_is_a_404_not_an_empty_list(self, tmp_path):
        r = self._client().get("/api/papers/browse", params={"path": str(tmp_path / "nope")})
        assert r.status_code == 404

    def test_a_file_is_not_a_folder(self, tmp_path):
        f = tmp_path / "a.tex"
        f.write_text("x")
        assert self._client().get("/api/papers/browse", params={"path": str(f)}).status_code == 400

    def test_it_never_returns_file_contents(self, tmp_path):
        (tmp_path / "secret.tex").write_text("SENSITIVE-CONTENT-MARKER")
        r = self._client().get("/api/papers/browse", params={"path": str(tmp_path)})
        assert "SENSITIVE-CONTENT-MARKER" not in r.text
