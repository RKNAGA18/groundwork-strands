"""Stage 2: Semantic retrieval from the knowledge base.

Queries the VectorStoreManager, which uses real HuggingFace embeddings
(BAAI/bge-small-en-v1.5) and ChromaDB cosine similarity to return
EvidenceChunk objects above the configured threshold.

If zero chunks survive the threshold, evidence = [] — this triggers
the automatic red/unsupported path downstream.
"""

import logging
from typing import List

from app.config import settings
from app.models import Question, EvidenceChunk

logger = logging.getLogger(__name__)


def retrieve_evidence(
    question: Question, kb_id: str, vector_store_manager
) -> List[EvidenceChunk]:
    """Retrieve relevant evidence chunks for a question.

    Args:
        question: The question to retrieve evidence for.
        kb_id: The knowledge base ID to search within.
        vector_store_manager: The VectorStoreManager instance.

    Returns:
        A list of EvidenceChunk objects (may be empty if nothing
        clears the similarity threshold).
    """
    logger.info(
        "Retrieving evidence for question '%s' (kb_id=%s)", question.id, kb_id
    )

    try:
        # VectorStoreManager.retrieve() now returns List[EvidenceChunk]
        # directly, with real cosine similarity scores and threshold filtering
        chunks = vector_store_manager.retrieve(
            kb_id=kb_id,
            query=question.text,
            top_k=settings.TOP_K,
            threshold=settings.SIMILARITY_THRESHOLD,
        )

        top_score = max((c.similarity for c in chunks), default=0.0)
        logger.info(
            "Retrieved %d chunks for question '%s'. Top score: %.4f",
            len(chunks),
            question.id,
            top_score,
        )

        return chunks

    except Exception as e:
        logger.error(
            "Error retrieving evidence for question '%s': %s",
            question.id,
            str(e),
        )
        return []
