"""Main collector loop — reads PLC data, processes events, and persists to SQLite.

Entry point::

    python -m api.collector.main
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_loader import ConfigLoader
from .data_processor import DataProcessor, ProductionEvent, StatusEvent, ProcessEvent
from .alert_engine import AlertEngine, Alert
from .drivers.factory import create_driver
from .drivers.base import BaseDriver

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------
DEFAULT_CYCLE_SECONDS = 5
DEFAULT_CONFIG_PATH = os.environ.get(
    "ME2_EQUIPMENT_CONFIG",
    str(Path(__file__).resolve().parent.parent / "config" / "equipment.json"),
)
DEFAULT_DB_PATH = os.environ.get(
    "ME2_COLLECTOR_DB",
    str(Path(__file__).resolve().parent.parent / "data" / "collector.db"),
)

# Shift boundaries as (hour, minute) tuples in local time, 24h format.
# Must be sorted in ascending order.
SHIFT_BOUNDARIES: list[tuple[int, int]] = [(5, 0), (13, 30), (22, 0)]


# ------------------------------------------------------------------
# SQLite persistence
# ------------------------------------------------------------------

def _ensure_db(db_path: str) -> sqlite3.Connection:
    """Create the SQLite database and tables if they do not exist."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS production_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            parts_ok        INTEGER NOT NULL,
            delta           INTEGER NOT NULL,
            cycle_time_s    REAL    NOT NULL,
            product_no      INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS status_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            word_status     INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS process_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            var_name        TEXT    NOT NULL,
            value           TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            level           INTEGER NOT NULL,
            downtime_minutes REAL   NOT NULL,
            word_status     INTEGER NOT NULL,
            message         TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_prod_ts ON production_events(serial_number, timestamp);
        CREATE INDEX IF NOT EXISTS idx_stat_ts ON status_events(serial_number, timestamp);
        CREATE INDEX IF NOT EXISTS idx_proc_ts ON process_events(serial_number, timestamp);
        CREATE INDEX IF NOT EXISTS idx_alert_ts ON alerts(serial_number, timestamp);
        """
    )
    conn.commit()
    logger.info("SQLite database ready at %s", db_path)
    return conn


def _insert_production(conn: sqlite3.Connection, event: ProductionEvent) -> None:
    conn.execute(
        "INSERT INTO production_events "
        "(serial_number, timestamp, parts_ok, delta, cycle_time_s, product_no) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            event.serial_number,
            event.timestamp.isoformat(),
            event.parts_ok,
            event.delta,
            event.cycle_time_s,
            event.product_no,
        ),
    )
    conn.commit()


def _insert_status(conn: sqlite3.Connection, event: StatusEvent) -> None:
    conn.execute(
        "INSERT INTO status_events (serial_number, timestamp, word_status) "
        "VALUES (?, ?, ?)",
        (
            event.serial_number,
            event.timestamp.isoformat(),
            event.word_status,
        ),
    )
    conn.commit()


def _insert_process(conn: sqlite3.Connection, event: ProcessEvent) -> None:
    conn.execute(
        "INSERT INTO process_events (serial_number, timestamp, var_name, value) "
        "VALUES (?, ?, ?, ?)",
        (
            event.serial_number,
            event.timestamp.isoformat(),
            event.var_name,
            str(event.value),
        ),
    )
    conn.commit()


def _insert_alert(conn: sqlite3.Connection, alert: Alert) -> None:
    conn.execute(
        "INSERT INTO alerts "
        "(serial_number, timestamp, level, downtime_minutes, word_status, message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            alert.serial_number,
            alert.timestamp.isoformat(),
            alert.level,
            alert.downtime_minutes,
            alert.word_status,
            alert.message,
        ),
    )
    conn.commit()


# ------------------------------------------------------------------
# Shift boundary detection
# ------------------------------------------------------------------

def _current_shift_boundary() -> tuple[int, int]:
    """Return the (hour, minute) boundary of the current shift in local time."""
    now_local = datetime.now()
    now_hm = (now_local.hour, now_local.minute)
    for boundary in reversed(SHIFT_BOUNDARIES):
        if now_hm >= boundary:
            return boundary
    # Before the first boundary => belongs to the previous day's last shift
    return SHIFT_BOUNDARIES[-1]


# ------------------------------------------------------------------
# Equipment polling
# ------------------------------------------------------------------

async def _poll_equipment(
    serial_number: str,
    driver: BaseDriver,
    eq_config: dict,
    processor: DataProcessor,
    alert_engine: AlertEngine,
    conn: sqlite3.Connection,
) -> None:
    """Read all configured variables from one equipment and process events."""
    variables: list[dict] = eq_config.get("variables", [])

    for var_cfg in variables:
        var_name: str = var_cfg["name"]
        address: dict = var_cfg["address"]
        role: str = var_cfg.get("role", "process")

        value = await driver.read_variable(address)
        if value is None:
            logger.warning("[%s] Failed to read variable '%s'", serial_number, var_name)
            continue

        # --- Production counter ---
        if role == "parts_ok":
            cycle_time_var = eq_config.get("cycle_time_var")
            cycle_time_s = 0.0
            if cycle_time_var:
                ct_val = await driver.read_variable(cycle_time_var)
                if ct_val is not None:
                    cycle_time_s = float(ct_val)

            product_no_var = eq_config.get("product_no_var")
            product_no = 0
            if product_no_var:
                pn_val = await driver.read_variable(product_no_var)
                if pn_val is not None:
                    product_no = int(pn_val)

            event = processor.process_production(
                serial_number=serial_number,
                parts_ok=int(value),
                cycle_time_s=cycle_time_s,
                product_no=product_no,
                config=eq_config,
            )
            if event is not None:
                _insert_production(conn, event)

        # --- Machine status word ---
        elif role == "word_status":
            status_event = processor.process_status(
                serial_number=serial_number,
                word_status=int(value),
            )
            if status_event is not None:
                _insert_status(conn, status_event)

            alert = alert_engine.check_status(
                serial_number=serial_number,
                word_status=int(value),
                config=eq_config,
            )
            if alert is not None:
                _insert_alert(conn, alert)

        # --- Generic process variable ---
        else:
            proc_event = processor.process_variable(
                serial_number=serial_number,
                var_name=var_name,
                value=value,
            )
            if proc_event is not None:
                _insert_process(conn, proc_event)


# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------

async def run_collector(
    config_path: str = DEFAULT_CONFIG_PATH,
    db_path: str = DEFAULT_DB_PATH,
    cycle_seconds: float = DEFAULT_CYCLE_SECONDS,
) -> None:
    """Run the collector forever (until KeyboardInterrupt or cancellation)."""
    logger.info("=== ME2 Collector starting ===")
    logger.info("Config : %s", config_path)
    logger.info("DB     : %s", db_path)
    logger.info("Cycle  : %.1fs", cycle_seconds)

    # Load configuration
    loader = ConfigLoader(config_path)
    loader.load()
    eq_configs = loader.get_equipment_configs()

    if not eq_configs:
        logger.error("No equipment configured — exiting")
        return

    # Create and connect drivers
    drivers: dict[str, BaseDriver] = {}
    for eq in eq_configs:
        sn = eq["serial_number"]
        try:
            drv = create_driver(eq)
            connected = await drv.connect()
            if connected:
                drivers[sn] = drv
            else:
                logger.error("[%s] Initial connection failed — will retry in loop", sn)
                drivers[sn] = drv  # keep it; reconnect logic is in the driver
        except Exception:
            logger.exception("[%s] Failed to create driver", sn)

    # Initialise processing components
    processor = DataProcessor()
    alert_engine = AlertEngine()
    conn = _ensure_db(db_path)

    last_shift_boundary = _current_shift_boundary()
    logger.info("Initial shift boundary: %s", last_shift_boundary)

    try:
        while True:
            cycle_start = time.monotonic()

            # Check for config reload
            if loader.reload():
                eq_configs = loader.get_equipment_configs()
                logger.info("Equipment configs reloaded (%d entries)", len(eq_configs))

            # Shift boundary detection
            current_shift = _current_shift_boundary()
            if current_shift != last_shift_boundary:
                logger.info(
                    "Shift boundary crossed (%s -> %s) — resetting processor state",
                    last_shift_boundary,
                    current_shift,
                )
                processor.reset_shift_state()
                last_shift_boundary = current_shift

            # Poll each equipment
            for eq_cfg in eq_configs:
                sn = eq_cfg["serial_number"]
                driver = drivers.get(sn)
                if driver is None:
                    continue
                try:
                    await _poll_equipment(
                        serial_number=sn,
                        driver=driver,
                        eq_config=eq_cfg,
                        processor=processor,
                        alert_engine=alert_engine,
                        conn=conn,
                    )
                except Exception:
                    logger.exception("[%s] Error during poll cycle", sn)

            elapsed = time.monotonic() - cycle_start
            logger.debug("Cycle completed in %.3fs", elapsed)

            await asyncio.sleep(cycle_seconds)

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Collector shutdown requested")
    finally:
        # Graceful cleanup
        logger.info("Disconnecting all drivers...")
        for sn, drv in drivers.items():
            try:
                await drv.disconnect()
            except Exception:
                logger.exception("[%s] Error during disconnect", sn)
        conn.close()
        logger.info("=== ME2 Collector stopped ===")


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main() -> None:
    """Synchronous entry point for ``python -m api.collector.main``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        asyncio.run(run_collector())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
