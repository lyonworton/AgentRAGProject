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
        "bare_minimum_mode": False, "iteration": 2, "max_iterations": 2,
        "prev_score": None, "collection_ids": [],
    }


class TestSynthesizeNode:
    async def test_synthesizes_answer_with_citations(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate.return_value = "RAG response [c:c1]."
        with patch("app.agents.nodes.get_llm", return_value=mock_llm):
            from app.agents.nodes import synthesize_node
            state = await synthesize_node(_make_state())
        assert len(state["final_answer"]) > 0
        assert len(state["citations"]) == 1

    async def test_empty_retrieved_returns_graceful_message(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate.return_value = "I cannot answer this question."
        with patch("app.agents.nodes.get_llm", return_value=mock_llm):
            from app.agents.nodes import synthesize_node
            state = await synthesize_node(_make_state(retrieved=[]))
        assert "cannot answer" in state["final_answer"].lower()
        assert state["citations"] == []
