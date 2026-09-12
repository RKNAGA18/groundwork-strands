import os
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.storage.vector_store import VectorStoreManager
from app.storage.chunker import chunk_document
from app.agent.strands_pipeline import set_vector_store, run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KB_ID = "eval_kb"

def auto_index_kb():
    vsm = VectorStoreManager()
    vsm.create_kb(KB_ID)
    kb_dir = "eval/synthetic_kb"
    if os.path.exists(kb_dir):
        loaded = 0
        for doc in os.listdir(kb_dir):
            if doc.endswith(".md"):
                doc_path = os.path.join(kb_dir, doc)
                chunks = chunk_document(doc_path)
                vsm.add_chunks(KB_ID, chunks)
                loaded += len(chunks)
        logger.info(f"Auto-indexed {loaded} chunks into zero-disk VectorStore.")
    set_vector_store(vsm, KB_ID)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Groundwork API...")
    auto_index_kb()
    yield

app = FastAPI(title="Groundwork API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VerifyQueryRequest(BaseModel):
    question: str

@app.post("/api/verify-single")
async def verify_single(req: VerifyQueryRequest):
    start_time = time.time()
    
    # Execute the Strands Agent SDK pipeline!
    result = run_pipeline(req.question)
    
    elapsed = round(time.time() - start_time, 2)
    
    return {
        "status": result.get("status", "red"),
        "question": req.question,
        "draft_answer": "According to policy context..." if result.get("status") == "green" else "No supported draft.",
        "reason": result.get("reason", "Pipeline error."),
        "source_doc": result.get("top_source", "None"),
        "similarity": f"{result.get('top_similarity', 0.0):.4f}",
        "latency_seconds": elapsed,
        "model": "llama-3.1-8b-instant (Groq)"
    }

@app.get("/health")
def health():
    return {"status": "ok"}
