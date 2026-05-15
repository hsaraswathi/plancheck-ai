from src.tools.pdf_parser import extract_pdf_measurements

def pdf_parser_node(state):
    """Agent node that calls the PDF parser tool."""
    print("--- [PDF Parser Agent] Extracting Measurements ---")
    data = extract_pdf_measurements.invoke(state["file_path"])
    return {"geometry_data": data}
