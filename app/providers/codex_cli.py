import shlex
import shutil
import subprocess

from app.providers.base import IntelligenceProvider, ProviderResult


class CodexCLIProvider(IntelligenceProvider):
    """Adapter for using Codex CLI as an optional intelligence provider."""

    name = "Codex CLI"

    def __init__(
        self,
        command: str = "codex",
        args: str = "exec --skip-git-repo-check",
        timeout_seconds: float = 120.0,
    ):
        self.command = command
        self.args = args
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        command_parts = shlex.split(self.command)

        if not command_parts:
            return False

        return shutil.which(command_parts[0]) is not None

    def generate(self, prompt: str) -> ProviderResult:
        if not self.is_available():
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error="Codex CLI command is not available.",
            )

        command = [
            *shlex.split(self.command),
            *shlex.split(self.args),
            prompt,
        ]

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error=str(error),
            )

        if result.returncode != 0:
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error=result.stderr.strip() or f"Codex exited with {result.returncode}.",
            )

        return ProviderResult(
            success=True,
            provider=self.name,
            content=result.stdout.strip(),
        )
