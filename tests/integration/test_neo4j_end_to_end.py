"""Integration tests: Neo4j KG store — connect, write, search, delete."""

import pytest


@pytest.mark.integration
class TestNeo4jEndToEnd:
    async def test_health_check(self, neo4j_store):
        """Can connect and health check passes."""
        await neo4j_store.aconnect()
        try:
            await neo4j_store.ahealth_check()
        finally:
            await neo4j_store.adisconnect()

    async def test_create_graph_and_search_entities(self, neo4j_store):
        """Write entities+relations, then search returns them."""
        doc_id = "integration-test-doc-1"
        entities = [
            {"id": "e1", "name": "Alice", "type": "person"},
            {"id": "e2", "name": "Bob", "type": "person"},
        ]
        relations = [
            {"from_entity": "e1", "to_entity": "e2", "type": "KNOWS"},
        ]

        await neo4j_store.aconnect()
        try:
            await neo4j_store.acreate_graph(doc_id, entities, relations)

            results = await neo4j_store.asearch_entities("Alice", top_k=5)
            assert len(results) > 0
            names = [r["name"] for r in results]
            assert "Alice" in names

            relations_found = await neo4j_store.aquery_relations("e1")
            assert any(r["type"] == "KNOWS" for r in relations_found)
        finally:
            await neo4j_store.adelete_document(doc_id)
            await neo4j_store.adisconnect()

    async def test_search_returns_empty_for_missing(self, neo4j_store):
        """Search for nonexistent entity returns no results."""
        await neo4j_store.aconnect()
        try:
            results = await neo4j_store.asearch_entities("zzz_nonexistent_xyzzy", top_k=5)
            assert results == [] or all(r["name"] != "zzz_nonexistent_xyzzy" for r in results)
        finally:
            await neo4j_store.adisconnect()

    async def test_delete_document_cleans_up(self, neo4j_store):
        """After deleting a document, its entities are removed."""
        doc_id = "integration-test-doc-2"
        entities = [{"id": "e_del", "name": "DeleteMe", "type": "concept"}]

        await neo4j_store.aconnect()
        try:
            await neo4j_store.acreate_graph(doc_id, entities, [])
            await neo4j_store.adelete_document(doc_id)

            results = await neo4j_store.asearch_entities("DeleteMe", top_k=5)
            assert all(r["name"] != "DeleteMe" for r in results)
        finally:
            await neo4j_store.adisconnect()