import json
import time
import structlog
from app.agents.state import AgentState, VerifiedClaim
from app.core.llm_factory import get_llm

logger = structlog.get_logger()

VERIFY_PROMPT = """Verify whether each claim in the draft answer is supported by the retrieved chunks.

Draft answer: {draft}

Retrieved chunks:
{chunks}

For each claim (sentence) in the draft:
1. Find the best supporting chunk for the claim
2. Mark as "verified" if supported, "unverified" if no support, "contradicted" if chunks disagree
3. If unverified, generate a search query to find the missing information

Output ONLY JSON:
{{
  "claims": [
    {{"text": "the claim text", "status": "verified", "source_chunk_id": "chunk_abc", "contradiction_note": null}},
    {{"text": "another claim", "status": "unverified", "source_chunk_id": null, "contradiction_note": null, "search_query": "how to find this"}}
  ]
}}
"""


async def verifier_node(state: AgentState) -> AgentState:
    logger.info("verify_node_start", draft_len=len(state.get("draft_answer", "")), retrieved=len(state.get("retrieved", [])))
    llm = get_llm()
    draft = state.get("draft_answer", "")
    chunks_text = "\n".join(
        f"[{r.get('chunk_id', '?')}] parent={r.get('metadata', {}).get('parent_group_id', '?')} "
        f"heading={r.get('metadata', {}).get('parent_heading', '?')}\n"
        f"  TEXT: {r.get('metadata', {}).get('parent_text', r.get('text', ''))[:2000]}"
        for r in state.get("retrieved", [])
    )

    if not draft.strip() or not chunks_text.strip():
        logger.info("verify_node_skip", reason="empty_draft_or_chunks")
        state["verified_claims"] = []
        state["need_supplement"] = False
        return state

    t0 = time.monotonic()
    result = await llm.agenerate_structured(
        VERIFY_PROMPT.format(draft=draft, chunks=chunks_text),
        "You are a fact verification specialist.",
        {"type": "object", "properties": {
            "claims": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"}, "status": {"type": "string", "enum": ["verified", "unverified", "contradicted"]},
                "source_chunk_id": {"type": "string", "nullable": True},
                "contradiction_note": {"type": "string", "nullable": True},
                "search_query": {"type": "string", "nullable": True}
            }}}
        }}
    )
    logger.info("verify_node_llm_done", elapsed_sec=round(time.monotonic() - t0, 2), claims=len(result.get("claims", [])))

    claims: list[VerifiedClaim] = [
        {"text": c["text"], "status": c["status"],
         "source_chunk_id": c.get("source_chunk_id"), "contradiction_note": c.get("contradiction_note")}
        for c in result.get("claims", [])
    ]
    state["verified_claims"] = claims

    verified_count = sum(1 for c in claims if c["status"] == "verified")
    total = len(claims)
    verified_ratio = verified_count / total if total > 0 else 1.0

    # 如果 unverified 超过 10%（即 verified 不到 90%），需要再查一轮
    if verified_ratio < 0.9:
        state["need_supplement"] = True
        state["supplement_queries"] = [
            c.get("search_query", c["text"]) for c in claims
            if c["status"] == "unverified" and c.get("search_query")
        ][:3]
    else:
        state["need_supplement"] = False
        state["supplement_queries"] = []

    return state
