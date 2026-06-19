from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/api/executions", tags=["executions"])


@router.get("", response_model=list[schemas.ExecutionOut])
def list_executions(db: Session = Depends(get_db)):
    return crud.list_executions(db)


@router.get("/{execution_id}", response_model=schemas.ExecutionOut)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    execution = crud.get_execution(db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution
