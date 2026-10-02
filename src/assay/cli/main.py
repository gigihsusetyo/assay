"""Assay CLI entry point."""

import typer
from rich.console import Console
from rich.table import Table

from assay.db import models  # noqa: F401  (register models)
from assay.db.base import Base, SessionLocal, engine
from assay.db.repositories.dataset import DatasetRepository, QuestionRepository
from assay.db.repositories.run import RunRepository

# Ensure tables exist before any CLI command runs.
# This is idempotent and safe to call on every invocation.
Base.metadata.create_all(bind=engine)

app = typer.Typer(
    name="assay",
    help="The release gate for RAG systems",
    no_args_is_help=True,
)

dataset_app = typer.Typer(help="Manage datasets")
run_app = typer.Typer(help="Manage evaluation runs")

app.add_typer(dataset_app, name="dataset")
app.add_typer(run_app, name="run")

console = Console()


@app.command()
def version() -> None:
    """Show the Assay version."""
    console.print("Assay v0.1.0")


@app.command()
def health() -> None:
    """Check if the Assay API is reachable."""
    console.print("[yellow]Not implemented yet.[/yellow]")


# Dataset commands
@dataset_app.command("create")
def dataset_create(
    name: str = typer.Argument(..., help="Dataset name"),
    description: str = typer.Option(None, "--description", "-d", help="Dataset description"),
) -> None:
    """Create a new dataset."""
    session = SessionLocal()
    try:
        repo = DatasetRepository(session)
        existing = repo.get_by_name(name)
        if existing is not None:
            console.print(f"[red]Dataset '{name}' already exists.[/red]")
            raise typer.Exit(code=1)
        dataset = repo.create(name=name, description=description)
        console.print(f"[green]Created dataset:[/green] {dataset.name} (id={dataset.id})")
    finally:
        session.close()


@dataset_app.command("list")
def dataset_list() -> None:
    """List all datasets."""
    session = SessionLocal()
    try:
        repo = DatasetRepository(session)
        datasets = repo.list()
        if not datasets:
            console.print("[yellow]No datasets found.[/yellow]")
            return
        table = Table("ID", "Name", "Version", "Description")
        for d in datasets:
            table.add_row(str(d.id), d.name, d.version, d.description or "")
        console.print(table)
    finally:
        session.close()


@dataset_app.command("show")
def dataset_show(
    dataset_id: int = typer.Argument(..., help="Dataset ID"),
) -> None:
    """Show dataset details."""
    session = SessionLocal()
    try:
        repo = DatasetRepository(session)
        dataset = repo.get(dataset_id)
        if dataset is None:
            console.print(f"[red]Dataset {dataset_id} not found.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[bold]Dataset:[/bold] {dataset.name}")
        console.print(f"[bold]ID:[/bold] {dataset.id}")
        console.print(f"[bold]Version:[/bold] {dataset.version}")
        console.print(f"[bold]Description:[/bold] {dataset.description or '(none)'}")
        console.print(f"[bold]Created:[/bold] {dataset.created_at}")

        q_repo = QuestionRepository(session)
        count = q_repo.count_by_dataset(dataset_id)
        console.print(f"[bold]Questions:[/bold] {count}")
    finally:
        session.close()


# Run commands
@run_app.command("create")
def run_create(
    dataset_id: int = typer.Option(..., "--dataset", "-d", help="Dataset ID"),
    name: str = typer.Option(..., "--name", "-n", help="Run name"),
    target_url: str = typer.Option(..., "--target", "-t", help="Target RAG endpoint URL"),
) -> None:
    """Create a new run."""
    session = SessionLocal()
    try:
        ds_repo = DatasetRepository(session)
        dataset = ds_repo.get(dataset_id)
        if dataset is None:
            console.print(f"[red]Dataset {dataset_id} not found.[/red]")
            raise typer.Exit(code=1)

        run_repo = RunRepository(session)
        existing = run_repo.get_by_name(name)
        if existing is not None:
            console.print(f"[red]Run '{name}' already exists.[/red]")
            raise typer.Exit(code=1)

        run = run_repo.create(dataset_id=dataset_id, name=name, target_url=target_url)
        console.print(f"[green]Created run:[/green] {run.name} (id={run.id})")
    finally:
        session.close()


