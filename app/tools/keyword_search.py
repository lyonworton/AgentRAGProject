from app.tools.base import BaseTool
from app.adapters.search.elasticsearch import ElasticsearchStore

TRUNCATE_LIMIT = 500


class KeywordSearchTool(BaseTool):
    name = "keyword_search"
    description = "Full-text keyword search via Elasticsearch with IK tokenizer — best for exact match and term queries"

    async def arun(
        self, query: str, collection_ids: list[str], top_k: int = 10
    ) -> list[dict]:
        if not collection_ids:
            return []

        es = ElasticsearchStore()
        results: list[dict] = []

        for col_id in collection_ids:
            try:
                hits = await es.asearch(col_id, query, top_k=top_k)
                for h in hits:
                    text = h["text"]
                    if len(text) > TRUNCATE_LIMIT:
                        text = text[:TRUNCATE_LIMIT] + "..."
                    results.append({
                        "chunk_id": h["document_id"],
                        "document_id": h["document_id"],
                        "text": text,
                        "score": h["score"],
                        "source": "keyword",
                    })
            except Exception:
                continue

        return results