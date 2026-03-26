"""Diagnose and test all connections with fixes applied."""
import os, sys
from urllib.parse import quote_plus, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

results = []

# ========== 1. PostgreSQL ==========
results.append("=" * 50)
results.append("1. PostgreSQL (Supabase)")
results.append("=" * 50)

raw_url = os.getenv("DATABASE_URL")
results.append(f"Raw URL: {raw_url}")
results.append("")

# Extract host/port/db from DATABASE_URL so we don't hardcode Supabase ports.
parsed = urlparse(raw_url)
db_user = parsed.username or "postgres"
db_password = parsed.password or ""
db_host = parsed.hostname or "localhost"
db_port = parsed.port or 5432
db_name = (parsed.path or "").lstrip("/") or "postgres"

query = parsed.query or ""
ssl_extra = ""
if "sslmode=" not in query:
    ssl_extra = ("&" if query else "?") + "sslmode=require"
query_str = f"?{query}" if query else ""

# Prefer testing the raw DATABASE_URL first (most accurate),
# then fall back to an encoded-password variant for edge cases.
try:
    from sqlalchemy import create_engine, text
    url_to_test = raw_url
    if "sslmode=" not in (parsed.query or ""):
        url_to_test = f"{raw_url}{ssl_extra}"

    results.append(f"Built URL: {url_to_test}")
    engine = create_engine(url_to_test, echo=False, connect_args={"connect_timeout": 15})
    with engine.connect() as conn:
        row = conn.execute(text("SELECT 1 AS test")).fetchone()
        results.append(f"Query result: {row}")
        results.append("STATUS: OK")
except Exception as e:
    results.append(f"STATUS: FAILED")
    results.append(f"ERROR: {type(e).__name__}: {e}")

# Try alternate approach: URL-encode the password
results.append("")
results.append("--- Alternate: URL-encoded password ---")
try:
    password_encoded = quote_plus(db_password)
    encoded_url = f"postgresql://{db_user}:{password_encoded}@{db_host}:{db_port}/{db_name}{query_str}{ssl_extra}"
    results.append(f"Encoded URL: {encoded_url}")
    engine2 = create_engine(encoded_url, echo=False, connect_args={"connect_timeout": 15})
    with engine2.connect() as conn:
        row = conn.execute(text("SELECT 1 AS test")).fetchone()
        results.append(f"Query result: {row}")
        results.append("STATUS: OK")
except Exception as e:
    results.append(f"STATUS: FAILED")
    results.append(f"ERROR: {type(e).__name__}: {e}")


# ========== 2. Neo4j ==========
results.append("")
results.append("=" * 50)
results.append("2. Neo4j (Aura)")
results.append("=" * 50)

neo4j_uri = os.getenv("NEO4J_URI")
neo4j_user = os.getenv("NEO4J_USERNAME")
neo4j_pass = os.getenv("NEO4J_PASSWORD")
results.append(f"URI: {neo4j_uri}")
results.append(f"Username from .env: {neo4j_user}")
results.append(f"Password: {neo4j_pass[:5]}...{neo4j_pass[-5:]}")

try:
    from neo4j import GraphDatabase, __version__ as neo4j_version
    results.append(f"neo4j driver version: {neo4j_version}")
except ImportError:
    results.append("neo4j package not installed!")

# Try with username from .env
results.append("")
results.append(f"--- Attempt 1: username='{neo4j_user}' ---")
try:
    from urllib.parse import urlparse as _urlparse
    from neo4j import TrustAll

    _scheme = _urlparse(neo4j_uri).scheme.lower()
    _driver_kwargs = {"auth": (neo4j_user, neo4j_pass)}
    if _scheme in {"bolt", "neo4j"}:
        _driver_kwargs["encrypted"] = True
        _driver_kwargs["trusted_certificates"] = TrustAll()

    driver = GraphDatabase.driver(neo4j_uri, **_driver_kwargs)
    driver.verify_connectivity()
    with driver.session() as session:
        val = session.run("RETURN 1 AS ok").single()["ok"]
        results.append(f"Query result: {val}")
    results.append("STATUS: OK")
    driver.close()
except Exception as e:
    results.append(f"STATUS: FAILED")
    results.append(f"ERROR: {type(e).__name__}: {e}")

# Try with standard 'neo4j' username
results.append(f"--- Attempt 2: username='neo4j' ---")
try:
    _scheme = _urlparse(neo4j_uri).scheme.lower()
    _driver_kwargs = {"auth": ("neo4j", neo4j_pass)}
    if _scheme in {"bolt", "neo4j"}:
        _driver_kwargs["encrypted"] = True
        _driver_kwargs["trusted_certificates"] = TrustAll()

    driver = GraphDatabase.driver(neo4j_uri, **_driver_kwargs)
    driver.verify_connectivity()
    with driver.session() as session:
        val = session.run("RETURN 1 AS ok").single()["ok"]
        results.append(f"Query result: {val}")
    results.append("STATUS: OK")
    driver.close()
except Exception as e:
    results.append(f"STATUS: FAILED")
    results.append(f"ERROR: {type(e).__name__}: {e}")


# ========== 3. Groq ==========
results.append("")
results.append("=" * 50)
results.append("3. Groq LLM")
results.append("=" * 50)

try:
    import groq as groq_module
    results.append(f"groq package version: {groq_module.__version__}")
except Exception:
    results.append("groq version unknown")

groq_key = os.getenv("GROQ_API_KEY")
results.append(f"API Key: {groq_key[:15]}...")

try:
    from groq import Groq
    client = Groq(api_key=groq_key)
    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=5,
    )
    results.append(f"Response: {resp.choices[0].message.content}")
    results.append("STATUS: OK")
except TypeError as e:
    results.append(f"STATUS: FAILED (package version issue)")
    results.append(f"ERROR: {e}")
    results.append("FIX: Run 'pip install --upgrade groq'")
except Exception as e:
    results.append(f"STATUS: FAILED")
    results.append(f"ERROR: {type(e).__name__}: {e}")


# ========== Write results ==========
output = "\n".join(results)
# Change this:
# with open("test_results.txt", "w") as f:
#     f.write(output)

# To this:
with open("test_results.txt", "w", encoding="utf-8") as f:
    f.write(output)
print(output, flush=True)
