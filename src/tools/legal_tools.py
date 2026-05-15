import os
from pathlib import Path
from pypdf import PdfReader
from langchain_core.tools import tool

BYE_LAWS_BASE_DIR = Path(__file__).parent.parent.parent / "data" / "bye-laws"

def _get_city_dir(city: str) -> Path | None:
    """Returns the bye-laws directory for the given city, or None if not found."""
    base = BYE_LAWS_BASE_DIR
    for variant in (city, city.title(), city.lower(), city.upper()):
        candidate = base / variant
        if candidate.exists():
            return candidate
    return None

def _extract_all_text(city: str) -> list[dict]:
    """Reads all PDFs from data/bye-laws/<city>/ and returns list of {filename, page, content}."""
    results = []
    city_dir = _get_city_dir(city)
    if not city_dir:
        return results
    for pdf_path in city_dir.glob("*.pdf"):
        try:
            reader = PdfReader(str(pdf_path))
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text and text.strip():
                    results.append({
                        "filename": pdf_path.name,
                        "page": page_num,
                        "content": text.strip(),
                    })
        except Exception as e:
            print(f"[ByeLaws] Error reading {pdf_path.name}: {e}")
    return results

@tool
def search_bye_laws(query: str, city: str) -> str:
    """Searches building regulations from PDF bye-laws in data/bye-laws/<city>/."""
    docs = _extract_all_text(city)
    if not docs:
        city_dir = _get_city_dir(city)
        return f"No bye-law PDFs found for {city} in {city_dir or BYE_LAWS_BASE_DIR / city}."

    query_lower = query.lower()

    relevant = []
    for doc in docs:
        content_lower = doc["content"].lower()
        if any(kw in content_lower for kw in query_lower.split()):
            relevant.append(
                f"[{doc['filename']} (p.{doc['page']})]\n{doc['content']}"
            )

    return "\n\n---\n\n".join(relevant[:5]) if relevant else f"No matching bye-laws found for {city}."
