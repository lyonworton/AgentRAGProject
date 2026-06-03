from urllib.parse import quote
from app.tools.base import BaseTool
from app.adapters.kg.neo4j import Neo4jKGStore


class KGSearchTool(BaseTool):
    name = "kg_search"
    description = "Knowledge graph search via Neo4j — best for entity relationships and multi-hop queries"

    async def arun(
        self, query: str, collection_ids: list[str], top_k: int = 10
    ) -> list[dict]:
        kg = Neo4jKGStore()
        entities = await kg.asearch_entities(query, top_k=top_k)
        if not entities:
            return []

        results: list[dict] = []
        for ent in entities:
            safe_id = quote(ent["id"], safe="")
            results.append({
                "chunk_id": f"kg-entity-{safe_id}",
                "text": f"Entity: {ent['name']} ({ent['type']})",
                "score": 0.5,
                "source": "kg",
            })

        # Expand relations for top 5 entities
        for ent in entities[:5]:
            try:
                relations = await kg.aquery_relations(ent["id"])
                for rel in relations:
                    results.append({
                        "chunk_id": f"kg-rel-{quote(rel['from'], safe='')}-{quote(rel['to'], safe='')}",
                        "text": f"{rel['from']} → {rel['type']} → {rel['to']}",
                        "score": 0.5,
                        "source": "kg",
                    })
            except Exception:
                continue

        return results