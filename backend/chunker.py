import os

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Simple text chunking for markdown and text documents."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def chunk_document(file_path: str) -> list[str]:
    """Read a markdown or text file and split into chunks."""
    if not os.path.exists(file_path):
        return []
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        
    return chunk_text(content)
