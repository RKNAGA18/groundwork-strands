import logging
import uuid
import os
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Request, HTTPException

from app.config import settings
from app.models import KBUploadResponse
from app.storage.chunker import chunk_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kb", tags=["Knowledge Base"])

@router.post("/upload", response_model=KBUploadResponse)
async def upload_kb(request: Request, file: UploadFile = File(...), kb_id: Optional[str] = None):
    """Upload a document to the knowledge base.
    
    Accepts PDF, Markdown, text, and docx files. The document is chunked,
    embedded, and stored in ChromaDB. Allows uploading multiple files to the same kb_id.
    """
    logger.info(f"Received KB upload request for file: {file.filename}")
    
    allowed = {".pdf", ".md", ".txt", ".docx"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        logger.warning(f"Unsupported file type: {ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {allowed}")
    
    if kb_id is None:
        kb_id = str(uuid.uuid4())
        logger.info(f"Generated new kb_id: {kb_id}")
    else:
        logger.info(f"Using provided kb_id: {kb_id}")
    
    file_path = os.path.join(settings.UPLOAD_DIR, f"{kb_id}_{file.filename}")
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved file to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file to disk")
    
    try:
        vector_store = request.app.state.vector_store
        chunks = chunk_document(file_path, kb_id, file.filename)
        vector_store.create_kb(kb_id)
        vector_store.add_chunks(kb_id, chunks)
        logger.info(f"Successfully processed and stored KB chunks for {kb_id}")
    except Exception as e:
        logger.error(f"Failed to process and store KB {kb_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process KB document: {str(e)}")
    
    return KBUploadResponse(kb_id=kb_id)
