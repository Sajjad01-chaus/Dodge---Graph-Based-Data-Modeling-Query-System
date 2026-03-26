# Dodge FDE — Graph-Based Data Modeling & Query System

A production-grade system that ingests SAP Order-to-Cash (O2C) business data, constructs a graph of interconnected entities, visualizes it interactively, and provides a conversational LLM-powered query interface.

![Architecture](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square)
![Database](https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=flat-square)
![Graph](https://img.shields.io/badge/Graph-Neo4j-008CC1?style=flat-square)
![LLM](https://img.shields.io/badge/LLM-Groq-F55036?style=flat-square)
![Frontend](https://img.shields.io/badge/Frontend-Cytoscape.js-F7DF1E?style=flat-square)

---

## 🏗️ Architecture

```
                    ┌──────────────────────────────────┐
                    │         Frontend (HTML/JS)        │
                    │  ┌─────────────┐ ┌──────────────┐│
                    │  │ Cytoscape.js│ │  Chat Panel  ││
                    │  │   Graph     │ │  (NL Query)  ││
                    │  └──────┬──────┘ └──────┬───────┘│
                    └─────────┼───────────────┼────────┘
                              │               │
                    ┌─────────▼───────────────▼────────┐
                    │       FastAPI Backend             │
                    │  ┌──────────┐ ┌────────────────┐ │
                    │  │ Graph API│ │   Chat API     │ │
                    │  └────┬─────┘ └──────┬─────────┘ │
                    │       │              │           │
                    │  ┌────▼────┐  ┌──────▼─────────┐│
                    │  │  Neo4j  │  │  LLM Service   ││
                    │  │ Driver  │  │  (Groq API)    ││
                    │  └────┬────┘  │  + Guardrails  ││
                    │       │       └──────┬─────────┘│
                    │       │              │          │
                    │  ┌────▼────┐  ┌──────▼────┐    │
                    │  │ Neo4j   │  │PostgreSQL │    │
                    │  │(Graph)  │  │(Relational)│   │
                    │  └─────────┘  └───────────┘    │
                    └─────────────────────────────────┘
```

### Why This Architecture?

| Decision | Rationale |
|----------|-----------|
| **Neo4j** for graph | Native graph database with Cypher query language — optimized for relationship traversal, path tracing, and neighborhood exploration |
| **PostgreSQL** for relational data | Production-grade SQL database for complex aggregations, filtering, and the LLM's NL-to-SQL pipeline |
| **Dual storage** | Graph DB excels at relationship queries; SQL DB excels at analytical queries — using both gives the LLM flexibility |
| **Groq** as LLM | Free tier with fast inference (LPU), good enough for SQL generation |
| **FastAPI** | Async Python framework with auto-generated OpenAPI docs, fast to develop |
| **Cytoscape.js** | Mature graph visualization library with built-in layouts, expansion, and styling |

---

## 📊 Data Model

### Entity Graph

```
Customer ──PLACED_ORDER──▶ SalesOrder ──CONTAINS_ITEM──▶ OrderItem
                               │                              │
                               │                         USES_MATERIAL
                               │                              │
                         DELIVERED_VIA                    Material
                               │
                               ▼
                           Delivery ──SHIPPED_FROM──▶ Plant
                               │
                         BILLED_AS
                               │
                               ▼
                       BillingDocument
                               │
                     ┌─────────┴─────────┐
               JOURNALED_AS         PAID_VIA
                     │                   │
                     ▼                   ▼
              JournalEntry           Payment
```

---

## 🤖 LLM Prompting Strategy

### Two-Step Pipeline

1. **NL → SQL Generation**: User question + DB schema → Groq generates a SQL query
2. **Answer Synthesis**: SQL results → Groq produces a natural language answer with data references

### Key Design Decisions

- **Schema injection**: Full DB schema is included in the system prompt so the LLM knows exact column names and types
- **Few-shot examples**: Common query patterns are provided as examples
- **Self-healing**: If a generated SQL fails, the error is sent back to the LLM for a retry
- **Result limiting**: Large result sets are capped at 30 rows for LLM context efficiency

### Guardrails

1. **Pre-filter** (keyword matching): Regex patterns detect obviously off-topic queries (poems, weather, coding) before they reach the LLM
2. **LLM classification**: Ambiguous queries are classified as ALLOWED/BLOCKED by the LLM
3. **SQL validation**: Only SELECT/WITH statements are allowed — INSERT, UPDATE, DELETE, DROP are blocked
4. **Response sanitization**: LLM responses containing the GUARDRAIL_BLOCKED marker are replaced with a standard rejection message

---

## 🚀 Setup & Running

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Neo4j database (local or [Aura free tier](https://neo4j.com/cloud/aura-free/))
- Groq API key ([console.groq.com](https://console.groq.com))

### Installation

```bash
# Clone
git clone <repo-url>
cd Dodge_FDE_project

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
cd backend
pip install -r requirements.txt

# Configure environment
cp ../.env.example .env
# Edit .env with your database URLs and API keys
```

### Data Ingestion

1. Place the dataset files (CSV/Excel) in the `backend/data/` directory
2. Start the server and trigger ingestion:

```bash
cd backend
python main.py
# Then POST to http://localhost:8000/api/ingest
```

### Running

```bash
cd backend
python main.py
# Open http://localhost:8000 in your browser
```

---

## 📁 Project Structure

```
Dodge_FDE_project/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Environment configuration
│   ├── requirements.txt     # Python dependencies
│   ├── database/
│   │   ├── postgres.py      # PostgreSQL connection + schema
│   │   └── neo4j_db.py      # Neo4j driver + Cypher helpers
│   ├── services/
│   │   ├── data_ingestion.py # Dataset parsing and loading
│   │   ├── graph_service.py  # Graph operations
│   │   ├── llm_service.py    # Groq API + NL-to-SQL pipeline
│   │   ├── guardrails.py     # Domain restriction
│   │   └── prompts.py        # LLM prompt templates
│   ├── routers/
│   │   ├── graph_router.py   # Graph API endpoints
│   │   └── chat_router.py    # Chat API endpoint
│   └── models/
│       └── schemas.py        # Pydantic models
├── frontend/
│   ├── index.html            # Main UI
│   ├── styles.css            # Dark theme
│   ├── app.js                # App initialization
│   ├── graph.js              # Cytoscape.js visualization
│   └── chat.js               # Chat interface
├── README.md
├── .env.example
└── .gitignore
```

---

## 🧪 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/graph/overview` | Get graph data for visualization |
| `GET` | `/api/graph/node/{id}` | Node details |
| `GET` | `/api/graph/expand/{id}` | Expand node neighbors |
| `GET` | `/api/graph/search?q=` | Search nodes |
| `GET` | `/api/graph/flow/{type}/{id}` | Trace O2C flow |
| `GET` | `/api/graph/broken-flows` | Find broken flows |
| `GET` | `/api/graph/statistics` | Graph statistics |
| `POST` | `/api/chat` | Natural language query |
| `POST` | `/api/ingest` | Trigger data ingestion |
| `GET` | `/api/schema` | Database schema info |

---

## License

MIT
