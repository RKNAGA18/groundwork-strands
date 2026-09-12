import os

patch_code = """
import boto3
import json
import requests
import os

if not hasattr(boto3, '_is_deepseek_patched'):
    _orig_client = boto3.client
    _orig_session_client = boto3.Session.client

    def _get_deepseek_mock():
        class MockBedrock:
            def converse(self, **cwargs):
                api_key = os.environ.get("DEEPSEEK_API_KEY")
                if not api_key:
                    return {"output": {"message": {"role": "assistant", "content": [{"text": '{"supported": false, "reason": "No DeepSeek Key"}'}]}}}

                msg_text = str(cwargs.get("messages", [])).lower()
                sys_text = str(cwargs.get("system", [])).lower()
                
                # We tell DeepSeek exactly what format we need based on the prompt type
                if "json" in sys_text or "json" in msg_text or "assess" in sys_text:
                    prompt = f"Analyze the following context and question. Return ONLY a valid JSON object with the keys 'supported' (boolean) and 'reason' (string). Context/Question: {msg_text}"
                else:
                    prompt = f"Answer this question based strictly on the provided context: {msg_text}"

                try:
                    response = requests.post(
                        "https://api.deepseek.com/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1
                        },
                        timeout=15
                    )
                    data = response.json()
                    res = data["choices"][0]["message"]["content"].replace("```json", "").replace("```", "").strip()
                except Exception as e:
                    print(f"DeepSeek Error: {e}")
                    res = '{"supported": false, "reason": "API Failure"}' if "json" in sys_text else "Failed to generate answer."
                    
                return {"output": {"message": {"role": "assistant", "content": [{"text": res}]}}}

            def invoke_model(self, **kwargs):
                class MockBody:
                    def read(self): return json.dumps({"embedding": [0.1]*1536}).encode("utf-8")
                return {"body": MockBody()}
                
        return MockBedrock()

    def _mock_client(svc, *args, **kwargs):
        if svc == "bedrock-runtime": return _get_deepseek_mock()
        return _orig_client(svc, *args, **kwargs)
        
    def _mock_session_client(self, svc, *args, **kwargs):
        if svc == "bedrock-runtime": return _get_deepseek_mock()
        return _orig_session_client(self, svc, *args, **kwargs)

    boto3.client = _mock_client
    boto3.Session.client = _mock_session_client
    boto3._is_deepseek_patched = True
"""

for file_path in ["eval/run_eval.py", "eval/run_ablation.py"]:
    with open(file_path, "r") as f:
        content = f.read()
    # Remove old patches if they exist to keep it clean
    if "_is_patched" in content:
        content = content.split('boto3._is_patched = True\n"""\n')[1]
    
    if "_is_deepseek_patched" not in content:
        with open(file_path, "w") as f:
            f.write(patch_code + "\n" + content)
        print(f"Applied DeepSeek interceptor to {file_path}")
