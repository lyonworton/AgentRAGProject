import json
from app.agents.state import AgentState, RetrievedChunk
from app.core.llm_factory import get_llm

REFLECT_DRAFT_PROMPT = """You are a helpful assistant and a strict quality reviewer combined.

Given the query and retrieved chunks below, do TWO things in ONE structured JSON output:

1. DRAFT a preliminary answer to the query using ONLY the retrieved content. Cite chunk IDs inline like [c:chunk_id].
2. SELF-RATE the draft on quality (0.0-1.0), noting what's missing and why.

If no relevant information found, say "insufficient data" in the draft.

Query: {query}
Retrieved chunks:
{chunks}

Output ONLY JSON:
{{
  "draft_answer": "the drafted answer with inline citations like [c:chunk_id]",
  "reflection_notes": "detailed critique of the draft",
  "missing_info": ["specific missing item 1", "specific missing item 2"],
  "quality_score": 0.75
}}
"""


async def reflector_node(state: AgentState) -> AgentState:
    llm = get_llm()
    chunks_text = "\n".join(
        f"[{r.get('chunk_id', '?')}] {r.get('text', '')[:500]}" for r in state.get("retrieved", [])
    )

    # Single LLM call: draft + self-rate
    result = await llm.agenerate_structured(
        REFLECT_DRAFT_PROMPT.format(query=state["query"], chunks=chunks_text),
        "You are a helpful assistant and a strict quality reviewer.",
        {"type": "object", "properties": {
            "draft_answer": {"type": "string"},
            "reflection_notes": {"type": "string"},
            "missing_info": {"type": "array", "items": {"type": "string"}},
            "quality_score": {"type": "number"}
        }, "required": ["draft_answer", "reflection_notes", "missing_info", "quality_score"]}
    )

    state["draft_answer"] = result.get("draft_answer", "")
    state["reflection_notes"] = result.get("reflection_notes", "")
    state["missing_info"] = result.get("missing_info", [])
    state["quality_score"] = result.get("quality_score", 0.0)
    state["need_another_round"] = state["quality_score"] < 0.7
    return state
