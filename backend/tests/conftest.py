import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dsar_api import create_app  # noqa: E402
from dsar_api.extensions import db  # noqa: E402

SERVICE = {"X-API-Key": "test-service-key"}
DPO = {"X-API-Key": "test-dpo-key"}


@pytest.fixture()
def app():
    app = create_app("testing")
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seeded(client):
    r = client.post("/api/users", json={"user_id": "72839102", "nombre": "Juan Pérez", "email": "juan@email.com"},
                    headers=SERVICE)
    assert r.status_code == 201
    return "72839102"
