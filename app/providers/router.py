import sys
from enum import Enum

from app.core.config import Settings
from app.core.artifacts import PipelineTrace
from app.providers.base import IntelligenceProvider, ProviderResult
from app.providers.codex_cli import CodexCLIProvider
from app.providers.local_llm import LocalLLMProvider


class ProviderPolicy(str, Enum):
    """User-selected provider routing policy."""

    AUTO = "AUTO"
    LOCAL_ONLY = "LOCAL_ONLY"
    CODEX_ONLY = "CODEX_ONLY"
    CODEX_PREFERRED = "CODEX_PREFERRED"
    ASK = "ASK"

    @classmethod
    def from_value(cls, value: str) -> "ProviderPolicy":
        normalized = value.strip().upper()

        for policy in cls:
            if policy.value == normalized:
                return policy

        return cls.AUTO


class ProviderRouter:
    """Selects an intelligence provider according to user policy."""

    def __init__(
        self,
        policy: ProviderPolicy,
        local_provider: IntelligenceProvider,
        codex_provider: IntelligenceProvider,
    ):
        self.policy = policy
        self.local_provider = local_provider
        self.codex_provider = codex_provider

    @classmethod
    def from_settings(cls, settings: Settings) -> "ProviderRouter":
        return cls(
            policy=ProviderPolicy.from_value(settings.provider_policy),
            local_provider=LocalLLMProvider(
                base_url=settings.local_llm_base_url,
                model=settings.local_llm_model,
                probe_timeout_seconds=settings.provider_probe_timeout_seconds,
                timeout_seconds=settings.local_llm_timeout_seconds,
            ),
            codex_provider=CodexCLIProvider(
                command=settings.codex_command,
                args=settings.codex_args,
                timeout_seconds=settings.codex_timeout_seconds,
            ),
        )

    def generate(
        self,
        prompt: str,
        trace: PipelineTrace | None = None,
    ) -> ProviderResult:
        policy = self._resolve_policy()

        if trace:
            trace.add("Provider Router", f"Using provider policy {policy.value}")

        failures = []

        for provider in self._providers_for(policy):
            if not provider.is_available():
                failures.append(f"{provider.name}: unavailable")

                if trace:
                    trace.add("Provider Router", f"{provider.name} unavailable")

                continue

            result = provider.generate(prompt)

            if result.success:
                if trace:
                    trace.add("Provider Router", f"Selected {provider.name}")

                return result

            failures.append(f"{provider.name}: {result.error or 'failed'}")

            if trace:
                trace.add(
                    "Provider Router",
                    f"{provider.name} failed: {result.error or 'unknown error'}",
                )

        return ProviderResult(
            success=False,
            provider="Provider Router",
            content="",
            error="; ".join(failures) or "No provider selected.",
        )

    def status(self) -> dict[str, str | bool]:
        return {
            "policy": self.policy.value,
            "local_available": self.local_provider.is_available(),
            "codex_available": self.codex_provider.is_available(),
        }

    def _providers_for(
        self,
        policy: ProviderPolicy,
    ) -> list[IntelligenceProvider]:
        if policy == ProviderPolicy.LOCAL_ONLY:
            return [self.local_provider]

        if policy == ProviderPolicy.CODEX_ONLY:
            return [self.codex_provider]

        if policy == ProviderPolicy.CODEX_PREFERRED:
            return [self.codex_provider, self.local_provider]

        return [self.local_provider]

    def _resolve_policy(self) -> ProviderPolicy:
        if self.policy != ProviderPolicy.ASK:
            return self.policy

        if not sys.stdin.isatty():
            return ProviderPolicy.AUTO

        print("Choose provider policy:")
        print("1. AUTO")
        print("2. LOCAL_ONLY")
        print("3. CODEX_ONLY")
        print("4. CODEX_PREFERRED")
        choice = input("> ").strip()

        return {
            "1": ProviderPolicy.AUTO,
            "2": ProviderPolicy.LOCAL_ONLY,
            "3": ProviderPolicy.CODEX_ONLY,
            "4": ProviderPolicy.CODEX_PREFERRED,
        }.get(choice, ProviderPolicy.AUTO)
