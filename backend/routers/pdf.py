"""Endpoint para subir y procesar PDFs en el chat privado con IA."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from services import rag as rag_service

router = APIRouter(prefix="/rooms", tags=["pdf"])


@router.post("/{room_id}/pdf")
async def upload_pdf(room_id: str, file: UploadFile = File(...)):
    if not room_id.startswith("ai__"):
        raise HTTPException(status_code=400, detail="Solo disponible en chats de IA.")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")

    if rag_service.count_pdfs(room_id) >= rag_service.MAX_PDFS_PER_ROOM:
        raise HTTPException(
            status_code=400,
            detail=f"Ya subiste el máximo de {rag_service.MAX_PDFS_PER_ROOM} PDFs en este chat.",
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    try:
        chunks = await rag_service.process_pdf(pdf_bytes, room_id, file.filename or "documento.pdf")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {type(e).__name__}: {e}")

    if chunks == 0:
        raise HTTPException(status_code=422, detail="No se pudo extraer texto del PDF.")

    return {
        "ok": True,
        "chunks": chunks,
        "filename": file.filename,
        "totalPdfs": rag_service.count_pdfs(room_id),
        "maxPdfs": rag_service.MAX_PDFS_PER_ROOM,
    }


@router.get("/{room_id}/pdf")
async def get_pdfs(room_id: str):
    return {"pdfs": rag_service.list_pdfs(room_id), "maxPdfs": rag_service.MAX_PDFS_PER_ROOM}


@router.delete("/{room_id}/pdf/{doc_id}")
async def delete_pdf(room_id: str, doc_id: str):
    if not rag_service.remove_pdf(room_id, doc_id):
        raise HTTPException(status_code=404, detail="PDF no encontrado.")
    return {"ok": True, "pdfs": rag_service.list_pdfs(room_id)}
