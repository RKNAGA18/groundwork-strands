#!/usr/bin/env python3
"""Groundwork stress test runner.

Actually executes the 5 adversarial scenarios documented in STRESS_TESTS.md
and reports what really happened, instead of guessing.

Requires: GEMINI_API_KEY in backend/.env

Tests:
  ST-01: Contradictory evidence (two docs disagree on retention)
  ST-02: Compound question (only half is in KB)
  ST-03: Paraphrase stress (different wording, same meaning)
  ST-04: Garbage/empty file upload
  ST-05: Completely irrelevant KB
"""

import sys
import os
import json
import shutil
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.models import Question
from app.storage.chunker import chunk_document
from app.storage.vector_store import VectorStoreManager
from app.pipeline.retrieve import retrieve_evidence
from app.pipeline.draft import draft_answer
from app.pipeline.verify import verify_answer
from app.pipeline.parse import parse_questionnaire
from app.llm.adapter import LLMAdapter


def setup_temp_chroma(label: str) -> str:
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(eval_dir, f".stress_{label}_chroma")
    if os.path.exists(path):
        shutil.rmtree(path)
    settings.CHROMA_PATH = path
    return path


def cleanup(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)


def write_temp_file(name: str, content: str) -> str:
    """Write a temp markdown file and return its path."""
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_dir = os.path.join(eval_dir, ".stress_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def st01_contradictory_evidence(llm: LLMAdapter) -> dict:
    """ST-01: Two KB docs contradict on retention periods."""
    print("\n--- ST-01: Contradictory Evidence ---")
    chroma_path = setup_temp_chroma("st01")
    vs = VectorStoreManager()
    kb_id = "st01_kb"
    vs.create_kb(kb_id)

    doc_a = write_temp_file("retention_7yr.md",
        "# Data Retention Policy\n\n"
        "All transaction logs must be stored for a minimum of 7 years "
        "to comply with financial regulations.")
    doc_b = write_temp_file("retention_180d.md",
        "# Operational Log Policy\n\n"
        "Operational log data, including all transaction records, "
        "is purged after 180 days to minimize storage costs.")

    chunks_a = chunk_document(doc_a, "doc_a", "retention_7yr.md")
    chunks_b = chunk_document(doc_b, "doc_b", "retention_180d.md")
    vs.add_chunks(kb_id, chunks_a)
    vs.add_chunks(kb_id, chunks_b)

    q = Question(id="st01", text="What is the mandatory retention period for user transaction logs?", source_row=None)
    evidence = retrieve_evidence(q, kb_id, vs)
    draft = draft_answer(q, evidence, llm)
    verification = verify_answer(draft, evidence, llm)

    result = {
        "test": "ST-01",
        "scenario": "Contradictory evidence",
        "evidence_count": len(evidence),
        "evidence_chunks": [{"chunk_id": e.chunk_id, "similarity": e.similarity} for e in evidence],
        "draft_text": draft.answer_text,
        "cited_chunks": draft.cited_chunk_ids,
        "verdict": verification.verdict,
        "status": verification.status,
        "notes": verification.notes,
    }
    print(f"  Evidence: {len(evidence)} chunks")
    print(f"  Draft: {draft.answer_text[:100]}")
    print(f"  Verdict: {verification.verdict}, Status: {verification.status}")
    print(f"  Notes: {verification.notes}")
    cleanup(chroma_path)
    return result


def st02_compound_question(llm: LLMAdapter) -> dict:
    """ST-02: Compound question where only one half is supported."""
    print("\n--- ST-02: Compound Question ---")
    chroma_path = setup_temp_chroma("st02")
    vs = VectorStoreManager()
    kb_id = "st02_kb"
    vs.create_kb(kb_id)

    doc = write_temp_file("encryption_partial.md",
        "# Encryption Policy\n\n"
        "The organization enforces AES-256 encryption for all data at rest "
        "using AWS KMS for key management. Keys are rotated annually.\n\n"
        "Note: On-premise hardware security module (HSM) key escrow is "
        "not currently supported. All key management is cloud-based.")

    chunks = chunk_document(doc, "enc", "encryption_partial.md")
    vs.add_chunks(kb_id, chunks)

    q = Question(
        id="st02",
        text="Does the organization enforce AES-256 encryption at rest, and maintain hardware security modules (HSM) for on-premise key escrow?",
        source_row=None,
    )
    evidence = retrieve_evidence(q, kb_id, vs)
    draft = draft_answer(q, evidence, llm)
    verification = verify_answer(draft, evidence, llm)

    result = {
        "test": "ST-02",
        "scenario": "Compound question (half supported)",
        "evidence_count": len(evidence),
        "draft_text": draft.answer_text,
        "cited_chunks": draft.cited_chunk_ids,
        "verdict": verification.verdict,
        "status": verification.status,
        "notes": verification.notes,
    }
    print(f"  Evidence: {len(evidence)} chunks")
    print(f"  Draft: {draft.answer_text[:100]}")
    print(f"  Verdict: {verification.verdict}, Status: {verification.status}")
    print(f"  Notes: {verification.notes}")
    cleanup(chroma_path)
    return result


def st03_paraphrase(llm: LLMAdapter) -> dict:
    """ST-03: Different wording, same meaning — tests semantic retrieval."""
    print("\n--- ST-03: Paraphrase Stress ---")
    chroma_path = setup_temp_chroma("st03")
    vs = VectorStoreManager()
    kb_id = "st03_kb"
    vs.create_kb(kb_id)

    doc = write_temp_file("bcp.md",
        "# Business Continuity Plan\n\n"
        "The maximum tolerable downtime, also known as the Recovery Time "
        "Objective (RTO), is 4 hours. The organization maintains multi-region "
        "failover across US-East, US-West, and EU-West.")

    chunks = chunk_document(doc, "bcp", "bcp.md")
    vs.add_chunks(kb_id, chunks)

    # Ask the same thing in very different wording
    q = Question(
        id="st03",
        text="In the event of a catastrophic regional datacenter failure, what is the recovery window before operations are restored?",
        source_row=None,
    )
    evidence = retrieve_evidence(q, kb_id, vs)
    draft = draft_answer(q, evidence, llm)
    verification = verify_answer(draft, evidence, llm)

    top_sim = max((e.similarity for e in evidence), default=0.0)

    result = {
        "test": "ST-03",
        "scenario": "Paraphrase stress",
        "evidence_count": len(evidence),
        "top_similarity": top_sim,
        "draft_text": draft.answer_text,
        "cited_chunks": draft.cited_chunk_ids,
        "verdict": verification.verdict,
        "status": verification.status,
        "notes": verification.notes,
    }
    print(f"  Evidence: {len(evidence)} chunks (top sim: {top_sim:.4f})")
    print(f"  Draft: {draft.answer_text[:100]}")
    print(f"  Verdict: {verification.verdict}, Status: {verification.status}")
    cleanup(chroma_path)
    return result


def st04_garbage_upload() -> dict:
    """ST-04: Garbage/empty file upload — no LLM needed."""
    print("\n--- ST-04: Garbage / Empty Upload ---")
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_dir = os.path.join(eval_dir, ".stress_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    results = []

    # Test 1: Empty file
    empty_path = os.path.join(tmp_dir, "empty.xlsx")
    with open(empty_path, "wb") as f:
        pass  # 0 bytes
    try:
        questions = parse_questionnaire(empty_path)
        results.append({"input": "0-byte .xlsx", "outcome": f"Parsed {len(questions)} questions", "crashed": False})
        print(f"  Empty .xlsx: parsed {len(questions)} questions")
    except ValueError as e:
        results.append({"input": "0-byte .xlsx", "outcome": f"Graceful error: {e}", "crashed": False})
        print(f"  Empty .xlsx: Graceful error: {str(e)[:80]}")
    except Exception as e:
        results.append({"input": "0-byte .xlsx", "outcome": f"CRASH: {type(e).__name__}: {e}", "crashed": True})
        print(f"  Empty .xlsx: CRASH: {type(e).__name__}: {str(e)[:80]}")

    # Test 2: Random binary data as PDF
    garbage_path = os.path.join(tmp_dir, "garbage.pdf")
    with open(garbage_path, "wb") as f:
        f.write(os.urandom(1024))
    try:
        questions = parse_questionnaire(garbage_path)
        results.append({"input": "Random binary .pdf", "outcome": f"Parsed {len(questions)} questions", "crashed": False})
        print(f"  Garbage .pdf: parsed {len(questions)} questions")
    except ValueError as e:
        results.append({"input": "Random binary .pdf", "outcome": f"Graceful error: {e}", "crashed": False})
        print(f"  Garbage .pdf: Graceful error: {str(e)[:80]}")
    except Exception as e:
        results.append({"input": "Random binary .pdf", "outcome": f"CRASH: {type(e).__name__}: {e}", "crashed": True})
        print(f"  Garbage .pdf: CRASH: {type(e).__name__}: {str(e)[:80]}")

    # Test 3: Text file with no questions
    txt_path = os.path.join(tmp_dir, "not_a_questionnaire.txt")
    with open(txt_path, "w") as f:
        f.write("This is just a random note about nothing in particular.\n")
    try:
        questions = parse_questionnaire(txt_path)
        results.append({"input": "Plain .txt", "outcome": f"Parsed {len(questions)} questions", "crashed": False})
        print(f"  Plain .txt: parsed {len(questions)} questions")
    except ValueError as e:
        results.append({"input": "Plain .txt", "outcome": f"Graceful error: {e}", "crashed": False})
        print(f"  Plain .txt: Graceful error: {str(e)[:80]}")
    except Exception as e:
        results.append({"input": "Plain .txt", "outcome": f"CRASH: {type(e).__name__}: {e}", "crashed": True})
        print(f"  Plain .txt: CRASH: {type(e).__name__}: {str(e)[:80]}")

    return {
        "test": "ST-04",
        "scenario": "Garbage/empty file upload",
        "file_tests": results,
        "any_crashes": any(r["crashed"] for r in results),
    }


def st05_irrelevant_kb(llm: LLMAdapter) -> dict:
    """ST-05: KB is completely irrelevant to the questions."""
    print("\n--- ST-05: Completely Irrelevant KB ---")
    chroma_path = setup_temp_chroma("st05")
    vs = VectorStoreManager()
    kb_id = "st05_kb"
    vs.create_kb(kb_id)

    # KB about cooking — nothing to do with security
    doc = write_temp_file("recipes.md",
        "# Company Cafeteria Menu\n\n"
        "## Monday Special\n"
        "Grilled chicken with roasted vegetables and brown rice.\n\n"
        "## Tuesday Special\n"
        "Pasta primavera with garlic bread and mixed greens salad.\n\n"
        "## Office Supplies\n"
        "Printer paper is restocked on the first Monday of each month. "
        "Contact facilities for ergonomic keyboard requests.")

    chunks = chunk_document(doc, "recipes", "recipes.md")
    vs.add_chunks(kb_id, chunks)

    # Security questions
    questions = [
        Question(id="st05_1", text="What encryption standards do you use for data at rest?", source_row=None),
        Question(id="st05_2", text="How do you handle incident response?", source_row=None),
        Question(id="st05_3", text="Describe your access control policy.", source_row=None),
        Question(id="st05_4", text="What is your data retention period?", source_row=None),
        Question(id="st05_5", text="Do you perform regular penetration testing?", source_row=None),
    ]

    red_count = 0
    question_results = []

    for q in questions:
        evidence = retrieve_evidence(q, kb_id, vs)
        draft = draft_answer(q, evidence, llm)
        verification = verify_answer(draft, evidence, llm)

        if verification.status == "red":
            red_count += 1

        question_results.append({
            "id": q.id,
            "evidence_count": len(evidence),
            "draft_is_insufficient": draft.answer_text == "INSUFFICIENT_EVIDENCE",
            "status": verification.status,
        })
        print(f"  {q.id}: evidence={len(evidence)}, status={verification.status}")

    result = {
        "test": "ST-05",
        "scenario": "Completely irrelevant KB",
        "total_questions": len(questions),
        "red_count": red_count,
        "all_red": red_count == len(questions),
        "question_results": question_results,
    }
    print(f"  Result: {red_count}/{len(questions)} marked red")
    cleanup(chroma_path)
    return result


def main():
    # Check API key
    if not settings.GEMINI_API_KEY:
        print("FATAL: No GEMINI_API_KEY found.", file=sys.stderr)
        print("Create backend/.env with: GEMINI_API_KEY=your-key-here", file=sys.stderr)
        print("\nNote: ST-04 (garbage upload) doesn't need an API key.", file=sys.stderr)
        print("Running ST-04 only...\n", file=sys.stderr)

        result = st04_garbage_upload()
        print(f"\nST-04 result: {'No crashes' if not result['any_crashes'] else 'CRASHED'}")
        # Cleanup temp files
        eval_dir = os.path.dirname(os.path.abspath(__file__))
        tmp_dir = os.path.join(eval_dir, ".stress_tmp")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        return

    print("=" * 60)
    print("GROUNDWORK STRESS TEST RUNNER")
    print("=" * 60)

    llm = LLMAdapter()
    all_results = []

    # Run all 5 tests
    all_results.append(st01_contradictory_evidence(llm))
    all_results.append(st02_compound_question(llm))
    all_results.append(st03_paraphrase(llm))
    all_results.append(st04_garbage_upload())
    all_results.append(st05_irrelevant_kb(llm))

    # Write results
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(eval_dir, "stress_test_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults written to: {os.path.basename(output_path)}")

    # Cleanup temp files
    tmp_dir = os.path.join(eval_dir, ".stress_tmp")
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

    # Summary
    print("\n" + "=" * 60)
    print("STRESS TEST SUMMARY")
    print("=" * 60)
    for r in all_results:
        test_id = r["test"]
        scenario = r["scenario"]
        if test_id == "ST-04":
            status = "PASS" if not r["any_crashes"] else "FAIL (crashes)"
        elif test_id == "ST-05":
            status = "PASS" if r["all_red"] else f"PARTIAL ({r['red_count']}/{r['total_questions']} red)"
        elif test_id in ("ST-01", "ST-02"):
            status = "PASS" if r["status"] in ("yellow", "red") else f"CONCERN (status={r['status']})"
        elif test_id == "ST-03":
            status = "PASS" if r["status"] in ("green", "yellow") else f"FAIL (status={r['status']})"
        else:
            status = "UNKNOWN"
        print(f"  {test_id} ({scenario}): {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
