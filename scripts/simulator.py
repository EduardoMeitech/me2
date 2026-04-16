"""
ME2 PLC Simulator — generates realistic production/status data for ALL
equipment into the collector's SQLite buffer.

Each machine has a unique production profile (cycle time, failure rate,
product mix) inspired by real BigQuery/E2 data from Meitech plants.

Usage:
    python scripts/simulator.py

The simulator writes to the same SQLite database that the collector would,
so the SyncService picks it up automatically and pushes to PostgreSQL +
broadcasts via WebSocket.

Press Ctrl+C to stop.
"""

from __future__ import annotations

import logging
import os
import platform
import random
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

if platform.system() == "Windows":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("simulator")

# SQLite path — same as collector uses
DB_PATH = os.environ.get(
    "ME2_COLLECTOR_DB",
    str(Path(__file__).resolve().parent.parent / "api" / "data" / "collector.db"),
)

TICK_INTERVAL = 3  # seconds between simulation ticks

# ---------------------------------------------------------------------------
# Equipment profiles — inspired by real BigQuery/E2 data
# ---------------------------------------------------------------------------

EQUIPMENT = [
    {
        "serial_number": "MEI-2024-0042",
        "name": "Depenadora 01",
        "cycle_time": 10.3,
        "cycle_jitter": 1.5,
        "products": ["Frango Inteiro", "Frango Medio"],
        "failure_rate": 0.04,
        "setup_rate": 0.015,
        "starving_rate": 0.02,
        "blocked_rate": 0.01,
    },
    {
        "serial_number": "MEI-2024-28321",
        "name": "Desossadora 01",
        "cycle_time": 8.8,
        "cycle_jitter": 1.2,
        "products": ["File de Peito", "Sassami", "Coxa c/ Sobrecoxa", "Meio Peito"],
        "failure_rate": 0.03,
        "setup_rate": 0.02,
        "starving_rate": 0.005,
        "blocked_rate": 0.04,
    },
    {
        "serial_number": "MEI-2024-28322",
        "name": "Desossadora 02",
        "cycle_time": 8.7,
        "cycle_jitter": 1.0,
        "products": ["File de Peito", "Sassami", "Coxa s/ Sobrecoxa", "Peito Inteiro"],
        "failure_rate": 0.03,
        "setup_rate": 0.02,
        "starving_rate": 0.005,
        "blocked_rate": 0.035,
    },
    {
        "serial_number": "MEI-2024-29072",
        "name": "Transportadora 01",
        "cycle_time": 7.8,
        "cycle_jitter": 1.0,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.02,
        "setup_rate": 0.005,
        "starving_rate": 0.03,
        "blocked_rate": 0.01,
    },
    {
        "serial_number": "MEI-2024-29073",
        "name": "Transportadora 02",
        "cycle_time": 8.8,
        "cycle_jitter": 1.2,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.02,
        "setup_rate": 0.005,
        "starving_rate": 0.035,
        "blocked_rate": 0.01,
    },
    {
        "serial_number": "MEI-2024-29075",
        "name": "Balanca Aerea 01",
        "cycle_time": 31.6,
        "cycle_jitter": 4.0,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.025,
        "setup_rate": 0.01,
        "starving_rate": 0.02,
        "blocked_rate": 0.005,
    },
    {
        "serial_number": "MEI-2024-29076",
        "name": "Balanca Aerea 02",
        "cycle_time": 8.2,
        "cycle_jitter": 1.0,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.02,
        "setup_rate": 0.01,
        "starving_rate": 0.025,
        "blocked_rate": 0.005,
    },
    {
        "serial_number": "MEI-2024-29078",
        "name": "Transferidora 01",
        "cycle_time": 17.5,
        "cycle_jitter": 2.5,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.02,
        "setup_rate": 0.005,
        "starving_rate": 0.08,
        "blocked_rate": 0.01,
    },
    {
        "serial_number": "MEI-2024-29657",
        "name": "Embaladora 01",
        "cycle_time": 7.7,
        "cycle_jitter": 1.0,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.06,
        "setup_rate": 0.01,
        "starving_rate": 0.04,
        "blocked_rate": 0.01,
    },
    {
        "serial_number": "MEI-2024-34513",
        "name": "Classificadora 01",
        "cycle_time": 7.7,
        "cycle_jitter": 1.0,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.02,
        "setup_rate": 0.008,
        "starving_rate": 0.03,
        "blocked_rate": 0.005,
    },
    {
        "serial_number": "MEI-2024-34514",
        "name": "Classificadora 02",
        "cycle_time": 7.7,
        "cycle_jitter": 1.0,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.015,
        "setup_rate": 0.008,
        "starving_rate": 0.025,
        "blocked_rate": 0.005,
    },
    {
        "serial_number": "MEI-2024-09999",
        "name": "Escaldadeira 01",
        "cycle_time": 8.2,
        "cycle_jitter": 1.0,
        "products": ["Frango Inteiro"],
        "failure_rate": 0.02,
        "setup_rate": 0.005,
        "starving_rate": 0.01,
        "blocked_rate": 0.04,
    },
]


# ---------------------------------------------------------------------------
# Machine state simulator
# ---------------------------------------------------------------------------

