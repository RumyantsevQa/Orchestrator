from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Artifact:
    """A typed result produced by a pipeline component or service."""

    name: str
    source: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PipelineEvent:
    """A single observable step in request processing."""

    component: str
    message: str


class PipelineTrace:
    """Collects component participation for debugging and CLI output."""

    def __init__(self):
        self._events: list[PipelineEvent] = []

    def add(self, component: str, message: str) -> None:
        self._events.append(PipelineEvent(component=component, message=message))

    def events(self) -> list[PipelineEvent]:
        return list(self._events)

    def component_names(self) -> list[str]:
        return [event.component for event in self._events]

    def to_dicts(self) -> list[dict[str, str]]:
        return [
            {
                "component": event.component,
                "message": event.message,
            }
            for event in self._events
        ]
