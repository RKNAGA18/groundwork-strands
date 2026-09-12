"""Plain-Python orchestrator — replaces LangGraph with ThreadPoolExecutor.

Architecture (per AGENTS.md):
    For each question:  retrieve → draft → verify → ReviewedAnswer
    Across questions:   ThreadPoolExecutor(max_workers=settings.MAX_WORKERS)

The DrafterAgent and VerifierAgent from the Strands agents module are
configured at pipeline start. Each question flows through the proven
sequential pipeline; parallelism happens across questions only.

Graceful degradation: if any single question fails (JSON parse error,
Bedrock timeout, etc.), it produces a red/unsupported ReviewedAnswer
with the error in `notes` — the pipeline NEVER crashes on a bad row.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.config import settings
from app.models import (
    Question,
    EvidenceChunk,
    Draft,
    ReviewedAnswer,
)
from app.pipeline.retrieve import retrieve_evidence
from app.pipeline.draft import draft_answer
from app.pipeline.verify import verify_answer
from app.llm.adapter import LLMAdapter
from app.storage.vector_store import VectorStoreManager
from app.storage.run_store import RunStore
try:
    from app.agents.drafter import configure as configure_drafter
    from app.agents.verifier import configure as configure_verifier
    _strands_available = True
except ImportError:
    _strands_available = False

logger = logging.getLogger(__name__)

# ANSI codes for demo-visible logs
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_RED = "\033[91m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


# ---------------------------------------------------------------------------
# Per-question processing (runs inside a thread)
# ---------------------------------------------------------------------------


def _process_question(
    q_dict: dict,
    kb_id: str,
    run_id: str,
    vector_store: VectorStoreManager,
    run_store: RunStore,
    llm: LLMAdapter,
) -> dict:
    """
    Process a single question using actual Strands Agent invocation.
    
    This function acts as the safety net for each row in the batch. By running
    the Drafter and Verifier agents inside a try/except block, we ensure that
    one malformed question or API timeout doesn't crash the entire 200-question batch.
    """
    question = Question(**q_dict)
    logger.info(
        "%s▶  Processing question '%s': %s%s",
        _CYAN, question.id, question.text[:80], _RESET,
    )

    try:
        from app.agents.drafter import build_drafter_agent
        from app.agents.verifier import build_verifier_agent
        import json
        
        # Instantiate our two independent agents
        drafter = build_drafter_agent()
        verifier = build_verifier_agent()
        
        if drafter is None or verifier is None:
            raise RuntimeError("Strands agents not available. Ensure strands-agents is installed.")

        # ==========================================
        # STAGE 1: DRAFTING
        # ==========================================
        logger.info("Question '%s': Invoking DrafterAgent", question.id)
        draft_result = drafter(
            f"Answer this question using retrieve_evidence and draft_answer. Knowledge base ID: {kb_id}. Question: {question.text}"
        )
        logger.info("Question '%s': DrafterAgent completed", question.id)

        # ==========================================
        # STAGE 2: VERIFICATION
        # ==========================================
        # Notice we pass the Draft output directly to the Verifier. The Verifier
        # has a totally separate context and system prompt—it acts as an auditor.
        logger.info("Question '%s': Invoking VerifierAgent", question.id)
        verification_result = verifier(
            f"Audit this draft against its evidence: {draft_result}"
        )
        logger.info("Question '%s': VerifierAgent completed", question.id)
        
        # Extract the Red/Yellow/Green status from the auditor's result.
        # Since it might be JSON embedded in text, we parse it safely.
        status = "yellow"  # fallback status if we aren't sure
        verdict_text = str(verification_result)
        
        try:
            # Look for a JSON block in the verdict text
            if "{" in verdict_text and "}" in verdict_text:
                json_str = verdict_text[verdict_text.find("{"):verdict_text.rfind("}")+1]
                v_data = json.loads(json_str)
                status = v_data.get("status", "yellow")
        except Exception:
            pass # We'll just stick with the 'yellow' fallback for safety

        # Assemble the final answer for the user review dashboard
        reviewed = ReviewedAnswer(
            question_id=question.id,
            question_text=question.text,
            final_text=str(draft_result),
            human_approved=False,
            status=status,
            cited_chunk_ids=[],
            evidence=[],
            notes=str(verification_result),
        )

    except Exception as exc:
        # ==========================================
        # GRACEFUL DEGRADATION
        # ==========================================
        # If Bedrock goes down, or the question is completely garbled, we catch it here.
        # We flag it as 'red' (unsupported) so a human will review it, rather than throwing an error page.
        logger.error(
            "%s✖  Question '%s' FAILED — degrading to red: %s%s",
            _RED, question.id, exc, _RESET,
        )
        reviewed = ReviewedAnswer(
            question_id=question.id,
            question_text=question.text,
            final_text="INSUFFICIENT_EVIDENCE",
            human_approved=False,
            status="red",
            cited_chunk_ids=[],
            evidence=[],
            notes=f"Pipeline error (graceful degradation): {exc}",
        )

    # Update progress in the run store (best-effort) so the frontend UI can show a progress bar
    if run_store is not None:
        try:
            current = run_store.get_status(run_id)
            done = current["progress"]["done"] + 1
            run_store.update_progress(run_id, done)
        except Exception:
            pass

    return reviewed.model_dump()


def run_pipeline(
    questions: list[dict],
    kb_id: str,
    run_id: str,
    vector_store: VectorStoreManager,
    run_store: RunStore,
) -> list[dict]:
    """Run the full pipeline on a batch of questions using Strands Agents."""
    llm = LLMAdapter()

    # Configure Strands agent modules with runtime dependencies
    if _strands_available:
        configure_drafter(vector_store, llm)
        configure_verifier(llm)

    if run_store is not None:
        run_store.set_status(run_id, "processing")
        run_store.update_progress(run_id, 0)

    logger.info(
        "%s%s🚀  Starting pipeline for run %s: %d questions against KB %s  "
        "(max_workers=%d)%s",
        _BOLD, _CYAN, run_id, len(questions), kb_id,
        settings.MAX_WORKERS, _RESET,
    )

    results: list[dict] = []

    try:
        with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    _process_question,
                    q, kb_id, run_id, vector_store, run_store, llm,
                ): q
                for q in questions
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        if run_store is not None:
            run_store.set_results(run_id, results)

        logger.info(
            "%s%s✅  Pipeline completed for run %s: %d results%s",
            _BOLD, _GREEN, run_id, len(results), _RESET,
        )

        return results

    except Exception as e:
        logger.error(
            "%s❌  Pipeline failed for run %s: %s%s",
            _RED, run_id, str(e), _RESET,
        )
        if run_store is not None:
            run_store.set_status(run_id, "failed")
        raise
