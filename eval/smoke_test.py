#!/usr/bin/env python3
"""Groundwork smoke test — first real API call.

Uploads one KB doc, runs 3 questions through the full pipeline
(retrieve -> draft -> verify), and prints what actually happened.

Usage:
  cd backend
  python -m eval.smoke_test

Requires: GEMINI_API_KEY in backend/.env
"""

import sys
import os
import json
import shutil

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


def main():
    eval_dir = os.path.dirname(os.path.abspath(__file__))

    # Check API key
    if not settings.GEMINI_API_KEY:
        print("FATAL: No GEMINI_API_KEY found.", file=sys.stderr)
        print("Create backend/.env with: GEMINI_API_KEY=your-key-here", file=sys.stderr)
        sys.exit(1)

    # Use temp chroma directory
    smoke_chroma = os.path.join(eval_dir, ".smoke_chroma_data")
    if os.path.exists(smoke_chroma):
        shutil.rmtree(smoke_chroma)
    settings.CHROMA_PATH = smoke_chroma

    print("=" * 60)
    print("GROUNDWORK SMOKE TEST - FIRST REAL API CALL")
    print("=" * 60)

    # Step 1: Load one KB doc
    kb_doc = os.path.join(eval_dir, "synthetic_kb", "data_security_policy.md")
    print(f"\n[1] Chunking: {os.path.basename(kb_doc)}")
    chunks = chunk_document(kb_doc, "data_sec", "data_security_policy.md")
    print(f"    {len(chunks)} chunks created")

    # Step 2: Index into ChromaDB
    print("[2] Indexing into ChromaDB...")
    vs = VectorStoreManager()
    kb_id = "smoke_test_kb"
    vs.create_kb(kb_id)
    vs.add_chunks(kb_id, chunks)
    print(f"    KB '{kb_id}' ready")

    # Step 3: Init LLM
    print(f"[3] Initializing LLM ({settings.LLM_MODEL})...")
    llm = LLMAdapter()
    print("    LLM ready")

    # Step 4: Run 3 test questions
    test_questions = [
        Question(id="smoke_1", text="What is your data retention policy?", source_row=None),
        Question(id="smoke_2", text="How do you classify sensitive data?", source_row=None),
        Question(id="smoke_3", text="What physical security controls protect your datacenter?", source_row=None),
    ]

    print(f"\n[4] Running {len(test_questions)} questions through full pipeline...\n")

    for q in test_questions:
        print(f"  --- {q.id}: {q.text} ---")

        # Retrieve
        evidence = retrieve_evidence(q, kb_id, vs)
        print(f"  Retrieved: {len(evidence)} chunks")
        for e in evidence:
            print(f"    [{e.chunk_id}] sim={e.similarity:.4f} ({e.chunk_text[:60]}...)")

        # Draft
        print(f"  Drafting...")
        draft = draft_answer(q, evidence, llm)
        print(f"  Draft answer: {draft.answer_text[:100]}...")
        print(f"  Cited chunks: {draft.cited_chunk_ids}")

        # Verify
        print(f"  Verifying...")
        verification = verify_answer(draft, evidence, llm)
        print(f"  Verdict: {verification.verdict}")
        print(f"  Status:  {verification.status}")
        print(f"  Notes:   {verification.notes}")
        print()

    # Cleanup
    if os.path.exists(smoke_chroma):
        shutil.rmtree(smoke_chroma)

    print("=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)
    print("\nIf all 3 questions produced valid JSON responses above,")
    print("the LLM integration is working. Check that:")
    print("  - smoke_1 & smoke_2 should be green or yellow (KB has this)")
    print("  - smoke_3 should be red (KB has no datacenter security)")


if __name__ == "__main__":
    main()
