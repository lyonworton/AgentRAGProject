import time
import structlog
from app.core.embedding_factory import get_embedder

logger = structlog.get_logger()

async def embed_chunks(chunks):
    t0 = time.monotonic()
    embedder = get_embedder()
    logger.info("embed_chunks_start", num_chunks=len(chunks), model_device=str(embedder._model.device) if embedder._model else "none")
    result = await embedder.aembed_documents([c["text"] for c in chunks])
    elapsed = time.monotonic() - t0
    logger.info("embed_chunks_done", num_chunks=len(chunks), elapsed_sec=round(elapsed, 2))
    return result
