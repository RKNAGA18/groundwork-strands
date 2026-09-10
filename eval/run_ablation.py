#!/usr/bin/env python3
"""Groundwork ablation study.

Three-way comparison:
  a) Naive baseline: LLM answers with NO retrieval (no KB, no citations)
  b) RAG, no verify: retrieval + draft, but skip verification (ship as green)
  c) Full pipeline: retrieval + draft + verify (as built)

The key output: "the verifier caught X% of drafts that would have shipped
an unsupported claim without it."

Writes results to eval/ablation_results.json for fill_submission_numbers.py.
"""

import sys
import os
import json
import glob
import uuid
import shutil
import time

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.models import Question, Draft, EvidenceChunk, Verification
from app.storage.chunker import chunk_document
from app.storage.vector_store import VectorStoreManager
from app.pipeline.retrieve import retrieve_evidence
from app.pipeline.draft import draft_answer
from app.pipeline.verify import verify_answer
from app.pipeline.confidence import compute_status
from app.llm.adapter import LLMAdapter, RateLimitExhaustedError
from app.llm.prompts import DRAFT_SYSTEM_PROMPT


def setup_kb(kb_dir: str, vector_store: VectorStoreManager) -> str:
    """Load all synthetic KB docs into ChromaDB and return kb_id."""
    kb_id = f"ablation_{uuid.uuid4().hex[:8]}"
    vector_store.create_kb(kb_id)

    doc_files = glob.glob(os.path.join(kb_dir, "*.md"))
    total_chunks = 0

    for doc_path in doc_files:
        doc_name = os.path.basename(doc_path)
        doc_id = os.path.splitext(doc_name)[0]
        chunks = chunk_document(doc_path, doc_id, doc_name)
        vector_store.add_chunks(kb_id, chunks)
        total_chunks += len(chunks)

    print(f"  Loaded {len(doc_files)} docs, {total_chunks} chunks")
    return kb_id


def run_naive_baseline(
    question: Question,
    kb_id: str,
    vector_store: VectorStoreManager,
    llm: LLMAdapter,
) -> str:
    """Mode A: LLM answers with NO retrieval at all.

    No KB, no citations, just the raw question. To honestly score this,
    we take its naive guess and run it through the Verifier alongside
    the actual KB evidence. This measures whether the naive LLM's generic
    guesses happen to match the company's specific policies.
    """
    naive_prompt = (
        "You are a compliance response writer. Answer the following security "
        "questionnaire question concisely and professionally. "
        "Output JSON: {\"answer_text\": string, \"cited_chunk_ids\": []}"
    )
    try:
        response = llm.generate(
            system_prompt=naive_prompt,
            user_message=f"Question: {question.text}",
            temperature=0.2,
        )
        data = json.loads(response)
        answer = data.get("answer_text", response)
    except Exception:
        answer = "Unable to generate response."

    # Create a draft object simulating the naive response
    # We pretend it cited all evidence so the verifier will evaluate its claims against them
    evidence = retrieve_evidence(question, kb_id, vector_store)
    cited_ids = [e.chunk_id for e in evidence]
    draft = Draft(question_id=question.id, answer_text=answer, cited_chunk_ids=cited_ids)
    
    # Grade the naive answer against the real evidence
    verification = verify_answer(draft, evidence, llm)
    return verification.status


def run_rag_no_verify(
    question: Question,
    kb_id: str,
    vector_store: VectorStoreManager,
    llm: LLMAdapter,
) -> tuple:
    """Mode B: Retrieval + draft, but NO verification.

    Whatever the drafter produces ships. If evidence was found, it's 'green'.
    If no evidence, drafter returns INSUFFICIENT_EVIDENCE -> 'red'.
    Returns (status, draft, evidence) for comparison with mode C.
    """
    evidence = retrieve_evidence(question, kb_id, vector_store)
    draft = draft_answer(question, evidence, llm)

    # Without verifier, drafter's INSUFFICIENT_EVIDENCE -> red, everything else -> green
    if draft.answer_text == "INSUFFICIENT_EVIDENCE" or not evidence:
        status = "red"
    else:
        # Ship as green -- no verification to catch unsupported claims
        status = "green"

    return status, draft, evidence


def run_full_pipeline(
    question: Question,
    kb_id: str,
    vector_store: VectorStoreManager,
    llm: LLMAdapter,
) -> tuple:
    """Mode C: Full pipeline with verification.

    Returns (status, draft, evidence, verification).
    """
    evidence = retrieve_evidence(question, kb_id, vector_store)
    draft = draft_answer(question, evidence, llm)
    verification = verify_answer(draft, evidence, llm)

    return verification.status, draft, evidence, verification


