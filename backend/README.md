# Backend del chat (Python)

FastAPI + WebSocket + MySQL. Auth la gestiona Firebase en el frontend.

## Pasos

1. Crea la base de datos ejecutando [`../db/schema.sql`](../db/schema.sql) en tu MySQL.
2. Copia `.env.example` a `.env` y pon tus credenciales de MySQL.
3. Instala dependencias y arranca:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

El servidor queda en `http://127.0.0.1:8000` y el WebSocket en
`ws://127.0.0.1:8000/chat?uid=<UID_DE_FIREBASE>`.

## Estructura

```
backend/
  main.py            # punto de entrada: app, CORS, /uploads y routers
  config.py          # constantes (carpeta de subidas, CORS)
  db.py              # pool de conexiones MySQL + helper query()
  models.py          # esquemas Pydantic (peticiones y respuestas)
  ws_manager.py      # gestor de conexiones WebSocket activas
  routers/           # endpoints agrupados por dominio
    users.py  rooms.py  messages.py  chat_ws.py
  services/          # lógica y consultas a la base de datos
    users.py  rooms.py  messages.py
```

La regla: los `routers` reciben la petición y delegan en los `services`,
que son los únicos que tocan la base de datos.

## Endpoints
- `POST /users/sync` — registra al usuario y lo marca conectado.
- `GET  /users` — directorio de usuarios.
- `GET  /rooms?uid=` — rooms del usuario.
- `POST /rooms/dm` — abre/crea un DM.
- `POST /rooms/group` — crea un grupo.
- `GET  /rooms/{id}/messages` — historial de un room.
- `WS   /chat?uid=` — mensajes en vivo (envelope JSON `{cid, roomId, text, senderUid, senderName}`).
