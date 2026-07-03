"""RAG: extrae texto de PDFs y los indexa con BM25 para búsqueda contextual."""

import asyncio
import uuid

import pymupdf
from rank_bm25 import BM25Okapi

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MAX_PDFS_PER_ROOM = 3
CHUNKS_PER_DOC = 3  # cuántos fragmentos como máximo se toman de CADA pdf en una búsqueda

# room_id -> lista de PDFs subidos: [{"filename": str, "chunks": [str, ...]}, ...]
_docs: dict[str, list[dict]] = {}

# room_id -> índice BM25 combinado de TODOS los pdfs de la sala + a qué doc pertenece cada chunk.
# El BM25 necesita un corpus combinado para que el idf tenga sentido: calculado por-documento
# (un índice por pdf) da estadísticas erróneas cuando un pdf tiene pocos fragmentos.
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


def count_pdfs(room_id: str) -> int:
    return len(_docs.get(room_id, []))


def list_pdfs(room_id: str) -> list[dict]:
    return [{"id": doc["id"], "filename": doc["filename"]} for doc in _docs.get(room_id, [])]


def remove_pdf(room_id: str, doc_id: str) -> bool:
    """Borra un PDF de la sala por su id y reconstruye el índice. True si existía."""
    docs = _docs.get(room_id, [])
    remaining = [d for d in docs if d["id"] != doc_id]
    if len(remaining) == len(docs):
        return False
    _docs[room_id] = remaining
    _rebuild_index(room_id)
    return True


async def process_pdf(pdf_bytes: bytes, room_id: str, filename: str) -> int:
    """Extrae texto, lo divide en chunks y reconstruye el índice combinado de la sala."""

    def _sync() -> int:
        text = _extract_text(pdf_bytes)
        chunks = _chunk(text)
        if not chunks:
            return 0
        doc = {"id": uuid.uuid4().hex, "filename": filename, "chunks": chunks}
        _docs.setdefault(room_id, []).append(doc)
        _rebuild_index(room_id)
        return len(chunks)

    return await asyncio.to_thread(_sync)


async def search(query: str, room_id: str, top_k: int = CHUNKS_PER_DOC) -> list[tuple[str, str]]:
    """Devuelve (filename, chunk) con los mejores fragmentos de CADA pdf relevante para la
    pregunta. Usa un único índice BM25 combinado (estadísticas correctas) pero agrupa los
    resultados por documento para que uno solo no eclipse a los demás."""
    idx = _index.get(room_id)
    docs = _docs.get(room_id, [])
    if not idx:
        return []

    def _sync() -> list[tuple[str, str]]:
        scores = idx["bm25"].get_scores(_tokenize(query))

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


def has_pdf(room_id: str) -> bool:
    """True si hay al menos un PDF indexado para esta sala en la sesión actual."""
    return bool(_docs.get(room_id))
