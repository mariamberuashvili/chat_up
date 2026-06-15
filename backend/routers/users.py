"""Endpoints REST de usuarios y presencia."""

from fastapi import APIRouter, File, UploadFile

from models import UserSync
from services import users as users_service

router = APIRouter(tags=["users"])


@router.post("/users/sync")
def users_sync(u: UserSync):
    """Registra/actualiza al usuario de Firebase y lo marca conectado."""
    users_service.sync_user(u.uid, u.email, u.displayName)
    return {"ok": True}


@router.get("/users")
def list_users():
    return users_service.list_users()


@router.get("/users/{uid}")
def get_user(uid: str):
    return users_service.get_user(uid)


@router.post("/users/{uid}/photo")
async def upload_photo(uid: str, file: UploadFile = File(...)):
    """Guarda la foto de perfil del usuario y devuelve su URL."""
    photo_url = users_service.save_photo(uid, file)
    return {"photoUrl": photo_url}
