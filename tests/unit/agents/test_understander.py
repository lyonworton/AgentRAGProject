import pytest
from unittest.mock import patch, AsyncMock


def _make_state(query="What is RAG?", history=None):
    return {
        "query": query, "conversation_history": history or [],
        "intent": "", "rewritten_query": "", "sub_tasks": [],
        "routes": {}, "retrieved": [], "raw_milvus_hits": [],
        "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0,
        "need_another_round": False, "draft_answer": "", "verified_claims": [],
        "supplement_queries": [], "need_supplement": False, "final_answer": "",
        "citations": [], "uncertainty_flags": [], "warnings": [],
        "bare_minimum_mode": False, "iteration": 0, "max_iterations": 5,
        "prev_score": None, "collection_ids": [],
    }


class TestUnderstandNode:
    async def test_populates_intent_and_subtasks(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "intent": "fact",
            "rewritten_query": "What is retrieval augmented generation?",
            "sub_tasks": [
                {"id": "t1", "description": "Define RAG", "intent": "fact", "depends_on": []},
            ],
        }
        with patch("app.agents.understander.get_llm", return_value=mock_llm):
            from app.agents.understander import understand_node
            state = await understand_node(_make_state("What is RAG?"))
        assert state["intent"] == "fact"
        assert "retrieval augmented" in state["rewritten_query"].lower()
        assert len(state["sub_tasks"]) == 1
        assert state["sub_tasks"][0]["status"] == "pending"

    async def test_handles_empty_subtasks(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "intent": "fact", "rewritten_query": "", "sub_tasks": [],
        }
        with patch("app.agents.understander.get_llm", return_value=mock_llm):
            from app.agents.understander import understand_node
            state = await understand_node(_make_state(""))
        assert state["intent"] == "fact"
        assert state["sub_tasks"] == []

    async def test_can_output_exact_intent(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "intent": "exact",
            "rewritten_query": "DOC-12345",
            "sub_tasks": [
                {"id": "t1", "description": "Find document DOC-12345", "intent": "exact", "depends_on": []},
            ],
        }
        with patch("app.agents.understander.get_llm", return_value=mock_llm):
            from app.agents.understander import understand_node
            state = await understand_node(_make_state('Find "DOC-12345"'))
        assert state["intent"] == "exact"
        assert state["sub_tasks"][0]["intent"] == "exact"
