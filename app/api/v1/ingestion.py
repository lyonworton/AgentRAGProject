import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.di import get_db
from app.core.config import get_settings
from app.api.deps import get_current_user
from app.domain.user import User
from app.domain.ingest_job import IngestJob
from app.services import collection_service
from app.workers.ingest import enqueue_ingest

router = APIRouter(prefix="/ingest", tags=["ingestion"])
settings = get_settings()

@router.post("/local")
async def ingest_local(collection_id: str = Form(...), files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    col = await collection_service.get_collection(db, collection_id)
    if not col or col.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    os.makedirs(settings.upload_dir, exist_ok=True)
    saved = []
    for f in files:
        if f.size and f.size > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File {f.filename} exceeds limit")
        dest = os.path.join(settings.upload_dir, f"{user.id}_{collection_id}_{f.filename}")
        content = await f.read()
        with open(dest, "wb") as out: out.write(content)
        saved.append(dest)
    job = IngestJob(collection_id=collection_id, user_id=user.id, source_type="local")
    db.add(job); await db.commit(); await db.refresh(job)
    arq_job_id = await enqueue_ingest(
        str(job.id), collection_id, user.id,
        source_type="local",
        source_config={"file_paths": saved},
    )
    return {"job_id": job.id, "arq_job_id": arq_job_id, "file_count": len(saved)}

class IngestJobListItem(BaseModel):
    id: str; collection_id: str; source_type: str; status: str
    total_docs: int; completed_docs: int; failed_docs: int
    errors: list; started_at: str | None; completed_at: str | None; created_at: str | None
    model_config = {"from_attributes": True}

@router.get("", response_model=list[IngestJobListItem])
async def list_ingest_jobs(
    collection_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(IngestJob).where(IngestJob.user_id == user.id)
    if collection_id:
        q = q.where(IngestJob.collection_id == collection_id)
    q = q.order_by(IngestJob.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()

class IngestJobResponse(BaseModel):
    id: str; status: str; total_docs: int; completed_docs: int
    failed_docs: int; errors: list; started_at: str | None; completed_at: str | None
    model_config = {"from_attributes": True}

@router.get("/{job_id}", response_model=IngestJobResponse)
async def get_ingest_status(job_id: str, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    job = await db.get(IngestJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
