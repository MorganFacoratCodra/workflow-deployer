from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    on: str | None = None


class NodeSchema(BaseModel):
    id: str
    type: str
    position: dict[str, float] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class GraphSchema(BaseModel):
    nodes: list[NodeSchema] = Field(default_factory=list)
    edges: list[EdgeSchema] = Field(default_factory=list)


class WorkflowBase(BaseModel):
    name: str
    version: int = 1
    graph: GraphSchema


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    version: int | None = None
    graph: GraphSchema | None = None


class WorkflowOut(WorkflowBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NodeRunOut(BaseModel):
    id: int
    execution_id: int
    node_id: str
    status: str
    logs: str
    duration_ms: int | None

    class Config:
        from_attributes = True


class ExecutionOut(BaseModel):
    id: int
    workflow_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    node_runs: list[NodeRunOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class RunResponse(BaseModel):
    execution_id: int


class WorkflowImportRequest(BaseModel):
    name: str
    version: int = 1
    graph: GraphSchema
