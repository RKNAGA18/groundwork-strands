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
from app.agents.drafter import configure as configure_drafter
from app.agents.verifier import configure as configure_verifier

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
    """Process a single question through retrieve → draft → verify.

    Graceful degradation: any exception produces a red/unsupported
    ReviewedAnswer so the overall batch never crashes on one bad row.
    """
    question = Question(**q_dict)
    logger.info(
        "%s▶  Processing question '%s': %s%s",
        _CYAN, question.id, question.text[:80], _RESET,
    )

    try:
        # --- Stage 2: Retrieve ---
        evidence = retrieve_evidence(question, kb_id, vector_store)
        logger.info(
            "Question '%s': retrieved %d evidence chunks",
            question.id, len(evidence),
        )

        # --- Stage 3: Draft ---
        draft = draft_answer(question, evidence, llm)
        logger.info(
            "Question '%s': draft generated (len=%d, cited=%d)",
            question.id, len(draft.answer_text), len(draft.cited_chunk_ids),
        )

        # --- Stage 4: Verify ---
        verification = verify_answer(draft, evidence, llm)
        logger.info(
            "Question '%s': verdict=%s, status=%s",
            question.id, verification.verdict, verification.status,
        )

        # --- Build ReviewedAnswer ---
        reviewed = ReviewedAnswer(
            question_id=question.id,
            question_text=question.text,
            final_text=draft.answer_text,
            human_approved=False,
            status=verification.status,
            cited_chunk_ids=draft.cited_chunk_ids,
            evidence=[e.model_dump() for e in evidence],
            notes=verification.notes,
        )

    except Exception as exc:
        # ---- Graceful degradation: never crash on a single row ----
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

    # Update progress (best-effort)
    if run_store is not None:
        try:
            current = run_store.get_status(run_id)
            done = current["progress"]["done"] + 1
            run_store.update_progress(run_id, done)
        except Exception:
            pass

    return reviewed.model_dump()


# ---------------------------------------------------------------------------
# Public entry point (same signature as the old LangGraph version)
# ---------------------------------------------------------------------------


def run_pipeline(
    questions: list[dict],
    kb_id: str,
    run_id: str,
    vector_store: VectorStoreManager,
    run_store: RunStore,
) -> list[dict]:
    """Run the full pipeline on a batch of questions.

    This is the main entry point called by the API route. It replaces
    the previous LangGraph StateGraph with a plain ThreadPoolExecutor.

    Args:
        questions: List of question dicts (matching Question schema).
        kb_id: The knowledge base ID to search against.
        run_id: The run ID for progress tracking.
        vector_store: The vector store manager instance.
        run_store: The run store instance for progress updates.

    Returns:
        A list of ReviewedAnswer dicts.
    """
    llm = LLMAdapter()

    # Configure Strands agent modules with runtime dependencies
    configure_drafter(vector_store, llm)
    configure_verifier(llm)

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
                result = future.result()  # exceptions already caught inside
                results.append(result)

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
        run_store.set_status(run_id, "failed")
        raise
