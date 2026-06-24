"""
paper writer compiler module.

handles latex compilation to pdf using pdflatex, and manages
the working directory for latex projects on disk.
"""

import logging
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

PAPERS_DIR = settings.data_dir / "papers_workspace"

# if the body uses one of these (left = regex), the package (middle) must be in
# the preamble, plus any extra setup lines (right). this lets us auto-heal
# documents whose preamble is missing a \usepackage the content relies on
# (e.g. AI-generated tikz/pgfplots charts or booktabs tables).
_PACKAGE_RULES = [
    (r"\\begin\{tikzpicture\}|\\usetikzlibrary", "tikz", []),
    (r"\\begin\{axis\}|\\addplot|pgfplots", "pgfplots", [r"\pgfplotsset{compat=1.18}"]),
    (r"\\toprule|\\midrule|\\bottomrule|\\cmidrule", "booktabs", []),
    (r"\\begin\{tabularx\}", "tabularx", []),
    (r"\\multirow", "multirow", []),
    (r"\\includegraphics", "graphicx", []),
    (r"\\(text)?color\b|\\definecolor", "xcolor", []),
    (r"\\href|\\url\b", "hyperref", []),
    (r"\{[^}]*\}\[H\]|\}\[H\]", "float", []),
    # common academic commands that otherwise throw "undefined control sequence"
    (r"\\citep|\\citet|\\citeauthor|\\citeyear", "natbib", []),
    (r"\\SI\b|\\si\b|\\num\b|\\SIrange\b|\\ang\b", "siunitx", []),
    (r"\\bm\b", "bm", []),
    (r"\\enquote\b", "csquotes", []),
    (r"\\begin\{subfigure\}|\\subcaptionbox", "subcaption", []),
    (r"\\mathbb|\\mathfrak|\\mathscr", "amssymb", []),
    (r"\\begin\{enumerate\}\[|\\begin\{itemize\}\[|\\setlist", "enumitem", []),
]

# the standard preamble shared by the starter template and the fragment
# wrapper, so a bare snippet (the AI often returns only body content) still
# compiles into a complete document.
_PREAMBLE = r"""\documentclass[12pt,a4paper]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
% --- tables ---
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{multirow}
% --- figures / charts ---
\usepackage{float}
\usepackage{caption}
\usepackage{xcolor}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric}
% --- links ---
\usepackage{hyperref}
\usepackage[margin=1in]{geometry}
"""


def _has_package(preamble: str, pkg: str) -> bool:
    """true if the preamble already loads ``pkg`` (handles grouped imports)."""
    return bool(
        re.search(r"\\usepackage(\[[^\]]*\])?\{[^}]*\b" + re.escape(pkg) + r"\b[^}]*\}", preamble)
    )


def _ensure_packages(source: str) -> str:
    """inject any \\usepackage lines the document body needs but is missing.

    keeps compilation robust when the AI generates charts/tables/figures whose
    packages were never declared (the classic "Environment tikzpicture
    undefined" error).
    """
    doc_start = source.find(r"\begin{document}")
    if doc_start == -1:
        return source  # not a complete document; leave untouched
    preamble = source[:doc_start]

    missing: list[str] = []
    extras: list[str] = []
    for pattern, pkg, extra in _PACKAGE_RULES:
        if re.search(pattern, source) and not _has_package(preamble, pkg):
            missing.append(pkg)
            extras.extend(extra)

    # pgfplots is built on tikz
    if "pgfplots" in missing and "tikz" not in missing and not _has_package(preamble, "tikz"):
        missing.insert(0, "tikz")

    missing = list(dict.fromkeys(missing))
    if not missing:
        return source

    inject = "% --- packages auto-added by thinkstack ---\n"
    inject += "".join(f"\\usepackage{{{p}}}\n" for p in missing)
    inject += "".join(f"{line}\n" for line in dict.fromkeys(extras))

    m = re.search(r"\\documentclass[^\n]*\n", preamble)
    if m:
        return source[: m.end()] + inject + source[m.end():]
    # no documentclass line found; prepend (best effort)
    return inject + source


def _ensure_compilable(source: str) -> str:
    """guarantee the source is a complete, compilable document.

    the AI is instructed to return only body content (no \\documentclass /
    \\begin{document}); if such a fragment is compiled directly you get
    "Environment figure undefined" (no class loaded). here we wrap any bare
    fragment in the standard preamble + document, then ensure packages.
    """
    s = (source or "").strip()
    if "\\documentclass" in s and "\\begin{document}" in s:
        return _ensure_packages(source)  # already a full document

    # extract the body if it is wrapped in document tags without a class,
    # otherwise treat the whole snippet as the body
    body = s
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", s, re.DOTALL)
    if m:
        body = m.group(1).strip()

    wrapped = f"{_PREAMBLE}\n\\begin{{document}}\n\n{body}\n\n\\end{{document}}\n"
    return _ensure_packages(wrapped)


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

    # auto-heal: ensure the preamble declares any packages the body relies on
    # (fixes "Environment tikzpicture undefined" and similar on older projects
    # or AI-generated content).
    try:
        source = tex_file.read_text(encoding="utf-8")
        fixed = _ensure_compilable(source)
        if fixed != source:
            tex_file.write_text(fixed, encoding="utf-8")
            logger.info("auto-wrapped / healed latex for %s", project_id)
    except Exception as e:  # noqa: BLE001 - best-effort, never block compile
        logger.warning("latex auto-heal skipped: %s", e)

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
            # extract the meaningful error from the log, INCLUDING the context
            # lines after each "!" (which carry the l.NN line number and the
            # offending control sequence) so the message is actually diagnosable.
            log_file = project_dir / "main.log"
            blocks = []
            if log_file.exists():
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                for i, line in enumerate(lines):
                    if line.startswith("!"):
                        # error line + up to 4 following lines of context
                        ctx = [l for l in lines[i:i + 5] if l.strip()]
                        blocks.append("\n".join(ctx))

            error_msg = "\n\n".join(blocks[:4]) if blocks else result.stdout[-1500:]
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
    return _PREAMBLE + rf"""
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
