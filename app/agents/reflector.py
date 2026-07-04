import json
import time
import structlog
from app.agents.state import AgentState, RetrievedChunk
from app.core.llm_factory import get_llm

logger = structlog.get_logger()

REFLECT_DRAFT_PROMPT = """You are a helpful assistant and a strict quality reviewer combined.

Given the query and retrieved chunks below, do TWO things in ONE structured JSON output:

1. DRAFT a preliminary answer to the query using ONLY the retrieved content. Cite using numbered brackets like [1], [2], [3].
2. SELF-RATE the draft on quality (0.0-1.0), noting what's missing and why.

If no relevant information found, say "insufficient data" in the draft.

Query: {query}
Retrieved chunks:
{chunks}

Output ONLY JSON:
{{
  "draft_answer": "the drafted answer with inline citations like [1], [2]",
  "reflection_notes": "detailed critique of the draft",
  "missing_info": ["specific missing item 1", "specific missing item 2"],
  "quality_score": 0.75
}}
"""


async def reflector_node(state: AgentState) -> AgentState:
    logger.info("reflect_node_start", retrieved=len(state.get("retrieved", [])))
    llm = get_llm()

    # Group by parent_group_id — each parent block emitted once with its children
    chunks_by_parent: dict[str, dict] = {}
    for r in state.get("retrieved", []):
        pg_id = r.get("metadata", {}).get("parent_group_id", "unassigned")
        if pg_id not in chunks_by_parent:
            chunks_by_parent[pg_id] = {
                "heading": r.get("metadata", {}).get("parent_heading", "Unassigned"),
                "parent_text": r.get("metadata", {}).get("parent_text", ""),
                "children": [],
            }
        chunks_by_parent[pg_id]["children"].append({
            "chunk_id": r.get("chunk_id", "?"),
            "text": r.get("text", ""),
            "score": r.get("score", 0),
        })

    def _fmt_block(pg_id: str, info: dict) -> str:
        heading = info["heading"]
        if len(heading) > 60:
            heading = heading[:57] + "..."
        if heading and heading != "Unassigned":
            lines = [f"=== SECTION: {heading} ==="]
        else:
            lines = [f"=== SECTION: (parent={pg_id}) ==="]
        if info["parent_text"]:
            lines.append(info["parent_text"])
        else:
            lines.extend(c["text"] for c in info["children"])
        lines.append("---")
        for c in sorted(info["children"], key=lambda x: x["score"], reverse=True):
            lines.append(f"  CHUNK [{c['chunk_id']}] (score={c['score']:.3f}): {c['text']}")
        return "\n".join(lines)

    chunks_text = "\n\n".join(
        _fmt_block(pg_id, info) for pg_id, info in chunks_by_parent.items()
    )

    # Single LLM call: draft + self-rate
    t0 = time.monotonic()
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
    logger.info("reflect_node_llm_done", elapsed_sec=round(time.monotonic() - t0, 2),
                 quality_score=result.get("quality_score", 0), draft_len=len(result.get("draft_answer", "")))

    state["draft_answer"] = result.get("draft_answer", "")
    state["reflection_notes"] = result.get("reflection_notes", "")
    state["missing_info"] = result.get("missing_info", [])
    state["quality_score"] = result.get("quality_score", 0.0)
    state["need_another_round"] = state["quality_score"] < 0.7
    # Increment iteration here — should_continue (a conditional edge function)
    # cannot persist state mutations, so we must do it in a node function.
    state["iteration"] = state.get("iteration", 0) + 1
    return state
