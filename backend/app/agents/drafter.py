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

from app.config import settings
from app.models import Question, EvidenceChunk, Draft
from app.pipeline.parse import parse_questionnaire as _parse_impl
from app.pipeline.retrieve import retrieve_evidence as _retrieve_impl
from app.pipeline.draft import draft_answer as _draft_impl
from app.llm.adapter import LLMAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strands SDK import — graceful if not installed
# ---------------------------------------------------------------------------
try:
    from strands import Agent, tool
    from strands.models.bedrock import BedrockModel
    _STRANDS_AVAILABLE = True
except ImportError:
    _STRANDS_AVAILABLE = False
    # Define no-op decorator so module still loads
    def tool(fn):
        return fn

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
    """
    Drafts a compliance answer using ONLY the provided evidence.
    
    We act as a strict compliance officer here. If we don't have evidence,
    we don't guess. We just say INSUFFICIENT_EVIDENCE.
    """
    from app.llm.prompts import DRAFT_SYSTEM_PROMPT
    import json
    
    # Short-circuit: If retrieval found nothing, don't waste money or time calling the LLM.
    if not evidence:
        logger.info("No evidence provided. Short-circuiting to INSUFFICIENT_EVIDENCE.")
        return {"answer_text": "INSUFFICIENT_EVIDENCE", "cited_chunk_ids": []}
        
    # Format the evidence nicely for the LLM to read, including chunk IDs for citation
    context = "\n\n".join(
        f"[{e.get('chunk_id')}]: {e.get('chunk_text', e.get('text', ''))}" 
        for e in evidence
    )
    
    if _llm is None:
        raise ValueError("LLM adapter is not configured. Please check your credentials.")
        
    # Ask the LLM to draft the answer. We use a low temperature (0.2) to keep it factual and grounded.
    response = _llm.generate(
        system_prompt=DRAFT_SYSTEM_PROMPT,
        user_message=f"Question: {question_text}\n\nEvidence:\n{context}",
        temperature=0.2,
    )
    
    # The LLM is instructed to return JSON. Sometimes it wraps it in markdown blocks (```json ... ```).
    # We carefully unwrap it here so our pipeline doesn't break.
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        else:
            json_str = response.strip()
            
        return json.loads(json_str)
        
    except Exception as e:
        logger.error(f"Oops! Failed to parse the LLM's JSON response. Raw output: {response}")
        # Graceful fallback: If parsing fails, we treat it as an error but keep the pipeline alive.
        return {"answer_text": "ERROR_PARSING_JSON", "cited_chunk_ids": []}


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------


def build_drafter_agent():
    """Build and return a configured DrafterAgent.

    Called by the orchestrator at pipeline start. Uses Bedrock as the
    model provider via Strands' BedrockModel.

    Returns None if strands-agents is not installed.
    """
    if not _STRANDS_AVAILABLE:
        logger.warning("strands-agents not installed — DrafterAgent unavailable")
        return None

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
