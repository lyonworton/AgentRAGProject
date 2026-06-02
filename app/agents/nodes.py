import json
import time
from app.agents.state import AgentState
from app.adapters.llm.openai import OpenAILLM

SYNTHESIZE_PROMPT = """Synthesize a final answer from the retrieved chunks. Follow these rules STRICTLY:

1. ONLY use information from the retrieved chunks below. Never use your own knowledge.
2. Cite EVERY factual statement with its source chunk ID like [c:chunk_id].
3. If sources disagree: "Sources disagree on X: [c:a] says A, but [c:b] says B."
4. If information is missing: "The available documents do not contain information about X."
5. If NO relevant chunks exist: "I cannot answer this question based on the available documents."
6. Be concise and accurate. Do not speculate.
7. Output the answer directly, no preamble.

Query: {query}

Retrieved chunks:
{chunks}
"""


async def synthesize_node(state: AgentState) -> AgentState:
    llm = OpenAILLM()
    chunks_text = "\n\n".join(
        f"CHUNK [{r.get('chunk_id', '?')}] (from {r.get('document_id', '?')}, score={r.get('score', 0):.3f}):\n{r.get('text', '')}"
        for r in state.get("retrieved", [])
    )

    if state.get("bare_minimum_mode"):
        chunks_text = f"RETRIEVAL UNAVAILABLE. Using memory only:\n{chunks_text}"

    if not chunks_text.strip():
        state["final_answer"] = "I cannot answer this question based on the available documents."
        state["citations"] = []
        state["uncertainty_flags"] = [{"note": "No relevant documents found", "severity": "high"}]
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
