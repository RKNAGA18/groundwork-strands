"""DrafterAgent — Strands-native agent for parsing, retrieval, and grounded drafting.

Wraps the pipeline functions (parse, retrieve, draft) as Strands @tool
functions and bundles them into a single DrafterAgent. Per AGENTS.md,
the orchestrator calls this agent per question, then passes its output
to the VerifierAgent.

The @tool functions delegate to the proven pipeline modules rather than
re-implementing logic, keeping Strands as a clean integration layer.
"""

import logging
from typing import Any

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from app.config import settings
from app.models import Question, EvidenceChunk, Draft
from app.pipeline.parse import parse_questionnaire as _parse_impl
from app.pipeline.retrieve import retrieve_evidence as _retrieve_impl
from app.pipeline.draft import draft_answer as _draft_impl
from app.llm.adapter import LLMAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons (set by orchestrator before agent invocation)
# ---------------------------------------------------------------------------
_vector_store: Any = None
_llm: LLMAdapter | None = None


def configure(vector_store: Any, llm: LLMAdapter) -> None:
    """Inject runtime dependencies before invoking the agent."""
    global _vector_store, _llm
    _vector_store = vector_store
    _llm = llm


# ---------------------------------------------------------------------------
# Strands @tool functions
# ---------------------------------------------------------------------------


@tool
def parse_questionnaire(file_path: str) -> list[dict]:
    """Split an uploaded questionnaire into discrete Question objects."""
    questions = _parse_impl(file_path)
    return [q.model_dump() for q in questions]


@tool
def retrieve_evidence(question_text: str, kb_id: str) -> list[dict]:
    """Return up to 5 EvidenceChunk objects above the 0.75 similarity
    threshold. Returns [] if none clear the bar."""
    question = Question(id="agent-q", text=question_text)
    chunks = _retrieve_impl(question, kb_id, _vector_store)
    return [c.model_dump() for c in chunks]


@tool
def draft_answer(question_text: str, evidence: list[dict]) -> dict:
    """Call the LLM with the exact Draft system prompt from AGENTS.md.
    Returns a Draft object."""
    question = Question(id="agent-q", text=question_text)
    evidence_objs = [EvidenceChunk(**e) for e in evidence]
    draft = _draft_impl(question, evidence_objs, _llm)
    return draft.model_dump()


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------


def build_drafter_agent() -> Agent:
    """Build and return a configured DrafterAgent.

    Called by the orchestrator at pipeline start. Uses Bedrock as the
    model provider via Strands' BedrockModel.
    """
    model = BedrockModel(
        model_id=settings.LLM_MODEL,
        region_name=settings.AWS_REGION,
    )
    return Agent(
        model=model,
        system_prompt=(
            "You orchestrate parsing, retrieval, and grounded "
            "drafting for one question at a time. Never answer "
            "from your own knowledge."
        ),
        tools=[parse_questionnaire, retrieve_evidence, draft_answer],
    )
