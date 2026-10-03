"""LLM-as-judge client for Assay.

This module calls an LLM to evaluate RAG quality. It uses the OpenAI-compatible
API, so it works with OpenRouter, OpenAI, Ollama, and any other provider that
follows the same format.

Configuration comes from environment variables. See config.py for details.

If the judge is not configured (no API key), these functions raise JudgeNotConfiguredError.
"""

import json
from dataclasses import dataclass

from openai import OpenAI

from assay.config import settings


class JudgeError(Exception):
    """Raised when the judge call fails."""

    pass


class JudgeNotConfiguredError(JudgeError):
    """Raised when the judge is not configured."""

    pass


@dataclass
class JudgeResult:
    """Result of a single judge call."""

    score: float
    reason: str
    raw_response: str


def _client() -> OpenAI:
    """Create an OpenAI-compatible client from settings."""
    if not settings.judge_enabled:
        raise JudgeNotConfiguredError(
            "Judge is not configured. Set ASSAY_JUDGE_PROVIDER, "
            "ASSAY_JUDGE_MODEL, and ASSAY_JUDGE_API_KEY."
        )
    return OpenAI(
        api_key=settings.judge_api_key,
        base_url=settings.judge_base_url,
        timeout=settings.judge_timeout,
    )


GROUNDEDNESS_PROMPT = """You are a strict groundedness judge.

You will be given a question, an answer, and a set of contexts.
Your job is to determine whether every claim in the answer is
supported by the contexts.

Rules:
- If the answer contains claims not supported by the contexts,
  it is not grounded.
- If the answer says "I do not have enough information" or similar,
  and the contexts do not contain the answer, it is grounded.
- Do not use outside knowledge. Only judge based on the contexts
  provided.

Question:
{question}

Answer:
{answer}

Contexts:
{contexts}

You MUST reply with a JSON object. Do NOT include any text before
or after the JSON. Do NOT wrap the JSON in markdown fences. Do NOT
add safety notes. Just the JSON object.

Format:
{{"grounded": true, "unsupported_claims": [], "confidence": 0.95, "reason": "..."}}

Your response must start with {{ and end with }}.
"""


def _call_with_retry(client: OpenAI, prompt: str, max_retries: int = 3) -> object:
    """Call the judge with retry on rate limit and server errors."""
    import time

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model=settings.judge_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str
            is_server_error = "500" in error_str or "502" in error_str or "503" in error_str

            if is_rate_limit or is_server_error:
                wait = 2 ** attempt  # 1s, 2s, 4s
                last_error = e
                time.sleep(wait)
                continue
            raise JudgeError(f"Judge call failed: {e}") from e

    raise JudgeError(f"Judge call failed after {max_retries} retries: {last_error}")


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from the model output.

    Some models wrap JSON in markdown fences or add text before/after.
    This function tries hard to find a valid JSON object.
    """
    if not text:
        return None

    # Try direct parse first
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Try to find JSON inside markdown fences
    import re

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            result = json.loads(fenced.group(1))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Try to find the first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            result = json.loads(brace_match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Last resort: parse text for grounded/unsafe signals
    lowered = text.lower()
    if "unsafe" in lowered or "not grounded" in lowered or "unsupported" in lowered:
        return {"grounded": False, "reason": text, "confidence": 0.5}
    if "safe" in lowered or "grounded" in lowered or "supported" in lowered:
        return {"grounded": True, "reason": text, "confidence": 0.5}

    return None


def judge_groundedness(
    question: str,
    answer: str,
    contexts: list[str],
) -> JudgeResult:
    """Judge whether the answer is grounded in the contexts.

    Returns a JudgeResult with score 1.0 if grounded, 0.0 if not.
    """
    if not answer or not contexts:
        return JudgeResult(score=0.0, reason="Empty answer or contexts.", raw_response="")

    context_text = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts))
    prompt = GROUNDEDNESS_PROMPT.format(
        question=question,
        answer=answer,
        contexts=context_text,
    )

    client = _client()
    response = _call_with_retry(client, prompt)

    raw = response.choices[0].message.content or ""

    # If the response is empty, try once more.
    if not raw.strip():
        response = _call_with_retry(client, prompt, max_retries=2)
        raw = response.choices[0].message.content or ""

    parsed = _extract_json(raw)
    if parsed is None:
        raise JudgeError(f"Judge returned invalid JSON: {raw[:200]}")

    grounded = parsed.get("grounded")
    if not isinstance(grounded, bool):
        raise JudgeError(f"Judge returned invalid 'grounded' field: {parsed}")

    return JudgeResult(
        score=1.0 if grounded else 0.0,
        reason=parsed.get("reason", ""),
        raw_response=raw,
    )
