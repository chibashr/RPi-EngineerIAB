import pytest

from services.api_gateway.main import create_app
from services.api_gateway.routes import system as system_routes


@pytest.mark.integration
def test_health_check():
    app = create_app()
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["status"] == "healthy"


@pytest.mark.integration
def test_system_status_includes_monitor_data(monkeypatch):
    app = create_app()
    client = app.test_client()

    monkeypatch.setattr(system_routes, "_system_manager", type("Stub", (), {"get_status": lambda *_: {"status": "healthy"}})())
    monkeypatch.setattr(
        system_routes,
        "_monitor_service",
        type("Stub", (), {"get_status": lambda *_: {"health": {"status": "healthy"}, "alerts": []}})(),
    )

    response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["status"] == "healthy"
    assert payload["data"]["health"]["status"] == "healthy"
