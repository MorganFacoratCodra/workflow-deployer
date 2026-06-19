from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas


def create_workflow(db: Session, workflow: schemas.WorkflowCreate) -> models.Workflow:
    db_workflow = models.Workflow(name=workflow.name, version=workflow.version, graph=workflow.graph.model_dump())
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow


def list_workflows(db: Session) -> list[models.Workflow]:
    return list(db.scalars(select(models.Workflow).order_by(models.Workflow.updated_at.desc())))


def get_workflow(db: Session, workflow_id: int) -> models.Workflow | None:
    return db.get(models.Workflow, workflow_id)


def update_workflow(db: Session, workflow: models.Workflow, data: schemas.WorkflowUpdate) -> models.Workflow:
    payload = data.model_dump(exclude_none=True)
    if "graph" in payload and payload["graph"] is not None:
        payload["graph"] = payload["graph"].model_dump()
    for key, value in payload.items():
        setattr(workflow, key, value)
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def delete_workflow(db: Session, workflow: models.Workflow) -> None:
    db.delete(workflow)
    db.commit()


def create_execution(db: Session, workflow_id: int) -> models.Execution:
    execution = models.Execution(workflow_id=workflow_id, status="pending")
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def list_executions(db: Session) -> list[models.Execution]:
    query = select(models.Execution).options(selectinload(models.Execution.node_runs)).order_by(models.Execution.started_at.desc())
    return list(db.scalars(query))


def get_execution(db: Session, execution_id: int) -> models.Execution | None:
    query = (
        select(models.Execution)
        .where(models.Execution.id == execution_id)
        .options(selectinload(models.Execution.node_runs))
    )
    return db.scalar(query)
