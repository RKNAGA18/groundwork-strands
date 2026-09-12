import os
from typing import List, Dict, Any
from strands import Agent
from strands.models.openai import OpenAIModel
from app.storage.vector_store import VectorStoreManager

_VSM = None
_KB_ID = "eval_kb"

def set_vector_store(vsm: VectorStoreManager, kb_id: str = "eval_kb"):
    global _VSM, _KB_ID
    _VSM = vsm
    _KB_ID = kb_id

def retrieve_evidence(question_text: str) -> List[Dict[str, Any]]:
    global _VSM, _KB_ID
    if _VSM is None: return []
    chunks = _VSM.retrieve(_KB_ID, question_text, top_k=3, threshold=0.05)
    return [c.to_dict() for c in chunks]

groq_model = OpenAIModel(
    client_args={
        "api_key": os.environ.get("GROQ_API_KEY", ""),
        "base_url": "https://api.groq.com/openai/v1"
    },
    model_id="llama-3.1-8b-instant",
    params={"temperature": 0.0, "max_tokens": 500}
)

DrafterAgent = Agent(
    model=groq_model,
    system_prompt="You are Groundwork's Drafter Agent. Based ONLY on the provided evidence, draft a brief answer. If evidence is empty, state 'Not addressed in policy'."
)

VerifierAgent = Agent(
    model=groq_model,
    system_prompt="You are an enterprise compliance auditor. Review the Question, the Draft, and the Evidence. If the draft is fully supported by the evidence, output 'STATUS: GREEN' followed by a 1-sentence reason. If it is unsupported, hallucinates, or evidence is missing, output 'STATUS: RED' followed by a 1-sentence reason."
)

def run_pipeline(question: str) -> Dict[str, Any]:
    try:
        evidence = retrieve_evidence(question)
        
        # LIVE API INVOCATION 1: Drafter
        draft_prompt = f"Question: {question}\nEvidence: {evidence}"
        draft_result = DrafterAgent.invoke(draft_prompt)
        draft_text = str(draft_result)
        
        # LIVE API INVOCATION 2: Verifier
        verify_prompt = f"Question: {question}\nDraft: {draft_text}\nEvidence: {evidence}"
        verify_result = VerifierAgent.invoke(verify_prompt)
        verify_text = str(verify_result)
        
        is_supported = "STATUS: GREEN" in verify_text.upper()
        status = "green" if is_supported else "red"
        
        # Clean up the output string for the UI
        clean_reason = verify_text.replace("STATUS: GREEN", "").replace("STATUS: RED", "").replace("Status: GREEN", "").replace("Status: RED", "").replace("\n", " ").strip()
        
        return {
            "status": status,
            "top_source": evidence[0]["doc_name"] if evidence else "None",
            "top_similarity": evidence[0]["similarity"] if evidence else 0.0,
            "reason": clean_reason
        }
    except Exception as e:
        return {"status": "red", "reason": f"Pipeline error: {str(e)}", "top_source": "None", "top_similarity": 0.0}
