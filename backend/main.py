from typing import List, Literal, Tuple
import os
import json
from datetime import datetime
from pathlib import Path
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

# ========== 
# FastAPI アプリ 
# ==========
app = FastAPI(
    title="Talk Assist API",
    description="LINEトーク要約＆返信生成API",
    version="0.1.0",
)

# CORS（Flutter Web や他クライアントも想定して緩めに許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番で必要ならドメインを絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 
# OpenAI クライアント 
# ==========
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    # 起動時に気づけるように明示的に落とす
    raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")

client = OpenAI(api_key=api_key)

MODEL_NAME = "gpt-4.1-mini"

# ========== 
# 長文対策用のしきい値 
# ==========
# 生テキストのハード上限（これを超えたらまず頭+尻だけにトリム）
MAX_RAW_CHARS = 8000
# モデルに渡す文字数の目安
MAX_USED_CHARS = 4000

# ========== 
# ログ設定（簡易） 
# ==========
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "talk_assist.log"


def write_log(record: dict) -> None:
    """エラーになっても処理を止めない、超簡易ログ"""
    try:
        record = {**record}
        record["ts"] = datetime.utcnow().isoformat()
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # ログ失敗は黙殺
        pass


# ========== 
# モデル I/O 用型 
# ==========
ToneLiteral = Literal["standard", "night", "business"]


class TalkRequest(BaseModel):
    text: str
    tone: str = "standard"  # 'standard' | 'night' | 'business'


class TalkResponse(BaseModel):
    summary: str
    replies: List[str]


# ========== 
# プロンプト関連 
# ==========

def build_tone_desc_and_temp(tone: ToneLiteral) -> Tuple[str, float]:
    """トーン別のプロンプト説明と temperature を返す"""
    if tone == "night":
        tone_desc = (
            "トーン: night（夜職向けの営業LINE）\n"
            "\n"
            "# 想定シーン\n"
            "- キャバクラ / ラウンジ / ガールズバー / ホスト等の営業LINEを想定してください。\n"
            "- 既に一度会ったお客様へのお礼、次回の来店・同伴・指名の提案、雑談で関係性を深めるLINEが中心です。\n"
            "\n"
            "# ゴール\n"
            "- 【最優先】お客様に『この子（この人）とLINEしてると楽しい』『また会いたい』と思ってもらうこと。\n"
            "- そのうえで、無理のない範囲で「次に会う約束」や「お店に来るきっかけ」を作ること。\n"
            "\n"
            "# トーン・文体\n"
            "- 基本はタメ口〜ゆるい敬語でOKです（例: 「〜やで」「〜だよ」「〜です笑」など）。\n"
            "- 相手のトーク履歴に合わせて、丁寧め / 砕けた口調 / 関西弁 などを自然に寄せてください。\n"
            "- 絵文字・顔文字は 1〜3 個までに抑え、連投しないでください（例: 「🥺🥺🥺🥺」のような多用は避ける）。\n"
            "- 1通の長さは、LINEの画面1〜3スクロール以内に収まるよう、読みやすい区切りで改行してください。\n"
            "\n"
            "# 営業としての振る舞い\n"
            "- 基本は『相手を褒める』『楽しかった・嬉しかった』などのポジティブな感情を素直に伝えます。\n"
            "- 来店や同伴の提案は、「押しつけ」ではなく「提案・お誘い」の形で柔らかく書いてください。\n"
            "- 相手が『今日は行けない』『お金がきつい』など断り気味のときは、無理に誘わず\n"
            "  ・理解を示す\n"
            "  ・軽い冗談や日常話で雰囲気を和らげる\n"
            "  ・『またタイミング合うときでいいよ』とフォローする\n"
            "  を優先してください。\n"
            "- お店のルールを破るような表現（無断アフター、出勤日以外の無理な約束など）は提案しないでください。\n"
            "- 金額やプレゼントを強要するような表現は使わないでください。\n"
            "\n"
            "# お客様の温度感の読み取り\n"
            "- トーク履歴から、お客様の温度をざっくり判定してください。\n"
            "  ・ノリが良く、前向きな返事が多い → 温度「高め」\n"
            "  ・返事はあるが、スタンプや短文が多い → 温度「普通」\n"
            "  ・断りがち / 返信が遅い / 既読のみが多い → 温度「低め」\n"
            "- 温度「高め」の場合: 次回の具体的な予定（候補日やイベント）を軽く提案してOKです。\n"
            "- 温度「普通」の場合: 無理に日程を押しつけず、『また会えたら嬉しいな』レベルのふんわり提案に留めてください。\n"
            "- 温度「低め」の場合: 来店の提案は控えめにして、雑談・感謝・相手の負担にならない話題を優先してください。\n"
            "\n"
            "# 返信案3パターンの役割\n"
            "- 返信案1: 一番安心感のある営業LINE\n"
            "  ・丁寧めで、相手にプレッシャーをかけない\n"
            "  ・お礼や気遣いをしっかり伝える\n"
            "- 返信案2: 少し甘めで距離を縮めるLINE\n"
            "  ・軽い冗談やあだ名、少しだけ甘い表現を入れてOK\n"
            "  ・ただし、相手を不快にさせるような過度な下ネタや重さは避ける\n"
            "- 返信案3: 次に会う約束につながるLINE\n"
            "  ・『また◯◯行きたい』『今度◯曜日空いてたりする？』など、具体的な一歩を提案\n"
            "  ・ただし、相手が断り気味のときは、「いつかタイミング合ったら」で軽く濁す形にしてください。\n"
        )
        temperature = 0.8
    elif tone == "business":
        tone_desc = (
            "トーン: business（ビジネスチャット）\n"
            "- 上司・同僚・顧客・取引先とのビジネスチャットを想定してください。\n"
            "- 丁寧で簡潔、事実ベースで、結論ファーストを心がけてください。\n"
            "- 不必要な絵文字や顔文字は使わないでください。\n"
            "- 返信案のバリエーション:\n"
            "  1: 一番フォーマルで無難な案\n"
            "  2: 少し柔らかいトーンの案\n"
            "  3: 相手に依頼・相談・交渉を含む少し踏み込んだ案\n"
        )
        temperature = 0.6
    else:
        # standard
        tone_desc = (
            "トーン: standard（一般的な友人・知人）\n"
            "- 友人・知人とのやりとりを想定した自然な日本語にしてください。\n"
            "- 丁寧すぎず、くだけすぎないバランスをとってください。\n"
            "- 絵文字・顔文字は0〜1個までに抑えてください。\n"
            "- 返信案のバリエーション:\n"
            "  1: 一番無難で丁寧な案\n"
            "  2: 少しくだけたフレンドリーな案\n"
            "  3: ごく短い一言〜二言で返す超短文案\n"
        )
        temperature = 0.7

    return tone_desc, temperature


