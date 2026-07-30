from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    """A named ability exposed by a service."""

    name: str
    description: str
    provider: str


class CapabilityRegistry:
    """Stores capabilities currently available to the planner."""

    def __init__(self):
        self._capabilities: dict[str, Capability] = {}

    def register(
        self,
        name: str,
        description: str,
        provider: str,
    ) -> None:
        self._capabilities[name] = Capability(
            name=name,
            description=description,
            provider=provider,
        )

    def has(self, name: str) -> bool:
        return name in self._capabilities

    def get(self, name: str) -> Capability:
        return self._capabilities[name]

    def all(self) -> list[Capability]:
        return list(self._capabilities.values())

    def names(self) -> set[str]:
        return set(self._capabilities)
