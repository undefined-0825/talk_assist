from __future__ import annotations

import datetime as dt
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.schemas import GenerateRequest, GenerateResponse, Candidate, DailyInfo
from app.security import get_auth_context, AuthContext
from app.config import settings
from app.ratelimit import fixed_window_limit
from app.errors import err
from app.safety_gate import check as safety_check
from app.ai_client import get_ai_client, GenerateContext
from app.models import UserSettings
from app.services.usage import get_or_create_usage
from app.services.idempotency import acquire
from app.utils_time import jst_today_ymd

router = APIRouter()


def _daily_limit(plan: str) -> int:
    return settings.pro_generate_daily_limit if plan == "pro" else settings.free_generate_daily_limit


def _to_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def _blocked_candidates(reason: str) -> list[str]:
    a = (
        "ごめんね、その内容はこのアプリでは手伝えないよ。"
        "でも、伝え方や別の言い回しなら一緒に考えられるから、"
        "目的だけ教えてくれたら安全な形で作るね。"
    )
    b = "ごめん、その内容は対応できない…！目的だけ教えてくれたら、言い方を変えて一緒に考えるよ。"
    c = "無理のない範囲で大丈夫。今いちばん困ってるポイントだけ、短く教えて？そこから整えるね。"
    return [a, b, c]


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    req: GenerateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    rid = getattr(request.state, "request_id", None) or ""

    if len(req.history_text) > settings.generate_max_chars:
        raise err("VALIDATION_FAILED", "入力が長すぎます", {"max_chars": settings.generate_max_chars}, status_code=422)

    if auth.plan != "pro" and req.combo_id not in (0, 1):
        raise err("PLAN_REQUIRED", "有料版のみ対応しています", {"combo_id": req.combo_id}, status_code=403)

    await fixed_window_limit(
        f"rl:generate:user:{auth.user_id}:1m",
        settings.rl_generate_minute_limit,
        settings.rl_generate_minute_window_seconds,
    )

    if idempotency_key:
        ok = await acquire(auth.user_id, idempotency_key)
        if not ok:
            raise err("RATE_LIMITED", "同じリクエストが処理中です", {"idempotency": "replay"}, status_code=429)

    usage = await get_or_create_usage(db, auth.user_id, auth.plan)
    limit = _daily_limit(auth.plan)
    used = int(usage.generate_count)
    if used >= limit:
        raise err("DAILY_LIMIT_REACHED", "本日の上限に達しました", {"limit": limit, "used": used}, status_code=429)

    why = safety_check(req.history_text)
    if why:
        texts = _blocked_candidates(why)
        daily = DailyInfo(date=jst_today_ymd(), limit=limit, used=used, remaining=max(0, limit - used))
        candidates = [
            Candidate(label="A", text=texts[0]),
            Candidate(label="B", text=texts[1]),
            Candidate(label="C", text=texts[2]),
        ]
        return GenerateResponse(
            request_id=rid,
            plan=auth.plan,
            daily=daily,
            candidates=candidates,
            model_hint="blocked",
            timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
            meta_pro=None,
        )

    row = await db.execute(select(UserSettings).where(UserSettings.user_id == auth.user_id))
    st = row.scalar_one_or_none()
    s = st.settings_json if (st and isinstance(st.settings_json, dict)) else {}

    ctx = GenerateContext(
        true_self_type=s.get("true_self_type"),
        night_self_type=s.get("night_self_type"),
        relationship_type=s.get("relationship_type"),
        reply_length_pref=s.get("reply_length_pref"),
        combo_id=req.combo_id,
        ng_tags=_to_list(s.get("ng_tags")),
        ng_free_phrases=_to_list(s.get("ng_free_phrases")),
        tuning=req.tuning if auth.plan == "pro" else None,
    )

    texts = await get_ai_client().generate_abc(req.history_text, ctx)
    if not isinstance(texts, list) or len(texts) != 3:
        raise err("INTERNAL_ERROR", "生成に失敗しました", status_code=500)

    usage.generate_count = int(usage.generate_count) + 1
    usage.plan_at_time = auth.plan
    await db.commit()

    used2 = int(usage.generate_count)
    daily = DailyInfo(date=jst_today_ymd(), limit=limit, used=used2, remaining=max(0, limit - used2))

    candidates = [
        Candidate(label="A", text=texts[0]),
        Candidate(label="B", text=texts[1]),
        Candidate(label="C", text=texts[2]),
    ]

    meta_pro = None
    if auth.plan == "pro":
        meta_pro = {
            "like": {"value": 55, "note": "推定"},
            "risk": {"value": 20, "note": "推定"},
        }

    return GenerateResponse(
        request_id=rid,
        plan=auth.plan,
        daily=daily,
        candidates=candidates,
        model_hint=settings.ai_provider,
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        meta_pro=meta_pro,
    )
