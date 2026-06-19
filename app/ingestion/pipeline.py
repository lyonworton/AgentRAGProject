import asyncio
import hashlib
from datetime import datetime, timezone
from app.adapters.vector_store.milvus import MilvusStore
from app.ingestion.sources.base import BaseSource
from app.ingestion.semantic_path.chunker import chunk_text
from app.ingestion.semantic_path.embedder import embed_chunks
from app.domain.document import Document
from app.domain.collection import Collection
from app.domain.ingest_job import IngestJob
from app.adapters.document_loader.pdf import PDFLoader
from app.adapters.document_loader.markdown import MarkdownLoader
from app.core.config import get_settings

LOADERS = {".pdf": PDFLoader, ".md": MarkdownLoader, ".txt": MarkdownLoader}


# === 三路路径函数 ===

async def run_semantic_path(doc, col_name: str, embedding_dim: int) -> dict:
    """Semantic path: chunk -> embed -> Milvus.

    Returns a dict with chunks, embeddings, and doc_id for batch flushing.
    The caller is responsible for batch flushing.
    """
    chunks = await chunk_text(doc.content, {"source": doc.source_path})
    if not chunks:
        raise ValueError("No chunks produced")
    embs = await embed_chunks(chunks)
    return {
        "doc_id": doc.id,
        "chunks": chunks,
        "embeddings": embs,
        "count": len(chunks),
    }


async def run_graph_path(doc) -> None:
    """图谱路径：实体提取 → 关系提取 → Neo4j"""
    from app.ingestion.graph_path.entity_extractor import extract_candidate_entities
    from app.ingestion.graph_path.relation_extractor import extract_relations
    from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j
    from app.core.di import get_kg_store
    import structlog

    logger = structlog.get_logger()

    candidates = extract_candidate_entities(doc.content)
    if not candidates:
        return

    try:
        from app.core.llm_factory import get_llm
        llm = get_llm()
        result = await asyncio.wait_for(
            extract_relations(doc.content, candidates, llm),
            timeout=60.0,
        )

        kg_store = await get_kg_store()
        await write_graph_to_neo4j(doc.id, result["entities"], result["relations"], kg_store)
        logger.info("graph_path_complete", doc_id=doc.id, entities=len(result["entities"]))
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning("graph_path_failed", doc_id=doc.id, error=str(e))
        raise


async def run_keyword_path(doc, collection_id: str) -> None:
    """关键词路径：全文档 → ES"""
    from app.ingestion.keyword_path.es_writer import write_document_to_es
    from app.core.di import get_search_store
    import structlog

    logger = structlog.get_logger()
    try:
        search_store = await get_search_store()
        await asyncio.wait_for(
            write_document_to_es(
                doc.id, collection_id, doc.title, doc.content, doc.metadata_, search_store
            ),
            timeout=30.0,
        )
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning("keyword_path_failed", doc_id=doc.id, error=str(e))
        raise


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




# === Batch flush helper ===

async def batch_flush_milvus(col_name: str, batch_data: list[dict]) -> int:
    """Flush accumulated chunks from multiple docs to Milvus in batches of 1000."""
    import uuid
    import structlog

    logger = structlog.get_logger()
    store = MilvusStore()
    BATCH_SIZE = 1000

    all_records = []
    all_embeddings = []

    for item in batch_data:
        doc_id = item['doc_id']
        chunks = item['chunks']
        embs = item['embeddings']
        for i, c in enumerate(chunks):
            all_records.append({
                'chunk_id': uuid.uuid4().hex[:12],
                'document_id': doc_id,
                'text': c['text'],
                'metadata': c.get('metadata', {}),
                'chunk_index': i,
                'parent_chunk_id': '',
            })
            all_embeddings.append(embs[i])

    for start in range(0, len(all_records), BATCH_SIZE):
        batch_records = all_records[start:start + BATCH_SIZE]
        batch_embs = all_embeddings[start:start + BATCH_SIZE]
        await store.insert(col_name, batch_records, batch_embs, flush=True)

    logger.info('batch_flush_complete', total=len(all_records))
    return len(all_records)

# === 主管道 ===

async def run_ingest_pipeline(
    job_id: str,
    collection_id: str,
    user_id: str,
    source: BaseSource,
    embedding_dim: int = -1,
    db_session_factory=None,
    commit_every: int = 5,
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
    semantic_batch_data: list[dict] = []
    docs_since_commit = 0

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
            semantic_results = await asyncio.gather(
                run_semantic_path(doc, col_name, embedding_dim),
                run_graph_path(doc),
                run_keyword_path(doc, collection_id),
                return_exceptions=True,
            )

            path_status = _compute_path_status(semantic_results)

            if path_status["milvus"] == "ok":
                if all(v == "ok" for v in path_status.values()):
                    final_status = "ready"
                else:
                    final_status = "partial"
                    await _handle_partial(doc_id, path_status)
            else:
                final_status = "error"

            # Determine chunk_count from semantic_results[0] (which is a dict)
            chunk_count = 0
            if not isinstance(semantic_results[0], Exception) and "count" in semantic_results[0]:
                chunk_count = semantic_results[0].get("count", 0)

            docs_since_commit += 1
            is_last_doc = (completed + failed + 1) >= total
            should_commit = (docs_since_commit >= commit_every) or is_last_doc or final_status == "error"

            async with db_session_factory() as db:
                d = await db.get(Document, doc_id)
                if d:
                    d.status = final_status
                    d.path_status = path_status
                    if final_status != "error":
                        d.chunk_count = chunk_count
                        d.embedding_model = get_settings().bge_embedding_model
                        d.ingested_at = datetime.now(timezone.utc)
                        # Update collection stats
                        col = await db.get(Collection, collection_id)
                        if col:
                            col.doc_count = (col.doc_count or 0) + 1
                            col.chunk_count = (col.chunk_count or 0) + chunk_count
                    if should_commit:
                        await db.commit()
                    elif final_status == "error":
                        # Always commit errors for visibility
                        await db.commit()

            # Accumulate semantic data for batch flush
            if not isinstance(semantic_results[0], Exception):
                semantic_batch_data.append(semantic_results[0])

            if final_status != "error":
                completed += 1
            else:
                failed += 1
                errors_list.append({"file": fp, "error": str(semantic_results[0]), "retryable": False})

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

    # === Batch flush remaining semantic data to Milvus ===
    if semantic_batch_data:
        try:
            flushed = await batch_flush_milvus(col_name, semantic_batch_data)
            logger.info("milvus_batch_flushed", total=flushed)
        except Exception as e:
            import structlog
            logger = structlog.get_logger()
            logger.error("batch_flush_milvus_failed", error=str(e))

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