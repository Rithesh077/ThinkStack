"""What the server says a JavaScript module is.

D-16: on Windows the reader could not open a PDF. The message named the file
rather than the paper:

    Could not open the pdf: Setting up fake worker failed:
    "Failed to fetch dynamically imported module:
     http://127.0.0.1:8000/assets/pdf.worker.min-rTJsTTt.mjs"

The asset is there and it is served. What is wrong is the CONTENT TYPE, and
the chain that produces it is two lines long:

    mimetypes.init()            -> db.read_windows_registry()
    starlette FileResponse      -> guess_type(path)[0] or "text/plain"

Python's mimetypes seeds itself from the Windows registry, which typically has
no entry for `.mjs` at all and frequently maps `.js` to `text/plain`. Starlette
then falls back to `text/plain`, and a browser refuses to execute a module
script that is not served as JavaScript. So the file arrives, and the browser
declines it.

Nothing about this is visible on Linux or macOS, where the built-in table
answers correctly, which is why every automated suite passed while the reader
was unusable on a third of the platforms we ship to.
"""

from __future__ import annotations

import mimetypes

import pytest

from main import register_web_mime_types

# The types a built single-page application is served as. `.mjs` is the one
# that broke; the rest are here because they fail the same way for the same
# reason, and finding out one at a time costs a release each.
WEB_TYPES = {
    ".mjs": "text/javascript",
    ".js": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".wasm": "application/wasm",
}


@pytest.fixture(autouse=True)
def restore_mimetypes():
    """Each test rewrites the process-wide table, so put it back."""
    saved = dict(mimetypes.types_map)
    yield
    mimetypes.types_map.clear()
    mimetypes.types_map.update(saved)


@pytest.mark.parametrize("ext,expected", sorted(WEB_TYPES.items()))
def test_the_type_survives_a_registry_that_disagrees(ext, expected):
    """Simulate Windows: the registry has already said something wrong."""
    mimetypes.add_type("text/plain", ext)
    assert mimetypes.guess_type(f"x{ext}")[0] == "text/plain"   # the bug

    register_web_mime_types()

    assert mimetypes.guess_type(f"x{ext}")[0] == expected


@pytest.mark.parametrize("ext,expected", sorted(WEB_TYPES.items()))
def test_the_type_survives_a_registry_that_has_never_heard_of_it(ext, expected):
    """And simulate the commoner case: `.mjs` is simply not registered."""
    mimetypes.types_map.pop(ext, None)
    mimetypes.types_map.pop(ext.upper(), None)

    register_web_mime_types()

    assert mimetypes.guess_type(f"x{ext}")[0] == expected


def test_a_module_is_never_served_as_plain_text():
    """The specific failure: a browser will not execute text/plain as a module."""
    mimetypes.add_type("text/plain", ".mjs")
    register_web_mime_types()

    kind = mimetypes.guess_type("pdf.worker.min-rTJsTTt.mjs")[0]

    assert kind is not None
    assert "javascript" in kind


def test_registering_twice_is_harmless():
    """It runs at import time, and the tests above call it again."""
    register_web_mime_types()
    register_web_mime_types()

    assert mimetypes.guess_type("x.mjs")[0] == "text/javascript"


def test_it_has_already_run_by_the_time_the_app_is_imported():
    """A fix that has to be called by hand is a fix nobody calls.

    `main` registers these at import, before StaticFiles can answer a request,
    so the guarantee holds for the packaged application and not only for a
    test that remembers to ask.
    """
    import main  # noqa: F401  -- the import is the assertion

    assert mimetypes.guess_type("x.mjs")[0] == "text/javascript"


# ─────────────────────── through the real server ───────────────────────
#
# The unit tests above prove the table is right. This proves the SERVER is,
# which is the thing the browser actually judges.

def test_the_worker_is_served_as_javascript(tmp_path):
    """The exact asset from the Windows report, through the real app."""
    import pathlib

    from fastapi.testclient import TestClient

    import main

    # Ask the app where its assets are rather than guessing from the working
    # directory: main resolves that path at import, and under the full suite
    # the cwd at import time is not necessarily the repository root.
    # Ask the app first; fall back to the repository, because the suite's
    # conftest repoints base_dir at a temporary directory and the mount is
    # resolved from it at import time.
    roots = [main.frontend_dist,
             pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist"]
    workers = next((w for r in roots for w in [sorted(r.glob("assets/*.mjs"))] if w), [])
    if not workers:
        pytest.skip("no built assets; run `npm --prefix frontend run build`")

    name = workers[0].name
    with TestClient(main.app) as client:
        response = client.get(f"/assets/{name}")
    if response.status_code == 404:
        pytest.skip("the app was imported without a built frontend to mount")

    assert response.status_code == 200
    # NOT text/plain, which is what a Windows registry without .mjs produces
    # and what a browser refuses to execute as a module.
    assert "javascript" in response.headers["content-type"]
