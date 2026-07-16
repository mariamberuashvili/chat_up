"""RAG: extrae texto de PDFs, genera embeddings y los indexa para búsqueda semántica.

Los PDFs (texto + embeddings) se guardan en MySQL (tabla pdf_docs) para que sobrevivan a un
reinicio del proceso: Render (plan free) reinicia el backend por inactividad o en cada
deploy, y si solo vivieran en memoria se perdían silenciosamente.

El índice vectorial en sí (matriz numpy por sala) vive en memoria y se reconstruye desde
MySQL la primera vez que la sala se usa en este proceso: es el mismo patrón que ya usaba
el índice BM25 anterior, solo que ahora la búsqueda es semántica (embeddings + similitud
coseno) en lugar de léxica.
"""

import asyncio
import json
import re
import uuid

import numpy as np
import pymupdf
from fastembed import TextEmbedding

from db import query

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MAX_PDFS_PER_ROOM = 3
CHUNKS_PER_DOC = 3  # cuántos fragmentos como máximo se toman de CADA pdf en una búsqueda

# Modelo multilingüe (soporta español) y liviano: corre en CPU vía ONNX, sin API key ni
# GPU. Se carga una sola vez, de forma perezosa (recién al primer PDF/búsqueda) para no
# alargar el arranque del backend cuando el chat no usa RAG.
EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Similitud coseno mínima para considerar un chunk relevante a la pregunta. Por debajo de
# esto se asume que el mensaje no tiene que ver con los PDFs y se deja que el bot responda
# como chat normal (ver chat_ws.py). Es un valor empírico: si el bot "alucina" contexto de
# preguntas no relacionadas, subirlo; si ignora preguntas que sí debería responder, bajarlo.
MIN_SIMILARITY = 0.45

_embedder: TextEmbedding | None = None

# room_id -> lista de PDFs cargados en memoria: [{"id", "filename", "chunks", "embeddings"}, ...]
# Es una cache del contenido de MySQL para no recalcular embeddings en cada mensaje.
_docs: dict[str, list[dict]] = {}
_loaded_rooms: set[str] = set()  # qué salas ya se hidrataron desde la DB en este proceso

# room_id -> índice vectorial combinado de TODOS los pdfs de la sala + a qué doc pertenece cada chunk.
_index: dict[str, dict] = {}


def _get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=EMBED_MODEL_NAME)
    return _embedder


def _embed(texts: list[str]) -> list[list[float]]:
    return [vec.tolist() for vec in _get_embedder().embed(texts)]


def _embed_one(text: str) -> list[float]:
    return _embed([text])[0]


def _extract_text(pdf_bytes: bytes) -> str:
    # PyMuPDF es una libreria en C (mucho mas rapida que pypdf, que es Python puro).
    # Con PDFs grandes pypdf podia tardar tanto que Render cortaba la conexion (timeout).
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    # Normaliza saltos de línea/espacios sueltos que deja la extracción de PDF antes de
    # partir por oraciones, si no cada salto de línea del PDF cuenta como límite de "frase".
    flat = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in _SENTENCE_SPLIT.split(flat) if s.strip()]


def _chunk(text: str) -> list[str]:
    """Chunking inteligente: agrupa oraciones completas hasta CHUNK_SIZE caracteres en vez
    de cortar a lo bruto por posición, para no partir frases (y por lo tanto ideas) a la
    mitad. Mantiene overlap entre chunks consecutivos arrastrando las últimas oraciones del
    chunk anterior, para no perder contexto en el límite entre fragmentos."""
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> list[str]:
        """Cierra el chunk actual y devuelve las oraciones de overlap para el siguiente."""
        chunks.append(" ".join(current))
        overlap: list[str] = []
        overlap_len = 0
        for s in reversed(current):
            if overlap_len + len(s) > CHUNK_OVERLAP:
                break
            overlap.insert(0, s)
            overlap_len += len(s) + 1
        return overlap

    for sentence in sentences:
        # Frase gigante sin puntuación intermedia (típico de tablas mal extraídas): se
        # corta a lo bruto para que no genere un chunk desmedido.
        if len(sentence) > CHUNK_SIZE:
            if current:
                current = flush()
                current_len = sum(len(s) + 1 for s in current)
            for start in range(0, len(sentence), CHUNK_SIZE - CHUNK_OVERLAP):
                piece = sentence[start : start + CHUNK_SIZE].strip()
                if piece:
                    chunks.append(piece)
            continue

        if current and current_len + len(sentence) + 1 > CHUNK_SIZE:
            current = flush()
            current_len = sum(len(s) + 1 for s in current)

        current.append(sentence)
        current_len += len(sentence) + 1

    if current:
        chunks.append(" ".join(current))

    return chunks


