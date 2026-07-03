"""RAG: extrae texto de PDFs, genera embeddings y los indexa en Qdrant."""

import asyncio
import io
import uuid

import pypdf
from qdrant_client import QdrantClient

QDRANT_PATH = "./qdrant_storage"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=QDRANT_PATH)
    return _client


def _col(room_id: str) -> str:
    """Convierte el room_id en nombre de colección válido para Qdrant."""
    return "pdf_" + room_id.replace("__", "_").replace("-", "_")


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


async def process_pdf(pdf_bytes: bytes, room_id: str) -> int:
    """Procesa el PDF y guarda los chunks en Qdrant. Devuelve el nº de chunks."""

    def _sync() -> int:
        client = _get_client()
        col = _col(room_id)

        existing = {c.name for c in client.get_collections().collections}
        if col in existing:
            client.delete_collection(col)

        text = _extract_text(pdf_bytes)
        chunks = _chunk(text)
        if not chunks:
            return 0

        client.add(
            collection_name=col,
            documents=chunks,
            ids=[str(uuid.uuid4()) for _ in chunks],
        )
        return len(chunks)

    return await asyncio.to_thread(_sync)


async def search(query: str, room_id: str, top_k: int = 5) -> list[str]:
    """Busca los chunks más relevantes para la pregunta del usuario."""

    def _sync() -> list[str]:
        client = _get_client()
        col = _col(room_id)
        existing = {c.name for c in client.get_collections().collections}
        if col not in existing:
            return []
        results = client.query(collection_name=col, query_text=query, limit=top_k)
        texts = []
        for r in results:
            doc = r.payload.get("document") if r.payload else None
            if doc:
                texts.append(doc)
        return texts

    return await asyncio.to_thread(_sync)


def has_pdf(room_id: str) -> bool:
    """Comprueba si hay un PDF indexado para esta sala."""
    try:
        client = _get_client()
        col = _col(room_id)
        existing = {c.name for c in client.get_collections().collections}
        if col not in existing:
            return False
        return client.count(collection_name=col).count > 0
    except Exception:
        return False
