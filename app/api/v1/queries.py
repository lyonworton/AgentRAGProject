import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.di import get_db
from app.api.deps import get_current_user
from app.domain.user import User
from app.services.rag_service import get_rag_service

router = APIRouter(prefix="/query", tags=["queries"])

class QueryOptions(BaseModel):
    max_iterations: int = 5
    quality_threshold: float = 0.7
    enable_web_search: bool = False
    response_style: str = "concise"

class QueryRequest(BaseModel):
    query: str
    collection_ids: list[str]
    session_id: str | None = None
    options: QueryOptions | None = None

class QueryResponse(BaseModel):
    answer: str
    citations: list[dict]
    agent_trace: dict
    uncertainty_flags: list[dict]
    trace_id: str

@router.post("", response_model=QueryResponse)
async def query_rag(req: QueryRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rag = get_rag_service()
    opts = req.options.model_dump() if req.options else {}
    result = await rag.query(db, user.id, req.query, req.collection_ids, req.session_id, opts)
    trace_id = uuid.uuid4().hex[:16]
    return QueryResponse(answer=result["answer"], citations=result["citations"],
        agent_trace=result["agent_trace"], uncertainty_flags=result["uncertainty_flags"], trace_id=trace_id)

@router.post("/stream")
async def query_stream(req: QueryRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    async def event_stream():
        import json
        rag = get_rag_service()
        opts = req.options.model_dump() if req.options else {}
        yield f"event: status\ndata: {json.dumps({'phase': 'analyzing', 'message': 'Understanding query...'})}\n\n"
        result = await rag.query(db, user.id, req.query, req.collection_ids, req.session_id, opts)
        trace_id = uuid.uuid4().hex[:16]
        chunks = result["answer"].split(" ")
        for i in range(0, len(chunks), 5):
            text = " ".join(chunks[i:i+5])
            yield f"event: chunk\ndata: {json.dumps({'text': text + ' ', 'citations': []})}\n\n"
        yield f"event: done\ndata: {json.dumps({'trace_id': trace_id, 'iterations': result['agent_trace']['iterations'], 'quality_score': result['agent_trace']['quality_score']})}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.get("/{trace_id}/trace")
async def get_trace(trace_id: str):
    return {"trace_id": trace_id, "note": "Trace persistence available in Phase 2"}
