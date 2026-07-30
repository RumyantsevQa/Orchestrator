from dataclasses import dataclass

from app.context.composer import ContextPackage
from app.core.artifacts import PipelineTrace
from app.core.models import UserRequest
from app.core.task_plan import TaskPlan


@dataclass(frozen=True)
class PromptPackage:
    """Provider-neutral prompt package for the LLM service."""

    text: str
    response_contract: str

    def to_dict(self) -> dict[str, str]:
        return {
            "text": self.text,
            "response_contract": self.response_contract,
        }


class PromptBuilder:
    """
    Converts a context package into a provider-neutral prompt package.

    It does not know whether context came from Memory, Retrieval, Jira, Browser,
    or any future service.
    """

    def build(
        self,
        request: UserRequest,
        plan: TaskPlan,
        context: ContextPackage,
        trace: PipelineTrace | None = None,
    ) -> PromptPackage:
        if trace:
            trace.add("Prompt Builder", "Built provider-neutral prompt package")

        text = "\n\n".join(
            [
                "System: QASkills prepares grounded QA work context.",
                f"User request: {request.text}",
                f"Goal: {plan.goal}",
                f"Context budget: {context.budget}",
                "Context:",
                context.summary,
            ]
        )

        return PromptPackage(
            text=text,
            response_contract=plan.response_contract,
        )
