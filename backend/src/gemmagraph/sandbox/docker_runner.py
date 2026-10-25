import asyncio
import re
import time
from pathlib import Path

from gemmagraph.sandbox.policy import validate_profile


class DockerRunner:
    def __init__(self, settings):
        self.settings = settings
        self.profiles = settings.profiles()

    @staticmethod
    async def _capture(*args, timeout):
        proc = await asyncio.create_subprocess_exec(
            "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        communication = asyncio.create_task(proc.communicate())
        try:
            out, err = await asyncio.wait_for(asyncio.shield(communication), timeout=timeout)
            return proc.returncode, out, err
        except (asyncio.TimeoutError, asyncio.CancelledError):
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            await asyncio.shield(communication)
            raise

    async def available(self):
        try:
            code, out, err = await self._capture("info", "--format", "{{.ServerVersion}}", timeout=5)
        except asyncio.TimeoutError:
            raise RuntimeError("Docker daemon 检查超时")
        if code:
            raise RuntimeError(err.decode(errors="replace")[:300])
        engine_version = out.decode().strip()
        try:
            code, _, image_err = await self._capture(
                "image", "inspect", self.settings.sandbox_image, "--format", "{{.Id}}", timeout=5)
        except asyncio.TimeoutError:
            raise RuntimeError("Docker 镜像检查超时")
        if code:
            detail = image_err.decode(errors="replace")[:240]
            raise RuntimeError(f"本地沙箱镜像 {self.settings.sandbox_image} 不可用；先构建 infra/sandbox/Dockerfile。 {detail}")
        return engine_version

    async def stop_run(self, run_id):
        name = f"gemmagraph-{run_id}"
        for args in (("kill", name), ("rm", "--force", name)):
            try:
                await self._capture(*args, timeout=3)
            except (OSError, asyncio.TimeoutError):
                continue

    async def run(self, root: Path, profile_id, timeout):
        profile = self.profiles.get(profile_id)
        validate_profile(profile or {}, self.settings.sandbox_image)
        await self.available()
        # The private run workspace is the only writable bind mount. Permit the
        # unprivileged container UID to write test output and temporary files there.
        for path in [root, *root.rglob("*")]:
            if path.is_dir():
                path.chmod(0o777)
            elif path.is_file():
                path.chmod(0o666)
        container_name = f"gemmagraph-{root.name}"
        await self.stop_run(root.name)
        cmd = ["docker", "run", "--pull=never", "--rm", "--name", container_name, "--network", "none",
               "--read-only", "--user", "65534:65534",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--memory",
               f"{profile.get('memory_mb',1024)}m", "--cpus", str(profile.get("cpus", 1)),
               "--pids-limit", str(profile.get("pids", 128)), "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
               "--mount", f"type=bind,src={root.resolve()},dst=/workspace,rw", "--workdir", "/workspace",
               "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
               self.settings.sandbox_image, *profile["command"]]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
        started = time.monotonic()
        communication = asyncio.create_task(proc.communicate())
        try:
            out, err = await asyncio.wait_for(asyncio.shield(communication), timeout=timeout)
            stdout, stderr = out.decode(errors="replace")[-16000:], err.decode(errors="replace")[-8000:]
            m = re.search(r"(\d+) (?:passed|failed|error|skipped|collected)", stdout + stderr)
            return {"exit_code": proc.returncode, "timed_out": False,
                    "collected": int(m.group(1)) if m else 0, "stdout": stdout,
                    "stderr": stderr, "environment_error": proc.returncode in {2, 3, 4, 5, 125, 126, 127}
                    or "no such image" in stderr.lower(),
                    "duration_seconds": round(time.monotonic() - started, 2)}
        except asyncio.TimeoutError:
            await self._stop_container(container_name, proc)
            try:
                out, err = await asyncio.wait_for(communication, timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                out, err = b"", "容器进程在终止后仍未退出".encode()
            return {"exit_code": -1, "timed_out": True, "collected": 0,
                    "stdout": out.decode(errors="replace")[-16000:],
                    "stderr": (err.decode(errors="replace")[-8000:] or "容器测试超时"),
                    "environment_error": False, "duration_seconds": round(time.monotonic() - started, 2)}
        except asyncio.CancelledError:
            await asyncio.shield(self._stop_container(container_name, proc))
            try:
                await asyncio.shield(asyncio.wait_for(communication, timeout=5))
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if proc.returncode is None:
                    proc.kill()
            raise

    async def _stop_container(self, name, client_process):
        try:
            await self._capture("kill", name, timeout=3)
        except (OSError, asyncio.TimeoutError):
            pass
        if client_process.returncode is None:
            client_process.terminate()
            try:
                await asyncio.wait_for(client_process.wait(), timeout=2)
            except asyncio.TimeoutError:
                client_process.kill()
                await client_process.wait()
