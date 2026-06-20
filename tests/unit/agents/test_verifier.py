import pytest
from unittest.mock import patch, AsyncMock


def _make_state(draft="", retrieved=None):
    return {
        "query": "test", "conversation_history": [], "intent": "fact",
        "rewritten_query": "test", "sub_tasks": [], "routes": {},
        "retrieved": retrieved if retrieved is not None else [
            {"chunk_id": "c1", "document_id": "d1", "text": "Evidence.", "score": 0.9, "source": "milvus", "metadata": {}},
        ],
        "raw_milvus_hits": [], "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0,
        "need_another_round": False, "draft_answer": draft, "verified_claims": [],
        "supplement_queries": [], "need_supplement": False, "final_answer": "",
        "citations": [], "uncertainty_flags": [], "warnings": [],
        "bare_minimum_mode": False, "iteration": 0, "max_iterations": 2,
        "prev_score": None, "collection_ids": [],
    }


class TestVerifierNode:
    async def test_verifies_claims(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "claims": [
                {"text": "A", "status": "verified", "source_chunk_id": "c1", "contradiction_note": None},
                {"text": "B", "status": "unverified", "source_chunk_id": None, "contradiction_note": None, "search_query": "find B"},
            ]
        }
        with patch("app.agents.verifier.get_llm", return_value=mock_llm):
            from app.agents.verifier import verifier_node
            state = await verifier_node(_make_state(draft="A. B."))
        assert len(state["verified_claims"]) == 2
        assert state["verified_claims"][0]["status"] == "verified"

    async def test_unverified_triggers_supplement(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "claims": [
                {"text": "X", "status": "unverified", "source_chunk_id": None, "contradiction_note": None, "search_query": "find X"},
                {"text": "Y", "status": "unverified", "source_chunk_id": None, "contradiction_note": None},
            ]
        }
        with patch("app.agents.verifier.get_llm", return_value=mock_llm):
            from app.agents.verifier import verifier_node
            state = await verifier_node(_make_state(draft="X. Y."))
        assert state["need_supplement"] is True

    async def test_empty_draft_returns_early(self):
        from app.agents.verifier import verifier_node
        state = await verifier_node(_make_state(draft=""))
        assert state["verified_claims"] == []
        assert state["need_supplement"] is False
