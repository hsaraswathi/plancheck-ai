import ezdxf
import re
from shapely.geometry import Polygon
from langchain_core.tools import tool

def get_unit_scale(doc):
    insunits = doc.header.get('$INSUNITS', 1)
    scales = {0: 1.0, 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.0254, 6: 1.0, 7: 1e-6, 8: 1e-3, 13: 0.01}
    return scales.get(insunits, 1.0)

def extract_numeric(text):
    match = re.search(r"[-+]?\d*\.\d+|\d+", str(text))
    return float(match.group()) if match else None

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

def infer_building_height(all_texts, has_attic, is_residential):
    """Infer building height from DXF annotations when explicit height is missing."""
    floor_indicators = []
    for t in all_texts:
        try:
            raw = t.dxf.text if hasattr(t.dxf, 'text') else t.text
            if re.search(r'FLOOR\s*\d|LEVEL\s*\d|STORY\s*\d|2ND\s*FLOOR|SECOND\s*FLOOR|UPSTAIRS', raw, re.IGNORECASE):
                floor_indicators.append(raw)
        except:
            pass

    num_floors = max(len(floor_indicators), 1)
    if is_residential:
        floor_height = 3.0
        roof_height = 1.5 if has_attic else 0.5
        return round(num_floors * floor_height + roof_height, 2)
    else:
        floor_height = 3.5
        return round(num_floors * floor_height, 2)

def find_entities_for_layers(msp, layer_names, dxf_type=None):
    results = []
    for layer in layer_names:
        safe_layer = layer.replace('"', '').replace("'", "")
        if dxf_type:
            results.extend(msp.query(f'{dxf_type}[layer=="{safe_layer}"]'))
        else:
            results.extend(msp.query(f'*[layer=="{safe_layer}"]'))
    return results

def extract_all_dimensions(msp):
    dims = msp.query('DIMENSION')
    values = []
    for d in dims:
        try:
            if hasattr(d, 'measurement') and d.measurement:
                values.append(float(d.measurement))
        except Exception:
            pass
    return values

def extract_all_text(msp, layer_names=None):
    texts = []
    if layer_names:
        for layer in layer_names:
            safe = layer.replace('"', '').replace("'", "")
            texts.extend(msp.query(f'TEXT[layer=="{safe}"]'))
            texts.extend(msp.query(f'MTEXT[layer=="{safe}"]'))
    else:
        texts.extend(msp.query('TEXT'))
        texts.extend(msp.query('MTEXT'))
    return texts

