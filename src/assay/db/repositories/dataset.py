"""Repository for Dataset and Question models."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from assay.db.models import Dataset, Question


class DatasetRepository:
    """CRUD operations for Dataset."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, name: str, description: str | None = None, version: str = "1.0.0") -> Dataset:
        """Create a new dataset."""
        dataset = Dataset(name=name, description=description, version=version)
        self.session.add(dataset)
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    def get(self, dataset_id: int) -> Dataset | None:
        """Get a dataset by ID."""
        return self.session.get(Dataset, dataset_id)

    def get_by_name(self, name: str) -> Dataset | None:
        """Get a dataset by name."""
        stmt = select(Dataset).where(Dataset.name == name)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(self) -> list[Dataset]:
        """List all datasets."""
        stmt = select(Dataset).order_by(Dataset.created_at.desc())
        return list(self.session.execute(stmt).scalars().all())

    def delete(self, dataset_id: int) -> bool:
        """Delete a dataset by ID. Returns True if deleted."""
        dataset = self.get(dataset_id)
        if dataset is None:
            return False
        self.session.delete(dataset)
        self.session.commit()
        return True


class QuestionRepository:
    """CRUD operations for Question."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        dataset_id: int,
        question: str,
        expected_answer: str | None = None,
        expected_context: str | None = None,
    ) -> Question:
        """Create a new question."""
        q = Question(
            dataset_id=dataset_id,
            question=question,
            expected_answer=expected_answer,
            expected_context=expected_context,
        )
        self.session.add(q)
        self.session.commit()
        self.session.refresh(q)
        return q

    def list_by_dataset(self, dataset_id: int) -> list[Question]:
        """List all questions in a dataset."""
        stmt = select(Question).where(Question.dataset_id == dataset_id).order_by(Question.id)
        return list(self.session.execute(stmt).scalars().all())

    def count_by_dataset(self, dataset_id: int) -> int:
        """Count questions in a dataset."""
        stmt = select(Question).where(Question.dataset_id == dataset_id)
        return len(list(self.session.execute(stmt).scalars().all()))
