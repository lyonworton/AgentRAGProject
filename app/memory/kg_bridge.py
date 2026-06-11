import structlog
from app.adapters.kg.neo4j import Neo4jKGStore

logger = structlog.get_logger()

ENTITY_EXTRACT_PROMPT = """Extract named entities from this Q&A exchange. Return only a JSON array.
Each entity has "name" (string) and "type" (one of: person, organization, concept, technical_term, product).
Limit to 5 most important entities. If none, return empty array [].

Q: {query}
A: {answer}

Output ONLY: [{{"name": "entity name", "type": "concept"}}, ...]"""


async def extract_entities(query: str, answer: str) -> list[dict]:
    """Use LLM to extract named entities from Q&A."""
    if not answer:
        return []
    try:
        from app.core.llm_factory import get_llm
        llm = get_llm()
        result = await llm.agenerate_structured(
            ENTITY_EXTRACT_PROMPT.format(query=query[:300], answer=answer),
            "You are an entity extraction specialist.",
            output_schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": ["person", "organization", "concept", "technical_term", "product"]},
                    },
                    "required": ["name", "type"],
                },
            },
        )
        return result if isinstance(result, list) else []
    except Exception:
        logger.debug("entity_extraction_failed", exc_info=True)
        return []


async def save_session_entities(session_id: str, entities: list[dict]) -> None:
    """Save extracted entities to Neo4j as UserMemory nodes linked to session."""
    if not session_id or not entities:
        return
    try:
        kg = Neo4jKGStore()
        await kg.aconnect()
        async with kg._driver.session() as sess:
            for ent in entities[:5]:
                await sess.run(
                    """
                    MERGE (s:Session {id: $session_id})
                    MERGE (e:UserMemory {name: $name, type: $type})
                    MERGE (s)-[:HAS_MEMORY]->(e)
                    SET e.session_id = $session_id
                    """,
                    session_id=session_id,
                    name=ent["name"],
                    type=ent["type"],
                )
    except Exception:
        logger.warning("kg_entity_save_failed", session_id=session_id, exc_info=True)


async def load_session_entities(session_id: str) -> list[dict]:
    """Load UserMemory entities linked to a session from Neo4j."""
    if not session_id:
        return []
    try:
        kg = Neo4jKGStore()
        await kg.aconnect()
        async with kg._driver.session() as sess:
            result = await sess.run(
                """
                MATCH (s:Session {id: $session_id})-[:HAS_MEMORY]->(e:UserMemory)
                RETURN e.name AS name, e.type AS type
                LIMIT 20
                """,
                session_id=session_id,
            )
            records = await result.data()
            return [{"name": r["name"], "type": r["type"]} for r in records]
    except Exception:
        logger.debug("kg_entity_load_failed", session_id=session_id, exc_info=True)
        return []