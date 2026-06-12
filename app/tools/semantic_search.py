import asyncio
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

    async def _expand_queries(self, query: str, n: int = 3) -> list[str]:
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
            qe = await embedder.aembed_query(variant)
            for col_id in collection_ids:
                col_name = f"col_{col_id}"
                try:
                    hits = await store.search(col_name, qe, top_k=top_k)
                    for hit in hits:
                        if hit.chunk_id not in seen:
                            all_hits.append({
                                "chunk_id": hit.chunk_id,
                                "document_id": hit.document_id,
                                "text": hit.text,
                                "score": hit.score,
                                "source": "milvus",
                            })
                            seen.add(hit.chunk_id)
                except Exception:
                    continue

        return all_hits