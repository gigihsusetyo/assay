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
def run_list(
    dataset_id: int = typer.Option(None, "--dataset", "-d", help="Filter by dataset ID"),
) -> None:
    """List all runs, optionally filtered by dataset."""
    session = SessionLocal()
    try:
        repo = RunRepository(session)
        runs = repo.list(dataset_id=dataset_id)
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


@app.command()
def gate(
    baseline: str = typer.Option(..., "--baseline", "-b", help="Baseline name"),
    current_run: int = typer.Option(..., "--run", "-r", help="Current run ID"),
    policy: str = typer.Option("examples/policy.yaml", "--policy", "-p", help="Policy file path"),
    top_failures: int = typer.Option(5, "--failures", "-f", help="Number of worst failures to show"),
    fmt: str = typer.Option("text", "--format", "-o", help="Output format: text, json, junit"),
) -> None:
    """Compare a run against a baseline and fail if quality regresses.

    Exit code 0 if passed, 1 if failed, 2 if error.
    """
    from assay.core.comparison.engine import compare_runs
    from assay.core.policy.loader import PolicyError, load_policy
    from assay.core.report import to_json, to_junit
    from assay.db.repositories.run import BaselineRepository, RunRepository

    if fmt not in ("text", "json", "junit"):
        console.print(f"[red]Invalid format:[/red] {fmt}. Use text, json, or junit.")
        raise typer.Exit(code=2)

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

        # Output based on format
        if fmt == "json":
            console.print(to_json(report))
        elif fmt == "junit":
            console.print(to_junit(report))
        else:
            # text format (default)
            console.print("[bold]Assay Report[/bold]")
            console.print(f"Baseline: {report.baseline_name} (run {report.baseline_run_id})")
            console.print(f"Current:  run {report.current_run_id}")
            console.print()

            table = Table(
                "Metric",
                "Baseline",
                "Current",
                "Δ abs",
                "Δ %",
                "Status",
                show_lines=False,
            )
            for m in report.metrics:
                base_str = f"{m.baseline_value:.3f}" if m.baseline_value is not None else "N/A"
                curr_str = f"{m.current_value:.3f}" if m.current_value is not None else "N/A"
                delta_abs_str = (
                    f"{m.delta_absolute:+.3f}" if m.delta_absolute is not None else "N/A"
                )
                delta_pct_str = (
                    f"{m.delta_percent:+.1f}%" if m.delta_percent is not None else "N/A"
                )
                if m.passed is True:
                    status_str = "[green]PASS[/green]"
                elif m.passed is False:
                    status_str = "[red]FAIL[/red]"
                else:
                    status_str = "-"
                table.add_row(
                    m.name, base_str, curr_str, delta_abs_str, delta_pct_str, status_str
                )
            console.print(table)
            console.print()

            if report.passed:
                console.print("[bold green]Verdict: PASSED[/bold green]")
            else:
                console.print("[bold red]Verdict: FAILED[/bold red]")
                for reason in report.reasons:
                    console.print(f"  [red]-[/red] {reason}")

        if fmt == "text" and report.worst_failures:
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
    judge: bool = typer.Option(False, "--judge", help="Use LLM-as-judge for groundedness"),
) -> None:
    """Execute a run: call the target for each question and store results."""
    from assay.core.executor import execute_run

    session = SessionLocal()
    try:
        try:
            summary = execute_run(session, run_id, verbose=verbose, use_judge=judge)
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
        if summary.judge_used:
            console.print(f"Judge used on [cyan]{summary.judge_used}[/cyan] questions")
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

        for item in data["questions"]:
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


baseline_app = typer.Typer(help="Manage baselines")
app.add_typer(baseline_app, name="baseline")


@baseline_app.command("create")
def baseline_create(
    name: str = typer.Option(..., "--name", "-n", help="Baseline name"),
    run_id: int = typer.Option(..., "--run", "-r", help="Run ID to pin as baseline"),
    description: str = typer.Option(None, "--description", "-d", help="Baseline description"),
) -> None:
    """Create a baseline from a completed run."""
    from assay.db.repositories.run import BaselineRepository, RunRepository

    session = SessionLocal()
    try:
        run_repo = RunRepository(session)
        run = run_repo.get(run_id)
        if run is None:
            console.print(f"[red]Run {run_id} not found.[/red]")
            raise typer.Exit(code=1)

        if run.status != "completed":
            console.print(f"[red]Run {run_id} has status '{run.status}'. Only completed runs can be pinned.[/red]")
            raise typer.Exit(code=1)

        base_repo = BaselineRepository(session)
        existing = base_repo.get_by_name(name)
        if existing is not None:
            console.print(f"[red]Baseline '{name}' already exists.[/red]")
            raise typer.Exit(code=1)

        baseline = base_repo.create(name=name, run_id=run_id, description=description)
        console.print(f"[green]Created baseline:[/green] {baseline.name} (id={baseline.id}, run_id={baseline.run_id})")
    finally:
        session.close()


@baseline_app.command("list")
def baseline_list() -> None:
    """List all baselines."""
    from assay.db.repositories.run import BaselineRepository

    session = SessionLocal()
    try:
        repo = BaselineRepository(session)
        baselines = repo.list()
        if not baselines:
            console.print("[yellow]No baselines found.[/yellow]")
            return
        table = Table("ID", "Name", "Run ID", "Description")
        for b in baselines:
            table.add_row(str(b.id), b.name, str(b.run_id), b.description or "")
        console.print(table)
    finally:
        session.close()


