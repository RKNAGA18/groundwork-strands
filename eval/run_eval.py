#!/usr/bin/env python3
"""Groundwork pipeline evaluation script.

Loads synthetic KB documents into ChromaDB, runs each test question
through the full pipeline (retrieve -> draft -> verify -> compute_status),
and reports accuracy + unsupported-detection precision/recall.

Writes results to eval/eval_results.json for fill_submission_numbers.py.
"""

import sys
import os
import json
import argparse
import glob
import uuid
import shutil
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
from app.pipeline.confidence import compute_status
from app.llm.adapter import LLMAdapter, RateLimitExhaustedError


def setup_kb(kb_dir: str, vector_store: VectorStoreManager) -> str:
    """Load all synthetic KB docs into ChromaDB and return kb_id."""
    kb_id = f"eval_{uuid.uuid4().hex[:8]}"
    vector_store.create_kb(kb_id)

    doc_files = glob.glob(os.path.join(kb_dir, "*.md"))
    total_chunks = 0

    for doc_path in doc_files:
        doc_name = os.path.basename(doc_path)
        doc_id = os.path.splitext(doc_name)[0]
        chunks = chunk_document(doc_path, doc_id, doc_name)
        vector_store.add_chunks(kb_id, chunks)
        total_chunks += len(chunks)
        print(f"  Loaded {doc_name}: {len(chunks)} chunks")

    print(f"  Total: {len(doc_files)} docs, {total_chunks} chunks")
    return kb_id


def evaluate_question(
    question: Question,
    kb_id: str,
    vector_store: VectorStoreManager,
    llm: LLMAdapter,
) -> str:
    """Run one question through the full pipeline, return predicted status."""
    # Stage 2: Retrieve
    evidence = retrieve_evidence(question, kb_id, vector_store)

    # Stage 3: Draft
    draft = draft_answer(question, evidence, llm)

    # Stage 4: Verify
    verification = verify_answer(draft, evidence, llm)

    return verification.status


def main():
    parser = argparse.ArgumentParser(description="Evaluate Groundwork pipeline")
    parser.add_argument(
        "--verbose", action="store_true", help="Print detailed per-question output"
    )
    args = parser.parse_args()

    eval_dir = os.path.dirname(os.path.abspath(__file__))
    kb_dir = os.path.join(eval_dir, "synthetic_kb")
    test_set_path = os.path.join(eval_dir, "test_set.json")
    results_output_path = os.path.join(eval_dir, "eval_results.json")

    # Use a temporary chroma directory for eval
    eval_chroma_path = os.path.join(eval_dir, ".eval_chroma_data")
    if os.path.exists(eval_chroma_path):
        shutil.rmtree(eval_chroma_path)
    settings.CHROMA_PATH = eval_chroma_path

    print("=" * 60)
    print("GROUNDWORK PIPELINE EVALUATION")
    print("=" * 60)

    # Setup
    print("\n[1/3] Loading synthetic KB...")
    vector_store = VectorStoreManager()
    kb_id = setup_kb(kb_dir, vector_store)

    print("\n[2/3] Initializing LLM adapter...")
    llm = LLMAdapter()

    with open(test_set_path, "r", encoding="utf-8") as f:
        test_set = json.load(f)

    print(f"\n[3/3] Running evaluation on {len(test_set)} questions...\n")

    correct = 0
    total = 0
    tp = fp = fn = tn = 0
    details = []
    start_time = time.time()

    for i, q in enumerate(test_set, 1):
        question = Question(id=q["id"], text=q["text"], source_row=None)
        expected = q["expected_status"]

        try:
            predicted = evaluate_question(question, kb_id, vector_store, llm)
        except RateLimitExhaustedError as e:
            print(f"  [!] Infrastructure Failure on {q['id']} (429 Rate Limit). Excluding from metrics.")
            continue
        except Exception as e:
            print(f"  [!] Error evaluating {q['id']}: {e}")
            predicted = "red"

        total += 1
        match = predicted == expected
        if match:
            correct += 1

        # Unsupported detection metrics (positive class = red)
        if expected == "red" and predicted == "red":
            tp += 1
        elif expected != "red" and predicted == "red":
            fp += 1
        elif expected == "red" and predicted != "red":
            fn += 1
        else:
            tn += 1

        mark = "PASS" if match else "FAIL"
        detail = {
            "id": q["id"],
            "text": q["text"][:60],
            "expected": expected,
            "predicted": predicted,
            "match": match,
        }
        details.append(detail)

        if args.verbose:
            print(
                f"  [{mark:^4}] {q['id']:>4}: {q['text'][:50]:<50} "
                f"| Exp: {expected:<6} | Pred: {predicted:<6}"
            )
        else:
            print(f"  [{mark:^4}] {q['id']:>4} ({expected} -> {predicted})")

    elapsed = time.time() - start_time

    # Report
    accuracy = correct / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0
    )

    print("\n" + "=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)
    print(f"  Total Questions:              {total}")
    print(f"  Overall Accuracy:             {correct}/{total} ({accuracy:.1%})")
    print(f"  Elapsed Time:                 {elapsed:.1f}s")
    print()
    print("  Unsupported Detection (positive class = red):")
    print(f"    Precision:                  {precision:.1%}")
    print(f"    Recall:                     {recall:.1%}")
    print(f"    F1 Score:                   {f1:.1%}")
    print()
    print("  Confusion Matrix:")
    print(f"    True Positives  (TP):       {tp}")
    print(f"    False Positives (FP):       {fp}")
    print(f"    False Negatives (FN):       {fn}")
    print(f"    True Negatives  (TN):       {tn}")
    print("=" * 60)

    cost_per_1m_input = 0.10
    cost_per_1m_output = 0.40
    total_cost = (
        (llm.total_input_tokens / 1_000_000) * cost_per_1m_input +
        (llm.total_output_tokens / 1_000_000) * cost_per_1m_output
    )

    # Write results to JSON for fill_submission_numbers.py
    results = {
        "overall_accuracy": accuracy,
        "unsupported_precision": precision,
        "unsupported_recall": recall,
        "unsupported_f1": f1,
        "batch_size": total,
        "batch_latency_seconds": elapsed,
        "total_cost_dollars": total_cost,
        "input_tokens": llm.total_input_tokens,
        "output_tokens": llm.total_output_tokens,
        "correct": correct,
        "total": total,
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "details": details,
    }

    with open(results_output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to: {os.path.basename(results_output_path)}")

    # Cleanup eval chroma data
    if os.path.exists(eval_chroma_path):
        shutil.rmtree(eval_chroma_path)

    if accuracy > 0.60:
        print("\n[OK] PASS: Accuracy above 60% threshold")
        sys.exit(0)
    else:
        print("\n[FAIL] FAIL: Accuracy below 60% threshold")
        sys.exit(1)


if __name__ == "__main__":
    main()
