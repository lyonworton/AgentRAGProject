import asyncio
from app.agents.state import AgentState, RetrievedChunk
from app.tools import get_tool_registry


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

    results = await asyncio.gather(*[
        registry.get(name).arun(task["description"], collection_ids)
        for name in tool_names
    ], return_exceptions=True)

    hits: list[dict] = []
    for name, result in zip(tool_names, results):
        if isinstance(result, Exception):
            warnings.append(f"Tool {name} failed: {result}")
        else:
            for item in result:
                item["_tool"] = name
            hits.extend(result)

    task["status"] = "failed" if not hits else "done"
    return hits, warnings


async def executor_node(state: AgentState) -> AgentState:
    sub_tasks = state.get("sub_tasks", [])
    routes = state.get("routes", {})
    collection_ids = state.get("collection_ids", [])

    state["raw_milvus_hits"] = []
    state["raw_kg_results"] = []
    state["raw_keyword_hits"] = []
    warnings: list[str] = []

    if not sub_tasks:
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

    retrieved: list[RetrievedChunk] = []
    seen: set[str] = set()
    for hit in sorted(all_hits, key=lambda h: h["score"], reverse=True):
        if hit["chunk_id"] not in seen:
            retrieved.append(RetrievedChunk(
                chunk_id=hit["chunk_id"],
                document_id=hit.get("document_id", ""),
                text=hit["text"],
                score=hit["score"],
                source=hit["source"],
                metadata={},
            ))
            seen.add(hit["chunk_id"])

    state["retrieved"] = retrieved
    state["raw_milvus_hits"] = [h for h in all_hits if h["_tool"] == "semantic_search"]
    state["raw_kg_results"] = [h for h in all_hits if h["_tool"] == "kg_search"]
    state["raw_keyword_hits"] = [h for h in all_hits if h["_tool"] == "keyword_search"]
    state.setdefault("warnings", []).extend(warnings)
    return state
