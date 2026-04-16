"""Production router — hourly production data for equipment."""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.models import Equipment, ProductionEvent, Shift
from api.core.schemas import APIResponse, ProductionHourResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/equipment", tags=["production"])


@router.get("/{equipment_id}/production", response_model=APIResponse)
async def get_production(
    equipment_id: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    shift: str | None = Query(None, description="Shift name (optional)"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Return hourly production data for a given equipment and date."""
    # Validate equipment exists
    eq_result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    )
    if eq_result.scalar_one_or_none() is None:
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

    # Determine time range
    day_start: datetime = datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
    day_end: datetime = day_start + timedelta(days=1)

    if shift is not None:
        # Shift times are stored in local BRT; convert to UTC (+3h)
        # T100: 05:00-13:29 BRT = 08:00-16:29 UTC
        # T200: 13:30-21:59 BRT = 16:30-00:59 UTC
        # T300: 22:00-04:59 BRT = 01:00-07:59 UTC
        shift_utc_ranges = {
            "T100": (timedelta(hours=8, minutes=0), timedelta(hours=16, minutes=29)),
            "T200": (timedelta(hours=16, minutes=30), timedelta(hours=23, minutes=59)),
            "T300": (timedelta(hours=1, minutes=0), timedelta(hours=7, minutes=59)),
        }
        if shift in shift_utc_ranges:
            start_offset, end_offset = shift_utc_ranges[shift]
            base = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=timezone.utc)
            day_start = base + start_offset
            day_end = base + end_offset + timedelta(minutes=1)
            # T300 crosses midnight: end is next calendar day
            if day_end <= day_start:
                day_end += timedelta(days=1)

    # Query hourly aggregation — each production_event row represents one
    # trigger-on-change (≈ 1 part produced). COUNT(*) is robust against
    # counter resets at shift boundaries. Same strategy as oee_calculator.
    hour_extract = func.date_trunc("hour", ProductionEvent.ts)
    stmt = (
        select(
            hour_extract.label("hour_bucket"),
            func.count(ProductionEvent.id).label("parts_count"),
            func.max(ProductionEvent.product_no).label("product_no"),
        )
        .where(
            ProductionEvent.equipment_id == equipment_id,
            ProductionEvent.ts >= day_start,
            ProductionEvent.ts < day_end,
        )
        .group_by(hour_extract)
        .order_by(hour_extract)
    )

    result = await db.execute(stmt)
    rows = result.all()

    data = [
        ProductionHourResponse(
            hour=row.hour_bucket.strftime("%H:%M") if row.hour_bucket else "00:00",
            parts_ok=int(row.parts_count) if row.parts_count else 0,
            product_no=row.product_no,
        ).model_dump()
        for row in rows
    ]

    logger.debug(
        "Returning %d hourly production rows for equipment=%s date=%s",
        len(data), equipment_id, date,
    )

    return APIResponse(
        success=True,
        data=data,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )
