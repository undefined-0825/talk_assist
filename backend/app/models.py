from __future__ import annotations

import datetime as dt
import uuid
from sqlalchemy import String, DateTime, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))


class PlanStatus(Base):
    __tablename__ = "plan_status"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan: Mapped[str] = mapped_column(String(16), default="free")  # free/pro
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    settings_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    etag: Mapped[str] = mapped_column(String(128))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))


class UsageDaily(Base):
    __tablename__ = "usage_daily"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    date: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD (JST)
    generate_count: Mapped[int] = mapped_column(Integer, default=0)
    plan_at_time: Mapped[str] = mapped_column(String(16), default="free")
