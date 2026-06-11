import pytest
from app.agents.query_detector import detect_query_type


class TestDetectQueryType:
    def test_detects_double_quoted_phrase(self):
        result = detect_query_type('"machine learning"')
        assert result["query_type"] == "exact"
        assert result["confidence"] >= 0.8

    def test_detects_single_quoted_phrase(self):
        result = detect_query_type("'deep neural network'")
        assert result["query_type"] == "exact"
        assert result["confidence"] >= 0.8

    def test_detects_id_pattern(self):
        result = detect_query_type("DOC-12345")
        assert result["query_type"] == "exact"
        assert result["confidence"] >= 0.9

    def test_detects_numeric_code(self):
        result = detect_query_type("123456789")
        assert result["query_type"] == "exact"
        assert result["confidence"] >= 0.8

    def test_defaults_to_semantic_for_normal_query(self):
        result = detect_query_type("What is retrieval augmented generation?")
        assert result["query_type"] == "semantic"
        assert result["confidence"] == 0.5

    def test_empty_query_defaults_to_semantic(self):
        result = detect_query_type("")
        assert result["query_type"] == "semantic"
        assert result["confidence"] == 0.5

    def test_whitespace_query_defaults_to_semantic(self):
        result = detect_query_type("   ")
        assert result["query_type"] == "semantic"
        assert result["confidence"] == 0.5

    def test_none_input(self):
        result = detect_query_type(None)
        assert result["query_type"] == "semantic"
        assert result["confidence"] == 0.5