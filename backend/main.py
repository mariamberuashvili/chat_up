
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import CORS_ORIGINS, UPLOAD_DIR
from routers import chat_ws, messages, pdf, rooms, users

ANGULAR_DIR = Path(__file__).parent.parent / "dist" / "WebSocket" / "browser"

app = FastAPI(title="Chat backend")

# Permite que el frontend Angular (otro puerto) llame a la API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sin este handler los errores 500 no llevan headers CORS y el navegador
# los bloquea mostrando un error de CORS en lugar del error real.
@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# Carpeta de fotos de perfil, servida en /uploads/<archivo>.
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Routers (cada uno agrupa endpoints de un dominio).
app.include_router(users.router)
app.include_router(rooms.router)
app.include_router(messages.router)
app.include_router(pdf.router)
app.include_router(chat_ws.router)

# Sirve el frontend Angular para cualquier ruta desconocida (SPA fallback).
# Esto permite que al refrescar /chat, /login, etc. Angular tome el control.
if ANGULAR_DIR.exists():
    @app.get("/{full_path:path}")
    async def serve_angular(full_path: str):
        file = ANGULAR_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(ANGULAR_DIR / "index.html")
