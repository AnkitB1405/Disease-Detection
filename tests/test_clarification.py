"""Tests for chatbot/clarification.py — no real API calls."""

from __future__ import annotations

import pytest
from chatbot.clarification import _parse_response, _strip_fences, _failure_result


def test_strip_fences_removes_json_fence():
    raw = "```json\n{\"has_enough_info\": false, \"question\": \"What crop?\"}\n```"
    assert _strip_fences(raw) == '{"has_enough_info": false, "question": "What crop?"}'


def test_strip_fences_no_fences_unchanged():
    raw = '{"has_enough_info": false, "question": "What crop?"}'
    assert _strip_fences(raw) == raw


def test_parse_response_resolved():
    raw = '{"has_enough_info": true, "crop_type": "Corn", "symptoms_summary": "orange spots on leaves"}'
    result = _parse_response(raw)
    assert result.resolved is True
    assert result.crop_type == "Corn"
    assert result.symptoms_summary == "orange spots on leaves"
    assert result.question is None


def test_parse_response_question():
    raw = '{"has_enough_info": false, "question": "Which part of the plant is affected?"}'
    result = _parse_response(raw)
    assert result.resolved is False
    assert result.question == "Which part of the plant is affected?"
    assert result.crop_type is None


def test_parse_response_malformed_json():
    raw = "This is not JSON at all."
    result = _parse_response(raw)
    assert result.resolved is False
    assert result.question is None  # failure result — caller should track failures


def test_parse_response_embedded_json_in_text():
    raw = 'Some preamble text. {"has_enough_info": false, "question": "How long?"} trailing text.'
    result = _parse_response(raw)
    assert result.resolved is False
    assert result.question == "How long?"


def test_parse_response_missing_required_fields():
    raw = '{"has_enough_info": true}'  # missing crop_type and symptoms_summary
    result = _parse_response(raw)
    assert result.resolved is False


def test_parse_response_fenced_resolved():
    raw = '```\n{"has_enough_info": true, "crop_type": "Grape", "symptoms_summary": "black spots on fruit"}\n```'
    result = _parse_response(raw)
    assert result.resolved is True
    assert result.crop_type == "Grape"
