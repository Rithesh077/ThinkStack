"""Nothing in Scribe may require an ingested paper.

The first thing a fresh install used to say was, in effect, "add papers" -- and
someone who opened ThinkStack to write a letter has no papers and no intention
of getting any. Scribe carries its own TeX engine and compiles offline, so an
empty library is a normal state, not a broken one.

Every route here is one a first-run user touches before ingesting anything. The
bar is deliberately low and absolute: none of them may fail. A 500 on an empty
library is the app telling a new user it is broken when it is not.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routes_citations as R
from domain.paper_writer import bibliography as B, compiler, templates as T


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A brand-new install: no documents, no stored PDFs, one empty project."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "main.tex").write_text(r"\documentclass{article}\begin{document}x\end{document}")

    monkeypatch.setattr(R, "get_document_metadata", dict)
    monkeypatch.setattr(R, "list_stored_pdfs", list)
    monkeypatch.setattr(R, "_get_project_dir", lambda pid: project_dir)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/papers")
    return TestClient(app)


class TestCitationRoutesSurviveAnEmptyLibrary:
    def test_the_citation_list_is_empty_not_broken(self, client):
        r = client.get("/api/papers/projects/p1/citations")
        assert r.status_code == 200
        assert r.json()["citations"] == []

    def test_asking_twice_is_still_fine(self, client):
        # The picker fetches on open, and it can be opened repeatedly.
        for _ in range(3):
            assert client.get("/api/papers/projects/p1/citations").status_code == 200


class TestBibliographyFunctionsOnAnEmptyDocument:
    def test_cited_keys_of_an_empty_document(self):
        # A count per key, so "nothing cited" is an empty mapping.
        assert B.cited_keys("") == {}

    def test_cited_keys_of_a_document_that_cites_nothing(self):
        assert B.cited_keys(T.render("letter", "To the editor")) == {}

    def test_bib_keys_of_an_empty_bibliography(self):
        # references.bib does not exist until something is cited; the panel
        # reads it as "" rather than special-casing the missing file.
        assert B.bib_keys("") == []


class TestWritingWithoutReading:
    """The whole point: a document exists, start to finish, with no library."""

    @pytest.fixture(autouse=True)
    def workspace(self, tmp_path, monkeypatch):
        monkeypatch.setattr(compiler, "PAPERS_DIR", tmp_path / "papers_ws")

    def test_a_project_can_be_created(self):
        proj = compiler.create_project("A letter", "letter")
        assert r"\documentclass" in proj["source"]

    def test_it_can_be_edited_and_read_back(self):
        proj = compiler.create_project("A letter", "letter")
        compiler.save_source(proj["project_id"], proj["source"] + "\n% edited")
        assert "% edited" in compiler.get_source(proj["project_id"])

    def test_it_appears_in_the_listing(self):
        proj = compiler.create_project("A letter", "letter")
        ids = [p["project_id"] for p in compiler.list_projects()]
        assert proj["project_id"] in ids

    @pytest.mark.parametrize("template_id", [t.id for t in T.ALL])
    def test_no_template_cites_anything_by_default(self, template_id):
        # A starter document that arrives citing a key nothing defines would
        # fail to compile on a machine with an empty library -- which is every
        # machine on first run.
        assert B.cited_keys(T.render(template_id, "Title")) == {}
