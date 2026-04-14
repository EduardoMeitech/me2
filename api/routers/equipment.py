"""Equipment router — list equipment and live status."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.models import Equipment, ProductionEvent, StatusEvent
from api.core.schemas import (
    APIResponse,
    EquipmentLiveResponse,
    EquipmentResponse,
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
