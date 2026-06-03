from abc import ABC, abstractmethod

class BaseKGStore(ABC):
    """Abstract base for knowledge graph stores (Neo4j)."""

    @abstractmethod
    async def aconnect(self) -> None:
        """Establish connection to the KG database."""

    @abstractmethod
    async def adisconnect(self) -> None:
        """Close connection to the KG database."""

    @abstractmethod
    async def acreate_graph(
        self, doc_id: str, entities: list[dict], relations: list[dict]
    ) -> None:
        """Create a subgraph for a document.

        Args:
            doc_id: The document identifier.
            entities: List of entity dicts with keys: id, name, type, aliases.
            relations: List of relation dicts with keys: from_entity, to_entity, type.
        """

    @abstractmethod
    async def asearch_entities(self, query: str, top_k: int = 10) -> list[dict]:
        """Search for entities matching the query string.

        Returns:
            List of entity dicts with keys: id, name, type, score.
        """

    @abstractmethod
    async def aquery_relations(
        self, entity_id: str, relation_type: str | None = None
    ) -> list[dict]:
        """Query relations for a given entity.

        Args:
            entity_id: The entity to query relations for.
            relation_type: Optional filter by relation type.

        Returns:
            List of relation dicts with keys: from, to, type.
        """

    @abstractmethod
    async def adelete_document(self, doc_id: str) -> None:
        """Remove all nodes and relations belonging to a document."""