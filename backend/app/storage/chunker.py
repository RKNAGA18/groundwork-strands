import os
import re
import PyPDF2

def chunk_document(file_path: str, doc_id: str, doc_name: str) -> list[dict]:
    """
    Chunks a document into smaller text segments suitable for vector storage.
    
    Args:
        file_path (str): The absolute path to the document file.
        doc_id (str): The unique identifier for the document.
        doc_name (str): The original name of the document.
        
    Returns:
        list[dict]: A list of chunk dictionaries containing text and metadata.
    """
    ext = os.path.splitext(file_path)[1].lower()
    text_content = []
    
    if ext == ".pdf":
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append({"text": page_text, "page_number": i + 1})
        except Exception:
            # Skip if error reading PDF
            pass
    elif ext in [".md", ".txt"]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content:
                    text_content.append({"text": content, "page_number": None})
        except Exception:
            # Skip if error reading text file
            pass
    else:
        # Unsupported file type
        return []

    chunks = []
    chunk_counter = 1
    
    MAX_CHARS = 2048
    OVERLAP_CHARS = 200
    
    for item in text_content:
        text = item["text"]
        page_num = item["page_number"]
        
        # Split by paragraph/section boundary
        sections = re.split(r'\n\n+', text)
        
        current_heading = ""
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Extract heading if it's markdown
            lines = section.split('\n')
            if lines[0].strip().startswith('#'):
                current_heading = lines[0].strip().lstrip('#').strip()
            
            # Hard wrap if over 2048 characters
            if len(section) > MAX_CHARS:
                start = 0
                while start < len(section):
                    end = start + MAX_CHARS
                    chunk_text = section[start:end]
                    
                    chunk_id = f"{doc_id}_chunk_{chunk_counter:03d}"
                    chunks.append({
                        "doc_id": doc_id,
                        "doc_name": doc_name,
                        "chunk_id": chunk_id,
                        "chunk_text": chunk_text,
                        "section_heading": current_heading,
                        "page_number": page_num
                    })
                    chunk_counter += 1
                    
                    if end >= len(section):
                        break
                    start += MAX_CHARS - OVERLAP_CHARS
            else:
                chunk_id = f"{doc_id}_chunk_{chunk_counter:03d}"
                chunks.append({
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "chunk_id": chunk_id,
                    "chunk_text": section,
                    "section_heading": current_heading,
                    "page_number": page_num
                })
                chunk_counter += 1

    return chunks
