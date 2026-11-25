import pytest
from fastapi.testclient import TestClient

import crm
import database


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Every test gets its own empty database and a working CRM."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(crm, "CRM_DOWN", False)
    database.init_db()


@pytest.fixture
def client():
    from api import app
    return TestClient(app)