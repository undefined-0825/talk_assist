from __future__ import annotations

import os
from typing import Any, Optional

try:
    import redis.asyncio as redis  # type: ignore
except Exception:
    redis = None  # type: ignore

from app.config import settings


class _MemoryRedis:
    def __init__(self):
        self._kv: dict[str, str] = {}
        self._set: dict[str, set[str]] = {}
        self._ttl: dict[str, int] = {}

    async def get(self, key: str) -> Optional[str]:
        return self._kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        if ex is not None:
            self._ttl[key] = ex
        return True

    async def delete(self, key: str) -> int:
        n = 1 if key in self._kv else 0
        self._kv.pop(key, None)
        self._ttl.pop(key, None)
        self._set.pop(key, None)
        return n

    async def incr(self, key: str) -> int:
        v = int(self._kv.get(key) or "0") + 1
        self._kv[key] = str(v)
        return v

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self._kv or key in self._set:
            self._ttl[key] = seconds
            return True
        return False

    async def ttl(self, key: str) -> int:
        return self._ttl.get(key, -1)

    async def exists(self, key: str) -> int:
        return 1 if (key in self._kv or key in self._set) else 0

    async def sadd(self, key: str, member: str) -> int:
        s = self._set.setdefault(key, set())
        before = len(s)
        s.add(member)
        return 1 if len(s) > before else 0

    async def smembers(self, key: str) -> set[str]:
        return set(self._set.get(key, set()))

    def pipeline(self):
        return _MemoryPipeline(self)


class _MemoryPipeline:
    def __init__(self, r: _MemoryRedis):
        self._r = r
        self._ops: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def incr(self, *a, **kw):
        self._ops.append(("incr", a, kw))
        return self

    def ttl(self, *a, **kw):
        self._ops.append(("ttl", a, kw))
        return self

    def expire(self, *a, **kw):
        self._ops.append(("expire", a, kw))
        return self

    def delete(self, *a, **kw):
        self._ops.append(("delete", a, kw))
        return self

    def set(self, *a, **kw):
        self._ops.append(("set", a, kw))
        return self

    async def execute(self):
        out = []
        for name, a, kw in self._ops:
            out.append(await getattr(self._r, name)(*a, **kw))
        self._ops.clear()
        return out


def _create_client():
    if os.getenv("REDIS_DISABLED", "").lower() in ("1", "true", "yes"):
        return _MemoryRedis()
    if redis is None:
        return _MemoryRedis()
    try:
        return redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return _MemoryRedis()


redis_client = _create_client()
