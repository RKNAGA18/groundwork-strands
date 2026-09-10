"""LLM adapter — AWS Bedrock (Claude 3 Haiku) via the Converse API.

Replaces the previous Google Gemini adapter. Uses boto3 bedrock-runtime
client with tenacity retry for throttling resilience.
"""

import json
import logging

import boto3
from botocore.exceptions import ClientError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

# ANSI colour codes for demo-visible terminal logs
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


class RateLimitExhaustedError(Exception):
    """Raised when Bedrock throttling retries are exhausted."""


def _is_throttling_error(exception: Exception) -> bool:
    """Check if the exception is a Bedrock ThrottlingException."""
    if isinstance(exception, ClientError):
        code = exception.response.get("Error", {}).get("Code", "")
        return code in ("ThrottlingException", "TooManyRequestsException")
    return False


class LLMAdapter:
    """Thin wrapper around AWS Bedrock Converse API for easy swapping."""

    def __init__(self):
        """Initialize the adapter with a Bedrock Runtime client."""
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @retry(
        retry=retry_if_exception(_is_throttling_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        reraise=True,
    )
    def _make_api_call(
        self, system_prompt: str, user_message: str, temperature: float
    ) -> dict:
        """Make a single Bedrock Converse API call with retry on throttle."""
        logger.info(
            "%s%s🔷  INVOKING AWS BEDROCK: %s%s",
            _BOLD, _CYAN, settings.LLM_MODEL, _RESET,
        )

        response = self._client.converse(
            modelId=settings.LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_message}],
                }
            ],
            system=[{"text": system_prompt}],
            inferenceConfig={
                "temperature": temperature,
                "maxTokens": 4096,
            },
        )

        logger.info(
            "%s%s✅  BEDROCK RESPONSE RECEIVED  (model: %s, stop: %s)%s",
            _BOLD,
            _GREEN,
            settings.LLM_MODEL,
            response.get("stopReason", "unknown"),
            _RESET,
        )
        return response

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
    ) -> str:
        """Generate a response from AWS Bedrock.

        Args:
            system_prompt: The system instruction for the model.
            user_message: The user message / query.
            temperature: Sampling temperature.

        Returns:
            The model's text response.
        """
        logger.debug(
            "Generating response from Bedrock (model=%s, temp=%f)",
            settings.LLM_MODEL,
            temperature,
        )
        try:
            response = self._make_api_call(system_prompt, user_message, temperature)
        except ClientError as e:
            if _is_throttling_error(e):
                logger.error(
                    "%s❌  Exhausted retries for Bedrock ThrottlingException.%s",
                    _RED, _RESET,
                )
                raise RateLimitExhaustedError(
                    "Exhausted retries for Bedrock ThrottlingException."
                ) from e
            raise

        # --- Track tokens for COST_PER_RUN metric ---
        usage = response.get("usage", {})
        in_tok = usage.get("inputTokens", 0)
        out_tok = usage.get("outputTokens", 0)
        self.total_input_tokens += in_tok
        self.total_output_tokens += out_tok
        logger.info(
            "%s📊  Tokens — input: %d, output: %d  (cumulative: %d / %d)%s",
            _YELLOW, in_tok, out_tok,
            self.total_input_tokens, self.total_output_tokens, _RESET,
        )

        # --- Extract text from Converse response ---
        try:
            text = response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError) as e:
            logger.error("Unexpected Bedrock response structure: %s", e)
            raise ValueError("Could not extract text from Bedrock response") from e

        return text
