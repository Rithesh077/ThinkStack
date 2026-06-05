"""
embedding service module.

provides local embedding generation using sentence-transformers.
the model is loaded once and cached in memory for efficient reuse
across embedding requests.
"""

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from config import settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """load and cache the sentence-transformer embedding model.

    the model is downloaded on first use and cached locally by the
    sentence-transformers library. subsequent calls return the
    cached instance.

    returns:
        the loaded SentenceTransformer model.
    """
    global _model
    if _model is None:
        logger.info("loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("embedding model loaded")
    return _model


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """generate embeddings for a batch of text strings.

    args:
        texts: list of text strings to embed.

    returns:
        list of embedding vectors as float lists.
    """
    model = get_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def generate_embedding(text: str) -> list[float]:
    """generate an embedding for a single text string.

    args:
        text: the text string to embed.

    returns:
        embedding vector as a float list.
    """
    return generate_embeddings([text])[0]