def build_system_prompt(tone: ToneLiteral) -> str:
    tone_desc, _ = build_tone_desc_and_temp(tone)

    return f"""あなたはLINEなどのチャットの返信を考えるアシスタントです。

# 役割
- ユーザーが受信したトーク履歴を読んで、会話の要約を行う
- ユーザーが送るべき返信候補を3パターン提案する
- 自動送信ではなく、あくまで「ユーザーが最終判断して送る」前提で提案だけを行う

# 共通ルール
- 相手との関係性やトーンをできるだけ読み取る
- 必要以上に盛らず、自然な日本語にする
- 喧嘩をあおったり、相手を攻撃するような表現は避ける
- 個人情報を勝手に推測しない

# トーン条件
{tone_desc}

# # 出力フォーマット（厳守）
1行目: 会話の要約（50〜120文字程度の日本語）
2行目以降: 返信案を3つ。各行は「- 」から始める。

注意:
- 「要約：」「返信案：」などの見出しやラベルは絶対に付けないでください。
- 要約と返信案の間に空行を1行入れても構いませんが、それ以外の余計な行は入れないでください。"""


def build_user_prompt(text: str, mode: str) -> str:
    """ユーザープロンプトを組み立て"""
    return f"""以下はLINEのトーク履歴です。内容を理解したうえで、

- 会話内容の要約
- 返信候補を3パターン（トーンの説明にしたがってニュアンスを変える）

を、指定の出力フォーマットどおりに作成してください。

入力モード: {mode}
  - full: 全文
  - trimmed: 一部トリミング（頭と末尾のみ）
  - summarized: 非常に長いためモデル内で要約済み

--- トーク履歴 ---
{text}
"""


# ========== 
# 長文前処理 
# ==========

def summarize_conversation(raw_text: str, tone: ToneLiteral) -> str:
    """
    非常に長い場合に使う要約フェーズ。
    tone は今はほぼ使わないが、将来拡張用に受け取っておく。
    """
    system_prompt = (
        "あなたは会話ログを要約するアシスタントです。\n"
        "入力されるのはLINEなどのチャット履歴です。\n\n"
        "# 目的\n"
        "- 会話の流れと重要なポイントが分かるように、重要な発言のみを時系列で簡潔にまとめてください。\n"
        "- 感情のニュアンス（怒っている・喜んでいる・困っている等）が分かるように含めてください。\n\n"
        "# 出力\n"
        "- 箇条書きや見出しは使わず、2〜6文程度の自然な日本語にしてください。"
    )

    user_prompt = f"""以下が会話の全文です。上記の指示に従って要約してください。

--- 会話全文 ---
{raw_text}
"""

    completion = client.responses.create(
        model=MODEL_NAME,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_output_tokens=256,
        temperature=0.4,
    )

    content = completion.output[0].content[0].text.strip()
    return content


