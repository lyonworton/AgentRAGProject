import structlog
from elasticsearch import AsyncElasticsearch
from app.adapters.search.base import BaseSearchStore
from app.core.config import get_settings

logger = structlog.get_logger()

_INDEX_SETTINGS = {
    "settings": {
        "analysis": {
            "analyzer": {
                "ik_max_word_analyzer": {"type": "custom", "tokenizer": "ik_max_word"},
                "ik_smart_analyzer": {"type": "custom", "tokenizer": "ik_smart"},
            }
        }
    },
    "mappings": {
        "properties": {
            "document_id": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "ik_max_word_analyzer",
                "search_analyzer": "ik_smart_analyzer",
            },
            "content": {
                "type": "text",
                "analyzer": "ik_max_word_analyzer",
                "search_analyzer": "ik_smart_analyzer",
            },
            "section_path": {"type": "keyword"},
            "page_number": {"type": "integer"},
            "source_type": {"type": "keyword"},
            "ingested_at": {"type": "date"},
        }
    },
}


class ElasticsearchStore(BaseSearchStore):
    """Elasticsearch full-text search store with IK Chinese tokenizer."""

    def __init__(self) -> None:
        settings = get_settings()
        self._host = settings.es_host
        self._client = AsyncElasticsearch(hosts=[self._host])

    async def aconnect(self) -> None:
        info = await self._client.info()
        logger.info("elasticsearch connected", version=info["version"]["number"])

    async def adisconnect(self) -> None:
        await self._client.close()
        logger.info("elasticsearch disconnected")

    def _index_name(self, collection_id: str) -> str:
        return f"col_{collection_id}"

    async def acreate_index(self, collection_id: str) -> None:
        index_name = self._index_name(collection_id)
        exists = await self._client.indices.exists(index=index_name)
        if not exists:
            await self._client.indices.create(index=index_name, body=_INDEX_SETTINGS)
            logger.info("es index created", index=index_name)

    async def aindex_document(
        self, collection_id: str, doc_id: str, title: str,
        content: str, metadata: dict
    ) -> None:
        await self.acreate_index(collection_id)
        index_name = self._index_name(collection_id)
        body = {
            "document_id": doc_id,
            "title": title,
            "content": content,
            "section_path": metadata.get("section_path", ""),
            "page_number": metadata.get("page_number"),
            "source_type": metadata.get("source_type", ""),
            "ingested_at": metadata.get("ingested_at"),
        }
        await self._client.index(index=index_name, id=doc_id, body=body)

    async def asearch(
        self, collection_id: str, query: str,
        fields: list[str] | None = None, top_k: int = 10,
        filters: dict | None = None
    ) -> list[dict]:
        search_fields = fields or ["title^2", "content"]
        index_name = self._index_name(collection_id)

        body = {
            "query": {
                "bool": {
                    "must": [
                        {"multi_match": {"query": query, "fields": search_fields}}
                    ]
                }
            },
            "size": top_k,
        }

        if filters:
            filter_clauses = []
            for key, value in filters.items():
                filter_clauses.append({"term": {key: value}})
            body["query"]["bool"]["filter"] = filter_clauses

        result = await self._client.search(index=index_name, body=body)
        hits = result["hits"]["hits"]
        return [
            {
                "document_id": h["_source"]["document_id"],
                "title": h["_source"]["title"],
                "text": h["_source"]["content"],
                "score": h["_score"],
            }
            for h in hits
        ]

    async def adelete_document(
        self, collection_id: str, doc_id: str
    ) -> None:
        index_name = self._index_name(collection_id)
        try:
            await self._client.delete(index=index_name, id=doc_id)
        except Exception:
            pass  # Document may not exist

    async def adelete_index(self, collection_id: str) -> None:
        index_name = self._index_name(collection_id)
        await self._client.indices.delete(index=index_name, ignore=[404])