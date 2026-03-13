"""Unit tests for Dashboard API routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestDashboardStatus:
    """Tests for GET /api/v1/dashboard/status."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/dashboard/status")
        assert r.status_code == 200

    def test_returns_aggregated_data(self, client):
        r = client.get("/api/v1/dashboard/status")
        data = r.json()
        assert "data" in data
        d = data["data"]
        assert "resources" in d
        assert "services" in d
        assert "alerts" in d
        assert "interfaces" in d
        assert "captures" in d
        assert "devices" in d
        assert "tools" in d

    def test_handles_all_manager_failures(self, client, monkeypatch):
        """When all concurrent tasks fail, response returns empty defaults."""
        from services.api_gateway.routes import dashboard

        def raise_error():
            raise RuntimeError("Manager failed")

        monkeypatch.setattr(dashboard._system_manager, "get_status", raise_error)
        monkeypatch.setattr(dashboard._network_manager, "list_interfaces", raise_error)
        monkeypatch.setattr(dashboard._monitor_service, "get_status", raise_error)
        monkeypatch.setattr(dashboard._remote_manager, "get_status", raise_error)

        r = client.get("/api/v1/dashboard/status")

        assert r.status_code == 200
        d = r.json()["data"]
        assert d["resources"] == {}
        assert d["services"] == {}
        assert d["interfaces"] == []
        assert d["tools"] == []

    def test_partial_failure_returns_successful_data(self, client, monkeypatch):
        """When some tasks fail, successful results are still included."""
        from services.api_gateway.routes import dashboard

        def raise_error():
            raise RuntimeError("Manager failed")

        monkeypatch.setattr(dashboard._system_manager, "get_status", raise_error)
        monkeypatch.setattr(
            dashboard._network_manager,
            "list_interfaces",
            lambda: {"interfaces": [{"id": "eth0"}]},
        )

        r = client.get("/api/v1/dashboard/status")

        assert r.status_code == 200
        d = r.json()["data"]
        assert d["resources"] == {}
        assert d["services"] == {}
        assert len(d["interfaces"]) == 1
        assert d["interfaces"][0]["id"] == "eth0"

    def test_alerts_sorted_by_timestamp_desc(self, client, monkeypatch):
        """Alerts with timestamps are sorted descending (newest first)."""
        from services.api_gateway.routes import dashboard
        from services import logging_service as log_svc

        alerts = [
            {"message": "old", "timestamp": "2024-01-01T00:00:00Z"},
            {"message": "new", "timestamp": "2024-12-31T23:59:59Z"},
            {"message": "mid", "timestamp": "2024-06-15T12:00:00Z"},
        ]

        monkeypatch.setattr(dashboard._monitor_service, "get_status", lambda: {"alerts": []})
        monkeypatch.setattr(log_svc.logging_service, "get_recent_log_alerts", lambda limit=30: alerts)

        r = client.get("/api/v1/dashboard/status")

        d = r.json()["data"]
        timestamps = [a.get("timestamp", "") for a in d["alerts"]]
        assert timestamps == sorted(timestamps, reverse=True)
        assert d["alerts"][0]["message"] == "new"
        assert d["alerts"][-1]["message"] == "old"

    def test_alerts_with_none_timestamps_dont_crash(self, client, monkeypatch):
        """Alerts with None timestamps don't crash sorting."""
        from services.api_gateway.routes import dashboard
        from services import logging_service as log_svc

        alerts = [
            {"message": "no_ts"},
            {"message": "has_ts", "timestamp": "2024-06-15T12:00:00Z"},
            {"message": "null_ts", "timestamp": None},
        ]

        monkeypatch.setattr(dashboard._monitor_service, "get_status", lambda: {"alerts": []})
        monkeypatch.setattr(log_svc.logging_service, "get_recent_log_alerts", lambda limit=30: alerts)

        r = client.get("/api/v1/dashboard/status")

        assert r.status_code == 200
        assert len(r.json()["data"]["alerts"]) == 3

    def test_alerts_capped_at_50(self, client, monkeypatch):
        """Combined alerts from monitor and logging_service capped at 50."""
        from services.api_gateway.routes import dashboard
        from services import logging_service as log_svc

        monitor_alerts = [{"message": f"monitor_{i}", "timestamp": f"2024-01-{i+1:02d}T00:00:00Z"} for i in range(30)]
        log_alerts = [{"message": f"log_{i}", "timestamp": f"2024-02-{i+1:02d}T00:00:00Z"} for i in range(30)]

        monkeypatch.setattr(dashboard._monitor_service, "get_status", lambda: {"alerts": monitor_alerts})
        monkeypatch.setattr(log_svc.logging_service, "get_recent_log_alerts", lambda limit=30: log_alerts)

        r = client.get("/api/v1/dashboard/status")

        d = r.json()["data"]
        assert len(d["alerts"]) == 50

    def test_log_alerts_exception_handled_gracefully(self, client, monkeypatch):
        """Exception in get_recent_log_alerts is handled without crashing."""
        from services.api_gateway.routes import dashboard
        from services import logging_service as log_svc

        def raise_error(limit=30):
            raise RuntimeError("Log service error")

        monkeypatch.setattr(log_svc.logging_service, "get_recent_log_alerts", raise_error)
        monkeypatch.setattr(dashboard._monitor_service, "get_status", lambda: {"alerts": [{"message": "test"}]})

        r = client.get("/api/v1/dashboard/status")

        assert r.status_code == 200
        assert len(r.json()["data"]["alerts"]) == 1