def preprocess_text(raw_text: str, tone: ToneLiteral) -> Tuple[str, str, int, int]:
    """
    長文対策の前処理。
    戻り値: (used_text, mode, original_len, used_len)
      mode: "full" | "trimmed" | "summarized"
    """
    text = raw_text.strip()
    original_len = len(text)

    # 生テキストが短ければそのまま
    if original_len <= MAX_USED_CHARS:
        return text, "full", original_len, original_len

    # まずは頭 + 尻でトリミング
    head = text[: MAX_USED_CHARS // 2]
    tail = text[-MAX_USED_CHARS // 2 :]
    trimmed = head + "\n...\n" + tail

    if original_len <= MAX_RAW_CHARS:
        used_len = len(trimmed)
        return trimmed, "trimmed", original_len, used_len

    # さらに長い場合は要約フェーズ（summarized）
    try:
        summary = summarize_conversation(text, tone)
        used_text = summary
        mode = "summarized"
    except Exception as e:
        # 要約に失敗したらトリム版で妥協
        print(f"[WARN] summarize_conversation failed: {e}")
        used_text = trimmed
        mode = "trimmed-fallback"

    used_len = len(used_text)
    return used_text, mode, original_len, used_len


# ========== 
# メインエンドポイント 
# ==========

def parse_ai_output(content: str) -> Tuple[str, List[str]]:
    """
    モデルから返ってきたテキストを「要約」「返信案」に分解する。
    - '要約：' / '要約:' 行は見出しとして扱う
    - '返信案：' / '返信案:' 行は見出しとしてスキップ
    - '- ' や '・' で始まる行を返信候補として優先
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return "（AIからの応答が空でした）", []

    summary: str | None = None
    summary_index: int = -1

    # 要約行を探す
    for idx, line in enumerate(lines):
        # "要約：" だけの行（中身なし）は見出し扱いでスキップ
        if re.fullmatch(r"要約[:：]?", line):
            continue

        # "要約: XXX" 形式なら、コロン以降を要約として取る
        m = re.match(r"要約[:：]\s*(.+)", line)
        if m:
            summary = m.group(1).strip()
            summary_index = idx
            break

        # それ以外は最初に出てきた非空行を要約とみなす
        summary = line
        summary_index = idx
        break

    if summary is None:
        summary = "（要約を抽出できませんでした）"
        summary_index = -1

    replies: List[str] = []

    # 返信候補を探す
    start_idx = summary_index + 1
    for line in lines[start_idx:]:
        # "返信案" 見出しっぽい行はスキップ
        if re.fullmatch(r"返信案[:：]?", line):
            continue

        # "- " や "・" で始まる行を優先
        if line.startswith("-"):
            replies.append(line.lstrip("-").strip())
            continue
        if line.startswith("・"):
            replies.append(line.lstrip("・").strip())
            continue

        # "1. xxx" / "１）xxx" など番号付きも拾う
        if re.match(r"^[0-9０-９]+[.)．）]\s*", line):
            line2 = re.sub(r"^[0-9０-９]+[.)．）]\s*", "", line)
            replies.append(line2.strip())
            continue

        # それ以外: 既に返信候補があれば無視、まだ無ければ拾っておく
        if not replies:
            replies.append(line)

    # 最大3件
    replies = replies[:3]

    return summary, replies


@app.get("/health")
async def health() -> dict:
    """死活監視用エンドポイント"""
    return {"status": "ok"}


@app.post("/api/talk/assist", response_model=TalkResponse)
async def talk_assist(req: TalkRequest) -> TalkResponse:
    raw_text = (req.text or "").strip()
    tone_raw = (req.tone or "standard").lower()

    if not raw_text:
        return TalkResponse(summary="（入力が空です）", replies=[])

    # tone を正規化
    if tone_raw not in ("standard", "night", "business"):
        tone: ToneLiteral = "standard"
    else:
        tone = tone_raw  # type: ignore[assignment]

    # 長文前処理
    used_text, mode, original_len, used_len = preprocess_text(raw_text, tone)

    system_prompt = build_system_prompt(tone)
    user_prompt = build_user_prompt(used_text, mode)
    _, temperature = build_tone_desc_and_temp(tone)

    try:
        completion = client.responses.create(
            model=MODEL_NAME,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_output_tokens=512,
        )

        # Responses API の結果からテキストを取り出す
        content = completion.output[0].content[0].text.strip()

        summary, replies = parse_ai_output(content)

        if not replies:
            # 返信案がうまく取れなかったケースはログに残しておく
            write_log(
                {
                    "event": "parsed_without_replies",
                    "tone": tone,
                    "original_len": original_len,
                    "used_len": used_len,
                    "mode": mode,
                    "raw_content_preview": content[:120],
                }
            )
        write_log(
            {
                "event": "success",
                "tone": tone,
                "original_len": original_len,
                "used_len": used_len,
                "mode": mode,
                "summary_preview": summary[:50],
                "replies_count": len(replies),
            }
        )

        return TalkResponse(summary=summary, replies=replies)

    except Exception as e:
        # サーバ側ログ
        print(f"[ERROR] talk_assist OpenAI error: {e}")
        write_log(
            {
                "event": "error",
                "tone": tone,
                "original_len": original_len,
                "used_len": used_len,
                "mode": mode,
                "error": str(e),
            }
        )
        # クライアントには汎用メッセージで返す
        return TalkResponse(
            summary="（AI呼び出しに失敗しました。しばらく時間をおいて再度お試しください。）",
            replies=[],
        )


# ========== 
# ローカル実行用エントリポイント 
# ==========
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)