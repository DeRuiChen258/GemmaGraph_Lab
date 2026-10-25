import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import aiosqlite

from gemmagraph.errors import AppError


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str = "") -> str:
    return prefix + uuid4().hex[:20]


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.connection = None
        self.lock = asyncio.Lock()

    async def open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.execute("PRAGMA busy_timeout=10000")
        await self.connection.executescript(Path(__file__).with_name("schema.sql").read_text())
        await self.connection.commit()
        return self

    async def close(self):
        if self.connection:
            await self.connection.close()

    @asynccontextmanager
    async def transaction(self):
        async with self.lock:
            await self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
                await self.connection.commit()
            except BaseException:
                await self.connection.rollback()
                raise

    async def get(self, kind, resource_id):
        async with self.lock:
            c = await self.connection.execute(
                "SELECT data FROM resources WHERE kind=? AND id=?", (kind, resource_id)
            )
            row = await c.fetchone()
        if not row:
            raise AppError("not_found", f"找不到资源 {resource_id}", 404)
        return json.loads(row[0])

    async def put(self, kind, value):
        async with self.transaction() as c:
            await c.execute(
                "INSERT INTO resources VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
                (kind, value["id"], json.dumps(value, ensure_ascii=False)),
            )
        return value

    async def update(self, kind, resource_id, **changes):
        async with self.transaction() as c:
            row = await (await c.execute(
                "SELECT data FROM resources WHERE kind=? AND id=?", (kind, resource_id)
            )).fetchone()
            if not row:
                raise AppError("not_found", "资源不存在", 404)
            value = json.loads(row[0])
            value.update(changes)
            if kind == "run":
                value["updated_at"] = now()
            await c.execute("UPDATE resources SET data=? WHERE kind=? AND id=?",
                            (json.dumps(value, ensure_ascii=False), kind, resource_id))
        return value

    async def list(self, kind):
        async with self.lock:
            rows = await (await self.connection.execute(
                "SELECT data FROM resources WHERE kind=? ORDER BY rowid DESC", (kind,)
            )).fetchall()
        return [json.loads(row[0]) for row in rows]
