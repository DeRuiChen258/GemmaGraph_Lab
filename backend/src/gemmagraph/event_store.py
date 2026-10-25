import json

from gemmagraph.db import now, uid


class EventStore:
    def __init__(self, db):
        self.db = db

    async def append(self, run_id, type, payload=None, node=None, attempt=0, source_key=None):
        async with self.db.transaction() as c:
            key = source_key or uid()
            old = await (await c.execute(
                "SELECT data FROM run_events WHERE run_id=? AND source_key=?", (run_id, key)
            )).fetchone()
            if old:
                return json.loads(old[0])
            row = await (await c.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?", (run_id,)
            )).fetchone()
            event = dict(schema_version=1, run_id=run_id, seq=row[0], timestamp=now(),
                         type=type, node=node, attempt=attempt, payload=payload or {})
            await c.execute("INSERT INTO run_events VALUES(?,?,?,?)",
                            (run_id, row[0], key, json.dumps(event, ensure_ascii=False)))
        return event

    async def read(self, run_id, after=0, limit=200):
        async with self.db.lock:
            rows = await (await self.db.connection.execute(
                "SELECT data FROM run_events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?",
                (run_id, after, limit),
            )).fetchall()
        return [json.loads(r[0]) for r in rows]
