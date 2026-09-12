import os
import sys

sys.path.insert(0, os.path.abspath("backend"))

from app.storage.vector_store import VectorStoreManager
from app.storage.chunker import chunk_document
from app.agent.strands_pipeline import set_vector_store, run_pipeline

print("\n============================================================")
print("GROUNDWORK SMOKE TEST — STRANDS GROQ PIPELINE")
print("============================================================\n")

kb_id = "eval_kb"
vsm = VectorStoreManager()
vsm.create_kb(kb_id)
kb_path = "eval/synthetic_kb"

print("[1] Loading Knowledge Base into Vector Store...")
for fname in sorted(os.listdir(kb_path)):
    if fname.endswith(".md"):
        vsm.add_chunks(kb_id, chunk_document(os.path.join(kb_path, fname)))

set_vector_store(vsm, kb_id)

smoke_suite = [
    {
        "id": "Q1",
        "question": "Is data encrypted at rest using AES-256?",
        "expected": "green"
    },
    {
        "id": "Q2",
        "question": "How quickly must access be revoked when an employee is terminated?",
        "expected": "green"
    },
    {
        "id": "Q3",
        "question": "Does the organization perform vulnerability scanning weekly?",
        "expected": "red" 
    }
]

print("\n[2] Running 3 questions through the pipeline...\n")

for item in smoke_suite:
    res = run_pipeline(item["question"])
    status = res["status"]
    match = (status == item["expected"])
    
    badge = "[PASS]" if match else "[FAIL]"
    print(f"{badge} {item['id']}: {item['question']}")
    print(f"       Status: {status.upper()} (Expected: {item['expected'].upper()})")
    print(f"       Source: {res['top_source']} | Sim: {res['top_similarity']:.4f}")
    print(f"       Verdict: {res['reason']}\n")

print("============================================================")
print("SMOKE TEST COMPLETE")
print("============================================================\n")
