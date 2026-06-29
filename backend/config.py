"""Configuración de la aplicación (constantes y ajustes leídos del entorno)."""

import os
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

# Carpeta donde se guardan archivos subidos (ej. fotos de perfil)
UPLOAD_DIR = "uploads"

# CORS (en producción deberías restringirlo, no usar "*")
CORS_ORIGINS = ["*"]

# Clave de API de Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY no está configurada en el archivo .env")