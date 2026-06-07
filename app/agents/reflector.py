import json
from app.agents.state import AgentState, RetrievedChunk
from app.core.llm_factory import get_llm

DRAFT_PROMPT = """Based on the retrieved chunks, draft a preliminary answer to the query.
Use ONLY the retrieved content. Do not fabricate. Cite chunk IDs inline like [c:chunk_id].
If no relevant information found, say "insufficient data".

Query: {query}
Retrieved chunks:
{chunks}
"""

REFLECT_PROMPT = """You are a strict critic. Review this draft answer against the original query.

Original query: {query}
Draft answer: {draft}

Check:
1. Does the answer fully address every aspect of the query?
2. Is any information missing from the draft?
3. Is the answer grounded in retrieved sources (not speculation)?
4. What specific information would improve the answer?

Output ONLY JSON:
{{
  "reflection_notes": "detailed critique",
  "missing_info": ["specific missing item 1", "specific missing item 2"],
  "quality_score": 0.75
}}
"""


async def reflector_node(state: AgentState) -> AgentState:
    llm = get_llm()
    chunks_text = "\n".join(
        f"[{r.get('chunk_id', '?')}] {r.get('text', '')[:500]}" for r in state.get("retrieved", [])
    )

    # Generate draft
    draft = await llm.agenerate(DRAFT_PROMPT.format(query=state["query"], chunks=chunks_text))
    state["draft_answer"] = draft

    # Reflect
    result = await llm.agenerate_structured(
        REFLECT_PROMPT.format(query=state["query"], draft=draft),
        "You are a strict quality reviewer.",
        {"type": "object", "properties": {
            "reflection_notes": {"type": "string"},
            "missing_info": {"type": "array", "items": {"type": "string"}},
            "quality_score": {"type": "number"}
        }, "required": ["reflection_notes", "missing_info", "quality_score"]}
    )

    state["reflection_notes"] = result["reflection_notes"]
    state["missing_info"] = result.get("missing_info", [])
    state["quality_score"] = result["quality_score"]
    state["need_another_round"] = state["quality_score"] < 0.7
    return state
