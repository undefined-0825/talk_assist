from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


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
        # 起動確認用のダミー。内容は最小限でOK（受け入れ条件の本番生成は後続でAIクライアントに委譲）
        rel = ctx.relationship_type or "unknown"
        base = "了解！メッセージありがとう。"
        a = f"{base}（A）関係: {rel}。今夜どうする？"
        b = f"{base}（B）関係: {rel}。落ち着いたら電話できる？"
        c = f"{base}（C）関係: {rel}。会える日また教えてね。"

        if (ctx.reply_length_pref or "standard") == "long":
            a += "\n\n今日はバタバタしてたけど、ちゃんと読んでるよ。無理ないタイミングで返してね。"
            b += "\n\nちょっとだけ声聞けたら安心する。タイミング合う時で大丈夫。"
            c += "\n\n予定が見えたら合わせるよ。無理なら無理って言ってね。"

        return [a, b, c]


def get_ai_client() -> AiClient:
    # settings 側のスイッチに合わせて選択（既存設計に合わせて最低限）
    provider = getattr(settings, "ai_provider", None) or getattr(settings, "AI_PROVIDER", None)
    if provider and str(provider).lower() == "openai":
        # 循環import回避のためローカルimport
        from app.ai_client_openai import OpenAiClient
        return OpenAiClient()
    return DummyAiClient()
