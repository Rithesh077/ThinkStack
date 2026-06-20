"""
system api routes.

provides health check, model status, and collection statistics
endpoints for monitoring the application state.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from infrastructure.ollama_client import ollama_client
from domain.knowledge_base.repository import get_collection_stats
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class SetModelRequest(BaseModel):
    """request body for switching the active llm model."""
    model: str


@router.get("/health")
async def health_check():
    """check overall system health including llm runtime connectivity.

    returns:
        system status, llm connection state, and configuration.
    """
    llm_status = await ollama_client.check_health()
    collection_stats = get_collection_stats()

    return {
        "status": "running",
        "llm": llm_status,
        "ollama": llm_status,
        "knowledge_base": collection_stats,
        "config": {
            "llm_provider": settings.llm_provider,
            "llm_model_path": str(settings.llm_model_path),
            "ollama_model": settings.ollama_model,
            "embedding_model": settings.embedding_model,
            "chunk_size": settings.chunk_size,
        },
    }


@router.get("/models")
async def list_models():
    """list all models available in the active local llm runtime.

    returns:
        list of available models and the currently configured target.
    """
    llm_status = await ollama_client.check_health()
    return {
        "provider": settings.llm_provider,
        "target_model": llm_status.get("target_model", settings.ollama_model),
        "available": llm_status.get("model_list", []),
        "target_available": llm_status.get("target_available", False),
    }


@router.post("/model")
async def set_model(request: SetModelRequest):
    """switch the active llm model at runtime (global for the app).

    for llama.cpp this releases the current model and loads the requested
    gguf file on the next generation. use a model name returned by the
    /models endpoint.

    args:
        request: the target model name (e.g. a gguf filename).

    returns:
        the now-active model and updated runtime status.
    """
    try:
        result = await ollama_client.set_model(request.model)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    llm_status = await ollama_client.check_health()
    return {
        **result,
        "provider": settings.llm_provider,
        "available": llm_status.get("model_list", []),
    }


@router.get("/stats")
async def system_stats():
    """get knowledge base statistics.

    returns:
        total documents, chunks, and document id listing.
    """
    return get_collection_stats()
