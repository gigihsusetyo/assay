"""Pydantic schemas for API request and response."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# Dataset schemas
class DatasetCreate(BaseModel):
    """Request body to create a dataset."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    version: str = "1.0.0"


class DatasetResponse(BaseModel):
    """Response body for a dataset."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    version: str
    created_at: datetime


# Question schemas
class QuestionCreate(BaseModel):
    """Request body to create a question."""

    question: str = Field(..., min_length=1)
    expected_answer: str | None = None
    expected_context: str | None = None


class QuestionResponse(BaseModel):
    """Response body for a question."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    question: str
    expected_answer: str | None
    expected_context: str | None
    created_at: datetime


# Run schemas
class RunCreate(BaseModel):
    """Request body to create a run."""

    dataset_id: int
    name: str = Field(..., min_length=1, max_length=255)
    target_url: str = Field(..., min_length=1, max_length=500)
    config: str | None = None


class RunResponse(BaseModel):
    """Response body for a run."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    name: str
    target_url: str
    config: str | None
    status: str
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
