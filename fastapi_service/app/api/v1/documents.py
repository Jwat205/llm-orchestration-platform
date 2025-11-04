# fastapi-service/app/api/v1/documents.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict
from app.document_processor.app.processors.pdf_processor import PDFProcessor

router = APIRouter()

class ProcessRequest(BaseModel):
    path: str

@router.post("/process")
def process_document(req: ProcessRequest) -> Dict[str, Any]:
    processor = PDFProcessor()
    try:
        return processor.process(req.path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
