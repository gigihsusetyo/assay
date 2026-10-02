"""Assay CLI entry point."""

import typer
from rich.console import Console
from rich.table import Table

from assay.db.base import SessionLocal
from assay.db.repositories.dataset import DatasetRepository, QuestionRepository
from assay.db.repositories.run import RunRepository

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
