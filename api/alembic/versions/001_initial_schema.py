"""Initial ME2 schema — all tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-04-14

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Tenants ---
    op.create_table(
        "me2_tenants",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(3), server_default="BRA"),
        sa.Column("timezone", sa.String(50), server_default="America/Sao_Paulo"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Users ---
    op.create_table(
        "me2_users",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.Enum("meitech_admin", "meitech_support", "client_admin", "client_operator", name="userrole"), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["me2_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # --- Plants ---
    op.create_table(
        "me2_plants",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("location", sa.String(300)),
        sa.Column("timezone", sa.String(50), server_default="America/Sao_Paulo"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["me2_tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Equipment ---
    op.create_table(
        "me2_equipment",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plant_id", postgresql.UUID(), nullable=False),
        sa.Column("serial_number", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("model", sa.String(100)),
        sa.Column("manufacturer", sa.String(100)),
        sa.Column("standard_cycle_time_s", sa.Float()),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["plant_id"], ["me2_plants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial_number"),
    )

    # --- Shifts ---
    op.create_table(
        "me2_shifts",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plant_id", postgresql.UUID(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("days", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["plant_id"], ["me2_plants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Targets ---
    op.create_table(
        "me2_targets",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(), nullable=False),
        sa.Column("shift_id", postgresql.UUID(), nullable=False),
        sa.Column("target_parts_hour", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["equipment_id"], ["me2_equipment.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["me2_shifts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Production Events (time-series) ---
    op.create_table(
        "production_events",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(), nullable=False),
        sa.Column("serial_number", sa.String(30), nullable=False),
        sa.Column("product_no", sa.String(30)),
        sa.Column("parts_ok", sa.Integer(), nullable=False),
        sa.Column("cycle_time_s", sa.Float()),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["me2_equipment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_production_equipment_ts", "production_events", ["equipment_id", "ts"])

    # --- Status Events (time-series) ---
    op.create_table(
        "status_events",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(), nullable=False),
        sa.Column("serial_number", sa.String(30), nullable=False),
        sa.Column("word_status", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["me2_equipment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_status_equipment_ts", "status_events", ["equipment_id", "ts"])

    # --- Process Events (time-series) ---
    op.create_table(
        "process_events",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(), nullable=False),
        sa.Column("variable_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["me2_equipment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_process_equipment_ts", "process_events", ["equipment_id", "ts"])

    # --- Connection Log ---
    op.create_table(
        "connection_log",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["me2_equipment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_connlog_equipment_ts", "connection_log", ["equipment_id", "ts"])

    # --- OEE Snapshots ---
    op.create_table(
        "oee_snapshots",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(), nullable=False),
        sa.Column("shift_id", postgresql.UUID()),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hour", sa.Integer()),
        sa.Column("availability_pct", sa.Float(), server_default="0"),
        sa.Column("performance_pct", sa.Float(), server_default="0"),
        sa.Column("quality_pct", sa.Float(), server_default="1"),
        sa.Column("oee_pct", sa.Float(), server_default="0"),
        sa.Column("parts_good", sa.Integer(), server_default="0"),
        sa.Column("downtime_min", sa.Float(), server_default="0"),
        sa.Column("planned_min", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["equipment_id"], ["me2_equipment.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["me2_shifts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oee_equipment_date", "oee_snapshots", ["equipment_id", "date"])
    op.create_index("uq_oee_equipment_date_hour", "oee_snapshots", ["equipment_id", "date", "hour"], unique=True)

    # --- Alerts ---
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["equipment_id"], ["me2_equipment.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Quality ---
    op.create_table(
        "me2_quality",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(), nullable=False),
        sa.Column("operator_id", postgresql.UUID()),
        sa.Column("quantity_scrap", sa.Integer(), server_default="0"),
        sa.Column("quantity_rework", sa.Integer(), server_default="0"),
        sa.Column("reason_code", sa.String(50)),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["equipment_id"], ["me2_equipment.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["me2_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("me2_quality")
    op.drop_table("alerts")
    op.drop_index("uq_oee_equipment_date_hour", table_name="oee_snapshots")
    op.drop_index("ix_oee_equipment_date", table_name="oee_snapshots")
    op.drop_table("oee_snapshots")
    op.drop_index("ix_connlog_equipment_ts", table_name="connection_log")
    op.drop_table("connection_log")
    op.drop_index("ix_process_equipment_ts", table_name="process_events")
    op.drop_table("process_events")
    op.drop_index("ix_status_equipment_ts", table_name="status_events")
    op.drop_table("status_events")
    op.drop_index("ix_production_equipment_ts", table_name="production_events")
    op.drop_table("production_events")
    op.drop_table("me2_targets")
    op.drop_table("me2_shifts")
    op.drop_table("me2_equipment")
    op.drop_table("me2_plants")
    op.drop_table("me2_users")
    op.drop_table("me2_tenants")
    op.execute("DROP TYPE IF EXISTS userrole")
