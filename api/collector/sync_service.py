"""SQLite -> PostgreSQL sync service with WebSocket broadcast.

Periodically reads unsynced events from the collector's SQLite buffer,
inserts them into the PostgreSQL database (mapping serial_number to
equipment_id), and broadcasts status/production events via WebSocket.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import async_session
from api.core.models import (
    Alert as PgAlert,
    Equipment,
    ProcessEvent as PgProcessEvent,
    ProductionEvent as PgProductionEvent,
    StatusEvent as PgStatusEvent,
)
from api.routers.live import manager

logger = logging.getLogger(__name__)

# Default SQLite path — mirrors collector.main logic
DEFAULT_SQLITE_PATH = os.environ.get(
    "ME2_COLLECTOR_DB",
    str(Path(__file__).resolve().parent.parent / "data" / "collector.db"),
)

DEFAULT_SYNC_INTERVAL = 5  # seconds


class SyncService:
    """Reads unsynced rows from SQLite, writes them to PostgreSQL, and
    broadcasts real-time events over WebSocket."""

    def __init__(
        self,
        sqlite_path: str = DEFAULT_SQLITE_PATH,
        sync_interval: float = DEFAULT_SYNC_INTERVAL,
    ) -> None:
        self.sqlite_path = sqlite_path
        self.sync_interval = sync_interval
        self._running = False
        # Cache: serial_number -> equipment_id (UUID string)
        self._equipment_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # SQLite helpers
    # ------------------------------------------------------------------

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        """Open (or reopen) the SQLite database and ensure the ``synced``
        column exists on every event table."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_synced_columns(conn)
        return conn

    @staticmethod
    def _ensure_synced_columns(conn: sqlite3.Connection) -> None:
        """Add a ``synced`` boolean column (default 0) to each event table
        if it does not already exist."""
        tables = ["production_events", "status_events", "process_events", "alerts"]
        for table in tables:
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN synced INTEGER NOT NULL DEFAULT 0"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_synced ON {table}(synced)"
                )
                conn.commit()
                logger.info("Added 'synced' column to SQLite table '%s'", table)
            except sqlite3.OperationalError:
                # Column already exists — that's fine
                pass

    # ------------------------------------------------------------------
    # Equipment lookup
    # ------------------------------------------------------------------

    async def _resolve_equipment_id(
        self, session: AsyncSession, serial_number: str
    ) -> str | None:
        """Return the PostgreSQL equipment UUID for a serial_number.

        Uses an in-memory cache to avoid repeated DB lookups.
        """
        if serial_number in self._equipment_cache:
            return self._equipment_cache[serial_number]

        result = await session.execute(
            select(Equipment.id).where(Equipment.serial_number == serial_number)
        )
        row = result.scalar_one_or_none()
        if row is None:
            logger.warning(
                "No equipment found in PostgreSQL for serial_number='%s' — "
                "skipping events for this equipment",
                serial_number,
            )
            return None

        self._equipment_cache[serial_number] = row
        return row

    # ------------------------------------------------------------------
    # Per-table sync methods
    # ------------------------------------------------------------------

    async def _sync_production_events(
        self,
        conn: sqlite3.Connection,
        session: AsyncSession,
    ) -> int:
        """Sync unsynced production_events. Returns count of synced rows."""
        rows = conn.execute(
            "SELECT id, serial_number, timestamp, parts_ok, delta, "
            "cycle_time_s, product_no FROM production_events WHERE synced = 0 "
            "ORDER BY id LIMIT 500"
        ).fetchall()

        if not rows:
            return 0

        synced_ids: list[int] = []

        for row in rows:
            equipment_id = await self._resolve_equipment_id(session, row["serial_number"])
            if equipment_id is None:
                continue

            ts = datetime.fromisoformat(row["timestamp"])
            pg_event = PgProductionEvent(
                equipment_id=equipment_id,
                serial_number=row["serial_number"],
                product_no=str(row["product_no"]) if row["product_no"] is not None else None,
                parts_ok=row["parts_ok"],
                cycle_time_s=row["cycle_time_s"],
                ts=ts,
            )
            session.add(pg_event)
            synced_ids.append(row["id"])

            # Broadcast via WebSocket
            await manager.broadcast(
                {
                    "type": "production",
                    "equipment_id": equipment_id,
                    "serial_number": row["serial_number"],
                    "parts_ok": row["parts_ok"],
                    "cycle_time_s": row["cycle_time_s"],
                    "ts": ts.isoformat(),
                }
            )

        if synced_ids:
            await session.flush()
            placeholders = ",".join("?" * len(synced_ids))
            conn.execute(
                f"UPDATE production_events SET synced = 1 WHERE id IN ({placeholders})",
                synced_ids,
            )
            conn.commit()

        return len(synced_ids)

    async def _sync_status_events(
        self,
        conn: sqlite3.Connection,
        session: AsyncSession,
    ) -> int:
        """Sync unsynced status_events. Returns count of synced rows."""
        rows = conn.execute(
            "SELECT id, serial_number, timestamp, word_status "
            "FROM status_events WHERE synced = 0 ORDER BY id LIMIT 500"
        ).fetchall()

        if not rows:
            return 0

        synced_ids: list[int] = []

        for row in rows:
            equipment_id = await self._resolve_equipment_id(session, row["serial_number"])
            if equipment_id is None:
                continue

            ts = datetime.fromisoformat(row["timestamp"])
            pg_event = PgStatusEvent(
                equipment_id=equipment_id,
                serial_number=row["serial_number"],
                word_status=row["word_status"],
                ts=ts,
            )
            session.add(pg_event)
            synced_ids.append(row["id"])

            # Broadcast via WebSocket
            await manager.broadcast(
                {
                    "type": "status",
                    "equipment_id": equipment_id,
                    "serial_number": row["serial_number"],
                    "word_status": row["word_status"],
                    "ts": ts.isoformat(),
                }
            )

        if synced_ids:
            await session.flush()
            placeholders = ",".join("?" * len(synced_ids))
            conn.execute(
                f"UPDATE status_events SET synced = 1 WHERE id IN ({placeholders})",
                synced_ids,
            )
            conn.commit()

        return len(synced_ids)

    async def _sync_process_events(
        self,
        conn: sqlite3.Connection,
        session: AsyncSession,
    ) -> int:
        """Sync unsynced process_events. Returns count of synced rows."""
        rows = conn.execute(
            "SELECT id, serial_number, timestamp, var_name, value "
            "FROM process_events WHERE synced = 0 ORDER BY id LIMIT 500"
        ).fetchall()

        if not rows:
            return 0

        synced_ids: list[int] = []

        for row in rows:
            equipment_id = await self._resolve_equipment_id(session, row["serial_number"])
            if equipment_id is None:
                continue

            ts = datetime.fromisoformat(row["timestamp"])
            try:
                float_value = float(row["value"])
            except (ValueError, TypeError):
                logger.warning(
                    "Cannot convert process_event value '%s' to float — skipping "
                    "(serial=%s, var=%s)",
                    row["value"],
                    row["serial_number"],
                    row["var_name"],
                )
                synced_ids.append(row["id"])  # mark as synced to avoid retrying
                continue

            pg_event = PgProcessEvent(
                equipment_id=equipment_id,
                variable_name=row["var_name"],
                value=float_value,
                ts=ts,
            )
            session.add(pg_event)
            synced_ids.append(row["id"])

        if synced_ids:
            await session.flush()
            placeholders = ",".join("?" * len(synced_ids))
            conn.execute(
                f"UPDATE process_events SET synced = 1 WHERE id IN ({placeholders})",
                synced_ids,
            )
            conn.commit()

        return len(synced_ids)

    async def _sync_alerts(
        self,
        conn: sqlite3.Connection,
        session: AsyncSession,
    ) -> int:
        """Sync unsynced alerts. Returns count of synced rows."""
        rows = conn.execute(
            "SELECT id, serial_number, timestamp, level, downtime_minutes, "
            "word_status, message FROM alerts WHERE synced = 0 ORDER BY id LIMIT 500"
        ).fetchall()

        if not rows:
            return 0

        synced_ids: list[int] = []

        for row in rows:
            equipment_id = await self._resolve_equipment_id(session, row["serial_number"])
            if equipment_id is None:
                continue

            ts = datetime.fromisoformat(row["timestamp"])
            pg_alert = PgAlert(
                equipment_id=equipment_id,
                level=row["level"],
                message=row["message"],
                started_at=ts,
            )
            session.add(pg_alert)
            synced_ids.append(row["id"])

        if synced_ids:
            await session.flush()
            placeholders = ",".join("?" * len(synced_ids))
            conn.execute(
                f"UPDATE alerts SET synced = 1 WHERE id IN ({placeholders})",
                synced_ids,
            )
            conn.commit()

        return len(synced_ids)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def _purge_synced(conn: sqlite3.Connection, max_age_hours: int = 24) -> None:
        """Delete synced rows older than *max_age_hours* to reclaim space."""
        cutoff = datetime.now(tz=timezone.utc).isoformat()
        for table in ["production_events", "status_events", "process_events", "alerts"]:
            conn.execute(
                f"DELETE FROM {table} WHERE synced = 1 AND "
                f"datetime(timestamp) < datetime(?, '-{max_age_hours} hours')",
                (cutoff,),
            )
        conn.commit()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        """Main sync loop — runs until cancelled."""
        self._running = True
        logger.info(
            "SyncService starting (sqlite=%s, interval=%.1fs)",
            self.sqlite_path,
            self.sync_interval,
        )

        while self._running:
            try:
                await self._sync_cycle()
            except asyncio.CancelledError:
                logger.info("SyncService cancelled — shutting down")
                self._running = False
                return
            except Exception:
                logger.exception("SyncService cycle failed — will retry next cycle")

            try:
                await asyncio.sleep(self.sync_interval)
            except asyncio.CancelledError:
                logger.info("SyncService sleep cancelled — shutting down")
                self._running = False
                return

    async def _sync_cycle(self) -> None:
        """Execute one full sync cycle across all event tables."""
        if not os.path.exists(self.sqlite_path):
            logger.debug("SQLite database not found at %s — skipping cycle", self.sqlite_path)
            return

        conn = self._get_sqlite_conn()
        try:
            async with async_session() as session:
                async with session.begin():
                    prod_count = await self._sync_production_events(conn, session)
                    status_count = await self._sync_status_events(conn, session)
                    process_count = await self._sync_process_events(conn, session)
                    alert_count = await self._sync_alerts(conn, session)

                total = prod_count + status_count + process_count + alert_count
                if total > 0:
                    logger.info(
                        "SyncService cycle: synced %d events "
                        "(prod=%d, status=%d, process=%d, alerts=%d)",
                        total,
                        prod_count,
                        status_count,
                        process_count,
                        alert_count,
                    )

            # Periodically purge old synced rows
            self._purge_synced(conn)

        finally:
            conn.close()

    def stop(self) -> None:
        """Signal the service to stop after the current cycle."""
        self._running = False
        logger.info("SyncService stop requested")
