import re
import json
import base64
from pypdf import PdfReader
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool

llm = ChatOpenAI(model="gpt-4o", temperature=0)

def pdf_to_images(file_path: str, max_pages: int = 4) -> list:
    """Convert PDF pages to base64-encoded images using PyMuPDF."""
    try:
        import fitz
        doc = fitz.open(file_path)
        result = []
        for i in range(min(len(doc), max_pages)):
            page = doc[i]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            result.append(b64)
        doc.close()
        return result
    except Exception as e:
        print(f"DEBUG PDF: PyMuPDF conversion failed: {e}")
        return []

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts all text from a PDF file."""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def extract_all_text_from_images(images_b64: list) -> str:
    """Use GPT-4o-mini vision to extract ALL text labels from PDF page images."""
    try:
        llm_mini = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except Exception:
        return ""

    content = [
        {
            "type": "text",
            "text": (
                "Transcribe all text from this building plan. List every label, number, and measurement you see. "
                "Format: one item per line. Include area values, dimensions, room names, and all annotations."
            )
        }
    ]
    for b64 in images_b64[:4]:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}
        })

    try:
        response = llm_mini.invoke([{"role": "user", "content": content}])
        text = response.content
        refusal_phrases = ["unable to", "cannot process", "cannot read", "cannot transcribe", "cannot extract"]
        if any(phrase in text.lower() for phrase in refusal_phrases):
            return ""
        return text
    except Exception as e:
        print(f"DEBUG PDF: Vision text extraction failed: {e}")
        return ""

def extract_measurements_from_images(images_b64: list) -> dict:
    """Use GPT-4o vision to extract structured measurements from PDF page images."""
    content = [
        {
            "type": "text",
            "text": (
                "You are a Building Plan Analyst. Analyze these building plan images and extract ALL measurements.\n"
                "Return ONLY valid JSON with these keys (use null if not found):\n"
                "plot_area_sqm, plot_area_sqft, building_area_sqm, building_area_sqft, footprint_area_sqm, "
                "building_height_m, setbacks (object with front_m, rear_m, side1_m, side2_m), "
                "road_width_m, parking_spots, parapet_height_m, fire_safety, lift_count, "
                "room_dimensions (array of objects with name, width_m, depth_m, area_sqm), "
                "plot_width_m, plot_depth_m, building_type (residential/commercial)\n"
                "Convert ALL imperial units to metric. 1ft = 0.3048m, 1sqft = 0.092903sqm.\n"
                "IMPORTANT: Look for labels like 'HOUSE AREA: 1,136 sq ft', 'GARAGE AREA: 260 sq ft'. "
                "Extract the EXACT number shown. Do not estimate or calculate - read the value from the plan."
            )
        }
    ]
    for b64 in images_b64[:4]:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}
        })

    try:
        response = llm.invoke([{"role": "user", "content": content}])
        resp_content = response.content
        if "```json" in resp_content:
            resp_content = resp_content.split("```json")[1].split("```")[0]
        elif "```" in resp_content:
            resp_content = resp_content.split("```")[1].split("```")[0]
        return json.loads(resp_content)
    except Exception as e:
        print(f"DEBUG PDF: Vision extraction failed: {e}")
        return {}

def extract_area_from_images(images_b64: list) -> dict:
    """Dedicated pass to extract area values from PDF images."""
    try:
        llm_mini = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except Exception:
        return {}

    content = [
        {
            "type": "text",
            "text": (
                "Find ALL area values on this building plan. Return ONLY JSON with these keys:\n"
                "house_area_sqft, garage_area_sqft, building_area_sqft, plot_area_sqft, total_area_sqft, "
                "floor_area_sqft, footprint_area_sqft, glazing_area_sqft\n"
                "Use null for any not found. Read the exact numbers from the plan."
            )
        }
    ]
    for b64 in images_b64[:4]:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}
        })

    try:
        response = llm_mini.invoke([{"role": "user", "content": content}])
        resp_content = response.content
        if "```json" in resp_content:
            resp_content = resp_content.split("```json")[1].split("```")[0]
        elif "```" in resp_content:
            resp_content = resp_content.split("```")[1].split("```")[0]
        return json.loads(resp_content)
    except Exception as e:
        print(f"DEBUG PDF: Area vision extraction failed: {e}")
        return {}

def parse_feet_inches(text):
    """Extract dimensions from strings like \"13'8 x 14'\" or \"21'2 x 20'10\"."""
    pattern = r"(\d+)'(\d+)\s*x\s*(\d+)'(\d+)"
    matches = re.findall(pattern, text)
    results = []
    for m in matches:
        w_ft, w_in, d_ft, d_in = int(m[0]), int(m[1]), int(m[2]), int(m[3])
        width_m = (w_ft + w_in/12) * 0.3048
        depth_m = (d_ft + d_in/12) * 0.3048
        results.append({"width_ft": f"{w_ft}'{w_in}\"", "depth_ft": f"{d_ft}'{d_in}\"", "width_m": round(width_m, 2), "depth_m": round(depth_m, 2), "area_sqm": round(width_m * depth_m, 2)})
    return results

