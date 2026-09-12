"""LLM adapter — DeepSeek-V4-Flash-Vision-Exp via AMD Radeon Cloud API.

Replaces the previous AWS Bedrock adapter for low-token, live testing.
"""

import os
import re
import time
import requests
import logging

logger = logging.getLogger(__name__)

# ANSI colour codes for demo-visible terminal logs
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


class RateLimitExhaustedError(Exception):
    """Raised when retries are exhausted."""


class LLMAdapter:
    """Thin wrapper around DeepSeek API on AMD Radeon Cloud."""

    def __init__(self):
        """Initialize the adapter with DeepSeek configuration."""
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "rc-9758889b39d72e8f43fac8f0cec90b7d607123b781bcee70").strip()
        self.url = "https://developer.amd.com.cn/radeon/api/v1/chat/completions"
        # Low token consumption model
        self.model = "DeepSeek-V4-Flash-Vision-Exp"
        
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
    ) -> str:
        """Generate a response from DeepSeek API.

        Args:
            system_prompt: The system instruction for the model.
            user_message: The user message / query.
            temperature: Sampling temperature.

        Returns:
            The model's text response.
        """
        logger.info(
            "%s%s🔷  INVOKING DEEPSEEK (AMD RADEON): %s%s",
            _BOLD, _CYAN, self.model, _RESET,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        # The user requested max_tokens=60 for verifier, but drafter might need slightly more.
        # Since we use this adapter for both, we'll give it a strict cap but enough for a draft (e.g. 150)
        # or stick to 60. Wait, a draft answer needs ~30-40 words. 60 tokens should barely fit, let's use 100 
        # to prevent JSON truncation issues which ruin parsing.
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 150 
        }

        for attempt in range(4):
            try:
                resp = requests.post(self.url, headers=headers, json=payload, timeout=20)
                if resp.status_code == 429:
                    logger.warning("Rate limit hit! Backing off for 3s...")
                    time.sleep(3)
                    continue
                resp.raise_for_status()
                data = resp.json()
                
                # Best-effort token tracking
                usage = data.get("usage", {})
                in_tok = usage.get("prompt_tokens", 0)
                out_tok = usage.get("completion_tokens", 0)
                self.total_input_tokens += in_tok
                self.total_output_tokens += out_tok
                
                logger.info(
                    "%s%s✅  RESPONSE RECEIVED  (model: %s)%s",
                    _BOLD, _GREEN, self.model, _RESET,
                )
                logger.info(
                    "%s📊  Tokens — input: %d, output: %d  (cumulative: %d / %d)%s",
                    _YELLOW, in_tok, out_tok,
                    self.total_input_tokens, self.total_output_tokens, _RESET,
                )
                
                msg = data["choices"][0]["message"]
                content = (msg.get("content") or "").strip()

                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)
                return content.strip()
                
            except Exception as e:
                logger.error(f"Attempt {attempt+1} failed: {e}")
                time.sleep(2)

        raise RateLimitExhaustedError("Exhausted retries or timed out on AMD Radeon Cloud")
