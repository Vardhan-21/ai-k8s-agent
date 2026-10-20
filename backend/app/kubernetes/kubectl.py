"""Reusable utility to safely execute kubectl commands.

Wraps Python subprocess to run kubectl, capture output,
handle failures gracefully, and return structured results.
"""

import asyncio
import shlex
from dataclasses import dataclass, field

from loguru import logger

from app.core.config import settings


@dataclass
class KubectlResult:
    """Structured result from a kubectl command execution."""

    command: str
    success: bool
    output: str = ""
    error: str = ""
    return_code: int = 0


class KubectlExecutor:
    """Execute kubectl commands safely via subprocess."""

    def __init__(self, context: str | None = None) -> None:
        self._kubeconfig = settings.KUBECONFIG_PATH
        self._context = context

    @property
    def context(self) -> str | None:
        return self._context

    def _build_command(self, args: str) -> str:
        """Build the full kubectl command string."""
        parts = ["kubectl"]
        if self._kubeconfig:
            parts.append(f"--kubeconfig {shlex.quote(self._kubeconfig)}")
        if self._context:
            parts.append(f"--context {shlex.quote(self._context)}")
        parts.append(args)
        return " ".join(parts)

    async def execute(self, args: str, timeout: int = 30) -> KubectlResult:
        """Execute a kubectl command and return structured output.

        Args:
            args: The kubectl arguments (e.g. "get pods -A -o json").
            timeout: Maximum seconds to wait for the command.

        Returns:
            KubectlResult with command output or error details.
        """
        full_command = self._build_command(args)
        logger.info(f"Executing: {full_command}")

        try:
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()
            success = process.returncode == 0

            if not success:
                logger.warning(
                    f"kubectl command failed (exit {process.returncode}): {stderr_str}"
                )

            return KubectlResult(
                command=full_command,
                success=success,
                output=stdout_str,
                error=stderr_str,
                return_code=process.returncode or 0,
            )

        except asyncio.TimeoutError:
            logger.error(f"kubectl command timed out after {timeout}s: {full_command}")
            return KubectlResult(
                command=full_command,
                success=False,
                error=f"Command timed out after {timeout} seconds",
                return_code=-1,
            )
        except Exception as exc:
            logger.error(f"kubectl execution error: {exc}")
            return KubectlResult(
                command=full_command,
                success=False,
                error=str(exc),
                return_code=-1,
            )

    async def execute_json(self, args: str, timeout: int = 30) -> tuple[bool, dict | list | None, str]:
        """Execute a kubectl command that returns JSON.

        Appends ``-o json`` when not already present, then parses the output.

        Returns:
            Tuple of (success, parsed_data_or_None, error_message).
        """
        import json as _json

        if "-o json" not in args and "-o=json" not in args:
            args = f"{args} -o json"

        result = await self.execute(args, timeout=timeout)

        if not result.success:
            return False, None, result.error

        try:
            data = _json.loads(result.output) if result.output else {}
            return True, data, ""
        except _json.JSONDecodeError as exc:
            logger.error(f"Failed to parse kubectl JSON output: {exc}")
            return False, None, f"JSON parse error: {exc}"
