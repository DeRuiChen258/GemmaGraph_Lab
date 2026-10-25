"""Process protocol regressions; these do not run Docker or repository code."""

import asyncio

import pytest
from gemmagraph.sandbox.docker_runner import DockerRunner


class ProcessFixture:
    def __init__(self):
        self.returncode = None
        self.stopped = asyncio.Event()
        self.communication_finished = False

    async def communicate(self):
        await self.stopped.wait()
        self.communication_finished = True
        return b"", b"fixture process stopped"

    def kill(self):
        self.returncode = -9
        self.stopped.set()


@pytest.fixture
def process_fixture(monkeypatch):
    process = ProcessFixture()
    async def create(*args, **kwargs):
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    return process


async def test_timeout_kills_check_process_and_drains_communication(process_fixture):
    with pytest.raises(asyncio.TimeoutError):
        await DockerRunner._capture("info", timeout=.01)
    assert process_fixture.returncode == -9
    assert process_fixture.communication_finished


async def test_cancellation_kills_check_process_and_drains_communication(process_fixture):
    task = asyncio.create_task(DockerRunner._capture("info", timeout=30))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process_fixture.returncode == -9
    assert process_fixture.communication_finished
