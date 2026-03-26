from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)
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
    """Return all user table names."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        )
        return [row[0] for row in result.fetchall()]


def get_schema_info() -> dict:
    """Return schema info: table -> list of {column, type}."""
    schema = {}
    with engine.connect() as conn:
        tables = get_table_names()
        for table in tables:
            result = conn.execute(
                text(
                    "SELECT column_name, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :table "
                    "ORDER BY ordinal_position"
                ),
                {"table": table},
            )
            schema[table] = [
                {"column": row[0], "type": row[1]} for row in result.fetchall()
            ]
    return schema


def init_postgres_schema():
    """Initialize — tables are created dynamically during ingestion."""
    print("[DB] PostgreSQL connection ready.")
