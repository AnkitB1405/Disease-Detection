"""Session CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.converters import to_session_out
from api.deps import get_session_or_404
from api.runtime import STORE
from api.schemas import ChatMessage, SessionCreate, SessionDetail, SessionOut
from api.services import visible_history
from tracking.models import CropSession

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut)
def create_session(body: SessionCreate) -> SessionOut:
    session = STORE.create(body.display_name)
    return to_session_out(session)


@router.get("", response_model=list[SessionOut])
def list_sessions() -> list[SessionOut]:
    return [to_session_out(s) for s in STORE.list()]


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session: CropSession = Depends(get_session_or_404)) -> SessionDetail:
    base = to_session_out(session)
    return SessionDetail(
        **base.model_dump(),
        mode=STORE.get_mode(session.session_id),
        chat_history=[ChatMessage(**m) for m in visible_history(session)],
    )


@router.delete("/{session_id}", status_code=204)
def delete_session(session: CropSession = Depends(get_session_or_404)) -> None:
    STORE.delete(session.session_id)
