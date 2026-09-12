import os
import sys
import json
from typing import List, Dict, Any

# Ensure OpenAI adapter pulls from DeepSeek AMD endpoint
os.environ["OPENAI_API_KEY"] = "rc-9758889b39d72e8f43fac8f0cec90b7d607123b781bcee70"
os.environ["OPENAI_BASE_URL"] = "https://developer.amd.com.cn/radeon/api/v1"

# In case the strands OpenAIModel ignores OPENAI_BASE_URL directly, we patch it
# by importing strands and the openai model provider.
try:
    from strands import Agent, tool
    from strands.models.openai import OpenAIModel
except ImportError as e:
    print(f"ImportError: {e}. Make sure you installed 'strands-agents[openai]'.")
    sys.exit(1)

@tool
def retrieve_evidence(question_text: str) -> List[Dict[str, Any]]:
    """Search internal enterprise security policies for grounded evidence chunks."""
    # Mocking retrieval to just prove the LLM is hit via Strands
    return [{"doc_name": "policy.md", "chunk_text": "AES-256 is strictly enforced for all encrypted data.", "similarity": 0.95}]

# DeepSeek via OpenAIModel. 
# We explicitly specify base_url in case the environment variable isn't caught.
deepseek_model = OpenAIModel(
    model_id="DeepSeek-V4-Flash",
    client_kwargs={"base_url": "https://developer.amd.com.cn/radeon/api/v1"}
)

DrafterAgent = Agent(
    model=deepseek_model,
    system_prompt="You are an enterprise compliance drafter. Answer the question strictly based on the provided evidence. Keep it under 2 sentences.",
    tools=[retrieve_evidence]
)

VerifierAgent = Agent(
    model=deepseek_model,
    system_prompt="You are a strict compliance verifier. Determine if the draft is 100% supported by the evidence. Respond with ONLY 'STATUS: GREEN' if supported, or 'STATUS: RED' if hallucinated or unsupported. Provide a brief 1-sentence reason after the status."
)

def main():
    print("============================================================")
    print("STARTING STRANDS + DEEPSEEK TEST")
    print("============================================================\n")
    question = "Is AES-256 secure according to the policy?"
    
    print(f"[1] Invoking DrafterAgent for question: '{question}'...")
    try:
        # Note: strands agents are typically invoked via `agent("prompt")` 
        # but if `invoke` exists we'll try it, else fallback to __call__
        prompt = f"Question: {question}"
        
        try:
            draft_result = DrafterAgent.invoke(prompt)
        except AttributeError:
            draft_result = DrafterAgent(prompt)
            
        draft_text = str(draft_result)
        print(f"\n[DRAFTER OUTPUT]\n{draft_text}\n")
        
        print(f"[2] Invoking VerifierAgent on the draft...")
        verify_prompt = f"Question: {question}\nDraft: {draft_text}\nEvidence: [{'doc_name': 'policy.md', 'chunk_text': 'AES-256 is strictly enforced for all encrypted data.', 'similarity': 0.95}]"
        
        try:
            verify_result = VerifierAgent.invoke(verify_prompt)
        except AttributeError:
            verify_result = VerifierAgent(verify_prompt)
            
        verify_text = str(verify_result)
        print(f"\n[VERIFIER OUTPUT]\n{verify_text}\n")
        
    except Exception as e:
        print(f"\n[ERROR] during Strands invocation: {e}")

if __name__ == "__main__":
    main()
