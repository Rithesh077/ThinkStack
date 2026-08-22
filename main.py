"""
thinkstack application entry point.

configures and starts the fastapi server with all api routers,
static file serving for the react frontend, cors middleware,
and startup/shutdown lifecycle events.
"""

import logging
import sys
import mimetypes
from contextlib import asynccontextmanager

# ── before anything imports llama.cpp ───────────────────────────────────────
# Two things have to happen at the very top of this file, ahead of every other
# import, because both are about which shared library llama.cpp will load and
# that is decided the first time it is imported.
#
# 1. The probe. A separate process asks whether downloaded GPU libraries can
#    actually load. It has to answer and exit before the application exists,
#    since the whole point is that it is allowed to crash where the backend is
#    not.
# 2. The override. If a previous activation was verified, LLAMA_CPP_LIB_PATH is
#    set now -- llama_cpp reads it at import, and every import of it in this
#    codebase is inside a function, so this is early enough.
from config import settings  # noqa: E402  - must precede the accel import
from infrastructure import acceleration  # noqa: E402

if acceleration.PROBE_FLAG in sys.argv:
    _i = sys.argv.index(acceleration.PROBE_FLAG)
    _dir = sys.argv[_i + 1] if len(sys.argv) > _i + 1 else ""
    raise SystemExit(acceleration.run_probe(_dir))

acceleration.apply_override(settings.data_dir)
# ────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from domain.paper_writer.compiler import ProjectIdError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def register_web_mime_types() -> None:
    """Say what a JavaScript module is, before anything is asked to serve one.

    D-16: on Windows the reader could not open a PDF, reporting

        Failed to fetch dynamically imported module: .../pdf.worker.min-*.mjs

    The file is present and is served. Its CONTENT TYPE is wrong, and the chain
    that produces it is two lines:

        mimetypes.init()        -> db.read_windows_registry()
        starlette FileResponse  -> guess_type(path)[0] or "text/plain"

    Python seeds its table from the Windows registry, which usually has no
    entry for `.mjs` and often maps `.js` to text/plain. Starlette then falls
    back to text/plain, and a browser refuses to execute a module script that
    is not served as JavaScript. The asset arrives; the browser declines it.

    None of this is visible on Linux or macOS, where the built-in table answers
    correctly. That is why every suite passed while the reader was unusable on
    a third of the platforms we ship to.

    Called at import, not from a startup hook: StaticFiles is mounted below and
    can answer a request the moment the app exists.
    """
    for suffix, kind in (
        (".mjs", "text/javascript"),
        (".js", "text/javascript"),
        (".css", "text/css"),
        (".json", "application/json"),
        (".svg", "image/svg+xml"),
        (".wasm", "application/wasm"),
    ):
        mimetypes.add_type(kind, suffix)


register_web_mime_types()

from infrastructure.file_manager import ensure_directories
from infrastructure.jobs import job_queue
from infrastructure.local_vector_store import get_vector_store
from api.routes_documents import router as documents_router
from api.routes_search import router as search_router
from api.routes_graph import router as graph_router
from api.routes_analysis import router as analysis_router
from api.routes_gaps import router as gaps_router
from api.routes_system import router as system_router
from api.routes_encryption import router as encryption_router
from api.routes_papers import router as papers_router
from api.routes_paper_files import router as paper_files_router
from api.routes_citations import router as citations_router
from api.routes_models import router as models_router
from api.routes_hf import router as hf_router
from api.routes_registry import router as registry_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("thinkstack")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """handle startup and shutdown tasks."""
    logger.info("initializing thinkstack")
    ensure_directories()
    get_vector_store()
    # started here rather than at import so the worker binds to the loop that
    # actually serves requests.
    job_queue.start()
    logger.info("thinkstack ready at http://%s:%s", settings.host, settings.port)
    yield
    logger.info("shutting down thinkstack")
    await job_queue.stop()


app = FastAPI(
    title="thinkstack",
    description="offline edge-ai research assistant with local inference",
    version="0.1.0",
    lifespan=lifespan,
)

