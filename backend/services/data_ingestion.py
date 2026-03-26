"""Data ingestion service — loads SAP O2C JSONL dataset into PostgreSQL and Neo4j."""

import os
import json
import pandas as pd
from backend.database.sqlite import engine
from backend.database.neo4j_db import run_cypher, init_neo4j_constraints
from sqlalchemy import text


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sap-o2c-data")


# ============================================================
# JSONL Loading
# ============================================================

def load_jsonl_directory(dir_path: str) -> pd.DataFrame:
    """Load all .jsonl files in a directory into a single DataFrame."""
    records = []
    if not os.path.exists(dir_path):
        return pd.DataFrame()

    for filename in sorted(os.listdir(dir_path)):
        if filename.endswith(".jsonl"):
            filepath = os.path.join(dir_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            # Flatten nested time objects
                            record = _flatten_record(record)
                            records.append(record)
                        except json.JSONDecodeError:
                            continue

    return pd.DataFrame(records) if records else pd.DataFrame()


def _flatten_record(record: dict) -> dict:
    """Flatten nested objects (like time fields) into strings."""
    flat = {}
    for key, value in record.items():
        if isinstance(value, dict):
            # e.g. {"hours": 6, "minutes": 49, "seconds": 13} -> "06:49:13"
            if "hours" in value and "minutes" in value:
                flat[key] = f"{value.get('hours',0):02d}:{value.get('minutes',0):02d}:{value.get('seconds',0):02d}"
            else:
                flat[key] = json.dumps(value)
        else:
            flat[key] = value
    return flat


# ============================================================
# PostgreSQL Ingestion
# ============================================================

def ingest_to_postgres():
    """Load all entity directories into PostgreSQL tables."""
    if not os.path.exists(DATA_DIR):
        print(f"[Ingest] Data directory not found: {DATA_DIR}")
        return False

    entity_dirs = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]
    print(f"[Ingest] Found {len(entity_dirs)} entity directories: {entity_dirs}")

    for entity_name in sorted(entity_dirs):
        dir_path = os.path.join(DATA_DIR, entity_name)
        df = load_jsonl_directory(dir_path)

        if df.empty:
            print(f"[Ingest] Skipping {entity_name} - no data")
            continue

        # Clean column names for PostgreSQL
        df.columns = [_clean_col_name(c) for c in df.columns]

        table_name = entity_name
        print(f"[Ingest] Loading {table_name}: {len(df)} rows, {len(df.columns)} columns")

        try:
            df.to_sql(table_name, engine, if_exists="replace", index=False)
            print(f"[Ingest] OK {table_name}")
        except Exception as e:
            print(f"[Ingest] FAIL {table_name}: {e}")

    return True


def _clean_col_name(col: str) -> str:
    """Convert camelCase to snake_case for PostgreSQL."""
    import re
    # Insert underscore before uppercase letters
    s = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', col)
    return s.lower()


# ============================================================
# Neo4j Ingestion
# ============================================================

def ingest_to_neo4j():
    """Build graph nodes and relationships in Neo4j."""
    init_neo4j_constraints()

    if not os.path.exists(DATA_DIR):
        print(f"[Neo4j] Data directory not found: {DATA_DIR}")
        return False

    # 1. Create nodes for each entity type
    _create_business_partner_nodes()
    _create_product_nodes()
    _create_plant_nodes()
    _create_sales_order_nodes()
    _create_sales_order_item_nodes()
    _create_delivery_nodes()
    _create_delivery_item_nodes()
    _create_billing_document_nodes()
    _create_billing_item_nodes()
    _create_journal_entry_nodes()
    _create_payment_nodes()

    # 2. Create relationships
    _create_relationships()

    print("[Neo4j] === Graph construction complete ===")
    return True


def _load_entity(name: str) -> pd.DataFrame:
    """Load an entity directory."""
    path = os.path.join(DATA_DIR, name)
    return load_jsonl_directory(path)


