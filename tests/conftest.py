"""Pytest configuration for the PaperMinder server tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import configure_database, reset_database  # noqa: E402
from src.main import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_url = f"sqlite:///{tmp_path / 'paperminder-test.db'}"
    configure_database(database_url)
    reset_database(database_url)

    app = create_app(database_url=database_url)
    with TestClient(app) as test_client:
        yield test_client
