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
        shift_result = await db.execute(
            select(Shift).where(Shift.name == shift)
        )
        shift_row: Shift | None = shift_result.scalar_one_or_none()
        if shift_row is not None:
            day_start = datetime.combine(parsed_date, shift_row.start_time, tzinfo=timezone.utc)
            day_end = datetime.combine(parsed_date, shift_row.end_time, tzinfo=timezone.utc)
            # Handle overnight shifts
            if day_end <= day_start:
                day_end += timedelta(days=1)

    # Query hourly aggregation
    hour_extract = func.date_trunc("hour", ProductionEvent.ts)
    stmt = (
        select(
            hour_extract.label("hour_bucket"),
            func.sum(ProductionEvent.parts_ok).label("total_parts"),
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
            parts_ok=int(row.total_parts) if row.total_parts else 0,
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
