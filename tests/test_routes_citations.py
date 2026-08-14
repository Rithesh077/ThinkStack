"""the two citation routes, against a library and a project on disk.

The GET must never write. That is not a style preference: it answers on every
keystroke while the author types, and a key that gets committed by being looked
at would fill references.bib with papers nobody cited.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routes_citations as R
from domain.knowledge_base.author_codec import encode_authors
from domain.paper_writer import bibliography as B


LIBRARY = {
    "a1": {
        "title": "Attention Is All You Need",
        "authors": encode_authors(["Ashish Vaswani", "Noam Shazeer"]),
        "year": "2017", "arxiv_id": "1706.03762", "doi": "",
    },
    "b2": {
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": encode_authors(["Jacob Devlin"]),
        "year": "2019", "arxiv_id": "", "doi": "10.18653/v1/N19-1423",
    },
}
FILES = [
    {"doc_id": "a1", "filename": "attention.pdf", "size_bytes": 1},
    {"doc_id": "b2", "filename": "bert.pdf", "size_bytes": 1},
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "main.tex").write_text("x")

    monkeypatch.setattr(R, "get_document_metadata", lambda: dict(LIBRARY))
    monkeypatch.setattr(R, "list_stored_pdfs", lambda: list(FILES))
    monkeypatch.setattr(R, "_get_project_dir", lambda pid: project_dir)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/papers")
    c = TestClient(app)
    c.project_dir = project_dir
    return c


def test_the_list_offers_every_document_with_the_key_it_would_get(client):
    rows = client.get("/api/papers/projects/p1/citations").json()["citations"]
    assert [r["key"] for r in rows] == ["vaswani2017attention", "devlin2019bert"]
    assert rows[0]["authors"] == ["Ashish Vaswani", "Noam Shazeer"]


def test_listing_does_not_write_the_bibliography(client):
    client.get("/api/papers/projects/p1/citations")
    assert not (client.project_dir / B.BIB_FILENAME).exists()


def test_citing_writes_the_entry_and_returns_what_to_insert(client):
    d = client.post("/api/papers/projects/p1/citations", json={"doc_id": "a1"}).json()
    assert d == {
        "key": "vaswani2017attention",
        "added": True,
        "cite": "\\cite{vaswani2017attention}",
    }
    assert "@article{vaswani2017attention," in (client.project_dir / B.BIB_FILENAME).read_text()


def test_citing_twice_is_idempotent(client):
    first = client.post("/api/papers/projects/p1/citations", json={"doc_id": "a1"}).json()
    second = client.post("/api/papers/projects/p1/citations", json={"doc_id": "a1"}).json()
    assert first["key"] == second["key"]
    assert (first["added"], second["added"]) == (True, False)


def test_a_cited_paper_is_marked_but_still_offered(client):
    """The second citation of a paper is the common case, not the edge."""
    client.post("/api/papers/projects/p1/citations", json={"doc_id": "a1"})
    rows = client.get("/api/papers/projects/p1/citations").json()["citations"]
    assert [(r["doc_id"], r["cited"]) for r in rows] == [("a1", True), ("b2", False)]


def test_a_document_with_no_title_is_listed_under_its_filename(client, monkeypatch):
    monkeypatch.setattr(R, "get_document_metadata", lambda: {"a1": {"title": "", "authors": ""}})
    monkeypatch.setattr(R, "list_stored_pdfs", lambda: [FILES[0]])
    rows = client.get("/api/papers/projects/p1/citations").json()["citations"]
    assert rows[0]["title"] == "attention"


def test_a_stored_pdf_whose_ingestion_never_finished_is_not_offered(client, monkeypatch):
    monkeypatch.setattr(R, "get_document_metadata", lambda: {"a1": LIBRARY["a1"]})
    rows = client.get("/api/papers/projects/p1/citations").json()["citations"]
    assert [r["doc_id"] for r in rows] == ["a1"]


def test_citing_something_that_is_not_in_the_library_is_a_404(client):
    assert client.post("/api/papers/projects/p1/citations", json={"doc_id": "nope"}).status_code == 404


def test_an_unknown_project_is_a_404_not_a_new_directory(client, monkeypatch, tmp_path):
    monkeypatch.setattr(R, "_get_project_dir", lambda pid: tmp_path / "absent")
    assert client.get("/api/papers/projects/absent/citations").status_code == 404
    assert not (tmp_path / "absent").exists()


def test_legacy_comma_joined_authors_are_read_rather_than_rejected(client, monkeypatch):
    """Documents ingested before the codec landed still have to be citable."""
    monkeypatch.setattr(R, "get_document_metadata", lambda: {
        "a1": {"title": "Attention Is All You Need",
               "authors": "Ashish Vaswani, Noam Shazeer", "year": "2017"},
    })
    monkeypatch.setattr(R, "list_stored_pdfs", lambda: [FILES[0]])
    rows = client.get("/api/papers/projects/p1/citations").json()["citations"]
    assert rows[0]["key"] == "vaswani2017attention"
