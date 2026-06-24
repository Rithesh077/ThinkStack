"""
chat domain models.

data classes for the retrieval-augmented chat assistant: individual
conversation turns, cited sources, and the assembled answer.
"""

from dataclasses import dataclass, field


@dataclass
class ChatTurn:
    """a single message in a conversation history."""
    role: str = "user"  # "user" or "assistant"
    content: str = ""


@dataclass
class ChatSource:
    """a knowledge-base chunk cited as grounding for an answer."""
    doc_id: str = ""
    title: str = ""
    score: float = 0.0


@dataclass
class ChatAnswer:
    """the assistant's reply with the sources used to ground it."""
    answer: str = ""
    sources: list[ChatSource] = field(default_factory=list)
    used_context: bool = False
