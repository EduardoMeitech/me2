"""Data processor that detects changes in production, status, and process variables.

Only emits events when a value has actually changed compared to the last
reading, avoiding duplicate writes to the database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Event dataclasses
# ------------------------------------------------------------------

@dataclass
class ProductionEvent:
    """Emitted when the parts-OK counter changes."""
    serial_number: str
    timestamp: datetime
    parts_ok: int
    delta: int
    cycle_time_s: float
    product_no: int


@dataclass
class StatusEvent:
    """Emitted when the machine word-status changes."""
    serial_number: str
    timestamp: datetime
    word_status: int


@dataclass
class ProcessEvent:
    """Emitted when a named process variable changes."""
    serial_number: str
    timestamp: datetime
    var_name: str
    value: Any


# ------------------------------------------------------------------
# Processor
# ------------------------------------------------------------------

class DataProcessor:
    """Stateful processor that compares new readings to the last known values.

    Keeps per-equipment state so that events are only generated on actual
    transitions.
    """

    def __init__(self):
        self._last_parts_ok: dict[str, int] = {}
        self._last_word_status: dict[str, int] = {}
        self._last_process_vars: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Production
    # ------------------------------------------------------------------

    def process_production(
        self,
        serial_number: str,
        parts_ok: int,
        cycle_time_s: float,
        product_no: int,
        config: dict | None = None,
    ) -> ProductionEvent | None:
        """Return a ``ProductionEvent`` if *parts_ok* differs from the last reading.

        When the config contains ``"overflow_fix": true`` and *parts_ok* is
        negative (signed 16-bit overflow), 32768 is added to correct it.
        """
        # Overflow fix for signed 16-bit counters
        if config and config.get("overflow_fix"):
            if parts_ok < 0:
                parts_ok += 32768
                logger.debug(
                    "[%s] Applied overflow fix -> parts_ok=%d", serial_number, parts_ok
                )

        previous = self._last_parts_ok.get(serial_number)

        if previous is not None and parts_ok == previous:
            return None  # no change

        delta = 0
        if previous is not None:
            delta = parts_ok - previous
            # Handle counter wrap-around / reset
            if delta < 0:
                delta = parts_ok
                logger.info(
                    "[%s] Counter wrap-around detected (prev=%d, cur=%d)",
                    serial_number,
                    previous,
                    parts_ok,
                )

        self._last_parts_ok[serial_number] = parts_ok

        event = ProductionEvent(
            serial_number=serial_number,
            timestamp=datetime.now(tz=timezone.utc),
            parts_ok=parts_ok,
            delta=delta,
            cycle_time_s=cycle_time_s,
            product_no=product_no,
        )
        logger.info(
            "[%s] Production event: parts_ok=%d delta=%d cycle=%.2fs product=%d",
            serial_number,
            parts_ok,
            delta,
            cycle_time_s,
            product_no,
        )
        return event

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def process_status(
        self,
        serial_number: str,
        word_status: int,
    ) -> StatusEvent | None:
        """Return a ``StatusEvent`` if *word_status* differs from the last reading."""
        previous = self._last_word_status.get(serial_number)
        if previous is not None and word_status == previous:
            return None

        self._last_word_status[serial_number] = word_status

        event = StatusEvent(
            serial_number=serial_number,
            timestamp=datetime.now(tz=timezone.utc),
            word_status=word_status,
        )
        logger.info(
            "[%s] Status event: word_status=%d (prev=%s)",
            serial_number,
            word_status,
            previous,
        )
        return event

    # ------------------------------------------------------------------
    # Process variables
    # ------------------------------------------------------------------

    def process_variable(
        self,
        serial_number: str,
        var_name: str,
        value: Any,
    ) -> ProcessEvent | None:
        """Return a ``ProcessEvent`` if *value* differs from the last reading."""
        eq_vars = self._last_process_vars.setdefault(serial_number, {})
        previous = eq_vars.get(var_name)
        if previous is not None and value == previous:
            return None

        eq_vars[var_name] = value

        event = ProcessEvent(
            serial_number=serial_number,
            timestamp=datetime.now(tz=timezone.utc),
            var_name=var_name,
            value=value,
        )
        logger.debug(
            "[%s] Process event: %s=%s (prev=%s)",
            serial_number,
            var_name,
            value,
            previous,
        )
        return event

    # ------------------------------------------------------------------
    # Shift boundary support
    # ------------------------------------------------------------------

    def reset_shift_state(self) -> None:
        """Clear all cached last-values.

        Call this at shift boundaries so that the very next reading for
        every equipment is guaranteed to produce an event (even if the
        raw PLC value has not changed).
        """
        logger.info("Resetting DataProcessor shift state")
        self._last_parts_ok.clear()
        self._last_word_status.clear()
        self._last_process_vars.clear()
