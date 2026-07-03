from config.settings import get_settings
from graph.state import AgentState


def route_after_observe(state: AgentState) -> str:
    """ok → finalize; needs-fix under budget → generate_code; else finalize."""
    if state.get("error"):
        return "finalize"  # fatal handled inside observe should route to handle_error
    verdict = state.get("critique_verdict", "ok")
    if verdict == "ok":
        return "finalize"
    if state.get("step_count", 0) >= get_settings().max_steps:
        return "finalize"
    return "generate_code"
