# Plancheck.ai

**AI-Powered Building Plan Compliance Checker**

Plancheck.ai automates the compliance verification of architectural building plans against local municipal bye-laws. Upload a DXF or PDF floor plan, select the city, and the system extracts geometric data, researches applicable bye-laws, and generates a detailed compliance report using a multi-agent LangGraph workflow.

---

## Features

- **Multi-Format Plan Upload**: Supports `.dxf` (CAD) and `.pdf` building plans.
- **Geometric Extraction**: Automatically parses floor plans to extract measurements like area, setbacks, height, room dimensions, and parking counts.
- **City-Specific Bye-Laws**: Currently supports **Bangalore**, **Hyderabad**, and **Chennai**. The system retrieves and interprets relevant local building regulations from uploaded bye-law documents.
- **AI Compliance Engine**: Uses a LangGraph-powered multi-agent system to compare extracted plan data against legal requirements.
- **Visual Compliance Dashboard**: A Streamlit-based web UI with a clean, card-based layout showing extracted measurements and compliance status (Compliant / Non-Compliant / Skipped).
- **Report Download**: Export a full text-based compliance report for records.

---

## Architecture Overview

```
┌──────────────┐
│  Streamlit   │  <-- Web UI (app.py)
│    (UI)      │
└──────┬───────┘
       │ file_path, city
       ▼
┌──────────────────────────────┐
│         LangGraph            │  <-- Orchestration Layer (src/graph.py)
│                              │
│  ┌──────────┐   ┌──────────┐ │
│  │  DXF     │   │  PDF     │ │  <-- Parser Agents (src/agents/)
│  │ Parser   │   │ Parser   │ │
│  └────┬─────┘   └────┬─────┘ │
│       └──────┬───────┘       │
│              ▼                │
│  ┌──────────────────────┐   │
│  │ Bye-Laws Researcher  │   │  <-- Retrieves local regulations
│  └──────────┬───────────┘   │
│             ▼               │
│  ┌──────────────────────┐   │
│  │ Compliance Checker   │   │  <-- Compares plan vs. laws
│  └──────────────────────┘   │
└──────────────────────────────┘
              │
              ▼
       Compliance Report
```

### Key Components

| Component | Description |
|-----------|-------------|
| `app.py` | Streamlit frontend for file upload, city selection, and results display. |
| `src/graph.py` | Defines the LangGraph state machine that orchestrates the agent workflow. |
| `src/agents/` | Contains specialized agents: `dfx_parser`, `pdf_parser`, `bye_laws_reasercher`, and `compliance_checker`. |
| `src/tools/` | Utility modules for CAD parsing (`cad_tools.py`), PDF text extraction (`pdf_parser.py`), and legal reasoning (`legal_tools.py`). |
| `data/bye-laws/` | Municipal bye-law PDFs organized by city. |
| `data/raw_plans/` | Sample uploaded plans (DXF/PDF). |

---

## Tech Stack

- **Python 3.13+**
- **Streamlit** – Interactive web interface
- **LangGraph** – Agent workflow orchestration
- **LangChain** – LLM chaining and tool binding
- **OpenAI / HuggingFace** – LLM & embedding providers
- **ezdxf** – DXF file parsing
- **PyPDF** – PDF text and structure extraction
- **Sentence-Transformers** – Text embeddings for bye-law retrieval
- **Shapely** – Geometric calculations
- **ChromaDB** – Vector store for bye-law document retrieval

---

## Installation

### Prerequisites

- Python 3.13 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`

### 1. Clone the Repository

```bash
git clone https://github.com/hsaraswathi/plancheck-ai.git
cd plancheck-ai
```

### 2. Set up Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env  # if available, otherwise create manually
```

Add your API keys (e.g., OpenAI):

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

> **Note:** `.env` is already in `.gitignore` and will **not** be committed.

### 3. Install Dependencies

Using `uv`:

```bash
uv sync
```

Or using `pip` with the virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## Usage

### Run the Streamlit App

```bash
streamlit run app.py
```

Then open your browser at `http://localhost:8501`.

### Workflow

1. **Select City** – Choose Bangalore, Hyderabad, or Chennai.
2. **Upload Plan** – Drop a `.dxf` or `.pdf` building plan file.
3. **Run Check** – Click "Run Compliance Check".
4. **Review Results** – View extracted measurements and compliance cards per category.
5. **Download Report** – Save the full compliance report as a `.txt` file.

---

## Deployment

This app can be deployed on any platform that supports Python or Docker. Below are guides for the most common options.

### Prerequisites for all platforms

- Set your environment variables (e.g. `OPENAI_API_KEY`). **Never commit `.env` to Git.**
- If using ChromaDB locally, note that on most PaaS platforms the filesystem is ephemeral. The app will re-index bye-law PDFs on each cold start (which is fine for small datasets).

### Option A: Streamlit Community Cloud (Free & Easiest)

Best for quick demos. The repo is already public.

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **"New app"** → select the `hsaraswathi/plancheck-ai` repo and the `main` branch.
3. Set the **Main file path** to `app.py`.
4. In **Advanced settings**, add your secrets:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
5. Click **Deploy**.

