import os
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.storage.vector_store import VectorStoreManager
from app.storage.chunker import chunk_document
from app.storage.run_store import RunStore
from app.agent.strands_pipeline import set_vector_store, run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KB_ID = "eval_kb"

# ---------------------------------------------------------------------------
# Resolve all paths relative to this file so they work on Render (or any
# host) regardless of the process working directory.
#
# Layout on disk:
#   repo/
#     backend/
#       app/
#         main.py        ← __file__
#       uploads/         ← UPLOAD_DIR
#     eval/
#       synthetic_kb/    ← KB_DIR
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # backend/app/
_BACKEND = _HERE.parent                           # backend/
_REPO_ROOT = _BACKEND.parent                      # repo root

KB_DIR = _REPO_ROOT / "eval" / "synthetic_kb"
UPLOAD_DIR = _BACKEND / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)    # create on first boot


def auto_index_kb(vsm: VectorStoreManager) -> None:
    """Index the synthetic KB documents into the in-memory BM25 store."""
    vsm.create_kb(KB_ID)
    if not KB_DIR.exists():
        logger.warning("KB directory not found at %s — skipping auto-index", KB_DIR)
        return

    loaded = 0
    for doc in sorted(KB_DIR.iterdir()):
        if doc.suffix == ".md":
            chunks = chunk_document(str(doc))
            vsm.add_chunks(KB_ID, chunks)
            loaded += len(chunks)

    logger.info("Auto-indexed %d chunks from %s", loaded, KB_DIR)
    set_vector_store(vsm, KB_ID)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Groundwork API...")
    vsm = VectorStoreManager()
    run_store = RunStore()
    auto_index_kb(vsm)

    # Share singletons with all route handlers via app.state
    app.state.vector_store = vsm
    app.state.run_store = run_store
    app.state.upload_dir = str(UPLOAD_DIR)
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

from app.routes import kb, questionnaire, runs
app.include_router(kb.router)
app.include_router(questionnaire.router)
app.include_router(runs.router)
