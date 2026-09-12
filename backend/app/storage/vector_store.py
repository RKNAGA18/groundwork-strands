"""Vector store manager — ChromaDB + HuggingFace local embeddings.

Uses sentence-transformers (BAAI/bge-small-en-v1.5) for real semantic
embeddings, stored and queried via ChromaDB. No Bedrock embedding calls.

The retrieve() method returns EvidenceChunk objects with real cosine
similarity scores, filtered by the configured threshold.
"""

import logging
import os
import uuid

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings
from app.models import EvidenceChunk

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages knowledge base collections in ChromaDB with real embeddings."""

    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or settings.CHROMA_PATH
        os.makedirs(self.persist_dir, exist_ok=True)

        # Use sentence-transformers for real semantic embeddings
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL,
        )

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        logger.info(
            "VectorStoreManager initialized (persist=%s, model=%s)",
            self.persist_dir, settings.EMBEDDING_MODEL,
        )

    def create_kb(self, kb_id: str) -> None:
        """Create (or get) a knowledge-base collection."""
        self.client.get_or_create_collection(
            name=kb_id,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("KB collection '%s' ready", kb_id)

    def add_chunks(self, kb_id: str, chunks: list) -> None:
        """Add document chunks to a knowledge-base collection.

        Args:
            kb_id: The knowledge base collection name.
            chunks: List of objects with .text, .chunk_id, .doc_id, .doc_name
        """
        if not chunks:
            return

        collection = self.client.get_or_create_collection(
            name=kb_id,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        texts = []
        for c in chunks:
            text = (getattr(c, "chunk_text", None) or getattr(c, "text", None)
                    or (c.get("chunk_text") if isinstance(c, dict) else None)
                    or (c.get("text") if isinstance(c, dict) else None))
            if not text:
                raise ValueError(f"Could not extract text from chunk: {c}")
            texts.append(text)

        ids = [getattr(c, "chunk_id", str(uuid.uuid4())) for c in chunks]
        metadatas = [
            {
                "chunk_id": getattr(c, "chunk_id", ids[i]),
                "doc_id": getattr(c, "doc_id", "unknown"),
                "doc_name": getattr(c, "doc_name", "unknown.md"),
            }
            for i, c in enumerate(chunks)
        ]

        # ChromaDB will compute embeddings via the collection's embed fn
        collection.add(documents=texts, metadatas=metadatas, ids=ids)
        logger.info("Added %d chunks to KB '%s'", len(chunks), kb_id)

    def retrieve(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
        threshold: float = None,
    ) -> list[EvidenceChunk]:
        """Retrieve evidence chunks via semantic similarity.

        Uses ChromaDB's built-in query (which calls the sentence-transformer
        embedding function on the query, then does cosine similarity search).

        Args:
            kb_id: The knowledge base collection name.
            query: The question text to search for.
            top_k: Maximum number of results.
            threshold: Minimum cosine similarity. Defaults to settings value.

        Returns:
            List of EvidenceChunk objects above the threshold, sorted by
            similarity descending.
        """
        if threshold is None:
            threshold = settings.SIMILARITY_THRESHOLD

        collection = self.client.get_or_create_collection(
            name=kb_id,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        # Check if collection has any documents
        count = collection.count()
        if count == 0:
            logger.warning("KB '%s' is empty, returning no evidence", kb_id)
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        # ChromaDB cosine distance = 1 - cosine_similarity
        # So similarity = 1 - distance
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        chunks = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            similarity = 1.0 - dist  # Convert distance to similarity
            if similarity < threshold:
                continue

            chunks.append(
                EvidenceChunk(
                    doc_id=meta.get("doc_id", "unknown"),
                    doc_name=meta.get("doc_name", "unknown.md"),
                    chunk_id=meta.get("chunk_id", str(uuid.uuid4())),
                    chunk_text=doc,
                    similarity=round(similarity, 4),
                )
            )

        # Sort by similarity descending
        chunks.sort(key=lambda c: c.similarity, reverse=True)

        if chunks:
            logger.info(
                "KB '%s' query: %d chunks above threshold %.2f (top=%.4f)",
                kb_id, len(chunks), threshold, chunks[0].similarity,
            )
        else:
            logger.info(
                "KB '%s' query: 0 chunks above threshold %.2f",
                kb_id, threshold,
            )

        return chunks
