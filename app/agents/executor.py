import json
from app.agents.state import AgentState, RetrievedChunk
from app.adapters.llm.openai import OpenAILLM
from app.adapters.embedding.openai_embed import OpenAIEmbedding
from app.adapters.vector_store.milvus import MilvusStore

QUERY_EXPAND_PROMPT = """Generate {n} alternative search queries for the given task description.
The variants should use different wording, synonyms, and perspectives to maximize recall.
Output JSON array of strings only.
"""


async def _expand_queries(task_desc: str, n: int = 3) -> list[str]:
    llm = OpenAILLM()
    result = await llm.agenerate_structured(
        QUERY_EXPAND_PROMPT.format(n=n) + f"\nTask: {task_desc}",
        output_schema={"type": "array", "items": {"type": "string"}}
    )
    return result if isinstance(result, list) else [task_desc]


async def executor_node(state: AgentState) -> AgentState:
    embedder = OpenAIEmbedding()
    store = MilvusStore()
    retrieved: list[RetrievedChunk] = []
    seen_ids: set[str] = set()

    for task in state.get("sub_tasks", []):
        route = state["routes"].get(task["id"], "milvus")
        if route != "milvus":
            continue  # Phase 1: only milvus

        variants = await _expand_queries(task["description"])
        all_hits = []

        for variant in variants:
            qe = await embedder.aembed_query(variant)
            # Use the appropriate collection for each collection_id
            for col_id in state.get("collection_ids", []):
                col_name = f"col_{col_id}"
                try:
                    hits = await store.search(col_name, qe, top_k=10)
                    all_hits.extend(hits)
                except Exception as e:
                    state.setdefault("warnings", []).append(f"Milvus search failed for {col_name}: {e}")
                    continue

        # Merge, deduplicate, sort by score
        all_hits.sort(key=lambda h: h.score, reverse=True)
        for hit in all_hits:
            if hit.chunk_id not in seen_ids:
                retrieved.append(hit)
                seen_ids.add(hit.chunk_id)

    state["retrieved"] = retrieved
    state["raw_milvus_hits"] = [{"chunk_id": r.chunk_id, "score": r.score, "text": r.text[:200]} for r in retrieved]
    return state
