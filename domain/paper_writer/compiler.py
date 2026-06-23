"""
paper writer compiler module.

handles latex compilation to pdf using pdflatex, and manages
the working directory for latex projects on disk.
"""

import logging
import shutil
import subprocess
import uuid
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

PAPERS_DIR = settings.data_dir / "papers_workspace"


def _ensure_workspace() -> Path:
    """create the papers workspace directory if it doesn't exist."""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    return PAPERS_DIR


def _get_project_dir(project_id: str) -> Path:
    """return the directory for a specific paper project."""
    return _ensure_workspace() / project_id


def create_project(name: str = "untitled") -> dict:
    """create a new paper project with a starter latex template.

    args:
        name: human-readable project name.

    returns:
        dict with project_id, name, and initial latex source.
    """
    project_id = uuid.uuid4().hex[:12]
    project_dir = _get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    template = _default_template(name)
    tex_file = project_dir / "main.tex"
    tex_file.write_text(template, encoding="utf-8")

    # persist project metadata
    meta_file = project_dir / "meta.json"
    import json
    meta_file.write_text(json.dumps({
        "project_id": project_id,
        "name": name,
    }), encoding="utf-8")

    return {
        "project_id": project_id,
        "name": name,
        "source": template,
    }


def save_source(project_id: str, source: str) -> dict:
    """save the latex source for a project.

    args:
        project_id: the project identifier.
        source: raw latex source code.

    returns:
        dict confirming the save.
    """
    project_dir = _get_project_dir(project_id)
    if not project_dir.exists():
        raise FileNotFoundError(f"project {project_id} not found")

    tex_file = project_dir / "main.tex"
    tex_file.write_text(source, encoding="utf-8")

    return {"project_id": project_id, "status": "saved"}


def compile_pdf(project_id: str) -> Path:
    """compile the project's main.tex into a pdf.

    runs pdflatex twice (for references/toc) in non-interactive mode.

    args:
        project_id: the project identifier.

    returns:
        path to the generated pdf file.

    raises:
        FileNotFoundError: if the project doesn't exist.
        RuntimeError: if pdflatex is not installed or compilation fails.
    """
    project_dir = _get_project_dir(project_id)
    tex_file = project_dir / "main.tex"

    if not tex_file.exists():
        raise FileNotFoundError(f"project {project_id} has no main.tex")

    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        raise RuntimeError(
            "pdflatex is not installed. install texlive-latex-base or equivalent."
        )

    # run pdflatex twice for cross-references
    for pass_num in range(2):
        result = subprocess.run(
            [
                pdflatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-output-directory", str(project_dir),
                str(tex_file),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(project_dir),
        )

        if result.returncode != 0:
            # extract the meaningful error from the log
            log_file = project_dir / "main.log"
            error_lines = []
            if log_file.exists():
                for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("!") or "Error" in line:
                        error_lines.append(line)

            error_msg = "\n".join(error_lines[:10]) if error_lines else result.stdout[-2000:]
            raise RuntimeError(f"pdflatex pass {pass_num + 1} failed:\n{error_msg}")

    pdf_path = project_dir / "main.pdf"
    if not pdf_path.exists():
        raise RuntimeError("pdflatex completed but no pdf was generated")

    return pdf_path


def list_projects() -> list[dict]:
    """list all paper projects.

    returns:
        list of project metadata dicts.
    """
    import json
    workspace = _ensure_workspace()
    projects = []

    for child in sorted(workspace.iterdir()):
        if not child.is_dir():
            continue
        meta_file = child / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                meta["has_pdf"] = (child / "main.pdf").exists()
                projects.append(meta)
            except Exception:
                continue

    return projects


def get_source(project_id: str) -> str:
    """read the latex source for a project.

    args:
        project_id: the project identifier.

    returns:
        the latex source string.
    """
    tex_file = _get_project_dir(project_id) / "main.tex"
    if not tex_file.exists():
        raise FileNotFoundError(f"project {project_id} not found")
    return tex_file.read_text(encoding="utf-8")


def delete_project(project_id: str) -> bool:
    """delete a paper project and all its files.

    args:
        project_id: the project identifier.

    returns:
        true if the project was deleted.
    """
    project_dir = _get_project_dir(project_id)
    if project_dir.exists():
        shutil.rmtree(project_dir)
        return True
    return False


def _default_template(title: str) -> str:
    """return a minimal academic paper latex template."""
    safe_title = title.replace("_", r"\_").replace("&", r"\&")
    return rf"""\documentclass[12pt,a4paper]{{article}}

\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{amsmath,amssymb}}
\usepackage{{graphicx}}
\usepackage{{hyperref}}
\usepackage[margin=1in]{{geometry}}

\title{{{safe_title}}}
\author{{author name}}
\date{{\today}}

\begin{{document}}

\maketitle

\begin{{abstract}}
% write your abstract here
\end{{abstract}}

\section{{introduction}}

% start writing here

\section{{methodology}}

\section{{results}}

\section{{conclusion}}

\bibliographystyle{{plain}}
\bibliography{{references}}

\end{{document}}
"""
