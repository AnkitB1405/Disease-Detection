"""Server-Sent Events helpers."""

from __future__ import annotations

import json

# Headers that keep SSE streaming responsive behind proxies.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def format_sse(event: dict) -> str:
    """Serialize one event dict into an SSE `data:` frame."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
