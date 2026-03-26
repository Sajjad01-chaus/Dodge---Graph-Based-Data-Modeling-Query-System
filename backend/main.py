"""FastAPI main application entry point."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from backend.config import settings
from backend.routers import graph_router, chat_router
from backend.database.sqlite import init_postgres_schema, get_table_names
from backend.database.neo4j_db import Neo4jConnection


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    print("=" * 60)
    print("  Dodge FDE - Graph Query System Starting...")
    print("=" * 60)

    # Initialize PostgreSQL schema
    try:
        init_postgres_schema()
        tables = get_table_names()
        print(f"[Startup] PostgreSQL ready. Tables: {tables}")
    except Exception as e:
        print(f"[Startup] PostgreSQL warning: {e}")

    # Test Neo4j connection
    try:
        driver = Neo4jConnection.get_driver()
        driver.verify_connectivity()
        print("[Startup] Neo4j connected successfully.")
    except Exception as e:
        print(f"[Startup] Neo4j warning: {e}")

    # Check if data needs ingestion
    try:
        tables = get_table_names()
        if not tables or len(tables) < 2:
            print("[Startup] No data found. Run /api/ingest to load data.")
        else:
            print(f"[Startup] Data loaded: {len(tables)} tables: {tables[:5]}...")
    except Exception:
        pass

    print("=" * 60)
    print(f"  Server running at http://{settings.APP_HOST}:{settings.APP_PORT}")
    print("=" * 60)

    yield

    # Shutdown
    Neo4jConnection.close()
    print("[Shutdown] Connections closed.")


app = FastAPI(
    title="Dodge FDE - Graph Query System",
    description="Graph-based data modeling and LLM-powered query system for SAP O2C data",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(graph_router.router)
app.include_router(chat_router.router)


# Data ingestion endpoint
@app.post("/api/ingest")
async def ingest_data():
    """Trigger data ingestion from files in the data/ directory."""
    from backend.services.data_ingestion import run_ingestion
    try:
        success = run_ingestion()
        if success:
            return {"status": "success", "message": "Data ingested successfully"}
        else:
            return {"status": "warning", "message": "No dataset files found in backend/data/ directory"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Schema endpoint
@app.get("/api/schema")
async def get_schema():
    """Get database schema information."""
    from backend.database.sqlite import get_schema_info
    return get_schema_info()


# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_index():
        index_path = os.path.join(frontend_dir, "index.html")
        return FileResponse(index_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
