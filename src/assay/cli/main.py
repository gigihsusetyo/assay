"""Assay CLI entry point."""

import typer
from rich.console import Console

app = typer.Typer(
    name="assay",
    help="The release gate for RAG systems",
    no_args_is_help=True,
)

console = Console()


@app.command()
def version() -> None:
    """Show the Assay version."""
    console.print("Assay v0.1.0")


@app.command()
def health() -> None:
    """Check if the Assay API is reachable."""
    console.print("[yellow]Not implemented yet.[/yellow]")


if __name__ == "__main__":
    app()
