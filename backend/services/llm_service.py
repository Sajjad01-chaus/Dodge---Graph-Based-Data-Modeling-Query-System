"""LLM service - Groq integration with NL-to-SQL pipeline."""

import json
import re
from groq import Groq
from config import settings
from database.postgres import execute_query, get_schema_info, get_table_names
from services.guardrails import check_guardrails, validate_sql, sanitize_response, BLOCKED_RESPONSE
from services.prompts import (
    SYSTEM_PROMPT,
    SQL_GENERATION_PROMPT,
    ANSWER_SYNTHESIS_PROMPT,
    GUARDRAIL_CHECK_PROMPT,
)

# Initialize Groq client
client = None


def get_client():
    global client
    if client is None:
        client = Groq(api_key=settings.GROQ_API_KEY)
    return client


# Conversation memory (in-memory, per session)
conversation_memory: list[dict] = []
MAX_MEMORY = 20


def _get_schema_context() -> str:
    """Build schema context string for LLM."""
    schema = get_schema_info()
    if not schema:
        # Fallback: list tables and fetch column info
        tables = get_table_names()
        if tables:
            schema_parts = []
            for table in tables:
                try:
                    cols = execute_query(
                        f"SELECT column_name, data_type FROM information_schema.columns "
                        f"WHERE table_name = '{table}' ORDER BY ordinal_position"
                    )
                    col_str = ", ".join([f"{c['column_name']} ({c['data_type']})" for c in cols])
                    schema_parts.append(f"Table: {table}\n  Columns: {col_str}")
                except Exception:
                    schema_parts.append(f"Table: {table}")
            return "\n\n".join(schema_parts)
    
    schema_parts = []
    for table, columns in schema.items():
        col_str = ", ".join([f"{c['column']} ({c['type']})" for c in columns])
        schema_parts.append(f"Table: {table}\n  Columns: {col_str}")
    return "\n\n".join(schema_parts)


def _get_tables_context() -> str:
    """List available data tables."""
    tables = get_table_names()
    return ", ".join(tables) if tables else "No tables found"


def _call_llm(messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
    """Call Groq LLM API."""
    try:
        c = get_client()
        response = c.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM] Error calling Groq: {e}")
        raise


def _llm_guardrail_check(message: str) -> bool:
    """Use LLM to verify if message is on-topic."""
    try:
        response = _call_llm(
            [{"role": "user", "content": GUARDRAIL_CHECK_PROMPT.format(message=message)}],
            temperature=0.0,
            max_tokens=10,
        )
        return "ALLOWED" in response.upper()
    except Exception:
        # If LLM check fails, allow the message (fail open for data queries)
        return True


