"""Email service for ME2 alert notifications via SMTP.

Uses aiosmtplib for async sending. Gracefully degrades to logging
when SMTP is not configured (smtp_enabled=False).
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

from api.core.config import settings

logger = logging.getLogger(__name__)


async def send_alert_email(
    subject: str,
    body_html: str,
    recipients: list[str],
) -> bool:
    """Send an alert email to the given recipients.

    Returns True if sent successfully, False otherwise.
    When SMTP is disabled, logs the email and returns False.
    """
    if not settings.smtp_enabled:
        logger.info(
            "[EMAIL DISABLED] Would send: subject='%s' to=%s",
            subject,
            recipients,
        )
        return False

    if not recipients:
        logger.warning("No recipients for alert email: %s", subject)
        return False

    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP credentials not configured — skipping email")
        return False

    try:
        import aiosmtplib

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from}>"
        msg["To"] = ", ".join(recipients)
        msg.set_content(_html_to_plain(body_html))
        msg.add_alternative(body_html, subtype="html")

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )

        logger.info(
            "Alert email sent: subject='%s' to=%s", subject, recipients
        )
        return True

    except Exception:
        logger.exception("Failed to send alert email: subject='%s'", subject)
        return False


def build_alert_html(
    serial_number: str,
    level: int,
    downtime_minutes: float,
    word_status: int,
    message: str,
) -> str:
    """Build a simple HTML email body for a downtime alert."""
    level_color = "#BA1A1A" if level >= 2 else "#F57C00"
    level_label = "CRÍTICO" if level >= 2 else "ATENÇÃO"

    return f"""\
<div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: {level_color}; color: #FFFFFF; padding: 16px 24px; border-radius: 8px 8px 0 0;">
    <h2 style="margin: 0; font-size: 20px;">
      ME2 Alerta L{level} — {level_label}
    </h2>
  </div>
  <div style="background: #FFFFFF; padding: 24px; border: 1px solid #E0E0E0; border-top: none; border-radius: 0 0 8px 8px;">
    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
      <tr>
        <td style="padding: 8px 0; color: #666;">Equipamento</td>
        <td style="padding: 8px 0; font-weight: 600;">{serial_number}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #666;">Tempo parado</td>
        <td style="padding: 8px 0; font-weight: 600; color: {level_color};">{downtime_minutes:.0f} minutos</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #666;">Status</td>
        <td style="padding: 8px 0;">{word_status}</td>
      </tr>
    </table>
    <p style="margin-top: 16px; padding: 12px; background: #F5F5F5; border-radius: 4px; font-size: 13px; color: #333;">
      {message}
    </p>
    <p style="margin-top: 16px; font-size: 12px; color: #999;">
      ME2 — Meitech Industrial · Keep Moving
    </p>
  </div>
</div>"""


def build_resolution_html(
    serial_number: str,
    downtime_minutes: float,
    message: str,
) -> str:
    """Build a simple HTML email body for an alert resolution."""
    return f"""\
<div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #388E3C; color: #FFFFFF; padding: 16px 24px; border-radius: 8px 8px 0 0;">
    <h2 style="margin: 0; font-size: 20px;">
      ME2 — Equipamento Retomou Produção
    </h2>
  </div>
  <div style="background: #FFFFFF; padding: 24px; border: 1px solid #E0E0E0; border-top: none; border-radius: 0 0 8px 8px;">
    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
      <tr>
        <td style="padding: 8px 0; color: #666;">Equipamento</td>
        <td style="padding: 8px 0; font-weight: 600;">{serial_number}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #666;">Duração da parada</td>
        <td style="padding: 8px 0; font-weight: 600;">{downtime_minutes:.0f} minutos</td>
      </tr>
    </table>
    <p style="margin-top: 16px; padding: 12px; background: #E8F5E9; border-radius: 4px; font-size: 13px; color: #333;">
      {message}
    </p>
    <p style="margin-top: 16px; font-size: 12px; color: #999;">
      ME2 — Meitech Industrial · Keep Moving
    </p>
  </div>
</div>"""


def _html_to_plain(html: str) -> str:
    """Crude HTML-to-plaintext fallback — strip tags."""
    import re
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text
