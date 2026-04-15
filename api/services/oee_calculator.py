"""OEE (Overall Equipment Effectiveness) calculation service for ME2.

Calculates availability, performance, and quality metrics per equipment
per hour and per shift, then upserts results into the oee_snapshots table.

OEE formula (from CLAUDE.md):
    availability = (planned_min - downtime_min) / planned_min
    performance  = parts_good / ((planned_min * 60) / target_cycle_time_s)
    quality      = parts_good / (parts_good + parts_scrap)   # 1.0 if no scrap
    oee          = availability * performance * quality

Downtime = sum of durations where word_status != 18 (18 = producing / Uptime).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import async_session
from api.core.models import (
    Equipment,
    OEESnapshot,
    ProductionEvent,
    Quality,
    Shift,
    StatusEvent,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shift definitions (fallback when DB shifts are unavailable)
# Times are in LOCAL BRT. UTC equivalents (+3h) used for DB queries.
# ---------------------------------------------------------------------------
SHIFT_DEFS: dict[str, dict] = {
    "T100": {"start_utc": time(8, 0), "end_utc": time(16, 29), "planned_min": 509.0},
    "T200": {"start_utc": time(16, 30), "end_utc": time(23, 59), "planned_min": 509.0},
    "T300": {"start_utc": time(1, 0), "end_utc": time(7, 59), "planned_min": 420.0},
}

# word_status values that count as uptime (producing)
_UPTIME_STATUSES = frozenset({18, 19})


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a value between lo and hi."""
    return max(lo, min(hi, value))


def _hour_range(dt_date: date, hour: int) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for a given date+hour window (UTC)."""
    start = datetime(dt_date.year, dt_date.month, dt_date.day, hour, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    return start, end


def _shift_range(dt_date: date, shift_name: str) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for a named shift on a given date (UTC)."""
    defn = SHIFT_DEFS.get(shift_name)
    if defn is None:
        raise ValueError(f"Unknown shift: {shift_name}")
    start_dt = datetime.combine(dt_date, defn["start_utc"], tzinfo=timezone.utc)
    end_dt = datetime.combine(dt_date, defn["end_utc"], tzinfo=timezone.utc)
    # Add 1 minute to include the final minute boundary
    end_dt = end_dt + timedelta(minutes=1)
    # Handle overnight (T300: end_utc < start_utc)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def _shift_for_hour(dt_date: date, hour: int) -> tuple[str, str | None]:
    """Determine which shift a given UTC hour belongs to.

    Returns (shift_name, None) — the second element is reserved for shift_id
    which callers resolve from the DB.
    """
    t = time(hour, 0)
    for name, defn in SHIFT_DEFS.items():
        s, e = defn["start_utc"], defn["end_utc"]
        if e < s:
            # Overnight shift (T300)
            if t >= s or t <= e:
                return name, None
        else:
            if s <= t <= e:
                return name, None
    return "T100", None


def _planned_min_for_hour(dt_date: date, hour: int) -> float:
    """How many planned minutes fall within a single UTC clock hour.

    For most hours inside a shift this is 60 min.  For boundary hours
    (the first / last hour of a shift), we prorate.
    """
    hour_start = datetime.combine(dt_date, time(hour, 0), tzinfo=timezone.utc)
    hour_end = hour_start + timedelta(hours=1)

    shift_name, _ = _shift_for_hour(dt_date, hour)
    try:
        shift_start, shift_end = _shift_range(dt_date, shift_name)
    except ValueError:
        return 0.0

    overlap_start = max(hour_start, shift_start)
    overlap_end = min(hour_end, shift_end)

    if overlap_end <= overlap_start:
        return 0.0

    return (overlap_end - overlap_start).total_seconds() / 60.0


# ═══════════════════════════════════════════════════════════════════════════
# OEECalculator
# ═══════════════════════════════════════════════════════════════════════════

