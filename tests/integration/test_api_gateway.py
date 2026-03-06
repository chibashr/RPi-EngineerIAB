import pytest

from services.api_gateway.main import create_app
from services.api_gateway.routes import system as system_routes
from services.api_gateway.routes import updates as updates_routes


@pytest.mark.integration
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "healthy"


@pytest.mark.integration
@pytest.mark.skip(reason="Phase 1: API routes stubbed; Phase 3 will restore")
def test_system_status_includes_monitor_data(client, monkeypatch):
    monkeypatch.setattr(system_routes, "_system_manager", type("Stub", (), {"get_status": lambda *_: {"status": "healthy"}})())
    monkeypatch.setattr(
        system_routes,
        "_monitor_service",
        type("Stub", (), {"get_status": lambda *_: {"health": {"status": "healthy"}, "alerts": []}})(),
    )
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["status"] == "healthy"
    assert payload["data"]["health"]["status"] == "healthy"


@pytest.mark.integration
def test_updates_apply_dry_run(client, monkeypatch):
    """POST /api/v1/updates/apply with dry run returns 200 and applied status."""
    mock_result = {
        "status": "applied",
        "dry_run": True,
        "previous_version": "a" * 7,
        "current_version": "b" * 7,
        "backup_path": "/data/backups/pre-update.zip",
    }
    monkeypatch.setattr(
        updates_routes.update_manager,
        "apply_update",
        lambda **kw: mock_result,
    )
    response = client.post("/api/v1/updates/apply")
    assert response.status_code == 200
    data = response.json().get("data", {})
    assert data.get("status") == "applied"
    assert data.get("dry_run") is True
    assert data.get("current_version") == "b" * 7


@pytest.mark.integration
def test_updates_apply_returns_500_on_runtime_error(client, monkeypatch):
    """POST /api/v1/updates/apply returns 500 when apply_update raises."""
    monkeypatch.setattr(
        updates_routes.update_manager,
        "apply_update",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("Update failed; rollback attempted: permission denied")),
    )
    response = client.post("/api/v1/updates/apply")
    assert response.status_code == 500
    payload = response.json()
    assert "error" in payload or "INTERNAL_ERROR" in str(payload)
