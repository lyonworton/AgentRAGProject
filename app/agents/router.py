import json
import structlog
from app.agents.state import AgentState
from app.adapters.llm.openai import OpenAILLM
from app.tools import get_tool_registry

logger = structlog.get_logger()

ROUTE_PROMPT = """You are a retrieval routing specialist. Based on each subtask's description and intent, decide which retrieval tools to use.

Available tools:
{tool_descriptions}

Routing guidelines:
- "fact" intent prioritizes semantic_search
- "relation" intent prioritizes kg_search
- "exact" intent prioritizes keyword_search
- "comparison" intent typically needs semantic_search + kg_search
- "reasoning" intent may need all three tools

Sub-tasks:
{tasks_json}

Output JSON array only:
[{{"task_id": "t1", "tools": ["semantic_search"]}}, ...]
"""

FALLBACK_RULES: dict[str, list[str]] = {
    "fact": ["semantic_search"],
    "relation": ["kg_search"],
    "exact": ["keyword_search"],
    "comparison": ["semantic_search", "kg_search"],
    "reasoning": ["semantic_search", "kg_search", "keyword_search"],
}

ROUTE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["task_id", "tools"],
    },
}


async def route_node(state: AgentState) -> AgentState:
    tasks = state.get("sub_tasks", [])
    if not tasks:
        state["routes"] = {}
        return state

    registry = get_tool_registry()
    prompt = ROUTE_PROMPT.format(
        tool_descriptions=registry.tool_descriptions,
        tasks_json=json.dumps([
            {"id": t["id"], "description": t["description"], "intent": t["intent"]}
            for t in tasks
        ]),
    )

    try:
        llm = OpenAILLM()
        result = await llm.agenerate_structured(
            prompt,
            "You are a retrieval routing specialist.",
            output_schema=ROUTE_SCHEMA,
        )
        routes = {r["task_id"]: r["tools"] for r in result}
    except Exception:
        logger.warning("llm_routing_failed_falling_back_to_rules", exc_info=True)
        routes = {
            t["id"]: FALLBACK_RULES.get(t["intent"], ["semantic_search"])
            for t in tasks
        }

    valid = set(registry.tool_names)
    state["routes"] = {
        tid: [t for t in tools if t in valid]
        for tid, tools in routes.items()
    }
    return state