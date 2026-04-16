"""Unit tests for the email service — no SMTP server required."""

import pytest

from api.services.email_service import (
    build_alert_html,
    build_resolution_html,
    send_alert_email,
    _html_to_plain,
)


class TestBuildAlertHtml:
    def test_contains_serial_number(self):
        html = build_alert_html("MEI-001", 1, 15.0, 32, "test message")
        assert "MEI-001" in html

    def test_contains_level(self):
        html = build_alert_html("MEI-001", 2, 30.0, 32, "test")
        assert "L2" in html
        assert "CR\u00cdTICO" in html

    def test_l1_shows_atencao(self):
        html = build_alert_html("MEI-001", 1, 10.0, 32, "test")
        assert "ATEN\u00c7\u00c3O" in html

    def test_contains_downtime_minutes(self):
        html = build_alert_html("MEI-001", 1, 42.7, 32, "test")
        assert "43 minutos" in html

    def test_contains_message(self):
        html = build_alert_html("MEI-001", 1, 10.0, 32, "Machine stopped")
        assert "Machine stopped" in html


class TestBuildResolutionHtml:
    def test_contains_serial_number(self):
        html = build_resolution_html("MEI-002", 25.0, "Resumed")
        assert "MEI-002" in html
        assert "Retomou" in html

    def test_contains_duration(self):
        html = build_resolution_html("MEI-002", 25.0, "Resumed")
        assert "25 minutos" in html


class TestHtmlToPlain:
    def test_strips_tags(self):
        result = _html_to_plain("<div><p>Hello <b>world</b></p></div>")
        assert "<" not in result
        assert "Hello" in result
        assert "world" in result

    def test_empty_string(self):
        assert _html_to_plain("") == ""


class TestSendAlertEmail:
    @pytest.mark.asyncio
    async def test_disabled_returns_false(self):
        # SMTP is disabled by default in test env
        result = await send_alert_email(
            "Test Subject",
            "<p>Test</p>",
            ["test@test.com"],
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_recipients_returns_false(self):
        result = await send_alert_email("Test", "<p>Test</p>", [])
        assert result is False
