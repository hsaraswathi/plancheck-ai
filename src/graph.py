from langgraph.graph import StateGraph, START, END
from src.state import AgentState
from src.agents.dfx_parser import parser_node as dxf_parser_node
from src.agents.pdf_parser import pdf_parser_node
from src.agents.bye_laws_reasercher import researcher_node
from src.agents.compliance_checker import supervisor_node

def route_parser(state):
    """Routes to the correct parser based on file type."""
    file_type = state.get("file_type", "dxf").lower()
    if file_type == "pdf":
        return "pdf_parser"
    return "dxf_parser"

def route_parser_node(state):
    """Node wrapper that returns empty dict (routing is handled by conditional edge)."""
    return {}

def route_parser_router(state):
    """Conditional edge function that returns the next node name."""
    file_type = state.get("file_type", "dxf").lower()
    if file_type == "pdf":
        return "pdf_parser"
    return "dxf_parser"

def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("dxf_parser", dxf_parser_node)
    builder.add_node("pdf_parser", pdf_parser_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("route_parser", route_parser_node)

    builder.add_edge(START, "route_parser")
    builder.add_conditional_edges("route_parser", route_parser_router, {
        "dxf_parser": "dxf_parser",
        "pdf_parser": "pdf_parser",
    })
    builder.add_edge("dxf_parser", "researcher")
    builder.add_edge("pdf_parser", "researcher")
    builder.add_edge("researcher", "supervisor")
    builder.add_edge("supervisor", END)

    return builder.compile()
