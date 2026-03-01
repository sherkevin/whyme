"""Garden module schemas for API requests and responses."""

import uuid
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# Garden Nodes API Schemas
# ============================================================================

class GardenNode(BaseModel):
    """A node in the Garden knowledge graph.

    Represents a knowledge item (note, card, task, etc.) with its metadata.
    """
    id: uuid.UUID = Field(..., description="Node unique identifier")
    object_type: str = Field(..., description="Type of object (note, card, task, etc.)")
    title: Optional[str] = Field(None, description="Node title")
    created_at: datetime = Field(..., description="Creation timestamp")
    strong_connection_count: int = Field(default=0, description="Number of strong connections")
    snippet: Optional[str] = Field(None, description="Content snippet/preview")

    model_config = ConfigDict(from_attributes=True)


class GardenNodeListResponse(BaseModel):
    """Response for garden nodes list endpoint."""
    data: List[GardenNode] = Field(..., description="List of garden nodes")
    total: int = Field(..., description="Total count of nodes")
    limit: int = Field(..., description="Requested limit")
    offset: int = Field(..., description="Requested offset")


# ============================================================================
# Garden Edges API Schemas
# ============================================================================

class GardenEdgeBatchRequest(BaseModel):
    """Request for batch edge query.

    Returns strong edges where both from_id and to_id are in the provided list.
    """
    node_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="List of node IDs to query edges for"
    )


class GardenEdge(BaseModel):
    """An edge (connection) between two nodes in the Garden graph.

    Represents a relationship between two knowledge items.
    """
    id: uuid.UUID = Field(..., description="Edge unique identifier")
    from_id: uuid.UUID = Field(..., description="Source node ID")
    to_id: uuid.UUID = Field(..., description="Target node ID")
    type: str = Field(..., description="Edge type (related, support, contradict, reference)")
    relation_strength: float = Field(..., ge=0.0, le=1.0, description="Connection strength (0.0-1.0)")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class GardenEdgeBatchResponse(BaseModel):
    """Response for garden edges batch endpoint."""
    data: List[GardenEdge] = Field(..., description="List of strong edges")
    connections_count: int = Field(..., description="Total number of strong connections")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


# ============================================================================
# Garden Node Detail API Schemas
# ============================================================================

class ConnectedNode(BaseModel):
    """A node connected to the main node.

    Includes connection strength for sorting.
    """
    id: uuid.UUID = Field(..., description="Connected node ID")
    title: Optional[str] = Field(None, description="Connected node title")
    object_type: str = Field(..., description="Type of connected object")
    relation_strength: float = Field(..., ge=0.0, le=1.0, description="Connection strength")
    jump_url: str = Field(..., description="URL to navigate to this node")

    model_config = ConfigDict(from_attributes=True)


class GardenNodeDetail(BaseModel):
    """Detailed view of a garden node.

    Includes full node information plus connected nodes.
    """
    id: uuid.UUID = Field(..., description="Node unique identifier")
    object_type: str = Field(..., description="Type of object")
    title: Optional[str] = Field(None, description="Node title")
    type: str = Field(..., description="Specific type")
    time: datetime = Field(..., description="Node time (created_at)")
    summary: Optional[str] = Field(None, description="Node summary/description")
    jump_url: str = Field(..., description="URL to navigate to this node")
    connected_nodes: List[ConnectedNode] = Field(
        default_factory=list,
        description="Up to 5 connected nodes sorted by relation_strength"
    )

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# User Stats Schema (for /auth/me endpoint)
# ============================================================================

class UserGardenStats(BaseModel):
    """User's garden statistics.

    Aggregated metrics about the user's knowledge graph.
    """
    total_notes: int = Field(..., description="Total number of active notes/cards")
    neural_connections: int = Field(..., description="Unique strong connections (undirected graph)")
    generated_insights: int = Field(..., description="Stable insights with level >= 2")


class UserInfoWithStats(BaseModel):
    """User info response with garden statistics.

    Extends basic user info with garden stats.
    """
    id: uuid.UUID = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    settings: Dict[str, Any] = Field(default_factory=dict, description="User settings")
    is_active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="Account creation time")
    stats: Optional[UserGardenStats] = Field(None, description="Garden statistics")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Today Insight API Schemas
# ============================================================================

class InsightSource(BaseModel):
    """A source item for an insight.

    Represents one piece of evidence supporting the insight.
    """
    id: uuid.UUID = Field(..., description="Source item ID")
    title: Optional[str] = Field(None, description="Source item title")
    item_type: str = Field(..., description="Type of source item")

    model_config = ConfigDict(from_attributes=True)


class DailyInsightResponse(BaseModel):
    """Response for daily insight endpoint.

    Structured insight data for rendering.
    """
    id: uuid.UUID = Field(..., description="Insight ID")
    claim: str = Field(..., description="Main claim/statement of the insight")
    rationale: str = Field(..., description="Reasoning/explanation")
    implications: List[str] = Field(..., description="List of implications")
    level: int = Field(..., ge=1, le=3, description="Insight level (1-3)")
    status: str = Field(..., description="Insight status (draft, candidate, stable, rejected)")
    evidence_count: int = Field(..., description="Number of evidence items")
    sources: List[InsightSource] = Field(
        default_factory=list,
        description="Source items supporting this insight"
    )
    created_at: datetime = Field(..., description="Insight creation time")
    updated_at: datetime = Field(..., description="Last update time")

    model_config = ConfigDict(from_attributes=True)


class TodayInsightListResponse(BaseModel):
    """Response for today insights list endpoint."""
    data: List[DailyInsightResponse] = Field(..., description="List of insights")
    day: str = Field(..., description="Date in YYYY-MM-DD format")
    total: int = Field(..., description="Total count")


# ============================================================================
# Error Schemas
# ============================================================================

class GardenErrorResponse(BaseModel):
    """Error response for Garden API endpoints."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application-specific error code")
