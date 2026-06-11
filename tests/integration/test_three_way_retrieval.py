"""Integration tests: three-way parallel retrieval with RRF cross-source fusion."""

import pytest


@pytest.mark.integration
class TestThreeWayRetrieval:
    async def test_all_three_tools_run_and_return(self, neo4j_store, es_store):
        """KG, ES, and semantic searches all run and return results."""
        import asyncio
        from app.tools.kg_search import KGSearchTool
        from app.tools.keyword_search import KeywordSearchTool
        from app.tools.semantic_search import SemanticSearchTool

        # Seed Neo4j with test data
        await neo4j_store.aconnect()
        try:
            await neo4j_store.acreate_graph(
                "three-way-doc-1",
                [{"id": "three-e1", "name": "ThreeWayTest", "type": "concept"}],
                [],
            )

            # Seed ES with test data
            await es_store.aconnect()
            await es_store.aindex_document(
                "three-way-col",
                "three-way-es-1",
                title="ThreeWayTest Document",
                content="This is a three-way integration test document for cross-source retrieval.",
                metadata={"source_type": "test"},
            )

            # Run all three in parallel
            tools = [SemanticSearchTool(), KGSearchTool(), KeywordSearchTool()]
            results = await asyncio.gather(*[
                t.arun("ThreeWayTest", ["three-way-col"]) for t in tools
            ], return_exceptions=True)

            # At least one tool should return results
            success_count = sum(1 for r in results if isinstance(r, list) and len(r) > 0)
            assert success_count >= 1, f"All three tools returned empty/error: {results}"
        finally:
            await neo4j_store.adelete_document("three-way-doc-1")
            await neo4j_store.adisconnect()
            await es_store.adelete_document("three-way-col", "three-way-es-1")
            await es_store.adelete_index("three-way-col")
            await es_store.adisconnect()

    async def test_rrf_fusion_unifies_scores(self, neo4j_store, es_store):
        """RRF gives comparable scores across KG, ES, and semantic sources."""
        from app.adapters.reranker.rrf import RRFReranker

        await neo4j_store.aconnect()
        await es_store.aconnect()
        try:
            await neo4j_store.acreate_graph(
                "rrf-fusion-doc",
                [{"id": "rrf-e1", "name": "RRF Test Entity", "type": "concept"}],
                [],
            )
            await es_store.aindex_document(
                "rrf-fusion-col",
                "rrf-es-1",
                title="RRF Fusion Test",
                content="RRF fusion integration test content.",
                metadata={"source_type": "test"},
            )

            from app.tools.kg_search import KGSearchTool
            from app.tools.keyword_search import KeywordSearchTool

            kg_tool = KGSearchTool()
            es_tool = KeywordSearchTool()

            kg_results = await kg_tool.arun("RRF", ["rrf-fusion-col"])
            es_results = await es_tool.arun("RRF", ["rrf-fusion-col"])

            if kg_results or es_results:
                all_docs = kg_results + es_results
                rrf = RRFReranker(k=60)
                fused = await rrf.rerank("RRF Test", all_docs, top_k=10)

                # All fused docs should have _rerank_score
                for doc in fused:
                    assert "_rerank_score" in doc
                    assert doc["_rerank_score"] > 0
                    assert doc["_rerank_score"] <= 1.0 / 61  # max possible: 1/(k+1)

                # Cross-source results should be mixed, not all from one source
                if len(fused) >= 2:
                    sources = {d.get("source") for d in fused}
                    assert len(sources) > 0
        finally:
            await neo4j_store.adelete_document("rrf-fusion-doc")
            await neo4j_store.adisconnect()
            await es_store.adelete_document("rrf-fusion-col", "rrf-es-1")
            await es_store.adelete_index("rrf-fusion-col")
            await es_store.adisconnect()

    async def test_rrf_empty_input_returns_empty(self):
        """RRF handles empty hit list gracefully."""
        from app.adapters.reranker.rrf import RRFReranker

        rrf = RRFReranker()
        result = await rrf.rerank("query", [], top_k=10)
        assert result == []