"""WebSocket del chat en vivo: recibe mensajes y los reenvía a la sala."""

import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import messages as messages_service
from services import unread
from services import rooms as rooms_service
from services import users as users_service
from ws_manager import manager

router = APIRouter()


@router.websocket("/chat")
async def chat_ws(ws: WebSocket, uid: str = ""):
    await ws.accept()
    manager.add(uid, ws)
    if uid:
        users_service.set_online(uid, True)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type in ("read", "mark_read"):
                reader_uid = msg.get("uid") or msg.get("senderUid", "")
                unread.reset(reader_uid, msg.get("roomId", ""))
                continue  # No guardar ni reenviar read receipts

            if msg_type == "delete":
                messages_service.delete(msg.get("cid"), msg.get("senderUid"))
            else:
                msg.setdefault("cid", str(uuid.uuid4()))
                messages_service.save(msg)

            # Reenvía solo a las conexiones de los miembros de la sala.
            targets = manager.sockets_for(rooms_service.member_uids(msg["roomId"]))
            payload = json.dumps(msg)
            for sock in targets:
                try:
                    await sock.send_text(payload)
                except Exception:
                    pass  # Un socket caído no debe impedir el envío al resto.

    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(uid, ws)
        # Si ya no le quedan conexiones, marcar desconectado.
        if uid and not manager.is_online(uid):
            users_service.set_online(uid, False)
