"""Integration test fixtures — skip gracefully when backend services are unavailable."""

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: tests requiring real Neo4j/ES/Milvus")


@pytest.fixture
def require_neo4j():
    """Skip if Neo4j is not reachable."""
    host = os.environ.get("NEO4J_HOST", os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    # Parse bolt://host:port
    if host.startswith("bolt://"):
        host = host.replace("bolt://", "").split(":")[0]
    try:
        from neo4j import GraphDatabase

        with GraphDatabase.driver(
            f"bolt://{host}:7687",
            auth=("neo4j", os.environ.get("NEO4J_PASSWORD", "agentrag123")),
        ) as d:
            d.verify_connectivity()
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")


@pytest.fixture
def require_es():
    """Skip if Elasticsearch is not reachable."""
    host = os.environ.get("ES_HOST", "http://localhost:9200")
    try:
        import httpx

        r = httpx.get(f"{host}/_cluster/health", timeout=5)
        if r.status_code != 200:
            pytest.skip(f"ES cluster health returned {r.status_code}")
    except Exception as e:
        pytest.skip(f"ES not available: {e}")


@pytest.fixture
def neo4j_store(require_neo4j):
    """Return a connected Neo4jKGStore."""
    from app.adapters.kg.neo4j import Neo4jKGStore

    store = Neo4jKGStore()
    return store


@pytest.fixture
def es_store(require_es):
    """Return a connected ElasticsearchStore."""
    from app.adapters.search.elasticsearch import ElasticsearchStore

    store = ElasticsearchStore()
    return store