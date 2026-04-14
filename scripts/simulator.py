"""
ME2 PLC Simulator — generates realistic production/status data into the
collector's SQLite buffer, allowing full pipeline testing without a real PLC.

Usage:
    python scripts/simulator.py

The simulator writes to the same SQLite database that the collector would,
so the SyncService picks it up automatically and pushes to PostgreSQL +
broadcasts via WebSocket.

Press Ctrl+C to stop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import random
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

# Fix asyncpg/asyncio on Windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("simulator")

# --- Config ---
SERIAL_NUMBER = "MEI-2024-0042"
CYCLE_SECONDS = 5          # How often to generate events
STANDARD_CYCLE_TIME = 6.0  # seconds per part
FAILURE_PROBABILITY = 0.05 # 5% chance of failure per cycle
SETUP_PROBABILITY = 0.02   # 2% chance of setup
STARVING_PROBABILITY = 0.03

# SQLite path — same as collector uses
DB_PATH = os.environ.get(
    "ME2_COLLECTOR_DB",
    str(Path(__file__).resolve().parent.parent / "api" / "data" / "collector.db"),
)


def init_db(db_path: str) -> sqlite3.Connection:
    """Create/open SQLite and ensure tables exist (same schema as collector)."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS production_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            parts_ok        INTEGER NOT NULL,
            delta           INTEGER NOT NULL,
            cycle_time_s    REAL    NOT NULL,
            product_no      INTEGER NOT NULL,
            synced          INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS status_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            word_status     INTEGER NOT NULL,
            synced          INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS process_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            var_name        TEXT    NOT NULL,
            value           TEXT    NOT NULL,
            synced          INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT    NOT NULL,
            timestamp       TEXT    NOT NULL,
            level           INTEGER NOT NULL,
            downtime_minutes REAL   NOT NULL,
            word_status     INTEGER NOT NULL,
            message         TEXT    NOT NULL,
            synced          INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_prod_synced ON production_events(synced);
        CREATE INDEX IF NOT EXISTS idx_stat_synced ON status_events(synced);
        CREATE INDEX IF NOT EXISTS idx_proc_synced ON process_events(synced);
        CREATE INDEX IF NOT EXISTS idx_alert_synced ON alerts(synced);
    """)
    conn.commit()
    logger.info("SQLite ready at %s", db_path)
    return conn


class PLCSimulator:
    """Simulates a Schneider M241 PLC producing parts with random events."""

    def __init__(self):
        self.parts_ok: int = 0
        self.word_status: int = 18  # Start in Uptime
        self.product_no: int = 9999
        self._downtime_remaining: int = 0  # cycles of downtime left
        self._last_status: int = 18

    def tick(self) -> dict:
        """Advance one cycle and return the current state."""
        now = datetime.now(tz=timezone.utc)

        # Handle ongoing downtime
        if self._downtime_remaining > 0:
            self._downtime_remaining -= 1
            if self._downtime_remaining == 0:
                self.word_status = 18  # Return to uptime
                logger.info("Machine RESUMED (Uptime)")

            return {
                "serial_number": SERIAL_NUMBER,
                "ts": now,
                "parts_ok": self.parts_ok,
                "word_status": self.word_status,
                "cycle_time_s": 0.0,
                "product_no": self.product_no,
                "status_changed": self.word_status != self._last_status,
                "parts_changed": False,
            }

        # Normal operation — produce a part
        roll = random.random()

        if roll < FAILURE_PROBABILITY:
            # Machine failure
            self.word_status = 32
            self._downtime_remaining = random.randint(3, 12)  # 15-60s downtime
            logger.warning("FAILURE! Downtime for %d cycles", self._downtime_remaining)
            status_changed = True
            parts_changed = False

        elif roll < FAILURE_PROBABILITY + SETUP_PROBABILITY:
            # Setup/changeover
            self.word_status = 64
            self._downtime_remaining = random.randint(6, 20)  # 30-100s
            self.product_no = random.choice([1001, 2002, 3003, 4004])
            logger.info("SETUP started (new product: %d, duration: %d cycles)",
                        self.product_no, self._downtime_remaining)
            status_changed = True
            parts_changed = False

        elif roll < FAILURE_PROBABILITY + SETUP_PROBABILITY + STARVING_PROBABILITY:
            # Starving
            self.word_status = 20
            self._downtime_remaining = random.randint(2, 8)
            logger.info("STARVING for %d cycles", self._downtime_remaining)
            status_changed = True
            parts_changed = False

        else:
            # Produce a part
            self.word_status = 18
            self.parts_ok += 1
            cycle_time = STANDARD_CYCLE_TIME + random.gauss(0, 0.5)
            cycle_time = max(3.0, min(12.0, cycle_time))  # clamp
            status_changed = self._last_status != 18
            parts_changed = True

            result = {
                "serial_number": SERIAL_NUMBER,
                "ts": now,
                "parts_ok": self.parts_ok,
                "word_status": self.word_status,
                "cycle_time_s": round(cycle_time, 2),
                "product_no": self.product_no,
                "status_changed": status_changed,
                "parts_changed": parts_changed,
            }
            self._last_status = self.word_status
            return result

        result = {
            "serial_number": SERIAL_NUMBER,
            "ts": now,
            "parts_ok": self.parts_ok,
            "word_status": self.word_status,
            "cycle_time_s": 0.0,
            "product_no": self.product_no,
            "status_changed": status_changed,
            "parts_changed": parts_changed,
        }
        self._last_status = self.word_status
        return result


def insert_events(conn: sqlite3.Connection, state: dict) -> None:
    """Write production and/or status events to SQLite (trigger on change)."""
    ts_iso = state["ts"].isoformat()

    if state["parts_changed"]:
        conn.execute(
            "INSERT INTO production_events "
            "(serial_number, timestamp, parts_ok, delta, cycle_time_s, product_no) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                state["serial_number"],
                ts_iso,
                state["parts_ok"],
                1,  # delta = 1 part
                state["cycle_time_s"],
                state["product_no"],
            ),
        )

    if state["status_changed"]:
        conn.execute(
            "INSERT INTO status_events "
            "(serial_number, timestamp, word_status) "
            "VALUES (?, ?, ?)",
            (
                state["serial_number"],
                ts_iso,
                state["word_status"],
            ),
        )

    conn.commit()


def main() -> None:
    logger.info("=" * 60)
    logger.info("ME2 PLC Simulator — %s", SERIAL_NUMBER)
    logger.info("Cycle: %ds | DB: %s", CYCLE_SECONDS, DB_PATH)
    logger.info("=" * 60)

    conn = init_db(DB_PATH)
    sim = PLCSimulator()

    # Insert initial status event
    ts_now = datetime.now(tz=timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO status_events (serial_number, timestamp, word_status) VALUES (?, ?, ?)",
        (SERIAL_NUMBER, ts_now, 18),
    )
    conn.commit()
    logger.info("Initial status: Uptime (18)")

    try:
        cycle = 0
        while True:
            cycle += 1
            state = sim.tick()

            insert_events(conn, state)

            # Log summary
            status_name = {18: "Uptime", 16: "Idle", 20: "Starving",
                           24: "Blocked", 32: "Failure", 64: "Setup"}.get(
                state["word_status"], f"Status({state['word_status']})"
            )
            logger.info(
                "[Cycle %4d] Status=%-10s Parts=%d CycleTime=%.1fs Product=%d%s%s",
                cycle,
                status_name,
                state["parts_ok"],
                state["cycle_time_s"],
                state["product_no"],
                " *PROD" if state["parts_changed"] else "",
                " *STATUS" if state["status_changed"] else "",
            )

            time.sleep(CYCLE_SECONDS)

    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
