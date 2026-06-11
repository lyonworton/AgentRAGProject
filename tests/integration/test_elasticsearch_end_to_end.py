"""Integration tests: Elasticsearch store — connect, write, search, delete."""

import pytest


@pytest.mark.integration
class TestElasticsearchEndToEnd:
    async def test_health_check(self, es_store):
        """Can connect and cluster health passes."""
        await es_store.aconnect()
        try:
            await es_store.ahealth_check()
        finally:
            await es_store.adisconnect()

    async def test_index_and_search_document(self, es_store):
        """Write a document then search returns it."""
        collection_id = "integration-test-col"
        doc_id = "es-test-doc-1"

        await es_store.aconnect()
        try:
            await es_store.aindex_document(
                collection_id,
                doc_id,
                title="Integration Test Document",
                content="This is a test document for Elasticsearch integration testing.",
                metadata={"source_type": "test", "page_number": 1},
            )

            # ES is near-realtime — force refresh
            await es_store._client.indices.refresh(index=es_store._index_name(collection_id))

            results = await es_store.asearch(collection_id, "integration test", top_k=5)
            assert len(results) > 0
            assert any(r["document_id"] == doc_id for r in results)
        finally:
            await es_store.adelete_document(collection_id, doc_id)
            await es_store.adelete_index(collection_id)
            await es_store.adisconnect()

    async def test_search_empty_for_missing(self, es_store):
        """Search in empty/nonexistent index returns nothing."""
        collection_id = "integration-test-empty"
        await es_store.aconnect()
        try:
            results = await es_store.asearch(collection_id, "nonexistent query", top_k=5)
            # Should return empty or raise not-found
            assert results == []
        finally:
            await es_store.adelete_index(collection_id)
            await es_store.adisconnect()

    async def test_delete_document_removes_from_index(self, es_store):
        """After deleting, the document is no longer searchable."""
        collection_id = "integration-test-col-2"
        doc_id = "es-test-doc-2"

        await es_store.aconnect()
        try:
            await es_store.aindex_document(
                collection_id,
                doc_id,
                title="To Be Deleted",
                content="This document will be deleted.",
                metadata={"source_type": "test"},
            )
            await es_store.adelete_document(collection_id, doc_id)

            results = await es_store.asearch(collection_id, "deleted", top_k=5)
            assert not any(r["document_id"] == doc_id for r in results)
        finally:
            await es_store.adelete_index(collection_id)
            await es_store.adisconnect()