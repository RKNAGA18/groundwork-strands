import chromadb
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core import Settings as LlamaSettings
from llama_index.core.schema import TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from app.config import settings
from app.models import EvidenceChunk

class VectorStoreManager:
    """
    Manages vector storage and retrieval using LlamaIndex and ChromaDB.
    """
    def __init__(self):
        """
        Initializes the ChromaDB client and HuggingFace embeddings.
        """
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        embed_model = HuggingFaceEmbedding(model_name=settings.EMBEDDING_MODEL)
        LlamaSettings.embed_model = embed_model
        
    def create_kb(self, kb_id: str):
        """
        Creates or retrieves a ChromaDB collection for the given knowledge base ID.
        
        Args:
            kb_id (str): The unique identifier for the knowledge base.
        """
        self.chroma_client.get_or_create_collection(
            name=kb_id,
            metadata={"hnsw:space": "cosine"}
        )
        
    def add_chunks(self, kb_id: str, chunks: list[dict]):
        """
        Adds text chunks to the specified knowledge base collection.
        
        Args:
            kb_id (str): The knowledge base identifier.
            chunks (list[dict]): A list of chunk dictionaries to add.
        """
        chroma_collection = self.chroma_client.get_or_create_collection(
            name=kb_id,
            metadata={"hnsw:space": "cosine"}
        )
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        nodes = []
        for chunk in chunks:
            node = TextNode(
                text=chunk["chunk_text"],
                id_=chunk["chunk_id"],
                metadata={
                    "doc_id": chunk["doc_id"],
                    "doc_name": chunk["doc_name"],
                    "chunk_id": chunk["chunk_id"],
                    "section_heading": chunk["section_heading"],
                    "page_number": chunk["page_number"] if chunk["page_number"] is not None else -1
                }
            )
            nodes.append(node)
            
        VectorStoreIndex(nodes, storage_context=storage_context)
        
    def retrieve(self, kb_id: str, query: str, top_k: int = 5, threshold: float = 0.75) -> list[EvidenceChunk]:
        """
        Retrieves relevant text chunks for a given query.
        
        Args:
            kb_id (str): The knowledge base identifier.
            query (str): The search query.
            top_k (int, optional): The number of top results to return. Defaults to 5.
            threshold (float, optional): The similarity score threshold. Defaults to 0.75.
            
        Returns:
            list[EvidenceChunk]: A list of retrieved evidence chunks.
        """
        try:
            chroma_collection = self.chroma_client.get_collection(name=kb_id)
        except Exception:
            return []
            
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
        
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes_with_scores = retriever.retrieve(query)
        
        results = []
        for node in nodes_with_scores:
            if node.score is not None and node.score >= threshold:
                metadata = node.node.metadata
                chunk = EvidenceChunk(
                    doc_id=metadata.get("doc_id", ""),
                    doc_name=metadata.get("doc_name", ""),
                    chunk_id=metadata.get("chunk_id", ""),
                    chunk_text=node.node.text,
                    similarity=float(node.score)
                )
                results.append(chunk)
                
        # Sort by similarity descending
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results
