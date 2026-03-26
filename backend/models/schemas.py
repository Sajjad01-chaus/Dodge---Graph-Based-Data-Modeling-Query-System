from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []


class ChatResponse(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    query_results: Optional[list[dict]] = None
    referenced_nodes: list[str] = []
    is_guardrail_blocked: bool = False


class GraphNode(BaseModel):
    id: str
    label: str
    display_name: str
    properties: dict


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NodeDetail(BaseModel):
    node: GraphNode
    neighbors: GraphData


class SchemaInfo(BaseModel):
    tables: dict[str, list[dict]]
