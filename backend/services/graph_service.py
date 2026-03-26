"""Graph service — higher level graph operations using Neo4j."""

from database.neo4j_db import run_cypher, get_graph_data, get_node_neighbors, search_nodes


def get_graph_overview(limit: int = 200) -> dict:
    """Get graph data for initial visualization."""
    return get_graph_data(limit=limit)


def get_node_detail(node_id: str) -> dict:
    """Get a specific node and its properties."""
    result = run_cypher(
        "MATCH (n) WHERE elementId(n) = $nid RETURN elementId(n) AS id, labels(n)[0] AS label, properties(n) AS props",
        {"nid": node_id},
    )
    if result:
        r = result[0]
        return {
            "id": str(r["id"]),
            "label": r["label"],
            "properties": r["props"],
        }
    return None


def expand_node(node_id: str, limit: int = 50) -> dict:
    """Get neighbors of a node for graph expansion."""
    return get_node_neighbors(node_id, limit=limit)


def search_graph(query: str, node_type: str = None, limit: int = 20) -> list[dict]:
    """Search for nodes matching a query string."""
    return search_nodes(query, node_type=node_type, limit=limit)


def get_entity_flow(entity_id: str, entity_type: str) -> dict:
    """Trace the O2C flow for a given entity."""
    if entity_type in ("SalesOrder", "sales_order"):
        return _trace_from_sales_order(entity_id)
    elif entity_type in ("Delivery", "delivery"):
        return _trace_from_delivery(entity_id)
    elif entity_type in ("BillingDocument", "billing"):
        return _trace_from_billing(entity_id)
    elif entity_type in ("Customer", "customer"):
        return _trace_from_customer(entity_id)
    else:
        return {"nodes": [], "edges": []}


def _trace_from_sales_order(so_id: str) -> dict:
    """Trace full O2C flow from a sales order."""
    result = run_cypher(
        """
        MATCH (so:SalesOrder {id: $soid})
        OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(so)
        OPTIONAL MATCH (so)-[:CONTAINS_ITEM]->(oi:OrderItem)
        OPTIONAL MATCH (so)-[:DELIVERED_VIA]->(d:Delivery)
        OPTIONAL MATCH (d)-[:BILLED_AS]->(b:BillingDocument)
        OPTIONAL MATCH (b)-[:JOURNALED_AS]->(j:JournalEntry)
        OPTIONAL MATCH (j)-[:PAID_VIA]->(pay:Payment)
        RETURN c, so, collect(DISTINCT oi) AS items,
               collect(DISTINCT d) AS deliveries,
               collect(DISTINCT b) AS billings,
               collect(DISTINCT j) AS journals,
               collect(DISTINCT pay) AS payments
        """,
        {"soid": so_id},
    )
    return _format_flow_result(result)


def _trace_from_delivery(d_id: str) -> dict:
    result = run_cypher(
        """
        MATCH (d:Delivery {id: $did})
        OPTIONAL MATCH (so:SalesOrder)-[:DELIVERED_VIA]->(d)
        OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(so)
        OPTIONAL MATCH (d)-[:BILLED_AS]->(b:BillingDocument)
        OPTIONAL MATCH (b)-[:JOURNALED_AS]->(j:JournalEntry)
        OPTIONAL MATCH (j)-[:PAID_VIA]->(pay:Payment)
        RETURN c, so, d,
               collect(DISTINCT b) AS billings,
               collect(DISTINCT j) AS journals,
               collect(DISTINCT pay) AS payments
        """,
        {"did": d_id},
    )
    return _format_flow_result(result)


def _trace_from_billing(b_id: str) -> dict:
    result = run_cypher(
        """
        MATCH (b:BillingDocument {id: $bid})
        OPTIONAL MATCH (d:Delivery)-[:BILLED_AS]->(b)
        OPTIONAL MATCH (so:SalesOrder)-[:DELIVERED_VIA]->(d)
        OPTIONAL MATCH (c:Customer)-[:PLACED_ORDER]->(so)
        OPTIONAL MATCH (b)-[:JOURNALED_AS]->(j:JournalEntry)
        OPTIONAL MATCH (j)-[:PAID_VIA]->(pay:Payment)
        RETURN c, so, d, b,
               collect(DISTINCT j) AS journals,
               collect(DISTINCT pay) AS payments
        """,
        {"bid": b_id},
    )
    return _format_flow_result(result)


