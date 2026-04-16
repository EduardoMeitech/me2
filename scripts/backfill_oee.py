"""Backfill OEE snapshots for past dates.

Usage:
    PYTHONPATH=. python scripts/backfill_oee.py [--days N]

Calculates hourly OEE for all active equipment for the last N days (default 5).
"""

import asyncio
import logging
import os
import platform
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://me2:me2dev@localhost:5432/me2")


async def backfill(days: int = 5):
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from api.core.models import Equipment
    from api.services.oee_calculator import OEECalculator

    calc = OEECalculator()
    today = datetime.now(timezone.utc).date()

    async with session_factory() as db:
        result = await db.execute(
            select(Equipment.id, Equipment.name).where(Equipment.active.is_(True))
        )
        equipment = result.all()
        logger.info("Found %d active equipment", len(equipment))

        for day_offset in range(days, -1, -1):
            target_date = today - timedelta(days=day_offset)
            logger.info("=== Backfilling %s ===", target_date)

            for eq_id, eq_name in equipment:
                for hour in range(24):
                    try:
                        await calc.calculate_hourly(db, eq_id, target_date, hour)
                    except Exception:
                        logger.exception(
                            "Failed: %s hour=%02d eq=%s", target_date, hour, eq_name
                        )

            logger.info("Done %s for %d equipment", target_date, len(equipment))

    await engine.dispose()
    logger.info("Backfill complete!")


if __name__ == "__main__":
    days = 5
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    asyncio.run(backfill(days))