class MachineSimulator:
    """Simulates one machine with realistic production patterns."""

    def __init__(self, profile: dict):
        self.serial = profile["serial_number"]
        self.name = profile["name"]
        self.cycle_time = profile["cycle_time"]
        self.cycle_jitter = profile["cycle_jitter"]
        self.products = profile["products"]
        self.failure_rate = profile["failure_rate"]
        self.setup_rate = profile["setup_rate"]
        self.starving_rate = profile["starving_rate"]
        self.blocked_rate = profile["blocked_rate"]

        self.parts_ok: int = 0
        self.word_status: int = 18
        self.product_no: str = random.choice(self.products)
        self._last_status: int = 18
        self._downtime_remaining: int = 0
        self._ticks_since_production: int = 0
        self._ticks_per_part: float = max(1, self.cycle_time / TICK_INTERVAL)

    def tick(self) -> dict:
        """Advance one tick. Returns state dict with change flags."""
        now = datetime.now(tz=timezone.utc)
        parts_changed = False
        status_changed = False

        # Handle ongoing downtime
        if self._downtime_remaining > 0:
            self._downtime_remaining -= 1
            if self._downtime_remaining == 0:
                old_status = self.word_status
                self.word_status = 18
                status_changed = True
        else:
            # Roll for events
            roll = random.random()
            threshold = 0.0

            threshold += self.failure_rate
            if roll < threshold:
                self.word_status = 32  # Failure
                self._downtime_remaining = random.randint(3, 15)
                status_changed = self._last_status != 32
            else:
                threshold += self.setup_rate
                if roll < threshold:
                    self.word_status = 64  # Setup
                    self._downtime_remaining = random.randint(5, 25)
                    self.product_no = random.choice(self.products)
                    status_changed = self._last_status != 64
                else:
                    threshold += self.starving_rate
                    if roll < threshold:
                        self.word_status = 20  # Starving
                        self._downtime_remaining = random.randint(2, 10)
                        status_changed = self._last_status != 20
                    else:
                        threshold += self.blocked_rate
                        if roll < threshold:
                            self.word_status = 24  # Blocked
                            self._downtime_remaining = random.randint(2, 8)
                            status_changed = self._last_status != 24
                        else:
                            # Producing
                            if self.word_status != 18:
                                status_changed = True
                            self.word_status = 18
                            self._ticks_since_production += 1

                            if self._ticks_since_production >= self._ticks_per_part:
                                self._ticks_since_production = 0
                                self.parts_ok += 1
                                parts_changed = True
                                # Vary the next cycle slightly
                                jitter = random.gauss(0, self.cycle_jitter)
                                self._ticks_per_part = max(1, (self.cycle_time + jitter) / TICK_INTERVAL)

        cycle_time_s = round(self.cycle_time + random.gauss(0, self.cycle_jitter * 0.5), 2)
        cycle_time_s = max(0.5, cycle_time_s)

        result = {
            "serial_number": self.serial,
            "ts": now,
            "parts_ok": self.parts_ok,
            "word_status": self.word_status,
            "cycle_time_s": cycle_time_s if parts_changed else 0.0,
            "product_no": self.product_no,
            "status_changed": status_changed,
            "parts_changed": parts_changed,
        }
        self._last_status = self.word_status
        return result


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    """Create/open SQLite and ensure tables exist."""
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


def insert_events(conn: sqlite3.Connection, state: dict) -> None:
    """Write events to SQLite (trigger on change only)."""
    ts_iso = state["ts"].isoformat()

    if state["parts_changed"]:
        conn.execute(
            "INSERT INTO production_events "
            "(serial_number, timestamp, parts_ok, delta, cycle_time_s, product_no) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (state["serial_number"], ts_iso, state["parts_ok"], 1,
             state["cycle_time_s"], state["product_no"]),
        )

    if state["status_changed"]:
        conn.execute(
            "INSERT INTO status_events "
            "(serial_number, timestamp, word_status) VALUES (?, ?, ?)",
            (state["serial_number"], ts_iso, state["word_status"]),
        )

    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

STATUS_NAMES = {
    18: "Uptime", 16: "Idle", 17: "PlannedStop", 20: "Starving",
    24: "Blocked", 32: "Failure", 64: "Setup", 128: "Emergency",
}


def main() -> None:
    logger.info("=" * 70)
    logger.info("ME2 Multi-Machine Simulator — %d machines, tick=%ds",
                len(EQUIPMENT), TICK_INTERVAL)
    logger.info("DB: %s", DB_PATH)
    logger.info("=" * 70)

    conn = init_db(DB_PATH)
    machines = [MachineSimulator(p) for p in EQUIPMENT]

    # Insert initial status for all machines
    ts_now = datetime.now(tz=timezone.utc).isoformat()
    for m in machines:
        conn.execute(
            "INSERT INTO status_events (serial_number, timestamp, word_status) "
            "VALUES (?, ?, ?)",
            (m.serial, ts_now, 18),
        )
    conn.commit()
    logger.info("Initialized %d machines", len(machines))

    try:
        cycle = 0
        while True:
            cycle += 1
            events_this_tick = 0

            for m in machines:
                state = m.tick()
                if state["parts_changed"] or state["status_changed"]:
                    insert_events(conn, state)
                    events_this_tick += 1

            # Summary log every 10 ticks
            if cycle % 10 == 0:
                summary = []
                for m in machines:
                    status = STATUS_NAMES.get(m.word_status, str(m.word_status))
                    summary.append(f"{m.name[:12]:12s} {status:8s} P={m.parts_ok}")
                logger.info("[Tick %4d] %d events | %s",
                            cycle, events_this_tick,
                            " | ".join(summary[:4]))
                if len(summary) > 4:
                    logger.info("           %s", " | ".join(summary[4:8]))
                    if len(summary) > 8:
                        logger.info("           %s", " | ".join(summary[8:]))

            time.sleep(TICK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
