"""Tests for the protected demo application."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_products():
    response = client.get("/api/products")
    assert response.status_code == 200
    assert [p["name"] for p in response.json()["products"]] == [
        "Sentinel Basic",
        "Sentinel Pro",
    ]


def test_current_user():
    response = client.get("/api/users/me")
    assert response.status_code == 200
    assert response.json() == {"id": 42, "name": "Demo Operator", "role": "analyst"}


def test_catch_all_echoes_method_and_path():
    response = client.post("/api/orders/7")
    assert response.status_code == 200
    assert response.json() == {
        "service": "protected-demo-app",
        "method": "POST",
        "path": "/api/orders/7",
        "status": "ok",
    }


def test_docs_disabled():
    # Swagger UI is off; /docs falls through to the catch-all echo instead.
    response = client.get("/docs")
    assert response.status_code == 200
    assert response.json()["path"] == "/docs"
