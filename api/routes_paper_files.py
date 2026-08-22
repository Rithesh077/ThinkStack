"""the files inside a paper project.

Mounted under the papers router, so every path here is
``/api/papers/projects/{project_id}/files...``.

A project has always been a directory; until now `main.tex` was the only thing
in it anything could reach, which is why `\\includegraphics{chart.png}` failed --
the compiler runs with the project directory as its working directory, so the
relative path was correct and the file simply was not there.

Every route resolves its argument through `files.safe_path`, which is the
security boundary: the webview can reach this API, so a filename is untrusted
input. Nothing here builds a path by concatenation.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from domain.paper_writer import files as F
from domain.paper_writer import links as L
from domain.paper_writer.compiler import ProjectIdError, _get_project_dir

logger = logging.getLogger(__name__)
router = APIRouter()


def _project(project_id: str) -> Path:
    """the project directory, or 404.

    A malformed id is answered with the same 404 as a missing one, deliberately:
    the caller has no business distinguishing "no such project" from "that was
    not a project id", and saying which would confirm to a probe that the id
    shape matters.
    """
    try:
        d = _get_project_dir(project_id)
    except ProjectIdError:
        raise HTTPException(status_code=404, detail="project not found") from None
    if not d.is_dir():
        raise HTTPException(status_code=404, detail="project not found")
    return d


def _tree(project_dir: Path) -> list[dict]:
    return [
        {"path": e.path, "name": e.name, "is_dir": e.is_dir, "size": e.size}
        for e in F.list_files(project_dir)
    ]


def _guard(fn):
    """turn a FileError into a 400 carrying its own message.

    `FileError` is raised only with text already written for a person, so it is
    passed through verbatim. Anything else is a bug here and must not have its
    internals shown to the webview.
    """
    try:
        return fn()
    except F.FileError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("project file operation failed: %s", e)
        raise HTTPException(status_code=500, detail="That did not work.") from e


class WriteRequest(BaseModel):
    path: str
    content: str = ""


class PathRequest(BaseModel):
    path: str


class MoveRequest(BaseModel):
    src: str
    dst: str


@router.get("/projects/{project_id}/files")
async def api_list_files(project_id: str):
    """every author-visible file, build artefacts excluded."""
    return {"project_id": project_id, "files": _tree(_project(project_id))}


@router.get("/projects/{project_id}/files/content")
async def api_read_file(project_id: str, path: str):
    """the text of one file, for the editor."""
    d = _project(project_id)
    return {"path": path, "content": _guard(lambda: F.read_file(d, path))}


@router.put("/projects/{project_id}/files/content")
async def api_write_file(project_id: str, req: WriteRequest):
    """create or overwrite a text file. Returns the tree, so the UI re-renders
    from one authoritative payload rather than patching a local guess."""
    d = _project(project_id)
    entry = _guard(lambda: F.write_file(d, req.path, req.content))
    return {"file": entry.__dict__, "files": _tree(d)}


@router.post("/projects/{project_id}/files/upload")
async def api_upload_file(
    project_id: str,
    file: UploadFile = File(...),
    dest: str = "",
):
    """store an uploaded figure or data file.

    `dest` is the folder to drop it into ("" = the project root). The name is
    taken from the upload but never trusted -- a browser can send
    `../../../evil.png` as a filename, so it goes through the same boundary as
    everything else, and an existing file is never silently replaced.
    """
    d = _project(project_id)
    raw = await file.read()

    name = Path(file.filename or "").name  # strip any directory the client sent
    if not name:
        raise HTTPException(status_code=400, detail="That upload had no file name.")

    target = f"{dest.strip('/')}/{name}" if dest.strip("/") else name
    free = _guard(lambda: F.unique_name(d, target))
    entry = _guard(lambda: F.write_bytes(d, free, raw))
    return {"file": entry.__dict__, "files": _tree(d)}


@router.get("/projects/{project_id}/files/raw")
async def api_raw_file(project_id: str, path: str):
    """serve a file as-is, so the tree can preview a figure."""
    d = _project(project_id)
    target = _guard(lambda: F.safe_path(d, path))
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(target, filename=target.name)


@router.post("/projects/{project_id}/files/folder")
async def api_make_folder(project_id: str, req: PathRequest):
    d = _project(project_id)
    entry = _guard(lambda: F.make_dir(d, req.path))
    return {"file": entry.__dict__, "files": _tree(d)}


@router.post("/projects/{project_id}/files/move")
async def api_move(project_id: str, req: MoveRequest):
    """rename, or move into a folder -- drag-and-drop inside the tree."""
    d = _project(project_id)
    entry = _guard(lambda: F.move_path(d, req.src, req.dst))
    return {"file": entry.__dict__, "files": _tree(d)}


@router.post("/projects/{project_id}/files/copy")
async def api_copy(project_id: str, req: MoveRequest):
    """the paste half of copy/paste."""
    d = _project(project_id)
    entry = _guard(lambda: F.copy_path(d, req.src, req.dst))
    return {"file": entry.__dict__, "files": _tree(d)}


@router.delete("/projects/{project_id}/files")
async def api_delete(project_id: str, path: str):
    d = _project(project_id)
    _guard(lambda: F.delete_path(d, path))
    return {"files": _tree(d)}


# ── files that live outside the project ──────────────────────────────────
#
# These take an ABSOLUTE path, which is the one thing `safe_path` exists to
# refuse everywhere else. Three things make that acceptable here and they are
# worth naming, because "it takes a path from the caller" is otherwise exactly
# the shape of the traversal this codebase already had once.
#
#   1. The caller is the application. The API answers only same-origin requests
#      and the Vite dev server; a page the user happens to visit cannot reach
#      it. That was not true until recently and is the reason this feature
#      waited for it.
#   2. The path comes from a native file dialog the user drove, not from
#      anything the interface invented.
#   3. Only suffixes a LaTeX project can use are linkable, so the files worth
#      stealing are not reachable through it: ~/.ssh/id_rsa has no suffix, and
#      neither does /etc/passwd.
#
# The file itself is never modified. A link is a note about where something is.


class LinkRequest(BaseModel):
    path: str


class RelinkRequest(BaseModel):
    path: str


class CopyInRequest(BaseModel):
    dest: str = ""


@router.get("/projects/{project_id}/links")
async def api_list_links(project_id: str):
    """Every linked file, with where it actually is now.

    Resolution happens on read rather than on a schedule: a file that moved
    while the application was closed is discovered the next time anyone looks,
    which is the moment it matters.
    """
    d = _project(project_id)
    return {"links": [r.as_dict() for r in L.list_links(d)]}


@router.post("/projects/{project_id}/links")
async def api_add_link(project_id: str, req: LinkRequest):
    d = _project(project_id)
    link = _guard(lambda: L.add_link(d, req.path))
    return {"link": link.as_dict(), "links": [r.as_dict() for r in L.list_links(d)]}


@router.put("/projects/{project_id}/links/{link_id}")
async def api_relink(project_id: str, link_id: str, req: RelinkRequest):
    """The user has found a file we lost. Remember where, keep the same link."""
    d = _project(project_id)
    link = _guard(lambda: L.relink(d, link_id, req.path))
    return {"link": link.as_dict(), "links": [r.as_dict() for r in L.list_links(d)]}


@router.delete("/projects/{project_id}/links/{link_id}")
async def api_remove_link(project_id: str, link_id: str):
    """Forget the link. The file is not ours and is not touched."""
    d = _project(project_id)
    _guard(lambda: L.remove(d, link_id))
    return {"links": [r.as_dict() for r in L.list_links(d)]}


@router.post("/projects/{project_id}/links/{link_id}/copy")
async def api_copy_link_in(project_id: str, link_id: str, req: CopyInRequest):
    """Take a copy into the project, on purpose."""
    d = _project(project_id)
    rel = _guard(lambda: L.copy_into_project(d, link_id, req.dest))
    return {"path": rel, "files": _tree(d), "links": [r.as_dict() for r in L.list_links(d)]}


@router.get("/projects/{project_id}/links/{link_id}/raw")
async def api_link_raw(project_id: str, link_id: str):
    """Serve a linked file, so a figure can be previewed where it lies."""
    d = _project(project_id)
    link = _guard(lambda: L.get(d, link_id))
    r = L.resolve(d, link)
    if r.resolved is None:
        raise HTTPException(status_code=404, detail=f"{link.name} cannot be found.")
    return FileResponse(r.resolved, filename=r.resolved.name)
