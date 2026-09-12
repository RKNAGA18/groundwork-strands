import os
import json
import re
import time
import requests

class DeepSeekLLM:
    """Ultra-lightweight, low-token adapter using MiniCPM5-2B with 429 rate-limit handling."""
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "rc-9758889b39d72e8f43fac8f0cec90b7d607123b781bcee70").strip()
        self.url = "https://developer.amd.com.cn/radeon/api/v1/chat/completions"
        # Using the ultra-lightweight 2B model
        self.model = os.environ.get("DEEPSEEK_MODEL", "MiniCPM5-2B").strip()

    def generate(self, prompt: str, system_prompt: str = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Keep system prompt short to minimize prompt token count
        base_sys = "Enterprise security evaluator. Answer concisely in English."
        sys_content = f"{base_sys} {system_prompt}" if system_prompt else base_sys

        messages = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 150  # Capped: saves tokens and prevents runaway generation
        }

        # Polite 1-second delay to stay under the 20 RPM ceiling
        time.sleep(1.0)

        for attempt in range(4):
            try:
                response = requests.post(self.url, headers=headers, json=payload, timeout=30)
                
                # Handle 429 Rate Limit with progressive backoff
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 3
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)
                    content = content.strip()

                return content
            except requests.exceptions.RequestException as e:
                if attempt == 3:
                    print(f"API Error after retries: {e}")
                    if system_prompt and "json" in system_prompt.lower():
                        return '{"supported": false, "reason": "Rate limited"}'
                    return "Error generating response."
                time.sleep(2)

        return '{"supported": false, "reason": "Failed after retries"}'

    def complete(self, prompt: str):
        class Response:
            def __init__(self, text):
                self.text = text
        return Response(self.generate(prompt))

    def chat(self, messages: list):
        sys_prompt = next((m.content for m in messages if hasattr(m, 'role') and str(m.role).upper() == "SYSTEM"), None)
        user_prompt = "\n".join([m.content for m in messages if hasattr(m, 'role') and str(m.role).upper() != "SYSTEM"])
        class Response:
            def __init__(self, text):
                self.message = type('obj', (object,), {'content': text})
        return Response(self.generate(user_prompt, sys_prompt))

def get_llm():
    return DeepSeekLLM()
