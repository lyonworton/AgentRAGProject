import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.di import get_db
from app.api.deps import get_current_user
from app.domain.user import User
from app.services.rag_service import get_rag_service
from app.services import session_service

router = APIRouter(prefix="/query", tags=["queries"])

class QueryOptions(BaseModel):
    max_iterations: int = 2
    quality_threshold: float = 0.7
    enable_web_search: bool = False
    response_style: str = "concise"
    timeout: int = 180

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
    import asyncio, json
    from app.services.agent_service import AgentService

    opts = req.options.model_dump() if req.options else {}
    svc = AgentService()
    trace_id = uuid.uuid4().hex[:16]
    timeout = opts.get("timeout", 180)

    final_answer = ""
    last_citations: list = []
    all_thoughts: list = []

    async def event_generator():
        nonlocal final_answer, last_citations, all_thoughts

        try:
            async with asyncio.timeout(timeout):
                async for msg in svc.run_stream(
                    req.query, req.collection_ids, req.session_id, opts):
                    if msg["event"] == "thought":
                        all_thoughts.append(msg["data"])
                    if msg["event"] == "done":
                        msg["data"]["trace_id"] = trace_id
                        final_answer = msg["data"].get("answer", "")
                        last_citations = msg["data"].get("citations", [])
                    yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
        except asyncio.TimeoutError:
            timeout_body = json.dumps({"message": "Request timed out", "trace_id": trace_id})
            yield f"event: timeout\ndata: {timeout_body}\n\n"

        # Persist messages immediately after stream finishes
        try:
            if req.session_id and final_answer:
                citations_out = []
                try:
                    citations_out = [
                        {"chunk_id": c["chunk_id"], "document_title": c.get("document_title", ""),
                         "text": c.get("text", ""), "relevance": c.get("relevance", 0)}
                        for c in last_citations[:20]
                    ]
                except Exception:
                    pass
                await session_service.add_message(db, req.session_id, role="user", content=req.query)
                await session_service.add_message(
                    db, req.session_id, role="assistant",
                    content=final_answer, trace_id=trace_id,
                    citations=citations_out, thoughts=all_thoughts,
                )
                await db.commit()
        except Exception:
            pass  # don't break SSE on persist failure

    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
    )

@router.get("/{trace_id}/trace")
async def get_trace(trace_id: str, db=Depends(get_db),
                    user: User = Depends(get_current_user)):
    from sqlalchemy import select
    from app.domain.query_trace import QueryTrace
    result = await db.execute(
        select(QueryTrace).where(
            QueryTrace.id == trace_id,
            QueryTrace.user_id == user.id,
        )
    )
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {
        "trace_id": trace.id,
        "session_id": trace.session_id,
        "query": trace.query,
        "answer": trace.answer,
        "model_used": trace.model_used,
        "total_tokens": trace.total_tokens,
        "estimated_cost": trace.estimated_cost,
        "citations": trace.citations,
        "agent_graph": trace.agent_graph,
        "quality_score": trace.quality_score,
        "iterations": trace.iterations,
        "latency_ms": trace.latency_ms,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
    }
