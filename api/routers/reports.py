"""Reports router — shift summary report."""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.models import Equipment, OEESnapshot, ProductionEvent, Shift, StatusEvent
from api.core.schemas import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/shift", response_model=APIResponse)
async def shift_report(
    equipment_id: str = Query(..., description="Equipment UUID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    shift: str = Query(..., description="Shift name"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Return a shift summary: total parts, OEE, downtime, and status breakdown."""
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

    # Resolve shift
    shift_result = await db.execute(
        select(Shift).where(Shift.name == shift)
    )
    shift_row: Shift | None = shift_result.scalar_one_or_none()
    if shift_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shift '{shift}' not found",
        )

    # Determine shift time range
    shift_start: datetime = datetime.combine(
        parsed_date, shift_row.start_time, tzinfo=timezone.utc
    )
    shift_end: datetime = datetime.combine(
        parsed_date, shift_row.end_time, tzinfo=timezone.utc
    )
    if shift_end <= shift_start:
        shift_end += timedelta(days=1)

    # --- Total parts produced during the shift ---
    parts_result = await db.execute(
        select(func.coalesce(func.sum(ProductionEvent.parts_ok), 0)).where(
            ProductionEvent.equipment_id == equipment_id,
            ProductionEvent.ts >= shift_start,
            ProductionEvent.ts < shift_end,
        )
    )
    total_parts: int = int(parts_result.scalar_one())

    # --- OEE aggregate for the shift ---
    oee_result = await db.execute(
        select(
            func.avg(OEESnapshot.availability_pct).label("avg_availability"),
            func.avg(OEESnapshot.performance_pct).label("avg_performance"),
            func.avg(OEESnapshot.quality_pct).label("avg_quality"),
            func.avg(OEESnapshot.oee_pct).label("avg_oee"),
            func.coalesce(func.sum(OEESnapshot.downtime_min), 0.0).label("total_downtime"),
            func.coalesce(func.sum(OEESnapshot.planned_min), 0.0).label("total_planned"),
        ).where(
            OEESnapshot.equipment_id == equipment_id,
            OEESnapshot.date == parsed_date,
            OEESnapshot.shift_id == shift_row.id,
        )
    )
    oee_row = oee_result.one()

    # --- Status breakdown during the shift ---
    status_result = await db.execute(
        select(
            StatusEvent.word_status,
            func.count(StatusEvent.id).label("count"),
        )
        .where(
            StatusEvent.equipment_id == equipment_id,
            StatusEvent.ts >= shift_start,
            StatusEvent.ts < shift_end,
        )
        .group_by(StatusEvent.word_status)
        .order_by(StatusEvent.word_status)
    )
    status_breakdown: list[dict] = [
        {"word_status": row.word_status, "count": row.count}
        for row in status_result.all()
    ]

    data = {
        "equipment_id": equipment_id,
        "equipment_name": equipment.name,
        "date": date,
        "shift": shift,
        "total_parts": total_parts,
        "oee": {
            "availability_pct": round(float(oee_row.avg_availability or 0), 2),
            "performance_pct": round(float(oee_row.avg_performance or 0), 2),
            "quality_pct": round(float(oee_row.avg_quality or 0), 2),
            "oee_pct": round(float(oee_row.avg_oee or 0), 2),
        },
        "downtime_min": round(float(oee_row.total_downtime), 2),
        "planned_min": round(float(oee_row.total_planned), 2),
        "status_breakdown": status_breakdown,
    }

    logger.info("Generated shift report for equipment=%s date=%s shift=%s", equipment_id, date, shift)

    return APIResponse(
        success=True,
        data=data,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )
