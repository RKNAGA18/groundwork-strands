import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.storage.vector_store import VectorStoreManager
from app.storage.chunker import chunk_document

kb_dir = "eval/synthetic_kb"
all_chunks = []
for doc_file in sorted(os.listdir(kb_dir)):
    if doc_file.endswith(".md"):
        doc_path = os.path.join(kb_dir, doc_file)
        chunks = chunk_document(doc_path, doc_file.replace(".md", ""), doc_file)
        all_chunks.extend(chunks)

vs = VectorStoreManager()
vs.create_kb("test_kb")
vs.add_chunks("test_kb", all_chunks)

with open("eval/test_set.json") as f:
    questions = json.load(f)

scores = []
for q in questions:
    chunks = vs.retrieve("test_kb", q["text"], top_k=3, threshold=0.0)
    top_score = chunks[0].match_score if chunks else 0.0
    scores.append((q["id"], q["expected_status"], top_score))

for s in sorted(scores, key=lambda x: x[2]):
    print(f"{s[0]:<4} | Expected: {s[1]:<5} | Score: {s[2]:.4f}")
