from app.config import settings
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerateContext:
    true_self_type: str | None
    night_self_type: str | None
    relationship_type: str | None
    reply_length_pref: str | None
    combo_id: int
    ng_tags: list[str]
    ng_free_phrases: list[str]
    tuning: dict | None


class AiClient:
    async def generate_abc(self, history_text: str, ctx: GenerateContext) -> list[str]:
        raise NotImplementedError


class DummyAiClient(AiClient):
    async def generate_abc(self, history_text: str, ctx: GenerateContext) -> list[str]:
        # 本文保存なし。テンプレ過依存を避けるために軽く揺らす程度。
        base = "了解だよ。"
        rel = f"（関係:{ctx.relationship_type or 'unknown'}）"
        length = ctx.reply_length_pref or "standard"
        combo = ctx.combo_id
        a = f"{base}{rel} 今日はどうする？無理ない範囲で、会えそうならサクッと予定合わせよ☺️"
        b = f"{base} 返信ありがと。{rel} 今週どこかタイミング合う日ある？"
        c = f"{base} {rel} もし今日いけるなら、軽く顔出してくれたら嬉しい。空いてる時間ある？"

        if length == "long":
            a += "\n\nこっちは落ち着いてるから、来れそうならで全然OK。来れないならまた別日で調整しよ。"
            b += "\n\n無理せずで大丈夫！都合いい日だけ教えて。"
            c += "\n\n今日が難しければ、候補日2つくらい投げてくれたら一番早いかも。"

        return [a, b, c]

_ai_singleton: AiClient | None = None


def get_ai_client() -> AiClient:
    global _ai_singleton
    if _ai_singleton is not None:
        return _ai_singleton

    if settings.ai_provider == "openai":
        from app.ai_client_openai import OpenAiResponsesClient
        _ai_singleton = OpenAiResponsesClient()
        return _ai_singleton

    _ai_singleton = DummyAiClient()
    return _ai_singleton
