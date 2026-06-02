import hashlib
from datetime import datetime, timezone
from app.adapters.vector_store.milvus import MilvusStore
from app.ingestion.sources.local import LocalSource
from app.ingestion.semantic_path.chunker import chunk_text
from app.ingestion.semantic_path.embedder import embed_chunks
from app.ingestion.semantic_path.milvus_writer import write_chunks_to_milvus
from app.domain.document import Document
from app.domain.ingest_job import IngestJob
from app.adapters.document_loader.pdf import PDFLoader
from app.adapters.document_loader.markdown import MarkdownLoader

LOADERS = {".pdf": PDFLoader, ".md": MarkdownLoader, ".txt": MarkdownLoader}

async def run_ingest_pipeline(job_id, collection_id, user_id, file_paths, embedding_dim, db_session_factory):
    source = LocalSource(file_paths)
    files = await source.list_files()
    store = MilvusStore()
    col_name = f"col_{collection_id}"
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
        try:
            ext = f".{fp.rsplit('.', 1)[-1].lower()}" if "." in fp else ".txt"
            if ext == ".txt": ext = ".md"
            loader_cls = LOADERS.get(ext, MarkdownLoader)
            parsed = await loader_cls().load(fp)

            async with db_session_factory() as db:
                doc = Document(collection_id=collection_id, title=parsed.title,
                    source_type="local", source_path=fp, mime_type=parsed.mime_type,
                    file_size=parsed.file_size,
                    content_hash=hashlib.sha256(parsed.content.encode()).hexdigest(),
                    status="processing")
                db.add(doc); await db.commit(); await db.refresh(doc); doc_id = doc.id

            chunks = await chunk_text(parsed.content, {"source": fp})
            if not chunks: raise ValueError("No chunks")
            embs = await embed_chunks(chunks)
            cnt = await write_chunks_to_milvus(col_name, doc_id, chunks, embs)

            async with db_session_factory() as db:
                d = await db.get(Document, doc_id)
                if d:
                    d.status = "ready"; d.chunk_count = cnt
                    d.embedding_model = "text-embedding-3-small"
                    d.path_status = {"milvus": "ok"}
                    d.ingested_at = datetime.now(timezone.utc)
                    await db.commit()
            completed += 1
        except Exception as e:
            failed += 1
            errors_list.append({"file": fp, "error": str(e), "retryable": True})
            async with db_session_factory() as db:
                if doc_id:
                    d = await db.get(Document, doc_id)
                    if d: d.status = "error"; d.error_message = str(e); await db.commit()

    async with db_session_factory() as db:
        job = await db.get(IngestJob, job_id)
        if job:
            job.completed_docs = completed; job.failed_docs = failed
            job.errors = errors_list; job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
    return {"completed": completed, "failed": failed}
