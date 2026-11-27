"""Request and response schemas for the tax Q&A endpoints."""
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConfidenceLevel(str, Enum):
    high = "high"   # All citations verified against retrieved chunks
    low = "low"     # No citations found, cross-check failed, or out-of-KB answer


# ---------------------------------------------------------------------------
# Citation object
# ---------------------------------------------------------------------------

class CitationObject(BaseModel):
    """A single legal citation extracted from a RAG answer, with supporting evidence."""
    model_config = ConfigDict(extra="forbid")

    section: str = Field(
        description="Cited section reference, e.g. 'Section 10(13A)'"
    )
    excerpt: str = Field(
        description=(
            "Short supporting text excerpt from the retrieved chunk where this citation "
            "was found. Empty string if citation cross-check failed (section not found in chunks)."
        )
    )


# ---------------------------------------------------------------------------
# Chat models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """Single turn in a conversation history for a session."""
    model_config = ConfigDict(extra="forbid")

    role: str = Field(description="'user' or 'assistant'")
    content: str
    timestamp: Optional[str] = None  # ISO 8601 — set server-side


# ---------------------------------------------------------------------------
# QueryRequest — incoming client request
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """
    A tax question. If profile_id is given, a numeric profile summary (no PII)
    is added to the prompt.
    """
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Tax question from the user. Must be at least 3 characters.",
    )
    profile_id: Optional[str] = None  # Links query to a financial profile for context
    session_id: str = Field(
        ...,
        min_length=1,
        description="Session identifier for chat history and FAQ cache.",
    )


# ---------------------------------------------------------------------------
# Session events and RAGResponse
# ---------------------------------------------------------------------------

class SessionEventRequest(BaseModel):
    """Incoming UI interaction event from the frontend."""
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, description="Session identifier")
    event_type: str = Field(
        ...,
        description="Category of action: tab_click, page_view, pdf_download, regime_compare, chat_open",
    )
    payload: dict = Field(default_factory=dict, description="Structured event context — no PII")


class RAGResponse(BaseModel):
    """
    An answer with its citations.

    confidence is "high" only when there is at least one citation and every
    cited section appears in the retrieved chunks. cached means it came from
    the FAQ cache. answer_mode is "general" when no relevant chunks were found
    and the model answered from general knowledge.
    """
    model_config = ConfigDict(extra="ignore")  # allow retrieved_chunks to pass through

    answer: str
    citations: List[CitationObject] = Field(
        default_factory=list,
        description=(
            "Legal citations extracted from the answer. Each citation has 'section' "
            "(e.g. 'Section 10(13A)') and 'excerpt' (supporting chunk text). "
            "Validated via regex + cross-check against retrieved chunks."
        ),
    )
    confidence: ConfidenceLevel
    cached: bool = Field(
        default=False,
        description="True if this response was served from Redis FAQ cache.",
    )
    answer_mode: Literal["kb_grounded", "general"] = Field(
        default="kb_grounded",
        description="'kb_grounded' if answered from IT Act KB; 'general' if KB had no relevant chunks.",
    )


__all__ = [
    "CitationObject",
    "ConfidenceLevel",
    "ChatMessage",
    "QueryRequest",
    "RAGResponse",
    "SessionEventRequest",
]