def _safe_props(row: dict) -> dict:
    """Convert row to Neo4j-safe properties (strings, no None)."""
    props = {}
    for k, v in row.items():
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        if isinstance(v, (dict, list)):
            props[k] = json.dumps(v)
        else:
            props[k] = str(v)
    return props


def _batch_create_nodes(label: str, id_field: str, df: pd.DataFrame, batch_size: int = 100):
    """Batch create nodes using UNWIND for performance."""
    if df.empty:
        print(f"[Neo4j] No data for {label}")
        return

    rows = []
    for _, row in df.iterrows():
        record = row.to_dict()
        if record.get(id_field) is None or (isinstance(record.get(id_field), float) and pd.isna(record.get(id_field))):
            continue
        props = _safe_props(record)
        props["_id"] = str(record[id_field])
        rows.append(props)

    # Process in batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            run_cypher(
                f"""
                UNWIND $batch AS row
                MERGE (n:{label} {{id: row._id}})
                SET n += row
                """,
                {"batch": batch},
            )
        except Exception as e:
            print(f"[Neo4j] Error creating {label} batch {i}: {e}")

    print(f"[Neo4j] OK Created {len(rows)} {label} nodes")


def _create_business_partner_nodes():
    df = _load_entity("business_partners")
    _batch_create_nodes("Customer", "businessPartner", df)


def _create_product_nodes():
    df = _load_entity("products")
    # Merge with descriptions
    desc_df = _load_entity("product_descriptions")
    if not desc_df.empty and not df.empty:
        desc_df = desc_df[desc_df.get("language", pd.Series(dtype=str)) == "EN"] if "language" in desc_df.columns else desc_df
        df = df.merge(desc_df[["product", "productDescription"]], on="product", how="left") if "product" in desc_df.columns else df
    _batch_create_nodes("Product", "product", df)


def _create_plant_nodes():
    df = _load_entity("plants")
    _batch_create_nodes("Plant", "plant", df)


def _create_sales_order_nodes():
    df = _load_entity("sales_order_headers")
    _batch_create_nodes("SalesOrder", "salesOrder", df)


def _create_sales_order_item_nodes():
    df = _load_entity("sales_order_items")
    if not df.empty and "salesOrder" in df.columns and "salesOrderItem" in df.columns:
        df["orderItemId"] = df["salesOrder"].astype(str) + "_" + df["salesOrderItem"].astype(str)
    _batch_create_nodes("OrderItem", "orderItemId", df)


def _create_delivery_nodes():
    df = _load_entity("outbound_delivery_headers")
    _batch_create_nodes("Delivery", "deliveryDocument", df)


def _create_delivery_item_nodes():
    df = _load_entity("outbound_delivery_items")
    if not df.empty and "deliveryDocument" in df.columns and "deliveryDocumentItem" in df.columns:
        df["deliveryItemId"] = df["deliveryDocument"].astype(str) + "_" + df["deliveryDocumentItem"].astype(str)
    _batch_create_nodes("DeliveryItem", "deliveryItemId", df)


def _create_billing_document_nodes():
    df = _load_entity("billing_document_headers")
    _batch_create_nodes("BillingDocument", "billingDocument", df)


def _create_billing_item_nodes():
    df = _load_entity("billing_document_items")
    if not df.empty and "billingDocument" in df.columns and "billingDocumentItem" in df.columns:
        df["billingItemId"] = df["billingDocument"].astype(str) + "_" + df["billingDocumentItem"].astype(str)
    _batch_create_nodes("BillingItem", "billingItemId", df)


def _create_journal_entry_nodes():
    df = _load_entity("journal_entry_items_accounts_receivable")
    if not df.empty and "accountingDocument" in df.columns:
        _batch_create_nodes("JournalEntry", "accountingDocument", df)


def _create_payment_nodes():
    df = _load_entity("payments_accounts_receivable")
    if not df.empty and "accountingDocument" in df.columns and "accountingDocumentItem" in df.columns:
        df["paymentId"] = df["accountingDocument"].astype(str) + "_" + df["accountingDocumentItem"].astype(str)
    _batch_create_nodes("Payment", "paymentId", df)


