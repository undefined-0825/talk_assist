from __future__ import annotations

import re

# 「中ゲート」前提。サーバは軽量に「明確NG」を止める（MUST）
PATTERNS = [
    (re.compile(r"(住所|電話番号|マイナンバー|クレカ|クレジットカード|口座番号)"), "個人情報の不正取得/晒し"),
    (re.compile(r"(殺す|脅す|脅迫|爆破|放火)"), "脅迫/危害"),
    (re.compile(r"(未成年|中学生|小学生).*(性|エロ|H|セックス)"), "未成年性的内容"),
]


def check(text: str) -> str | None:
    for rx, why in PATTERNS:
        if rx.search(text):
            return why
    return None
