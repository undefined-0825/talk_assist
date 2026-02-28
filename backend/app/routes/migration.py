from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.security import get_auth_context, AuthContext, create_session, invalidate_all_sessions
from app.schemas import MigrationStartResponse, MigrationCompleteRequest, MigrationCompleteResponse
from app.config import settings
from app.ratelimit import fixed_window_limit
from app.redis_client import redis_client
from app.utils import new_ticket_id, new_migration_code_12digits, sha256_hex
from app.errors import err

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/migration/start", response_model=MigrationStartResponse)
async def migration_start(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    ip = _client_ip(request)
    await fixed_window_limit(f"rl:mig_start:user:{auth.user_id}:1d", settings.rl_mig_start_user_limit, settings.rl_mig_start_user_window_seconds)
    await fixed_window_limit(f"rl:mig_start:ip:{ip}:1d", settings.rl_mig_start_ip_limit, settings.rl_mig_start_ip_window_seconds)

    ticket_id = new_ticket_id()
    code = new_migration_code_12digits()
    code_hash = sha256_hex(code)

    # 平文コードは保存しない：hashのみ
    # value: from_user_id|ticket_id|used(0/1)
    await redis_client.set(
        f"mig:codehash:{code_hash}",
        f"{auth.user_id}|{ticket_id}|0",
        ex=settings.migration_code_ttl_seconds,
    )
    await redis_client.set(
        f"mig:ticket:{ticket_id}",
        f"{auth.user_id}|started",
        ex=settings.migration_ticket_ttl_seconds,
    )

    return MigrationStartResponse(migration_code=code, ticket_id=ticket_id)


@router.post("/migration/complete", response_model=MigrationCompleteResponse)
async def migration_complete(
    req: MigrationCompleteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = _client_ip(request)
    # serverside spec v2 fixed: IP 5/min
    await fixed_window_limit(
        f"rl:mig_complete:ip:{ip}:1m",
        settings.rl_mig_complete_ip_limit,
        settings.rl_mig_complete_ip_window_seconds,
    )

    code_hash = sha256_hex(req.migration_code)

    # lock判定（10回失敗で無効化）
    if await redis_client.exists(f"mig:lock:{code_hash}"):
        raise err("MIGRATION_CODE_INVALID", "移行コードが無効です", status_code=400)

    v = await redis_client.get(f"mig:codehash:{code_hash}")
    if not v:
        tries_key = f"mig:tries:{code_hash}"
        tries = await redis_client.incr(tries_key)
        await redis_client.expire(tries_key, settings.migration_code_ttl_seconds)
        if int(tries) >= int(settings.mig_complete_max_tries):
            await redis_client.set(f"mig:lock:{code_hash}", "1", ex=settings.migration_lock_ttl_seconds)
        raise err("MIGRATION_CODE_INVALID", "移行コードが無効です", status_code=400)

    from_user_id, ticket_id, used = v.split("|", 2)
    if used == "1":
        raise err("MIGRATION_CODE_USED", "移行コードは使用済みです", status_code=400)

    # 1回限り：使用済み化 + code削除
    pipe = redis_client.pipeline()
    pipe.set(f"mig:codehash:{code_hash}", f"{from_user_id}|{ticket_id}|1", ex=settings.migration_code_ttl_seconds)
    pipe.delete(f"mig:tries:{code_hash}")
    await pipe.execute()

    # 旧セッション失効 + 新セッション発行（同一user_id引き継ぎ）
    await invalidate_all_sessions(from_user_id)
    new_token = await create_session(from_user_id)

    # チケットも使用済みに寄せる（存在すれば）
    await redis_client.set(f"mig:ticket:{ticket_id}", f"{from_user_id}|completed", ex=settings.migration_ticket_ttl_seconds)

    return MigrationCompleteResponse(user_id=from_user_id, access_token=new_token)
