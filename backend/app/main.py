import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.storage.vector_store import VectorStoreManager
from app.storage.run_store import RunStore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application."""
    logger.info("Starting up Groundwork API...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    app.state.vector_store = VectorStoreManager()
    app.state.run_store = RunStore()
    yield
    logger.info("Shutting down Groundwork API...")

app = FastAPI(
    title="Groundwork API",
    description="AI-powered security questionnaire answering",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes import kb, questionnaire, runs, health
app.include_router(kb.router)
app.include_router(questionnaire.router)
app.include_router(runs.router)
app.include_router(health.router)
