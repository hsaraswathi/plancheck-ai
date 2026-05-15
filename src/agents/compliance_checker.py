import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage

llm = ChatOpenAI(model="gpt-4o", temperature=0)

CHECK_CATEGORIES = [
    "FAR/FSI",
    "Building Setback",
    "Height Restrictions",
    "Plot Size & Road Width",
    "Parking Requirements",
    "Parapet Wall Designs",
    "Fire Safety Regulations",
    "Lift Requirements",
]

def supervisor_node(state):
    geometry = state.get("geometry_data", {})
    units_map = geometry.get("units", {})

    available_checks = []
    missing_checks = []

    if geometry.get("plot_area") or geometry.get("building_area") or geometry.get("footprint_area") or geometry.get("total_room_area"):
        available_checks.append("FAR/FSI")
    else:
        missing_checks.append("FAR/FSI")

    if geometry.get("setbacks"):
        available_checks.append("Building Setback")
    else:
        missing_checks.append("Building Setback")

    if geometry.get("building_height"):
        available_checks.append("Height Restrictions")
    else:
        missing_checks.append("Height Restrictions")

    if geometry.get("plot_area") and geometry.get("road_width"):
        available_checks.append("Plot Size & Road Width")
    else:
        missing_checks.append("Plot Size & Road Width")

    if geometry.get("parking_spots") is not None:
        available_checks.append("Parking Requirements")
    else:
        missing_checks.append("Parking Requirements")

    if geometry.get("parapet_height") is not None:
        available_checks.append("Parapet Wall Designs")
    else:
        missing_checks.append("Parapet Wall Designs")

    if geometry.get("fire_safety") is not None:
        available_checks.append("Fire Safety Regulations")
    else:
        missing_checks.append("Fire Safety Regulations")

    if geometry.get("lift_count") is not None:
        available_checks.append("Lift Requirements")
    else:
        missing_checks.append("Lift Requirements")

    skip_note = ""
    if missing_checks:
        skip_note = f"\n\nSKIP the following checks (data not available in DXF): {', '.join(missing_checks)}"

    annotations = geometry.get("annotations", [])
    annotations_text = f"\n\nDXF Annotations/Labels: {annotations}" if annotations else ""

    sys_msg = SystemMessage(
        content=(
            f"You are a Building Inspector. Review the geometry data and research findings to determine compliance with city building codes.\n\n"
            f"DXF Geometry Data: {geometry}{annotations_text}\n\n"
            f"Perform compliance checks ONLY for: {', '.join(available_checks)}"
            f"{skip_note}\n\n"
            f"For each available check, compare the DXF measurements against the bye-law requirements.\n"
            f"Return a JSON object with the following structure:\n"
            f"{{\n"
            f'  "Category Name": {{\n'
            f'    "status": "compliant" or "non-compliant" or "skipped",\n'
            f'    "required": "Rule from bye-laws",\n'
            f'    "actual": "Value from DXF",\n'
            f'    "reason": "Explanation"\n'
            f"  }}\n"
            f"}}"
        )
    )

    raw_messages = state.get("messages", [])
    context_parts = []
    for m in raw_messages:
        if isinstance(m, ToolMessage):
            context_parts.append(f"[Bye-law Reference]\n{m.content}")
        elif hasattr(m, "content") and m.content:
            context_parts.append(str(m.content))

    context_text = "\n\n".join(context_parts)

    human_msg = HumanMessage(content=f"Here are the research findings:\n\n{context_text}\n\nNow perform the compliance checks and return ONLY valid JSON.")

    full_input = [sys_msg, human_msg]

    response = llm.invoke(full_input)
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        compliance_results = json.loads(content)
    except Exception:
        compliance_results = {"error": "Failed to parse compliance results"}

    return {"messages": [response], "compliance_results": compliance_results}
