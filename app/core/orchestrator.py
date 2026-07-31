from app.context.composer import ContextComposer
from app.core.config import load_settings
from app.core.artifacts import Artifact, PipelineTrace
from app.core.capabilities import CapabilityRegistry
from app.core.executor import PlanExecutor
from app.core.intent import UserIntent
from app.core.intent_analyzer import IntentAnalyzer
from app.core.models import UserRequest, OrchestratorResponse
from app.core.planner import TaskPlanner
from app.core.task_plan import TaskPlan
from app.prompt.prompt_builder import PromptBuilder
from app.providers.router import ProviderRouter
from app.response.composer import ResponseComposer
from app.services.jira_client import JiraCredentials
from app.work_context import (
    SeenStateDelta,
    SeenStateStorage,
    compare_seen_state,
    current_jira_issue_state,
)
from app.services import (
    ChangeAnalysisService,
    DailyBriefService,
    JiraService,
    LLMService,
    MemoryService,
    ServiceRegistry,
    SkillService,
    SnapshotService,
)


class Orchestrator:
    """Application service that wires the current request pipeline together."""

    def __init__(self):
        self.settings = load_settings()
        self.capabilities = CapabilityRegistry()
        self.services = ServiceRegistry(self.capabilities)

        for service in [
            MemoryService(
                vault_path=self.settings.memory_vault_path,
                index_path=self.settings.document_index_path,
            ),
            SkillService(vault_path=self.settings.memory_vault_path),
            JiraService(
                credentials=JiraCredentials.from_settings(self.settings),
            ),
            SnapshotService(vault_path=self.settings.memory_vault_path),
            ChangeAnalysisService(),
            DailyBriefService(),
            LLMService(
                provider_router=ProviderRouter.from_settings(self.settings),
            ),
        ]:
            self.services.register(service)

        self.intent_analyzer = IntentAnalyzer()
        self.task_planner = TaskPlanner(self.capabilities)
        self.plan_executor = PlanExecutor(self.services)
        self.response_composer = ResponseComposer()
        self.seen_state_storage = SeenStateStorage(
            self.settings.personal_seen_state_path
        )

    def process(self, request: UserRequest) -> OrchestratorResponse:
        trace = PipelineTrace()

        trace.add("Orchestrator", "Started request pipeline")
        intent = self.intent_analyzer.analyze(request)
        trace.add("Intent Analyzer", f"Detected intent {intent.name}")

        plan = self.task_planner.plan(intent, trace=trace)

        artifacts = self.plan_executor.execute_collection(
            plan=plan,
            request=request,
            intent=intent,
            trace=trace,
        )
        artifacts = self._with_seen_state_delta(
            intent=intent,
            artifacts=artifacts,
        )

        llm_artifact = None

        if plan.needs_generation():
            context = ContextComposer().compose(
                plan=plan,
                artifacts=artifacts,
                trace=trace,
            )

            prompt = PromptBuilder().build(
                request=request,
                plan=plan,
                context=context,
                trace=trace,
            )

            llm_artifact = self._generate_response_artifact(
                plan=plan,
                request=request,
                intent=intent,
                artifacts=artifacts,
                prompt_text=prompt.text,
                trace=trace,
            )

        return self.response_composer.compose(
            request=request,
            intent=intent,
            plan=plan,
            artifacts=artifacts,
            llm_artifact=llm_artifact,
            trace=trace,
        )

    def ask(self, prompt: str) -> str:
        response = self.process(UserRequest(text=prompt))
        return response.message

    def _generate_response_artifact(
        self,
        plan: TaskPlan,
        request: UserRequest,
        intent: UserIntent,
        artifacts: list[Artifact],
        prompt_text: str,
        trace: PipelineTrace,
    ) -> Artifact | None:
        generation_step = plan.generation_step()

        if not generation_step:
            return None

        return self.plan_executor.execute_step(
            step=generation_step,
            plan=plan,
            request=request,
            intent=intent,
            artifacts=artifacts,
            trace=trace,
            payload={"prompt": prompt_text},
        )

    def _with_seen_state_delta(
        self,
        intent: UserIntent,
        artifacts: list[Artifact],
    ) -> list[Artifact]:
        if intent.name not in {"prepare_task", "test_task_strategy"}:
            return artifacts

        jira_issue = self._artifact_named(artifacts, "jira_issue")

        if not jira_issue:
            return artifacts

        issue = jira_issue.metadata.get("issue")

        if not isinstance(issue, dict):
            return artifacts

        try:
            current = current_jira_issue_state(issue)
        except ValueError:
            return artifacts

        previous = self.seen_state_storage.get(
            source=current.source,
            entity_type=current.entity_type,
            entity_id=current.entity_id,
        )

        if not previous:
            return artifacts

        delta = compare_seen_state(previous, current)

        return [
            *artifacts,
            Artifact(
                name="work_context_delta",
                source="Personal Work Context",
                content=self._delta_content(delta),
                metadata={"delta": delta.to_dict()},
            ),
        ]

    def _delta_content(self, delta: SeenStateDelta) -> str:
        if delta.has_changes:
            return (
                "Personal Seen State delta calculated: "
                f"{len(delta.field_changes)} field changes, "
                f"{len(delta.new_comment_ids)} new comments."
            )

        return "Personal Seen State delta calculated: no changes."

    def _artifact_named(
        self,
        artifacts: list[Artifact],
        name: str,
    ) -> Artifact | None:
        for artifact in artifacts:
            if artifact.name == name:
                return artifact

        return None
