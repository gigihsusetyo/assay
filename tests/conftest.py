"""Pytest fixtures for Assay tests."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from assay.db import models  # noqa: F401  (register models)
from assay.db.base import Base


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_session(test_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    test_session_local = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = test_session_local()
    try:
        yield session
    finally:
        session.close()
