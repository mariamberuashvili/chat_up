from collections import defaultdict

# unread[user_id][room_id] = count
unread = defaultdict(lambda: defaultdict(int))


def increase(room_id: str, sender_uid: str, members: list[str]):
    """
    Incrementa contador para todos los miembros excepto el emisor
    """
    for uid in members:
        if uid != sender_uid:
            unread[uid][room_id] += 1


def reset(uid: str, room_id: str):
    """
    Resetea contador cuando el usuario abre el chat
    """
    unread[uid][room_id] = 0


def get(uid: str, room_id: str) -> int:
    """
    Devuelve contador de no leídos
    """
    return unread[uid][room_id]


def get_all(uid: str) -> dict:
    """
    Devuelve todos los contadores del usuario
    """
    return dict(unread[uid])