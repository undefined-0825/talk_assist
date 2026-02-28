from __future__ import annotations

from app.redis_client import redis_client
from app.config import settings


async def acquire(user_id: str, idem_key: str) -> bool:
    key = f"idem:gen:{user_id}:{idem_key}"
    ok = await redis_client.set(key, "1", nx=True, ex=settings.idempotency_ttl_seconds)
    return bool(ok)


async def release(user_id: str, idem_key: str) -> None:
    key = f"idem:gen:{user_id}:{idem_key}"
    await redis_client.delete(key)
