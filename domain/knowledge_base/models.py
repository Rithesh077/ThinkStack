"""
knowledge base domain models.

data classes for knowledge entries stored in the vector database,
representing the indexed and searchable form of document chunks.
"""

from dataclasses import dataclass, field


@dataclass
class KnowledgeEntry:
    """a single indexed entry in the knowledge base."""
    entry_id: str = ""
    doc_id: str = ""
    text: str = ""
    embedding: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class CollectionStats:
    """statistics about a chromadb collection."""
    name: str = ""
    count: int = 0
    document_count: int = 0
