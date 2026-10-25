import hashlib
import io
import json
import zipfile

from fastapi import APIRouter, Header, Request
from fastapi.responses import Response

from gemmagraph.contracts import ExperimentCreate
from gemmagraph.errors import AppError

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("", status_code=202)
async def create_experiment(body: ExperimentCreate, request: Request,
                           idempotency_key: str = Header(..., alias="Idempotency-Key",
                                                         min_length=8, max_length=200)):
    return await request.app.state.experiments.create(body, idempotency_key)


@router.get("")
async def list_experiments(request: Request):
    values = await request.app.state.db.list("experiment")
    return {"items": [{k: v for k, v in x.items() if k != "run_ids"}
                       for x in sorted(values, key=lambda v: v["created_at"], reverse=True)]}


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str, request: Request):
    return await request.app.state.experiments.detail(experiment_id)


@router.post("/{experiment_id}/cancel", status_code=202)
async def cancel_experiment(experiment_id: str, request: Request):
    exp = await request.app.state.db.get("experiment", experiment_id)
    for rid in exp["run_ids"]:
        try:
            run = await request.app.state.db.get("run", rid)
            if run["status"] in {"queued", "running"}:
                await request.app.state.db.update("run", rid, cancel_requested=True)
                await request.app.state.events.append(rid, "run.cancel_requested", source_key="run:cancel-requested")
        except AppError:
            continue
    return {"id": experiment_id, "status": "cancelling"}


@router.post("/{experiment_id}/export")
async def export_experiment(experiment_id: str, request: Request):
    exp = await request.app.state.experiments.detail(experiment_id)
    if exp["status"] != "completed":
        raise AppError("experiment_incomplete", "实验仍有运行项尚未完成", 409)
    dataset = await request.app.state.db.get("dataset", exp["dataset_id"])
    results = []
    for run in exp["runs"]:
        results.append(run)
    metrics = [{k: v for k, v in row.items() if k != "items"} for row in exp["metrics"]]
    buffer = io.BytesIO()
    payloads = {
        "tasks.jsonl": "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in dataset["tasks"]),
        "results.jsonl": "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in results),
        "metrics.json": json.dumps(metrics, ensure_ascii=False, indent=2),
        "config.json": json.dumps(exp["config"], ensure_ascii=False, indent=2),
    }
    manifest = {"experiment_id": experiment_id, "dataset_sha256": dataset["sha256"],
                "files": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in payloads.items()}}
    payloads["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2)
    payloads["report.md"] = "# 实验结果\n\n" + "\n".join(
        f"- {m['method']}: {m['solved']}/{m['planned']}，成功率 {m['solve_rate']:.3f}"
        for m in metrics)
    payloads["reproduce.md"] = (
        "# 复现\n\n请按 config.json 使用相同版本模型、任务清单、检索方法、预算和沙箱镜像重新运行。"
        "模型修订与平台未能采集的指标见逐任务结果。\n"
    )
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in payloads.items():
            zf.writestr(name, content)
    return Response(buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{experiment_id}.zip"'})
