"""Tests for chatbot/groq_client.py using mocks — no real API calls."""

from __future__ import annotations

import os
import pytest


def test_complete_missing_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from chatbot import groq_client
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        groq_client.complete([{"role": "user", "content": "hi"}], "sys")


def test_complete_returns_content(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    class FakeMessage:
        content = "Hello from mock"

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = FakeChat()

    import chatbot.groq_client as gc
    monkeypatch.setattr(gc, "_client", lambda: FakeGroq("test-key"))

    result = gc.complete([{"role": "user", "content": "hi"}], "system prompt")
    assert result == "Hello from mock"


def test_summarize_empty_messages(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    from chatbot import groq_client
    result = groq_client.summarize([])
    assert result == ""
