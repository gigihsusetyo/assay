"""Integration tests for the `assay gate` CLI command."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from typer.testing import CliRunner

from assay.cli.main import app
from assay.db import base as db_base
from assay.db.repositories.dataset import DatasetRepository, QuestionRepository
from assay.db.repositories.run import BaselineRepository, ResultRepository, RunRepository

runner = CliRunner()


@pytest.fixture
def use_test_db(test_engine, monkeypatch):
    """Point SessionLocal at the in-memory test engine.

    Both assay.db.base and assay.cli.main import SessionLocal, so we must
    patch both. The CLI module captures the name at import time.
    """
    from sqlalchemy.orm import sessionmaker

    import assay.cli.main as cli_main

    test_session_local = sessionmaker(
        bind=test_engine, autocommit=False, autoflush=False
    )
    monkeypatch.setattr(db_base, "SessionLocal", test_session_local)
    monkeypatch.setattr(cli_main, "SessionLocal", test_session_local)
    return test_session_local


def _seed_pass_scenario(test_engine):
    """Seed a baseline and a current run that both pass."""
    from sqlalchemy.orm import sessionmaker

    SL = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = SL()
    try:
        ds_repo = DatasetRepository(session)
        q_repo = QuestionRepository(session)
        run_repo = RunRepository(session)
        res_repo = ResultRepository(session)
        base_repo = BaselineRepository(session)

        ds = ds_repo.create(name="gate-ds")
        q = q_repo.create(dataset_id=ds.id, question="Q?")

        baseline_run = run_repo.create(
            dataset_id=ds.id, name="baseline-run", target_url="http://mock"
        )
        res_repo.create(
            run_id=baseline_run.id, question_id=q.id, groundedness=0.90, latency_ms=1000
        )
        base_repo.create(name="bl-pass", run_id=baseline_run.id)

        current_run = run_repo.create(
            dataset_id=ds.id, name="current-run", target_url="http://mock"
        )
        res_repo.create(
            run_id=current_run.id, question_id=q.id, groundedness=0.89, latency_ms=1000
        )

        return current_run.id
    finally:
        session.close()


def _seed_fail_scenario(test_engine):
    """Seed a baseline and a current run where groundedness regresses."""
    from sqlalchemy.orm import sessionmaker

    SL = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = SL()
    try:
        ds_repo = DatasetRepository(session)
        q_repo = QuestionRepository(session)
        run_repo = RunRepository(session)
        res_repo = ResultRepository(session)
        base_repo = BaselineRepository(session)

        ds = ds_repo.create(name="gate-ds-fail")
        q = q_repo.create(dataset_id=ds.id, question="Q?")

        baseline_run = run_repo.create(
            dataset_id=ds.id, name="baseline-run-fail", target_url="http://mock"
        )
        res_repo.create(
            run_id=baseline_run.id, question_id=q.id, groundedness=0.90, latency_ms=1000
        )
        base_repo.create(name="bl-fail", run_id=baseline_run.id)

        current_run = run_repo.create(
            dataset_id=ds.id, name="current-run-fail", target_url="http://mock"
        )
        res_repo.create(
            run_id=current_run.id, question_id=q.id, groundedness=0.50, latency_ms=1000
        )

        return current_run.id
    finally:
        session.close()


def _write_policy(tmp_path: Path) -> str:
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "version: 1\nthresholds:\n  groundedness: 5.0\n",
        encoding="utf-8",
    )
    return str(policy)


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


def test_gate_passes_exit_0(test_engine, use_test_db, tmp_path) -> None:
    run_id = _seed_pass_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        ["gate", "--baseline", "bl-pass", "--run", str(run_id), "--policy", policy_path],
    )
    assert result.exit_code == 0


def test_gate_fails_exit_1(test_engine, use_test_db, tmp_path) -> None:
    run_id = _seed_fail_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        ["gate", "--baseline", "bl-fail", "--run", str(run_id), "--policy", policy_path],
    )
    assert result.exit_code == 1


def test_gate_baseline_not_found_exit_2(test_engine, use_test_db, tmp_path) -> None:
    run_id = _seed_pass_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        ["gate", "--baseline", "nope", "--run", str(run_id), "--policy", policy_path],
    )
    assert result.exit_code == 2
    assert "not found" in result.stdout.lower()


def test_gate_run_not_found_exit_2(test_engine, use_test_db, tmp_path) -> None:
    _seed_pass_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        ["gate", "--baseline", "bl-pass", "--run", "99999", "--policy", policy_path],
    )
    assert result.exit_code == 2
    assert "not found" in result.stdout.lower()


def test_gate_policy_file_not_found_exit_2(test_engine, use_test_db) -> None:
    run_id = _seed_pass_scenario(test_engine)

    result = runner.invoke(
        app,
        [
            "gate",
            "--baseline", "bl-pass",
            "--run", str(run_id),
            "--policy", "/nonexistent/policy.yaml",
        ],
    )
    assert result.exit_code == 2
    assert "policy" in result.stdout.lower()


def test_gate_invalid_format_exit_2(test_engine, use_test_db, tmp_path) -> None:
    run_id = _seed_pass_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        [
            "gate",
            "--baseline", "bl-pass",
            "--run", str(run_id),
            "--policy", policy_path,
            "--format", "weird",
        ],
    )
    assert result.exit_code == 2
    assert "format" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Output formats
# ---------------------------------------------------------------------------


def test_gate_json_output(test_engine, use_test_db, tmp_path) -> None:
    run_id = _seed_pass_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        [
            "gate",
            "--baseline", "bl-pass",
            "--run", str(run_id),
            "--policy", policy_path,
            "--format", "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["baseline_name"] == "bl-pass"
    assert isinstance(payload["metrics"], list)


def test_gate_junit_output(test_engine, use_test_db, tmp_path) -> None:
    run_id = _seed_fail_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        [
            "gate",
            "--baseline", "bl-fail",
            "--run", str(run_id),
            "--policy", policy_path,
            "--format", "junit",
        ],
    )
    # JUnit is still printed even though the gate failed
    assert result.exit_code == 1
    root = ET.fromstring(result.stdout)
    assert root.tag == "testsuite"
    assert root.attrib["name"] == "assay-gate"
    failures = int(root.attrib["failures"])
    assert failures >= 1


def test_gate_text_output_pass(test_engine, use_test_db, tmp_path) -> None:
    run_id = _seed_pass_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        ["gate", "--baseline", "bl-pass", "--run", str(run_id), "--policy", policy_path],
    )
    assert result.exit_code == 0
    assert "PASSED" in result.stdout


def test_gate_text_output_fail(test_engine, use_test_db, tmp_path) -> None:
    run_id = _seed_fail_scenario(test_engine)
    policy_path = _write_policy(tmp_path)

    result = runner.invoke(
        app,
        ["gate", "--baseline", "bl-fail", "--run", str(run_id), "--policy", policy_path],
    )
    assert result.exit_code == 1
    assert "FAILED" in result.stdout
