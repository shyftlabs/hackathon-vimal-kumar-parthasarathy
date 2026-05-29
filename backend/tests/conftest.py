"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from backend.api.server import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
