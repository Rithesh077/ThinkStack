"""PDF text extraction: PyMuPDF, falling back to pdfplumber.

Everything downstream sees only the text this produces. A scanned PDF with no
text layer yields nothing, and no later stage can recover from that.
"""

import logging
from pathlib import Path

import fitz
import pdfplumber

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


def get_page_count(file_path: str) -> int:
    """Page count, without extracting anything."""
    doc = fitz.open(file_path)
    count = len(doc)
    doc.close()
    return count
