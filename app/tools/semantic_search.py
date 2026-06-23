import asyncio
from sqlalchemy import select
from app.tools.base import BaseTool
from app.core.embedding_factory import get_embedder
from app.adapters.vector_store.milvus import MilvusStore
from app.core.llm_factory import get_llm

QUERY_EXPAND_PROMPT = """Generate {n} alternative search queries for the given task description.
The variants should use different wording, synonyms, and perspectives to maximize recall.
Output JSON array of strings only.
"""


class SemanticSearchTool(BaseTool):
    name = "semantic_search"
    description = "Vector semantic search via Milvus (BGE-M3 dense embeddings) — best for fact lookup and concept matching"

    async def _expand_queries(self, query: str, n: int = 1) -> list[str]:
        try:
            llm = get_llm()
            result = await asyncio.wait_for(
                llm.agenerate_structured(
                    QUERY_EXPAND_PROMPT.format(n=n) + f"\nTask: {query}",
                    output_schema={"type": "array", "items": {"type": "string"}},
                ),
                timeout=8.0,
            )
            return result if isinstance(result, list) else [query]
        except (asyncio.TimeoutError, Exception):
            return [query]

    async def arun(
        self, query: str, collection_ids: list[str], top_k: int = 10
    ) -> list[dict]:
        if not collection_ids:
            return []
        embedder = get_embedder()
        store = MilvusStore()
        variants = await self._expand_queries(query)
        all_hits: list[dict] = []
        seen: set[str] = set()

        for variant in variants:
            try:
                qe = await asyncio.wait_for(
                    embedder.aembed_query(variant), timeout=30.0
                )
            except (asyncio.TimeoutError, Exception):
                qe = [0.0] * 1024  # fallback embedding

            for col_id in collection_ids:
                col_name = f"col_{col_id}"
                try:
                    hits = await asyncio.wait_for(
                        store.search(col_name, qe, top_k=top_k), timeout=10.0
                    )

                    # Collect unique parent_group_ids for enrichment
                    parent_ids: set[str] = set()
                    for hit in hits:
                        pg_id = getattr(hit, "parent_group_id", None) or hit.metadata.get("parent_group_id")
                        if pg_id:
                            parent_ids.add(pg_id)

                    # Lookup parent groups from document metadata
                    parent_lookup = {}
                    if parent_ids:
                        from app.core.di import get_db
                        from app.domain.document import Document
                        try:
                            # Collect all document_ids from hits
                            doc_ids = set()
                            for h in hits:
                                did = getattr(h, "document_id", None) or h.metadata.get("document_id")
                                if did:
                                    doc_ids.add(did)
                            async for db in get_db():
                                for doc_id in doc_ids:
                                    stmt = select(Document.metadata_).where(Document.id == doc_id)
                                    result = await db.execute(stmt)
                                    meta = result.scalar_one_or_none() or {}
                                    pg_data = meta.get("parent_groups", {})
                                    for pg_id, pg_info in pg_data.items():
                                        if pg_id in parent_ids:
                                            parent_lookup[pg_id] = {
                                                "text": pg_info.get("text", ""),
                                                "heading": pg_info.get("heading", ""),
                                            }
                        except Exception:
                            pass  # parent lookup is best-effort

                    for hit in hits:
                        if hit.chunk_id not in seen:
                            pg_id = getattr(hit, "parent_group_id", None) or hit.metadata.get("parent_group_id")
                            parent_info = parent_lookup.get(pg_id, {})
                            all_hits.append({
                                "chunk_id": hit.chunk_id,
                                "document_id": hit.document_id,
                                "text": hit.text,
                                "score": hit.score,
                                "source": "milvus",
                                "parent_group_id": pg_id or "",
                                "parent_text": parent_info.get("text", ""),
                                "parent_heading": parent_info.get("heading", ""),
                            })
                            seen.add(hit.chunk_id)
                except (asyncio.TimeoutError, Exception):
                    continue

        return all_hits