> **Note:** Streamlit Cloud free tier has a 1 GB resource limit. Because this project installs `torch` and `sentence-transformers`, the build may exceed that limit. If it fails, use Option B or C.

### Option B: Render (Free Web Service)

Good balance of ease and flexibility.

1. Create a free account at [render.com](https://render.com).
2. From the dashboard, click **"New Web Service"** and connect your GitHub repo.
3. Use the following settings:
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
4. Add environment variables under the **Environment** tab:
   - `OPENAI_API_KEY` = `sk-...`
5. Click **Create Web Service**.

> Render free web services spin down after 15 minutes of inactivity (≈30 s cold start).

### Option C: Fly.io (Docker-based)

Best if you want a containerized deployment with a generous free allowance.

1. Install the [Fly.io CLI](https://fly.io/docs/flyctl/install/):
   ```bash
   brew install flyctl        # macOS
   # OR
   curl -L https://fly.io/install.sh | sh
   ```
2. Log in:
   ```bash
   fly auth login
   ```
3. Launch the app (from the repo root):
   ```bash
   fly launch --name plancheck-ai --dockerfile Dockerfile
   ```
   - Choose the region closest to you.
   - Select **"No"** for Postgres and **"No"** for Redis when prompted.
4. Set secrets:
   ```bash
   fly secrets set OPENAI_API_KEY=sk-...
   ```
5. Deploy:
   ```bash
   fly deploy
   ```

### Option D: Self-Hosted (VPS / EC2 / Droplet)

If you want full control.

1. Provision a server with **at least 2 GB RAM** (torch + sentence-transformers are memory-heavy).
2. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
3. Clone the repo and build:
   ```bash
   git clone https://github.com/hsaraswathi/plancheck-ai.git
   cd plancheck-ai
   docker build -t plancheck-ai .
   ```
4. Run:
   ```bash
   docker run -d -p 8501:8501 -e OPENAI_API_KEY=sk-... --name plancheck-ai plancheck-ai
   ```
5. Open `http://<server-ip>:8501`.

---

## Project Structure

```
plancheck-ai/
├── app.py                          # Streamlit entry point
├── main.py                         # Minimal CLI entry (for dev/testing)
├── pyproject.toml                  # Project metadata & dependencies
├── uv.lock                         # Locked dependency versions
├── .env                            # API keys & secrets (not committed)
├── .gitignore
├── data/
│   ├── bye-laws/                   # City-specific bye-law PDFs
│   │   ├── Bangalore/
│   │   ├── Hyderabad/
│   │   └── Chennai/
│   ├── raw_plans/                  # Uploaded/sample plans
│   └── plans/
├── src/
│   ├── graph.py                    # LangGraph workflow definition
│   ├── state.py                    # Shared state schema
│   ├── agents/
│   │   ├── dfx_parser.py           # DXF plan parser agent
│   │   ├── pdf_parser.py           # PDF plan parser agent
│   │   ├── bye_laws_reasercher.py  # Bye-law retrieval agent
│   │   └── compliance_checker.py   # Compliance evaluation agent
│   └── tools/
│       ├── cad_tools.py            # CAD geometric utilities
│       ├── pdf_parser.py           # PDF extraction utilities
│       └── legal_tools.py          # Legal reasoning utilities
└── README.md
```

---

## Compliance Categories Checked

The system evaluates plans against the following categories (where data is available):

- **FAR / FSI** (Floor Area Ratio / Floor Space Index)
- **Building Setback**
- **Height Restrictions**
- **Plot Size & Road Width**
- **Parking Requirements**
- **Parapet Wall Designs**
- **Fire Safety Regulations**
- **Lift Requirements**

> Categories may show as "Skipped" if the bye-law document or plan data does not contain sufficient information for that check.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM calls (GPT-4 / GPT-3.5). |
| `HUGGINGFACE_API_KEY` | No* | HuggingFace token for embedding models (if used). |

*Depends on the embedding provider configured in `src/graph.py` or `src/agents/`.

---

## Future Enhancements

- [ ] Add more Indian cities (Delhi, Mumbai, Pune, etc.)
- [ ] Auto-download bye-laws from municipal corporation portals
- [ ] 3D plan support (IFC / Revit)
- [ ] Multi-language bye-law support
- [ ] Role-based access for architects, planners, and officials
- [ ] Historical plan comparison and version tracking

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/xyz`).
3. Commit your changes (`git commit -m "Add feature xyz"`).
4. Push to the branch (`git push origin feature/xyz`).
5. Open a Pull Request.

---

## License

[MIT](LICENSE) – (Add a LICENSE file if you choose to use this.)

---

## Acknowledgments

- Built with [LangGraph](https://www.langchain.com/langgraph) and [LangChain](https://www.langchain.com/).
- UI powered by [Streamlit](https://streamlit.io/).
- CAD parsing via [ezdxf](https://ezdxf.mozman.at/).

---

> **Disclaimer:** Plancheck.ai is an AI-assisted tool. The compliance reports generated should be reviewed by a qualified architect or town planner before submission to municipal authorities. It does not replace professional legal or structural advice.
