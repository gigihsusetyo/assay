"""Repository for Run, Result, and Baseline models."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from assay.db.models import Baseline, Result, Run, RunStatus


class RunRepository:
    """CRUD operations for Run."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        dataset_id: int,
        name: str,
        target_url: str,
        config: str | None = None,
    ) -> Run:
        """Create a new run in PENDING status."""
        run = Run(
            dataset_id=dataset_id,
            name=name,
            target_url=target_url,
            config=config,
            status=RunStatus.PENDING.value,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get(self, run_id: int) -> Run | None:
        """Get a run by ID."""
        return self.session.get(Run, run_id)

    def get_by_name(self, name: str) -> Run | None:
        """Get a run by name."""
        stmt = select(Run).where(Run.name == name)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(self, dataset_id: int | None = None) -> list[Run]:
        """List all runs, optionally filtered by dataset."""
        stmt = select(Run).order_by(Run.created_at.desc())
        if dataset_id is not None:
            stmt = stmt.where(Run.dataset_id == dataset_id)
        return list(self.session.execute(stmt).scalars().all())

    def mark_running(self, run_id: int) -> Run | None:
        """Mark a run as RUNNING and set started_at."""
        run = self.get(run_id)
        if run is None:
            return None
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(run)
        return run

    def mark_completed(self, run_id: int) -> Run | None:
        """Mark a run as COMPLETED and set completed_at."""
        run = self.get(run_id)
        if run is None:
            return None
        run.status = RunStatus.COMPLETED.value
        run.completed_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(run)
        return run

    def mark_failed(self, run_id: int, error_message: str) -> Run | None:
        """Mark a run as FAILED with an error message."""
        run = self.get(run_id)
        if run is None:
            return None
        run.status = RunStatus.FAILED.value
        run.error_message = error_message
        run.completed_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(run)
        return run

    def delete(self, run_id: int) -> bool:
        """Delete a run by ID."""
        run = self.get(run_id)
        if run is None:
            return False
        self.session.delete(run)
        self.session.commit()
        return True


class ResultRepository:
    """CRUD operations for Result."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        run_id: int,
        question_id: int,
        answer: str | None = None,
        retrieved_contexts: str | None = None,
        groundedness: float | None = None,
        context_recall: float | None = None,
        latency_ms: int | None = None,
        cost_usd: float | None = None,
        error_message: str | None = None,
    ) -> Result:
        """Create a new result for a run and question."""
        result = Result(
            run_id=run_id,
            question_id=question_id,
            answer=answer,
            retrieved_contexts=retrieved_contexts,
            groundedness=groundedness,
            context_recall=context_recall,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            error_message=error_message,
        )
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        return result

    def list_by_run(self, run_id: int) -> list[Result]:
        """List all results for a run."""
        stmt = select(Result).where(Result.run_id == run_id).order_by(Result.id)
        return list(self.session.execute(stmt).scalars().all())

    def count_by_run(self, run_id: int) -> int:
        """Count results for a run."""
        stmt = select(Result).where(Result.run_id == run_id)
        return len(list(self.session.execute(stmt).scalars().all()))


class BaselineRepository:
    """CRUD operations for Baseline."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        name: str,
        run_id: int,
        description: str | None = None,
    ) -> Baseline:
        """Create a new baseline pointing to a run."""
        baseline = Baseline(name=name, run_id=run_id, description=description)
        self.session.add(baseline)
        self.session.commit()
        self.session.refresh(baseline)
        return baseline

    def get_by_name(self, name: str) -> Baseline | None:
        """Get a baseline by name."""
        stmt = select(Baseline).where(Baseline.name == name)
        return self.session.execute(stmt).scalar_one_or_none()

    def list(self) -> list[Baseline]:
        """List all baselines."""
        stmt = select(Baseline).order_by(Baseline.created_at.desc())
        return list(self.session.execute(stmt).scalars().all())

    def delete(self, baseline_id: int) -> bool:
        """Delete a baseline by ID."""
        baseline = self.session.get(Baseline, baseline_id)
        if baseline is None:
            return False
        self.session.delete(baseline)
        self.session.commit()
        return True
