"""Endpoint REST del historial de mensajes de una sala."""

from fastapi import APIRouter

from services import messages as messages_service
from services import unread

router = APIRouter(tags=["messages"])


@router.get("/rooms/{room_id}/messages")
def get_messages(room_id: str):
    return messages_service.history(room_id)


@router.get("/users/{uid}/unread")
def get_unread(uid: str):
    return unread.get_all(uid)