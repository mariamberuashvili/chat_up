"""WebSocket del chat en vivo: recibe mensajes y los reenvía a la sala."""

import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import ai as ai_service
from services import messages as messages_service
from services import rag as rag_service
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

            # Respuesta de IA: solo si está activada y el emisor no es el bot.
            if (
                msg_type != "delete"
                and msg.get("senderUid") != ai_service.AI_UID
                and rooms_service.is_ai_enabled(msg["roomId"])
            ):
                try:
                    room_id = msg["roomId"]
                    chunks = await rag_service.search(msg.get("text", ""), room_id) if await rag_service.has_pdf(room_id) else []
                    if chunks:
                        # Hay PDF(s) y el mensaje coincide con contenido suyo: responde con RAG.
                        ai_text = await ai_service.respond_rag(msg.get("text", ""), chunks)
                    else:
                        # Sin PDF, o el mensaje no tiene relación con los PDFs subidos: charla normal.
                        history = messages_service.history(room_id)
                        ai_text = await ai_service.respond(history)
                    ai_msg   = {
                        "cid":        str(uuid.uuid4()),
                        "roomId":     room_id,
                        "text":       ai_text,
                        "senderUid":  ai_service.AI_UID,
                        "senderName": ai_service.AI_NAME,
                    }
                    messages_service.save(ai_msg)
                    ai_payload = json.dumps(ai_msg)
                    for sock in manager.sockets_for(rooms_service.member_uids(room_id)):
                        try:
                            await sock.send_text(ai_payload)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[IA ERROR] {type(e).__name__}: {e}")

    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(uid, ws)
        # Si ya no le quedan conexiones, marcar desconectado.
        if uid and not manager.is_online(uid):
            users_service.set_online(uid, False)
