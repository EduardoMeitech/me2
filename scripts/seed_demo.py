"""
ME2 seed_demo.py — Generate synthetic data for demo/testing.

Usage:
    python scripts/seed_demo.py

Creates a tenant, plant, user, equipment, shifts, and sample events
in the PostgreSQL database.
"""

import asyncio
import logging
import os
import platform
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Fix asyncpg on Windows — use SelectorEventLoop instead of ProactorEventLoop
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://me2:me2dev@localhost:5432/me2")


async def seed():
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # --- Tenant ---
        result = await db.execute(
            text("""
                INSERT INTO me2_tenants (name, country, timezone)
                VALUES ('Meitech Industrial', 'BRA', 'America/Sao_Paulo')
                ON CONFLICT DO NOTHING
                RETURNING id
            """)
        )
        row = result.fetchone()
        if row:
            tenant_id = row[0]
            logger.info(f"Tenant criado: {tenant_id}")
        else:
            result = await db.execute(text("SELECT id FROM me2_tenants LIMIT 1"))
            tenant_id = result.scalar()
            logger.info(f"Tenant existente: {tenant_id}")

        # --- Plant ---
        result = await db.execute(
            text("""
                INSERT INTO me2_plants (tenant_id, name, location, timezone)
                VALUES (:tid, 'Planta Meitech Videira', 'Videira - SC', 'America/Sao_Paulo')
                ON CONFLICT DO NOTHING
                RETURNING id
            """),
            {"tid": tenant_id},
        )
        row = result.fetchone()
        plant_id = row[0] if row else (await db.execute(text("SELECT id FROM me2_plants LIMIT 1"))).scalar()
        logger.info(f"Plant: {plant_id}")

        # --- Admin User (password: me2admin) ---
        # Pre-generated bcrypt hash for "me2admin" (rounds=12)
        # To regenerate: python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('me2admin'))"
        password_hash = "$2b$12$K4r9CQkBqUyY8k5xOq5qXexbCntV7jT2Q5GqNpGqZMfH0VHjGnKLi"
        await db.execute(
            text("""
                INSERT INTO me2_users (tenant_id, name, email, role, password_hash)
                VALUES (:tid, 'Eduardo Rosa', 'eduardo.rosa@meitech.com.br', 'meitech_admin', :pwd)
                ON CONFLICT (email) DO NOTHING
            """),
            {"tid": tenant_id, "pwd": password_hash},
        )

        # --- Equipment ---
        result = await db.execute(
            text("""
                INSERT INTO me2_equipment (plant_id, serial_number, name, model, manufacturer, standard_cycle_time_s)
                VALUES (:pid, 'MEI-2024-0042', 'Depenadora 01', 'M241', 'Schneider Electric', 6.0)
                ON CONFLICT (serial_number) DO NOTHING
                RETURNING id
            """),
            {"pid": plant_id},
        )
        row = result.fetchone()
        equip_id = row[0] if row else (await db.execute(text("SELECT id FROM me2_equipment LIMIT 1"))).scalar()
        logger.info(f"Equipment: {equip_id}")

        # --- Shifts ---
        from datetime import time as dt_time
        shifts = [
            ("T100", dt_time(5, 0), dt_time(13, 29)),
            ("T200", dt_time(13, 30), dt_time(21, 59)),
            ("T300", dt_time(22, 0), dt_time(4, 59)),
        ]
        for name, start, end in shifts:
            await db.execute(
                text("""
                    INSERT INTO me2_shifts (plant_id, name, start_time, end_time)
                    VALUES (:pid, :name, :start, :end)
                    ON CONFLICT DO NOTHING
                """),
                {"pid": plant_id, "name": name, "start": start, "end": end},
            )

        # --- Sample production events (last 24h) ---
        now = datetime.now(timezone.utc)
        parts = 0
        for hours_ago in range(24, 0, -1):
            ts = now - timedelta(hours=hours_ago)
            parts += random.randint(30, 80)
            cycle_time = random.uniform(4.5, 7.5)

            await db.execute(
                text("""
                    INSERT INTO production_events (equipment_id, serial_number, product_no, parts_ok, cycle_time_s, ts)
                    VALUES (:eid, 'MEI-2024-0042', '9999', :parts, :ct, :ts)
                """),
                {"eid": equip_id, "parts": parts, "ct": round(cycle_time, 2), "ts": ts},
            )

        # --- Sample status events ---
        statuses = [18, 18, 18, 32, 18, 64, 18, 20, 18]
        for i, ws in enumerate(statuses):
            ts = now - timedelta(hours=len(statuses) - i, minutes=random.randint(0, 30))
            await db.execute(
                text("""
                    INSERT INTO status_events (equipment_id, serial_number, word_status, ts)
                    VALUES (:eid, 'MEI-2024-0042', :ws, :ts)
                """),
                {"eid": equip_id, "ws": ws, "ts": ts},
            )

        await db.commit()
        logger.info("Seed completo!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