@run_app.command("list")
def run_list() -> None:
    """List all runs."""
    session = SessionLocal()
    try:
        repo = RunRepository(session)
        runs = repo.list()
        if not runs:
            console.print("[yellow]No runs found.[/yellow]")
            return
        table = Table("ID", "Name", "Dataset", "Status", "Target")
        for r in runs:
            table.add_row(str(r.id), r.name, str(r.dataset_id), r.status, r.target_url)
        console.print(table)
    finally:
        session.close()


@run_app.command("show")
def run_show(
    run_id: int = typer.Argument(..., help="Run ID"),
) -> None:
    """Show run details."""
    session = SessionLocal()
    try:
        repo = RunRepository(session)
        run = repo.get(run_id)
        if run is None:
            console.print(f"[red]Run {run_id} not found.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[bold]Run:[/bold] {run.name}")
        console.print(f"[bold]ID:[/bold] {run.id}")
        console.print(f"[bold]Dataset ID:[/bold] {run.dataset_id}")
        console.print(f"[bold]Status:[/bold] {run.status}")
        console.print(f"[bold]Target:[/bold] {run.target_url}")
        console.print(f"[bold]Created:[/bold] {run.created_at}")
        if run.started_at:
            console.print(f"[bold]Started:[/bold] {run.started_at}")
        if run.completed_at:
            console.print(f"[bold]Completed:[/bold] {run.completed_at}")
        if run.error_message:
            console.print(f"[bold red]Error:[/bold red] {run.error_message}")
    finally:
        session.close()


if __name__ == "__main__":
    app()


@app.command()
def gate(
    baseline: str = typer.Option(..., "--baseline", "-b", help="Baseline name"),
    current_run: int = typer.Option(..., "--run", "-r", help="Current run ID"),
    policy: str = typer.Option("examples/policy.yaml", "--policy", "-p", help="Policy file path"),
    top_failures: int = typer.Option(5, "--failures", "-f", help="Number of worst failures to show"),
) -> None:
    """Compare a run against a baseline and fail if quality regresses.

    Exit code 0 if passed, 1 if failed, 2 if error.
    """
    from assay.core.comparison.engine import compare_runs
    from assay.core.policy.loader import PolicyError, load_policy
    from assay.db.repositories.run import BaselineRepository, RunRepository

    session = SessionLocal()
    try:
        # Load policy
        try:
            thresholds = load_policy(policy)
        except PolicyError as e:
            console.print(f"[red]Policy error:[/red] {e}")
            raise typer.Exit(code=2) from e

        # Load baseline
        base_repo = BaselineRepository(session)
        baseline_obj = base_repo.get_by_name(baseline)
        if baseline_obj is None:
            console.print(f"[red]Baseline '{baseline}' not found.[/red]")
            raise typer.Exit(code=2)

        # Load run
        run_repo = RunRepository(session)
        run = run_repo.get(current_run)
        if run is None:
            console.print(f"[red]Run {current_run} not found.[/red]")
            raise typer.Exit(code=2)

        # Compare
        report = compare_runs(
            session,
            baseline=baseline_obj,
            current_run=run,
            thresholds=thresholds,
            top_failures=top_failures,
        )

        # Print report
        console.print("[bold]Assay Report[/bold]")
        console.print(f"Baseline: {report.baseline_name} (run {report.baseline_run_id})")
        console.print(f"Current:  run {report.current_run_id}")
        console.print()

        table = Table("Metric", "Baseline", "Current", "Delta", "Status")
        for m in report.metrics:
            base_str = f"{m.baseline_value:.3f}" if m.baseline_value is not None else "N/A"
            curr_str = f"{m.current_value:.3f}" if m.current_value is not None else "N/A"
            delta_str = f"{m.delta_percent:+.1f}%" if m.delta_percent is not None else "N/A"
            if m.passed is True:
                status_str = "[green]PASS[/green]"
            elif m.passed is False:
                status_str = "[red]FAIL[/red]"
            else:
                status_str = "-"
            table.add_row(m.name, base_str, curr_str, delta_str, status_str)
        console.print(table)
        console.print()

        if report.passed:
            console.print("[bold green]Verdict: PASSED[/bold green]")
        else:
            console.print("[bold red]Verdict: FAILED[/bold red]")
            for reason in report.reasons:
                console.print(f"  [red]-[/red] {reason}")

        if report.worst_failures:
            console.print()
            console.print("[bold]Worst failures:[/bold]")
            for f in report.worst_failures:
                console.print(
                    f"  Q{f.question_id} \"{f.question_text}\": "
                    f"{f.baseline_value:.2f} -> {f.current_value:.2f} "
                    f"(delta {f.delta:+.2f})"
                )

        if not report.passed:
            raise typer.Exit(code=1)
    finally:
        session.close()


