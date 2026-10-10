import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("payload", [[1, 2], 'hello', 123, True])
def test_rejects_malformed_item(client, payload):
    resp = client.post("/items", json=payload)
    assert resp.status_code == 400
