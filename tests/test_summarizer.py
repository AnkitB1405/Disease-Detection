"""Tests for chatbot/summarizer.py — no real API calls."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from chatbot import summarizer
from chatbot.summarizer import MESSAGES_TO_KEEP, total_chars
from tracking.models import CropSession


def _make_session(n_messages: int, chars_per_message: int = 100) -> CropSession:
    session = CropSession(
        session_id="test-session",
        display_name="Test",
        crop_name="Corn",
        disease_name="rust",
        created_at=datetime.now(),
    )
    for i in range(n_messages):
        session.chat_history.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": "x" * chars_per_message,
        })
    return session


def test_total_chars():
    messages = [{"role": "user", "content": "abc"}, {"role": "assistant", "content": "de"}]
    assert total_chars(messages) == 5


def test_no_summarize_below_threshold():
    session = _make_session(n_messages=5, chars_per_message=100)
    result = summarizer.maybe_summarize(session)
    assert result is False
    assert len(session.chat_history) == 5


def test_summarize_triggers_above_threshold():
    # Set a very low threshold for testing
    original_threshold = summarizer.SUMMARIZE_THRESHOLD
    summarizer.SUMMARIZE_THRESHOLD = 50  # 50 chars will trigger immediately

    session = _make_session(n_messages=15, chars_per_message=10)
    # Total = 150 chars > 50 threshold

    with patch("chatbot.groq_client.summarize", return_value="Farmer applied fungicide in week 1."), \
         patch("tracking.persistence.save_session"):
        result = summarizer.maybe_summarize(session)

    assert result is True
    assert session.chat_summary == "Farmer applied fungicide in week 1."
    # Anchor (first message) + summary system message + last MESSAGES_TO_KEEP
    assert len(session.chat_history) == 2 + MESSAGES_TO_KEEP

    summarizer.SUMMARIZE_THRESHOLD = original_threshold


def test_anchor_message_always_preserved():
    original_threshold = summarizer.SUMMARIZE_THRESHOLD
    summarizer.SUMMARIZE_THRESHOLD = 10

    session = _make_session(n_messages=20, chars_per_message=5)
    anchor_content = session.chat_history[0]["content"]

    with patch("chatbot.groq_client.summarize", return_value="summary"), \
         patch("tracking.persistence.save_session"):
        summarizer.maybe_summarize(session)

    assert session.chat_history[0]["content"] == anchor_content

    summarizer.SUMMARIZE_THRESHOLD = original_threshold


def test_messages_for_groq_returns_list():
    session = _make_session(n_messages=3)
    with patch("chatbot.summarizer.maybe_summarize", return_value=False):
        result = summarizer.messages_for_groq(session)
    assert isinstance(result, list)
    assert len(result) == 3
