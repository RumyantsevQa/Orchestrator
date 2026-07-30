from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.artifacts import Artifact, PipelineTrace
from app.core.capabilities import CapabilityRegistry
from app.core.intent import UserIntent
from app.core.task_plan import TaskPlan


@dataclass(frozen=True)
class ServiceRequest:
    """Input envelope passed to services by the plan executor."""

    user_text: str
    intent: UserIntent
    plan: TaskPlan
    artifacts: tuple[Artifact, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)


class BaseService(ABC):
    """Abstract service interface used by the executor."""

    name: str
    capabilities: dict[str, str]

    @abstractmethod
    def execute(
        self,
        capability: str,
        request: ServiceRequest,
        trace: PipelineTrace | None = None,
    ) -> Artifact:
        pass


class ServiceRegistry:
    """Maps capabilities to service implementations."""

    def __init__(self, capabilities: CapabilityRegistry):
        self.capabilities = capabilities
        self._services_by_capability: dict[str, BaseService] = {}

    def register(self, service: BaseService) -> None:
        for capability, description in service.capabilities.items():
            self.capabilities.register(
                name=capability,
                description=description,
                provider=service.name,
            )
            self._services_by_capability[capability] = service

    def get(self, capability: str) -> BaseService:
        return self._services_by_capability[capability]

    def available_capabilities(self) -> set[str]:
        return set(self._services_by_capability)
