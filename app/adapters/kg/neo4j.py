import re
import structlog
from neo4j import AsyncGraphDatabase
from app.adapters.kg.base import BaseKGStore
from app.core.config import get_settings

logger = structlog.get_logger()

# Whitelist for relationship type identifiers (Cypher cannot parameterize schema names)
_REL_TYPE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _validate_rel_type(rel_type: str) -> str:
    """Validate and normalize a relationship type. Raises ValueError on invalid input."""
    safe = rel_type.strip().upper()
    if not _REL_TYPE_RE.match(safe):
        raise ValueError(f"Invalid relationship type: {rel_type!r}. "
                         f"Must be alphanumeric+underscore, max 64 chars, start with letter.")
    return safe


class Neo4jKGStore(BaseKGStore):
    """Neo4j knowledge graph store implementation."""

    def __init__(self) -> None:
        settings = get_settings()
        self._uri = settings.neo4j_uri
        self._user = settings.neo4j_user
        self._password = settings.neo4j_password
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )

    async def aconnect(self) -> None:
        await self._driver.verify_connectivity()
        logger.info("neo4j connected", uri=self._uri)

    async def adisconnect(self) -> None:
        await self._driver.close()
        logger.info("neo4j disconnected")

    async def acreate_graph(
        self, doc_id: str, entities: list[dict], relations: list[dict]
    ) -> None:
        """Create Document, Entity, Chunk nodes and their relationships."""
        async with self._driver.session() as session:
            await session.run(
                "MERGE (d:Document {id: $doc_id})",
                doc_id=doc_id,
            )

            for ent in entities:
                await session.run(
                    """
                    MERGE (e:Entity {id: $id})
                    SET e.name = $name, e.type = $type, e.aliases = $aliases
                    """,
                    id=ent["id"],
                    name=ent.get("name", ""),
                    type=ent.get("type", ""),
                    aliases=ent.get("aliases", []),
                )
                # Link Document -> Entity provenance
                await session.run(
                    """
                    MATCH (d:Document {id: $doc_id}), (e:Entity {id: $entity_id})
                    MERGE (d)-[:CONTAINS]->(e)
                    """,
                    doc_id=doc_id,
                    entity_id=ent["id"],
                )

            for rel in relations:
                rel_type = _validate_rel_type(rel["type"])
                await session.run(
                    f"""
                    MATCH (a {{id: $from_id}}), (b {{id: $to_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    """,
                    from_id=rel["from_entity"],
                    to_id=rel["to_entity"],
                )

        logger.info("graph created", doc_id=doc_id, entities=len(entities), relations=len(relations))

    async def asearch_entities(self, query: str, top_k: int = 10) -> list[dict]:
        """Search entities by name using CONTAINS (Phase 1 simple match)."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $query
                RETURN e.id AS id, e.name AS name, e.type AS type
                LIMIT $top_k
                """,
                query=query,
                top_k=top_k,
            )
            records = await result.data()
            return [
                {"id": r["id"], "name": r["name"], "type": r["type"], "score": 1.0}
                for r in records
            ]

    async def aquery_relations(
        self, entity_id: str, relation_type: str | None = None
    ) -> list[dict]:
        """Query relations for an entity."""
        type_filter = f":{_validate_rel_type(relation_type)}" if relation_type else ""
        async with self._driver.session() as session:
            result = await session.run(
                f"""
                MATCH (a {{id: $entity_id}})-[r{type_filter}]-(b)
                RETURN a.id AS from_id, type(r) AS rel_type, b.id AS to_id,
                       labels(b) AS to_labels
                """,
                entity_id=entity_id,
            )
            records = await result.data()
            return [
                {
                    "from": r["from_id"],
                    "type": r["rel_type"],
                    "to": r["to_id"],
                }
                for r in records
            ]

    async def adelete_document(self, doc_id: str) -> None:
        """Remove document node and all its connected entities/relations."""
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (d:Document {id: $doc_id})
                OPTIONAL MATCH (d)-[r]-(n)
                DETACH DELETE d, n
                """,
                doc_id=doc_id,
            )
        logger.info("graph document deleted", doc_id=doc_id)