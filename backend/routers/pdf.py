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

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    try:
        chunks = await rag_service.process_pdf(pdf_bytes, room_id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {type(e).__name__}: {e}")

    if chunks == 0:
        raise HTTPException(status_code=422, detail="No se pudo extraer texto del PDF.")

    return {"ok": True, "chunks": chunks, "filename": file.filename}