result_app = typer.Typer(help="Inspect evaluation results")
app.add_typer(result_app, name="result")


@result_app.command("list")
def result_list(
    run_id: int = typer.Option(..., "--run", "-r", help="Run ID"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of results"),
) -> None:
    """List results for a run."""
    from assay.db.repositories.run import ResultRepository

    session = SessionLocal()
    try:
        repo = ResultRepository(session)
        results = repo.list_by_run(run_id)
        if not results:
            console.print(f"[yellow]No results found for run {run_id}.[/yellow]")
            return

        table = Table("Q#", "Groundedness", "Recall", "Latency (ms)", "Cost (USD)", "Error")
        for r in results[:limit]:
            g = f"{r.groundedness:.2f}" if r.groundedness is not None else "-"
            rc = f"{r.context_recall:.2f}" if r.context_recall is not None else "-"
            lat = str(r.latency_ms) if r.latency_ms is not None else "-"
            cost = f"{r.cost_usd:.4f}" if r.cost_usd is not None else "-"
            err = "yes" if r.error_message else ""
            table.add_row(str(r.question_id), g, rc, lat, cost, err)
        console.print(table)
        console.print(f"[dim]Showing {min(len(results), limit)} of {len(results)} results.[/dim]")
    finally:
        session.close()


@dataset_app.command("delete")
def dataset_delete(
    dataset_id: int = typer.Argument(..., help="Dataset ID"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a dataset and all its questions."""
    session = SessionLocal()
    try:
        ds_repo = DatasetRepository(session)
        dataset = ds_repo.get(dataset_id)
        if dataset is None:
            console.print(f"[red]Dataset {dataset_id} not found.[/red]")
            raise typer.Exit(code=1)

        if not confirm:
            console.print(
                f"[yellow]About to delete dataset '{dataset.name}' "
                f"(id={dataset.id}) and all its questions.[/yellow]"
            )
            typer.confirm("Are you sure?", abort=True)

        ds_repo.delete(dataset_id)
        console.print(f"[green]Deleted dataset {dataset_id}.[/green]")
    finally:
        session.close()


@baseline_app.command("delete")
def baseline_delete(
    baseline_id: int = typer.Argument(..., help="Baseline ID"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a baseline."""
    from assay.db.repositories.run import BaselineRepository

    session = SessionLocal()
    try:
        repo = BaselineRepository(session)
        baseline = repo.get(baseline_id) if hasattr(repo, "get") else None

        if baseline is None:
            # Fallback: iterate list to find by id
            baselines = repo.list()
            baseline = next((b for b in baselines if b.id == baseline_id), None)

        if baseline is None:
            console.print(f"[red]Baseline {baseline_id} not found.[/red]")
            raise typer.Exit(code=1)

        if not confirm:
            console.print(f"[yellow]About to delete baseline '{baseline.name}' (id={baseline.id}).[/yellow]")
            typer.confirm("Are you sure?", abort=True)

        repo.delete(baseline_id)
        console.print(f"[green]Deleted baseline {baseline_id}.[/green]")
    finally:
        session.close()


@run_app.command("delete")
def run_delete(
    run_id: int = typer.Argument(..., help="Run ID"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a run and all its results."""
    session = SessionLocal()
    try:
        repo = RunRepository(session)
        run = repo.get(run_id)
        if run is None:
            console.print(f"[red]Run {run_id} not found.[/red]")
            raise typer.Exit(code=1)

        if not confirm:
            console.print(
                f"[yellow]About to delete run '{run.name}' "
                f"(id={run.id}) and all its results.[/yellow]"
            )
            typer.confirm("Are you sure?", abort=True)

        repo.delete(run_id)
        console.print(f"[green]Deleted run {run_id}.[/green]")
    finally:
        session.close()


question_app = typer.Typer(help="Inspect questions in a dataset")
app.add_typer(question_app, name="question")


@question_app.command("list")
def question_list(
    dataset_id: int = typer.Option(..., "--dataset", "-d", help="Dataset ID"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of questions"),
) -> None:
    """List questions in a dataset."""
    session = SessionLocal()
    try:
        ds_repo = DatasetRepository(session)
        dataset = ds_repo.get(dataset_id)
        if dataset is None:
            console.print(f"[red]Dataset {dataset_id} not found.[/red]")
            raise typer.Exit(code=1)

        q_repo = QuestionRepository(session)
        questions = q_repo.list_by_dataset(dataset_id)
        if not questions:
            console.print(f"[yellow]No questions in dataset {dataset_id}.[/yellow]")
            return

        table = Table("ID", "Question", "Has Answer", "Has Context")
        for q in questions[:limit]:
            q_text = q.question[:60] + "..." if len(q.question) > 60 else q.question
            has_answer = "yes" if q.expected_answer else ""
            has_context = "yes" if q.expected_context else ""
            table.add_row(str(q.id), q_text, has_answer, has_context)
        console.print(table)
        console.print(f"[dim]Showing {min(len(questions), limit)} of {len(questions)} questions.[/dim]")
    finally:
        session.close()


if __name__ == "__main__":
    app()
