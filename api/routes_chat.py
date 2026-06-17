"""
chat api routes.

exposes the retrieval-augmented chat assistant. questions are grounded
in relevant chunks retrieved from the knowledge base, so responses stay
fast and on-topic. works with either the llama.cpp or ollama runtime
via the shared llm client.
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from domain.chat.chat_service import answer_question
from domain.chat.models import ChatTurn

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    """a single conversation turn from the client."""
    role: str = "user"
    content: str = ""


class ChatRequest(BaseModel):
    """request body for the chat endpoint."""
    message: str = Field(..., min_length=1)
    doc_ids: list[str] = Field(default_factory=list)
    history: list[ChatMessage] = Field(default_factory=list)
    context: str = ""


@router.post("")
async def chat(request: ChatRequest):
    """answer a question about the user's papers using rag + the local llm.

    retrieves the most relevant chunks (optionally scoped to selected
    documents), grounds the prompt in them plus any current analysis
    context, and returns the assistant's reply with cited sources.

    args:
        request: the user message, optional document scope, prior history,
            and optional analysis context.

    returns:
        the assistant answer and the sources used to ground it.
    """
    history = [ChatTurn(role=m.role, content=m.content) for m in request.history]

    answer = await answer_question(
        question=request.message,
        doc_ids=request.doc_ids,
        history=history,
        analysis_context=request.context,
    )

    return {
        "answer": answer.answer,
        "sources": [asdict(s) for s in answer.sources],
        "used_context": answer.used_context,
    }
