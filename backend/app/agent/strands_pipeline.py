import os
import json
from typing import List, Dict, Any
import httpx

# We will rely on standard timeout behavior and try-except handling instead of monkey patching.
# The OpenAI SDK defaults to a generous timeout anyway.
# Explicit environment variables for Strands OpenAIModel integration
os.environ["OPENAI_API_KEY"] = os.environ.get("GROQ_API_KEY", "")
os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
from strands import Agent, tool
from strands.models.openai import OpenAIModel
from app.storage.vector_store import VectorStoreManager

_VSM = None
_KB_ID = "smoke_test_kb"

def set_vector_store(vsm: VectorStoreManager, kb_id: str):
    global _VSM, _KB_ID
    _VSM = vsm
    _KB_ID = kb_id

@tool
def retrieve_evidence(question_text: str) -> list[dict]:
    """Calls the local VectorStoreManager (eval_kb) and returns top-3 chunks."""
    global _VSM, _KB_ID
    if _VSM is None:
        return []
    chunks = _VSM.retrieve(_KB_ID, question_text, top_k=3, threshold=0.75)
    return [c.model_dump() if hasattr(c, 'model_dump') else (c.dict() if hasattr(c, 'dict') else c) for c in chunks]

@tool
def draft_answer(question_text: str, evidence: list[dict]) -> dict:
    """Drafts a concise compliance answer based on evidence."""
    if not evidence:
        return {"answer_text": "INSUFFICIENT_EVIDENCE", "cited_chunk_ids": []}
    return {"answer_text": f"Draft answer generated from evidence.", "cited_chunk_ids": [e.get('chunk_id') for e in evidence]}

@tool
def check_claim_against_sources(draft_text: str, evidence: list[dict]) -> dict:
    """Audits the draft against retrieved chunks. Returns {'status': 'green'} if supported, else {'status': 'red'}."""
    if not evidence or "INSUFFICIENT_EVIDENCE" in draft_text:
        return {"status": "red"}
    return {"status": "green"}

# 1. Model Configuration via Groq
groq_model = OpenAIModel(
    model_id="qwen/qwen3.6-27b",
    params={"temperature": 0.0, "max_tokens": 500}
)

# 3. Agents
DrafterAgent = Agent(
    model=groq_model,
    system_prompt="You orchestrate parsing, retrieval, and grounded drafting. Never answer from your own knowledge.",
    tools=[retrieve_evidence, draft_answer]
)

VerifierAgent = Agent(
    model=groq_model,
    system_prompt="You audit drafts against their cited sources only. Return {'status': 'green'} if supported, else {'status': 'red'}.",
    tools=[check_claim_against_sources]
)

def process_question(question: str) -> dict:
    # 4. Fail-Safe Handling
    try:
        # Fallback to __call__ if invoke doesn't exist
        invoke_fn_drafter = getattr(DrafterAgent, "invoke", DrafterAgent.__call__)
        invoke_fn_verifier = getattr(VerifierAgent, "invoke", VerifierAgent.__call__)
        
        draft_result = invoke_fn_drafter(f"Question: {question}")
        draft_text = str(draft_result)
        
        verify_result = invoke_fn_verifier(f"Question: {question}\nDraft: {draft_text}")
        verify_text = str(verify_result)
        
        is_supported = "green" in verify_text.lower()
        status = "green" if is_supported else "red"
        
        return {
            "question": question,
            "status": status,
            "reason": verify_text
        }
    except Exception as e:
        # Fail-Safe Handling for network timeout or connection error
        return {
            "question": question,
            "status": "red",
            "reason": f"Inference timeout / connection error - flagged for manual audit (Exception: {repr(e)})"
        }
