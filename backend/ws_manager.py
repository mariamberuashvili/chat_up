"""Gestor de conexiones WebSocket activas, indexadas por uid.

Permite reenviar un mensaje solo a las conexiones de los miembros de una sala.
"""

from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    def add(self, uid: str, ws: WebSocket) -> None:
        self._connections.setdefault(uid, set()).add(ws)

    def remove(self, uid: str, ws: WebSocket) -> None:
        socks = self._connections.get(uid)
        if socks:
            socks.discard(ws)
            if not socks:
                self._connections.pop(uid, None)

    def is_online(self, uid: str) -> bool:
        return bool(self._connections.get(uid))

    def sockets_for(self, uids: list[str]) -> Set[WebSocket]:
        """Sockets activos de todos los uids indicados."""
        targets: Set[WebSocket] = set()
        for uid in uids:
            targets.update(self._connections.get(uid, set()))
        return targets


# Instancia única compartida por toda la app.
manager = ConnectionManager()
