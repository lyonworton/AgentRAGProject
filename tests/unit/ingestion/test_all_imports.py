def test_import_entity_extractor():
    from app.ingestion.graph_path.entity_extractor import extract_candidate_entities
    assert extract_candidate_entities is not None


def test_import_relation_extractor():
    from app.ingestion.graph_path.relation_extractor import extract_relations, RELATION_SCHEMA
    assert extract_relations is not None
    assert RELATION_SCHEMA is not None


def test_import_neo4j_writer():
    from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j
    assert write_graph_to_neo4j is not None


def test_import_es_writer():
    from app.ingestion.keyword_path.es_writer import write_document_to_es
    assert write_document_to_es is not None


def test_import_web_source():
    from app.ingestion.sources.web import WebSource
    assert WebSource is not None


def test_import_db_source():
    from app.ingestion.sources.database import DBSource
    assert DBSource is not None


def test_import_repair_worker():
    from app.workers.repair import repair_document_path, enqueue_repair, BACKOFF
    assert repair_document_path is not None
    assert enqueue_repair is not None
    assert BACKOFF is not None


def test_import_pipeline_functions():
    from app.ingestion.pipeline import (
        run_semantic_path, run_graph_path, run_keyword_path,
        _compute_path_status, run_ingest_pipeline,
    )
    assert run_semantic_path is not None
    assert run_graph_path is not None
    assert run_keyword_path is not None
    assert _compute_path_status is not None
    assert run_ingest_pipeline is not None