def infer_building_height(text, is_residential):
    """Infer building height from PDF text when explicit height is missing."""
    floor_patterns = [r'floor\s*\d', r'level\s*\d', r'story\s*\d', r'2nd\s*floor', r'second\s*floor', r'upstairs', r'ground\s*floor']
    num_floors = max(len([m for m in floor_patterns if re.search(m, text, re.IGNORECASE)]), 1)
    has_attic = bool(re.search(r'attic', text, re.IGNORECASE))
    if is_residential:
        floor_height = 3.0
        roof_height = 1.5 if has_attic else 0.5
        return round(num_floors * floor_height + roof_height, 2), has_attic
    else:
        floor_height = 3.5
        return round(num_floors * floor_height, 2), False

@tool
def extract_pdf_measurements(file_path: str) -> dict:
    """
    Extracts building measurements from a PDF building plan.
    Returns a dictionary of measurements for compliance analysis.
    """
    text = extract_text_from_pdf(file_path)
    if text.startswith("Error"):
        return {"error": text}

    result = {}

    # Vision-based extraction for image/scanned PDFs
    images_b64 = pdf_to_images(file_path)
    if images_b64:
        print(f"DEBUG PDF: Converted {len(images_b64)} pages to images for vision extraction")

        # Pass 1: Extract ALL text labels from images
        vision_text = extract_all_text_from_images(images_b64)
        if vision_text:
            print(f"DEBUG PDF: Vision text extracted ({len(vision_text)} chars)")
            print(f"DEBUG PDF: Vision text preview:\n{vision_text[:500]}")
            text += "\n" + vision_text

        # Pass 2: Extract structured measurements from images
        vision_data = extract_measurements_from_images(images_b64)
        if vision_data:
            print(f"DEBUG PDF: Vision structured data: {json.dumps(vision_data, indent=2)}")
            key_map = {
                "plot_area_sqm": "plot_area",
                "plot_area_sqft": None,
                "building_area_sqm": "building_area",
                "building_area_sqft": None,
                "footprint_area_sqm": "footprint_area",
                "building_height_m": "building_height",
                "road_width_m": "road_width",
                "parking_spots": "parking_spots",
                "parapet_height_m": "parapet_height",
                "plot_width_m": "plot_width",
                "plot_depth_m": "plot_depth",
            }
            for vk, rk in key_map.items():
                if rk and vision_data.get(vk) is not None and rk not in result:
                    result[rk] = vision_data[vk]

            if vision_data.get("setbacks") and isinstance(vision_data["setbacks"], dict):
                setbacks = {}
                for sk, sv in vision_data["setbacks"].items():
                    if sv is not None:
                        setbacks[sk] = sv
                if setbacks and "setbacks" not in result:
                    result["setbacks"] = setbacks

            if vision_data.get("room_dimensions") and "room_dimensions" not in result:
                result["room_dimensions"] = vision_data["room_dimensions"]
                result["total_room_area"] = round(sum(r.get("area_sqm", 0) for r in vision_data["room_dimensions"]), 2)

            if vision_data.get("building_type"):
                result["building_type"] = vision_data["building_type"]

        # Pass 3: Dedicated area extraction
        area_data = extract_area_from_images(images_b64)
        if area_data:
            print(f"DEBUG PDF: Area extraction data: {json.dumps(area_data, indent=2)}")
            area_key_map = {
                "house_area_sqft": ("building_area", "sqft"),
                "garage_area_sqft": ("garage_area", "sqft"),
                "building_area_sqft": ("building_area", "sqft"),
                "plot_area_sqft": ("plot_area", "sqft"),
                "total_area_sqft": ("plot_area", "sqft"),
                "floor_area_sqft": ("building_area", "sqft"),
                "footprint_area_sqft": ("footprint_area", "sqft"),
                "glazing_area_sqft": ("glazing_area", "sqft"),
            }
            for ak, (rk, unit) in area_key_map.items():
                val = area_data.get(ak)
                if val is not None and rk not in result:
                    if unit == "sqft":
                        val = round(val * 0.092903, 2)
                    result[rk] = val

    # Regex-based text extraction (works on both PDF text and vision-extracted text)
    # 1. Parse room dimensions from text like "13'8 x 14'"
    room_dimensions = parse_feet_inches(text)
    if room_dimensions and "room_dimensions" not in result:
        result["room_dimensions"] = room_dimensions
        result["total_room_area"] = round(sum(r["area_sqm"] for r in room_dimensions), 2)

    # 2. Extract area values - comprehensive patterns for image-extracted text
    area_patterns = [
        (r'(?:house|building)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sq\s*ft|sqft|ft2|ft²)', 'building', 'sqft'),
        (r'(?:house|building)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sqm|sq\.?\s*m|square\s*metre|square\s*meter|m2|m²)', 'building', 'sqm'),
        (r'(?:garage|car\s*port)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sq\s*ft|sqft|ft2|ft²)', 'garage', 'sqft'),
        (r'(?:garage|car\s*port)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sqm|sq\.?\s*m|square\s*metre|square\s*meter|m2|m²)', 'garage', 'sqm'),
        (r'(?:plot|site|lot)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sqm|sq\.?\s*m|square\s*metre|square\s*meter|m2|m²)', 'plot', 'sqm'),
        (r'(?:plot|site|lot)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sq\s*ft|sqft|ft2|ft²)', 'plot', 'sqft'),
        (r'(?:built[\s-]*up|floor)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sqm|sq\.?\s*m|square\s*metre|square\s*meter|m2|m²)', 'building', 'sqm'),
        (r'(?:built[\s-]*up|floor)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sq\s*ft|sqft|ft2|ft²)', 'building', 'sqft'),
        (r'(?:footprint)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sqm|sq\.?\s*m|square\s*metre|square\s*meter|m2|m²)', 'footprint', 'sqm'),
        (r'(?:footprint)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sq\s*ft|sqft|ft2|ft²)', 'footprint', 'sqft'),
        (r'(?:total)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sqm|sq\.?\s*m|square\s*metre|square\s*meter|m2|m²)', 'plot', 'sqm'),
        (r'(?:total)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sq\s*ft|sqft|ft2|ft²)', 'plot', 'sqft'),
        (r'(?:glazing)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sq\s*ft|sqft|ft2|ft²)', 'glazing', 'sqft'),
        (r'(?:glazing)\s*area[:\s]*([\d,]+\.?\d*)\s*(?:sqm|sq\.?\s*m|square\s*metre|square\s*meter|m2|m²)', 'glazing', 'sqm'),
        (r'([\d,]+\.?\d*)\s*(?:sqm|sq\.?\s*m|square\s*metre|square\s*meter|m2|m²)', 'plot', 'sqm'),
        (r'([\d,]+\.?\d*)\s*(?:sq\s*ft|sqft|ft2|ft²)', 'plot', 'sqft'),
    ]
    for pattern, area_type, unit in area_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(',', ''))
            if unit == 'sqft':
                val = val * 0.092903
            if area_type == 'plot' and 'plot_area' not in result:
                result["plot_area"] = round(val, 2)
            elif area_type == 'building' and 'building_area' not in result:
                result["building_area"] = round(val, 2)
            elif area_type == 'footprint' and 'footprint_area' not in result:
                result["footprint_area"] = round(val, 2)
            elif area_type == 'garage' and 'garage_area' not in result:
                result["garage_area"] = round(val, 2)
            elif area_type == 'glazing' and 'glazing_area' not in result:
                result["glazing_area"] = round(val, 2)

    # 3. Extract plot dimensions like "30'x40'" or "30 x 40" (feet)
    plot_dim_patterns = [
        r"(\d+)'?\s*x\s*(\d+)'?\s*(?:site|plot|lot)",
        r"(?:site|plot|lot)\s*(?:size|dimension)?[:\s]*(\d+)'?\s*x\s*(\d+)'?",
        r"(\d+)\s*['ft]+\s*x\s*(\d+)\s*['ft]+",
        r"(\d+)\s*x\s*(\d+)\s*(?:site|plot|lot)",
        r"(?:site|plot|lot)\s*(?:size|dimension)?[:\s]*(\d+)\s*x\s*(\d+)",
    ]
    for pattern in plot_dim_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            width_ft = float(match.group(1))
            depth_ft = float(match.group(2))
            width_m = round(width_ft * 0.3048, 2)
            depth_m = round(depth_ft * 0.3048, 2)
            plot_area_sqm = round(width_m * depth_m, 2)
            if "plot_area" not in result:
                result["plot_area"] = plot_area_sqm
            result["plot_width"] = width_m
            result["plot_depth"] = depth_m
            result["plot_dimensions_ft"] = f"{width_ft}'x{depth_ft}'"
            break

    # 4. Extract height values
    height_patterns = [
        r'building\s*height[:\s]*([\d.]+)\s*(m|metre|meter)',
        r'height[:\s]*([\d.]+)\s*(m|metre|meter)',
        r'elevation[:\s]*([\d.]+)\s*(m|metre|meter)',
        r'story\s*height[:\s]*([\d.]+)\s*(m|metre|meter)',
    ]
    for pattern in height_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["building_height"] = float(match.group(1))
            result["building_height_inferred"] = False
            break

    # 5. Extract setback values
    setback_patterns = [
        r'front\s*setback[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'rear\s*setback[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'side\s*1\s*setback[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'side\s*2\s*setback[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'side\s*setback[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'setback[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'building\s*line[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
    ]
    setbacks = {}
    for pattern in setback_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            unit = match.group(2).lower()
            if 'ft' in unit or 'feet' in unit:
                val *= 0.3048
            if 'front' in pattern:
                setbacks['front'] = round(val, 2)
            elif 'rear' in pattern:
                setbacks['rear'] = round(val, 2)
            elif 'side' in pattern:
                if 'side 1' in pattern or 'side 2' in pattern:
                    side_key = 'side_1' if 'side 1' in pattern else 'side_2'
                    setbacks[side_key] = round(val, 2)
                else:
                    setbacks.setdefault('side', []).append(round(val, 2))
            else:
                setbacks.setdefault('general', []).append(round(val, 2))
    if setbacks and "setbacks" not in result:
        result["setbacks"] = setbacks

    # 6. Extract road width
    road_patterns = [
        r"(\d+)'\s*\(([\d.]+)\s*(?:m|mts|metre|meter)\)\s*(?:wide\s*)?road",
        r'road\s*width[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'street\s*width[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'r\.?o\.?w\.?[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'right\s*of\s*way[:\s]*([\d.]+)\s*(m|metre|meter|mts|ft|feet)',
        r'([\d.]+)\s*(?:m|mts|metre|meter)\s*(?:wide\s*)?road',
        r'road\s*of\s*([\d.]+)\s*(?:m|mts|metre|meter)',
    ]
    for pattern in road_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if match.lastindex and match.lastindex >= 2 and "'" in pattern:
                val = float(match.group(2))
            else:
                val = float(match.group(1))
                unit = match.group(2) if match.lastindex and match.lastindex >= 2 else 'm'
                if isinstance(unit, str) and ('ft' in unit.lower() or 'feet' in unit.lower()):
                    val *= 0.3048
            result["road_width"] = round(val, 2)
            break

    # 7. Extract parking
    parking_patterns = [
        r'parking\s*spots?[:\s]*(\d+)',
        r'car\s*parks?[:\s]*(\d+)',
        r'parking\s*spaces?[:\s]*(\d+)',
        r'(\d+)\s*car\s*garage',
        r'garage\s*for\s*(\d+)\s*cars',
    ]
    for pattern in parking_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["parking_spots"] = int(match.group(1))
            break

    # 7b. Infer parking spots from garage area/dimensions if not explicitly stated
    if "parking_spots" not in result:
        garage_area_sqm = result.get("garage_area")
        if garage_area_sqm and garage_area_sqm > 0:
            single_car_sqm = 18
            result["parking_spots"] = max(1, round(garage_area_sqm / single_car_sqm))
        elif re.search(r'\bgarage\b', text, re.IGNORECASE):
            result["parking_spots"] = 1

    # 8. Extract parapet height
    parapet_patterns = [
        r'parapet\s*height[:\s]*([\d.]+)\s*(m|metre|meter|ft|feet)',
        r'parapet[:\s]*([\d.]+)\s*(m|metre|meter|ft|feet)',
    ]
    for pattern in parapet_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            unit = match.group(2).lower()
            if 'ft' in unit or 'feet' in unit:
                val *= 0.3048
            result["parapet_height"] = round(val, 2)
            break

    # 9. Extract fire safety
    fire_patterns = [
        r'fire\s*exits?[:\s]*(\d+)',
        r'fire\s*stair(?:s)?[:\s]*(\d+)',
        r'sprinkler\s*system[:\s]*(yes|no|provided|not\s*provided)',
    ]
    for pattern in fire_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1)
            if val.isdigit():
                result["fire_safety"] = int(val)
            else:
                result["fire_safety"] = 1 if val.lower() in ['yes', 'provided'] else 0
            break

    # 10. Extract lift
    lift_patterns = [
        r'lifts?[:\s]*(\d+)',
        r'elevators?[:\s]*(\d+)',
        r'(\d+)\s*lift',
        r'(\d+)\s*elevator',
    ]
    for pattern in lift_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["lift_count"] = int(match.group(1))
            break

    # 11. Infer building height if not explicitly provided
    is_residential = bool(re.search(r'bedroom|kitchen|garage|bath|living|residential|house|apartment', text, re.IGNORECASE))
    if "building_height" not in result:
        inferred_height, has_attic = infer_building_height(text, is_residential)
        result["building_height"] = inferred_height
        result["building_height_inferred"] = True
        result["has_attic"] = has_attic
    else:
        result["building_height_inferred"] = False

    result["building_type"] = "residential" if is_residential else "commercial"

    # 12. Fallback: If no area found but we have room dimensions, use total_room_area as building_area
    if not any(k in result for k in ["plot_area", "building_area", "footprint_area"]):
        if result.get("total_room_area"):
            result["building_area"] = result["total_room_area"]

    # 13. Attach units
    result["units"] = {
        "footprint_area": "sqm",
        "footprint_width": "m",
        "footprint_depth": "m",
        "plot_area": "sqm",
        "plot_width": "m",
        "plot_depth": "m",
        "building_area": "sqm",
        "garage_area": "sqm",
        "glazing_area": "sqm",
        "building_height": "m",
        "road_width": "m",
        "parapet_height": "m",
        "setbacks": "m",
        "parking_spots": "count",
        "fire_safety": "count",
        "lift_count": "count",
        "lift_dims": "m",
        "total_room_area": "sqm",
    }

    # 14. Extract annotations
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    result["annotations"] = lines[:50]

    return result
