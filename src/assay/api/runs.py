"""API endpoints for runs."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from assay.api.schemas import RunCreate, RunResponse
from assay.db.base import get_db
from assay.db.repositories.dataset import DatasetRepository
from assay.db.repositories.run import RunRepository

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: RunCreate,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Create a new run."""
    ds_repo = DatasetRepository(db)
    dataset = ds_repo.get(payload.dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {payload.dataset_id} not found",
        )

    run_repo = RunRepository(db)
    existing = run_repo.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run with name '{payload.name}' already exists",
        )

    run = run_repo.create(
        dataset_id=payload.dataset_id,
        name=payload.name,
        target_url=payload.target_url,
        config=payload.config,
    )
    return RunResponse.model_validate(run)


@router.get("", response_model=list[RunResponse])
def list_runs(
    dataset_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[RunResponse]:
    """List all runs, optionally filtered by dataset."""
    repo = RunRepository(db)
    runs = repo.list(dataset_id=dataset_id)
    return [RunResponse.model_validate(r) for r in runs]


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Get a run by ID."""
    repo = RunRepository(db)
    run = repo.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    return RunResponse.model_validate(run)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a run by ID."""
    repo = RunRepository(db)
    deleted = repo.delete(run_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )


@router.post("/{run_id}/start", response_model=RunResponse)
def start_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Mark a run as RUNNING."""
    repo = RunRepository(db)
    run = repo.mark_running(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    return RunResponse.model_validate(run)


@router.post("/{run_id}/complete", response_model=RunResponse)
def complete_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Mark a run as COMPLETED."""
    repo = RunRepository(db)
    run = repo.mark_completed(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    return RunResponse.model_validate(run)
