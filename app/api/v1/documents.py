from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.di import get_db
from app.api.deps import get_current_user
from app.domain.user import User
from app.services import document_service, collection_service

router = APIRouter(prefix="/collections/{col_id}/documents", tags=["documents"])

class DocumentResponse(BaseModel):
    id: str; title: str; source_type: str; mime_type: str | None
    file_size: int | None; status: str; chunk_count: int; ingested_at: str | None
    model_config = {"from_attributes": True}

@router.get("", response_model=list[DocumentResponse])
async def list_documents(col_id: str, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    col = await collection_service.get_collection(db, col_id)
    if not col or col.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    return await document_service.list_documents(db, col_id)

@router.delete("/{doc_id}", status_code=204)
async def delete_document(col_id: str, doc_id: str, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    doc = await document_service.get_document(db, doc_id)
    if not doc or doc.collection_id != col_id:
        raise HTTPException(status_code=404, detail="Document not found")
    await document_service.delete_document(db, doc_id)