# ============================================================
# Relationships
# ============================================================

def _create_relationships():
    """Create graph relationships based on foreign keys in the data."""
    print("[Neo4j] Building relationships...")

    # Customer -> SalesOrder (via soldToParty)
    so_df = _load_entity("sales_order_headers")
    if not so_df.empty:
        _batch_create_rels(
            "Customer", "id", "soldToParty",
            "SalesOrder", "id", "salesOrder",
            "PLACED_ORDER", so_df,
        )

    # SalesOrder -> OrderItem
    soi_df = _load_entity("sales_order_items")
    if not soi_df.empty:
        soi_df["orderItemId"] = soi_df["salesOrder"].astype(str) + "_" + soi_df["salesOrderItem"].astype(str)
        _batch_create_rels(
            "SalesOrder", "id", "salesOrder",
            "OrderItem", "id", "orderItemId",
            "CONTAINS_ITEM", soi_df,
        )

        # OrderItem -> Product (via material)
        _batch_create_rels(
            "OrderItem", "id", "orderItemId",
            "Product", "id", "material",
            "USES_MATERIAL", soi_df,
        )

        # OrderItem -> Plant (via productionPlant)
        if "productionPlant" in soi_df.columns:
            _batch_create_rels(
                "OrderItem", "id", "orderItemId",
                "Plant", "id", "productionPlant",
                "PRODUCED_AT", soi_df,
            )

    # Delivery -> SalesOrder (via delivery items -> referenceSdDocument)
    di_df = _load_entity("outbound_delivery_items")
    if not di_df.empty:
        di_df["deliveryItemId"] = di_df["deliveryDocument"].astype(str) + "_" + di_df["deliveryDocumentItem"].astype(str)

        # DeliveryItem -> Delivery
        _batch_create_rels(
            "Delivery", "id", "deliveryDocument",
            "DeliveryItem", "id", "deliveryItemId",
            "HAS_ITEM", di_df,
        )

        # SalesOrder -> Delivery (via referenceSdDocument on delivery items)
        # Get unique SO -> Delivery mappings
        if "referenceSdDocument" in di_df.columns:
            so_del_df = di_df[["referenceSdDocument", "deliveryDocument"]].drop_duplicates()
            _batch_create_rels(
                "SalesOrder", "id", "referenceSdDocument",
                "Delivery", "id", "deliveryDocument",
                "DELIVERED_VIA", so_del_df,
            )

        # DeliveryItem -> Product (via material in delivery items)
        if "material" in di_df.columns:
            _batch_create_rels(
                "DeliveryItem", "id", "deliveryItemId",
                "Product", "id", "material",
                "DELIVERS_PRODUCT", di_df,
            )

        # DeliveryItem -> Plant
        if "plant" in di_df.columns:
            _batch_create_rels(
                "DeliveryItem", "id", "deliveryItemId",
                "Plant", "id", "plant",
                "SHIPPED_FROM", di_df,
            )

    # BillingDocument -> Delivery (via billing items -> referenceSdDocument)
    bi_df = _load_entity("billing_document_items")
    if not bi_df.empty:
        bi_df["billingItemId"] = bi_df["billingDocument"].astype(str) + "_" + bi_df["billingDocumentItem"].astype(str)

        # BillingDocument -> BillingItem
        _batch_create_rels(
            "BillingDocument", "id", "billingDocument",
            "BillingItem", "id", "billingItemId",
            "HAS_ITEM", bi_df,
        )

        # Delivery -> BillingDocument (via referenceSdDocument on billing items)
        if "referenceSdDocument" in bi_df.columns:
            del_bill_df = bi_df[["referenceSdDocument", "billingDocument"]].drop_duplicates()
            _batch_create_rels(
                "Delivery", "id", "referenceSdDocument",
                "BillingDocument", "id", "billingDocument",
                "BILLED_AS", del_bill_df,
            )

        # BillingItem -> Product (via material)
        if "material" in bi_df.columns:
            _batch_create_rels(
                "BillingItem", "id", "billingItemId",
                "Product", "id", "material",
                "BILLS_PRODUCT", bi_df,
            )

    # JournalEntry -> BillingDocument (via referenceDocument)
    je_df = _load_entity("journal_entry_items_accounts_receivable")
    if not je_df.empty and "referenceDocument" in je_df.columns:
        je_bill_df = je_df[["accountingDocument", "referenceDocument"]].drop_duplicates()
        _batch_create_rels(
            "BillingDocument", "id", "referenceDocument",
            "JournalEntry", "id", "accountingDocument",
            "JOURNALED_AS", je_bill_df,
        )

    # Payment -> JournalEntry (via clearingAccountingDocument or accountingDocument)
    pay_df = _load_entity("payments_accounts_receivable")
    if not pay_df.empty:
        pay_df["paymentId"] = pay_df["accountingDocument"].astype(str) + "_" + pay_df["accountingDocumentItem"].astype(str)
        if "clearingAccountingDocument" in pay_df.columns:
            pay_clear = pay_df[pay_df["clearingAccountingDocument"].notna() & (pay_df["clearingAccountingDocument"] != "")]
            if not pay_clear.empty:
                _batch_create_rels(
                    "JournalEntry", "id", "accountingDocument",
                    "Payment", "id", "paymentId",
                    "PAID_VIA", pay_clear,
                )

    print("[Neo4j] OK All relationships created")