@run_app.command("execute")
def run_execute(
    run_id: int = typer.Argument(..., help="Run ID to execute"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-question output"),
) -> None:
    """Execute a run: call the target for each question and store results."""
    from assay.core.executor import execute_run

    session = SessionLocal()
    try:
        try:
            summary = execute_run(session, run_id, verbose=verbose)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=2) from e

        console.print()
        console.print(f"[bold green]Run {summary.run_id} completed[/bold green]")
        console.print(f"Total questions: {summary.total}")
        console.print(f"Succeeded: [green]{summary.succeeded}[/green]")
        console.print(f"Failed: [red]{summary.failed}[/red]" if summary.failed else f"Failed: {summary.failed}")
        console.print(f"Total latency: {summary.total_latency_ms}ms")
        console.print(f"Total cost: ${summary.total_cost_usd:.4f}")
    finally:
        session.close()


@dataset_app.command("add-question")
def dataset_add_question(
    dataset_id: int = typer.Argument(..., help="Dataset ID"),
    question: str = typer.Option(..., "--question", "-q", help="Question text"),
    expected_answer: str = typer.Option(None, "--answer", "-a", help="Expected answer"),
    expected_context: str = typer.Option(None, "--context", "-c", help="Expected context"),
) -> None:
    """Add a question to a dataset."""
    session = SessionLocal()
    try:
        ds_repo = DatasetRepository(session)
        dataset = ds_repo.get(dataset_id)
        if dataset is None:
            console.print(f"[red]Dataset {dataset_id} not found.[/red]")
            raise typer.Exit(code=1)

        q_repo = QuestionRepository(session)
        q = q_repo.create(
            dataset_id=dataset_id,
            question=question,
            expected_answer=expected_answer,
            expected_context=expected_context,
        )
        console.print(f"[green]Added question:[/green] id={q.id} to dataset {dataset_id}")
    finally:
        session.close()


@dataset_app.command("import")
def dataset_import(
    file_path: str = typer.Argument(..., help="Path to JSON dataset file"),
    name: str = typer.Option(None, "--name", "-n", help="Override dataset name"),
    description: str = typer.Option(None, "--description", "-d", help="Override description"),
) -> None:
    """Import a dataset from a JSON file."""
    import json
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        raise typer.Exit(code=1)

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON:[/red] {e}")
        raise typer.Exit(code=1) from e

    if "questions" not in data or not isinstance(data["questions"], list):
        console.print("[red]JSON must have a 'questions' list.[/red]")
        raise typer.Exit(code=1)

    dataset_name = name or data.get("name")
    if not dataset_name:
        console.print("[red]Dataset name is required.[/red]")
        raise typer.Exit(code=1)

    dataset_description = description or data.get("description")
    dataset_version = data.get("version", "1.0.0")

    session = SessionLocal()
    try:
        ds_repo = DatasetRepository(session)
        existing = ds_repo.get_by_name(dataset_name)
        if existing is not None:
            console.print(f"[red]Dataset '{dataset_name}' already exists.[/red]")
            raise typer.Exit(code=1)

        ds = ds_repo.create(
            name=dataset_name,
            description=dataset_description,
            version=dataset_version,
        )
        console.print(f"[green]Created dataset:[/green] {ds.name} (id={ds.id})")

        q_repo = QuestionRepository(session)
        imported = 0
        skipped = 0

        for i, item in enumerate(data["questions"]):
            if not isinstance(item, dict):
                skipped += 1
                continue
            question_text = item.get("question")
            if not question_text:
                skipped += 1
                continue

            q_repo.create(
                dataset_id=ds.id,
                question=question_text,
                expected_answer=item.get("expected_answer"),
                expected_context=item.get("expected_context"),
            )
            imported += 1

        console.print(f"[green]Imported {imported} questions.[/green]")
        if skipped:
            console.print(f"[yellow]Skipped {skipped} items.[/yellow]")
    finally:
        session.close()
