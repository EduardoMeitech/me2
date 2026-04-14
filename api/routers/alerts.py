"""Alerts router — active alerts and acknowledgement."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.models import Alert
from api.core.schemas import AlertResponse, APIResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("/active", response_model=APIResponse)
async def get_active_alerts(db: AsyncSession = Depends(get_db)) -> APIResponse:
    """Return all alerts that have not been resolved."""
    result = await db.execute(
        select(Alert)
        .where(Alert.resolved_at.is_(None))
        .order_by(Alert.started_at.desc())
    )
    rows = result.scalars().all()

    data = [AlertResponse.model_validate(a).model_dump(mode="json") for a in rows]
    logger.debug("Returning %d active alerts", len(data))

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
