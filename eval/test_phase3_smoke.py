import os
import sys

# Ensure root is in path so we can import 'backend' and 'eval' modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.agent.strands_pipeline import process_question, set_vector_store
from app.storage.vector_store import VectorStoreManager
from app.models import Question

test_questions = [
    Question(id="smoke_1", text="Does the organization classify data based on sensitivity levels?", source_row=1),
    Question(id="smoke_2", text="How quickly must access be revoked when an employee is terminated?", source_row=2),
    Question(id="smoke_3", text="What physical security controls protect your datacenter?", source_row=3)
]

def main():
    print("============================================================")
    print("GROUNDWORK SMOKE TEST — STRANDS GROQ PIPELINE")
    print("============================================================\n")

    print("[1] Bypassing Vector Store (using mock/empty retrieval for LLM inference test)...")
    kb_id = "smoke_test_kb"
    set_vector_store(None, kb_id)
    
    print("\n[2] Running 3 questions through the pipeline...\n")
    
    for i, q in enumerate(test_questions, 1):
        print(f"[{i}] Question: {q.text}")
        result = process_question(q.text)
        print(f"    Status: {result['status'].upper()}")
        print(f"    Reason: {result['reason']}\n")

    print("============================================================")
    print("SMOKE TEST COMPLETE")
    print("============================================================")

if __name__ == "__main__":
    main()
