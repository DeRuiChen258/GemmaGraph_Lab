import json

from fastapi import APIRouter, File, Form, Request, UploadFile

from gemmagraph.errors import AppError

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/import", status_code=201)
async def import_dataset(request: Request, file: UploadFile = File(...),
                         repository_map: str = Form("{}"), name: str | None = Form(None)):
    try:
        mapping = json.loads(repository_map)
        if not isinstance(mapping, dict):
            raise ValueError
    except ValueError as e:
        raise AppError("invalid_repository_map", "repository_map 必须是 JSON 对象") from e
    return await request.app.state.datasets.import_jsonl(name or (file.filename or "tasks.jsonl"),
                                                          await file.read(5 * 1024 * 1024 + 1), mapping)


@router.get("")
async def list_datasets(request: Request):
    return {"items": [{k: v for k, v in d.items() if k != "tasks"}
                       for d in await request.app.state.db.list("dataset")]}


@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str, request: Request):
    return await request.app.state.db.get("dataset", dataset_id)
