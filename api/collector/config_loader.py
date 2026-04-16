"""Loader and validator for the equipment configuration file (equipment.json)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = ("serial_number", "protocol", "connection")


class ConfigLoader:
    """Reads, validates, and caches the equipment configuration.

    Usage::

        loader = ConfigLoader("config/equipment.json")
        loader.load()
        for eq in loader.get_equipment_configs():
            ...
    """

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._data: dict[str, Any] = {}
        self._equipments: list[dict[str, Any]] = []
        self._mtime: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Read and parse the JSON configuration file.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
            ValueError: If required fields are missing.
        """
        logger.info("Loading equipment config from %s", self._path)

        if not self._path.exists():
            raise FileNotFoundError(f"Config file not found: {self._path}")

        with open(self._path, encoding="utf-8") as fh:
            raw = json.load(fh)

        self._mtime = os.path.getmtime(self._path)
        self._data = raw

        # Accept either a top-level list or {"equipments": [...]}
        if isinstance(raw, list):
            equipments = raw
        elif isinstance(raw, dict):
            equipments = raw.get("equipments", raw.get("equipment", []))
        else:
            raise ValueError("Unexpected config format — expected list or object")

        validated: list[dict[str, Any]] = []
        for idx, eq in enumerate(equipments):
            self._validate(eq, idx)
            self._normalize_variables(eq)
            validated.append(eq)

        self._equipments = validated
        logger.info("Loaded %d equipment config(s)", len(self._equipments))

    def get_equipment_configs(self) -> list[dict[str, Any]]:
        """Return the list of validated equipment configuration dicts."""
        return list(self._equipments)

    def reload(self) -> bool:
        """Reload the file only if it has been modified on disk.

        Returns True if the file was actually reloaded, False otherwise.
        """
        try:
            current_mtime = os.path.getmtime(self._path)
        except OSError:
            logger.warning("Cannot stat config file %s", self._path)
            return False

        if current_mtime <= self._mtime:
            return False

        logger.info("Config file changed — reloading %s", self._path)
        try:
            self.load()
            return True
        except Exception:
            logger.exception("Failed to reload config %s — keeping previous data", self._path)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(eq: dict, index: int) -> None:
        """Ensure that required fields are present in a single equipment dict."""
        for field in _REQUIRED_FIELDS:
            if field not in eq:
                raise ValueError(
                    f"Equipment entry #{index} is missing required field '{field}'"
                )

        conn = eq["connection"]
        if not isinstance(conn, dict) or not conn.get("host"):
            raise ValueError(
                f"Equipment '{eq.get('serial_number', index)}' has invalid "
                f"'connection' — must be a dict with at least a 'host' key"
            )

    # ------------------------------------------------------------------
    # Variable normalisation
    # ------------------------------------------------------------------

    # Variable names that map directly to a role (everything else -> "process")
    _KNOWN_ROLES = frozenset({
        "word_status", "parts_ok", "cycle_time",
        "product_no", "serial_number",
    })

    # Modbus equipment.json type -> driver type understood by ModbusDriver
    _MODBUS_TYPE_MAP: dict[str, str] = {
        "uint16": "word",
        "uint32": "dword",
        "int16": "word",
        "float32": "real",
        "string": "string",
        "bool": "bit",
    }

    # S7 equipment.json type -> driver type understood by Snap7Driver
    _S7_TYPE_MAP: dict[str, str] = {
        "uint16": "word",
        "uint32": "dword",
        "int16": "word",
        "float32": "real",
        "string": "string",
        "bool": "bit",
    }

    @classmethod
    def _normalize_variables(cls, eq: dict) -> None:
        """Transform the nested variables dict from equipment.json into the
        flat list-of-dicts format expected by ``_poll_equipment()``.

        After this call:
        - ``eq["variables"]`` is a ``list[dict]`` with keys: name, address, role.
        - ``eq["cycle_time_var"]`` is the address dict for the cycle_time variable
          (or ``None``).
        - ``eq["product_no_var"]`` is the address dict for the product_no variable
          (or ``None``).
        """
        raw_vars = eq.get("variables")
        if not isinstance(raw_vars, dict):
            # Already a list (or missing) — nothing to do
            return

        protocol = eq.get("protocol", "modbus")

        # HTTP / MCBT protocol — different variable format
        if protocol == "http":
            cls._normalize_http_variables(eq, raw_vars)
            return

        vendor_key = "schneider" if protocol == "modbus" else "siemens"

        vendor_vars: dict[str, dict] = raw_vars.get(vendor_key, {})
        if not vendor_vars:
            logger.warning(
                "Equipment '%s': no variables under key '%s'",
                eq.get("serial_number", "?"),
                vendor_key,
            )
            eq["variables"] = []
            return

        flat: list[dict[str, Any]] = []
        cycle_time_addr: dict | None = None
        product_no_addr: dict | None = None

        for var_name, var_def in vendor_vars.items():
            # Determine role
            role = var_name if var_name in cls._KNOWN_ROLES else "process"

            # Build the address dict the driver expects
            if protocol == "modbus":
                type_map = cls._MODBUS_TYPE_MAP
                driver_type = type_map.get(var_def.get("type", ""), var_def.get("type", "word"))
                addr: dict[str, Any] = {
                    "register": var_def["address"],
                    "type": driver_type,
                    "count": var_def.get("count", 1),
                    "overflow_fix": var_def.get("overflow_fix", False),
                }
                if "bit" in var_def:
                    addr["bit"] = var_def["bit"]
            else:
                # S7
                type_map = cls._S7_TYPE_MAP
                driver_type = type_map.get(var_def.get("type", ""), var_def.get("type", "word"))
                addr = {
                    "db": var_def["db"],
                    "byte": var_def["offset"],
                    "type": driver_type,
                }
                if "bit" in var_def:
                    addr["bit"] = var_def["bit"]
                if driver_type == "string":
                    # S7 STRING: size includes the 2-byte header; length is the
                    # payload the driver should read.
                    addr["length"] = var_def.get("size", 22) - 2

            # Stash direct-access addresses for cycle_time / product_no
            if var_name == "cycle_time":
                cycle_time_addr = addr
            elif var_name == "product_no":
                product_no_addr = addr

            # Skip cycle_time and product_no from the polling list — the
            # collector reads them inline when it encounters parts_ok.
            if var_name in ("cycle_time", "product_no"):
                continue

            flat.append({
                "name": var_name,
                "address": addr,
                "role": role,
            })

        eq["variables"] = flat
        eq["cycle_time_var"] = cycle_time_addr
        eq["product_no_var"] = product_no_addr

    # ------------------------------------------------------------------
    # HTTP / MCBT variable normalisation
    # ------------------------------------------------------------------

    @classmethod
    def _normalize_http_variables(cls, eq: dict, raw_vars: dict) -> None:
        """Normalize MCBT HTTP variables into the standard flat list format.

        MCBT variables use ``{"source": "derived", "derivation": "..."}``
        or ``{"source": "dashboard", "field": "..."}`` address dicts.
        """
        mcbt_vars: dict[str, dict] = raw_vars.get("mcbt", {})
        if not mcbt_vars:
            logger.warning(
                "Equipment '%s': no variables under key 'mcbt'",
                eq.get("serial_number", "?"),
            )
            eq["variables"] = []
            eq["cycle_time_var"] = None
            eq["product_no_var"] = None
            return

        flat: list[dict[str, Any]] = []
        cycle_time_addr: dict | None = None
        product_no_addr: dict | None = None

        for var_name, var_def in mcbt_vars.items():
            role = var_name if var_name in cls._KNOWN_ROLES else "process"

            # Build the address dict — HTTP uses source/derivation/field
            addr: dict[str, Any] = {
                "source": var_def.get("source", "derived"),
            }
            if "derivation" in var_def:
                addr["derivation"] = var_def["derivation"]
            if "field" in var_def:
                addr["field"] = var_def["field"]

            # Stash direct-access addresses for cycle_time / product_no
            if var_name == "cycle_time":
                cycle_time_addr = addr
            elif var_name == "product_no":
                product_no_addr = addr

            # Skip cycle_time and product_no from polling list
            if var_name in ("cycle_time", "product_no"):
                continue

            flat.append({
                "name": var_name,
                "address": addr,
                "role": role,
            })

        eq["variables"] = flat
        eq["cycle_time_var"] = cycle_time_addr
        eq["product_no_var"] = product_no_addr