def _extract_sql(response: str) -> str:
    """Extract SQL query from LLM response."""
    # Try to find SQL in code blocks
    sql_match = re.search(r"```(?:sql)?\s*\n?(.*?)\n?```", response, re.DOTALL | re.IGNORECASE)
    if sql_match:
        return sql_match.group(1).strip()

    # Try to find SELECT statement
    select_match = re.search(r"(SELECT\s+.*?;?)\s*$", response, re.DOTALL | re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip()

    # Try WITH (CTE)
    with_match = re.search(r"(WITH\s+.*?;?)\s*$", response, re.DOTALL | re.IGNORECASE)
    if with_match:
        return with_match.group(1).strip()

    return response.strip()


def process_query(user_message: str, conversation_history: list[dict] = None) -> dict:
    """
    Main query processing pipeline:
    1. Check guardrails
    2. Generate SQL
    3. Execute SQL
    4. Synthesize answer
    """
    # Step 1: Check guardrails (keyword-based)
    is_allowed, block_reason = check_guardrails(user_message)
    if not is_allowed:
        return {
            "answer": block_reason,
            "sql_query": None,
            "query_results": None,
            "referenced_nodes": [],
            "is_guardrail_blocked": True,
        }

    # Step 1b: LLM guardrail check for ambiguous cases
    if not _llm_guardrail_check(user_message):
        return {
            "answer": BLOCKED_RESPONSE,
            "sql_query": None,
            "query_results": None,
            "referenced_nodes": [],
            "is_guardrail_blocked": True,
        }

    # Get schema context
    schema_context = _get_schema_context()
    raw_tables = _get_tables_context()

    # Step 2: Generate SQL
    try:
        sql_prompt = SQL_GENERATION_PROMPT.format(
            schema=schema_context,
            question=user_message,
        )
        sql_response = _call_llm(
            [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT.format(schema=schema_context, raw_tables=raw_tables),
                },
                {"role": "user", "content": sql_prompt},
            ],
            temperature=0.0,
        )

        sql_query = _extract_sql(sql_response)

        # Check for guardrail in LLM response
        if "GUARDRAIL_BLOCKED" in sql_response:
            return {
                "answer": BLOCKED_RESPONSE,
                "sql_query": None,
                "query_results": None,
                "referenced_nodes": [],
                "is_guardrail_blocked": True,
            }

    except Exception as e:
        return {
            "answer": f"I encountered an error generating the query: {str(e)}",
            "sql_query": None,
            "query_results": None,
            "referenced_nodes": [],
            "is_guardrail_blocked": False,
        }

    # Step 3: Validate and execute SQL
    is_safe, safety_reason = validate_sql(sql_query)
    if not is_safe:
        return {
            "answer": f"The generated query was blocked for safety: {safety_reason}",
            "sql_query": sql_query,
            "query_results": None,
            "referenced_nodes": [],
            "is_guardrail_blocked": True,
        }

    try:
        results = execute_query(sql_query)
    except Exception as e:
        error_msg = str(e)
        # Try to fix the query once
        try:
            fix_prompt = (
                f"The following SQL query failed with error: {error_msg}\n\n"
                f"Original query: {sql_query}\n\n"
                f"Schema: {schema_context}\n\n"
                f"Please fix the query and return ONLY the corrected SQL."
            )
            fixed_response = _call_llm(
                [{"role": "user", "content": fix_prompt}],
                temperature=0.0,
            )
            sql_query = _extract_sql(fixed_response)
            is_safe, _ = validate_sql(sql_query)
            if is_safe:
                results = execute_query(sql_query)
            else:
                return {
                    "answer": f"I was unable to generate a valid query for your question. Please try rephrasing.",
                    "sql_query": sql_query,
                    "query_results": None,
                    "referenced_nodes": [],
                    "is_guardrail_blocked": False,
                }
        except Exception as e2:
            return {
                "answer": f"I was unable to query the database. Error: {str(e2)[:200]}. Please try rephrasing your question.",
                "sql_query": sql_query,
                "query_results": None,
                "referenced_nodes": [],
                "is_guardrail_blocked": False,
            }

    # Step 4: Synthesize answer
    try:
        # Limit results for LLM context
        display_results = results[:30] if len(results) > 30 else results
        results_str = json.dumps(display_results, indent=2, default=str)

        answer_prompt = ANSWER_SYNTHESIS_PROMPT.format(
            question=user_message,
            sql_query=sql_query,
            results=results_str,
        )
        answer = _call_llm(
            [
                {
                    "role": "system",
                    "content": "You are a helpful data analyst. Provide clear, concise answers based on query results. Always reference specific data values.",
                },
                {"role": "user", "content": answer_prompt},
            ],
            temperature=0.3,
        )
        answer = sanitize_response(answer)

    except Exception as e:
        answer = f"Query executed successfully. Found {len(results)} results."
        if results:
            answer += f"\n\nSample: {json.dumps(results[:5], indent=2, default=str)}"

    # Extract referenced node IDs
    referenced = _extract_referenced_nodes(results)

    # Update conversation memory
    conversation_memory.append({"role": "user", "content": user_message})
    conversation_memory.append({"role": "assistant", "content": answer})
    if len(conversation_memory) > MAX_MEMORY:
        conversation_memory.pop(0)
        conversation_memory.pop(0)

    return {
        "answer": answer,
        "sql_query": sql_query,
        "query_results": display_results if results else [],
        "referenced_nodes": referenced,
        "is_guardrail_blocked": False,
    }


def _extract_referenced_nodes(results: list[dict]) -> list[str]:
    """Extract entity IDs from query results for graph highlighting."""
    node_ids = []
    id_columns = [
        "sales_order_id", "customer_id", "delivery_id", "material_id",
        "billing_doc_id", "journal_entry_id", "payment_id", "plant_id",
        "sales_order", "delivery", "billing_document", "customer",
    ]
    for row in results[:20]:  # Limit to avoid too many highlights
        for col in id_columns:
            if col in row and row[col]:
                node_ids.append(str(row[col]))
    return list(set(node_ids))