def _trace_from_customer(c_id: str) -> dict:
    result = run_cypher(
        """
        MATCH (c:Customer {id: $cid})-[:PLACED_ORDER]->(so:SalesOrder)
        OPTIONAL MATCH (so)-[:DELIVERED_VIA]->(d:Delivery)
        OPTIONAL MATCH (d)-[:BILLED_AS]->(b:BillingDocument)
        OPTIONAL MATCH (b)-[:JOURNALED_AS]->(j:JournalEntry)
        OPTIONAL MATCH (j)-[:PAID_VIA]->(pay:Payment)
        RETURN c, collect(DISTINCT so) AS orders,
               collect(DISTINCT d) AS deliveries,
               collect(DISTINCT b) AS billings,
               collect(DISTINCT j) AS journals,
               collect(DISTINCT pay) AS payments
        LIMIT 20
        """,
        {"cid": c_id},
    )
    return _format_flow_result(result)


def _format_flow_result(result: list[dict]) -> dict:
    """Format Cypher result into graph visualization format."""
    nodes = []
    seen_ids = set()

    for record in result:
        for key, value in record.items():
            if isinstance(value, dict) and value:
                _add_node(value, nodes, seen_ids)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and item:
                        _add_node(item, nodes, seen_ids)

    return {"nodes": nodes, "edges": []}


def _add_node(props: dict, nodes: list, seen_ids: set):
    """Add a node from props."""
    nid = props.get("id", "")
    if nid and nid not in seen_ids:
        seen_ids.add(nid)
        nodes.append({
            "id": nid,
            "label": "Unknown",
            "display_name": nid,
            "properties": props,
        })


def get_broken_flows() -> dict:
    """Find sales orders with broken/incomplete O2C flows."""
    delivered_not_billed = run_cypher(
        """
        MATCH (so:SalesOrder)-[:DELIVERED_VIA]->(d:Delivery)
        WHERE NOT (d)-[:BILLED_AS]->(:BillingDocument)
        RETURN so.id AS sales_order, d.id AS delivery,
               'Delivered but not billed' AS issue
        LIMIT 50
        """
    )

    billed_not_delivered = run_cypher(
        """
        MATCH (b:BillingDocument)
        WHERE NOT (:Delivery)-[:BILLED_AS]->(b)
        RETURN b.id AS billing_doc,
               'Billed without delivery link' AS issue
        LIMIT 50
        """
    )

    billed_no_journal = run_cypher(
        """
        MATCH (b:BillingDocument)
        WHERE NOT (b)-[:JOURNALED_AS]->(:JournalEntry)
        RETURN b.id AS billing_doc,
               'No journal entry created' AS issue
        LIMIT 50
        """
    )

    return {
        "delivered_not_billed": delivered_not_billed,
        "billed_not_delivered": billed_not_delivered,
        "billed_no_journal": billed_no_journal,
        "total_issues": len(delivered_not_billed) + len(billed_not_delivered) + len(billed_no_journal),
    }


def get_graph_statistics() -> dict:
    """Get statistics about the graph."""
    stats = run_cypher(
        """
        MATCH (n)
        RETURN labels(n)[0] AS label, count(n) AS count
        ORDER BY count DESC
        """
    )

    rel_stats = run_cypher(
        """
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(r) AS count
        ORDER BY count DESC
        """
    )

    return {
        "node_counts": {s["label"]: s["count"] for s in stats},
        "relationship_counts": {s["type"]: s["count"] for s in rel_stats},
        "total_nodes": sum(s["count"] for s in stats),
        "total_relationships": sum(s["count"] for s in rel_stats),
    }
