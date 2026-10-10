import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_add_item(client):
    resp = client.post("/items", json={"name": "widget"})
    assert resp.status_code == 201
    assert resp.get_json() == {"id": 1, "name": "widget"}


def test_add_item_requires_name(client):
    resp = client.post("/items", json={})
    assert resp.status_code == 400


def test_list_items(client):
    client.post("/items", json={"name": "a"})
    client.post("/items", json={"name": "b"})
    resp = client.get("/items")
    assert resp.status_code == 200
    assert resp.get_json() == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
