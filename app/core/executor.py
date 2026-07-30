from collections.abc import Mapping
from typing import Any

from app.core.artifacts import Artifact, PipelineTrace
from app.core.intent import UserIntent
from app.core.models import UserRequest
from app.core.task_plan import PlanStep, TaskPlan
from app.services.base import ServiceRegistry, ServiceRequest


class PlanExecutor:
    """
    Executes plan steps through service interfaces.

    The executor does not know how a service is implemented. It only resolves a
    capability to a registered service and asks that service to execute it.
    """

    def __init__(self, services: ServiceRegistry):
        self.services = services

    def execute_collection(
        self,
        plan: TaskPlan,
        request: UserRequest,
        intent: UserIntent,
        trace: PipelineTrace | None = None,
    ) -> list[Artifact]:
        if trace:
            trace.add("Plan Executor", "Executing collection steps")

        artifacts = []

        for step in plan.collection_steps():
            artifacts.append(
                self.execute_step(
                    step=step,
                    plan=plan,
                    request=request,
                    intent=intent,
                    artifacts=artifacts,
                    trace=trace,
                )
            )

        return artifacts

    def execute_step(
        self,
        step: PlanStep,
        plan: TaskPlan,
        request: UserRequest,
        intent: UserIntent,
        artifacts: list[Artifact],
        trace: PipelineTrace | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Artifact:
        service = self.services.get(step.capability)
        service_payload = dict(step.parameters)
        service_payload.update(dict(payload or {}))

        service_request = ServiceRequest(
            user_text=request.text,
            intent=intent,
            plan=plan,
            artifacts=tuple(artifacts),
            payload=service_payload,
        )

        return service.execute(
            capability=step.capability,
            request=service_request,
            trace=trace,
        )
