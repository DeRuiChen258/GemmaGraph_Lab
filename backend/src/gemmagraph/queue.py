import json
import time

from gemmagraph.db import uid


async def enqueue(c, kind, resource_id, payload=None):
    job_id = uid("job_")
    await c.execute(
        "INSERT OR IGNORE INTO jobs(id,kind,resource_id,payload,created_at) VALUES(?,?,?,?,?)",
        (job_id, kind, resource_id, json.dumps(payload or {}), time.time()),
    )
    return job_id


class Queue:
    def __init__(self, db):
        self.db = db

    async def add(self, kind, resource_id, payload=None):
        async with self.db.transaction() as c:
            return await enqueue(c, kind, resource_id, payload)

    async def claim(self, owner):
        async with self.db.transaction() as c:
            row = await (await c.execute(
                "SELECT * FROM jobs WHERE status='queued' OR (status='running' AND lease_until<?) "
                "ORDER BY created_at LIMIT 1", (time.time(),)
            )).fetchone()
            if not row:
                return None
            await c.execute(
                "UPDATE jobs SET status='running',lease_owner=?,lease_until=?,attempts=attempts+1 WHERE id=?",
                (owner, time.time() + 30, row["id"]),
            )
            return {**dict(row), "payload": json.loads(row["payload"])}

    async def renew(self, job_id, owner):
        async with self.db.transaction() as c:
            await c.execute("UPDATE jobs SET lease_until=? WHERE id=? AND lease_owner=? AND status='running'",
                            (time.time() + 30, job_id, owner))

    async def finish(self, job_id, owner, status="done"):
        async with self.db.transaction() as c:
            await c.execute("UPDATE jobs SET status=?,lease_until=NULL WHERE id=? AND lease_owner=?",
                            (status, job_id, owner))

    async def release(self, job_id, owner):
        async with self.db.transaction() as c:
            await c.execute("UPDATE jobs SET status='queued',lease_owner=NULL,lease_until=NULL "
                            "WHERE id=? AND lease_owner=? AND status='running'", (job_id, owner))
