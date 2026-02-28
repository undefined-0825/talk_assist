from __future__ import annotations

from fastapi import HTTPException


def err(code: str, message: str, detail: dict | None = None, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "detail": detail or {}}})
