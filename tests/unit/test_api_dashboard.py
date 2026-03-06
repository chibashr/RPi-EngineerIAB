"""Unit tests for Dashboard API routes."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Phase 1: API routes stubbed; Phase 3 will restore")
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
