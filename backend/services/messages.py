"""Lógica de mensajes: historial, guardado y borrado."""

import time
from db import query

from services import unread
from services import rooms as rooms_service


def history(room_id: str) -> list[dict]:
    """Historial de mensajes de una sala en orden cronológico."""
    return query(
        """SELECT cid, room_id AS roomId, text,
                  sender_uid AS senderUid, sender_name AS senderName,
                  UNIX_TIMESTAMP(created_at) * 1000 AS createdAt
           FROM messages
           WHERE room_id = %(rid)s
           ORDER BY created_at ASC""",
        {"rid": room_id},
        fetch=True,
    )


def save(msg: dict) -> None:
    """Persiste un mensaje y actualiza el resumen de la sala."""

    query(
        """INSERT IGNORE INTO messages (cid, room_id, sender_uid, sender_name, text)
           VALUES (%(cid)s, %(roomId)s, %(senderUid)s, %(senderName)s, %(text)s)""",
        {
            "cid": msg["cid"],
            "roomId": msg["roomId"],
            "senderUid": msg["senderUid"],
            "senderName": msg["senderName"],
            "text": msg["text"],
        },
    )

    query(
        "UPDATE rooms SET last_message = %(text)s, last_message_at = %(ts)s WHERE id = %(rid)s",
        {"text": msg["text"], "ts": int(time.time() * 1000), "rid": msg["roomId"]},
    )

    # ✅ AQUÍ SÍ VA LA LÓGICA (DENTRO DE LA FUNCIÓN)
    members = rooms_service.member_uids(msg["roomId"])
    unread.increase(msg["roomId"], msg["senderUid"], members)


def delete(cid: str, sender_uid: str) -> None:
    """Borra un mensaje: solo el autor puede eliminar el suyo."""
    query(
        "DELETE FROM messages WHERE cid = %(cid)s AND sender_uid = %(uid)s",
        {"cid": cid, "uid": sender_uid},
    )