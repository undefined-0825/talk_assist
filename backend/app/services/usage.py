from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import UsageDaily
from app.utils_time import jst_today_ymd


async def get_or_create_usage(db: AsyncSession, user_id: str, plan: str) -> UsageDaily:
    d = jst_today_ymd()
    row = await db.execute(select(UsageDaily).where(UsageDaily.user_id == user_id, UsageDaily.date == d))
    u = row.scalar_one_or_none()
    if u:
        return u
    u = UsageDaily(user_id=user_id, date=d, generate_count=0, plan_at_time=plan)
    db.add(u)
    await db.flush()
    return u
