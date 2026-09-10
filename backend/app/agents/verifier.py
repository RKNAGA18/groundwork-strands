"""VerifierAgent — Strands-native agent for independent compliance auditing.

Wraps the verification function as a Strands @tool and bundles it into
a VerifierAgent. This agent operates in a SEPARATE context from the
DrafterAgent — it has no access to the original question or any context
beyond the draft and its cited evidence passages.

Critical rule: if the evidence list is empty, the model call is skipped
entirely and the verdict is 'unsupported' by rule, not by model judgment.
This saves AWS costs and mathematically prevents zero-context hallucinations.
"""

import logging
from typing import Any

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from app.config import settings
from app.models import Draft, EvidenceChunk, Verification
from app.pipeline.verify import verify_answer as _verify_impl
from app.llm.adapter import LLMAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton (set by orchestrator before agent invocation)
# ---------------------------------------------------------------------------
_llm: LLMAdapter | None = None


def configure(llm: LLMAdapter) -> None:
    """Inject runtime dependencies before invoking the agent."""
    global _llm
    _llm = llm


# ---------------------------------------------------------------------------
# Strands @tool function
# ---------------------------------------------------------------------------


@tool
def check_claim_against_sources(draft: dict, evidence: list[dict]) -> dict:
    """Call the LLM with the exact Verify system prompt from AGENTS.md.
    Returns a Verification object. If evidence is empty, skip the model
    call and return unsupported directly, per AGENTS.md."""
    draft_obj = Draft(**draft)
    evidence_objs = [EvidenceChunk(**e) for e in evidence]

    # The empty-evidence short-circuit is enforced inside _verify_impl,
    # but we also guard here for clarity and to guarantee no Bedrock call
    # is made when there is nothing to verify against.
    if not evidence_objs or not draft_obj.cited_chunk_ids:
        logger.info(
            "VerifierAgent: empty evidence for question '%s' — "
            "auto-unsupported, NO Bedrock call made.",
            draft_obj.question_id,
        )
        return Verification(
            question_id=draft_obj.question_id,
            verdict="unsupported",
            status="red",
            notes="No evidence was cited. Verdict is unsupported by rule, "
                  "not by model judgment. Bedrock call skipped.",
        ).model_dump()

    verification = _verify_impl(draft_obj, evidence_objs, _llm)
    return verification.model_dump()


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------


def build_verifier_agent() -> Agent:
    """Build and return a configured VerifierAgent.

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
            "You audit drafts against their cited sources only. "
            "You did not write the draft and have no other context."
        ),
        tools=[check_claim_against_sources],
    )
