"""JSON-structured clarification loop for the text-only input path.

Groq is instructed to respond with strict JSON only. This module parses
that JSON, handles malformed output gracefully, and signals when the loop
is resolved so handlers.py can transition to ACTIVE_TREATMENT.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from chatbot import groq_client
from chatbot.prompts import CLARIFICATION_SYSTEM_PROMPT

_MAX_PARSE_RETRIES = 2
_FALLBACK_QUESTION = (
    "Could you describe the symptoms in more detail? "
    "For example: which part of the plant is affected, "
    "what colour or pattern do you see, and how long has it been like this?"
)


@dataclass
class ClarificationResult:
    resolved: bool
    question: str | None         # set when resolved == False
    crop_type: str | None        # set when resolved == True
    symptoms_summary: str | None # set when resolved == True


def process_turn(
    messages: list[dict[str, str]],
    consecutive_failures: int = 0,
) -> ClarificationResult:
    """Run one clarification turn and return the result.

    Parameters
    ----------
    messages:
        Full conversation history to send to Groq (user + assistant turns).
    consecutive_failures:
        Number of JSON parse failures in a row for this session. When this
        reaches _MAX_PARSE_RETRIES, a canned follow-up question is returned
        instead of calling Groq again.
    """
    if consecutive_failures >= _MAX_PARSE_RETRIES:
        return ClarificationResult(
            resolved=False,
            question=_FALLBACK_QUESTION,
            crop_type=None,
            symptoms_summary=None,
        )

    raw = groq_client.complete(
        messages=messages,
        system_prompt=CLARIFICATION_SYSTEM_PROMPT,
        model="llama3-70b-8192",
    )

    return _parse_response(raw)


def _parse_response(raw: str) -> ClarificationResult:
    cleaned = _strip_fences(raw).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try extracting the first {...} block if Groq added extra text
        match = re.search(r"\{[^{}]+\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return _failure_result()
        else:
            return _failure_result()

    if not isinstance(data, dict):
        return _failure_result()

    has_enough = data.get("has_enough_info", False)

    if has_enough:
        crop_type = data.get("crop_type", "")
        symptoms = data.get("symptoms_summary", "")
        if crop_type and symptoms:
            return ClarificationResult(
                resolved=True,
                question=None,
                crop_type=str(crop_type),
                symptoms_summary=str(symptoms),
            )
        return _failure_result()

    question = data.get("question", "")
    if question:
        return ClarificationResult(
            resolved=False,
            question=str(question),
            crop_type=None,
            symptoms_summary=None,
        )

    return _failure_result()


def _strip_fences(text: str) -> str:
    """Remove markdown code fences Groq occasionally wraps JSON in."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


def _failure_result() -> ClarificationResult:
    return ClarificationResult(
        resolved=False,
        question=None,  # caller checks for None to detect parse failure
        crop_type=None,
        symptoms_summary=None,
    )
