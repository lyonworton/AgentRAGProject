from abc import ABC, abstractmethod

class BaseSearchStore(ABC):
    """Abstract base for full-text search stores (Elasticsearch)."""

    @abstractmethod
    async def aconnect(self) -> None:
        """Establish connection to the search engine."""

    @abstractmethod
    async def adisconnect(self) -> None:
        """Close connection to the search engine."""

    @abstractmethod
    async def acreate_index(self, collection_id: str) -> None:
        """Create a search index for a collection with IK analyzer settings."""

    @abstractmethod
    async def aindex_document(
        self, collection_id: str, doc_id: str, title: str,
        content: str, metadata: dict
    ) -> None:
        """Index a document into the search store."""

    @abstractmethod
    async def asearch(
        self, collection_id: str, query: str,
        fields: list[str] | None = None, top_k: int = 10,
        filters: dict | None = None
    ) -> list[dict]:
        """Full-text search in a collection.

        Returns:
            List of hit dicts with keys: document_id, title, text, score.
        """

    @abstractmethod
    async def adelete_document(
        self, collection_id: str, doc_id: str
    ) -> None:
        """Remove a document from the search index."""

    @abstractmethod
    async def adelete_index(self, collection_id: str) -> None:
        """Delete an entire search index."""