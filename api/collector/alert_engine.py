"""Alert engine for equipment downtime monitoring.

Tracks per-equipment downtime duration and fires tiered alerts (L1, L2)
when configurable thresholds are exceeded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Default uptime status code (machine running normally)
DEFAULT_UPTIME_STATUS = 18


@dataclass
class Alert:
    """Represents a single alert or resolution event."""
    serial_number: str
    timestamp: datetime
    level: int          # 1 = L1, 2 = L2, 0 = resolution
    downtime_minutes: float
    word_status: int
    message: str


class AlertEngine:
    """Monitors word-status transitions and generates downtime alerts.

    Configuration per equipment (inside the config dict):
        uptime_status_code : int  -- status value that means "running" (default 18)
        downtime_l1_min    : int  -- minutes before L1 alert fires
        downtime_l2_min    : int  -- minutes before L2 alert fires
        alert_recipients   : list[str]  -- email addresses
    """

    def __init__(self):
        self._downtime_start: dict[str, datetime] = {}
        self._alert_sent: dict[str, int] = {}  # 0=none, 1=L1, 2=L2

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_status(
        self,
        serial_number: str,
        word_status: int,
        config: dict,
    ) -> Alert | None:
        """Evaluate the current word_status and return an Alert when appropriate.

        Returns None if no alert or resolution is warranted.
        """
        uptime_code = config.get("uptime_status_code", DEFAULT_UPTIME_STATUS)
        l1_min = config.get("downtime_l1_min")
        l2_min = config.get("downtime_l2_min")

        is_running = word_status == uptime_code
        now = datetime.now(tz=timezone.utc)

        if is_running:
            return self._handle_uptime(serial_number, word_status, now)
        else:
            return self._handle_downtime(
                serial_number, word_status, now, l1_min, l2_min, config
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _handle_uptime(
        self,
        serial_number: str,
        word_status: int,
        now: datetime,
    ) -> Alert | None:
        """Machine is running — clear timers and emit resolution if we had an alert."""
        previous_level = self._alert_sent.get(serial_number, 0)

        if serial_number in self._downtime_start:
            downtime_start = self._downtime_start.pop(serial_number)
            downtime_min = (now - downtime_start).total_seconds() / 60.0
            self._alert_sent[serial_number] = 0

            if previous_level > 0:
                msg = (
                    f"[{serial_number}] Equipment resumed after "
                    f"{downtime_min:.1f} min downtime (was L{previous_level})"
                )
                logger.info(msg)
                return Alert(
                    serial_number=serial_number,
                    timestamp=now,
                    level=0,
                    downtime_minutes=round(downtime_min, 1),
                    word_status=word_status,
                    message=msg,
                )
            else:
                logger.debug("[%s] Uptime restored (no alert was active)", serial_number)
        return None

    def _handle_downtime(
        self,
        serial_number: str,
        word_status: int,
        now: datetime,
        l1_min: int | None,
        l2_min: int | None,
        config: dict,
    ) -> Alert | None:
        """Machine is NOT running — track duration, fire alerts at thresholds."""
        # Start tracking if not already
        if serial_number not in self._downtime_start:
            self._downtime_start[serial_number] = now
            self._alert_sent.setdefault(serial_number, 0)
            logger.info(
                "[%s] Downtime started (word_status=%d)", serial_number, word_status
            )
            return None

        downtime_start = self._downtime_start[serial_number]
        downtime_min = (now - downtime_start).total_seconds() / 60.0
        current_level = self._alert_sent.get(serial_number, 0)

        # Check L2 threshold first (higher priority)
        if l2_min is not None and downtime_min >= l2_min and current_level < 2:
            self._alert_sent[serial_number] = 2
            msg = (
                f"[{serial_number}] L2 ALERT: equipment down for "
                f"{downtime_min:.1f} min (threshold={l2_min} min, status={word_status})"
            )
            logger.warning(msg)
            self._fire_email(serial_number, msg, config, level=2)
            return Alert(
                serial_number=serial_number,
                timestamp=now,
                level=2,
                downtime_minutes=round(downtime_min, 1),
                word_status=word_status,
                message=msg,
            )

        # Check L1 threshold
        if l1_min is not None and downtime_min >= l1_min and current_level < 1:
            self._alert_sent[serial_number] = 1
            msg = (
                f"[{serial_number}] L1 ALERT: equipment down for "
                f"{downtime_min:.1f} min (threshold={l1_min} min, status={word_status})"
            )
            logger.warning(msg)
            self._fire_email(serial_number, msg, config, level=1)
            return Alert(
                serial_number=serial_number,
                timestamp=now,
                level=1,
                downtime_minutes=round(downtime_min, 1),
                word_status=word_status,
                message=msg,
            )

        return None

    # ------------------------------------------------------------------
    # Email placeholder
    # ------------------------------------------------------------------

    def _fire_email(
        self,
        serial_number: str,
        message: str,
        config: dict,
        level: int,
    ) -> None:
        """Synchronous wrapper that schedules the async email send.

        In the collector loop (async context) this would be awaited directly.
        Here we just log, since actual email delivery is a TODO.
        """
        recipients = config.get("alert_recipients", [])
        subject = f"ME2 Downtime L{level} — {serial_number}"
        logger.info(
            "Would send email alert: subject='%s' to=%s", subject, recipients
        )
        # TODO: integrate with actual SMTP / notification service
        # await self._send_email_alert(subject, message, recipients)

    async def _send_email_alert(
        self,
        subject: str,
        body: str,
        recipients: list[str],
    ) -> None:
        """Placeholder for sending email alerts.

        Replace with aiosmtplib or an HTTP call to your notification
        microservice.
        """
        logger.info(
            "Sending email: subject='%s' recipients=%s body_len=%d",
            subject,
            recipients,
            len(body),
        )
        # TODO: implement actual email sending
        # async with aiosmtplib.SMTP(...) as smtp:
        #     await smtp.send_message(msg)