def _load_from_db(room_id: str) -> None:
    """Trae los PDFs de la sala desde MySQL si este proceso todavía no los tiene en memoria."""
    if room_id in _loaded_rooms:
        return
    rows = query(
        "SELECT id, filename, chunks, embeddings FROM pdf_docs WHERE room_id = %(room_id)s ORDER BY created_at",
        {"room_id": room_id},
        fetch=True,
    )
    docs = []
    for r in rows:
        chunks = json.loads(r["chunks"])
        if r["embeddings"]:
            embeddings = json.loads(r["embeddings"])
        else:
            # PDFs subidos antes de tener embeddings (o migración vieja): se calculan una
            # vez y se guardan, así no hay que correr una migración de datos aparte.
            embeddings = _embed(chunks)
            query(
                "UPDATE pdf_docs SET embeddings = %(embeddings)s WHERE id = %(id)s",
                {"embeddings": json.dumps(embeddings), "id": r["id"]},
            )
        docs.append({"id": r["id"], "filename": r["filename"], "chunks": chunks, "embeddings": embeddings})
    _docs[room_id] = docs
    _loaded_rooms.add(room_id)
    _rebuild_index(room_id)


def _rebuild_index(room_id: str) -> None:
    docs = _docs.get(room_id, [])
    chunks: list[str] = []
    owner: list[int] = []  # owner[i] = índice del doc dueño de chunks[i]
    vectors: list[list[float]] = []
    for doc_idx, doc in enumerate(docs):
        for c, v in zip(doc["chunks"], doc["embeddings"]):
            chunks.append(c)
            owner.append(doc_idx)
            vectors.append(v)

    if not chunks:
        _index.pop(room_id, None)
        return

    matrix = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1  # evita división por cero si algún vector quedara en cero
    _index[room_id] = {
        "matrix": matrix / norms,  # normalizado: producto punto == similitud coseno
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
    """Extrae texto, lo divide en chunks, genera sus embeddings, lo guarda en MySQL y
    reconstruye el índice vectorial de la sala."""

    def _sync() -> int:
        _load_from_db(room_id)
        text = _extract_text(pdf_bytes)
        chunks = _chunk(text)
        if not chunks:
            return 0
        embeddings = _embed(chunks)
        doc_id = uuid.uuid4().hex
        query(
            """INSERT INTO pdf_docs (id, room_id, filename, chunks, embeddings)
               VALUES (%(id)s, %(room_id)s, %(filename)s, %(chunks)s, %(embeddings)s)""",
            {
                "id": doc_id,
                "room_id": room_id,
                "filename": filename,
                "chunks": json.dumps(chunks),
                "embeddings": json.dumps(embeddings),
            },
        )
        _docs.setdefault(room_id, []).append(
            {"id": doc_id, "filename": filename, "chunks": chunks, "embeddings": embeddings}
        )
        _rebuild_index(room_id)
        return len(chunks)

    return await asyncio.to_thread(_sync)


async def search(query_text: str, room_id: str, top_k: int = CHUNKS_PER_DOC) -> list[tuple[str, str]]:
    """Búsqueda semántica (Top-K): embebe la pregunta y devuelve (filename, chunk) de los
    fragmentos con mayor similitud coseno, agrupados por documento para que uno solo no
    eclipse a los demás cuando hay varios PDFs relevantes."""

    def _sync() -> list[tuple[str, str]]:
        _load_from_db(room_id)
        idx = _index.get(room_id)
        docs = _docs.get(room_id, [])
        if not idx:
            return []

        query_vec = np.array(_embed_one(query_text), dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm

        scores = idx["matrix"] @ query_vec  # similitud coseno de la pregunta contra cada chunk

        by_doc: dict[int, list[tuple[float, int]]] = {}
        for i, (score, doc_idx) in enumerate(zip(scores, idx["owner"])):
            by_doc.setdefault(doc_idx, []).append((float(score), i))

        results: list[tuple[str, str]] = []
        for doc_idx in sorted(by_doc):
            entries = sorted(by_doc[doc_idx], key=lambda t: t[0], reverse=True)
            filename = docs[doc_idx]["filename"]
            for score, i in entries[:top_k]:
                if score >= MIN_SIMILARITY:
                    results.append((filename, idx["chunks"][i]))
        return results

    return await asyncio.to_thread(_sync)


async def has_pdf(room_id: str) -> bool:
    """True si hay al menos un PDF indexado para esta sala."""

    def _sync() -> bool:
        _load_from_db(room_id)
        return bool(_docs.get(room_id))

    return await asyncio.to_thread(_sync)