@tool
def extract_dxf_geometry(file_path: str) -> dict:
    """
    Extracts geometric measurements and text labels from a DXF file.
    Returns a dictionary of raw data for compliance analysis.
    """
    try:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
        scale = get_unit_scale(doc)
        layer_names = [l.dxf.name for l in doc.layers]

        result = {}

        # 1. Geometry Extraction (Plot & Footprint)
        for key in ["PLOT", "FOOTPRINT"]:
            target_layers = [l for l in layer_names if key.upper() in l.upper()]
            if not target_layers:
                continue

            entities = find_entities_for_layers(msp, target_layers, dxf_type="LWPOLYLINE")
            if not entities:
                entities = find_entities_for_layers(msp, target_layers, dxf_type="POLYLINE")

            polys = []
            for ent in entities:
                try:
                    pts = [(p[0]*scale, p[1]*scale) for p in ent.get_points()]
                    if len(pts) > 2:
                        polys.append(Polygon(pts))
                except Exception:
                    continue

            if polys:
                main_poly = max(polys, key=lambda p: p.area)
                prefix = key.lower()
                result[f"{prefix}_area"] = round(main_poly.area, 2)
                result[f"{prefix}_width"] = round(main_poly.bounds[2] - main_poly.bounds[0], 2)
                result[f"{prefix}_depth"] = round(main_poly.bounds[3] - main_poly.bounds[1], 2)

        # 2. Overall dimensions from DIMENSION entities
        dim_values = extract_all_dimensions(msp)
        if dim_values:
            dim_values_scaled = [v * scale for v in dim_values]
            result["dimension_values"] = [round(v, 2) for v in dim_values_scaled]
            result["max_dimension"] = round(max(dim_values_scaled), 2)
            result["min_dimension"] = round(min(dim_values_scaled), 2)

        # 3. Smart Text Extraction
        text_queries = {
            "building_height": [r".*HEIGHT.*", r".*ELEVATION.*", r".*STORY.*"],
            "road_width": [r".*ROAD.*", r".*STREET.*", r".*R\.O\.W\..*"],
            "lift_data": [r".*LIFT.*", r".*ELEVATOR.*"],
            "fire_safety": [r".*FIRE.*", r".*SPRINKLER.*", r".*EXIT.*"],
            "parapet_height": [r".*PARAPET.*"],
            "parking": [r".*PARK.*", r".*GARAGE.*", r".*CAR.*"],
            "setback": [r".*SETBACK.*", r".*BUILDING LINE.*"],
        }

        all_texts = extract_all_text(msp)

        for key, patterns in text_queries.items():
            matched_values = []
            for t in all_texts:
                try:
                    raw_text = t.dxf.text if hasattr(t.dxf, 'text') else t.text
                    if any(re.search(p, raw_text, re.IGNORECASE) for p in patterns):
                        val = extract_numeric(raw_text)
                        if val:
                            matched_values.append(val)
                except Exception:
                    continue

            if key == "lift_data":
                result["lift_count"] = len(matched_values) if matched_values else None
                result["lift_dims"] = matched_values if matched_values else None
            elif key == "setback":
                result["setbacks"] = matched_values if matched_values else None
            elif key == "parking":
                result["parking_spots"] = sum(matched_values) if matched_values else None
            else:
                result[key] = max(matched_values) if matched_values else None

        # 4. Parse room dimensions from text like "13'8 x 14'"
        room_dimensions = []
        for t in all_texts:
            try:
                raw = t.dxf.text if hasattr(t.dxf, 'text') else t.text
                dims = parse_feet_inches(raw)
                room_dimensions.extend(dims)
            except:
                pass
        if room_dimensions:
            result["room_dimensions"] = room_dimensions
            total_room_area = sum(r["area_sqm"] for r in room_dimensions)
            result["total_room_area"] = round(total_room_area, 2)

        # 5. Infer building height if not explicitly provided
        has_attic = any(re.search(r'ATTIC', t.dxf.text if hasattr(t.dxf, 'text') else t.text, re.IGNORECASE) for t in all_texts)
        is_residential = any(re.search(r'BEDROOM|KITCHEN|GARAGE|BATH|LIVING', t.dxf.text if hasattr(t.dxf, 'text') else t.text, re.IGNORECASE) for t in all_texts)

        if result.get("building_height") is None:
            inferred_height = infer_building_height(all_texts, has_attic, is_residential)
            result["building_height"] = inferred_height
            result["building_height_inferred"] = True
            result["has_attic"] = has_attic
            result["building_type"] = "residential" if is_residential else "commercial"
        else:
            result["building_height_inferred"] = False

        # 6. Extract room labels and annotations for context
        room_texts = []
        for t in all_texts:
            try:
                raw_text = t.dxf.text if hasattr(t.dxf, 'text') else t.text
                if raw_text and not raw_text.startswith('%%'):
                    room_texts.append(raw_text.strip())
            except Exception:
                continue
        if room_texts:
            result["annotations"] = room_texts[:50]

        # 7. Attach units to each measurement
        result["units"] = {
            "footprint_area": "sqm",
            "footprint_width": "m",
            "footprint_depth": "m",
            "plot_area": "sqm",
            "plot_width": "m",
            "plot_depth": "m",
            "building_area": "sqm",
            "building_height": "m",
            "road_width": "m",
            "parapet_height": "m",
            "setbacks": "m",
            "parking_spots": "count",
            "fire_safety": "count",
            "lift_count": "count",
            "lift_dims": "m",
            "max_dimension": "m",
            "min_dimension": "m",
            "dimension_values": "m",
            "total_room_area": "sqm",
        }

        return result
    except Exception as e:
        return {"error": f"Failed to parse DXF: {str(e)}"}
