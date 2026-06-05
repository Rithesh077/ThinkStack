"""
ingestion domain models.

data classes representing documents and their chunks as they flow
through the ingestion pipeline from raw pdf to indexed knowledge.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DocumentMetadata:
    """metadata extracted from a research paper."""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    year: str = ""
    source: str = ""
    pages: int = 0


@dataclass
class TextChunk:
    """a segment of text from a document with positional information."""
    chunk_id: str = ""
    doc_id: str = ""
    text: str = ""
    page_number: int = 0
    chunk_index: int = 0
    token_count: int = 0


@dataclass
class Document:
    """a fully processed research document ready for knowledge base storage."""
    doc_id: str = ""
    filename: str = ""
    file_path: str = ""
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    chunks: list[TextChunk] = field(default_factory=list)
    raw_text: str = ""
    ingested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"
