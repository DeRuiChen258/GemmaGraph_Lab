from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, request: Request):
    path, record = await request.app.state.artifacts.file(artifact_id)
    return FileResponse(path, media_type=record["media_type"], filename=record["name"])