def _batch_create_rels(
    src_label: str, src_prop: str, src_col: str,
    tgt_label: str, tgt_prop: str, tgt_col: str,
    rel_type: str, df: pd.DataFrame, batch_size: int = 200
):
    """Batch create relationships using UNWIND."""
    if df.empty or src_col not in df.columns or tgt_col not in df.columns:
        return

    pairs = []
    for _, row in df.iterrows():
        s = row.get(src_col)
        t = row.get(tgt_col)
        if s is not None and t is not None and not (isinstance(s, float) and pd.isna(s)) and not (isinstance(t, float) and pd.isna(t)):
            pairs.append({"src": str(s), "tgt": str(t)})

    if not pairs:
        return

    # Deduplicate
    unique = list({(p["src"], p["tgt"]): p for p in pairs}.values())

    for i in range(0, len(unique), batch_size):
        batch = unique[i:i + batch_size]
        try:
            run_cypher(
                f"""
                UNWIND $batch AS pair
                MATCH (a:{src_label} {{{src_prop}: pair.src}})
                MATCH (b:{tgt_label} {{{tgt_prop}: pair.tgt}})
                MERGE (a)-[:{rel_type}]->(b)
                """,
                {"batch": batch},
            )
        except Exception as e:
            print(f"[Neo4j] Error creating {rel_type} batch {i}: {e}")

    print(f"[Neo4j]   {rel_type}: {len(unique)} relationships ({src_label} -> {tgt_label})")


# ============================================================
# Main Entry Point
# ============================================================

def run_ingestion():
    """Main ingestion entry point."""
    if not os.path.exists(DATA_DIR):
        print(f"[Ingest] Dataset directory not found: {DATA_DIR}")
        print(f"[Ingest] Please extract sap-order-to-cash-dataset.zip into backend/data/")
        return False

    entity_dirs = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]
    if not entity_dirs:
        print(f"[Ingest] No entity directories found in {DATA_DIR}")
        return False

    print(f"[Ingest] === Starting ingestion of {len(entity_dirs)} entities ===")

    # Load into PostgreSQL
    print("\n[Ingest] === Phase 1: Loading into PostgreSQL ===")
    ingest_to_postgres()

    # Load into Neo4j
    print("\n[Ingest] === Phase 2: Building Neo4j Graph ===")
    ingest_to_neo4j()

    print("\n[Ingest] === Ingestion complete ===")
    return True

# THIS IS THE PART THAT TRIGGERS THE ACTUAL WORK
if __name__ == "__main__":
    run_ingestion()