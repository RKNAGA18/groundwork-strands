import logging
import os
from typing import Dict, Any, List

from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from fastapi.responses import FileResponse
from docx import Document as DocxDocument

from app.config import settings
from app.models import (
    ProcessRequest, ProcessResponse, RunStatusResponse,
    ProgressInfo, AnswerUpdateRequest
)
from app.pipeline.graph import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs", tags=["Runs"])


def _run_pipeline_background(
    questions: list[dict],
    kb_id: str,
    run_id: str,
    vector_store,
    run_store,
) -> None:
    """Background task that runs the LangGraph pipeline."""
    try:
        run_pipeline(questions, kb_id, run_id, vector_store, run_store)
    except Exception as e:
        logger.error("Background pipeline failed for run %s: %s", run_id, str(e))


@router.post("/{run_id}/process", response_model=ProcessResponse)
async def process_run(
    run_id: str,
    body: ProcessRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Start processing a questionnaire run against a knowledge base."""
    logger.info("Process run requested for run_id: %s, kb_id: %s", run_id, body.kb_id)
    run_store = request.app.state.run_store
    vector_store = request.app.state.vector_store

    try:
        run_store.get_status(run_id)
    except KeyError:
        logger.warning("Run %s not found", run_id)
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    questions = run_store.get_questions(run_id)

    background_tasks.add_task(
        _run_pipeline_background,
        questions,
        body.kb_id,
        run_id,
        vector_store,
        run_store,
    )

    logger.info("Pipeline launched in background for run %s (%d questions)", run_id, len(questions))
    return ProcessResponse(status="processing")

@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: str, request: Request):
    """Get the current status and progress of a run."""
    logger.info(f"Status requested for run_id: {run_id}")
    run_store = request.app.state.run_store
    
    try:
        status_data = run_store.get_status(run_id)
    except KeyError:
        logger.warning(f"Run {run_id} not found")
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        
    return RunStatusResponse(
        status=status_data["status"],
        progress=ProgressInfo(**status_data["progress"])
    )

@router.get("/{run_id}/results", response_model=List[Dict[str, Any]])
async def get_run_results(run_id: str, request: Request):
    """Get the full results of a run including all answers."""
    logger.info(f"Results requested for run_id: {run_id}")
    run_store = request.app.state.run_store
    
    try:
        results = run_store.get_results(run_id)
    except KeyError:
        logger.warning(f"Run {run_id} not found")
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        
    return results

@router.patch("/{run_id}/answers/{question_id}")
async def update_answer(run_id: str, question_id: str, body: AnswerUpdateRequest, request: Request):
    """Update an answer for a specific question in a run."""
    logger.info(f"Update answer requested for run_id: {run_id}, question_id: {question_id}")
    run_store = request.app.state.run_store
    
    try:
        run_store.update_answer(run_id, question_id, body.final_text, body.human_approved)
        logger.info(f"Successfully updated answer for {question_id}")
    except KeyError:
        logger.warning(f"Run {run_id} or question {question_id} not found")
        raise HTTPException(status_code=404, detail=f"Run {run_id} or question {question_id} not found")
        
    return {"status": "updated"}

@router.post("/{run_id}/export")
async def export_run(run_id: str, request: Request):
    """Export approved answers to a .docx file."""
    logger.info(f"Export requested for run_id: {run_id}")
    run_store = request.app.state.run_store
    
    try:
        results = run_store.get_results(run_id)
    except KeyError:
        logger.warning(f"Run {run_id} not found")
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    try:
        doc = DocxDocument()
        doc.add_heading("Groundwork — Questionnaire Response", level=0)
        
        for r in results:
            question_text = r.get('question_text', r.get('question_id', ''))
            doc.add_heading(f"Q: {question_text}", level=2)
            
            status = r.get('status', 'unknown')
            doc.add_paragraph(f"Status: {status.upper()}", style="Intense Quote")
            
            answer_text = r.get('final_text', 'No answer provided.')
            if answer_text is None:
                answer_text = 'No answer provided.'
            doc.add_paragraph(answer_text)
            doc.add_paragraph("")  # spacer
        
        upload_dir = getattr(request.app.state, "upload_dir", settings.UPLOAD_DIR)
        export_path = os.path.join(upload_dir, f"{run_id}_export.docx")
        doc.save(export_path)
        logger.info(f"Successfully exported run {run_id} to {export_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate export doc for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate export document: {str(e)}")
    
    return FileResponse(
        export_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"groundwork_export_{run_id}.docx"
    )
