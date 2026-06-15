"""Lógica de usuarios: alta/sincronización, directorio, presencia y foto."""

import os
import shutil
import time

from fastapi import UploadFile

from config import UPLOAD_DIR
from db import query


def sync_user(uid: str, email: str, display_name: str) -> None:
    """Registra/actualiza al usuario de Firebase y lo marca conectado."""
    query(
        """INSERT INTO users (uid, email, display_name, online)
           VALUES (%(uid)s, %(email)s, %(displayName)s, 1)
           ON DUPLICATE KEY UPDATE
             email = VALUES(email),
             display_name = VALUES(display_name),
             online = 1,
             last_seen = CURRENT_TIMESTAMP(3)""",
        {"uid": uid, "email": email, "displayName": display_name},
    )


def list_users() -> list[dict]:
    return query(
        "SELECT uid, email, display_name AS displayName, photo_url AS photoUrl, online FROM users",
        fetch=True,
    )


def get_user(uid: str) -> dict | None:
    rows = query(
        """SELECT uid, email, display_name AS displayName, photo_url AS photoUrl, online
           FROM users WHERE uid = %(uid)s""",
        {"uid": uid},
        fetch=True,
    )
    return rows[0] if rows else None


def save_photo(uid: str, file: UploadFile) -> str:
    """Guarda la foto de perfil del usuario y devuelve su URL relativa."""
    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    # Nombre con marca de tiempo para refrescar la caché del navegador.
    fname = f"{uid}_{int(time.time())}{ext}"
    path = os.path.join(UPLOAD_DIR, fname)
    with open(path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    photo_url = f"/uploads/{fname}"
    query("UPDATE users SET photo_url = %(p)s WHERE uid = %(uid)s", {"p": photo_url, "uid": uid})
    return photo_url


def set_online(uid: str, online: bool) -> None:
    query(
        "UPDATE users SET online = %(on)s, last_seen = CURRENT_TIMESTAMP(3) WHERE uid = %(uid)s",
        {"on": 1 if online else 0, "uid": uid},
    )
