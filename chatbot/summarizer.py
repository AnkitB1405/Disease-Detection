"""Rolling context-window summarization.

When the chat history approaches the model's context limit, compresses
older messages into a summary paragraph and pins the original YOLO analysis
message so the LLM always has the ground-truth detection data.

SUMMARIZE_THRESHOLD  — approximate character count at which summarization
                       triggers (70% of llama3-70b's 32 768-token window,
                       using the 1 token ≈ 4 chars heuristic → ~91 750 chars).
MESSAGES_TO_KEEP     — number of most-recent messages preserved verbatim.
"""

from __future__ import annotations

from chatbot import groq_client
from tracking.models import CropSession
from tracking import persistence

SUMMARIZE_THRESHOLD = 91_750   # characters — tune down in tests
MESSAGES_TO_KEEP = 8


def total_chars(messages: list[dict]) -> int:
    return sum(len(m.get("content", "")) for m in messages)


def maybe_summarize(session: CropSession) -> bool:
    """Summarize in-place if the history exceeds the threshold.

    Returns True if summarization was performed, False otherwise.
    The session object is mutated: older messages are replaced by a
    synthetic summary message and session.chat_summary is updated.
    """
    history = session.chat_history
    if total_chars(history) < SUMMARIZE_THRESHOLD:
        return False

    # The first message is the YOLO analysis — never compress it.
    if not history:
        return False

    anchor = history[0]             # original analysis message — always kept
    recent = history[-MESSAGES_TO_KEEP:]
    compressible = history[1: len(history) - MESSAGES_TO_KEEP]

    if not compressible:
        return False

    summary_text = groq_client.summarize(compressible)

    summary_message = {
        "role": "system",
        "content": f"Previous conversation summary:\n{summary_text}",
    }

    session.chat_history = [anchor, summary_message] + list(recent)
    session.chat_summary = summary_text

    persistence.save_session(session)
    return True


def messages_for_groq(session: CropSession) -> list[dict]:
    """Return the message list to send to Groq, triggering summarization first.

    Only `role` and `content` are sent — any UI-only fields (e.g. display_content,
    used to show a shorter farmer-facing version of long internal prompts) are
    stripped here so the Groq API never sees extra keys it doesn't expect.
    """
    maybe_summarize(session)
    return [{"role": m["role"], "content": m["content"]} for m in session.chat_history]