from __future__ import annotations

import logging


class NoBodyFilter(logging.Filter):
    """本文混入を防ぐ保険フィルタ（MUST）"""
    BLOCK_KEYS = {
        "body",
        "request_body",
        "response_body",
        "content",
        "payload",
        "migration_code",
        "text",
        "history_text",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.args, dict):
                for k in list(record.args.keys()):
                    if k in self.BLOCK_KEYS:
                        record.args[k] = "[REDACTED]"
            for k in self.BLOCK_KEYS:
                if hasattr(record, k):
                    setattr(record, k, "[REDACTED]")
        except Exception:
            pass
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addFilter(NoBodyFilter())
    logging.getLogger("uvicorn.error").addFilter(NoBodyFilter())
    logging.getLogger("uvicorn.access").addFilter(NoBodyFilter())
