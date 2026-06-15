"""Lógica de salas: listado del usuario, chats directos (DM) y grupos."""

import uuid

from db import query


def list_for_user(uid: str) -> list[dict]:
    """Salas a las que pertenece el usuario, con sus miembros y último mensaje."""
    rows = query(
        """SELECT r.id, r.type, r.name,
                  r.last_message AS lastMessage,
                  r.last_message_at AS lastMessageAt,
                  GROUP_CONCAT(rm2.user_uid) AS members
           FROM rooms r
           JOIN room_members rm  ON rm.room_id = r.id AND rm.user_uid = %(uid)s
           JOIN room_members rm2 ON rm2.room_id = r.id
           GROUP BY r.id
           ORDER BY r.last_message_at DESC""",
        {"uid": uid},
        fetch=True,
    )
    for r in rows:
        r["members"] = r["members"].split(",") if r["members"] else []
    return rows


def open_dm(me_uid: str, other_uid: str) -> dict:
    """Abre (o crea si no existe) el chat directo entre dos usuarios."""
    rid = "dm__" + "__".join(sorted([me_uid, other_uid]))
    query("INSERT IGNORE INTO rooms (id, type, name) VALUES (%(id)s, 'dm', '')", {"id": rid})
    query(
        """INSERT IGNORE INTO room_members (room_id, user_uid)
           VALUES (%(id)s, %(a)s), (%(id)s, %(b)s)""",
        {"id": rid, "a": me_uid, "b": other_uid},
    )
    return {"id": rid, "type": "dm", "name": "", "members": [me_uid, other_uid]}


def create_group(name: str, members: list[str]) -> dict:
    """Crea un grupo nuevo con los miembros indicados."""
    rid = str(uuid.uuid4())
    query(
        "INSERT INTO rooms (id, type, name) VALUES (%(id)s, 'group', %(name)s)",
        {"id": rid, "name": name},
    )
    for uid in members:
        query(
            "INSERT IGNORE INTO room_members (room_id, user_uid) VALUES (%(id)s, %(uid)s)",
            {"id": rid, "uid": uid},
        )
    return {"id": rid, "type": "group", "name": name, "members": members}


def add_members(room_id: str, members: list[str]) -> dict:
    """Añade miembros a un grupo existente (ignora los que ya están)."""
    for uid in members:
        query(
            "INSERT IGNORE INTO room_members (room_id, user_uid) VALUES (%(id)s, %(uid)s)",
            {"id": room_id, "uid": uid},
        )
    return {"id": room_id, "members": member_uids(room_id)}


def leave_group(room_id: str, uid: str) -> dict:
    """Saca a un usuario de un grupo."""
    query(
        "DELETE FROM room_members WHERE room_id = %(id)s AND user_uid = %(uid)s",
        {"id": room_id, "uid": uid},
    )
    return {"id": room_id, "members": member_uids(room_id)}


def delete_room(room_id: str) -> None:
    """Elimina sala, miembros y mensajes."""
    query("DELETE FROM messages WHERE room_id = %(rid)s", {"rid": room_id})
    query("DELETE FROM room_members WHERE room_id = %(rid)s", {"rid": room_id})
    query("DELETE FROM rooms WHERE id = %(rid)s", {"rid": room_id})


def member_uids(room_id: str) -> list[str]:
    """UIDs de los miembros de una sala (para reenviar mensajes en vivo)."""
    rows = query(
        "SELECT user_uid FROM room_members WHERE room_id = %(rid)s",
        {"rid": room_id},
        fetch=True,
    )
    return [r["user_uid"] for r in rows]
