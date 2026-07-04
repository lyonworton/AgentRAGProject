import json
import time
import structlog
from app.agents.state import AgentState
from app.core.llm_factory import get_llm

logger = structlog.get_logger()

SYNTHESIZE_PROMPT = """Synthesize a final answer from the retrieved chunks. Follow these rules STRICTLY:

1. ONLY use information from the retrieved chunks below. Never use your own knowledge.
2. Cite EVERY factual statement with a numbered bracket like [1], [2], [3]. The number corresponds to the chunk number in the list below.
3. If sources disagree: "Sources disagree on X: [1] says A, but [2] says B."
4. If information is missing: "The available documents do not contain information about X."
5. If NO relevant chunks exist: "I cannot answer this question based on the available documents."
6. Be concise and accurate. Do not speculate.
7. Output the answer directly, no preamble.

Query: {query}

Retrieved chunks:
{chunks}
"""


async def synthesize_node(state: AgentState) -> AgentState:
    logger.info("synthesize_node_start", quality_score=state.get("quality_score", 0),
                has_draft=bool(state.get("draft_answer")), retrieved=len(state.get("retrieved", [])))
    llm = get_llm()

    # Group retrieved chunks by parent_group_id so each parent block
    # (heading + full text) is emitted once, with its child chunks listed below.
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
        # Truncate long headings to keep prompt clean
        if len(heading) > 60:
            heading = heading[:57] + "..."
        if heading and heading != "Unassigned":
            lines = [f"=== SECTION: {heading} ==="]
        else:
            lines = [f"=== SECTION: (parent={pg_id}) ==="]
        if info["parent_text"]:
            # Strip bracketed citation-like markers to prevent LLM from mimicking them
            text = info["parent_text"]
            lines.append(text)
        else:
            # Fallback: concatenate child texts if no parent block stored
            lines.extend(c["text"] for c in info["children"])
        lines.append("---")
        for c in sorted(info["children"], key=lambda x: x["score"], reverse=True):
            lines.append(f"  CHUNK [{c['chunk_id']}] (score={c['score']:.3f}): {c['text']}")
        return "\n".join(lines)

    chunks_text = "\n\n".join(
        _fmt_block(pg_id, info) for pg_id, info in chunks_by_parent.items()
    )

    if state.get("bare_minimum_mode"):
        chunks_text = f"RETRIEVAL UNAVAILABLE. Using memory only:\n{chunks_text}"

    if not chunks_text.strip():
        state["final_answer"] = "I cannot answer this question based on the available documents."
        state["citations"] = []
        state["uncertainty_flags"] = [{"note": "No relevant documents found", "severity": "high"}]
        return state

    # 高质量直接复用 draft，省掉 ~5s
    if state.get("quality_score", 0) >= 0.9 and state.get("draft_answer"):
        state["final_answer"] = state["draft_answer"]
        state["citations"] = [
            {"chunk_id": r.get("chunk_id", "?"),
             "document_title": r.get("document_id", "?"),
             "text": r.get("text", "")[:200],
             "relevance": r.get("score", 0)}
            for r in state.get("retrieved", [])[:10]
        ]
        state["uncertainty_flags"] = [
            {"text": c["text"], "status": c["status"]}
            for c in state.get("verified_claims", []) if c["status"] != "verified"
        ]
        return state

    answer = await llm.agenerate(
        SYNTHESIZE_PROMPT.format(query=state["query"], chunks=chunks_text),
        system_prompt="You are a precise answer synthesizer. Only use provided sources."
    )

    state["final_answer"] = answer
    state["citations"] = [
        {"chunk_id": r.get("chunk_id", "?"),
         "document_title": r.get("document_id", "?"),
         "text": r.get("text", "")[:200],
         "relevance": r.get("score", 0)}
        for r in state.get("retrieved", [])[:10]
    ]
    state["uncertainty_flags"] = [
        {"text": c["text"], "status": c["status"]}
        for c in state.get("verified_claims", []) if c["status"] != "verified"
    ]
    return state
