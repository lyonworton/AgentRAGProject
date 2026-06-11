import asyncio
import hashlib
from datetime import datetime, timezone
from app.adapters.vector_store.milvus import MilvusStore
from app.ingestion.sources.base import BaseSource
from app.ingestion.semantic_path.chunker import chunk_text
from app.ingestion.semantic_path.embedder import embed_chunks
from app.ingestion.semantic_path.milvus_writer import write_chunks_to_milvus
from app.domain.document import Document
from app.domain.ingest_job import IngestJob
from app.adapters.document_loader.pdf import PDFLoader
from app.adapters.document_loader.markdown import MarkdownLoader
from app.core.config import get_settings

LOADERS = {".pdf": PDFLoader, ".md": MarkdownLoader, ".txt": MarkdownLoader}


# === 三路路径函数 ===

async def run_semantic_path(doc, col_name: str, embedding_dim: int) -> int:
    """语义路径：分块 → Embedding → Milvus"""
    chunks = await chunk_text(doc.content, {"source": doc.source_path})
    if not chunks:
        raise ValueError("No chunks produced")
    embs = await embed_chunks(chunks)
    return await write_chunks_to_milvus(col_name, doc.id, chunks, embs)


async def run_graph_path(doc) -> None:
    """图谱路径：实体提取 → 关系提取 → Neo4j"""
    from app.ingestion.graph_path.entity_extractor import extract_candidate_entities
    from app.ingestion.graph_path.relation_extractor import extract_relations
    from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j
    from app.core.di import get_kg_store

    candidates = extract_candidate_entities(doc.content)
    if not candidates:
        return

    from app.core.llm_factory import get_llm
    llm = get_llm()
    result = await extract_relations(doc.content, candidates, llm)

    kg_store = await get_kg_store()
    await write_graph_to_neo4j(doc.id, result["entities"], result["relations"], kg_store)


async def run_keyword_path(doc, collection_id: str) -> None:
    """关键词路径：全文档 → ES"""
    from app.ingestion.keyword_path.es_writer import write_document_to_es
    from app.core.di import get_search_store

    search_store = await get_search_store()
    await write_document_to_es(
        doc.id, collection_id, doc.title, doc.content, doc.metadata_, search_store
    )


def _compute_path_status(results: list) -> dict:
    """将 asyncio.gather 的结果转为 path_status dict。

    results 顺序: [semantic_result, graph_result, keyword_result]
    """
    paths = ["milvus", "neo4j", "es"]
    return {
        path: "error" if isinstance(result, Exception) else "ok"
        for path, result in zip(paths, results)
    }


async def _handle_partial(doc_id: str, path_status: dict):
    """部分成功 → 入修复队列。"""
    from app.workers.repair import enqueue_repair

    FAILED_PATHS = ["neo4j", "es"]
    for path in FAILED_PATHS:
        if path_status.get(path) == "error":
            try:
                await enqueue_repair(doc_id, path, attempt=0)
            except Exception:
                pass


# === 主管道 ===

async def run_ingest_pipeline(
    job_id: str,
    collection_id: str,
    user_id: str,
    source: BaseSource,
    embedding_dim: int = -1,
    db_session_factory=None,
):
    """统一摄入管道：Source → Parse → PG写入 → 三路并行 Fork → 状态汇总。"""
    files = await source.list_files()
    store = MilvusStore()
    col_name = f"col_{collection_id}"
    if embedding_dim <= 0:
        embedding_dim = get_settings().embedding_dim
    await store.create_collection(col_name, embedding_dim)
    total = len(files)
    completed, failed = 0, 0
    errors_list = []
    doc_id = None

    async with db_session_factory() as db:
        job = await db.get(IngestJob, job_id)
        if job:
            job.total_docs = total
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

    for fp in files:
        doc_id = None
        try:
            ext = f".{fp.rsplit('.', 1)[-1].lower()}" if "." in fp else ".txt"
            if ext == ".txt":
                ext = ".md"
            loader_cls = LOADERS.get(ext, MarkdownLoader)
            parsed = await loader_cls().load(fp)

            async with db_session_factory() as db:
                doc = Document(
                    collection_id=collection_id,
                    title=parsed.title,
                    source_type="local",
                    source_path=fp,
                    mime_type=parsed.mime_type,
                    file_size=parsed.file_size,
                    content=parsed.content,
                    content_hash=hashlib.sha256(parsed.content.encode()).hexdigest(),
                    status="processing",
                )
                db.add(doc)
                await db.commit()
                doc_id = doc.id
                await db.refresh(doc)

            # 三路并行 Fork
            results = await asyncio.gather(
                run_semantic_path(doc, col_name, embedding_dim),
                run_graph_path(doc),
                run_keyword_path(doc, collection_id),
                return_exceptions=True,
            )

            path_status = _compute_path_status(results)

            if path_status["milvus"] == "ok":
                if all(v == "ok" for v in path_status.values()):
                    final_status = "ready"
                else:
                    final_status = "partial"
                    await _handle_partial(doc_id, path_status)
            else:
                final_status = "error"

            async with db_session_factory() as db:
                d = await db.get(Document, doc_id)
                if d:
                    d.status = final_status
                    d.path_status = path_status
                    if final_status != "error":
                        d.chunk_count = results[0] if isinstance(results[0], int) else 0
                        d.embedding_model = get_settings().bge_embedding_model
                        d.ingested_at = datetime.now(timezone.utc)
                    else:
                        d.error_message = str(results[0])
                    await db.commit()

            if final_status != "error":
                completed += 1
            else:
                failed += 1
                errors_list.append({"file": fp, "error": str(results[0]), "retryable": False})

        except Exception as e:
            failed += 1
            errors_list.append({"file": fp, "error": str(e), "retryable": True})
            async with db_session_factory() as db:
                if doc_id:
                    d = await db.get(Document, doc_id)
                    if d:
                        d.status = "error"
                        d.error_message = str(e)
                        await db.commit()

    async with db_session_factory() as db:
        job = await db.get(IngestJob, job_id)
        if job:
            job.completed_docs = completed
            job.failed_docs = failed
            job.errors = errors_list
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

    return {"completed": completed, "failed": failed}