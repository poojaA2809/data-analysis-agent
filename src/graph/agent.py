from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    plan,
    generate_code,
    execute_code,
    observe,
    finalize,
    handle_error,
)
from graph.edges import route_after_observe


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", plan)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("observe", observe)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("plan")

    g.add_conditional_edges(
        "plan",
        lambda s: "handle_error" if s.get("error") else "generate_code",
        {"handle_error": "handle_error", "generate_code": "generate_code"},
    )
    g.add_conditional_edges(
        "generate_code",
        lambda s: "handle_error" if s.get("error") else "execute_code",
        {"handle_error": "handle_error", "execute_code": "execute_code"},
    )
    g.add_edge("execute_code", "observe")
    g.add_conditional_edges(
        "observe",
        route_after_observe,
        {"generate_code": "generate_code", "finalize": "finalize"},
    )
    g.add_conditional_edges(
        "finalize",
        lambda s: "handle_error" if s.get("error") else "end",
        {"handle_error": "handle_error", "end": END},
    )
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
