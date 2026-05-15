from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from src.tools.legal_tools import search_bye_laws
from langchain_core.messages import HumanMessage, ToolMessage

llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools([search_bye_laws])

COMPLIANCE_CATEGORIES = [
    "FAR FSI Floor Area Ratio Floor Space Index",
    "building setback building line",
    "height restriction maximum height",
    "minimum plot size road width",
    "parking requirements car parking",
    "parapet wall design height",
    "fire safety fire exit",
    "lift elevator requirement",
]

def researcher_node(state):
    print("--- [Researcher Agent] Searching Laws ---")
    city = state.get("city", "Bangalore")
    geometry = state.get("geometry_data", {})
    plot_area = (
        geometry.get("plot_area")
        or geometry.get("area")
        or geometry.get("building_area")
        or geometry.get("footprint_area")
        or geometry.get("total_room_area")
        or 0
    )
    building_height = geometry.get("building_height")
    road_width = geometry.get("road_width")

    tool_messages = []
    for category in COMPLIANCE_CATEGORIES:
        query = f"What are the {category} regulations for a {plot_area} sqm plot in {city}?"
        if building_height:
            query += f" Building height is {building_height}m."
        if road_width:
            query += f" Road width is {road_width}m."

        messages = list(state["messages"]) + [HumanMessage(content=query)]
        response = llm.invoke(messages)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = search_bye_laws.invoke({"query": tool_call['args']['query'], "city": city})
                tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call['id']))

    if not tool_messages:
        query = f"What are the building regulations for FAR, setback, height, parking, fire safety, lift, parapet, and road width for a {plot_area} sqm plot in {city}?"
        messages = list(state["messages"]) + [HumanMessage(content=query)]
        response = llm.invoke(messages)
        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = search_bye_laws.invoke({"query": tool_call['args']['query'], "city": city})
                tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call['id']))
        else:
            tool_messages.append(response)

    return {"messages": tool_messages}