class OEECalculator:
    """Calculate and persist OEE metrics for ME2 equipment."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_shift_id(self, db: AsyncSession, shift_name: str) -> str | None:
        """Resolve a shift name to its UUID from me2_shifts."""
        result = await db.execute(
            select(Shift.id).where(Shift.name == shift_name)
        )
        row = result.scalar_one_or_none()
        return row

    async def _get_equipment_cycle_time(
        self, db: AsyncSession, equipment_id: str
    ) -> float | None:
        """Return standard_cycle_time_s for equipment, or None."""
        result = await db.execute(
            select(Equipment.standard_cycle_time_s).where(Equipment.id == equipment_id)
        )
        return result.scalar_one_or_none()

    async def _count_parts(
        self,
        db: AsyncSession,
        equipment_id: str,
        range_start: datetime,
        range_end: datetime,
    ) -> int:
        """Count parts produced in a time window.

        Strategy: production_events are triggered on change.  Each event
        represents one completed part.  So the count of events in the
        window equals parts produced.
        """
        result = await db.execute(
            select(func.count(ProductionEvent.id)).where(
                ProductionEvent.equipment_id == equipment_id,
                ProductionEvent.ts >= range_start,
                ProductionEvent.ts < range_end,
            )
        )
        return result.scalar_one() or 0

    async def _calc_downtime(
        self,
        db: AsyncSession,
        equipment_id: str,
        range_start: datetime,
        range_end: datetime,
    ) -> float:
        """Calculate total downtime (minutes) from status_events in a window.

        Algorithm:
        1. Fetch all status events in [range_start - 1h, range_end] so we
           capture the status that was active *before* the window began.
        2. Walk consecutive pairs: the duration of each status is
           next_event.ts - current_event.ts.
        3. Clip durations to [range_start, range_end].
        4. Sum durations where word_status NOT in _UPTIME_STATUSES.
        """
        # Extend lookback to capture the status that was already active
        lookback = range_start - timedelta(hours=1)

        result = await db.execute(
            select(StatusEvent.word_status, StatusEvent.ts)
            .where(
                StatusEvent.equipment_id == equipment_id,
                StatusEvent.ts >= lookback,
                StatusEvent.ts < range_end,
            )
            .order_by(StatusEvent.ts)
        )
        rows = result.all()

        if not rows:
            # No status data — assume full downtime (conservative)
            return (range_end - range_start).total_seconds() / 60.0

        downtime_seconds = 0.0

        for i, (ws, ts) in enumerate(rows):
            # Determine the end of this status period
            if i + 1 < len(rows):
                next_ts = rows[i + 1][1]
            else:
                # Last known status extends to end of window
                next_ts = range_end

            # Clip to the analysis window
            seg_start = max(ts, range_start)
            seg_end = min(next_ts, range_end)

            if seg_end <= seg_start:
                continue

            if ws not in _UPTIME_STATUSES:
                downtime_seconds += (seg_end - seg_start).total_seconds()

        return downtime_seconds / 60.0

    async def _get_scrap(
        self,
        db: AsyncSession,
        equipment_id: str,
        range_start: datetime,
        range_end: datetime,
    ) -> int:
        """Sum scrap quantities from me2_quality in a time window."""
        result = await db.execute(
            select(func.coalesce(func.sum(Quality.quantity_scrap), 0)).where(
                Quality.equipment_id == equipment_id,
                Quality.ts >= range_start,
                Quality.ts < range_end,
            )
        )
        return result.scalar_one() or 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calculate_hourly(
        self,
        db: AsyncSession,
        equipment_id: str,
        dt_date: date,
        hour: int,
    ) -> OEESnapshot:
        """Calculate OEE for one equipment for one clock hour and upsert.

        Parameters
        ----------
        db : AsyncSession
        equipment_id : UUID of equipment
        dt_date : calendar date
        hour : 0-23

        Returns
        -------
        OEESnapshot (the upserted row)
        """
        range_start, range_end = _hour_range(dt_date, hour)

        # Gather metrics concurrently
        parts_good, downtime_min, scrap, cycle_time = await asyncio.gather(
            self._count_parts(db, equipment_id, range_start, range_end),
            self._calc_downtime(db, equipment_id, range_start, range_end),
            self._get_scrap(db, equipment_id, range_start, range_end),
            self._get_equipment_cycle_time(db, equipment_id),
        )

        planned_min = _planned_min_for_hour(dt_date, hour)
        shift_name, _ = _shift_for_hour(dt_date, hour)
        shift_id = await self._get_shift_id(db, shift_name)

        # Guard against zero-division
        if planned_min <= 0:
            availability = 0.0
            performance = 0.0
        else:
            availability = _clamp((planned_min - downtime_min) / planned_min)

            target_cycle = cycle_time if cycle_time and cycle_time > 0 else 30.0
            max_possible = (planned_min * 60.0) / target_cycle
            performance = _clamp(parts_good / max_possible) if max_possible > 0 else 0.0

        total_parts = parts_good + scrap
        quality = _clamp(parts_good / total_parts) if total_parts > 0 else 1.0

        oee = availability * performance * quality

        # Upsert (INSERT ... ON CONFLICT UPDATE)
        stmt = pg_insert(OEESnapshot).values(
            equipment_id=equipment_id,
            shift_id=shift_id,
            date=dt_date,
            hour=hour,
            availability_pct=round(availability, 4),
            performance_pct=round(performance, 4),
            quality_pct=round(quality, 4),
            oee_pct=round(oee, 4),
            parts_good=parts_good,
            downtime_min=round(downtime_min, 2),
            planned_min=round(planned_min, 2),
        )

        # We need a unique constraint for ON CONFLICT.  Use a raw
        # DO UPDATE keyed on (equipment_id, date, hour).
        stmt = stmt.on_conflict_do_update(
            index_elements=["equipment_id", "date", "hour"],
            set_={
                "shift_id": stmt.excluded.shift_id,
                "availability_pct": stmt.excluded.availability_pct,
                "performance_pct": stmt.excluded.performance_pct,
                "quality_pct": stmt.excluded.quality_pct,
                "oee_pct": stmt.excluded.oee_pct,
                "parts_good": stmt.excluded.parts_good,
                "downtime_min": stmt.excluded.downtime_min,
                "planned_min": stmt.excluded.planned_min,
            },
        )

        await db.execute(stmt)
        await db.commit()

        # Fetch the row back for return value
        result = await db.execute(
            select(OEESnapshot).where(
                OEESnapshot.equipment_id == equipment_id,
                OEESnapshot.date == dt_date,
                OEESnapshot.hour == hour,
            )
        )
        snapshot = result.scalar_one()
        logger.info(
            "OEE hourly: equipment=%s date=%s hour=%02d => "
            "A=%.1f%% P=%.1f%% Q=%.1f%% OEE=%.1f%% parts=%d dt=%.1fmin",
            equipment_id,
            dt_date,
            hour,
            availability * 100,
            performance * 100,
            quality * 100,
            oee * 100,
            parts_good,
            downtime_min,
        )
        return snapshot

    async def calculate_shift(
        self,
        db: AsyncSession,
        equipment_id: str,
        dt_date: date,
        shift_name: str,
    ) -> OEESnapshot:
        """Calculate OEE for a full shift from raw events and upsert.

        Calculates directly from raw events for the shift time range
        rather than aggregating hourly snapshots, to ensure accuracy.

        Parameters
        ----------
        db : AsyncSession
        equipment_id : UUID of equipment
        dt_date : calendar date the shift starts on
        shift_name : one of T100, T200, T300

        Returns
        -------
        OEESnapshot (the upserted row, with hour=None for shift-level)
        """
        defn = SHIFT_DEFS.get(shift_name)
        if defn is None:
            raise ValueError(f"Unknown shift: {shift_name}")

        range_start, range_end = _shift_range(dt_date, shift_name)
        planned_min = defn["planned_min"]

        parts_good, downtime_min, scrap, cycle_time = await asyncio.gather(
            self._count_parts(db, equipment_id, range_start, range_end),
            self._calc_downtime(db, equipment_id, range_start, range_end),
            self._get_scrap(db, equipment_id, range_start, range_end),
            self._get_equipment_cycle_time(db, equipment_id),
        )

        shift_id = await self._get_shift_id(db, shift_name)

        # Availability
        if planned_min <= 0:
            availability = 0.0
            performance = 0.0
        else:
            availability = _clamp((planned_min - downtime_min) / planned_min)

            target_cycle = cycle_time if cycle_time and cycle_time > 0 else 30.0
            max_possible = (planned_min * 60.0) / target_cycle
            performance = _clamp(parts_good / max_possible) if max_possible > 0 else 0.0

        total_parts = parts_good + scrap
        quality = _clamp(parts_good / total_parts) if total_parts > 0 else 1.0

        oee = availability * performance * quality

        # Upsert — shift-level rows have hour=NULL
        stmt = pg_insert(OEESnapshot).values(
            equipment_id=equipment_id,
            shift_id=shift_id,
            date=dt_date,
            hour=None,
            availability_pct=round(availability, 4),
            performance_pct=round(performance, 4),
            quality_pct=round(quality, 4),
            oee_pct=round(oee, 4),
            parts_good=parts_good,
            downtime_min=round(downtime_min, 2),
            planned_min=round(planned_min, 2),
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["equipment_id", "date", "hour"],
            set_={
                "shift_id": stmt.excluded.shift_id,
                "availability_pct": stmt.excluded.availability_pct,
                "performance_pct": stmt.excluded.performance_pct,
                "quality_pct": stmt.excluded.quality_pct,
                "oee_pct": stmt.excluded.oee_pct,
                "parts_good": stmt.excluded.parts_good,
                "downtime_min": stmt.excluded.downtime_min,
                "planned_min": stmt.excluded.planned_min,
            },
        )

        await db.execute(stmt)
        await db.commit()

        result = await db.execute(
            select(OEESnapshot).where(
                OEESnapshot.equipment_id == equipment_id,
                OEESnapshot.date == dt_date,
                OEESnapshot.hour.is_(None),
                OEESnapshot.shift_id == shift_id,
            )
        )
        snapshot = result.scalar_one()
        logger.info(
            "OEE shift: equipment=%s date=%s shift=%s => "
            "A=%.1f%% P=%.1f%% Q=%.1f%% OEE=%.1f%% parts=%d dt=%.1fmin",
            equipment_id,
            dt_date,
            shift_name,
            availability * 100,
            performance * 100,
            quality * 100,
            oee * 100,
            parts_good,
            downtime_min,
        )
        return snapshot

    async def run_periodic(self, interval_seconds: int = 300) -> None:
        """Background loop: recalculate current-hour OEE for all active equipment.

        Runs indefinitely, sleeping *interval_seconds* between cycles.
        Designed to be launched as an ``asyncio.create_task()`` from the
        FastAPI lifespan.

        Parameters
        ----------
        interval_seconds : how often to recalculate (default 300 = 5 min)
        """
        logger.info(
            "OEE periodic calculator started (interval=%ds)", interval_seconds
        )

        while True:
            try:
                async with async_session() as db:
                    # Fetch all active equipment
                    result = await db.execute(
                        select(Equipment.id).where(Equipment.active.is_(True))
                    )
                    equipment_ids: list[str] = list(result.scalars().all())

                    now = datetime.now(timezone.utc)
                    current_date = now.date()

                    logger.info(
                        "OEE periodic run: %d active equipment, date=%s",
                        len(equipment_ids),
                        current_date,
                    )

                    # Recalculate ALL hours of today that have data
                    for eq_id in equipment_ids:
                        for hour in range(24):
                            try:
                                await self.calculate_hourly(
                                    db, eq_id, current_date, hour
                                )
                            except Exception:
                                logger.exception(
                                    "OEE calc failed for equipment=%s date=%s hour=%02d",
                                    eq_id,
                                    current_date,
                                    hour,
                                )

            except Exception:
                logger.exception("OEE periodic cycle failed")

            await asyncio.sleep(interval_seconds)