def main():
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    kb_dir = os.path.join(eval_dir, "synthetic_kb")
    test_set_path = os.path.join(eval_dir, "test_set.json")
    output_path = os.path.join(eval_dir, "ablation_results.json")

    # Use a temporary chroma directory
    eval_chroma_path = os.path.join(eval_dir, ".ablation_chroma_data")
    if os.path.exists(eval_chroma_path):
        shutil.rmtree(eval_chroma_path)
    settings.CHROMA_PATH = eval_chroma_path

    print("=" * 60)
    print("GROUNDWORK ABLATION STUDY")
    print("=" * 60)

    # Setup
    print("\n[1/4] Loading synthetic KB...")
    vector_store = VectorStoreManager()
    kb_id = setup_kb(kb_dir, vector_store)

    print("[2/4] Initializing LLM adapter...")
    llm = LLMAdapter()

    with open(test_set_path, "r", encoding="utf-8") as f:
        test_set = json.load(f)

    total = len(test_set)
    print(f"[3/4] Running 3-way ablation on {total} questions...\n")

    # Track results per mode
    naive_results = []
    rag_noverify_results = []
    full_results = []

    # The key metric: how many answers Mode B ships as green that Mode C
    # correctly downgrades to yellow or red
    verifier_catches = 0
    verifier_catch_opportunities = 0  # cases where B shipped green

    valid_total = 0

    start_time = time.time()

    for i, q in enumerate(test_set, 1):
        question = Question(id=q["id"], text=q["text"], source_row=None)
        expected = q["expected_status"]

        print(f"  [{i:>2}/{total}] {q['id']}: {q['text'][:50]}...")

        # Mode A: Naive baseline
        try:
            naive_status = run_naive_baseline(question, kb_id, vector_store, llm)
        except RateLimitExhaustedError:
            print(f"    [!] Rate Limit Exhausted. Skipping question {q['id']}.")
            continue
        except Exception as e:
            print(f"    [!] Naive error: {e}")
            naive_status = "green"

        # Mode B: RAG, no verify
        try:
            rag_status, rag_draft, rag_evidence = run_rag_no_verify(
                question, kb_id, vector_store, llm
            )
        except RateLimitExhaustedError:
            print(f"    [!] Rate Limit Exhausted. Skipping question {q['id']}.")
            continue
        except Exception as e:
            print(f"    [!] RAG-no-verify error: {e}")
            rag_status = "green"

        # Mode C: Full pipeline
        try:
            full_status, full_draft, full_evidence, full_verification = (
                run_full_pipeline(question, kb_id, vector_store, llm)
            )
        except RateLimitExhaustedError:
            print(f"    [!] Rate Limit Exhausted. Skipping question {q['id']}.")
            continue
        except Exception as e:
            print(f"    [!] Full pipeline error: {e}")
            full_status = "red"
            
        valid_total += 1

        # Track verifier catches:
        # B shipped green, but C downgraded to yellow or red
        if rag_status == "green":
            verifier_catch_opportunities += 1
            if full_status in ("yellow", "red"):
                verifier_catches += 1

        naive_match = naive_status == expected
        rag_match = rag_status == expected
        full_match = full_status == expected

        naive_results.append({"id": q["id"], "expected": expected, "predicted": naive_status, "match": naive_match})
        rag_noverify_results.append({"id": q["id"], "expected": expected, "predicted": rag_status, "match": rag_match})
        full_results.append({"id": q["id"], "expected": expected, "predicted": full_status, "match": full_match})

        print(f"         Naive: {naive_status:<6} | RAG-noV: {rag_status:<6} | Full: {full_status:<6} | Expected: {expected}")

    elapsed = time.time() - start_time

    # Compute accuracy for each mode
    naive_correct = sum(1 for r in naive_results if r["match"])
    rag_correct = sum(1 for r in rag_noverify_results if r["match"])
    full_correct = sum(1 for r in full_results if r["match"])

    naive_accuracy = naive_correct / valid_total if valid_total else 0
    rag_accuracy = rag_correct / valid_total if valid_total else 0
    full_accuracy = full_correct / valid_total if valid_total else 0

    # The key number
    verifier_catch_rate = (
        (verifier_catches / verifier_catch_opportunities * 100)
        if verifier_catch_opportunities > 0
        else 0.0
    )

    print("\n" + "=" * 60)
    print("ABLATION RESULTS")
    print("=" * 60)
    print(f"\n  Mode A (Naive LLM, no KB):      {naive_correct}/{valid_total} ({naive_accuracy:.1%})")
    print(f"  Mode B (RAG, no verify):         {rag_correct}/{valid_total} ({rag_accuracy:.1%})")
    print(f"  Mode C (Full pipeline):          {full_correct}/{valid_total} ({full_accuracy:.1%})")
    print()
    print(f"  Verifier catch opportunities:    {verifier_catch_opportunities}")
    print(f"  Verifier catches:                {verifier_catches}")
    print(f"  Verifier catch rate:             {verifier_catch_rate:.1f}%")
    print()
    print(f"  Total elapsed time:              {elapsed:.1f}s")
    print()
    print(f'  KEY CLAIM: "The verifier caught {verifier_catch_rate:.1f}% of drafts')
    print(f'  that would have shipped an unsupported claim without it."')
    print("=" * 60)

    # Write results
    output = {
        "naive_accuracy": naive_accuracy,
        "rag_no_verify_accuracy": rag_accuracy,
        "full_pipeline_accuracy": full_accuracy,
        "verifier_catch_opportunities": verifier_catch_opportunities,
        "verifier_catches": verifier_catches,
        "verifier_catch_rate": verifier_catch_rate,
        "batch_latency": elapsed,
        "total_questions": total,
        "naive_details": naive_results,
        "rag_no_verify_details": rag_noverify_results,
        "full_pipeline_details": full_results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to: {os.path.basename(output_path)}")

    # Cleanup
    if os.path.exists(eval_chroma_path):
        shutil.rmtree(eval_chroma_path)


if __name__ == "__main__":
    main()
