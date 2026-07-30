import os
import tempfile
import unittest
from pathlib import Path

from app.core.capabilities import CapabilityRegistry
from app.core.intent import UserIntent
from app.core.models import UserRequest
from app.core.orchestrator import Orchestrator
from app.core.planner import TaskPlanner


class ApplicationPipelineTest(unittest.TestCase):
    def setUp(self):
        self._original_vault = os.environ.get("QASKILLS_MEMORY_VAULT_PATH")
        self._original_index = os.environ.get("QASKILLS_DOCUMENT_INDEX_PATH")
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
        os.environ["QASKILLS_MEMORY_VAULT_PATH"] = str(vault)
        os.environ["QASKILLS_DOCUMENT_INDEX_PATH"] = str(vault / "index.json")

    def tearDown(self):
        if self._original_vault is None:
            os.environ.pop("QASKILLS_MEMORY_VAULT_PATH", None)
        else:
            os.environ["QASKILLS_MEMORY_VAULT_PATH"] = self._original_vault

        if self._original_index is None:
            os.environ.pop("QASKILLS_DOCUMENT_INDEX_PATH", None)
        else:
            os.environ["QASKILLS_DOCUMENT_INDEX_PATH"] = self._original_index

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


if __name__ == "__main__":
    unittest.main()
