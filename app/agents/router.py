import json
import structlog
from app.agents.state import AgentState
from app.agents.query_detector import detect_query_type
from app.core.llm_factory import get_llm
from app.tools import get_tool_registry

logger = structlog.get_logger()


def _apply_rules_baseline(
    tasks: list[dict],
    fallback_rules: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Apply fallback rules to guarantee minimum retrieval tools per intent.

    Returns {task_id: [tool_names]} where tool_names is always non-empty.
    This is the non-negotiable baseline — LLM can only ADD, never remove.
    """
    return {
        t["id"]: list(fallback_rules.get(t["intent"], ["semantic_search"]))
        for t in tasks
    }

ROUTE_PROMPT = """You are a retrieval routing specialist. For each subtask, a baseline of tools is already assigned based on intent. Your job is to suggest ADDITIONAL tools that could improve retrieval quality.

Available tools:
{tool_descriptions}

Routing guidelines:
- "fact" baseline includes semantic_search; consider adding kg_search for entity-heavy facts
- "relation" baseline includes kg_search; consider adding semantic_search for context
- "exact" baseline includes keyword_search; consider adding semantic_search for recall
- "comparison" baseline includes semantic_search + kg_search
- "reasoning" baseline includes all three tools
- Only suggest a tool when you are confident it adds value beyond the baseline

Sub-tasks:
{tasks_json}

Output JSON array of additional tool suggestions only (never repeat baseline tools):
[{{"task_id": "t1", "extra_tools": ["kg_search"]}}, ...]
"""

FALLBACK_RULES: dict[str, list[str]] = {
    "fact": ["semantic_search"],
    "relation": ["kg_search"],
    "exact": ["keyword_search"],
    "comparison": ["semantic_search", "kg_search"],
    "reasoning": ["semantic_search", "kg_search", "keyword_search"],
    "web": ["web_search"],
}



async def route_node(state: AgentState) -> AgentState:
    tasks = state.get("sub_tasks", [])
    if not tasks:
        state["routes"] = {}
        return state

    registry = get_tool_registry()

    # Layer 1: Rules baseline — guaranteed minimum tools per intent
    routes = _apply_rules_baseline(tasks, FALLBACK_RULES)

    # Layer 2: Use understander's pre-computed route_suggestions (merged understand+route)
    suggestions = state.get("route_suggestions", [])
    if suggestions:
        for s in suggestions:
            tid = s.get("task_id", "")
            if tid in routes:
                extras = [t for t in s.get("extra_tools", []) if t not in routes[tid]]
                routes[tid].extend(extras)
    else:
        # Fallback: LLM-only if understander failed to produce suggestions
        try:
            llm = get_llm()
            prompt = ROUTE_PROMPT.format(
                tool_descriptions=registry.tool_descriptions,
                tasks_json=json.dumps([
                    {"id": t["id"], "description": t["description"], "intent": t["intent"]}
                    for t in tasks
                ]),
            )
            suggestions = await llm.agenerate_structured(
                prompt,
                "You are a retrieval routing specialist.",
                output_schema={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "extra_tools": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["task_id", "extra_tools"],
                    },
                },
            )
            for s in suggestions:
                tid = s["task_id"]
                if tid in routes:
                    extras = [t for t in s["extra_tools"] if t not in routes[tid]]
                    routes[tid].extend(extras)
        except Exception:
            logger.warning("llm_enhancement_failed_using_rules_baseline", exc_info=True)

    # Query detector hint: exact-match queries always get keyword_search
    query_hint = detect_query_type(state.get("query", ""))
    if query_hint["query_type"] == "exact" and query_hint["confidence"] >= 0.7:
        for tid in routes:
            if "keyword_search" not in routes[tid]:
                routes[tid].append("keyword_search")
                logger.debug("query_detector_added_keyword_search",
                             task_id=tid, query=state["query"][:80])

    # Filter to only valid tool names
    valid = set(registry.tool_names)
    state["routes"] = {
        tid: [t for t in tools if t in valid]
        for tid, tools in routes.items()
    }
    return state