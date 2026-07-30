from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderResult:
    """Result returned by an intelligence provider."""

    success: bool
    provider: str
    content: str
    error: str | None = None


class IntelligenceProvider(ABC):
    """Common interface for local and external intelligence providers."""

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the provider can be used now."""

    @abstractmethod
    def generate(self, prompt: str) -> ProviderResult:
        """Generate a response from a provider-neutral prompt."""
