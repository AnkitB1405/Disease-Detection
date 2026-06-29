"""Text chat: clarification loop + follow-up treatment chat, streamed over SSE."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.deps import get_session_or_404
from api.runtime import STORE
from api.schemas import MessageIn
from api.services import message_events
from api.sse import SSE_HEADERS, format_sse
from tracking.models import CropSession

LOGGER = logging.getLogger("api.chat")
router = APIRouter(prefix="/api/sessions", tags=["chat"])


@router.post("/{session_id}/messages")
def post_message(
    body: MessageIn,
    session: CropSession = Depends(get_session_or_404),
) -> StreamingResponse:
    """Send one user message. Streams the assistant reply as SSE.

    Emits {"type": "question"} (clarification) or a series of
    {"type": "token"} events (treatment/follow-up), then {"type": "done"}.
    """

    def gen():
        try:
            for event in message_events(session, body.text, STORE):
                yield format_sse(event)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Message stream failed")
            yield format_sse({"type": "error", "content": str(exc)})
        yield format_sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
