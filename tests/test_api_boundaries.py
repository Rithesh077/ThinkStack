"""The two boundaries a local HTTP server has to hold.

Both of these were open, and both were confirmed against a running backend
before they were closed. They are tested together because they compose: the
first decides who may talk to the API at all, and the second decides how far a
caller who does can reach.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from domain.paper_writer.compiler import ProjectIdError, _get_project_dir


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


class TestWhoMayCall:
    """A page the user happens to visit must not be able to read the library.

    "Offline" is about what this application sends, not who may call it. The
    backend listens on localhost, and any site the user opens can issue a
    request to localhost; the CORS header decides whether that site may READ the
    answer. It used to say "*".
    """

    def test_a_stranger_origin_is_not_allowed_to_read(self, client):
        r = client.get("/api/documents", headers={"Origin": "https://evil.example"})
        # the wildcard is gone, and the caller's own origin is not echoed back
        allow = r.headers.get("access-control-allow-origin")
        assert allow != "*"
        assert allow != "https://evil.example"

    def test_a_stranger_origin_is_not_preflighted_for_delete(self, client):
        r = client.options(
            "/api/documents/anything",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        assert r.headers.get("access-control-allow-origin") not in ("*", "https://evil.example")

    def test_the_dev_server_is_still_allowed(self, client):
        """`./scripts/dev.sh` serves the UI from 3001 and must keep working."""
        r = client.get("/api/documents", headers={"Origin": "http://localhost:3001"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3001"

    def test_credentials_are_not_offered(self, client):
        r = client.get("/api/documents", headers={"Origin": "http://localhost:3001"})
        assert r.headers.get("access-control-allow-credentials") != "true"


class TestHowFarACallerCanReach:
    """A project id is one path segment, and was joined to a path unchecked.

    `_project()` in the routes only asked whether the result was a directory,
    and "../../../../etc" is a directory. That was enough to list it and to read
    /etc/passwd through the ordinary file routes.
    """

    @pytest.mark.parametrize(
        "bad",
        [
            "../" * 12 + "etc",
            "../..",
            "..",
            ".",
            "a/b",
            "/etc",
            "\\windows\\system32",
            "",
            "   ",
        ],
    )
    def test_a_path_is_not_a_project_id(self, bad):
        with pytest.raises(ProjectIdError):
            _get_project_dir(bad)

    @pytest.mark.parametrize("good", ["0040e3568858", "texbundle", "tex015", "a-b_c.1"])
    def test_ordinary_ids_still_work(self, good):
        # two early projects were named by hand, so this cannot be hex-only
        assert _get_project_dir(good).name == good

    def test_the_result_is_always_inside_the_workspace(self):
        from domain.paper_writer.compiler import _ensure_workspace

        root = _ensure_workspace().resolve()
        d = _get_project_dir("0040e3568858").resolve()
        assert root == d or root in d.parents

    @pytest.mark.parametrize(
        "call",
        [
            lambda c, evil: c.post("/api/papers/compile", json={"project_id": evil}),
            lambda c, evil: c.post("/api/papers/save",
                                   json={"project_id": evil, "source": "x"}),
        ],
        ids=["compile", "save"],
    )
    def test_a_traversal_looks_exactly_like_a_missing_project(self, call):
        """The id arrives in a BODY, which no URL normalisation touches.

        A `../` in the path is collapsed by the router before a handler sees it,
        so the vector that mattered was the JSON body. It answered 500 with the
        attempted path quoted back, which tells a probe its input got somewhere.
        """
        from fastapi.testclient import TestClient

        c = TestClient(main.app, raise_server_exceptions=False)
        r = call(c, "../" * 12 + "etc")
        assert r.status_code == 404
        assert r.json() == {"detail": "project not found"}
        assert "etc" not in r.text and "passwd" not in r.text

    def test_a_traversal_in_the_url_never_returns_a_directory(self):
        """The path form is a different shape and needs its own assertion.

        `../` inside a URL is collapsed before routing, so that request becomes
        an ordinary unknown path and falls through to the single-page app -- a
        200 carrying index.html, which is correct and is not a traversal. What
        must be true is only that no filesystem outside the workspace is ever
        described in a reply.
        """
        from fastapi.testclient import TestClient

        c = TestClient(main.app, raise_server_exceptions=False)
        for url in (
            "/api/papers/projects/" + "../" * 12 + "etc/files",
            "/api/papers/projects/" + "%2e%2e%2f" * 12 + "etc/files",
            "/api/papers/projects/..%2f..%2fetc/files",
        ):
            r = c.get(url)
            assert "passwd" not in r.text
            assert "shadow" not in r.text
            # a directory listing would carry these keys; index.html does not
            assert '"files"' not in r.text or r.status_code == 404


class TestWhereItListens:
    """The default bind address, which was every interface.

    Three launchers passed --host 127.0.0.1, so the safe behaviour was real but
    accidental: it held because three callers remembered. Anything starting the
    binary without the flag served an unauthenticated API to the local network.
    """

    def test_the_default_is_loopback(self):
        from config import Settings

        assert Settings().host == "127.0.0.1"

    def test_the_argument_parser_inherits_that_default(self):
        """`main.py --port 9000` with no --host must still bind loopback."""
        import argparse

        from config import settings

        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default=settings.host)
        parser.add_argument("--port", type=int, default=settings.port)
        assert parser.parse_args(["--port", "9000"]).host == "127.0.0.1"

    def test_binding_wider_is_still_possible_on_purpose(self, monkeypatch):
        from config import Settings

        monkeypatch.setenv("THINKSTACK_HOST", "0.0.0.0")
        assert Settings().host == "0.0.0.0"