# Cross-origin access, and why it is now a short list rather than "*".
#
# "Offline" describes what this application SENDS, not who may call it. The
# backend is an HTTP server on 127.0.0.1, and the machine running it still has
# a browser with a network. Any page the user opens can issue a request to
# localhost -- nothing stops the request being made -- and the header below is
# the browser asking whether that page may READ the reply.
#
# It used to answer "*", which means anyone. With it, a page the user happened
# to visit could enumerate their library, read a paper, read a Scribe project
# and delete a document, and the reply landed in that page's JavaScript. For an
# application whose entire premise is that the documents never leave the
# machine, that is the promise failing in the exact way it claims to prevent.
#
# Production does not need CORS at all: the window navigates to 127.0.0.1:8000
# and the backend serves the interface from there, so the UI is SAME-ORIGIN.
# The only cross-origin caller that has ever been wanted is the Vite dev server
# on 3001 during `./scripts/dev.sh`, so that is the whole list.
#
# Credentials stay off. Nothing here uses cookies, and `allow_credentials` with
# a wildcard is a combination browsers refuse anyway.
DEV_ORIGINS = [
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

# A refused project id is a 404 everywhere, from one place.
#
# ProjectIdError is raised at the single point that joins an id to a path, and
# twenty-seven call sites reach the filesystem through it. Handled here rather
# than in each route because the routes catch inconsistently -- some map
# ValueError to 400, some let it become a 500 -- and a 500 carrying the message
# echoed the attempted path back to the caller, which tells a probe that its
# input reached something.
#
# 404, not 400: a caller has no business distinguishing "no such project" from
# "that was not a project id", and answering differently confirms the id shape
# matters.
@app.exception_handler(ProjectIdError)
async def _bad_project_id(request, exc):        # noqa: ARG001 - signature is fastapi's
    return JSONResponse(status_code=404, content={"detail": "project not found"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(search_router, prefix="/api/search", tags=["search"])
app.include_router(graph_router, prefix="/api/graph", tags=["graph"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])
app.include_router(gaps_router, prefix="/api/gaps", tags=["gaps"])
app.include_router(system_router, prefix="/api/system", tags=["system"])
app.include_router(encryption_router, prefix="/api/encryption", tags=["encryption"])
app.include_router(papers_router, prefix="/api/papers", tags=["papers"])
# The files inside a project. Same prefix on purpose: a project's files are part
# of the project, not a separate resource.
app.include_router(paper_files_router, prefix="/api/papers", tags=["papers"])
# Citing the library from inside a project -- also part of the project.
app.include_router(citations_router, prefix="/api/papers", tags=["papers"])
app.include_router(models_router, prefix="/api/models", tags=["models"])
# the registry shares the /api/models prefix on purpose: it is the same
# resource, split across two modules because setup and management are
# different jobs with different consequences.
app.include_router(registry_router, prefix="/api/models", tags=["models"])
# The ONLY routes that reach the internet, kept under their own prefix so
# that is obvious from the URL alone.
app.include_router(hf_router, prefix="/api/hf", tags=["huggingface"])

frontend_dist = settings.base_dir / "frontend" / "dist"

# Caching rules for the bundled UI, and why they are not optional.
#
# The desktop shell is a WebKit view pointed at http://127.0.0.1:8000, and it
# keeps an HTTP cache that OUTLIVES the application: updating the app replaces
# the binary, not the webview's cache. Nothing here sent any cache header, so
# WebKit applied *heuristic* freshness -- with no Cache-Control it may reuse a
# response for a fraction of its age without revalidating at all.
#
# index.html is the file that breaks: its name never changes, so a stale copy
# keeps referencing the PREVIOUS build's asset filenames. An updated app then
# renders the old UI, reports the old __APP_VERSION__ in the sidebar, and looks
# for all the world like the update never installed. That is exactly what was
# reported after 1.6.8 shipped -- a freshly downloaded build still showing
# v1.6.7 and the old two-button Analysis screen.
#
# Vite content-hashes everything under /assets (index-B4FzKC14.js), so a new
# build is always a new URL and can never be served stale. Those are safe to
# cache permanently; index.html must never be cached.
INDEX_CACHE = "no-store, no-cache, must-revalidate, max-age=0"
ASSET_CACHE = "public, max-age=31536000, immutable"


class _ImmutableAssets(StaticFiles):
    """StaticFiles for content-hashed bundles: cache forever, safely."""

    def is_not_modified(self, response_headers, request_headers) -> bool:
        response_headers.setdefault("cache-control", ASSET_CACHE)
        return super().is_not_modified(response_headers, request_headers)

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers.setdefault("cache-control", ASSET_CACHE)
        return response


if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    # serve hashed build assets directly
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", _ImmutableAssets(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        """serve the SPA: real files when present, else index.html.

        client-side routes (e.g. /analysis, /write) and a hard refresh on
        them fall back to index.html instead of 404ing. api paths are left
        to their routers.
        """
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        candidate = frontend_dist / full_path
        if full_path and candidate.is_file():
            # A hashed asset can be cached forever; anything else (favicon,
            # manifest, and index.html itself) must not be, because its name
            # is stable across builds.
            cache = ASSET_CACHE if full_path.startswith("assets/") else INDEX_CACHE
            return FileResponse(str(candidate), headers={"Cache-Control": cache})
        return FileResponse(
            str(frontend_dist / "index.html"),
            headers={"Cache-Control": INDEX_CACHE},
        )

if __name__ == "__main__":
    import argparse
    import multiprocessing
    import sys

    import uvicorn

    # pyinstaller re-executes the bundle for every child process; without this
    # a frozen build that spawns one would boot a second copy of the whole app.
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="thinkstack backend server")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()

    frozen = getattr(sys, "frozen", False)

    # the reloader works by respawning the interpreter and watching source
    # files on disk. a frozen build has neither, so enabling it there spawns a
    # broken child and the server never comes up -- only ever reload from
    # source. passing the app object directly (rather than "main:app") also
    # avoids a re-import of __main__ inside the bundle.
    uvicorn.run(
        app if frozen else "main:app",
        host=args.host,
        port=args.port,
        reload=settings.debug and not frozen,
    )
