from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.di import get_db
from app.api.deps import get_current_user
from app.domain.user import User
from app.services import collection_service

router = APIRouter(prefix="/collections", tags=["collections"])

class CreateCollectionRequest(BaseModel):
    name: str
    description: str | None = None

class CollectionResponse(BaseModel):
    id: str; name: str; description: str | None; config: dict | None
    doc_count: int; chunk_count: int; status: str
    model_config = {"from_attributes": True}

@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(req: CreateCollectionRequest, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    return await collection_service.create_collection(db, user.id, req.name, req.description)

@router.get("", response_model=list[CollectionResponse])
async def list_collections(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await collection_service.list_collections(db, user.id)

@router.get("/{col_id}", response_model=CollectionResponse)
async def get_collection(col_id: str, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    col = await collection_service.get_collection(db, col_id)
    if not col or col.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col

@router.delete("/{col_id}", status_code=204)
async def delete_collection(col_id: str, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    col = await collection_service.get_collection(db, col_id)
    if not col or col.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    await collection_service.delete_collection(db, col_id)
