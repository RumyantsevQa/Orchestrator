from dataclasses import dataclass, field
from typing import Any

from app.core.intent import UserIntent


@dataclass(frozen=True)
class PlanStep:
    """One executable step selected by the planner."""

    id: str
    component: str
    capability: str
    phase: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskPlan:
    """Planner output consumed by the executor and downstream composers."""

    goal: str
    intent: UserIntent
    steps: list[PlanStep]
    response_contract: str
    context_budget: int
    missing_capabilities: list[str] = field(default_factory=list)

    def collection_steps(self) -> list[PlanStep]:
        return [step for step in self.steps if step.phase == "collect"]

    def generation_step(self) -> PlanStep | None:
        for step in self.steps:
            if step.phase == "generate":
                return step

        return None

    def needs_generation(self) -> bool:
        """Return whether this plan explicitly asks for LLM generation."""

        return self.generation_step() is not None

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "intent": self.intent.name,
            "response_contract": self.response_contract,
            "context_budget": self.context_budget,
            "missing_capabilities": self.missing_capabilities,
            "steps": [
                {
                    "id": step.id,
                    "component": step.component,
                    "capability": step.capability,
                    "phase": step.phase,
                    "description": step.description,
                    "parameters": step.parameters,
                }
                for step in self.steps
            ],
        }
