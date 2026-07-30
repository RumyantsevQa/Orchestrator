from app.core.artifacts import PipelineTrace
from app.core.capabilities import CapabilityRegistry
from app.core.intent import UserIntent
from app.core.task_plan import PlanStep, TaskPlan


class TaskPlanner:
    """
    Builds an executable task plan from an intent and available capabilities.

    The planner never calls services directly. It only reasons about named
    capabilities registered by the service layer.
    """

    def __init__(self, capabilities: CapabilityRegistry):
        self.capabilities = capabilities

    def plan(
        self,
        intent: UserIntent,
        trace: PipelineTrace | None = None,
    ) -> TaskPlan:
        if trace:
            trace.add("Task Planner", "Built task plan from available capabilities")

        desired_steps = self._desired_steps(intent)
        steps = [
            step
            for step in desired_steps
            if self.capabilities.has(step.capability)
        ]
        missing = [
            step.capability
            for step in desired_steps
            if not self.capabilities.has(step.capability)
        ]

        return TaskPlan(
            goal=intent.raw_text,
            intent=intent,
            steps=steps,
            response_contract=intent.expected_output,
            context_budget=2000,
            missing_capabilities=missing,
        )

    def _desired_steps(self, intent: UserIntent) -> list[PlanStep]:
        if intent.name == "knowledge_update":
            return [
                PlanStep(
                    id="save_memory_note",
                    component="Memory Service",
                    capability="memory.write_document",
                    phase="collect",
                    description="Save a user-approved note to memory.",
                    parameters={
                        "title": intent.metadata.get("title", ""),
                        "content": intent.metadata.get("content", ""),
                    },
                )
            ]

        if intent.name == "task_analysis":
            return [
                self._memory_search_step(intent, "search_memory_for_task_analysis"),
                PlanStep(
                    id="apply_feature_analysis_skill",
                    component="Skill Service",
                    capability="skill.analyze_feature",
                    phase="collect",
                    description="Apply feature analysis guidance.",
                ),
                self._generation_step(),
            ]

        if intent.name == "meeting_analysis":
            return [
                self._memory_search_step(intent, "search_memory_for_meeting_analysis"),
                PlanStep(
                    id="apply_meeting_analysis_skill",
                    component="Skill Service",
                    capability="skill.analyze_meeting",
                    phase="collect",
                    description="Apply meeting analysis guidance.",
                ),
                self._generation_step(),
            ]

        if intent.name == "jira_list_my_tasks":
            return [
                self._memory_search_step(intent, "search_memory_for_jira_tasks"),
                PlanStep(
                    id="list_jira_tasks",
                    component="Jira Service",
                    capability="jira.list_my_tasks",
                    phase="collect",
                    description="List Jira tasks through the Jira workspace boundary.",
                ),
            ]

        if intent.name == "jira_whoami":
            return [
                PlanStep(
                    id="jira_whoami",
                    component="Jira Service",
                    capability="jira.whoami",
                    phase="collect",
                    description="Show the authenticated Jira user.",
                )
            ]

        if intent.name == "jira_list_projects":
            return [
                PlanStep(
                    id="list_jira_projects",
                    component="Jira Service",
                    capability="jira.list_projects",
                    phase="collect",
                    description="List Jira projects visible to the authenticated user.",
                )
            ]

        if intent.name == "jira_get_issue":
            return [
                PlanStep(
                    id="get_jira_issue",
                    component="Jira Service",
                    capability="jira.get_issue",
                    phase="collect",
                    description="Read a Jira issue from Jira Cloud.",
                    parameters={"issue_key": intent.metadata.get("issue_key", "")},
                )
            ]

        if intent.name == "jira_find_issue":
            return [
                self._memory_search_step(intent, "search_memory_for_jira_issue"),
                PlanStep(
                    id="find_jira_issue",
                    component="Jira Service",
                    capability="jira.find_issue",
                    phase="collect",
                    description="Find a Jira issue by key.",
                    parameters={"issue_key": intent.metadata.get("issue_key", "")},
                ),
            ]

        if intent.name == "jira_analyze_issue":
            return [
                self._memory_search_step(intent, "search_memory_for_jira_analysis"),
                PlanStep(
                    id="apply_feature_analysis_skill",
                    component="Skill Service",
                    capability="skill.analyze_feature",
                    phase="collect",
                    description="Apply feature analysis guidance.",
                ),
                PlanStep(
                    id="analyze_jira_issue",
                    component="Jira Service",
                    capability="jira.analyze_issue",
                    phase="collect",
                    description="Prepare Jira issue QA analysis.",
                    parameters={"issue_key": intent.metadata.get("issue_key", "")},
                ),
                self._generation_step(),
            ]

        if intent.name == "jira_bug_report":
            return [
                self._memory_search_step(intent, "search_memory_for_bug_report"),
                PlanStep(
                    id="apply_bug_report_skill",
                    component="Skill Service",
                    capability="skill.bug_report",
                    phase="collect",
                    description="Apply bug report guidance.",
                ),
                PlanStep(
                    id="prepare_bug_report_template",
                    component="Jira Service",
                    capability="jira.create_bug_report_template",
                    phase="collect",
                    description="Prepare a bug report draft.",
                    parameters={"issue_key": intent.metadata.get("issue_key", "")},
                ),
                self._generation_step(),
            ]

        if intent.name == "jira_daily_issue":
            return [
                self._memory_search_step(intent, "search_memory_for_jira_daily"),
                PlanStep(
                    id="apply_daily_skill",
                    component="Skill Service",
                    capability="skill.daily_preparation",
                    phase="collect",
                    description="Apply daily preparation guidance.",
                ),
                PlanStep(
                    id="prepare_jira_daily_context",
                    component="Jira Service",
                    capability="jira.prepare_daily_for_issue",
                    phase="collect",
                    description="Prepare daily context for a Jira issue.",
                    parameters={"issue_key": intent.metadata.get("issue_key", "")},
                ),
                self._generation_step(),
            ]

        if intent.name == "memory_list_projects":
            return [
                PlanStep(
                    id="list_project_documents",
                    component="Memory Service",
                    capability="memory.list_documents",
                    phase="collect",
                    description="List project memory documents.",
                    parameters={"scope": intent.metadata.get("scope", "projects")},
                )
            ]

        if intent.name == "memory_list_project_documents":
            return [
                PlanStep(
                    id="list_named_project_documents",
                    component="Memory Service",
                    capability="memory.list_documents",
                    phase="collect",
                    description="List documents for a named project.",
                    parameters={
                        "scope": "projects",
                        "project_name": intent.metadata.get("project_name", ""),
                    },
                )
            ]

        if intent.name == "memory_list_tagged_documents":
            return [
                PlanStep(
                    id="list_tagged_documents",
                    component="Memory Service",
                    capability="memory.list_documents",
                    phase="collect",
                    description="List documents by indexed tag.",
                    parameters={"tag": intent.metadata.get("tag", "")},
                )
            ]

        if intent.name == "memory_list_heading_documents":
            return [
                PlanStep(
                    id="list_heading_documents",
                    component="Memory Service",
                    capability="memory.list_documents",
                    phase="collect",
                    description="List documents by indexed heading.",
                    parameters={"heading": intent.metadata.get("heading", "")},
                )
            ]

        if intent.name == "memory_vault_structure":
            return [
                PlanStep(
                    id="show_vault_structure",
                    component="Memory Service",
                    capability="memory.vault_structure",
                    phase="collect",
                    description="Show indexed vault folder structure.",
                )
            ]

        if intent.name == "memory_list_recent":
            return [
                PlanStep(
                    id="list_recent_documents",
                    component="Memory Service",
                    capability="memory.list_recent",
                    phase="collect",
                    description="List recently modified memory documents.",
                    parameters={"limit": 10},
                )
            ]

        if intent.name == "memory_read_document":
            return [
                PlanStep(
                    id="read_memory_document",
                    component="Memory Service",
                    capability="memory.read_document",
                    phase="collect",
                    description="Read a memory document by name.",
                    parameters={"name": intent.metadata.get("document_name", "")},
                )
            ]

        if intent.name == "memory_search":
            return [
                PlanStep(
                    id="search_memory",
                    component="Memory Service",
                    capability="memory.search",
                    phase="collect",
                    description="Search indexed memory metadata.",
                    parameters={
                        "query": intent.metadata.get("query", intent.raw_text),
                        "limit": 5,
                    },
                )
            ]

        if intent.name == "knowledge_question":
            return [
                PlanStep(
                    id="search_memory_for_question",
                    component="Memory Service",
                    capability="memory.search",
                    phase="collect",
                    description="Find source documents for the question.",
                    parameters={
                        "query": intent.metadata.get("query", intent.raw_text),
                        "limit": 5,
                    },
                ),
                PlanStep(
                    id="generate_response",
                    component="LLM Service",
                    capability="llm.generate",
                    phase="generate",
                    description="Generate the final user-facing answer.",
                ),
            ]

        if intent.name == "daily_preparation":
            return [
                PlanStep(
                    id="list_recent_memory_documents",
                    component="Memory Service",
                    capability="memory.list_recent",
                    phase="collect",
                    description="Collect recent memory documents for daily preparation.",
                    parameters={"limit": 5},
                ),
                PlanStep(
                    id="apply_daily_skill",
                    component="Skill Service",
                    capability="skill.daily_preparation",
                    phase="collect",
                    description="Apply daily preparation guidance.",
                ),
                PlanStep(
                    id="generate_response",
                    component="LLM Service",
                    capability="llm.generate",
                    phase="generate",
                    description="Generate the final user-facing answer.",
                ),
            ]

        if intent.name == "daily_briefing":
            return [
                PlanStep(
                    id="collect_assigned_jira_issues",
                    component="Jira Service",
                    capability="jira.list_assigned_issues",
                    phase="collect",
                    description="Collect raw Jira issues assigned to the user.",
                    parameters={"max_results": 25},
                ),
                PlanStep(
                    id="save_daily_snapshot",
                    component="Snapshot Service",
                    capability="snapshot.daily.save",
                    phase="collect",
                    description="Save current Jira state and load previous snapshot.",
                ),
                PlanStep(
                    id="analyze_daily_changes",
                    component="Change Analysis Service",
                    capability="change.daily.analyze",
                    phase="collect",
                    description="Compare previous and current daily snapshots.",
                ),
                PlanStep(
                    id="search_daily_memory_context",
                    component="Memory Service",
                    capability="memory.search",
                    phase="collect",
                    description="Find Obsidian knowledge related to today's Jira changes.",
                    parameters={
                        "mode": "daily_context",
                        "limit": 12,
                    },
                ),
                PlanStep(
                    id="prepare_daily_brief",
                    component="Daily Brief Service",
                    capability="daily.prepare",
                    phase="collect",
                    description="Build the analytical daily briefing from snapshots.",
                ),
            ]

        steps = [
            PlanStep(
                id="list_memory_documents",
                component="Memory Service",
                capability="memory.list_documents",
                phase="collect",
                description="List memory documents.",
            ),
        ]

        return steps

    def _memory_search_step(self, intent: UserIntent, step_id: str) -> PlanStep:
        return PlanStep(
            id=step_id,
            component="Memory Service",
            capability="memory.search",
            phase="collect",
            description="Find local knowledge before continuing the workflow.",
            parameters={
                "query": intent.metadata.get("query", intent.raw_text),
                "limit": 5,
            },
        )

    def _generation_step(self) -> PlanStep:
        return PlanStep(
            id="generate_response",
            component="LLM Service",
            capability="llm.generate",
            phase="generate",
            description="Generate the final user-facing answer.",
        )
