from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def jst_today_ymd(now_utc: dt.datetime | None = None) -> str:
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    return now.astimezone(JST).strftime("%Y-%m-%d")
