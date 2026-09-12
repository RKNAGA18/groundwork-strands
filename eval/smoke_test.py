#!/usr/bin/env python3
"""Groundwork smoke test — prove one question works end-to-end.

Uploads one KB doc, runs 3 questions through the full pipeline
(retrieve -> draft -> verify), and prints exactly what happened.

Usage:
  cd backend
  python -m eval.smoke_test

Requires: AWS credentials (via boto3 chain) for Bedrock, OR run with
the vector store + retrieval only to test the non-LLM path.
"""

import sys
import os
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

    # Use temp chroma directory to avoid polluting the main one
    smoke_chroma = os.path.join(eval_dir, ".smoke_chroma_data")
    if os.path.exists(smoke_chroma):
        shutil.rmtree(smoke_chroma)

    print("=" * 60)
    print("GROUNDWORK SMOKE TEST — REAL PIPELINE")
    print("=" * 60)

    # Step 1: Load KB docs
    kb_dir = os.path.join(eval_dir, "synthetic_kb")
    all_chunks = []
    for doc_file in sorted(os.listdir(kb_dir)):
        if doc_file.endswith(".md"):
            doc_path = os.path.join(kb_dir, doc_file)
            chunks = chunk_document(doc_path, doc_file.replace(".md", ""), doc_file)
            all_chunks.extend(chunks)
            print(f"  [KB] {doc_file}: {len(chunks)} chunks")

    # Step 2: Index into ChromaDB with REAL embeddings
    print(f"\n[1] Indexing {len(all_chunks)} chunks into ChromaDB "
          f"(model: {settings.EMBEDDING_MODEL})...")
    vs = VectorStoreManager(persist_dir=smoke_chroma)
    kb_id = "smoke_test_kb"
    vs.create_kb(kb_id)
    vs.add_chunks(kb_id, all_chunks)
    print(f"    KB '{kb_id}' ready with real embeddings")

    # Step 3: Init LLM
    print(f"\n[2] Initializing LLM ({settings.LLM_MODEL})...")
    try:
        llm = LLMAdapter()
        print("    LLM adapter ready (AWS Bedrock)")
        llm_available = True
    except Exception as e:
        print(f"    WARNING: LLM init failed ({e})")
        print("    Running retrieval-only mode (no draft/verify)")
        llm_available = False

    # Step 4: Run test questions
    test_questions = [
        Question(
            id="smoke_1",
            text="Does the organization classify data based on sensitivity levels?",
            source_row=None,
        ),
        Question(
            id="smoke_2",
            text="How quickly must access be revoked when an employee is terminated?",
            source_row=None,
        ),
        Question(
            id="smoke_3",
            text="What physical security controls protect your datacenter?",
            source_row=None,
        ),
    ]

    print(f"\n[3] Running {len(test_questions)} questions through pipeline...\n")
    
    from app.storage.run_store import RunStore
    run_store = RunStore()
    q_dicts = [q.model_dump() for q in test_questions]
    
    run_store.create_run("smoke_run", q_dicts)
    
    try:
        from app.pipeline.graph import run_pipeline
        results = run_pipeline(q_dicts, kb_id, "smoke_run", vs, run_store)
        
        for r in results:
            print(f"  {'='*50}")
            print(f"  Q: {r.get('question_text')}")
            print(f"  ID: {r.get('question_id')}")
            print()
            print(f"  Final Text: {r.get('final_text')[:120]}...")
            print(f"  Status:  {r.get('status')}")
            print(f"  Notes:   {r.get('notes')}")
            print()
    except Exception as e:
        print(f"Pipeline failed: {e}")

    # Cleanup
    if os.path.exists(smoke_chroma):
        try:
            shutil.rmtree(smoke_chroma)
        except PermissionError:
            pass

    print("=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)
    print()
    if llm_available:
        print("Check above: smoke_1 & smoke_2 should be green/yellow,")
        print("smoke_3 should be red (no datacenter security in KB).")
    else:
        print("LLM was unavailable. Retrieval was tested.")
        print("smoke_1 & smoke_2 should have evidence, smoke_3 should not.")


if __name__ == "__main__":
    main()
