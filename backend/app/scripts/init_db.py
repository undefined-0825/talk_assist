from __future__ import annotations

import asyncio
from app.db import engine, Base


import app.models  # モデル登録（create_all用）
async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(main())
