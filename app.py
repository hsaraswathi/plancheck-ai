import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import streamlit as st
import streamlit.components.v1 as components

# Environment Setup
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path, override=True)
else:
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path, override=True)

from src.graph import build_graph

st.set_page_config(page_title="Plancheck.ai", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: #0a0a0f; }
    
    .main-header {
        text-align: center;
        padding: 3rem 0 1rem 0;
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 50%, #7c3aed 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0;
    }
    
    .subtitle {
        text-align: center;
        color: #a78bfa;
        font-size: 1.1rem;
        margin-top: 0;
        margin-bottom: 3rem;
    }

    /* File Uploader Container */
    [data-testid="stFileUploader"] {
        background: rgba(124, 58, 237, 0.05);
        border: 2px solid rgba(124, 58, 237, 0.3);
        border-radius: 20px;
        padding: 20px;
    }

    [data-testid="stFileUploader"] section {
        flex-direction: column !important;
        align-items: center !important;
        background: transparent !important;
        border: none !important;
    }

    [data-testid="stFileUploader"] label { display: none !important; }
    
    /* Buttons */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
        color: white !important;
        border-radius: 12px;
        padding: 0.8rem 2rem;
        font-weight: 600;
        margin-top: 1.5rem;
        border: none;
        width: 100%;
        transition: all 0.3s ease;
    }

    .stButton>button:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(124, 58, 237, 0.4);
    }

    @keyframes pulse-purple { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
    .stButton>button:disabled {
        background: #4c1d95 !important;
        animation: pulse-purple 2s infinite ease-in-out;
    }

    /* Measurements */
    .measurement-card {
        background: rgba(124, 58, 237, 0.1);
        border: 1px solid rgba(124, 58, 237, 0.2);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    /* Compliance Cards */
    .category-card {
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.5rem 0;
        height: 100%;
        backdrop-filter: blur(10px);
    }
    
    .compliant { 
        background: rgba(16, 185, 129, 0.15); 
        border: 1px solid rgba(16, 185, 129, 0.4); 
        border-left: 6px solid #10b981; 
    }
    .non-compliant { 
        background: rgba(239, 68, 68, 0.15); 
        border: 1px solid rgba(239, 68, 68, 0.4); 
        border-left: 6px solid #ef4444; 
    }
    .skipped { 
        background: rgba(124, 58, 237, 0.1); 
        border: 1px solid rgba(124, 58, 237, 0.3); 
        border-left: 6px solid #7c3aed; 
    }

    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 800;
        margin-bottom: 0.8rem;
        text-transform: uppercase;
    }
    .badge-compliant { background: #10b981; color: white; }
    .badge-non-compliant { background: #ef4444; color: white; }
    .badge-skipped { background: #7c3aed; color: white; }

    h1, h2, h3 { color: #e2e8f0 !important; }
    .divider { height: 1px; background: rgba(124, 58, 237, 0.3); margin: 2.5rem 0; }
</style>
""", unsafe_allow_html=True)

# Constants
COMPLIANCE_CATEGORIES = [
    "FAR/FSI", "Building Setback", "Height Restrictions", 
    "Plot Size & Road Width", "Parking Requirements", 
    "Parapet Wall Designs", "Fire Safety Regulations", "Lift Requirements"
]

def format_with_unit(key, val, units_map):
    if val is None: return "N/A"
    unit = units_map.get(key, "")
    return f"{val} {unit}" if unit and unit != "count" else str(val)

if 'processing' not in st.session_state:
    st.session_state.processing = False

# --- HEADER ---
st.markdown('<h1 class="main-header">Plancheck.ai</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">AI-Powered Building Plan Compliance Checker</p>', unsafe_allow_html=True)

# --- UPLOAD AREA ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    city = st.selectbox("Select City", ["Bangalore", "Hyderabad", "Chennai"], disabled=st.session_state.processing)
    uploaded_file = st.file_uploader("Upload Plan", type=['dxf', 'pdf'], disabled=st.session_state.processing, label_visibility="collapsed")
    
    btn_label = "🔄 Processing your building plan..." if st.session_state.processing else "🚀 Run Compliance Check"
    if st.button(btn_label, use_container_width=True, disabled=st.session_state.processing or not uploaded_file):
        st.session_state.processing = True
        st.rerun()

# --- PROCESSING LOGIC ---
if st.session_state.processing and uploaded_file:
    ext = uploaded_file.name.split('.')[-1].lower()
    path = f"data/raw_plans/{uploaded_file.name}"
    os.makedirs("data/raw_plans", exist_ok=True)
    with open(path, "wb") as f: f.write(uploaded_file.getbuffer())
    
    graph = build_graph()
    st.session_state.result = graph.invoke({
        "file_path": path, 
        "file_type": "pdf" if ext == "pdf" else "dxf", 
        "city": city, 
        "messages": []
    })
    st.session_state.processing = False
    st.rerun()

# --- RESULTS SECTION ---
if 'result' in st.session_state:
    res = st.session_state.result
    geom = res.get("geometry_data", {})
    comp = res.get("compliance_results", {})
    units = geom.get("units", {})

    # Invisible anchor for auto-scroll
    st.markdown('<div id="results-section"></div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # Centered Results Header
    st.markdown(f"<h2 style='text-align: center; margin-bottom: 2rem;'>Results for {city}</h2>", unsafe_allow_html=True)

    # 📐 Measurements Grid
    st.markdown("### 📐 Extracted Measurements")
    m_cols = st.columns(3)
    idx = 0
    report_text = f"COMPLIANCE REPORT: {city}\n" + "="*30 + "\n\nMEASUREMENTS:\n"
    
    for k, v in geom.items():
        if k in ("annotations", "units", "building_height_inferred", "has_attic", "building_type", "room_dimensions"): continue
        val_str = format_with_unit(k, v, units)
        report_text += f"- {k.replace('_', ' ').title()}: {val_str}\n"
        with m_cols[idx % 3]:
            st.markdown(f"""
                <div class="measurement-card">
                    <div style="color: #a78bfa; font-size: 0.8rem; text-transform: uppercase;">{k.replace('_', ' ')}</div>
                    <div style="font-size: 1.4rem; font-weight: 700; color: white;">{val_str}</div>
                </div>
            """, unsafe_allow_html=True)
        idx += 1

    # ✅ Compliance Report Cards
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("### ✅ Compliance Report")
    report_text += "\nCOMPLIANCE CHECK:\n"
    
    for row_idx in range(0, len(COMPLIANCE_CATEGORIES), 2):
        c_cols = st.columns(2)
        for i in range(2):
            if row_idx + i < len(COMPLIANCE_CATEGORIES):
                cat = COMPLIANCE_CATEGORIES[row_idx + i]
                data = comp.get(cat, {})
                status = data.get("status", "unknown").lower()
                
                if status == "compliant": s_class, b_class, icon = "compliant", "badge-compliant", "✅"
                elif status == "non-compliant": s_class, b_class, icon = "non-compliant", "badge-non-compliant", "❌"
                else: s_class, b_class, icon = "skipped", "badge-skipped", "⚠️"
                
                report_text += f"[{status.upper()}] {cat}\n  Required: {data.get('required')}\n  Actual: {data.get('actual')}\n  Reason: {data.get('reason')}\n\n"
                
                with c_cols[i]:
                    st.markdown(f"""<div class="category-card {s_class}">
                        <span class="status-badge {b_class}">{icon} {status.upper()}</span>
                        <div style="font-weight: 600; color: white; font-size: 1.1rem; margin-bottom: 5px;">{cat}</div>
                        <div style="font-size: 0.9rem; color: #e2e8f0;"><strong>Req:</strong> {data.get('required', 'N/A')} | <strong>Act:</strong> {data.get('actual', 'N/A')}</div>
                        <div style="font-size: 0.8rem; color: #cbd5e1; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px;">{data.get('reason', '')}</div>
                    </div>""", unsafe_allow_html=True)

    # 📂 Download Action
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.download_button(
        label="📂 Download Full Compliance Report (.txt)",
        data=report_text,
        file_name=f"Report_{city}_{uploaded_file.name}.txt",
        mime="text/plain",
        use_container_width=True
    )

    # Trigger Auto-Scroll to Results
    components.html(
        """
        <script>
            window.parent.document.getElementById('results-section').scrollIntoView({behavior: 'smooth'});
        </script>
        """,
        height=0,
    )