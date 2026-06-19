import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.engine.executor import GraphValidationError, run_execution_background, validate_graph

router = APIRouter(prefix="/api/workflows", tags=["workflows"])
logger = logging.getLogger(__name__)


def _validate_graph_or_400(graph: dict) -> None:
    try:
        validate_graph(graph)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _log_background_task_exception(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except Exception:
        logger.exception("Erreur inattendue dans la tâche d'exécution en arrière-plan.")


@router.post("", response_model=schemas.WorkflowOut, status_code=status.HTTP_201_CREATED)
def create_workflow(workflow: schemas.WorkflowCreate, db: Session = Depends(get_db)):
    _validate_graph_or_400(workflow.graph.model_dump())
    return crud.create_workflow(db, workflow)


@router.get("", response_model=list[schemas.WorkflowOut])
def list_workflows(db: Session = Depends(get_db)):
    return crud.list_workflows(db)


@router.get("/{workflow_id}", response_model=schemas.WorkflowOut)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = crud.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.put("/{workflow_id}", response_model=schemas.WorkflowOut)
def update_workflow(workflow_id: int, workflow_update: schemas.WorkflowUpdate, db: Session = Depends(get_db)):
    workflow = crud.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow_update.graph is not None:
        _validate_graph_or_400(workflow_update.graph.model_dump())
    return crud.update_workflow(db, workflow, workflow_update)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = crud.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    crud.delete_workflow(db, workflow)


@router.get("/{workflow_id}/export", response_model=schemas.WorkflowOut)
def export_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = crud.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("/import", response_model=schemas.WorkflowOut, status_code=status.HTTP_201_CREATED)
def import_workflow(payload: schemas.WorkflowImportRequest, db: Session = Depends(get_db)):
    _validate_graph_or_400(payload.graph.model_dump())
    workflow = schemas.WorkflowCreate(name=payload.name, version=payload.version, graph=payload.graph)
    return crud.create_workflow(db, workflow)


@router.post("/{workflow_id}/run", response_model=schemas.RunResponse)
async def run_workflow(workflow_id: int, db: Session = Depends(get_db)):
    workflow = crud.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _validate_graph_or_400(workflow.graph)

    execution = crud.create_execution(db, workflow_id)
    task = asyncio.create_task(run_execution_background(execution.id))
    task.add_done_callback(_log_background_task_exception)
    return schemas.RunResponse(execution_id=execution.id)
