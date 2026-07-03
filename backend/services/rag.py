"""RAG: extrae texto de PDFs y los indexa con BM25 para búsqueda contextual."""

import asyncio
import io

import pypdf
from rank_bm25 import BM25Okapi

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# Almacén en memoria: room_id -> (índice BM25, lista de chunks)
_store: dict[str, tuple] = {}


def _extract_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


def _chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start : start + CHUNK_SIZE].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


async def process_pdf(pdf_bytes: bytes, room_id: str) -> int:
    """Extrae texto, divide en chunks y construye el índice BM25 en memoria."""

    def _sync() -> int:
        text = _extract_text(pdf_bytes)
        chunks = _chunk(text)
        if not chunks:
            return 0
        bm25 = BM25Okapi([_tokenize(c) for c in chunks])
        _store[room_id] = (bm25, chunks)
        return len(chunks)

    return await asyncio.to_thread(_sync)


async def search(query: str, room_id: str, top_k: int = 5) -> list[str]:
    """Devuelve los chunks más relevantes para la pregunta (BM25)."""
    if room_id not in _store:
        return []

    def _sync() -> list[str]:
        bm25, chunks = _store[room_id]
        scores = bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [chunks[i] for i in ranked[:top_k] if scores[i] > 0]

    return await asyncio.to_thread(_sync)


def has_pdf(room_id: str) -> bool:
    """True si hay un PDF indexado para esta sala en la sesión actual."""
    return room_id in _store
