from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.redis_client import redis_client
from app.config import settings
from app.db import get_db
from app.models import User, PlanStatus
from app.errors import err


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    plan: str


def _bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


async def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    key = f"sess:{token}"
    await redis_client.set(key, user_id, ex=settings.session_ttl_seconds)

    # user->tokens index (migration invalidate)
    await redis_client.sadd(f"sess_u:{user_id}", token)
    await redis_client.expire(f"sess_u:{user_id}", settings.session_ttl_seconds)
    return token


async def invalidate_all_sessions(user_id: str) -> int:
    key = f"sess_u:{user_id}"
    tokens = await redis_client.smembers(key)
    if not tokens:
        return 0
    pipe = redis_client.pipeline()
    for t in tokens:
        pipe.delete(f"sess:{t}")
    pipe.delete(key)
    res = await pipe.execute()
    # delete returns 0/1
    return sum(int(x) for x in res if isinstance(x, int))


async def get_auth_context(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> AuthContext:
    token = _bearer_token(authorization)
    if not token:
        raise err("AUTH_REQUIRED", "認証が必要です", status_code=401)

    user_id = await redis_client.get(f"sess:{token}")
    if not user_id:
        raise err("AUTH_INVALID", "認証が無効です", status_code=401)

    row = await db.execute(select(User).where(User.user_id == user_id))
    user = row.scalar_one_or_none()
    if not user:
        raise err("AUTH_INVALID", "認証が無効です", status_code=401)

    pr = await db.execute(select(PlanStatus).where(PlanStatus.user_id == user_id))
    ps = pr.scalar_one_or_none()
    plan = ps.plan if ps else "free"

    return AuthContext(user_id=user_id, plan=plan)
