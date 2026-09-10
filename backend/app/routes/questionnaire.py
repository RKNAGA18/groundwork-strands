import logging
import uuid
import os

from fastapi import APIRouter, UploadFile, File, Request, HTTPException

from app.config import settings
from app.models import QuestionnaireUploadResponse
from app.pipeline.parse import parse_questionnaire

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/questionnaire", tags=["Questionnaire"])

@router.post("/upload", response_model=QuestionnaireUploadResponse)
async def upload_questionnaire(request: Request, file: UploadFile = File(...)):
    """Upload a questionnaire file (XLSX or PDF) for processing."""
    logger.info(f"Received questionnaire upload request: {file.filename}")
    
    allowed = {".xlsx", ".pdf"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        logger.warning(f"Unsupported questionnaire file type: {ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    
    run_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{run_id}_{file.filename}")
    
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved questionnaire to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save questionnaire {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save questionnaire file")
    
    try:
        questions = parse_questionnaire(file_path)
        logger.info(f"Parsed {len(questions)} questions from {file.filename}")
        
        run_store = request.app.state.run_store
        run_store.create_run(run_id, [q.model_dump() for q in questions])
        logger.info(f"Created run {run_id} in RunStore")
    except ValueError as e:
        logger.error(f"Invalid questionnaire format: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to parse questionnaire or create run: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process questionnaire: {str(e)}")
    
    return QuestionnaireUploadResponse(run_id=run_id, question_count=len(questions))
