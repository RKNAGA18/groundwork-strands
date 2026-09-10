"""Data models matching the exact contracts from AGENTS.md.

Field names are kept identical across all builds as specified in the
architecture contract.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core data contracts
# ---------------------------------------------------------------------------


class Question(BaseModel):
    """A single parsed question from a questionnaire."""

    id: str
    text: str
    source_row: Optional[int] = None


class EvidenceChunk(BaseModel):
    """A chunk of text retrieved from the knowledge base with its similarity score."""

    doc_id: str
    doc_name: str
    chunk_id: str
    chunk_text: str
    similarity: float


class Draft(BaseModel):
    """A drafted answer for a question, with citations to evidence chunks."""

    question_id: str
    answer_text: str
    cited_chunk_ids: list[str] = Field(default_factory=list)


class Verdict(str, Enum):
    """Verification verdict from the independent auditor."""

    GROUNDED = "grounded"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"


class Status(str, Enum):
    """Confidence status for display in the review UI."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class Verification(BaseModel):
    """Result of the independent verification step."""

    question_id: str
    verdict: str  # "grounded" | "partial" | "unsupported"
    status: str  # "green" | "yellow" | "red"
    notes: str = ""


class ReviewedAnswer(BaseModel):
    """A complete answer record for the review UI.

    Extends the base ReviewedAnswer contract with additional fields
    needed by the frontend (question_text, status, evidence, etc.).
    """

    question_id: str
    question_text: str = ""
    final_text: str
    human_approved: bool = False
    status: str = "red"  # "green" | "yellow" | "red"
    cited_chunk_ids: list[str] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------


class KBUploadResponse(BaseModel):
    """Response from POST /api/kb/upload."""

    kb_id: str


class QuestionnaireUploadResponse(BaseModel):
    """Response from POST /api/questionnaire/upload."""

    run_id: str
    question_count: int


class ProcessRequest(BaseModel):
    """Request body for POST /api/runs/{run_id}/process."""

    kb_id: str


class ProcessResponse(BaseModel):
    """Response from POST /api/runs/{run_id}/process."""

    status: str


class ProgressInfo(BaseModel):
    """Progress tracker for a running pipeline."""

    done: int
    total: int


class RunStatusResponse(BaseModel):
    """Response from GET /api/runs/{run_id}/status."""

    status: str
    progress: ProgressInfo


class AnswerUpdateRequest(BaseModel):
    """Request body for PATCH /api/runs/{run_id}/answers/{question_id}."""

    final_text: str
    human_approved: bool
