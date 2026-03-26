"""Graph API router — endpoints for graph visualization and exploration."""

from fastapi import APIRouter, Query, HTTPException
from services.graph_service import (
    get_graph_overview,
    get_node_detail,
    expand_node,
    search_graph,
    get_entity_flow,
    get_broken_flows,
    get_graph_statistics,
)

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/overview")
async def graph_overview(limit: int = Query(200, ge=1, le=1000)):
    """Get graph data for initial visualization."""
    try:
        data = get_graph_overview(limit=limit)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load graph: {str(e)}")


@router.get("/node/{node_id:path}")
async def node_detail(node_id: str):
    """Get details of a specific node."""
    try:
        node = get_node_detail(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return node
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expand/{node_id:path}")
async def expand(node_id: str, limit: int = Query(50, ge=1, le=200)):
    """Expand a node to see its neighbors."""
    try:
        return expand_node(node_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    node_type: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Search for nodes by property values."""
    try:
        return search_graph(q, node_type=node_type, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flow/{entity_type}/{entity_id}")
async def trace_flow(entity_type: str, entity_id: str):
    """Trace the O2C flow for a specific entity."""
    try:
        return get_entity_flow(entity_id, entity_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/broken-flows")
async def broken_flows():
    """Find orders with broken/incomplete O2C flows."""
    try:
        return get_broken_flows()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def statistics():
    """Get graph statistics."""
    try:
        return get_graph_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
