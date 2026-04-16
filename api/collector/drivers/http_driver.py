"""HTTP REST driver for MCBT 2.0 (Multicabeçote) integration.

The MCBT is a Toradex-based machine that exposes HTTP REST + WebSocket APIs.
This driver acts as an HTTP client, fetching data from the MCBT's Pistache
server and mapping it to the ME2 domain model (word_status, parts_ok, etc.).

Unlike PLC drivers that read individual registers, the HttpDriver fetches
all data in one HTTP call and caches it. Subsequent read_variable() calls
within the same polling cycle resolve from cache (TTL-based).

See docs/INTEGRATION_ME2.md for the full integration spec.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .base import BaseDriver

logger = logging.getLogger(__name__)

# MCBT firmware hardcodes UTC-3 (São Paulo) for all timestamps
_MCBT_TZ = timezone(timedelta(hours=-3))


class HttpDriver(BaseDriver):
    """HTTP REST driver for MCBT 2.0 equipment.

    Fetches data from the MCBT's HTTP API, caches responses per-cycle,
    and derives ME2-compatible values (word_status, parts_ok, etc.).

    Address dict shapes:
        Derived variables:  {"source": "derived", "derivation": "word_status"}
        Dashboard fields:   {"source": "dashboard", "field": "systemInfo.cpuTemp"}
        Recipe fields:      {"source": "recipe", "field": "name"}
    """

    CACHE_TTL_S = 30.0
    REQUEST_TIMEOUT_S = 10.0
    MAX_PACKAGES_FETCH = 20

    def __init__(
        self,
        host: str,
        http_port: int = 8080,
        name: str = "http",
        auth: dict | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(host=host, port=http_port, name=name, **kwargs)
        self._base_url = f"http://{host}:{http_port}"
        self._auth_config = dict(auth) if auth else {}

        # Resolve env-var passwords like ${MCBT_PASSWORD_MEI_2024_0100}
        password = self._auth_config.get("password", "")
        if isinstance(password, str) and password.startswith("${") and password.endswith("}"):
            env_key = password[2:-1]
            self._auth_config["password"] = os.environ.get(env_key, "")
            if not self._auth_config["password"]:
                logger.warning("[%s] Env var '%s' not set — auth may fail", name, env_key)

        self._client: httpx.AsyncClient | None = None
        self._jwt_token: str | None = None

        # Per-cycle cache
        self._cache: dict[str, Any] = {}
        self._cache_ts: float = 0.0

        # State for parts_ok derivation
        self._last_seen_package_ts: str | None = None
        self._cumulative_parts_ok: int = 0

    # ------------------------------------------------------------------
    # BaseDriver interface
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Create HTTP client, authenticate, and verify connectivity."""
        try:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.REQUEST_TIMEOUT_S),
            )

            # Authenticate if config provides credentials
            if self._auth_config.get("user"):
                if not await self._login():
                    logger.warning("[%s] MCBT login failed — continuing without auth", self.name)

            # Health check — fetch dashboardData to verify connectivity
            data = await self._http_get("/dashboardData")
            if data is not None:
                logger.info("[%s] MCBT connected at %s", self.name, self._base_url)
                return True

            logger.warning("[%s] MCBT health check failed at %s", self.name, self._base_url)
            return False

        except Exception:
            logger.exception("[%s] Failed to connect to MCBT at %s", self.name, self._base_url)
            return False

    async def disconnect(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._jwt_token = None
        self._cache.clear()
        self._cache_ts = 0.0
        logger.info("[%s] MCBT disconnected", self.name)

    async def is_connected(self) -> bool:
        """Return True if client exists and last fetch was recent."""
        if self._client is None:
            return False
        # Consider connected if we had a successful cache refresh recently
        return (time.monotonic() - self._cache_ts) < (self.CACHE_TTL_S * 5)

    async def read_variable(self, address: dict) -> Any:
        """Read a variable from cached MCBT data.

        Address dict:
            {"source": "derived", "derivation": "word_status"|"parts_ok"|"cycle_time"|"product_no"}
            {"source": "dashboard", "field": "dot.delimited.path"}
            {"source": "recipe", "field": "dot.delimited.path"}
        """
        if not await self._ensure_cache():
            return None

        source = address.get("source", "derived")

        if source == "derived":
            return self._cache.get(address.get("derivation", ""))

        if source == "dashboard":
            return _resolve_dotted(self._cache.get("_dashboard", {}), address.get("field", ""))

        if source == "recipe":
            return _resolve_dotted(self._cache.get("_recipe", {}), address.get("field", ""))

        logger.warning("[%s] Unknown MCBT address source '%s'", self.name, source)
        return None

    async def write_variable(self, address: dict, value: Any) -> bool:
        """Write is NOT supported for MCBT from ME2. See INTEGRATION_ME2.md §8.7."""
        logger.error(
            "[%s] Write to MCBT is not allowed from ME2 collector (address=%s)",
            self.name,
            address,
        )
        return False

    # ------------------------------------------------------------------
    # Cache layer
    # ------------------------------------------------------------------

    async def _ensure_cache(self) -> bool:
        """Fetch data from MCBT if cache is stale. Return True if cache is valid."""
        now = time.monotonic()
        if self._cache and (now - self._cache_ts) < self.CACHE_TTL_S:
            return True

        # Reconnect if client was lost
        if self._client is None:
            if not await self.connect():
                return False

        # Fetch all endpoints
        dashboard = await self._http_get("/dashboardData")
        if dashboard is None:
            return False

        packages = await self._http_get(f"/history/lastPackages/{self.MAX_PACKAGES_FETCH}")
        recipe = await self._http_get("/recipe/getActiveRecipe")

        # Derive ME2-compatible values
        self._cache = {
            "word_status": self._derive_word_status(dashboard),
            "parts_ok": self._derive_parts_ok(packages),
            "cycle_time": self._derive_cycle_time(packages),
            "product_no": recipe.get("rec_name", "") if isinstance(recipe, dict) else "",
            "_dashboard": dashboard,
            "_recipe": recipe or {},
        }
        self._cache_ts = now
        return True

    # ------------------------------------------------------------------
    # Derivation: word_status
    # ------------------------------------------------------------------

    def _derive_word_status(self, dashboard: dict) -> int:
        """Derive ME2 word_status from MCBT dashboard fields.

        See docs/INTEGRATION_ME2.md §4 for the mapping table.
        """
        is_running = dashboard.get("isRunning", False)
        is_in_error = dashboard.get("isInError", False)
        pkg_status = dashboard.get("packageMachineStatus") or {}
        state = pkg_status.get("state", "")
        sanitization = dashboard.get("sanitizationMode", False)
        paused = dashboard.get("paused", False)

        if is_in_error:
            return 32   # Failure

        if not is_running and sanitization:
            return 64   # Setup (higienização)

        if paused:
            return 17   # Planned Stop

        if is_running and state in ("PACKAGING", "REJECTING"):
            return 18   # Uptime

        if is_running and state == "READY":
            return 16   # Idle

        # Central cone disabled → starving
        central = dashboard.get("centralCone") or {}
        if central.get("status") == "DISABLED":
            return 20   # Starving

        return 16       # Idle (safe fallback)

    # ------------------------------------------------------------------
    # Derivation: parts_ok
    # ------------------------------------------------------------------

    def _derive_parts_ok(self, packages: Any) -> int:
        """Count new packages since last fetch to increment cumulative counter."""
        if not isinstance(packages, list) or not packages:
            return self._cumulative_parts_ok

        # Sort ascending by timestamp
        sorted_pkgs = sorted(packages, key=lambda p: p.get("timestamp", ""))

        new_count = 0
        for pkg in sorted_pkgs:
            pkg_ts = pkg.get("timestamp", "")
            if self._last_seen_package_ts is None or pkg_ts > self._last_seen_package_ts:
                new_count += 1

        if sorted_pkgs:
            latest_ts = sorted_pkgs[-1].get("timestamp")
            if latest_ts:
                self._last_seen_package_ts = latest_ts

        self._cumulative_parts_ok += new_count
        return self._cumulative_parts_ok

    # ------------------------------------------------------------------
    # Derivation: cycle_time
    # ------------------------------------------------------------------

    def _derive_cycle_time(self, packages: Any) -> float:
        """Average time delta between consecutive packages (seconds)."""
        if not isinstance(packages, list) or len(packages) < 2:
            return 0.0

        sorted_pkgs = sorted(packages, key=lambda p: p.get("timestamp", ""))
        deltas: list[float] = []

        for i in range(1, len(sorted_pkgs)):
            t1 = _parse_mcbt_timestamp(sorted_pkgs[i - 1].get("timestamp", ""))
            t2 = _parse_mcbt_timestamp(sorted_pkgs[i].get("timestamp", ""))
            if t1 and t2:
                delta = (t2 - t1).total_seconds()
                if delta > 0:
                    deltas.append(delta)

        return round(sum(deltas) / len(deltas), 2) if deltas else 0.0

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _http_get(self, path: str) -> dict | list | None:
        """GET request with automatic re-auth on 401."""
        if self._client is None:
            return None

        url = f"{self._base_url}{path}"
        headers = self._auth_headers()

        try:
            response = await self._client.get(url, headers=headers)

            # Re-authenticate on 401
            if response.status_code == 401 and self._auth_config.get("user"):
                logger.warning("[%s] MCBT 401 on %s — re-authenticating", self.name, path)
                if await self._login():
                    response = await self._client.get(url, headers=self._auth_headers())
                else:
                    return None

            if response.status_code != 200:
                logger.warning(
                    "[%s] MCBT %s returned HTTP %d", self.name, path, response.status_code
                )
                return None

            return response.json()

        except httpx.TimeoutException:
            logger.warning("[%s] MCBT timeout on %s", self.name, path)
            return None
        except httpx.ConnectError:
            logger.warning("[%s] MCBT connection failed for %s", self.name, path)
            return None
        except Exception:
            logger.exception("[%s] MCBT request error on %s", self.name, path)
            return None

    async def _login(self) -> bool:
        """Authenticate with POST /usr/login and store JWT token."""
        if self._client is None:
            return False

        endpoint = self._auth_config.get("endpoint", "/usr/login")
        url = f"{self._base_url}{endpoint}"
        body = {
            "user": self._auth_config.get("user", ""),
            "password": self._auth_config.get("password", ""),
        }

        try:
            response = await self._client.post(url, json=body)
            if response.status_code == 200:
                data = response.json()
                self._jwt_token = data.get("token") or data.get("access_token")
                logger.info("[%s] MCBT login successful", self.name)
                return True
            else:
                logger.error(
                    "[%s] MCBT login failed (HTTP %d)", self.name, response.status_code
                )
                return False
        except Exception:
            logger.exception("[%s] MCBT login error", self.name)
            return False

    def _auth_headers(self) -> dict[str, str]:
        """Return Authorization header dict if JWT token is available."""
        if self._jwt_token:
            return {"Authorization": f"Bearer {self._jwt_token}"}
        return {}


# ------------------------------------------------------------------
# Module-level utilities
# ------------------------------------------------------------------

def _resolve_dotted(data: dict, path: str) -> Any:
    """Resolve a dot-delimited path from a nested dict.

    Example: _resolve_dotted({"a": {"b": 42}}, "a.b") → 42
    """
    if not path:
        return None
    current: Any = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _parse_mcbt_timestamp(ts_str: str) -> datetime | None:
    """Parse MCBT timestamp (hardcoded UTC-3) and return as UTC.

    MCBT stores timestamps as naive strings like "2026-04-16 14:30:45"
    which are implicitly in America/Sao_Paulo (UTC-3).
    """
    if not ts_str:
        return None
    try:
        naive = datetime.fromisoformat(ts_str)
        localized = naive.replace(tzinfo=_MCBT_TZ)
        return localized.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None
