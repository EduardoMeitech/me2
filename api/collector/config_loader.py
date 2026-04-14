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
