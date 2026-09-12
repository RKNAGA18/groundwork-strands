#!/usr/bin/env python3
"""Groundwork 3-way ablation study.

Compares three modes on the same 20 questions:
  Mode A — Naive LLM (no KB, no retrieval, no verify)
  Mode B — RAG (retrieve + draft, no verify)
  Mode C — Full pipeline (retrieve + draft + verify)

This proves the value of each component. The key metric is the
verifier catch rate: of drafts that would have shipped an unsupported
claim without the verifier, how many did it catch?

Usage:
  cd backend
  python -m eval.run_ablation
"""

import json
import os
import shutil
import sys
import time

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.models import Question
from app.storage.chunker import chunk_document
from app.storage.vector_store import VectorStoreManager
from app.pipeline.retrieve import retrieve_evidence
from app.pipeline.draft import draft_answer
from app.pipeline.verify import verify_answer
from app.llm.adapter import LLMAdapter
from app.llm.prompts import DRAFT_SYSTEM_PROMPT


def setup_kb(kb_dir: str, vector_store: VectorStoreManager) -> str:
    """Load all synthetic KB docs."""
    kb_id = "ablation_kb"
    vector_store.create_kb(kb_id)
    all_chunks = []
    for doc_file in sorted(os.listdir(kb_dir)):
        if doc_file.endswith(".md"):
            doc_path = os.path.join(kb_dir, doc_file)
            chunks = chunk_document(doc_path, doc_file.replace(".md", ""), doc_file)
            all_chunks.extend(chunks)
    vector_store.add_chunks(kb_id, all_chunks)
    return kb_id


def main():
    eval_dir = os.path.dirname(os.path.abspath(__file__))

    # Use temp chroma directory
    ablation_chroma = os.path.join(eval_dir, ".ablation_chroma_data")
    if os.path.exists(ablation_chroma):
        shutil.rmtree(ablation_chroma)

    print("=" * 60)
    print("GROUNDWORK ABLATION STUDY")
    print(f"Model: {settings.LLM_MODEL}")
    print("=" * 60 + "\n")

    print("[1/4] Loading synthetic KB...")
    vector_store = VectorStoreManager(persist_dir=ablation_chroma)
    kb_dir = os.path.join(eval_dir, "synthetic_kb")
    kb_id = setup_kb(kb_dir, vector_store)
    print("  KB loaded with real embeddings.\n")

    print("[2/4] Initializing LLM adapter...")
    llm = LLMAdapter()
    print(f"  Ready: {settings.LLM_MODEL}\n")

    # Load test set
    test_set_path = os.path.join(eval_dir, "test_set.json")
    with open(test_set_path) as f:
        test_set = json.load(f)

    print(f"[3/4] Running 3-way ablation on {len(test_set)} questions...\n")

    start_time = time.time()
    mode_a_correct = mode_b_correct = mode_c_correct = 0
    catch_opportunities = catches = 0

    for item in test_set:
        q = Question(id=item["id"], text=item["text"])
        expected = item["expected_status"]

        try:
            # Mode A: Naive LLM — no KB, no retrieval
            naive_response = llm.generate(
                system_prompt="Answer yes or no based on general knowledge only.",
                user_message=f"Does a typical enterprise have this? {q.text}",
                temperature=0.0,
            )
            naive = "green" if "yes" in naive_response.lower() else "red"

            # Retrieve evidence (shared by Mode B and C)
            evidence = retrieve_evidence(q, kb_id, vector_store)

            # Mode B: RAG without verify — draft only
            draft = draft_answer(q, evidence, llm)
            if draft.answer_text == "INSUFFICIENT_EVIDENCE" or not evidence:
                rag_nov = "red"
            else:
                rag_nov = "green"

            # Mode C: Full pipeline — draft + verify
            verification = verify_answer(draft, evidence, llm)
            full = verification.status

        except Exception as e:
            print(f"  [!] Error on {q.id}: {e}")
            naive = rag_nov = full = "red"

        if naive == expected:
            mode_a_correct += 1
        if rag_nov == expected:
            mode_b_correct += 1
        if full == expected:
            mode_c_correct += 1

        # Track verifier catch rate: when RAG-noV would pass a bad answer
        # but the verifier catches it
        if expected == "red" and rag_nov == "green":
            catch_opportunities += 1
            if full == "red":
                catches += 1

        q_short = (q.text[:50] + "...") if len(q.text) > 50 else q.text
        print(f"  [{q.id:>3}] {q_short}")
        print(
            f"         Naive: {naive:<6} | RAG-noV: {rag_nov:<6} | "
            f"Full: {full:<6} | Expected: {expected}"
        )

    elapsed = time.time() - start_time
    n = len(test_set)
    catch_rate = (catches / catch_opportunities) if catch_opportunities > 0 else 0.0

    print(f"\n{'=' * 60}")
    print("ABLATION RESULTS")
    print("=" * 60)
    print(f"  Mode A (Naive LLM, no KB):      {mode_a_correct}/{n} ({mode_a_correct/n*100:.1f}%)")
    print(f"  Mode B (RAG, no verify):         {mode_b_correct}/{n} ({mode_b_correct/n*100:.1f}%)")
    print(f"  Mode C (Full pipeline):          {mode_c_correct}/{n} ({mode_c_correct/n*100:.1f}%)\n")
    print(f"  Verifier catch opportunities:    {catch_opportunities}")
    print(f"  Verifier catches:                {catches}")
    print(f"  Verifier catch rate:             {catch_rate*100:.1f}%\n")
    print(f"  Total elapsed time:              {elapsed:.1f}s\n")
    print(f'  KEY CLAIM: "The verifier caught {catch_rate*100:.1f}% of drafts')
    print('  that would have shipped an unsupported claim without it."')
    print("=" * 60 + "\n")

    results = {
        "mode_a_accuracy": mode_a_correct / n,
        "mode_b_accuracy": mode_b_correct / n,
        "mode_c_accuracy": mode_c_correct / n,
        "catch_rate": catch_rate,
        "catch_opportunities": catch_opportunities,
        "catches": catches,
        "elapsed_time": elapsed,
        "llm": settings.LLM_MODEL,
        "embeddings": settings.EMBEDDING_MODEL,
    }
    results_path = os.path.join(eval_dir, "ablation_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results written to: {results_path}")

    # Cleanup
    if os.path.exists(ablation_chroma):
        shutil.rmtree(ablation_chroma)


if __name__ == "__main__":
    main()
