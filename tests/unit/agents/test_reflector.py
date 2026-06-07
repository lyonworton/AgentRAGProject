import pytest
from unittest.mock import patch, AsyncMock


def _make_state(query="test", retrieved=None):
    return {
        "query": query, "conversation_history": [], "intent": "fact",
        "rewritten_query": query, "sub_tasks": [], "routes": {},
        "retrieved": retrieved if retrieved is not None else [
            {"chunk_id": "c1", "document_id": "d1", "text": "RAG test.", "score": 0.9, "source": "milvus", "metadata": {}},
        ],
        "raw_milvus_hits": [], "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0,
        "need_another_round": False, "draft_answer": "", "verified_claims": [],
        "supplement_queries": [], "need_supplement": False, "final_answer": "",
        "citations": [], "uncertainty_flags": [], "warnings": [],
        "bare_minimum_mode": False, "iteration": 0, "max_iterations": 5,
        "prev_score": None, "collection_ids": [],
    }


class TestReflectorNode:
    async def test_generates_draft_and_reflection(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate.return_value = "RAG combines retrieval with generation."
        mock_llm.agenerate_structured.return_value = {
            "reflection_notes": "Good coverage", "missing_info": [], "quality_score": 0.85,
        }
        with patch("app.agents.reflector.get_llm", return_value=mock_llm):
            from app.agents.reflector import reflector_node
            state = await reflector_node(_make_state())
        assert len(state["draft_answer"]) > 0
        assert state["quality_score"] == 0.85

    async def test_low_quality_triggers_another_round(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate.return_value = "Short."
        mock_llm.agenerate_structured.return_value = {
            "reflection_notes": "Incomplete", "missing_info": ["Missing X"], "quality_score": 0.3,
        }
        with patch("app.agents.reflector.get_llm", return_value=mock_llm):
            from app.agents.reflector import reflector_node
            state = await reflector_node(_make_state())
        assert state["quality_score"] == 0.3
        assert state["need_another_round"] is True
