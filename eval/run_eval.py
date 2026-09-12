#!/usr/bin/env python3
"""Groundwork pipeline evaluation — 20 labeled questions.

Runs the full dual-agent pipeline (retrieve → draft → verify) against
the synthetic KB and compares predicted status to expected status.

Reports:
- Overall accuracy
- Unsupported-detection precision, recall, F1
- Confusion matrix

Usage:
  cd backend
  python -m eval.run_eval
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


def setup_kb(kb_dir: str, vector_store: VectorStoreManager) -> str:
    """Load all synthetic KB docs into a fresh collection."""
    kb_id = "eval_kb"
    vector_store.create_kb(kb_id)
    all_chunks = []
    for doc_file in sorted(os.listdir(kb_dir)):
        if doc_file.endswith(".md"):
            doc_path = os.path.join(kb_dir, doc_file)
            chunks = chunk_document(doc_path, doc_file.replace(".md", ""), doc_file)
            all_chunks.extend(chunks)
            print(f"  Loaded {doc_file}: {len(chunks)} chunks")
    vector_store.add_chunks(kb_id, all_chunks)
    print(f"  Total: {len(all_chunks)} chunks indexed with real embeddings\n")
    return kb_id


def main():
    eval_dir = os.path.dirname(os.path.abspath(__file__))

    # Use temp chroma directory
    eval_chroma = os.path.join(eval_dir, ".eval_chroma_data")
    if os.path.exists(eval_chroma):
        shutil.rmtree(eval_chroma)

    print("=" * 60)
    print("GROUNDWORK PIPELINE EVALUATION")
    print(f"Model: {settings.LLM_MODEL}")
    print(f"Embeddings: {settings.EMBEDDING_MODEL}")
    print("=" * 60 + "\n")

    # Load test set
    test_set_path = os.path.join(eval_dir, "test_set.json")
    with open(test_set_path) as f:
        test_set = json.load(f)

    print(f"[1/3] Loading synthetic KB...")
    vector_store = VectorStoreManager(persist_dir=eval_chroma)
    kb_dir = os.path.join(eval_dir, "synthetic_kb")
    kb_id = setup_kb(kb_dir, vector_store)

    print(f"[2/3] Initializing LLM adapter...")
    llm = LLMAdapter()
    print(f"  Ready: {settings.LLM_MODEL}\n")

    print(f"[3/3] Running evaluation on {len(test_set)} questions...\n")

    start_time = time.time()
    tp = fp = fn = tn = 0
    results_log = []

    for item in test_set:
        q = Question(id=item["id"], text=item["text"])
        expected = item["expected_status"]

        try:
            # Stage 2: Retrieve
            evidence = retrieve_evidence(q, kb_id, vector_store)

            # Stage 3: Draft
            draft = draft_answer(q, evidence, llm)

            # Stage 4: Verify
            verification = verify_answer(draft, evidence, llm)
            actual = verification.status

        except Exception as e:
            print(f"  [!] Error on {q.id}: {e}")
            actual = "red"

        # Map to binary: green → supported, yellow/red → flagged
        # For the confusion matrix, treat "unsupported" (red) as positive class
        expected_is_red = expected == "red"
        actual_is_red = actual == "red"

        if actual == expected:
            label = "PASS"
        elif expected == "red" and actual == "yellow":
            label = "SOFT"  # Caught as yellow instead of red — still flagged
        elif expected == "green" and actual == "yellow":
            label = "SOFT"  # Over-cautious but not wrong
        else:
            label = "FAIL"

        print(f"  [{label}]  {q.id}: expected={expected}, actual={actual}")

        # Binary confusion: red vs not-red
        if expected_is_red and actual_is_red:
            tp += 1
        elif not expected_is_red and not actual_is_red:
            tn += 1
        elif not expected_is_red and actual_is_red:
            fp += 1
        else:  # expected red, got not-red
            fn += 1

        results_log.append({
            "id": q.id,
            "text": q.text,
            "expected": expected,
            "actual": actual,
            "evidence_count": len(evidence) if 'evidence' in dir() else 0,
        })

    elapsed = time.time() - start_time
    total = tp + fp + fn + tn

    # Exact status match accuracy
    exact_match = sum(1 for r in results_log if r["expected"] == r["actual"])
    exact_accuracy = exact_match / len(results_log) if results_log else 0

    # Binary precision/recall for red detection
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n{'=' * 60}")
    print("EVALUATION REPORT")
    print("=" * 60)
    print(f"  Total Questions:              {len(results_log)}")
    print(f"  Exact Status Match:           {exact_match}/{len(results_log)} ({exact_accuracy*100:.1f}%)")
    print(f"  Elapsed Time:                 {elapsed:.1f}s\n")
    print(f"  Unsupported Detection (positive class = red):")
    print(f"    Precision:                  {precision*100:.1f}%")
    print(f"    Recall:                     {recall*100:.1f}%")
    print(f"    F1 Score:                   {f1*100:.1f}%\n")
    print(f"  Confusion Matrix (red vs not-red):")
    print(f"    True Positives  (TP):       {tp}")
    print(f"    False Positives (FP):       {fp}")
    print(f"    False Negatives (FN):       {fn}")
    print(f"    True Negatives  (TN):       {tn}")
    print("=" * 60 + "\n")

    # Save results
    output = {
        "exact_accuracy": exact_accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "elapsed_time": elapsed,
        "llm": settings.LLM_MODEL,
        "embeddings": settings.EMBEDDING_MODEL,
        "details": results_log,
    }
    results_path = os.path.join(eval_dir, "eval_results.json")
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results written to: {results_path}")

    # Cleanup
    if os.path.exists(eval_chroma):
        shutil.rmtree(eval_chroma)


if __name__ == "__main__":
    main()
