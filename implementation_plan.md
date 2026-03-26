# Graph-Based Data Modeling & Query System — Implementation Plan (v2)

## Overview

Build a production-level system that ingests business transaction data, stores it in **PostgreSQL** (relational) and **Neo4j** (graph), visualizes entity relationships via **Cytoscape.js**, and provides an LLM-powered conversational query interface using **Groq**.

> [!IMPORTANT]
> **Deadline**: March 26, 11:59 PM IST. Speed of execution is evaluated.

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend** | Python + FastAPI | Async, auto-docs, production-ready |
| **Relational DB** | PostgreSQL | Robust, production-grade, complex SQL support |
| **Graph DB** | Neo4j (Aura Free Tier) | Native graph storage, Cypher queries, relationship-first design |
| **Graph Visualization** | Cytoscape.js | Interactive expand/collapse, node inspection |
| **Frontend** | HTML/CSS/JS | Simple, no build step, fast iteration |
| **LLM Provider** | Groq (free tier) | Fast inference, free, good quality |
| **Deployment** | Railway / Render | Free tier, GitHub deploy |

---

## Project Structure

```
Dodge_FDE_project/
├── backend/
│   ├── main.py                  # FastAPI entry point, CORS, startup
│   ├── config.py                # Environment config (DB URLs, API keys)
│   ├── requirements.txt         # Python dependencies
│   ├── database/
│   │   ├── postgres.py          # PostgreSQL connection + schema
│   │   ├── neo4j_db.py          # Neo4j driver + Cypher helpers
│   │   └── schema.sql           # PostgreSQL schema definition
│   ├── services/
│   │   ├── data_ingestion.py    # CSV/Excel parsing → PG + Neo4j
│   │   ├── graph_service.py     # Graph operations (Neo4j Cypher)
│   │   ├── llm_service.py       # Groq API + NL-to-SQL/Cypher
│   │   ├── guardrails.py        # Domain restriction + validation
│   │   └── prompts.py           # LLM prompt templates
│   ├── routers/
│   │   ├── graph_router.py      # /api/graph/* endpoints
│   │   └── chat_router.py       # /api/chat endpoint
│   ├── models/
│   │   └── schemas.py           # Pydantic models
│   └── data/                    # Raw dataset files
├── frontend/
│   ├── index.html               # Split-pane: graph + chat
│   ├── styles.css               # Dark theme, modern UI
│   ├── app.js                   # App init, API layer
│   ├── graph.js                 # Cytoscape.js rendering
│   └── chat.js                  # Chat interface
├── README.md
├── .env.example                 # Environment variable template
└── .gitignore
```

---

## Core Functionality

### 1. Data Ingestion & Storage
- Parse dataset with `pandas`
- Load into **PostgreSQL** tables: `customers`, `sales_orders`, `order_items`, `deliveries`, `invoices`, `payments`, `products`, `addresses`
- Simultaneously create **Neo4j** nodes + relationships via Cypher `MERGE` statements
- Foreign keys in PG, relationship edges in Neo4j

### 2. Graph Construction (Neo4j)
- **Nodes**: Customer, SalesOrder, OrderItem, Delivery, BillingDoc, JournalEntry, Material, Plant
- **Relationships**: `PLACED_ORDER`, `CONTAINS_ITEM`, `USES_MATERIAL`, `DELIVERED_VIA`, `BILLED_AS`, `JOURNALED_AS`, `SHIPPED_FROM`
- Each node carries all entity metadata as properties
- Cypher queries power graph traversal and path tracing

### 3. Graph Visualization (Cytoscape.js)
- Color-coded nodes by entity type
- Click to expand neighbors (lazy loading from Neo4j)
- Side panel for node metadata inspection
- Search/filter by entity type or ID

### 4. Conversational Query Interface (Groq LLM)
- **NL → SQL/Cypher**: LLM generates structured queries from natural language
- **Two-step pipeline**: (a) generate query, (b) execute, (c) synthesize human-readable answer
- **Few-shot prompting** with schema context and example queries
- **Conversation memory** for follow-up questions

### 5. Guardrails
- System prompt restricts LLM to dataset-only questions
- Pre-classification of user intent (on-topic vs off-topic)
- SQL/Cypher validation (SELECT/MATCH only, no mutations)
- Clear rejection message for off-topic prompts

---

## Verification Plan

1. **Data**: Verify all tables populated, Neo4j nodes/relationships match expected counts
2. **Graph UI**: Expand nodes, inspect metadata, navigate relationships
3. **Queries**: Test the 3 required example queries + edge cases
4. **Guardrails**: Test off-topic rejection ("What's the capital of France?", "Write a poem")
5. **End-to-end**: Full demo walkthrough via browser
