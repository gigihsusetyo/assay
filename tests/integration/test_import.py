"""Integration tests for dataset import validation."""

import json
from pathlib import Path

from typer.testing import CliRunner

from assay.cli.main import app

runner = CliRunner()


def test_import_missing_file() -> None:
    """Import fails if file does not exist."""
    result = runner.invoke(app, ["dataset", "import", "/nonexistent/file.json"])
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_import_invalid_json(tmp_path: Path) -> None:
    """Import fails if JSON is invalid."""
    dataset_file = tmp_path / "invalid.json"
    dataset_file.write_text("not a valid json")

    result = runner.invoke(app, ["dataset", "import", str(dataset_file)])
    assert result.exit_code == 1
    assert "Invalid JSON" in result.stdout


def test_import_missing_questions_key(tmp_path: Path) -> None:
    """Import fails if JSON has no 'questions' key."""
    dataset_file = tmp_path / "no_questions.json"
    dataset_file.write_text(json.dumps({"name": "test"}))

    result = runner.invoke(app, ["dataset", "import", str(dataset_file)])
    assert result.exit_code == 1
    assert "questions" in result.stdout


def test_import_missing_name(tmp_path: Path) -> None:
    """Import fails if no name is provided and JSON has no name."""
    dataset_file = tmp_path / "no_name.json"
    dataset_file.write_text(json.dumps({"questions": []}))

    result = runner.invoke(app, ["dataset", "import", str(dataset_file)])
    assert result.exit_code == 1
    assert "name" in result.stdout.lower()
