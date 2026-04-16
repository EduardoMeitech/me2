"""Alerts router — active alerts, history, and acknowledgement."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.models import Alert, Equipment
from api.core.schemas import AlertResponse, APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _build_alert_dict(alert: Alert, equipment: Equipment | None) -> dict:
    """Build alert response dict with equipment info."""
    data = AlertResponse.model_validate(alert).model_dump(mode="json")
    if equipment:
        data["equipment_name"] = equipment.name
        data["serial_number"] = equipment.serial_number
    return data


@router.get("/active", response_model=APIResponse)
async def get_active_alerts(db: AsyncSession = Depends(get_db)) -> APIResponse:
    """Return all alerts that have not been resolved, with equipment info."""
    result = await db.execute(
        select(Alert, Equipment)
        .outerjoin(Equipment, Alert.equipment_id == Equipment.id)
        .where(Alert.resolved_at.is_(None))
        .order_by(Alert.started_at.desc())
    )
    rows = result.all()

    data = [_build_alert_dict(alert, eq) for alert, eq in rows]
    logger.debug("Returning %d active alerts", len(data))

    return APIResponse(
        success=True,
        data=data,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )


@router.get("/history", response_model=APIResponse)
async def get_alert_history(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    equipment_id: str | None = Query(None, description="Filter by equipment UUID"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Return resolved alerts from the last N days, with equipment info."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(Alert, Equipment)
        .outerjoin(Equipment, Alert.equipment_id == Equipment.id)
        .where(
            Alert.resolved_at.is_not(None),
            Alert.started_at >= cutoff,
        )
    )
    if equipment_id:
        query = query.where(Alert.equipment_id == equipment_id)

    query = query.order_by(Alert.started_at.desc())
    result = await db.execute(query)
    rows = result.all()

    data = [_build_alert_dict(alert, eq) for alert, eq in rows]
    logger.debug("Returning %d history alerts (last %d days)", len(data), days)

    return APIResponse(
        success=True,
        data=data,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )


@router.get("/summary", response_model=APIResponse)
async def get_alert_summary(db: AsyncSession = Depends(get_db)) -> APIResponse:
    """Return alert counts: active (L1, L2), resolved today."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Active counts by level
    active_result = await db.execute(
        select(Alert.level, func.count(Alert.id))
        .where(Alert.resolved_at.is_(None))
        .group_by(Alert.level)
    )
    active_by_level = {level: count for level, count in active_result.all()}

    # Resolved today count
    resolved_result = await db.execute(
        select(func.count(Alert.id)).where(
            Alert.resolved_at.is_not(None),
            Alert.resolved_at >= today_start,
        )
    )
    resolved_today = resolved_result.scalar_one()

    data = {
        "active_total": sum(active_by_level.values()),
        "active_l1": active_by_level.get(1, 0),
        "active_l2": active_by_level.get(2, 0),
        "resolved_today": resolved_today,
    }

    return APIResponse(
        success=True,
        data=data,
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )


@router.post("/{alert_id}/acknowledge", response_model=APIResponse)
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
) -> APIResponse:
    """Set acknowledged_at = now() on the specified alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert: Alert | None = result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    if alert.acknowledged_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alert already acknowledged",
        )

    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(alert)

    logger.info("Alert %s acknowledged", alert_id)

    return APIResponse(
        success=True,
        data=AlertResponse.model_validate(alert).model_dump(mode="json"),
        meta={"version": "1.0", "ts": datetime.now(timezone.utc).isoformat()},
    )
