"""OEE router — query OEE snapshots for equipment."""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.models import Equipment, OEESnapshot, Shift
from api.core.schemas import APIResponse, OEEResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/equipment", tags=["oee"])


@router.get("/{equipment_id}/oee", response_model=APIResponse)
async def get_oee(
    equipment_id: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    shift: str | None = Query(None, description="Shift name (optional)"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Return OEE snapshot data for a given equipment, date, and optional shift."""
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

    # Build query
    stmt = select(OEESnapshot).where(
        OEESnapshot.equipment_id == equipment_id,
        OEESnapshot.date == parsed_date,
    )

    # Filter by shift if provided
    if shift is not None:
        shift_result = await db.execute(
            select(Shift).where(Shift.name == shift)
        )
        shift_row: Shift | None = shift_result.scalar_one_or_none()
        if shift_row is not None:
            stmt = stmt.where(OEESnapshot.shift_id == shift_row.id)
        else:
            # Shift name not found — return empty result
            return APIResponse(
                success=True,
                data=[],
                meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
            )

    stmt = stmt.order_by(OEESnapshot.hour)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    data = [
        OEEResponse(
            equipment_id=row.equipment_id,
            date=str(row.date),
            shift=shift,
            hour=row.hour,
            availability_pct=row.availability_pct,
            performance_pct=row.performance_pct,
            quality_pct=row.quality_pct,
            oee_pct=row.oee_pct,
            parts_good=row.parts_good,
            downtime_min=row.downtime_min,
            planned_min=row.planned_min,
        ).model_dump()
        for row in rows
    ]

    logger.debug("Returning %d OEE rows for equipment=%s date=%s", len(data), equipment_id, date)

    return APIResponse(
        success=True,
        data=data,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )
