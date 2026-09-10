import logging
from typing import List

from app.config import settings
from app.models import Question, EvidenceChunk

logger = logging.getLogger(__name__)

def retrieve_evidence(question: Question, kb_id: str, vector_store_manager) -> List[EvidenceChunk]:
    """Retrieve relevant evidence chunks from the vector store for a given question.
    
    Args:
        question: The question to retrieve evidence for.
        kb_id: The knowledge base ID to search within.
        vector_store_manager: The vector store manager instance.
        
    Returns:
        A list of EvidenceChunk objects.
    """
    logger.info("Retrieving evidence for question '%s' (kb_id=%s)", question.id, kb_id)
    
    try:
        chunks = vector_store_manager.retrieve(
            kb_id=kb_id,
            query=question.text,
            top_k=settings.TOP_K,
            threshold=settings.SIMILARITY_THRESHOLD
        )
        
        top_score = max((chunk.similarity for chunk in chunks), default=0.0)
        logger.info(
            "Retrieved %d chunks for question '%s'. Top score: %.3f",
            len(chunks), question.id, top_score
        )
        
        return chunks
    except Exception as e:
        logger.error("Error retrieving evidence for question '%s': %s", question.id, str(e))
        return []
