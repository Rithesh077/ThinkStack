"""Saving the compiled PDF where the author chose.

The destination is an absolute path, which is normally the shape of a
traversal. What makes it acceptable is that the CONTENT is not chosen by the
caller: this copies one file -- the project's own compiled PDF -- and nothing
else. It is not a write endpoint that happens to be pointed at a PDF.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from api.routes_papers import _pdf_name


@pytest.fixture
def client():
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.fixture
def project(tmp_path, monkeypatch):
    from domain.paper_writer import compiler

    workspace = tmp_path / "papers"
    workspace.mkdir()
    monkeypatch.setattr(compiler, "PAPERS_DIR", workspace)
    d = workspace / "abc123456789"
    d.mkdir()
    (d / "main.pdf").write_bytes(b"%PDF-1.4 fake")
    (d / "meta.json").write_text('{"project_id":"abc123456789","name":"My Paper"}')
    return d


class TestTheFilename:
    def test_it_is_the_papers_name_not_its_id(self, project, monkeypatch):
        """`0040e3568858.pdf` is a file nobody can identify a week later."""
        from domain.paper_writer import compiler

        monkeypatch.setattr(
            compiler, "list_projects",
            lambda: [{"project_id": "abc123456789", "name": "My Paper"}],
        )
        assert _pdf_name("abc123456789") == "My Paper"

    @pytest.mark.parametrize(
        "name,expected",
        [
            ('a<b>c:d"e/f\\g|h?i*j', "abcdefghij"),   # every character Windows refuses
            ("trailing dots...", "trailing dots"),
            ("   ", "fallback"),                      # nothing usable left
            ("", "fallback"),
        ],
    )
    def test_it_survives_being_put_on_any_filesystem(self, monkeypatch, name, expected):
        from domain.paper_writer import compiler

        monkeypatch.setattr(
            compiler, "list_projects",
            lambda: [{"project_id": "fallback", "name": name}],
        )
        assert _pdf_name("fallback") == expected


class TestSaving:
    def test_it_writes_where_it_was_told(self, client, project, tmp_path):
        dest = tmp_path / "out" / "paper.pdf"
        dest.parent.mkdir()
        r = client.post("/api/papers/projects/abc123456789/export-pdf",
                        json={"path": str(dest)})
        assert r.status_code == 200
        assert dest.read_bytes() == b"%PDF-1.4 fake"

    @pytest.mark.parametrize(
        "path,why",
        [
            ("relative.pdf", "not absolute"),
            ("/tmp/payload.exe", "not a pdf"),
            ("/tmp/payload.sh", "not a pdf"),
        ],
    )
    def test_it_refuses_a_destination_it_should_not_write(self, client, project, path, why):
        r = client.post("/api/papers/projects/abc123456789/export-pdf",
                        json={"path": path})
        assert r.status_code == 400, why

    def test_a_folder_that_does_not_exist_is_refused(self, client, project, tmp_path):
        r = client.post("/api/papers/projects/abc123456789/export-pdf",
                        json={"path": str(tmp_path / "nope" / "x.pdf")})
        assert r.status_code == 400

    @pytest.mark.parametrize("pid", ["..%2F..%2Fetc", "../../etc", "..%2f..%2fetc"])
    def test_a_crafted_project_never_writes(self, client, project, tmp_path, pid):
        """A traversal in the URL is collapsed before routing, so it lands on a
        path that takes no POST -- but the property that matters is not the
        status code, it is that nothing was written."""
        dest = tmp_path / "planted.pdf"
        r = client.post(f"/api/papers/projects/{pid}/export-pdf",
                        json={"path": str(dest)})
        assert r.status_code >= 400
        assert not dest.exists(), "a refused request still wrote a file"

    def test_an_uncompiled_paper_says_so(self, client, project, tmp_path):
        (project / "main.pdf").unlink()
        r = client.post("/api/papers/projects/abc123456789/export-pdf",
                        json={"path": str(tmp_path / "x.pdf")})
        assert r.status_code == 404
        assert "ompile" in r.text
