"""Stage 4: Independent verification of draft answers.

This module implements the verification step as a SEPARATE model call
(different invocation, not the same context as the draft). Given only
the draft and its cited chunks, it judges support as:
grounded / partial / unsupported.

If the cited evidence list is empty, the model call is skipped entirely
and the verdict is "unsupported" by rule.
"""

import json
import logging

from app.config import settings
from app.models import Draft, EvidenceChunk, Verification
from app.llm.adapter import LLMAdapter
from app.llm.prompts import VERIFY_SYSTEM_PROMPT
from app.pipeline.confidence import compute_status

logger = logging.getLogger(__name__)


def verify_answer(
    draft: Draft,
    evidence: list[EvidenceChunk],
    llm: LLMAdapter,
) -> Verification:
    """Verify a draft answer against its cited evidence passages.

    This is a SEPARATE model call from the drafting step, ensuring
    independent judgment. If no evidence was cited, the call is skipped
    and the answer is automatically marked as unsupported.

    Args:
        draft: The draft answer to verify.
        evidence: The evidence chunks that were cited in the draft.
        llm: The LLM adapter for making the verification call.

    Returns:
        A Verification object with verdict, status, and notes.
    """
    # Rule: if cited evidence list is empty, skip model call entirely
    if not draft.cited_chunk_ids or not evidence:
        logger.info(
            "Question '%s': no cited evidence — auto-unsupported (no model call)",
            draft.question_id,
        )
        return Verification(
            question_id=draft.question_id,
            verdict="unsupported",
            status="red",
            notes="No evidence was cited. Verdict is unsupported by rule, not by model judgment.",
        )

    # Build the evidence map: only include chunks that were actually cited
    cited_chunks = [c for c in evidence if c.chunk_id in draft.cited_chunk_ids]

    # If somehow cited_chunk_ids reference chunks not in the evidence list,
    # still mark as unsupported
    if not cited_chunks:
        logger.warning(
            "Question '%s': cited_chunk_ids %s not found in evidence",
            draft.question_id,
            draft.cited_chunk_ids,
        )
        return Verification(
            question_id=draft.question_id,
            verdict="unsupported",
            status="red",
            notes="Cited chunk IDs could not be matched to evidence passages.",
        )

    # Format the user message for the verifier
    evidence_text = "\n".join(
        f"[{chunk.chunk_id}]: {chunk.chunk_text}" for chunk in cited_chunks
    )

    user_message = (
        f"Draft answer: {draft.answer_text}\n\n"
        f"Cited evidence:\n{evidence_text}"
    )

    logger.info(
        "Verifying question '%s' with %d cited chunks",
        draft.question_id,
        len(cited_chunks),
    )

    try:
        response_text = llm.generate(
            system_prompt=VERIFY_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=settings.VERIFY_TEMPERATURE,
        )

        response_data = json.loads(response_text)

        verdict = response_data.get("verdict", "unsupported")
        notes = response_data.get("notes", "")

        # Validate verdict
        if verdict not in ("grounded", "partial", "unsupported"):
            logger.warning(
                "Question '%s': unexpected verdict '%s', defaulting to unsupported",
                draft.question_id,
                verdict,
            )
            verdict = "unsupported"

        # Compute the confidence status using the decision table
        top_similarity = max(
            (c.similarity for c in cited_chunks), default=0.0
        )
        status = compute_status(verdict, top_similarity)

        logger.info(
            "Question '%s': verdict=%s, top_similarity=%.3f, status=%s",
            draft.question_id,
            verdict,
            top_similarity,
            status,
        )

        return Verification(
            question_id=draft.question_id,
            verdict=verdict,
            status=status,
            notes=notes,
        )

    except json.JSONDecodeError as e:
        logger.error(
            "Failed to parse verify response for question '%s': %s",
            draft.question_id,
            str(e),
        )
        return Verification(
            question_id=draft.question_id,
            verdict="unsupported",
            status="red",
            notes=f"Verification failed: could not parse model response. {str(e)}",
        )
    except Exception as e:
        logger.error(
            "Error verifying question '%s': %s",
            draft.question_id,
            str(e),
        )
        return Verification(
            question_id=draft.question_id,
            verdict="unsupported",
            status="red",
            notes=f"Verification failed: {str(e)}",
        )
