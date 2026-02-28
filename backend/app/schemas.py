from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    error: dict


class AuthAnonymousResponse(BaseModel):
    user_id: str
    access_token: str


class SettingsResponse(BaseModel):
    settings: dict


class SettingsUpdateRequest(BaseModel):
    settings: dict = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    history_text: str = Field(..., description="トーク履歴の原文（本文保存なし）")
    combo_id: int = Field(..., ge=0, le=5)
    tuning: dict | None = None  # Proのみ（クライアントが付与）


class Candidate(BaseModel):
    label: str
    text: str


class DailyInfo(BaseModel):
    date: str
    limit: int
    used: int
    remaining: int


class GenerateResponse(BaseModel):
    request_id: str
    plan: str
    daily: DailyInfo
    candidates: list[Candidate]
    model_hint: str | None = None
    timestamp: str | None = None
    meta_pro: dict | None = None


class MigrationStartResponse(BaseModel):
    migration_code: str
    ticket_id: str


class MigrationCompleteRequest(BaseModel):
    migration_code: str


class MigrationCompleteResponse(BaseModel):
    user_id: str
    access_token: str
