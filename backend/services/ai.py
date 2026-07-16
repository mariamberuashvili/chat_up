"""Integración con Groq (Llama 3): genera la respuesta del bot de IA."""

import asyncio
from groq import Groq

from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

AI_UID  = "ai-bot"
AI_NAME = "Inteligente IA"

_SYSTEM = (
    "Eres Inteligente, un asistente de chat integrado en una aplicación. "
    "Participa en la conversación de forma natural, amigable y concisa. "
    "Responde siempre en el mismo idioma del último mensaje recibido. "
    "No digas que eres una IA a menos que te lo pregunten explícitamente."
)

_RAG_SYSTEM = (
    "Eres un asistente que responde EXCLUSIVAMENTE con información de los documentos que se te proporcionan. "
    "Puede haber varios documentos: usa información de todos los que sean relevantes para la pregunta, "
    "no solo del primero o el último. Indica de qué documento sale cada dato si la pregunta compara varios. "
    "Si la información solicitada no está en ningún documento, responde exactamente: "
    "'No encuentro esa información en el PDF.' "
    "No uses conocimiento externo. No inventes ni completes información."
)


def _build_messages(history: list[dict]) -> list[dict]:
    messages = [{"role": "system", "content": _SYSTEM}]
    for m in history[-20:]:
        role = "assistant" if m.get("senderUid") == AI_UID else "user"
        name = m.get("senderName", "Usuario")
        text = m.get("text", "")
        content = f"{name}: {text}" if role == "user" else text
        messages.append({"role": role, "content": content})
    return messages


async def respond(history: list[dict]) -> str:
    if not history:
        return ""

    messages = _build_messages(history)

    def _call() -> str:
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=512,
                temperature=0.7,
            )
            text = completion.choices[0].message.content
            return text.strip() if text else "No pude generar respuesta."
        except Exception as e:
            print("❌ Error Groq:", str(e))
            return "Error al generar respuesta."

    return await asyncio.to_thread(_call)


async def respond_rag(query: str, chunks: list[tuple[str, str]]) -> str:
    """Responde usando SOLO los fragmentos recuperados (búsqueda semántica) de los PDFs
    subidos, y agrega al final qué documentos se usaron como fuente."""
    if not chunks:
        return "No encuentro esa información en el PDF."

    context = "\n\n---\n\n".join(f"[Documento: {filename}]\n{text}" for filename, text in chunks)
    messages = [
        {
            "role": "system",
            "content": f"{_RAG_SYSTEM}\n\nDOCUMENTO:\n{context}",
        },
        {"role": "user", "content": query},
    ]

    # Fuentes realmente usadas para armar el contexto, en el orden en que fueron recuperadas.
    sources = list(dict.fromkeys(filename for filename, _ in chunks))

    def _call() -> str:
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                max_tokens=512,
                temperature=0.1,
            )
            text = completion.choices[0].message.content
            answer = text.strip() if text else "No encuentro esa información en el PDF."
        except Exception as e:
            print("❌ Error Groq RAG:", str(e))
            return "Error al generar respuesta."

        if answer == "No encuentro esa información en el PDF.":
            return answer
        return f"{answer}\n\nFuentes: {', '.join(sources)}"

    return await asyncio.to_thread(_call)
