import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.artifacts import Artifact, PipelineTrace
from app.core.capabilities import CapabilityRegistry
from app.core.intent import UserIntent
from app.core.models import UserRequest
from app.core.orchestrator import Orchestrator
from app.core.planner import TaskPlanner
from app.core.task_plan import TaskPlan
from app.response.composer import ResponseComposer
from app.work_context import (
    SeenEntityState,
    SeenStateStorage,
    current_jira_issue_state,
)


class ApplicationPipelineTest(unittest.TestCase):
    def setUp(self):
        self._original_vault = os.environ.get("QASKILLS_MEMORY_VAULT_PATH")
        self._original_index = os.environ.get("QASKILLS_DOCUMENT_INDEX_PATH")
        self._original_seen_state = os.environ.get(
            "QASKILLS_PERSONAL_SEEN_STATE_PATH"
        )
        self._original_jira = {
            name: os.environ.get(name)
            for name in ["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]
        }
        self._tempdir = tempfile.TemporaryDirectory()
        vault = Path(self._tempdir.name)
        (vault / "QASkills.md").write_text(
            "\n".join(
                [
                    "---",
                    "tags: [QA]",
                    "---",
                    "# QASkills",
                    "",
                    "## Planner",
                    "",
                    "Project memory document.",
                ]
            ),
            encoding="utf-8",
        )
        (vault / "QASkills" / "Memory" / "Projects").mkdir(parents=True)
        (vault / "QASkills" / "Memory" / "Projects" / "Project A.md").write_text(
            "# Project A\n\nCurrent project.",
            encoding="utf-8",
        )
        (vault / "QASkills" / "Memory" / "Projects" / "SCRUM-7.md").write_text(
            "\n".join(
                [
                    "---",
                    "tags: [qa, scrum]",
                    "---",
                    "# SCRUM-7 Registration",
                    "",
                    "## Test ideas",
                    "",
                    "Check registration, login, and password recovery.",
                ]
            ),
            encoding="utf-8",
        )
        os.environ["QASKILLS_MEMORY_VAULT_PATH"] = str(vault)
        os.environ["QASKILLS_DOCUMENT_INDEX_PATH"] = str(vault / "index.json")
        os.environ["QASKILLS_PERSONAL_SEEN_STATE_PATH"] = str(
            vault / "personal_seen_state.json"
        )
        os.environ["JIRA_URL"] = ""
        os.environ["JIRA_EMAIL"] = ""
        os.environ["JIRA_API_TOKEN"] = ""

    def tearDown(self):
        if self._original_vault is None:
            os.environ.pop("QASKILLS_MEMORY_VAULT_PATH", None)
        else:
            os.environ["QASKILLS_MEMORY_VAULT_PATH"] = self._original_vault

        if self._original_index is None:
            os.environ.pop("QASKILLS_DOCUMENT_INDEX_PATH", None)
        else:
            os.environ["QASKILLS_DOCUMENT_INDEX_PATH"] = self._original_index

        if self._original_seen_state is None:
            os.environ.pop("QASKILLS_PERSONAL_SEEN_STATE_PATH", None)
        else:
            os.environ["QASKILLS_PERSONAL_SEEN_STATE_PATH"] = self._original_seen_state

        for name, value in self._original_jira.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

        self._tempdir.cleanup()

    def test_daily_request_runs_generation_step_when_planned(self):
        response = Orchestrator().process(
            UserRequest(text="Подготовь меня к дейли")
        )

        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertTrue(response.success)
        self.assertIn("Intent Analyzer", components)
        self.assertIn("Task Planner", components)
        self.assertIn("Plan Executor", components)
        self.assertIn("Memory Service", components)
        self.assertIn("Skill Service", components)
        self.assertIn("Context Composer", components)
        self.assertIn("Prompt Builder", components)
        self.assertIn("LLM Service", components)
        self.assertIn("Response Composer", components)

    def test_general_request_finishes_without_llm_pipeline(self):
        response = Orchestrator().process(
            UserRequest(text="Покажи доступные данные")
        )

        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertTrue(response.success)
        self.assertIn("Intent Analyzer", components)
        self.assertIn("Task Planner", components)
        self.assertIn("Plan Executor", components)
        self.assertIn("Memory Service", components)
        self.assertIn("Response Composer", components)
        self.assertNotIn("Context Composer", components)
        self.assertNotIn("Prompt Builder", components)
        self.assertNotIn("LLM Service", components)
        self.assertIsNone(response.data["llm_artifact"])
        self.assertIn("Документы:", response.message)

    def test_planner_uses_available_daily_capabilities(self):
        registry = CapabilityRegistry()
        registry.register(
            name="memory.list_recent",
            description="List recent documents.",
            provider="Memory Service",
        )

        plan = TaskPlanner(registry).plan(
            UserIntent(
                name="daily_preparation",
                raw_text="Подготовь меня к дейли",
                expected_output="daily_briefing",
                confidence=0.9,
            )
        )

        self.assertEqual(
            [step.capability for step in plan.steps],
            ["memory.list_recent"],
        )
        self.assertIn("skill.daily_preparation", plan.missing_capabilities)
        self.assertIn("llm.generate", plan.missing_capabilities)

    def test_planner_does_not_require_llm_for_general_request(self):
        registry = CapabilityRegistry()
        registry.register(
            name="memory.list_documents",
            description="List documents.",
            provider="Memory Service",
        )

        plan = TaskPlanner(registry).plan(
            UserIntent(
                name="general_request",
                raw_text="Покажи доступные данные",
                expected_output="answer",
                confidence=0.6,
            )
        )

        self.assertFalse(plan.needs_generation())
        self.assertNotIn("llm.generate", plan.missing_capabilities)

    def test_planner_builds_daily_brief_without_llm(self):
        registry = CapabilityRegistry()
        registry.register(
            name="jira.list_assigned_issues",
            description="List assigned Jira issues.",
            provider="Jira Service",
        )
        registry.register(
            name="daily.prepare",
            description="Prepare daily briefing.",
            provider="Daily Brief Service",
        )
        registry.register(
            name="snapshot.daily.save",
            description="Save daily snapshot.",
            provider="Snapshot Service",
        )
        registry.register(
            name="change.daily.analyze",
            description="Analyze daily changes.",
            provider="Change Analysis Service",
        )

        plan = TaskPlanner(registry).plan(
            UserIntent(
                name="daily_briefing",
                raw_text="prepare daily",
                expected_output="daily_brief",
                confidence=0.95,
            )
        )

        self.assertEqual(
            [step.capability for step in plan.steps],
            [
                "jira.list_assigned_issues",
                "snapshot.daily.save",
                "change.daily.analyze",
                "daily.prepare",
            ],
        )
        self.assertFalse(plan.needs_generation())
        self.assertNotIn("llm.generate", plan.missing_capabilities)

    def test_planner_enriches_daily_brief_with_memory_when_available(self):
        registry = CapabilityRegistry()

        for capability, provider in [
            ("jira.list_assigned_issues", "Jira Service"),
            ("snapshot.daily.save", "Snapshot Service"),
            ("change.daily.analyze", "Change Analysis Service"),
            ("memory.search", "Memory Service"),
            ("daily.prepare", "Daily Brief Service"),
        ]:
            registry.register(
                name=capability,
                description=capability,
                provider=provider,
            )

        plan = TaskPlanner(registry).plan(
            UserIntent(
                name="daily_briefing",
                raw_text="prepare daily",
                expected_output="daily_brief",
                confidence=0.95,
            )
        )

        self.assertEqual(
            [step.capability for step in plan.steps],
            [
                "jira.list_assigned_issues",
                "snapshot.daily.save",
                "change.daily.analyze",
                "memory.search",
                "daily.prepare",
            ],
        )
        self.assertEqual(plan.steps[3].parameters["mode"], "daily_context")
        self.assertFalse(plan.needs_generation())

    def test_prepare_task_uses_jira_memory_and_skill_without_llm(self):
        registry = CapabilityRegistry()

        for capability, provider in [
            ("jira.get_issue", "Jira Service"),
            ("memory.search", "Memory Service"),
            ("skill.analyze_feature", "Skill Service"),
        ]:
            registry.register(
                name=capability,
                description=capability,
                provider=provider,
            )

        plan = TaskPlanner(registry).plan(
            UserIntent(
                name="prepare_task",
                raw_text="Подготовь меня к SCRUM-7",
                expected_output="task_preparation",
                confidence=0.9,
                metadata={"issue_key": "SCRUM-7", "query": "SCRUM-7"},
            )
        )

        self.assertEqual(
            [step.capability for step in plan.steps],
            ["jira.get_issue", "memory.search", "skill.analyze_feature"],
        )
        self.assertFalse(plan.needs_generation())

    def test_test_task_strategy_uses_jira_memory_and_skill_without_llm(self):
        registry = CapabilityRegistry()

        for capability, provider in [
            ("jira.get_issue", "Jira Service"),
            ("memory.search", "Memory Service"),
            ("skill.analyze_feature", "Skill Service"),
        ]:
            registry.register(
                name=capability,
                description=capability,
                provider=provider,
            )

        plan = TaskPlanner(registry).plan(
            UserIntent(
                name="test_task_strategy",
                raw_text="Помоги протестировать SCRUM-7",
                expected_output="test_strategy",
                confidence=0.9,
                metadata={"issue_key": "SCRUM-7", "query": "SCRUM-7"},
            )
        )

        self.assertEqual(
            [step.capability for step in plan.steps],
            ["jira.get_issue", "memory.search", "skill.analyze_feature"],
        )
        self.assertFalse(plan.needs_generation())

    def test_natural_language_prepare_task_returns_calm_report(self):
        response = Orchestrator().process(
            UserRequest(text="Подготовь меня к SCRUM-7")
        )
        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertTrue(response.success)
        self.assertEqual(response.data["intent"]["name"], "prepare_task")
        self.assertIn("Jira Service", components)
        self.assertIn("Memory Service", components)
        self.assertIn("Skill Service", components)
        self.assertNotIn("LLM Service", components)
        self.assertIn("Я подготовил задачу SCRUM-7.", response.message)
        self.assertIn("Главное", response.message)
        self.assertIn("На что обратить внимание", response.message)
        self.assertIn("Что мешает начать", response.message)
        self.assertIn("Facts", response.message)
        self.assertIn("Inferences", response.message)
        self.assertIn("Recommendations", response.message)
        self.assertIn("Следующий лучший шаг", response.message)
        self.assertIn("Я ничего не сохранял", response.message)
        self.assertIn("SCRUM-7 Registration", response.message)
        self.assertNotIn("Reporter", response.message)
        self.assertNotIn("Assignee", response.message)
        self.assertFalse(
            any(
                artifact["name"] == "work_context_delta"
                for artifact in response.data["artifacts"]
            )
        )

    @patch("app.services.jira.JiraService._live_issue")
    def test_prepare_task_without_seen_state_keeps_alpha_02_artifacts(
        self,
        live_issue,
    ):
        live_issue.return_value = Artifact(
            name="jira_issue",
            source="Jira Service",
            content="Jira Issue SCRUM-7",
            metadata={"issue": self._jira_issue(status="Ready for QA")},
        )

        response = Orchestrator().process(
            UserRequest(text="Подготовь меня к SCRUM-7")
        )

        self.assertTrue(response.success)
        self.assertIn("Я подготовил задачу SCRUM-7.", response.message)
        self.assertFalse(
            any(
                artifact["name"] == "work_context_delta"
                for artifact in response.data["artifacts"]
            )
        )
        self.assertFalse(
            Path(os.environ["QASKILLS_PERSONAL_SEEN_STATE_PATH"]).exists()
        )

    @patch("app.services.jira.JiraService._live_issue")
    def test_prepare_task_reads_seen_state_and_adds_delta_artifact(
        self,
        live_issue,
    ):
        state_path = Path(os.environ["QASKILLS_PERSONAL_SEEN_STATE_PATH"])
        previously_seen = current_jira_issue_state(
            self._jira_issue(
                status="In Progress",
                priority="Medium",
                comments=[
                    {
                        "id": "10001",
                        "author": "Developer",
                        "created": "2026-07-31T08:00:00+03:00",
                        "updated": "2026-07-31T08:00:00+03:00",
                        "body": "Initial clarification.",
                    }
                ],
            )
        )
        SeenStateStorage(state_path).upsert(
            SeenEntityState(
                source=previously_seen.source,
                entity_type=previously_seen.entity_type,
                entity_id=previously_seen.entity_id,
                last_seen_at="2026-07-31T08:30:00+03:00",
                source_updated_at=previously_seen.source_updated_at,
                status_seen=previously_seen.status,
                priority_seen=previously_seen.priority,
                summary_fingerprint=previously_seen.summary_fingerprint,
                description_fingerprint=previously_seen.description_fingerprint,
                links_fingerprint=previously_seen.links_fingerprint,
                comments_seen=previously_seen.comment_ids,
                last_workflow="prepare_task",
            )
        )
        persisted_before = state_path.read_text(encoding="utf-8")
        live_issue.return_value = Artifact(
            name="jira_issue",
            source="Jira Service",
            content="Jira Issue SCRUM-7",
            metadata={
                "issue": self._jira_issue(
                    status="Ready for QA",
                    priority="High",
                    comments=[
                        {
                            "id": "10001",
                            "author": "Developer",
                            "created": "2026-07-31T08:00:00+03:00",
                            "updated": "2026-07-31T08:00:00+03:00",
                            "body": "Initial clarification.",
                        },
                        {
                            "id": "10002",
                            "author": "Developer",
                            "created": "2026-07-31T09:00:00+03:00",
                            "updated": "2026-07-31T09:00:00+03:00",
                            "body": "Moved to Ready for QA.",
                        },
                    ],
                )
            },
        )

        response = Orchestrator().process(
            UserRequest(text="Подготовь меня к SCRUM-7")
        )
        delta_artifacts = [
            artifact
            for artifact in response.data["artifacts"]
            if artifact["name"] == "work_context_delta"
        ]

        self.assertEqual(len(delta_artifacts), 1)
        delta = delta_artifacts[0]["metadata"]["delta"]
        self.assertTrue(delta["has_previous"])
        self.assertTrue(delta["has_changes"])
        self.assertEqual(delta["new_comment_ids"], ["10002"])
        self.assertEqual(
            {
                change["field"]
                for change in delta["field_changes"]
            },
            {"status", "priority"},
        )
        self.assertEqual(
            state_path.read_text(encoding="utf-8"),
            persisted_before,
        )
        self.assertIn("Я подготовил задачу SCRUM-7.", response.message)

    @patch("app.services.jira.JiraService._live_issue")
    def test_work_context_delta_keeps_prepare_task_response_byte_for_byte(
        self,
        live_issue,
    ):
        current_issue = self._jira_issue(
            status="Ready for QA",
            priority="High",
            comments=[
                {
                    "id": "10001",
                    "author": "Developer",
                    "created": "2026-07-31T08:00:00+03:00",
                    "updated": "2026-07-31T08:00:00+03:00",
                    "body": "Initial clarification.",
                },
                {
                    "id": "10002",
                    "author": "Developer",
                    "created": "2026-07-31T09:00:00+03:00",
                    "updated": "2026-07-31T09:00:00+03:00",
                    "body": "Moved to Ready for QA.",
                },
            ],
        )
        live_issue.return_value = Artifact(
            name="jira_issue",
            source="Jira Service",
            content="Jira Issue SCRUM-7",
            metadata={"issue": current_issue},
        )

        response_without_delta = Orchestrator().process(
            UserRequest(text="Подготовь меня к SCRUM-7")
        )
        self.assertFalse(
            any(
                artifact["name"] == "work_context_delta"
                for artifact in response_without_delta.data["artifacts"]
            )
        )

        state_path = Path(os.environ["QASKILLS_PERSONAL_SEEN_STATE_PATH"])
        previously_seen = current_jira_issue_state(
            self._jira_issue(
                status="In Progress",
                priority="Medium",
                comments=[
                    {
                        "id": "10001",
                        "author": "Developer",
                        "created": "2026-07-31T08:00:00+03:00",
                        "updated": "2026-07-31T08:00:00+03:00",
                        "body": "Initial clarification.",
                    }
                ],
            )
        )
        SeenStateStorage(state_path).upsert(
            SeenEntityState(
                source=previously_seen.source,
                entity_type=previously_seen.entity_type,
                entity_id=previously_seen.entity_id,
                last_seen_at="2026-07-31T08:30:00+03:00",
                source_updated_at=previously_seen.source_updated_at,
                status_seen=previously_seen.status,
                priority_seen=previously_seen.priority,
                summary_fingerprint=previously_seen.summary_fingerprint,
                description_fingerprint=previously_seen.description_fingerprint,
                links_fingerprint=previously_seen.links_fingerprint,
                comments_seen=previously_seen.comment_ids,
                last_workflow="prepare_task",
            )
        )

        response_with_delta = Orchestrator().process(
            UserRequest(text="Подготовь меня к SCRUM-7")
        )
        self.assertTrue(
            any(
                artifact["name"] == "work_context_delta"
                for artifact in response_with_delta.data["artifacts"]
            )
        )
        self.assertEqual(
            response_without_delta.message,
            response_with_delta.message,
        )

    def test_natural_language_test_task_returns_strategy_without_llm(self):
        response = Orchestrator().process(
            UserRequest(text="Помоги протестировать SCRUM-7")
        )
        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertTrue(response.success)
        self.assertEqual(response.data["intent"]["name"], "test_task_strategy")
        self.assertIn("Jira Service", components)
        self.assertIn("Memory Service", components)
        self.assertIn("Skill Service", components)
        self.assertNotIn("LLM Service", components)
        self.assertIn(
            "Продолжаю по SCRUM-7: стратегия тестирования.",
            response.message,
        )
        self.assertIn("Что проверить в первую очередь", response.message)
        self.assertIn("Основные пользовательские сценарии", response.message)
        self.assertIn("Негативные проверки", response.message)
        self.assertIn("Граничные случаи", response.message)
        self.assertIn("Возможные регрессии", response.message)
        self.assertIn("Что пока неизвестно", response.message)
        self.assertIn("SCRUM-7 Registration", response.message)

    def test_test_strategy_interprets_jira_and_memory_context(self):
        intent = UserIntent(
            name="test_task_strategy",
            raw_text="Помоги протестировать SCRUM-7",
            expected_output="test_strategy",
            confidence=0.9,
            metadata={"issue_key": "SCRUM-7"},
        )
        plan = TaskPlan(
            goal=intent.raw_text,
            intent=intent,
            steps=[],
            response_contract="test_strategy",
            context_budget=2000,
        )
        issue = {
            "key": "SCRUM-7",
            "summary": "Registration with email confirmation",
            "status": "In Progress",
            "priority": "High",
            "description": (
                "User registration flow. "
                "Acceptance Criteria: email confirmation is required."
            ),
            "comments": [
                {
                    "author": "Developer",
                    "created": "2026-07-31",
                    "body": "Changed email confirmation order after registration.",
                }
            ],
            "links": [],
        }
        document = {
            "title": "SCRUM-7 Registration",
            "path": "Projects/SCRUM-7.md",
            "tags": ["qa"],
            "headings": ["Test ideas"],
        }
        artifacts = [
            Artifact(
                name="jira_issue",
                source="Jira Service",
                content="",
                metadata={"issue": issue},
            ),
            Artifact(
                name="memory_search_results",
                source="Memory Service",
                content="",
                metadata={
                    "results": [
                        {
                            "score": 10,
                            "reasons": ["title"],
                            "document": document,
                        }
                    ]
                },
            ),
            Artifact(
                name="skill_guidance",
                source="Skill Service",
                content="",
                metadata={},
            ),
        ]

        message = ResponseComposer().compose(
            request=UserRequest(text="Помоги протестировать SCRUM-7"),
            intent=intent,
            plan=plan,
            artifacts=artifacts,
            llm_artifact=None,
            trace=PipelineTrace(),
        ).message

        self.assertIn("регистрация", message)
        self.assertIn("подтверждение email", message)
        self.assertIn("последнего комментария", message)
        self.assertIn("Попытка регистрации с уже занятым email", message)
        self.assertIn("Это не полный чек-лист", message)
        self.assertIn("QA guidance: анализ функциональности и рисков.", message)
        self.assertNotIn("Feature Analysis Skill", message)

    def test_test_strategy_uses_safe_excerpt_when_comment_meaning_is_unknown(self):
        intent = UserIntent(
            name="test_task_strategy",
            raw_text="Помоги протестировать SCRUM-7",
            expected_output="test_strategy",
            confidence=0.9,
            metadata={"issue_key": "SCRUM-7"},
        )
        plan = TaskPlan(
            goal=intent.raw_text,
            intent=intent,
            steps=[],
            response_contract="test_strategy",
            context_budget=2000,
        )
        issue = {
            "key": "SCRUM-7",
            "summary": "Task update",
            "status": "In Progress",
            "priority": "Medium",
            "description": "Acceptance Criteria: updated behavior is required.",
            "comments": [
                {
                    "author": "Developer",
                    "created": "2026-07-31",
                    "body": "Please check the updated flow at https://example.test with qa@example.test.",
                }
            ],
            "links": [],
        }
        artifacts = [
            Artifact(
                name="jira_issue",
                source="Jira Service",
                content="",
                metadata={"issue": issue},
            ),
            Artifact(
                name="memory_search_results",
                source="Memory Service",
                content="",
                metadata={"results": []},
            ),
        ]

        message = ResponseComposer().compose(
            request=UserRequest(text="Помоги протестировать SCRUM-7"),
            intent=intent,
            plan=plan,
            artifacts=artifacts,
            llm_artifact=None,
            trace=PipelineTrace(),
        ).message

        self.assertIn("Сначала проверить последний комментарий", message)
        self.assertIn("[link]", message)
        self.assertIn("[email]", message)
        self.assertNotIn("https://example.test", message)
        self.assertNotIn("qa@example.test", message)

    def test_open_document_finishes_without_llm(self):
        response = Orchestrator().process(
            UserRequest(text="Открой документ QASkills")
        )

        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertIn("Memory Service", components)
        self.assertNotIn("LLM Service", components)
        self.assertIn("Документ: QASkills", response.message)
        self.assertIn("Project memory document.", response.message)

    def test_vault_structure_finishes_without_llm(self):
        hidden_folder = Path(os.environ["QASKILLS_MEMORY_VAULT_PATH"]) / ".venv"
        hidden_folder.mkdir()
        (hidden_folder / "Hidden.md").write_text("# Hidden", encoding="utf-8")

        response = Orchestrator().process(
            UserRequest(text="Покажи структуру Vault")
        )

        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertNotIn("LLM Service", components)
        self.assertIn("Структура Vault", response.message)
        self.assertNotIn(".venv", response.message)

    def test_named_project_documents_finish_without_llm(self):
        response = Orchestrator().process(
            UserRequest(text="Покажи документы проекта QASkills")
        )

        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertNotIn("LLM Service", components)
        self.assertIn("Документы проекта QASkills", response.message)
        self.assertIn("Project A", response.message)

    def test_tag_and_heading_filters_finish_without_llm(self):
        tag_response = Orchestrator().process(
            UserRequest(text="Покажи документы с тегом QA")
        )
        heading_response = Orchestrator().process(
            UserRequest(text="Покажи документы, где есть заголовок Planner")
        )

        self.assertIn("Документы с тегом QA", tag_response.message)
        self.assertIn("QASkills", tag_response.message)
        self.assertIn("Документы с заголовком Planner", heading_response.message)
        self.assertIn("QASkills", heading_response.message)

    def test_jira_task_analysis_uses_existing_pipeline(self):
        response = Orchestrator().process(
            UserRequest(text="jira анализ задачи SCRUM-42")
        )

        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertTrue(response.success)
        self.assertIn("Memory Service", components)
        self.assertIn("Skill Service", components)
        self.assertIn("Jira Service", components)
        self.assertIn("LLM Service", components)
        self.assertTrue(
            any(
                artifact["name"] == "jira_issue_analysis"
                for artifact in response.data["artifacts"]
            )
        )

    def test_memory_update_intent_saves_without_llm(self):
        response = Orchestrator().process(
            UserRequest(text="Запомни это: Daily note for QA Alpha")
        )

        components = [
            event["component"]
            for event in response.data["pipeline"]
        ]

        self.assertTrue(response.success)
        self.assertIn("Memory Service", components)
        self.assertNotIn("LLM Service", components)
        self.assertIn("Saved note", response.message)

    def _jira_issue(
        self,
        status: str = "In Progress",
        priority: str = "High",
        comments: list[dict[str, str]] | None = None,
    ) -> dict:
        return {
            "key": "SCRUM-7",
            "summary": "Registration with email confirmation",
            "updated": "2026-07-31T09:00:00+03:00",
            "status": status,
            "assignee": "QA Engineer",
            "priority": priority,
            "reporter": "Product Owner",
            "description": (
                "User registration flow. "
                "Acceptance Criteria: email confirmation is required."
            ),
            "comments": list(comments or []),
            "links": [],
        }


if __name__ == "__main__":
    unittest.main()
