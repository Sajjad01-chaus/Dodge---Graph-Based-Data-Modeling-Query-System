from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.config import settings

# 1. ADDED connect_args to allow FastAPI multi-threading with SQLite
engine = create_engine(
    settings.DATABASE_URL, 
    echo=False,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def execute_query(sql: str, params: dict = None) -> list[dict]:
    """Execute a read-only SQL query and return results as list of dicts."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]

def get_table_names() -> list[str]:
    """Return all user table names (UPDATED FOR SQLITE)."""
    with engine.connect() as conn:
        # SQLite uses sqlite_master instead of information_schema
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        )
        return [row[0] for row in result.fetchall()]

def get_schema_info() -> dict:
    """Return schema info (UPDATED FOR SQLITE)."""
    schema = {}
    with engine.connect() as conn:
        tables = get_table_names()
        for table in tables:
            # SQLite uses PRAGMA table_info instead of information_schema.columns
            result = conn.execute(text(f"PRAGMA table_info({table})"))
            # PRAGMA returns: (id, name, type, notnull, default_value, pk)
            schema[table] = [
                {"column": row[1], "type": row[2]} for row in result.fetchall()
            ]
    return schema

def init_postgres_schema():
    """Initialize connection."""
    print(f"[DB] SQLite connection ready: {settings.DATABASE_URL}")