from fastapi.testclient import TestClient

from app.main import app


def test_health_check():
    """Test GET /api/health endpoint"""
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "newbody-content-auditor"


def test_health_check_response_schema():
    """Test /api/health response matches schema"""
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert isinstance(data["status"], str)
    assert isinstance(data["service"], str)
