"""API endpoints for datasets and questions."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from assay.api.schemas import (
    DatasetCreate,
    DatasetResponse,
    QuestionCreate,
    QuestionResponse,
)
from assay.db.base import get_db
from assay.db.repositories.dataset import DatasetRepository, QuestionRepository

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def create_dataset(
    payload: DatasetCreate,
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Create a new dataset."""
    repo = DatasetRepository(db)
    existing = repo.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset with name '{payload.name}' already exists",
        )
    dataset = repo.create(
        name=payload.name,
        description=payload.description,
        version=payload.version,
    )
    return DatasetResponse.model_validate(dataset)


@router.get("", response_model=list[DatasetResponse])
def list_datasets(db: Session = Depends(get_db)) -> list[DatasetResponse]:
    """List all datasets."""
    repo = DatasetRepository(db)
    datasets = repo.list()
    return [DatasetResponse.model_validate(d) for d in datasets]


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
) -> DatasetResponse:
    """Get a dataset by ID."""
    repo = DatasetRepository(db)
    dataset = repo.get(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )
    return DatasetResponse.model_validate(dataset)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a dataset by ID."""
    repo = DatasetRepository(db)
    deleted = repo.delete(dataset_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )


@router.post(
    "/{dataset_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_question(
    dataset_id: int,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
) -> QuestionResponse:
    """Add a question to a dataset."""
    ds_repo = DatasetRepository(db)
    dataset = ds_repo.get(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )
    q_repo = QuestionRepository(db)
    question = q_repo.create(
        dataset_id=dataset_id,
        question=payload.question,
        expected_answer=payload.expected_answer,
        expected_context=payload.expected_context,
    )
    return QuestionResponse.model_validate(question)


@router.get("/{dataset_id}/questions", response_model=list[QuestionResponse])
def list_questions(
    dataset_id: int,
    db: Session = Depends(get_db),
) -> list[QuestionResponse]:
    """List all questions in a dataset."""
    ds_repo = DatasetRepository(db)
    dataset = ds_repo.get(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )
    q_repo = QuestionRepository(db)
    questions = q_repo.list_by_dataset(dataset_id)
    return [QuestionResponse.model_validate(q) for q in questions]
