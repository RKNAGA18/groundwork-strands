import json
import logging
from typing import List

from app.config import settings
from app.models import Question, EvidenceChunk, Draft
from app.llm.adapter import LLMAdapter
from app.llm.prompts import DRAFT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def draft_answer(question: Question, evidence: List[EvidenceChunk], llm: LLMAdapter) -> Draft:
    """Generate a draft answer for a question based on retrieved evidence.
    
    Args:
        question: The question to answer.
        evidence: A list of evidence chunks.
        llm: The LLM adapter to use for generation.
        
    Returns:
        A Draft object containing the answer and citations.
    """
    if not evidence:
        logger.warning("No evidence provided for question '%s', returning INSUFFICIENT_EVIDENCE", question.id)
        return Draft(
            question_id=question.id,
            answer_text="INSUFFICIENT_EVIDENCE",
            cited_chunk_ids=[]
        )
        
    # Format evidence for the prompt
    evidence_text = "\n".join(
        f"[{chunk.chunk_id}]: {chunk.chunk_text}" for chunk in evidence
    )
    
    user_message = f"Question: {question.text}\n\nEvidence:\n{evidence_text}"
    
    logger.info("Generating draft for question '%s' using %d evidence chunks", question.id, len(evidence))
    
    try:
        response_text = llm.generate(
            system_prompt=DRAFT_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=settings.DRAFT_TEMPERATURE
        )
        
        response_data = json.loads(response_text)
        
        return Draft(
            question_id=question.id,
            answer_text=response_data.get("answer_text", "INSUFFICIENT_EVIDENCE"),
            cited_chunk_ids=response_data.get("cited_chunk_ids", [])
        )
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON response from LLM for question '%s': %s", question.id, str(e))
        return Draft(
            question_id=question.id,
            answer_text="INSUFFICIENT_EVIDENCE",
            cited_chunk_ids=[]
        )
    except Exception as e:
        logger.error("Error generating draft for question '%s': %s", question.id, str(e))
        return Draft(
            question_id=question.id,
            answer_text="INSUFFICIENT_EVIDENCE",
            cited_chunk_ids=[]
        )
