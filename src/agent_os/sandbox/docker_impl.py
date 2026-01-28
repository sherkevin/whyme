from __future__ import annotations

import asyncio
import tarfile
from io import BytesIO
from typing import Optional, cast

import docker
from docker.models.containers import Container

from agent_os.core.interfaces import ExecutionEnvironment
from agent_os.server.security import (
    validate_command,
    validate_file_size,
    sanitize_path,
)


class DockerSandbox(ExecutionEnvironment):
    def __init__(
        self,
        image: str = "agentos-ubuntu:latest",
        workspace: str = "/workspace",
        memory_limit: str = "512m",
        cpu_quota: int = 50000,  # 50% of one CPU core
        network_disabled: bool = False,
        read_only: bool = False
    ) -> None:
        self.image = image
        self.workspace = workspace
        self.memory_limit = memory_limit
        self.cpu_quota = cpu_quota
        self.network_disabled = network_disabled
        self.read_only = read_only
        self._client: Optional[docker.DockerClient] = None
        self._container: Optional[Container] = None

    def _require_container(self) -> Container:
        if self._container is None:
            raise RuntimeError("Container not started")
        return self._container

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        if self._container:
            return
        self._client = await loop.run_in_executor(None, docker.from_env)

        def _start() -> Container:
            client = cast(docker.DockerClient, self._client)

            # Security and isolation configuration
            container_config = {
                "image": self.image,
                "command": "sleep infinity",
                "detach": True,
                "tty": True,
                "working_dir": self.workspace,
                # Resource limits
                "mem_limit": self.memory_limit,
                "cpu_quota": self.cpu_quota,
                "cpu_period": 100000,  # Standard CPU period
                # Security options
                "security_opt": ["no-new-privileges:true"],
                "cap_drop": ["ALL"],  # Drop all capabilities
                "cap_add": ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"],  # Add only necessary ones
                "read_only": self.read_only,
                # Network isolation
                "network_disabled": self.network_disabled,
                # User namespace remapping
                "user": "agentuser",
                # Prevent container from gaining new privileges
                "privileged": False,
                # Tmpfs for /tmp to prevent disk abuse
                "tmpfs": {"/tmp": "size=100m,mode=1777"},
                # Auto remove when stopped (optional)
                "auto_remove": False,
                # Labels for identification
                "labels": {
                    "agentos.sandbox": "true",
                    "agentos.type": "user-workspace"
                }
            }

            return client.containers.run(**container_config)

        self._container = await loop.run_in_executor(None, _start)

    async def run_command(self, cmd: str) -> str:
        if not self._container:
            await self.start()
        container = self._require_container()
        loop = asyncio.get_running_loop()

        # Security: Validate command before execution
        try:
            validate_command(cmd)
        except ValueError as e:
            raise RuntimeError(f"Command validation failed: {e}")

        def _exec() -> str:
            exec_result = container.exec_run(cmd, workdir=self.workspace)
            if isinstance(exec_result, tuple):
                exit_code, output = exec_result
            else:
                exit_code, output = exec_result.exit_code, exec_result.output
            if exit_code != 0:
                decoded = output.decode() if hasattr(output, "decode") else str(output)
                raise RuntimeError(decoded)
            return output.decode() if hasattr(output, "decode") else str(output)

        return await loop.run_in_executor(None, _exec)

    async def write_file(self, path: str, content: str) -> None:
        if not self._container:
            await self.start()

        # Security: Validate file size
        try:
            validate_file_size(len(content))
        except ValueError as e:
            raise RuntimeError(f"File size validation failed: {e}")

        container = self._require_container()
        loop = asyncio.get_running_loop()
        tarstream = BytesIO()

        # Security: Sanitize path
        try:
            safe_path = sanitize_path(path, "/")
        except ValueError as e:
            raise RuntimeError(f"Path validation failed: {e}")

        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            data = content.encode()
            tarinfo = tarfile.TarInfo(name=safe_path.lstrip("/"))
            tarinfo.size = len(data)
            tar.addfile(tarinfo=tarinfo, fileobj=BytesIO(data))
        tarstream.seek(0)

        def _put() -> None:
            container.put_archive(path="/", data=tarstream.getvalue())

        await loop.run_in_executor(None, _put)

    async def read_file(self, path: str) -> str:
        if not self._container:
            await self.start()
        container = self._require_container()
        loop = asyncio.get_running_loop()

        def _cat() -> str:
            cmd = f"cat {path}"
            exec_result = container.exec_run(cmd, workdir=self.workspace)
            if isinstance(exec_result, tuple):
                exit_code, output = exec_result
            else:
                exit_code, output = exec_result.exit_code, exec_result.output
            if exit_code != 0:
                decoded = output.decode() if hasattr(output, "decode") else str(output)
                raise RuntimeError(decoded)
            return output.decode() if hasattr(output, "decode") else str(output)

        return await loop.run_in_executor(None, _cat)

    async def list_files(self, path: str = ".") -> list[str]:
        output = await self.run_command(f"find {path} -maxdepth 5 -not -path '*/.*' -type f")
        return [line.strip().lstrip("./") for line in output.splitlines() if line.strip()]

    async def stop(self) -> None:
        if not self._container:
            return
        container = self._require_container()
        loop = asyncio.get_running_loop()

        def _stop() -> None:
            container.stop()
            container.remove()

        await loop.run_in_executor(None, _stop)
        self._container = None
