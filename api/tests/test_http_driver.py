"""Unit tests for HttpDriver — MCBT 2.0 integration.

No real HTTP server required — all requests are mocked via httpx.MockTransport.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api.collector.drivers.http_driver import HttpDriver, _parse_mcbt_timestamp, _resolve_dotted


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def driver():
    """Create an HttpDriver instance without connecting."""
    d = HttpDriver(
        host="192.168.1.230",
        http_port=8080,
        name="MEI-TEST-MCBT",
        auth={"endpoint": "/usr/login", "user": "meitech", "password": "testpass"},
    )
    return d


def _make_dashboard(
    is_running=True,
    is_in_error=False,
    state="PACKAGING",
    sanitization=False,
    paused=False,
    central_cone_status="ENABLED",
):
    """Build a minimal MCBT dashboardData response."""
    return {
        "machineType": "MCBT",
        "version": "250815",
        "isRunning": is_running,
        "isInError": is_in_error,
        "sanitizationMode": sanitization,
        "paused": paused,
        "packageMachineStatus": {"state": state, "notReadyTimeSeconds": 0},
        "centralCone": {"status": central_cone_status, "weight": 500},
        "systemInfo": {"cpuTemp": 55.2, "cpuUsage": 23.1},
    }


def _make_packages(count=5, base_time="2026-04-16 10:00:00", interval_s=5):
    """Build a list of package history records."""
    pkgs = []
    base = datetime.fromisoformat(base_time)
    for i in range(count):
        ts = base + timedelta(seconds=i * interval_s)
        pkgs.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "recipeId": 1,
            "weight": 800 + i,
            "moduleIds": "1,2,3",
            "modulesWeights": "300,250,250",
        })
    return pkgs


# ---------------------------------------------------------------------------
# word_status derivation
# ---------------------------------------------------------------------------

class TestDeriveWordStatus:
    def test_running_packaging_returns_18(self, driver):
        d = _make_dashboard(is_running=True, state="PACKAGING")
        assert driver._derive_word_status(d) == 18

    def test_running_rejecting_returns_18(self, driver):
        d = _make_dashboard(is_running=True, state="REJECTING")
        assert driver._derive_word_status(d) == 18

    def test_running_ready_returns_16_idle(self, driver):
        d = _make_dashboard(is_running=True, state="READY")
        assert driver._derive_word_status(d) == 16

    def test_error_returns_32(self, driver):
        d = _make_dashboard(is_in_error=True, state="PACKAGING")
        assert driver._derive_word_status(d) == 32

    def test_sanitization_returns_64(self, driver):
        d = _make_dashboard(is_running=False, sanitization=True)
        assert driver._derive_word_status(d) == 64

    def test_paused_returns_17(self, driver):
        d = _make_dashboard(is_running=True, paused=True)
        assert driver._derive_word_status(d) == 17

    def test_central_cone_disabled_returns_20(self, driver):
        d = _make_dashboard(is_running=True, state="READY", central_cone_status="DISABLED")
        # Running + READY first → Idle (16), but central cone disabled → Starving (20)
        # The derivation checks is_running + READY before centralCone, so:
        # Actually, running + READY returns 16 before reaching centralCone check.
        # Let's test with not running to hit the centralCone branch.
        d2 = _make_dashboard(is_running=False, central_cone_status="DISABLED")
        assert driver._derive_word_status(d2) == 20

    def test_fallback_returns_16(self, driver):
        d = _make_dashboard(is_running=False)
        assert driver._derive_word_status(d) == 16

    def test_error_takes_priority_over_running(self, driver):
        d = _make_dashboard(is_running=True, is_in_error=True, state="PACKAGING")
        assert driver._derive_word_status(d) == 32


# ---------------------------------------------------------------------------
# parts_ok derivation
# ---------------------------------------------------------------------------

class TestDerivePartsOk:
    def test_counts_all_packages_on_first_call(self, driver):
        pkgs = _make_packages(count=5)
        result = driver._derive_parts_ok(pkgs)
        assert result == 5

    def test_deduplicates_on_second_call(self, driver):
        pkgs = _make_packages(count=5)
        driver._derive_parts_ok(pkgs)
        # Same packages again — no new count
        result = driver._derive_parts_ok(pkgs)
        assert result == 5

    def test_increments_with_new_packages(self, driver):
        pkgs1 = _make_packages(count=3, base_time="2026-04-16 10:00:00")
        driver._derive_parts_ok(pkgs1)
        assert driver._cumulative_parts_ok == 3

        pkgs2 = _make_packages(count=2, base_time="2026-04-16 10:00:15")
        driver._derive_parts_ok(pkgs2)
        assert driver._cumulative_parts_ok == 5

    def test_empty_packages_returns_current(self, driver):
        driver._cumulative_parts_ok = 42
        result = driver._derive_parts_ok([])
        assert result == 42

    def test_none_packages_returns_current(self, driver):
        driver._cumulative_parts_ok = 10
        result = driver._derive_parts_ok(None)
        assert result == 10


# ---------------------------------------------------------------------------
# cycle_time derivation
# ---------------------------------------------------------------------------

class TestDeriveCycleTime:
    def test_calculates_average_delta(self, driver):
        pkgs = _make_packages(count=4, interval_s=6)
        result = driver._derive_cycle_time(pkgs)
        assert result == 6.0

    def test_single_package_returns_zero(self, driver):
        pkgs = _make_packages(count=1)
        assert driver._derive_cycle_time(pkgs) == 0.0

    def test_empty_returns_zero(self, driver):
        assert driver._derive_cycle_time([]) == 0.0
        assert driver._derive_cycle_time(None) == 0.0


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

class TestParseTimestamp:
    def test_converts_utc_minus_3_to_utc(self):
        result = _parse_mcbt_timestamp("2026-04-16 12:00:00")
        assert result is not None
        assert result.tzinfo == timezone.utc
        # 12:00 UTC-3 = 15:00 UTC
        assert result.hour == 15

    def test_empty_returns_none(self):
        assert _parse_mcbt_timestamp("") is None

    def test_invalid_returns_none(self):
        assert _parse_mcbt_timestamp("not-a-date") is None


# ---------------------------------------------------------------------------
# Dotted path resolution
# ---------------------------------------------------------------------------

class TestResolveDotted:
    def test_single_key(self):
        assert _resolve_dotted({"a": 42}, "a") == 42

    def test_nested_key(self):
        assert _resolve_dotted({"a": {"b": {"c": 99}}}, "a.b.c") == 99

    def test_missing_key(self):
        assert _resolve_dotted({"a": 1}, "b") is None

    def test_empty_path(self):
        assert _resolve_dotted({"a": 1}, "") is None

    def test_non_dict_intermediate(self):
        assert _resolve_dotted({"a": 42}, "a.b") is None


# ---------------------------------------------------------------------------
# read_variable via cache
# ---------------------------------------------------------------------------

class TestReadVariable:
    @pytest.mark.asyncio
    async def test_derived_word_status(self, driver):
        # Pre-populate cache
        driver._cache = {
            "word_status": 18,
            "parts_ok": 100,
            "cycle_time": 5.5,
            "product_no": "Coxinha 800g",
            "_dashboard": {},
            "_recipe": {},
        }
        driver._cache_ts = __import__("time").monotonic()

        result = await driver.read_variable({"source": "derived", "derivation": "word_status"})
        assert result == 18

    @pytest.mark.asyncio
    async def test_derived_parts_ok(self, driver):
        driver._cache = {"parts_ok": 42, "word_status": 18, "_dashboard": {}, "_recipe": {}}
        driver._cache_ts = __import__("time").monotonic()

        result = await driver.read_variable({"source": "derived", "derivation": "parts_ok"})
        assert result == 42

    @pytest.mark.asyncio
    async def test_dashboard_field(self, driver):
        driver._cache = {
            "_dashboard": {"systemInfo": {"cpuTemp": 55.2}},
            "_recipe": {},
            "word_status": 18,
        }
        driver._cache_ts = __import__("time").monotonic()

        result = await driver.read_variable({"source": "dashboard", "field": "systemInfo.cpuTemp"})
        assert result == 55.2

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cache(self, driver):
        # No cache, no client → None
        result = await driver.read_variable({"source": "derived", "derivation": "word_status"})
        assert result is None


# ---------------------------------------------------------------------------
# write_variable
# ---------------------------------------------------------------------------

class TestWriteVariable:
    @pytest.mark.asyncio
    async def test_write_returns_false(self, driver):
        result = await driver.write_variable({"field": "anything"}, 42)
        assert result is False


# ---------------------------------------------------------------------------
# Auth / env-var resolution
# ---------------------------------------------------------------------------

class TestEnvVarResolution:
    def test_resolves_env_var_password(self):
        with patch.dict("os.environ", {"MCBT_PW_TEST": "secret123"}):
            d = HttpDriver(
                host="127.0.0.1",
                auth={"user": "test", "password": "${MCBT_PW_TEST}"},
            )
            assert d._auth_config["password"] == "secret123"

    def test_missing_env_var_sets_empty(self):
        d = HttpDriver(
            host="127.0.0.1",
            auth={"user": "test", "password": "${NONEXISTENT_VAR_XYZ}"},
        )
        assert d._auth_config["password"] == ""
