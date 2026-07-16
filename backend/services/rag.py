"""RAG: extrae texto de PDFs y los indexa con BM25 para búsqueda contextual.

Los PDFs se guardan en MySQL (tabla pdf_docs) para que sobrevivan a un reinicio
del proceso: Render (plan free) reinicia el backend por inactividad o en cada
deploy, y si solo viviera en memoria se perdían silenciosamente.
"""

import asyncio
import json
import uuid

import pymupdf
from rank_bm25 import BM25Okapi

from db import query

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MAX_PDFS_PER_ROOM = 3
CHUNKS_PER_DOC = 3  # cuántos fragmentos como máximo se toman de CADA pdf en una búsqueda

# room_id -> lista de PDFs cargados en memoria: [{"id", "filename", "chunks"}, ...]
# Es una cache del contenido de MySQL para no reconstruir el índice BM25 en cada mensaje.
_docs: dict[str, list[dict]] = {}
_loaded_rooms: set[str] = set()  # qué salas ya se hidrataron desde la DB en este proceso

# room_id -> índice BM25 combinado de TODOS los pdfs de la sala + a qué doc pertenece cada chunk.
_index: dict[str, dict] = {}


def _extract_text(pdf_bytes: bytes) -> str:
    # PyMuPDF es una libreria en C (mucho mas rapida que pypdf, que es Python puro).
    # Con PDFs grandes pypdf podia tardar tanto que Render cortaba la conexion (timeout).
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


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


def _load_from_db(room_id: str) -> None:
    """Trae los PDFs de la sala desde MySQL si este proceso todavía no los tiene en memoria."""
    if room_id in _loaded_rooms:
        return
    rows = query(
        "SELECT id, filename, chunks FROM pdf_docs WHERE room_id = %(room_id)s ORDER BY created_at",
        {"room_id": room_id},
        fetch=True,
    )
    _docs[room_id] = [
        {"id": r["id"], "filename": r["filename"], "chunks": json.loads(r["chunks"])} for r in rows
    ]
    _loaded_rooms.add(room_id)
    _rebuild_index(room_id)


def _rebuild_index(room_id: str) -> None:
    docs = _docs.get(room_id, [])
    chunks: list[str] = []
    owner: list[int] = []  # owner[i] = índice del doc dueño de chunks[i]
    for doc_idx, doc in enumerate(docs):
        for c in doc["chunks"]:
            chunks.append(c)
            owner.append(doc_idx)

    if not chunks:
        _index.pop(room_id, None)
        return

    _index[room_id] = {
        "bm25": BM25Okapi([_tokenize(c) for c in chunks]),
        "chunks": chunks,
        "owner": owner,
    }


async def count_pdfs(room_id: str) -> int:
    def _sync() -> int:
        _load_from_db(room_id)
        return len(_docs.get(room_id, []))

    return await asyncio.to_thread(_sync)


async def list_pdfs(room_id: str) -> list[dict]:
    def _sync() -> list[dict]:
        _load_from_db(room_id)
        return [{"id": doc["id"], "filename": doc["filename"]} for doc in _docs.get(room_id, [])]

    return await asyncio.to_thread(_sync)


async def remove_pdf(room_id: str, doc_id: str) -> bool:
    """Borra un PDF de la sala (DB + memoria) y reconstruye el índice. True si existía."""

    def _sync() -> bool:
        _load_from_db(room_id)
        docs = _docs.get(room_id, [])
        remaining = [d for d in docs if d["id"] != doc_id]
        if len(remaining) == len(docs):
            return False
        query("DELETE FROM pdf_docs WHERE id = %(id)s AND room_id = %(room_id)s", {"id": doc_id, "room_id": room_id})
        _docs[room_id] = remaining
        _rebuild_index(room_id)
        return True

    return await asyncio.to_thread(_sync)


async def process_pdf(pdf_bytes: bytes, room_id: str, filename: str) -> int:
    """Extrae texto, lo divide en chunks, lo guarda en MySQL y reconstruye el índice."""

    def _sync() -> int:
        _load_from_db(room_id)
        text = _extract_text(pdf_bytes)
        chunks = _chunk(text)
        if not chunks:
            return 0
        doc_id = uuid.uuid4().hex
        query(
            "INSERT INTO pdf_docs (id, room_id, filename, chunks) VALUES (%(id)s, %(room_id)s, %(filename)s, %(chunks)s)",
            {"id": doc_id, "room_id": room_id, "filename": filename, "chunks": json.dumps(chunks)},
        )
        _docs.setdefault(room_id, []).append({"id": doc_id, "filename": filename, "chunks": chunks})
        _rebuild_index(room_id)
        return len(chunks)

    return await asyncio.to_thread(_sync)


async def search(query_text: str, room_id: str, top_k: int = CHUNKS_PER_DOC) -> list[tuple[str, str]]:
    """Devuelve (filename, chunk) con los mejores fragmentos de CADA pdf relevante para la
    pregunta. Usa un único índice BM25 combinado (estadísticas correctas) pero agrupa los
    resultados por documento para que uno solo no eclipse a los demás."""

    def _sync() -> list[tuple[str, str]]:
        _load_from_db(room_id)
        idx = _index.get(room_id)
        docs = _docs.get(room_id, [])
        if not idx:
            return []

        scores = idx["bm25"].get_scores(_tokenize(query_text))

        by_doc: dict[int, list[tuple[float, int]]] = {}
        for i, (score, doc_idx) in enumerate(zip(scores, idx["owner"])):
            by_doc.setdefault(doc_idx, []).append((score, i))

        results: list[tuple[str, str]] = []
        for doc_idx in sorted(by_doc):
            entries = sorted(by_doc[doc_idx], key=lambda t: t[0], reverse=True)
            filename = docs[doc_idx]["filename"]
            for score, i in entries[:top_k]:
                if score > 0:
                    results.append((filename, idx["chunks"][i]))
        return results

    return await asyncio.to_thread(_sync)


async def has_pdf(room_id: str) -> bool:
    """True si hay al menos un PDF indexado para esta sala."""

    def _sync() -> bool:
        _load_from_db(room_id)
        return bool(_docs.get(room_id))

    return await asyncio.to_thread(_sync)
