from dataclasses import dataclass, field


@dataclass(frozen=True)
class UserIntent:
    """Normalized representation of what the user wants to accomplish."""

    name: str
    raw_text: str
    expected_output: str
    confidence: float
    metadata: dict[str, str] = field(default_factory=dict)
