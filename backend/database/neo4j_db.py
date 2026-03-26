from urllib.parse import urlparse
from neo4j import GraphDatabase, TrustAll
from backend.config import settings

class Neo4jConnection:
    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            uri = settings.NEO4J_URI
            # Force the correct default username for Aura
            username = settings.NEO4J_USERNAME if settings.NEO4J_USERNAME else "neo4j"
            
            driver_kwargs = {
                "auth": (username, settings.NEO4J_PASSWORD),
            }

            # FORCE TRUST ALL CERTIFICATES to bypass WiFi/ISP blocks
            # This fixes the "SSLCertVerificationError" and "Operation not permitted"
            driver_kwargs["encrypted"] = True
            driver_kwargs["trusted_certificates"] = TrustAll()

            try:
                cls._driver = GraphDatabase.driver(uri, **driver_kwargs)
            except Exception as e:
                print(f"[Neo4j] Driver creation failed: {e}")
                raise e
        return cls._driver

    @classmethod
    def close(cls):
        if cls._driver:
            cls._driver.close()
            cls._driver = None

# ... (Keep the rest of your functions like run_cypher, init_neo4j_constraints, etc. as they are)


def run_cypher(query: str, params: dict = None) -> list[dict]:
    """Execute a Cypher query and return results as list of dicts."""
    driver = Neo4jConnection.get_driver()
    with driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


def init_neo4j_constraints():
    """Create uniqueness constraints for node types."""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (so:SalesOrder) REQUIRE so.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Product) REQUIRE m.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Plant) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Delivery) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (di:DeliveryItem) REQUIRE di.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (b:BillingDocument) REQUIRE b.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (bi:BillingItem) REQUIRE bi.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (j:JournalEntry) REQUIRE j.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (pay:Payment) REQUIRE pay.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (oi:OrderItem) REQUIRE oi.id IS UNIQUE",
    ]
    driver = Neo4jConnection.get_driver()
    with driver.session() as session:
        for constraint in constraints:
            try:
                session.run(constraint)
            except Exception as e:
                print(f"[Neo4j] Constraint warning: {e}")
    print("[Neo4j] Constraints initialized.")


# Display name mapping per label
DISPLAY_NAME_FIELDS = {
    "Customer": ["businessPartnerName", "businessPartnerFullName", "businessPartner"],
    "SalesOrder": ["salesOrder"],
    "OrderItem": ["orderItemId", "salesOrder"],
    "Product": ["productDescription", "productOldId", "product"],
    "Plant": ["plantName", "plant"],
    "Delivery": ["deliveryDocument"],
    "DeliveryItem": ["deliveryItemId"],
    "BillingDocument": ["billingDocument"],
    "BillingItem": ["billingItemId"],
    "JournalEntry": ["accountingDocument"],
    "Payment": ["paymentId"],
}


def _get_display_name(label: str, props: dict) -> str:
    """Get a human-readable display name for a node."""
    fields = DISPLAY_NAME_FIELDS.get(label, [])
    for field in fields:
        if field in props and props[field]:
            return str(props[field])
    return props.get("id", "?")


def get_graph_data(limit: int = 200) -> dict:
    """Get graph nodes and relationships for visualization."""
    driver = Neo4jConnection.get_driver()
    with driver.session() as session:
        # Get nodes
        node_result = session.run(
            """
            MATCH (n)
            WITH n, labels(n)[0] AS label
            RETURN elementId(n) AS id, label, properties(n) AS props
            LIMIT $limit
            """,
            {"limit": limit},
        )
        nodes = []
        node_ids = set()
        for record in node_result:
            nid = str(record["id"])
            label = record["label"]
            props = record["props"]
            node_ids.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "display_name": _get_display_name(label, props),
                "properties": props,
            })

        # Get relationships between visible nodes
        rel_result = session.run(
            """
            MATCH (a)-[r]->(b)
            WITH elementId(a) AS src, elementId(b) AS tgt, type(r) AS relType
            RETURN src, tgt, relType
            LIMIT $limit
            """,
            {"limit": limit * 3},
        )
        edges = []
        for record in rel_result:
            src = str(record["src"])
            tgt = str(record["tgt"])
            if src in node_ids and tgt in node_ids:
                edges.append({
                    "source": src,
                    "target": tgt,
                    "type": record["relType"],
                })

        return {"nodes": nodes, "edges": edges}


def get_node_neighbors(node_id: str, limit: int = 50) -> dict:
    """Get neighbors of a specific node."""
    driver = Neo4jConnection.get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)-[r]-(neighbor)
            WHERE elementId(n) = $node_id
            RETURN elementId(n) AS src_id, elementId(neighbor) AS neighbor_id,
                   labels(neighbor)[0] AS neighbor_label,
                   properties(neighbor) AS neighbor_props,
                   type(r) AS rel_type,
                   CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END AS direction
            LIMIT $limit
            """,
            {"node_id": node_id, "limit": limit},
        )

        nodes = {}
        edges = []
        for record in result:
            nid = str(record["neighbor_id"])
            if nid not in nodes:
                label = record["neighbor_label"]
                props = record["neighbor_props"]
                nodes[nid] = {
                    "id": nid,
                    "label": label,
                    "display_name": _get_display_name(label, props),
                    "properties": props,
                }

            if record["direction"] == "outgoing":
                edges.append({
                    "source": str(record["src_id"]),
                    "target": nid,
                    "type": record["rel_type"],
                })
            else:
                edges.append({
                    "source": nid,
                    "target": str(record["src_id"]),
                    "type": record["rel_type"],
                })

        return {"nodes": list(nodes.values()), "edges": edges}


def search_nodes(query: str, node_type: str = None, limit: int = 20) -> list[dict]:
    """Search nodes by property values."""
    if node_type:
        cypher = f"""
            MATCH (n:{node_type})
            WHERE any(prop IN keys(n) WHERE toString(n[prop]) =~ $query)
            RETURN elementId(n) AS id, labels(n)[0] AS label, properties(n) AS props
            LIMIT $limit
        """
    else:
        cypher = """
            MATCH (n)
            WHERE any(prop IN keys(n) WHERE toString(n[prop]) =~ $query)
            RETURN elementId(n) AS id, labels(n)[0] AS label, properties(n) AS props
            LIMIT $limit
        """

    params = {"query": f"(?i).*{query}.*", "limit": limit}

    driver = Neo4jConnection.get_driver()
    with driver.session() as session:
        result = session.run(cypher, params)
        return [
            {
                "id": str(record["id"]),
                "label": record["label"],
                "properties": record["props"],
            }
            for record in result
        ]
