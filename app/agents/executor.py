import asyncio
import structlog
from app.agents.state import AgentState, RetrievedChunk
from app.tools import get_tool_registry

logger = structlog.get_logger()


def _resolve_groups(sub_tasks: list[dict]) -> list[list[str]]:
    """Topological sort into execution groups. Tasks within a group have no mutual dependencies."""
    if not sub_tasks:
        return []

    all_ids = {t["id"] for t in sub_tasks}
    for t in sub_tasks:
        for dep in t.get("depends_on", []):
            if dep not in all_ids:
                raise ValueError(f"Task {t['id']} depends on unknown task {dep}")

    completed: set[str] = set()
    remaining = {t["id"]: set(t.get("depends_on", [])) for t in sub_tasks}
    groups: list[list[str]] = []

    while remaining:
        ready = [tid for tid, deps in remaining.items() if deps.issubset(completed)]
        if not ready:
            raise ValueError(f"Circular dependency detected: {remaining}")
        groups.append(ready)
        completed.update(ready)
        for tid in ready:
            del remaining[tid]

    return groups


async def _execute_task(
    task: dict,
    routes: dict[str, list[str]],
    collection_ids: list[str],
    registry,
) -> tuple[list[dict], list[str]]:
    tool_names = routes.get(task["id"], ["semantic_search"])
    task["status"] = "running"
    warnings: list[str] = []

    async def _run_tool(name: str):
        try:
            return await asyncio.wait_for(
                registry.get(name).arun(task["description"], collection_ids),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            return TimeoutError(f"Tool {name} timed out after 60s — BGE model may still be loading")
        except Exception as e:
            return e

    results = await asyncio.gather(*[_run_tool(name) for name in tool_names])

    hits: list[dict] = []
    for name, result in zip(tool_names, results):
        if isinstance(result, Exception):
            warnings.append(f"Tool {name} failed: {result}")
        else:
            tagged = [dict(item, _tool=name) for item in result]
            hits.extend(tagged)

    task["status"] = "failed" if not hits else "done"
    return hits, warnings


async def executor_node(state: AgentState) -> AgentState:
    sub_tasks = state.get("sub_tasks", [])
    routes = state.get("routes", {})
    collection_ids = state.get("collection_ids", [])

    logger.info("executor_node", sub_tasks=len(sub_tasks), routes=list(routes.keys()), collection_ids=collection_ids)
    state["raw_milvus_hits"] = []
    state["raw_kg_results"] = []
    state["raw_keyword_hits"] = []
    warnings: list[str] = []

    if not sub_tasks:
        logger.warning("executor_no_sub_tasks", query=state.get("query", "")[:100])
        state["retrieved"] = []
        state["warnings"] = warnings
        return state

    registry = get_tool_registry()

    try:
        groups = _resolve_groups(sub_tasks)
    except ValueError as e:
        if "depends on unknown" in str(e):
            groups = [[t["id"]] for t in sub_tasks]
            warnings.append(f"Dependency resolution skipped: {e}")
        else:
            raise

    all_hits: list[dict] = []
    for group in groups:
        group_tasks = [t for t in sub_tasks if t["id"] in group]
        group_results = await asyncio.gather(*[
            _execute_task(t, routes, collection_ids, registry)
            for t in group_tasks
        ])
        for hits, warns in group_results:
            all_hits.extend(hits)
            warnings.extend(warns)

    # Phase 5: Rerank with pluggable reranker (default RRF, zero-cost)
    if all_hits:
        from app.adapters.reranker.factory import get_reranker
        reranker = get_reranker()
        all_hits = await reranker.rerank(state["query"], all_hits, top_k=10)
    else:
        all_hits = []

    # Phase 6: Compute routing quality metrics
    tool_selection_counts: dict[str, int] = {}
    for tid, tools in routes.items():
        for t in tools:
            tool_selection_counts[t] = tool_selection_counts.get(t, 0) + 1

    tool_hit_counts: dict[str, int] = {}
    for h in all_hits:
        tool = h["_tool"]
        tool_hit_counts[tool] = tool_hit_counts.get(tool, 0) + 1

    sources_after = list({h["source"] for h in all_hits})

    state["routing_metrics"] = {
        "tools_selected": tool_selection_counts,
        "results_per_tool": tool_hit_counts,
        "sources_in_final": sources_after,
        "source_diversity": len(sources_after) / max(len(tool_selection_counts), 1),
    }

    retrieved: list[RetrievedChunk] = []
    seen: set[str] = set()
    for hit in all_hits:
        if hit["chunk_id"] not in seen:
            retrieved.append(RetrievedChunk(
                chunk_id=hit["chunk_id"],
                document_id=hit.get("document_id", ""),
                text=hit["text"],
                score=hit.get("_rerank_score", hit["score"]),
                source=hit["source"],
                metadata={},
            ))
            seen.add(hit["chunk_id"])

    state["retrieved"] = retrieved
    state["raw_milvus_hits"] = [h for h in all_hits if h["_tool"] == "semantic_search"]
    state["raw_kg_results"] = [h for h in all_hits if h["_tool"] == "kg_search"]
    state["raw_keyword_hits"] = [h for h in all_hits if h["_tool"] == "keyword_search"]
    state.setdefault("warnings", []).extend(warnings)
    logger.info("executor_done", retrieved=len(retrieved), warnings=len(warnings))
    return state
