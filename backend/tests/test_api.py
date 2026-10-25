"""In-process HTTP regressions against the real FastAPI app and SQLite services.

No model inference or Docker execution takes place in these API tests.
"""

from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
from gemmagraph.settings import Settings


def archive_with(path="src/calc.py"):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(path, "def add(left, right):\n    return left - right\n")
    return stream.getvalue()


@pytest.fixture
async def api_client(tmp_path, monkeypatch):
    from gemmagraph import main

    settings = Settings(_env_file=None, data_dir=tmp_path / "data", model_provider="llama_cpp_local",
                        model_path=tmp_path / "fixture.gguf", llama_cpp_dir=tmp_path / "runtime",
                        model_api_key="fixture-secret-must-not-be-returned", model_gpu_layers=999)

    class SandboxFixture:
        def __init__(self, settings):
            pass

        async def available(self):
            raise RuntimeError("Docker status fixture: no daemon requested")

    monkeypatch.setattr(main, "Settings", lambda: settings)
    monkeypatch.setattr(main, "DockerRunner", SandboxFixture)
    async with main.app.router.lifespan_context(main.app):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_health_and_local_settings_are_valid_json_without_credentials(api_client):
    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "ready",
                               "worker": {"alive": False, "last_seen_seconds": None}}
    response = await api_client.get("/api/v1/settings")
    assert response.status_code == 200
    model = response.json()["model"]
    assert model["provider"] == "llama_cpp_local"
    assert model["transport"] == "subprocess" and model["device"] == "gpu"
    assert model["cuda_toolkit_version"] == "13.4"
    assert model["base_url"] == "" and model["key_configured"] is False
    assert "model_api_key" not in model
    assert "fixture-secret-must-not-be-returned" not in response.text


async def test_repository_upload_and_run_creation_are_idempotent(api_client):
    uploaded = await api_client.post("/api/v1/repositories", data={"name": "API fixture"},
                                     files={"archive": ("fixture.zip", archive_with(), "application/zip")})
    assert uploaded.status_code == 202
    repository_id = uploaded.json()["id"]
    payload = {"repository_id": repository_id, "issue": "Fix the subtraction in add."}
    headers = {"Idempotency-Key": "api-fixture-run-key"}
    first = await api_client.post("/api/v1/runs", json=payload, headers=headers)
    assert first.status_code == 202
    repeated = await api_client.post("/api/v1/runs", json=payload, headers=headers)
    assert repeated.status_code == 202
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["status"] == "queued"
    assert first.json()["config_snapshot"]["model"]["provider"] == "llama_cpp_local"
    conflicting = await api_client.post("/api/v1/runs", headers=headers,
                                        json={**payload, "issue": "A different issue with the same request key."})
    assert conflicting.status_code == 409
    assert conflicting.json()["code"] == "idempotency_conflict"
    listed = await api_client.get("/api/v1/runs")
    assert len(listed.json()["items"]) == 1


async def test_zip_traversal_and_file_traversal_are_rejected(api_client):
    malicious = await api_client.post("/api/v1/repositories", data={"name": "Malicious fixture"},
                                      files={"archive": ("bad.zip", archive_with("../../outside.py"),
                                                         "application/zip")})
    assert malicious.status_code == 400
    assert malicious.json()["code"] == "invalid_zip_path"
    assert (await api_client.get("/api/v1/repositories")).json()["items"] == []
    uploaded = await api_client.post("/api/v1/repositories", data={"name": "Safe fixture"},
                                     files={"archive": ("safe.zip", archive_with(), "application/zip")})
    assert uploaded.status_code == 202
    repository_id = uploaded.json()["id"]
    rejected = await api_client.get(f"/api/v1/repositories/{repository_id}/file",
                                    params={"path": "../../outside.py"})
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "invalid_path"
    source = await api_client.get(f"/api/v1/repositories/{repository_id}/file",
                                  params={"path": "src/calc.py"})
    assert source.status_code == 200
    assert "return left - right" in source.json()["content"]
