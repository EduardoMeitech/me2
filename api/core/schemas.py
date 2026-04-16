"""Pydantic v2 schemas for ME2 API request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------

class APIResponse(BaseModel):
    success: bool = True
    data: Any = None
    meta: dict = Field(default_factory=lambda: {"version": "1.0"})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    role: str


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

class EquipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    serial_number: str
    name: str
    model: str | None = None
    manufacturer: str | None = None
    standard_cycle_time_s: float | None = None
    active: bool = True


class EquipmentLiveResponse(BaseModel):
    serial_number: str
    word_status: int | None = None
    parts_ok: int | None = None
    cycle_time_s: float | None = None
    product_no: str | None = None
    ts: datetime | None = None


# ---------------------------------------------------------------------------
# OEE
# ---------------------------------------------------------------------------

class OEEResponse(BaseModel):
    equipment_id: str
    date: str
    shift: str | None = None
    hour: int | None = None
    availability_pct: float = 0.0
    performance_pct: float = 0.0
    quality_pct: float = 1.0
    oee_pct: float = 0.0
    parts_good: int = 0
    downtime_min: float = 0.0
    planned_min: float = 0.0


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------

class ProductionHourResponse(BaseModel):
    hour: str
    parts_ok: int = 0
    product_no: str | None = None


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class StatusEventResponse(BaseModel):
    word_status: int
    ts: datetime
    duration_min: float | None = None


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    equipment_id: str
    level: int
    message: str | None = None
    started_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    equipment_name: str | None = None
    serial_number: str | None = None


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

class QualityCreate(BaseModel):
    equipment_id: str
    quantity_scrap: int = 0
    quantity_rework: int = 0
    reason_code: str | None = None
