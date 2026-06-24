"""
system api routes.

provides health check, model status, and collection statistics
endpoints for monitoring the application state.
"""

import logging

from fastapi import APIRouter

from infrastructure.ollama_client import ollama_client
from domain.knowledge_base.repository import get_collection_stats
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """check overall system health including ollama connectivity.

    returns:
        system status, ollama connection state, and configuration.
    """
    ollama_status = await ollama_client.check_health()
    collection_stats = get_collection_stats()

    return {
        "status": "running",
        "ollama": ollama_status,
        "knowledge_base": collection_stats,
        "config": {
            "ollama_model": settings.ollama_model,
            "embedding_model": settings.embedding_model,
            "chunk_size": settings.chunk_size,
        },
    }


@router.get("/models")
async def list_models():
    """list all models available in the local ollama instance.

    returns:
        list of available models and the currently configured target.
    """
    ollama_status = await ollama_client.check_health()
    return {
        "target_model": settings.ollama_model,
        "available": ollama_status.get("model_list", []),
        "target_available": ollama_status.get("target_available", False),
    }


@router.get("/stats")
async def system_stats():
    """get knowledge base statistics.

    returns:
        total documents, chunks, and document id listing.
    """
    return get_collection_stats()
