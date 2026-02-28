from __future__ import annotations

import hashlib
import json
import secrets


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def etag_for_json(obj: dict) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256_hex(raw)


def new_ticket_id() -> str:
    return secrets.token_urlsafe(16)


def new_migration_code_12digits() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(12))
