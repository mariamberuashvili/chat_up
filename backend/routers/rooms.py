"""Endpoints REST de salas: listado, chats directos y grupos."""

import json

from fastapi import APIRouter

from models import AddMembersReq, AiRoomReq, DeleteRoomReq, DmReq, GroupReq, LeaveGroupReq
from services import rooms as rooms_service
from ws_manager import manager

router = APIRouter(tags=["rooms"])


@router.get("/rooms")
def list_rooms(uid: str):
    return rooms_service.list_for_user(uid)


@router.post("/rooms/dm")
def open_dm(req: DmReq):
    return rooms_service.open_dm(req.meUid, req.otherUid)


@router.post("/rooms/group")
def create_group(req: GroupReq):
    return rooms_service.create_group(req.name, req.members)


@router.post("/rooms/group/members")
def add_members(req: AddMembersReq):
    return rooms_service.add_members(req.roomId, req.members)


@router.post("/rooms/group/leave")
def leave_group(req: LeaveGroupReq):
    return rooms_service.leave_group(req.roomId, req.uid)


@router.post("/rooms/ai")
def open_ai_room(req: AiRoomReq):
    """Crea (o devuelve) el chat privado del usuario con la IA."""
    return rooms_service.create_ai_room(req.uid)


@router.post("/rooms/{room_id}/ai-toggle")
def ai_toggle(room_id: str):
    """Activa o desactiva la IA en una sala existente."""
    enabled = rooms_service.toggle_ai(room_id)
    return {"aiEnabled": enabled}


@router.post("/rooms/delete")
async def delete_room(req: DeleteRoomReq):
    members = rooms_service.member_uids(req.roomId)
    rooms_service.delete_room(req.roomId)
    payload = json.dumps({"type": "deleted", "roomId": req.roomId})
    for sock in manager.sockets_for(members):
        try:
            await sock.send_text(payload)
        except Exception:
            pass
    return {"ok": True}
