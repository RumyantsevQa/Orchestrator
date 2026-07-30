from dataclasses import dataclass

from app.core.artifacts import Artifact, PipelineTrace
from app.core.task_plan import TaskPlan


@dataclass(frozen=True)
class ContextPackage:
    """Bounded context package produced from generic artifacts."""

    summary: str
    artifacts: tuple[Artifact, ...]
    budget: int

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "budget": self.budget,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


class ContextComposer:
    """
    Builds context from artifacts without knowing which service produced them.

    The composer does not know about Retrieval, Memory, Jira, or any other
    concrete source. It only receives artifacts and a task plan.
    """

    def compose(
        self,
        plan: TaskPlan,
        artifacts: list[Artifact],
        trace: PipelineTrace | None = None,
    ) -> ContextPackage:
        if trace:
            trace.add("Context Composer", "Composed context package from artifacts")

        summary = "\n".join(
            f"- {artifact.source}: {artifact.content}"
            for artifact in artifacts
        )

        return ContextPackage(
            summary=summary,
            artifacts=tuple(artifacts),
            budget=plan.context_budget,
        )
