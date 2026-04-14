"""SQLAlchemy ORM models for ME2 — PostgreSQL 16."""

from __future__ import annotations

import enum
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    meitech_admin = "meitech_admin"
    meitech_support = "meitech_support"
    client_admin = "client_admin"
    client_operator = "client_operator"


# ---------------------------------------------------------------------------
# Admin / Config tables
# ---------------------------------------------------------------------------

class Tenant(Base):
    __tablename__ = "me2_tenants"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(3), default="BRA")
    timezone: Mapped[str] = mapped_column(String(50), default="America/Sao_Paulo")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    users: Mapped[list[User]] = relationship(back_populates="tenant")
    plants: Mapped[list[Plant]] = relationship(back_populates="tenant")


class User(Base):
    __tablename__ = "me2_users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("me2_tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class Plant(Base):
    __tablename__ = "me2_plants"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("me2_tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300))
    timezone: Mapped[str] = mapped_column(String(50), default="America/Sao_Paulo")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    tenant: Mapped[Tenant] = relationship(back_populates="plants")
    equipment: Mapped[list[Equipment]] = relationship(back_populates="plant")
    shifts: Mapped[list[Shift]] = relationship(back_populates="plant")


class Equipment(Base):
    __tablename__ = "me2_equipment"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    plant_id: Mapped[str] = mapped_column(ForeignKey("me2_plants.id"), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    standard_cycle_time_s: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    plant: Mapped[Plant] = relationship(back_populates="equipment")


class Shift(Base):
    __tablename__ = "me2_shifts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    plant_id: Mapped[str] = mapped_column(ForeignKey("me2_plants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    days: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    plant: Mapped[Plant] = relationship(back_populates="shifts")


class Target(Base):
    __tablename__ = "me2_targets"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[str] = mapped_column(ForeignKey("me2_equipment.id"), nullable=False)
    shift_id: Mapped[str] = mapped_column(ForeignKey("me2_shifts.id"), nullable=False)
    target_parts_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


# ---------------------------------------------------------------------------
# Time-series event tables
# ---------------------------------------------------------------------------

class ProductionEvent(Base):
    __tablename__ = "production_events"
    __table_args__ = (
        Index("ix_production_equipment_ts", "equipment_id", "ts"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[str] = mapped_column(ForeignKey("me2_equipment.id"), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(30), nullable=False)
    product_no: Mapped[str | None] = mapped_column(String(30))
    parts_ok: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_time_s: Mapped[float | None] = mapped_column(Float)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StatusEvent(Base):
    __tablename__ = "status_events"
    __table_args__ = (
        Index("ix_status_equipment_ts", "equipment_id", "ts"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[str] = mapped_column(ForeignKey("me2_equipment.id"), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(30), nullable=False)
    word_status: Mapped[int] = mapped_column(Integer, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProcessEvent(Base):
    __tablename__ = "process_events"
    __table_args__ = (
        Index("ix_process_equipment_ts", "equipment_id", "ts"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[str] = mapped_column(ForeignKey("me2_equipment.id"), nullable=False)
    variable_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectionLog(Base):
    __tablename__ = "connection_log"
    __table_args__ = (
        Index("ix_connlog_equipment_ts", "equipment_id", "ts"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[str] = mapped_column(ForeignKey("me2_equipment.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Aggregated / computed tables
# ---------------------------------------------------------------------------

class OEESnapshot(Base):
    __tablename__ = "oee_snapshots"
    __table_args__ = (
        Index("ix_oee_equipment_date", "equipment_id", "date"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[str] = mapped_column(ForeignKey("me2_equipment.id"), nullable=False)
    shift_id: Mapped[str | None] = mapped_column(ForeignKey("me2_shifts.id"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    hour: Mapped[int | None] = mapped_column(Integer)
    availability_pct: Mapped[float] = mapped_column(Float, default=0.0)
    performance_pct: Mapped[float] = mapped_column(Float, default=0.0)
    quality_pct: Mapped[float] = mapped_column(Float, default=1.0)
    oee_pct: Mapped[float] = mapped_column(Float, default=0.0)
    parts_good: Mapped[int] = mapped_column(Integer, default=0)
    downtime_min: Mapped[float] = mapped_column(Float, default=0.0)
    planned_min: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[str] = mapped_column(ForeignKey("me2_equipment.id"), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Quality(Base):
    __tablename__ = "me2_quality"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    equipment_id: Mapped[str] = mapped_column(ForeignKey("me2_equipment.id"), nullable=False)
    operator_id: Mapped[str | None] = mapped_column(ForeignKey("me2_users.id"))
    quantity_scrap: Mapped[int] = mapped_column(Integer, default=0)
    quantity_rework: Mapped[int] = mapped_column(Integer, default=0)
    reason_code: Mapped[str | None] = mapped_column(String(50))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
