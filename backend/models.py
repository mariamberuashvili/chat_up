"""Modelos Pydantic: forma de los datos que entran y salen de la API."""

from pydantic import BaseModel


# ----------------------------- Peticiones --------------------------

class UserSync(BaseModel):
    """Alta/actualización del usuario autenticado en Firebase."""
    uid: str
    email: str
    displayName: str


class DmReq(BaseModel):
    """Petición para abrir un chat directo entre dos usuarios."""
    meUid: str
    otherUid: str


class GroupReq(BaseModel):
    """Petición para crear un grupo con una lista de miembros."""
    name: str
    members: list[str]


class AddMembersReq(BaseModel):
    """Petición para añadir miembros a un grupo ya existente."""
    roomId: str
    members: list[str]


class LeaveGroupReq(BaseModel):
    """Petición para que un usuario salga de un grupo."""
    roomId: str
    uid: str


class DeleteRoomReq(BaseModel):
    """Petición para eliminar una sala completa."""
    roomId: str


# ----------------------------- Respuestas --------------------------

class UserOut(BaseModel):
    uid: str
    email: str
    displayName: str
    photoUrl: str | None = None
    online: bool


class RoomOut(BaseModel):
    id: str
    type: str
    name: str
    members: list[str]
    lastMessage: str | None = None
    lastMessageAt: int | None = None


class MessageOut(BaseModel):
    cid: str
    roomId: str
    text: str
    senderUid: str
    senderName: str
    createdAt: int | None = None
