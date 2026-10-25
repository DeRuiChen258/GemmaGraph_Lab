import hashlib
import json
import os
from pathlib import Path

from gemmagraph.db import now
from gemmagraph.services.workspaces import resolve_inside, safe_relative


class Artifacts:
    def __init__(self, db, settings):
        self.db, self.root = db, settings.data_dir.resolve()

    async def write(self, run_id, name, content, media_type="text/plain"):
        safe_relative(run_id)
        safe_relative(name)
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False, indent=2)
            media_type = "application/json"
        raw = content.encode() if isinstance(content, str) else content
        sha = hashlib.sha256(raw).hexdigest()
        artifact_id = "art_" + hashlib.sha256(f"{run_id}/{name}/{sha}".encode()).hexdigest()[:24]
        path = self.root / "artifacts" / run_id / artifact_id / Path(name).name
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(raw)
        os.replace(temp, path)
        value = dict(id=artifact_id, run_id=run_id, name=name, sha256=sha, size=len(raw),
                     media_type=media_type, created_at=now(), internal_path=str(path.relative_to(self.root)))
        await self.db.put("artifact", value)
        return {k: v for k, v in value.items() if k != "internal_path"}

    async def file(self, artifact_id):
        value = await self.db.get("artifact", artifact_id)
        return resolve_inside(self.root, value["internal_path"]), value

    async def list(self, run_id):
        return [{k: v for k, v in x.items() if k != "internal_path"}
                for x in await self.db.list("artifact") if x["run_id"] == run_id]
