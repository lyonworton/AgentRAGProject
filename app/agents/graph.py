from langgraph.graph import StateGraph, END, START
from app.agents.state import AgentState
from app.agents.understander import understand_node
from app.agents.router import route_node
from app.agents.executor import executor_node
from app.agents.reflector import reflector_node
from app.agents.verifier import verifier_node
from app.agents.nodes import synthesize_node

# Placeholder memory node for Phase 1
async def memory_node(state: AgentState) -> AgentState:
    return state


async def should_continue(state: AgentState) -> str:
    if state["iteration"] >= state["max_iterations"]:
        return "synthesize"
    if state["quality_score"] >= 0.7:
        return "verify"
    if state.get("prev_score") and state["quality_score"] <= state["prev_score"]:
        return "verify"
    state["iteration"] += 1
    state["prev_score"] = state["quality_score"]
    return "route"


async def should_verify(state: AgentState) -> str:
    if state.get("need_supplement"):
        return "route"
    return "synthesize"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("understand", understand_node)
    graph.add_node("route", route_node)
    graph.add_node("execute", executor_node)
    graph.add_node("reflect", reflector_node)
    graph.add_node("verify", verifier_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("memory", memory_node)

    graph.add_edge(START, "understand")
    graph.add_edge("understand", "route")
    graph.add_edge("route", "execute")
    graph.add_edge("execute", "reflect")

    graph.add_conditional_edges("reflect", should_continue, {
        "route": "route",
        "verify": "verify",
        "synthesize": "synthesize",
    })

    graph.add_conditional_edges("verify", should_verify, {
        "route": "route",
        "synthesize": "synthesize",
    })

    graph.add_edge("synthesize", "memory")
    graph.add_edge("memory", END)

    return graph.compile()


_graph_instance = None

def get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
