"""Integration tests for ME2 API endpoints.

Requires a running PostgreSQL test database.
Run: cd api && TEST_DATABASE_URL="postgresql+asyncpg://me2:me2dev@localhost:5432/me2_test" pytest
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio

from api.core.models import Alert, ProductionEvent, StatusEvent


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    @pytest.mark.asyncio
    async def test_login_success(self, client, seed_data):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": seed_data["email"], "password": seed_data["password"]},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, seed_data):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": seed_data["email"], "password": "wrongpass"},
        )
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "test"},
        )
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

class TestEquipment:
    @pytest.mark.asyncio
    async def test_list_equipment(self, client, seed_data):
        res = await client.get("/api/v1/equipment")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1
        assert data["data"][0]["serial_number"] == "MEI-TEST-0001"

    @pytest.mark.asyncio
    async def test_equipment_live_no_data(self, client, seed_data):
        res = await client.get(f"/api/v1/equipment/{seed_data['equipment_id']}/live")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["serial_number"] == "MEI-TEST-0001"
        assert data["word_status"] is None

    @pytest.mark.asyncio
    async def test_equipment_not_found(self, client):
        fake_id = str(uuid4())
        res = await client.get(f"/api/v1/equipment/{fake_id}/live")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class TestAlerts:
    @pytest.mark.asyncio
    async def test_active_alerts_empty(self, client, seed_data):
        res = await client.get("/api/v1/alerts/active")
        assert res.status_code == 200
        assert res.json()["data"] == []

    @pytest.mark.asyncio
    async def test_active_alerts_with_data(self, client, seed_data, db_session):
        alert = Alert(
            equipment_id=seed_data["equipment_id"],
            level=1,
            message="Test alert",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(alert)
        await db_session.flush()

        res = await client.get("/api/v1/alerts/active")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) >= 1
        assert data[0]["equipment_name"] == "Teste Corte 01"
        assert data[0]["serial_number"] == "MEI-TEST-0001"

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, client, seed_data, db_session):
        alert = Alert(
            id=str(uuid4()),
            equipment_id=seed_data["equipment_id"],
            level=1,
            message="Test ack",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(alert)
        await db_session.flush()

        res = await client.post(f"/api/v1/alerts/{alert.id}/acknowledge")
        assert res.status_code == 200
        assert res.json()["data"]["acknowledged_at"] is not None

    @pytest.mark.asyncio
    async def test_acknowledge_already_acked(self, client, seed_data, db_session):
        alert = Alert(
            id=str(uuid4()),
            equipment_id=seed_data["equipment_id"],
            level=1,
            message="Already acked",
            started_at=datetime.now(timezone.utc),
            acknowledged_at=datetime.now(timezone.utc),
        )
        db_session.add(alert)
        await db_session.flush()

        res = await client.post(f"/api/v1/alerts/{alert.id}/acknowledge")
        assert res.status_code == 409

    @pytest.mark.asyncio
    async def test_acknowledge_not_found(self, client):
        res = await client.post(f"/api/v1/alerts/{uuid4()}/acknowledge")
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_alert_summary(self, client, seed_data, db_session):
        # Add L1 and L2 active alerts
        db_session.add(Alert(
            equipment_id=seed_data["equipment_id"], level=1,
            message="L1", started_at=datetime.now(timezone.utc),
        ))
        db_session.add(Alert(
            equipment_id=seed_data["equipment_id"], level=2,
            message="L2", started_at=datetime.now(timezone.utc),
        ))
        await db_session.flush()

        res = await client.get("/api/v1/alerts/summary")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["active_total"] >= 2
        assert data["active_l1"] >= 1
        assert data["active_l2"] >= 1

    @pytest.mark.asyncio
    async def test_alert_history(self, client, seed_data, db_session):
        db_session.add(Alert(
            equipment_id=seed_data["equipment_id"], level=1,
            message="Resolved", started_at=datetime.now(timezone.utc),
            resolved_at=datetime.now(timezone.utc),
        ))
        await db_session.flush()

        res = await client.get("/api/v1/alerts/history?days=7")
        assert res.status_code == 200
        data = res.json()["data"]
        assert len(data) >= 1


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------

class TestProduction:
    @pytest.mark.asyncio
    async def test_production_no_data(self, client, seed_data):
        res = await client.get(
            f"/api/v1/equipment/{seed_data['equipment_id']}/production",
            params={"date": "2026-04-16"},
        )
        assert res.status_code == 200
        assert res.json()["data"] == []

    @pytest.mark.asyncio
    async def test_production_with_shift(self, client, seed_data):
        res = await client.get(
            f"/api/v1/equipment/{seed_data['equipment_id']}/production",
            params={"date": "2026-04-16", "shift": "T100"},
        )
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_production_invalid_date(self, client, seed_data):
        res = await client.get(
            f"/api/v1/equipment/{seed_data['equipment_id']}/production",
            params={"date": "not-a-date"},
        )
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class TestReports:
    @pytest.mark.asyncio
    async def test_shift_report_no_data(self, client, seed_data):
        res = await client.get(
            "/api/v1/reports/shift",
            params={
                "equipment_id": seed_data["equipment_id"],
                "date": "2026-04-16",
                "shift": "T100",
            },
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["equipment_name"] == "Teste Corte 01"
        assert data["total_parts"] == 0
        assert data["shift"] == "T100"
        assert data["shift_label"] == "Turno 1"

    @pytest.mark.asyncio
    async def test_shift_report_invalid_shift(self, client, seed_data):
        res = await client.get(
            "/api/v1/reports/shift",
            params={
                "equipment_id": seed_data["equipment_id"],
                "date": "2026-04-16",
                "shift": "INVALID",
            },
        )
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_shift_report_equipment_not_found(self, client):
        res = await client.get(
            "/api/v1/reports/shift",
            params={
                "equipment_id": str(uuid4()),
                "date": "2026-04-16",
                "shift": "T100",
            },
        )
        assert res.status_code == 404
