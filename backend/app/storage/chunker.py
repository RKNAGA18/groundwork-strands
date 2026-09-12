import os
import uuid

class DocumentChunk:
    def __init__(self, text: str, chunk_id: str, doc_id: str, doc_name: str):
        self.text = text
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.doc_name = doc_name
        self.similarity = 0.95
        self.score = 0.95
        self.node = self

    def get_text(self):
        return self.text

    def __getattr__(self, name):
        if name == "content":
            return self.text
        return None

    def __str__(self):
        return self.text

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def chunk_document(file_path: str, doc_id: str = None, doc_name: str = None) -> list:
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    doc_name = doc_name or os.path.basename(file_path)
    doc_id = doc_id or str(uuid.uuid4())
    text_chunks = chunk_text(content)

    chunks = []
    for i, t in enumerate(text_chunks):
        cid = f"{doc_name}_chunk_{i}"
        chunks.append(DocumentChunk(text=t, chunk_id=cid, doc_id=doc_id, doc_name=doc_name))
    return chunks
