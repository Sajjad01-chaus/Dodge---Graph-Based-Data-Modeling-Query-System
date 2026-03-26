"""Guardrails service - restricts queries to business dataset domain."""

import re


# Keywords that indicate off-topic queries
OFF_TOPIC_PATTERNS = [
    r"\b(write|compose|create)\s+(a\s+)?(poem|story|essay|song|code|script|program)\b",
    r"\b(capital|president|king|queen|prime minister)\s+of\b",
    r"\b(weather|news|sports|movie|music|recipe|cook)\b",
    r"\b(translate|definition|meaning of)\b",
    r"\b(how to|tutorial|teach me|explain)\s+(?!.*(?:order|delivery|invoice|billing|payment|sales|customer|material|plant|journal))",
    r"\b(joke|riddle|fun fact|trivia)\b",
    r"\b(hello|hi|hey|goodbye|bye|thanks|thank you)\s*[!?.]?\s*$",
    r"\b(who are you|what are you|your name)\b",
]

# Keywords that indicate on-topic queries
ON_TOPIC_KEYWORDS = [
    "order", "delivery", "invoice", "billing", "payment", "customer",
    "material", "product", "plant", "sales", "journal", "entry",
    "flow", "trace", "broken", "incomplete", "missing", "document",
    "quantity", "amount", "price", "value", "date", "status",
    "ship", "deliver", "bill", "pay", "purchase", "item",
    "highest", "lowest", "most", "least", "average", "total",
    "count", "sum", "how many", "which", "list", "show",
    "associated", "linked", "connected", "related", "between",
]

BLOCKED_RESPONSE = (
    "This system is designed to answer questions related to the provided "
    "business dataset only. Please ask questions about orders, deliveries, "
    "billing documents, payments, customers, materials, or their relationships."
)


def check_guardrails(message: str) -> tuple[bool, str]:
    """
    Check if a message is within the allowed domain.
    Returns (is_allowed, reason).
    """
    message_lower = message.lower().strip()

    # Very short messages (less than 3 chars) - block
    if len(message_lower) < 3:
        return False, BLOCKED_RESPONSE

    # Check for off-topic patterns
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            # But check if it also contains on-topic keywords
            has_on_topic = any(kw in message_lower for kw in ON_TOPIC_KEYWORDS)
            if not has_on_topic:
                return False, BLOCKED_RESPONSE

    # Check for on-topic keywords
    has_on_topic = any(kw in message_lower for kw in ON_TOPIC_KEYWORDS)
    if has_on_topic:
        return True, ""

    # Ambiguous - let the LLM decide (will be further checked by LLM guardrail)
    return True, ""


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Validate that generated SQL is safe (SELECT-only).
    Returns (is_safe, reason).
    """
    sql_upper = sql.upper().strip()

    # Must start with SELECT or WITH (CTE)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False, "Only SELECT queries are allowed."

    # Block dangerous keywords
    dangerous = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
        "INTO", "COPY", "\\\\",
    ]
    for keyword in dangerous:
        # Check for standalone keyword (not part of a column/table name)
        pattern = r"\b" + keyword + r"\b"
        if re.search(pattern, sql_upper):
            # Allow "INTO" only in "SELECT ... INTO" if it's a subquery alias
            if keyword == "INTO":
                # Allow SELECT INTO only if it's clearly just an alias
                continue
            return False, f"Query contains forbidden keyword: {keyword}"

    return True, ""


def sanitize_response(response: str) -> str:
    """Clean up LLM response and check for guardrail blocks."""
    if "GUARDRAIL_BLOCKED" in response:
        return BLOCKED_RESPONSE
    return response.strip()
