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

from app.config import settings
from app.models import Draft, EvidenceChunk, Verification
from app.pipeline.verify import verify_answer as _verify_impl
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
    def tool(fn):
        return fn

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
def check_claim_against_sources(draft_text: str, evidence: list[dict]) -> dict:
    """
    Independently audits a drafted answer against its cited evidence.
    
    This is the core of our "two independent agents" pitch. This agent didn't
    write the draft, so it evaluates the claims purely on whether the provided
    evidence supports them. No hallucinations allowed!
    """
    from app.llm.prompts import VERIFY_SYSTEM_PROMPT
    import json
    
    # Short-circuit: If there's no evidence, it's immediately unsupported by rule.
    # No need to pay an LLM to tell us that zero evidence equals zero support!
    if not evidence:
        logger.info("Verifier: No evidence available. Automatically flagging as unsupported.")
        return {"verdict": "unsupported", "status": "red", "notes": "No evidence available."}
        
    if _llm is None:
        raise ValueError("LLM adapter is not configured. Please check your credentials.")
        
    # Prepare the context for the auditor
    evidence_str = "\n\n".join(
        f"[{e.get('chunk_id')}]: {e.get('chunk_text', e.get('text', ''))}" 
        for e in evidence
    )
        
    # We use a temperature of 0.0 here because we want deterministic, highly analytical judgments.
    response = _llm.generate(
        system_prompt=VERIFY_SYSTEM_PROMPT,
        user_message=f"Draft: {draft_text}\n\nCited evidence:\n{evidence_str}",
        temperature=0.0,
    )
    
    # Parse the LLM's JSON judgment, handling potential markdown code blocks
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        else:
            json_str = response.strip()
            
        result = json.loads(json_str)
        
        # Determine the traffic-light status based on the verdict if the LLM didn't provide one
        if "status" not in result:
            result["status"] = "red" if result.get("verdict") == "unsupported" else "yellow" 
            
        return result
        
    except Exception as e:
        logger.error(f"Verifier failed to parse JSON from LLM: {response}")
        # When in doubt, flag it Red for human review. Safety first!
        return {"verdict": "unsupported", "status": "red", "notes": "Error parsing JSON from LLM"}


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------


def build_verifier_agent():
    """Build and return a configured VerifierAgent.

    Called by the orchestrator at pipeline start. Uses Bedrock as the
    model provider via Strands' BedrockModel.

    Returns None if strands-agents is not installed.
    """
    if not _STRANDS_AVAILABLE:
        logger.warning("strands-agents not installed — VerifierAgent unavailable")
        return None

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
