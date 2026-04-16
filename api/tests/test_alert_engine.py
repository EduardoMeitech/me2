"""Unit tests for the AlertEngine — no database required."""

from datetime import datetime, timedelta, timezone

import pytest

from api.collector.alert_engine import AlertEngine


@pytest.fixture
def engine():
    return AlertEngine()


@pytest.fixture
def config():
    return {
        "uptime_status_code": 18,
        "downtime_l1_min": 10,
        "downtime_l2_min": 30,
        "alert_recipients": [],
    }


class TestAlertEngineUptime:
    """Tests for machines in uptime status."""

    def test_uptime_no_prior_downtime_returns_none(self, engine, config):
        result = engine.check_status("MEI-001", 18, config)
        assert result is None

    def test_uptime_clears_downtime_without_alert(self, engine, config):
        # Start downtime
        engine.check_status("MEI-001", 32, config)
        # Back to uptime before L1 threshold
        result = engine.check_status("MEI-001", 18, config)
        assert result is None
        assert "MEI-001" not in engine._downtime_start

    def test_uptime_after_l1_emits_resolution(self, engine, config):
        # Simulate L1 alert already fired
        engine._downtime_start["MEI-001"] = datetime.now(timezone.utc) - timedelta(minutes=15)
        engine._alert_sent["MEI-001"] = 1

        result = engine.check_status("MEI-001", 18, config)
        assert result is not None
        assert result.level == 0  # resolution
        assert result.downtime_minutes > 0
        assert "MEI-001" not in engine._downtime_start


class TestAlertEngineDowntime:
    """Tests for machines in downtime status."""

    def test_first_downtime_starts_tracking(self, engine, config):
        result = engine.check_status("MEI-001", 32, config)
        assert result is None  # no alert yet
        assert "MEI-001" in engine._downtime_start

    def test_l1_fires_at_threshold(self, engine, config):
        # Pretend downtime started 11 minutes ago
        engine._downtime_start["MEI-001"] = datetime.now(timezone.utc) - timedelta(minutes=11)
        engine._alert_sent["MEI-001"] = 0

        result = engine.check_status("MEI-001", 32, config)
        assert result is not None
        assert result.level == 1
        assert result.serial_number == "MEI-001"

    def test_l1_does_not_fire_twice(self, engine, config):
        engine._downtime_start["MEI-001"] = datetime.now(timezone.utc) - timedelta(minutes=15)
        engine._alert_sent["MEI-001"] = 1

        result = engine.check_status("MEI-001", 32, config)
        assert result is None  # already sent L1

    def test_l2_fires_at_threshold(self, engine, config):
        engine._downtime_start["MEI-001"] = datetime.now(timezone.utc) - timedelta(minutes=35)
        engine._alert_sent["MEI-001"] = 1

        result = engine.check_status("MEI-001", 32, config)
        assert result is not None
        assert result.level == 2

    def test_l2_does_not_fire_twice(self, engine, config):
        engine._downtime_start["MEI-001"] = datetime.now(timezone.utc) - timedelta(minutes=40)
        engine._alert_sent["MEI-001"] = 2

        result = engine.check_status("MEI-001", 32, config)
        assert result is None

    def test_no_thresholds_configured(self, engine):
        config_no_thresh = {"uptime_status_code": 18, "alert_recipients": []}
        engine.check_status("MEI-001", 32, config_no_thresh)
        result = engine.check_status("MEI-001", 32, config_no_thresh)
        assert result is None


class TestAlertEngineCustomUptimeCode:
    """Tests for custom uptime_status_code (e.g., 19)."""

    def test_custom_uptime_code(self, engine):
        config = {"uptime_status_code": 19, "downtime_l1_min": 5, "alert_recipients": []}
        # Status 18 is NOT uptime in this config
        engine.check_status("MEI-002", 18, config)
        assert "MEI-002" in engine._downtime_start

        # Status 19 IS uptime
        engine.check_status("MEI-002", 19, config)
        assert "MEI-002" not in engine._downtime_start


class TestAlertEngineMultipleEquipment:
    """Tests that equipment tracking is independent."""

    def test_independent_tracking(self, engine, config):
        engine.check_status("MEI-001", 32, config)
        engine.check_status("MEI-002", 18, config)

        assert "MEI-001" in engine._downtime_start
        assert "MEI-002" not in engine._downtime_start

    def test_l1_on_one_does_not_affect_other(self, engine, config):
        engine._downtime_start["MEI-001"] = datetime.now(timezone.utc) - timedelta(minutes=11)
        engine._alert_sent["MEI-001"] = 0

        result_001 = engine.check_status("MEI-001", 32, config)
        result_002 = engine.check_status("MEI-002", 32, config)

        assert result_001 is not None and result_001.level == 1
        assert result_002 is None
