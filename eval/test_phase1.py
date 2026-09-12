import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.storage.chunker import chunk_document
from app.storage.vector_store import VectorStoreManager

def main():
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    kb_doc = os.path.join(eval_dir, "synthetic_kb", "data_security_policy.md")
    
    # Use proper signature: chunk_document(fpath, doc_id=fname, doc_name=fname)
    fname = os.path.basename(kb_doc)
    chunks = chunk_document(kb_doc, doc_id=fname, doc_name=fname)
    
    print(f"Chunks generated: {len(chunks)}")
    
    vs = VectorStoreManager(persist_dir=os.path.join(eval_dir, ".test_chroma"))
    kb_id = "test_kb"
    vs.create_kb(kb_id)
    vs.add_chunks(kb_id, chunks)
    
    # Test retrieval
    query = "What is the data retention policy for financial data?"
    print(f"Query: {query}")
    
    results = vs.retrieve(kb_id, query, top_k=1, threshold=0.0)
    
    for r in results:
        print(f"Score: {r.similarity}")
        print(f"Doc Name: {r.doc_name}")
        print(f"Chunk Text: {r.chunk_text[:100]}")

if __name__ == "__main__":
    main()
