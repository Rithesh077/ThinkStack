"""PDF text extraction: PyMuPDF, falling back to pdfplumber.

Everything downstream sees only the text this produces. A scanned PDF with no
text layer yields nothing, and no later stage can recover from that.
"""

import logging
from pathlib import Path

import fitz
import pdfplumber

from domain.ingestion.models import PageLayout, TextSpan

logger = logging.getLogger(__name__)


def extract_text_pymupdf(file_path: str) -> list[dict]:
    """Per-page `{page_number, text}`. Empty pages are skipped."""
    pages = []
    doc = fitz.open(file_path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        if text.strip():
            pages.append({
                "page_number": page_num + 1,
                "text": text.strip(),
            })
    doc.close()
    return pages


def extract_text_pdfplumber(file_path: str) -> list[dict]:
    """Same shape as extract_text_pymupdf. Slower, but reads scanned pages and
    complex table layouts PyMuPDF returns blank."""
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({
                    "page_number": i + 1,
                    "text": text.strip(),
                })
    return pages


def extract_text(file_path: str) -> tuple[list[dict], str]:
    """Returns `(pages, full_text)`.

    Under 100 characters from PyMuPDF means the page is almost certainly an
    image, so pdfplumber gets a turn before giving up.
    """
    pages = extract_text_pymupdf(file_path)
    total_text = " ".join(p["text"] for p in pages)

    if len(total_text) < 100:
        logger.info("pymupdf yielded minimal text, falling back to pdfplumber")
        pages = extract_text_pdfplumber(file_path)
        total_text = " ".join(p["text"] for p in pages)

    logger.info(
        "extracted %d pages, %d characters from %s",
        len(pages),
        len(total_text),
        Path(file_path).name,
    )
    return pages, total_text


def extract_layout(file_path: str, max_pages: int = 1) -> list[PageLayout]:
    """Pages as positioned spans, for callers that need font size and position.

    `extract_text` flattens a PDF into a string, which throws away the only
    signal that reliably marks a title: it is the biggest text on page 1.
    This keeps that signal.

    Defaults to page 1 because that is where bibliographic data lives, and
    building spans for a 30-page paper is work nobody asked for.
    """
    layouts = []
    doc = fitz.open(file_path)
    try:
        for page_num in range(min(max_pages, len(doc))):
            page = doc.load_page(page_num)
            spans = []
            for block in page.get_text("dict").get("blocks", []):
                # type 1 blocks are images; they have no lines.
                for line in block.get("lines", []):
                    # dir is the writing direction unit vector. (1, 0) is
                    # left-to-right; anything else is rotated.
                    horizontal = tuple(line.get("dir", (1, 0))) == (1, 0)
                    for span in line.get("spans", []):
                        # Kept unstripped on purpose. A span carries its own
                        # spacing, and whether "ADAM" was typeset as one span
                        # or as "A" + "DAM" in two sizes is only recoverable
                        # from that -- stripping forces a guess later.
                        text = span.get("text", "")
                        if not text.strip():
                            continue
                        x0, y0, x1, y1 = span.get("bbox", (0, 0, 0, 0))
                        spans.append(TextSpan(
                            text=text,
                            size=round(float(span.get("size", 0.0)), 1),
                            x0=x0, y0=y0, x1=x1, y1=y1,
                            horizontal=horizontal,
                            baseline=float(span.get("origin", (0.0, y1))[1]),
                        ))
            layouts.append(PageLayout(
                page_number=page_num + 1,
                width=page.rect.width,
                height=page.rect.height,
                spans=spans,
            ))
    finally:
        doc.close()
    return layouts


def get_page_count(file_path: str) -> int:
    """Page count, without extracting anything."""
    doc = fitz.open(file_path)
    count = len(doc)
    doc.close()
    return count
