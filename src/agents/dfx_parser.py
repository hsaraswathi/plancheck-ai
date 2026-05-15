from src.tools.cad_tools import extract_dxf_geometry

def parser_node(state):
    print("--- [Parser Agent] Extracting Geometry ---")
    data = extract_dxf_geometry.invoke(state["file_path"])
    return {"geometry_data": data}