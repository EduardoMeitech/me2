"""Equipment router — list equipment and live status."""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.models import Equipment, ProductionEvent, StatusEvent
from api.core.schemas import (
    APIResponse,
    EquipmentLiveResponse,
    EquipmentResponse,
    StatusEventResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/equipment", tags=["equipment"])


@router.get("/", response_model=APIResponse)
async def list_equipment(db: AsyncSession = Depends(get_db)) -> APIResponse:
    """Return all active equipment."""
    result = await db.execute(
        select(Equipment).where(Equipment.active.is_(True)).order_by(Equipment.name)
    )
    rows = result.scalars().all()

    data = [EquipmentResponse.model_validate(eq).model_dump() for eq in rows]
    logger.debug("Returning %d active equipment records", len(data))

    return APIResponse(
        success=True,
        data=data,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )


@router.get("/{equipment_id}/live", response_model=APIResponse)
async def equipment_live(
    equipment_id: str,
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Return the latest ProductionEvent and StatusEvent for a given equipment."""
    # Verify equipment exists
    eq_result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    )
    equipment: Equipment | None = eq_result.scalar_one_or_none()
    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment {equipment_id} not found",
        )

    # Latest production event
    prod_result = await db.execute(
        select(ProductionEvent)
        .where(ProductionEvent.equipment_id == equipment_id)
        .order_by(ProductionEvent.ts.desc())
        .limit(1)
    )
    prod: ProductionEvent | None = prod_result.scalar_one_or_none()

    # Latest status event
    stat_result = await db.execute(
        select(StatusEvent)
        .where(StatusEvent.equipment_id == equipment_id)
        .order_by(StatusEvent.ts.desc())
        .limit(1)
    )
    stat: StatusEvent | None = stat_result.scalar_one_or_none()

    live = EquipmentLiveResponse(
        serial_number=equipment.serial_number,
        word_status=stat.word_status if stat else None,
        parts_ok=prod.parts_ok if prod else None,
        cycle_time_s=prod.cycle_time_s if prod else None,
        product_no=prod.product_no if prod else None,
        ts=stat.ts if stat else (prod.ts if prod else None),
    )

    return APIResponse(
        success=True,
        data=live.model_dump(mode="json"),
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )


@router.get("/{equipment_id}/status", response_model=APIResponse)
async def equipment_status(
    equipment_id: str,
    date: str | None = Query(None, description="Date YYYY-MM-DD (default today)"),
    shift: str | None = Query(None, description="Shift: T100, T200, T300"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Return status events for the given equipment, date and shift, with durations."""
    # Parse date
    if date:
        try:
            target_date = date_type.fromisoformat(date)
        except ValueError:
            target_date = datetime.now(timezone.utc).date()
    else:
        target_date = datetime.now(timezone.utc).date()

    # Shift time ranges (UTC — Sao Paulo is UTC-3, shifts defined in local time)
    # T100: 05:00-13:29 local = 08:00-16:29 UTC
    # T200: 13:30-21:59 local = 16:30-00:59 UTC
    # T300: 22:00-04:59 local = 01:00-07:59 UTC
    shift_ranges = {
        "T100": (timedelta(hours=8, minutes=0), timedelta(hours=16, minutes=29)),
        "T200": (timedelta(hours=16, minutes=30), timedelta(hours=23, minutes=59)),
        "T300": (timedelta(hours=1, minutes=0), timedelta(hours=7, minutes=59)),
    }

    if shift and shift in shift_ranges:
        start_offset, end_offset = shift_ranges[shift]
        day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc) + start_offset
        day_end = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc) + end_offset + timedelta(minutes=1)
        if shift == "T300":
            # T300 crosses midnight — end is next day
            day_end = day_end + timedelta(days=1)
    else:
        # Full day: 05:00 local (08:00 UTC) to next day 05:00
        day_start = datetime(target_date.year, target_date.month, target_date.day, 8, 0, tzinfo=timezone.utc)
        day_end = day_start + timedelta(hours=24)

    result = await db.execute(
        select(StatusEvent)
        .where(
            and_(
                StatusEvent.equipment_id == equipment_id,
                StatusEvent.ts >= day_start,
                StatusEvent.ts < day_end,
            )
        )
        .order_by(StatusEvent.ts.asc())
    )
    rows = result.scalars().all()

    # Calculate duration for each status event.
    # Last event: cap at shift/day end or now (whichever is earlier) to avoid
    # inflating durations when viewing historical data.
    cap = min(day_end, datetime.now(timezone.utc))
    events = []
    for i, row in enumerate(rows):
        if i + 1 < len(rows):
            duration = (rows[i + 1].ts - row.ts).total_seconds() / 60.0
        else:
            duration = max((cap - row.ts).total_seconds() / 60.0, 0)

        events.append(
            StatusEventResponse(
                word_status=row.word_status,
                ts=row.ts,
                duration_min=round(duration, 1),
            ).model_dump(mode="json")
        )

    return APIResponse(
        success=True,
        data=events,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )
