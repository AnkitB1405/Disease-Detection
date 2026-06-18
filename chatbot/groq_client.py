"""Groq API wrapper — complete, stream, and summarize.

Reads GROQ_API_KEY from the environment.
No Streamlit imports — callers handle st.write_stream themselves.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_SUMMARIZE_MODEL = "llama3-8b-8192"  # smaller/faster for summarization


def _client():
    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError(
            "groq package is not installed. Run: pip install -r requirements.txt"
        ) from exc

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. "
            "Export it before starting the app: export GROQ_API_KEY=your_key"
        )
    return Groq(api_key=api_key)


def complete(
    messages: list[dict[str, str]],
    system_prompt: str,
    model: str = _DEFAULT_MODEL,
) -> str:
    """Blocking call — returns the full response string.

    Used for structured JSON responses (clarification loop) where the
    response must be parsed atomically before displaying anything.
    """
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = _client().chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=0.2,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


def stream(
    messages: list[dict[str, str]],
    system_prompt: str,
    model: str = _DEFAULT_MODEL,
) -> Iterator[str]:
    """Streaming call — yields text chunks.

    Pass the returned iterator directly to st.write_stream() in the UI layer.
    Used for treatment plan responses so the farmer sees tokens as they arrive.
    """
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    with _client().chat.completions.stream(
        model=model,
        messages=full_messages,
        temperature=0.3,
        max_tokens=2048,
    ) as s:
        for chunk in s:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


def summarize(
    messages_to_compress: list[dict[str, str]],
    model: str = _SUMMARIZE_MODEL,
) -> str:
    """Summarize a slice of chat history into one compact paragraph.

    Called by chatbot/summarizer.py when the context window approaches capacity.
    """
    if not messages_to_compress:
        return ""

    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages_to_compress
    )
    prompt = (
        "Summarize the following crop disease treatment conversation "
        "in 3–5 concise sentences. Preserve: the confirmed disease, "
        "the medications discussed, their schedule, and any progress "
        "notes the farmer reported. Do not add opinions or new advice.\n\n"
        f"{conversation_text}"
    )
    response = _client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=512,
    )
    return response.choices[0].message.content or ""