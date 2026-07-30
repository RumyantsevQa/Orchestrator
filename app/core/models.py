from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UserRequest:
    """External request received from the user-facing interface."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrchestratorResponse:
    """Serializable response returned by the application entrypoints."""

    success: bool
    message: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
        }
