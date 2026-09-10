import logging
import os
import re
from typing import List

import openpyxl
from PyPDF2 import PdfReader

from app.models import Question

logger = logging.getLogger(__name__)

def parse_questionnaire(file_path: str) -> List[Question]:
    """Parse a questionnaire file (XLSX or PDF) into a list of Question objects.
    
    Args:
        file_path: Path to the questionnaire file.
        
    Returns:
        A list of Question objects.
        
    Raises:
        ValueError: If the file type is not supported.
    """
    ext = os.path.splitext(file_path)[1].lower()
    logger.info("Parsing questionnaire file: %s", file_path)
    
    try:
        if ext == ".xlsx":
            return _parse_xlsx(file_path)
        elif ext == ".pdf":
            return _parse_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
    except (openpyxl.utils.exceptions.InvalidFileException, ValueError) as e:
        raise ValueError(f"Invalid or corrupted file: {e}")
    except Exception as e:
        # Catch BadZipFile for empty xlsx, PdfReadError for garbage pdfs
        if "BadZipFile" in type(e).__name__ or "PdfReadError" in type(e).__name__:
            raise ValueError(f"Corrupted or empty file structure: {e}")
        raise

def _parse_xlsx(file_path: str) -> List[Question]:
    """Parse an XLSX file into questions."""
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    
    header_row_idx = None
    question_col_idx = None
    id_col_idx = None
    
    # Try to find header row (look in first 5 rows)
    for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=5, values_only=True), 1):
        for c_idx, cell in enumerate(row, 1):
            if isinstance(cell, str):
                cell_lower = cell.lower()
                if "question" in cell_lower:
                    header_row_idx = r_idx
                    question_col_idx = c_idx
                elif "id" in cell_lower or "control" in cell_lower:
                    if id_col_idx is None:
                        id_col_idx = c_idx
                        
        if header_row_idx is not None:
            break
            
    # If no explicit 'question' column found, use heuristic: longest average text length
    if question_col_idx is None:
        logger.warning("No 'question' column found in XLSX, falling back to heuristics")
        col_lengths = {}
        for row in ws.iter_rows(min_row=1, max_row=50, values_only=True):
            for c_idx, cell in enumerate(row, 1):
                if isinstance(cell, str):
                    col_lengths[c_idx] = col_lengths.get(c_idx, 0) + len(cell)
        if col_lengths:
            question_col_idx = max(col_lengths, key=col_lengths.get)
        else:
            question_col_idx = 1
            
        header_row_idx = 1 # fallback
        
    questions = []
    question_num = 1
    
    start_row = header_row_idx + 1 if header_row_idx else 1
    
    for r_idx, row in enumerate(ws.iter_rows(min_row=start_row, values_only=True), start_row):
        if not row:
            continue
            
        # Get question text
        if question_col_idx - 1 < len(row):
            q_text = row[question_col_idx - 1]
        else:
            q_text = None
            
        if not q_text or not str(q_text).strip():
            continue
            
        # Get ID
        q_id = None
        if id_col_idx is not None and id_col_idx - 1 < len(row):
            val = row[id_col_idx - 1]
            if val:
                q_id = str(val).strip()
                
        if not q_id:
            q_id = f"Q-{question_num}"
            
        questions.append(Question(
            id=q_id,
            text=str(q_text).strip(),
            source_row=r_idx
        ))
        question_num += 1
        
    logger.info("Parsed %d questions from XLSX", len(questions))
    return questions

def _parse_pdf(file_path: str) -> List[Question]:
    """Parse a PDF file into questions using basic numbered list heuristics."""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
            
    questions = []
    
    # Split text by common question numbering formats (1. , 1) , Q1: )
    pattern = re.compile(r'(?:^|\n)(?:Q\d+[:.]|\d+[\.)])\s+(.*?(?=(?:\n(?:Q\d+[:.]|\d+[\.)]))|\Z))', re.DOTALL)
    
    matches = pattern.finditer(text)
    match_list = list(matches)
    
    if match_list:
        for i, match in enumerate(match_list, 1):
            q_text = match.group(1).strip()
            # Clean up text
            q_text = re.sub(r'\n+', ' ', q_text)
            if q_text:
                questions.append(Question(
                    id=f"Q-{i}",
                    text=q_text,
                    source_row=i
                ))
    else:
        # Fallback to splitting by line and filtering empty lines
        logger.warning("No numbered list found in PDF, falling back to line-by-line")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for i, line in enumerate(lines, 1):
            questions.append(Question(
                id=f"Q-{i}",
                text=line,
                source_row=i
            ))
            
    logger.info("Parsed %d questions from PDF", len(questions))
    return questions
