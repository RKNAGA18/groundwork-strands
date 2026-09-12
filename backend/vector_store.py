import os
import json
import boto3
from app.config import get_settings

settings = get_settings()

class BedrockTitanEmbedding:
    """Lightweight custom embedding wrapper using Amazon Bedrock Titan via boto3."""
    def __init__(self):
        # Supports both IAM credentials and AWS_BEARER_TOKEN_BEDROCK
        self.client = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)
        self.model_id = "amazon.titan-embed-text-v1"

    def get_text_embedding(self, text: str) -> list[float]:
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text})
        )
        response_body = json.loads(response["body"].read())
        return response_body["embedding"]

    def __call__(self, text: str) -> list[float]:
        return self.get_text_embedding(text)

class VectorStoreManager:
    def __init__(self, persist_dir: str = "./chroma_data"):
        import chromadb
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embed_model = BedrockTitanEmbedding()

    def get_or_create_collection(self, name: str):
        return self.client.get_or_create_collection(name=name)

    def add_documents(self, collection_name: str, documents: list[str], metadatas: list[dict] = None):
        collection = self.get_or_create_collection(collection_name)
        ids = [f"doc_{i}" for i in range(len(documents))]
        embeddings = [self.embed_model(doc) for doc in documents]
        
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas if metadatas else [{}] * len(documents),
            ids=ids
        )

    def query(self, collection_name: str, query_text: str, n_results: int = 3):
        collection = self.get_or_create_collection(collection_name)
        query_embedding = self.embed_model(query_text)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        return results
