"""Reports router — shift and daily summary reports."""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.models import Equipment, OEESnapshot, ProductionEvent, StatusEvent
from api.core.schemas import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

# Shift UTC ranges (BRT-3 → UTC)
SHIFT_UTC_RANGES = {
    "T100": (timedelta(hours=8, minutes=0), timedelta(hours=16, minutes=29), 509),
    "T200": (timedelta(hours=16, minutes=30), timedelta(hours=23, minutes=59), 509),
    "T300": (timedelta(hours=1, minutes=0), timedelta(hours=7, minutes=59), 420),
}

SHIFT_LABELS = {"T100": "Turno 1", "T200": "Turno 2", "T300": "Turno 3"}


def _resolve_shift_range(
    parsed_date: date_type, shift: str
) -> tuple[datetime, datetime, int]:
    """Return (start_utc, end_utc, planned_minutes) for a shift code."""
    if shift not in SHIFT_UTC_RANGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid shift '{shift}'. Use T100, T200, or T300.",
        )
    start_offset, end_offset, planned_min = SHIFT_UTC_RANGES[shift]
    base = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=timezone.utc)
    start = base + start_offset
    end = base + end_offset + timedelta(minutes=1)
    if end <= start:
        end += timedelta(days=1)
    return start, end, planned_min


@router.get("/shift", response_model=APIResponse)
async def shift_report(
    equipment_id: str = Query(..., description="Equipment UUID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    shift: str = Query(..., description="Shift code: T100, T200, T300"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Return a shift summary: total parts, OEE (E2 formula), downtime, and status breakdown."""
    # Validate equipment
    eq_result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    )
    equipment: Equipment | None = eq_result.scalar_one_or_none()
    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment {equipment_id} not found",
        )

    # Parse date
    try:
        parsed_date: date_type = date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    shift_start, shift_end, planned_min = _resolve_shift_range(parsed_date, shift)

    # --- Total parts produced during the shift ---
    parts_result = await db.execute(
        select(func.coalesce(func.sum(ProductionEvent.parts_ok), 0)).where(
            ProductionEvent.equipment_id == equipment_id,
            ProductionEvent.ts >= shift_start,
            ProductionEvent.ts < shift_end,
        )
    )
    total_parts: int = int(parts_result.scalar_one())

    # --- Status breakdown with duration (not just count) ---
    status_result = await db.execute(
        select(StatusEvent)
        .where(
            StatusEvent.equipment_id == equipment_id,
            StatusEvent.ts >= shift_start,
            StatusEvent.ts < shift_end,
        )
        .order_by(StatusEvent.ts.asc())
    )
    status_rows = status_result.scalars().all()

    # Calculate durations per status
    status_durations: dict[int, float] = {}
    total_downtime_min = 0.0
    for i, row in enumerate(status_rows):
        if i + 1 < len(status_rows):
            duration = (status_rows[i + 1].ts - row.ts).total_seconds() / 60.0
        else:
            # Last event: duration until shift end or now (whichever is earlier)
            cap = min(shift_end, datetime.now(timezone.utc))
            duration = max((cap - row.ts).total_seconds() / 60.0, 0)

        ws = row.word_status
        status_durations[ws] = status_durations.get(ws, 0) + duration
        if ws != 18 and ws != 19:
            total_downtime_min += duration

    status_breakdown = [
        {"word_status": ws, "duration_min": round(dur, 1)}
        for ws, dur in sorted(status_durations.items(), key=lambda x: -x[1])
    ]

    # --- OEE calculation (E2 formula from totals) ---
    cycle_time = equipment.standard_cycle_time_s or 0
    availability = (planned_min - total_downtime_min) / planned_min if planned_min > 0 else 0
    availability = max(0, min(availability, 1))
    max_possible = (planned_min * 60) / cycle_time if cycle_time > 0 else 0
    performance = total_parts / max_possible if max_possible > 0 else 0
    performance = min(performance, 1)
    quality = 1.0  # No scrap data in POC
    oee = availability * performance * quality

    data = {
        "equipment_id": equipment_id,
        "equipment_name": equipment.name,
        "serial_number": equipment.serial_number,
        "date": date,
        "shift": shift,
        "shift_label": SHIFT_LABELS.get(shift, shift),
        "total_parts": total_parts,
        "oee": {
            "availability_pct": round(availability, 4),
            "performance_pct": round(performance, 4),
            "quality_pct": round(quality, 4),
            "oee_pct": round(oee, 4),
        },
        "downtime_min": round(total_downtime_min, 1),
        "planned_min": planned_min,
        "cycle_time_s": cycle_time,
        "status_breakdown": status_breakdown,
    }

    logger.info("Generated shift report for equipment=%s date=%s shift=%s", equipment_id, date, shift)

    return APIResponse(
        success=True,
        data=data,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )
