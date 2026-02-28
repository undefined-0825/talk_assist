from __future__ import annotations

from fastapi import HTTPException
from app.redis_client import redis_client


async def fixed_window_limit(key: str, limit: int, window_seconds: int) -> None:
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count, ttl = await pipe.execute()

    if ttl == -1:
        await redis_client.expire(key, window_seconds)

    if int(count) > int(limit):
        raise HTTPException(status_code=429, detail={"error": {"code": "RATE_LIMITED", "message": "回数制限です", "detail": {}}})
