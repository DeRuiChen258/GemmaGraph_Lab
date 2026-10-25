import asyncio

from fastapi import APIRouter, File, Form, Query, Request, UploadFile

from gemmagraph.errors import AppError
from gemmagraph.services.workspaces import resolve_inside

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("", status_code=202)
async def create_repository(request: Request, name: str = Form(...), archive: UploadFile = File(...)):
    if not archive.filename or not archive.filename.lower().endswith(".zip"):
        raise AppError("invalid_upload", "请选择 .zip 格式的 Python 仓库")
    raw = await archive.read(50 * 1024 * 1024 + 1)
    value = await request.app.state.repositories.import_zip(name, raw)
    return value


@router.get("")
async def list_repositories(request: Request, limit: int = Query(50, ge=1, le=200)):
    values = sorted(await request.app.state.db.list("repository"),
                    key=lambda r: r["created_at"], reverse=True)
    return {"items": values[:limit], "next_cursor": values[limit]["id"] if len(values) > limit else None}


@router.get("/{repository_id}")
async def repository_detail(repository_id: str, request: Request):
    return await request.app.state.db.get("repository", repository_id)


@router.post("/{repository_id}/index", status_code=202)
async def reindex(repository_id: str, request: Request):
    await request.app.state.db.get("repository", repository_id)
    await request.app.state.queue.add("index", repository_id)
    await request.app.state.db.update("repository", repository_id, index_status="queued")
    return {"repository_id": repository_id, "index_status": "queued"}


@router.get("/{repository_id}/tree")
async def file_tree(repository_id: str, request: Request, directory: str = ""):
    repo = await request.app.state.db.get("repository", repository_id)
    root = request.app.state.workspaces.source(repo["snapshot_id"])
    folder = resolve_inside(root, directory) if directory else root
    if not folder.is_dir():
        raise AppError("not_found", "目录不存在", 404)
    items = []
    for p in sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))[:500]:
        rel = p.relative_to(root).as_posix()
        from gemmagraph.services.workspaces import is_public
        if p.is_symlink() or not is_public(rel):
            continue
        items.append({"name": p.name, "path": rel, "type": "directory" if p.is_dir() else "file",
                      "size": None if p.is_dir() else p.stat().st_size})
    return {"items": items, "truncated": len(list(folder.iterdir())) > len(items)}


@router.get("/{repository_id}/file")
async def file_content(repository_id: str, request: Request, path: str,
                       start_line: int = Query(1, ge=1), end_line: int | None = Query(None, ge=1)):
    repo = await request.app.state.db.get("repository", repository_id)
    return await request.app.state.repositories.file(repo, path, start_line, end_line)


@router.get("/{repository_id}/graph")
async def graph(repository_id: str, request: Request, node: str | None = None,
                query: str = "", hops: int = Query(1, ge=0, le=2), limit: int = Query(200, ge=1, le=500)):
    repo = await request.app.state.db.get("repository", repository_id)
    index = await asyncio.to_thread(request.app.state.index_store.load_or_build, repo)
    if repo.get("index_status") != "ready":
        await request.app.state.db.update("repository", repository_id, index_status="ready",
                                          file_count=index.file_count, symbol_count=len(index.symbols),
                                          parse_coverage=index.parsed_count / max(1, index.python_count),
                                          diagnostics=index.diagnostics)
    return request.app.state.index_store.subgraph(index, node=node, query=query, hops=hops, limit=limit)
