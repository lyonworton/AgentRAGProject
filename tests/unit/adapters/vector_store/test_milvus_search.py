import pytest
from app.adapters.vector_store.base import SearchResult


def test_search_result_populates_content_start_content_end_parent_group_id_from_metadata():
    """SearchResult.__post_init__ should populate content_start, content_end, parent_group_id from metadata."""
    sr = SearchResult(
        chunk_id="c1",
        document_id="d1",
        text="hello world",
        score=0.95,
        metadata={
            "content_start": 10,
            "content_end": 50,
            "parent_group_id": "group-abc",
        },
    )
    assert sr.content_start == 10
    assert sr.content_end == 50
    assert sr.parent_group_id == "group-abc"


def test_search_result_defaults_to_none_when_metadata_absent():
    """When metadata doesn't contain the fields, they should default to None."""
    sr = SearchResult(
        chunk_id="c1",
        document_id="d1",
        text="hello world",
        score=0.95,
        metadata={},
    )
    assert sr.content_start is None
    assert sr.content_end is None
    assert sr.parent_group_id is None
