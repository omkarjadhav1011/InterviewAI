"""Shared utilities for calling Google Gemini with timeouts and parsing JSON responses.

Used by services/gemini_service.py and services/resume_parser.py so we have a single
place that enforces request timeouts and tolerates the variety of JSON shapes Gemini
returns (raw JSON, ```json fenced, prose-wrapped, single-quoted, etc.).
"""
import concurrent.futures
import json
import logging
import re

logger = logging.getLogger(__name__)


def call_gemini_with_timeout(model, prompt: str, timeout: int) -> str:
    """Run model.generate_content(prompt) in a worker thread; raise TimeoutError if it exceeds timeout seconds.

    Returns the raw response text. Caller is responsible for JSON parsing.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(model.generate_content, prompt)
        try:
            response = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.error("Gemini call exceeded %ss timeout", timeout)
            raise TimeoutError(f"Gemini call exceeded {timeout}s")
    if not response or not getattr(response, "text", None):
        raise ValueError("Gemini returned empty response")
    return response.text


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_response(raw: str):
    """Strip markdown fences, parse JSON, fall back to regex-bracketed extraction.

    Returns the parsed object (dict or list). Raises ValueError if no JSON can be recovered.
    """
    if raw is None:
        raise ValueError("empty Gemini response")
    text = _FENCE_RE.sub("", raw.strip()).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back: try the first {...} or [...] in the response
    for pattern in (r"\{.*\}", r"\[.*\]"):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                continue

    # Last resort: replace single quotes with double quotes
    try:
        return json.loads(text.replace("'", '"'))
    except json.JSONDecodeError:
        pass

    raise ValueError(f"non-JSON Gemini response: {text[:200]}")
