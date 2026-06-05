"""
pdf parser module.

extracts text content from pdf files using pymupdf as the primary
engine with pdfplumber as a fallback for documents where pymupdf
produces poor results (scanned documents, complex layouts).
"""

import logging
from pathlib import Path

import fitz
import pdfplumber

logger = logging.getLogger(__name__)


def extract_text_pymupdf(file_path: str) -> list[dict]:
    """extract text from a pdf using pymupdf (fitz).

    args:
        file_path: absolute path to the pdf file.

    returns:
        list of dicts with page_number and text for each page.
    """
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
    """extract text from a pdf using pdfplumber.

    serves as a fallback for pdfs where pymupdf produces insufficient
    text, such as scanned documents or those with complex table layouts.

    args:
        file_path: absolute path to the pdf file.

    returns:
        list of dicts with page_number and text for each page.
    """
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
    """extract text from a pdf, trying pymupdf first then pdfplumber.

    attempts extraction with pymupdf. if the result has fewer than
    100 characters total, falls back to pdfplumber which handles
    certain pdf types better.

    args:
        file_path: absolute path to the pdf file.

    returns:
        tuple of (pages_list, full_text) where pages_list contains
        per-page text and full_text is the concatenated result.
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
    """return the total number of pages in a pdf.

    args:
        file_path: absolute path to the pdf file.

    returns:
        integer page count.
    """
    doc = fitz.open(file_path)
    count = len(doc)
    doc.close()
    return count
