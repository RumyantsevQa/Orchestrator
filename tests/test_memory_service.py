import os
import tempfile
import unittest
from pathlib import Path

from app.core.artifacts import Artifact
from app.core.intent import UserIntent
from app.core.task_plan import TaskPlan
from app.services.base import ServiceRequest
from app.services.memory import MemoryService


class MemoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.index_path = self.root / "index.json"

        self.projects = self.vault / "QASkills" / "Memory" / "Projects"
        self.projects.mkdir(parents=True)

        self.alpha = self.projects / "Alpha.md"
        self.beta = self.vault / "Beta.md"

        self.alpha.write_text(
            "\n".join(
                [
                    "---",
                    "aliases:",
                    "  - Alpha Alias",
                    "tags:",
                    "  - QA",
                    "---",
                    "# Alpha",
                    "",
                    "## Planner",
                    "",
                    "Alpha project.",
                ]
            ),
            encoding="utf-8",
        )
        self.beta.write_text("# Beta\n\nBeta document.", encoding="utf-8")

        os.utime(self.alpha, (1000, 1000))
        os.utime(self.beta, (2000, 2000))

        self.service = MemoryService(
            vault_path=str(self.vault),
            index_path=str(self.index_path),
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_list_documents_returns_markdown_metadata(self):
        documents = self.service.list_documents()

        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].title, "Beta")
        self.assertEqual(documents[1].title, "Alpha")
        self.assertTrue(documents[0].path.endswith(".md"))
        self.assertGreater(documents[0].size, 0)

    def test_list_documents_can_filter_projects_scope(self):
        documents = self.service.list_documents(scope="projects")

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].title, "Alpha")

    def test_list_documents_can_filter_tag(self):
        documents = self.service.list_documents(tag="QA")

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].title, "Alpha")

    def test_list_documents_can_filter_heading(self):
        documents = self.service.list_documents(heading="Planner")

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].title, "Alpha")

    def test_read_document_by_path(self):
        document = self.service.read_document_by_path("Beta.md")

        self.assertEqual(document.info.title, "Beta")
        self.assertIn("Beta document.", document.content)

    def test_read_document_by_name(self):
        document = self.service.read_document_by_name("Alpha Alias")

        self.assertEqual(document.info.title, "Alpha")
        self.assertIn("Alpha project.", document.content)

    def test_list_recent_returns_recent_documents_first(self):
        documents = self.service.list_recent(limit=1)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].title, "Beta")

    def test_vault_structure_uses_index(self):
        structure = self.service.vault_structure()

        self.assertEqual(structure["."], 1)
        self.assertEqual(structure["QASkills/Memory/Projects"], 1)

    def test_write_document_saves_note_and_refreshes_index(self):
        document = self.service.write_document(
            title="Daily Decision",
            content="Use QASkills as the daily entrypoint.",
        )

        self.assertEqual(document.title, "Daily Decision")
        self.assertEqual(document.folder, "QASkills/Memory/Inbox")
        self.assertTrue((self.vault / document.path).exists())

        matches = self.service.search("Daily Decision")

        self.assertTrue(matches)
        self.assertEqual(matches[0][1].title, "Daily Decision")

    def test_daily_context_finds_jira_project_questions_and_test_ideas(self):
        note = self.projects / "SCRUM-1 Auth Daily.md"
        note.write_text(
            "\n".join(
                [
                    "---",
                    "tags: [SCRUM, daily]",
                    "---",
                    "# SCRUM-1 Auth Daily",
                    "",
                    "## Open questions",
                    "",
                    "- Clarify refresh token behavior.",
                    "",
                    "## Test ideas",
                    "",
                    "- проверить авторизацию после истечения токена.",
                    "",
                    "## Yesterday conclusions",
                    "",
                    "- Вчера договорились начать с smoke checks.",
                ]
            ),
            encoding="utf-8",
        )
        self.service.rebuild_index()

        artifact = self.service.execute(
            "memory.search",
            self.daily_context_request(
                issue_key="SCRUM-1",
                project="SCRUM",
            ),
        )

        self.assertEqual(artifact.name, "daily_memory_context")
        self.assertEqual(artifact.metadata["document_count"], 1)
        self.assertIn("SCRUM-1", artifact.metadata["issue_keys"])
        self.assertIn("SCRUM", artifact.metadata["projects"])
        self.assertTrue(artifact.metadata["categories"]["jira_keys"])
        self.assertTrue(artifact.metadata["categories"]["projects"])
        self.assertTrue(artifact.metadata["categories"]["open_questions"])
        self.assertTrue(artifact.metadata["categories"]["test_ideas"])
        self.assertIn("Found 1 related Obsidian", artifact.content)

    def daily_context_request(self, issue_key: str, project: str) -> ServiceRequest:
        intent = UserIntent(
            name="daily_briefing",
            raw_text="prepare daily",
            expected_output="daily_brief",
            confidence=0.95,
        )
        snapshot = {
            "timestamp": "2026-07-30T09:00:00+00:00",
            "project": project,
            "assigned_issues": [
                {
                    "key": issue_key,
                    "project": project,
                    "summary": "Authentication",
                }
            ],
        }

        return ServiceRequest(
            user_text="prepare daily",
            intent=intent,
            plan=TaskPlan(
                goal="prepare daily",
                intent=intent,
                steps=[],
                response_contract="daily_brief",
                context_budget=2000,
            ),
            artifacts=(
                Artifact(
                    name="daily_snapshots",
                    source="Snapshot Service",
                    content="Daily snapshot saved.",
                    metadata={
                        "current_snapshot": snapshot,
                        "previous_snapshot": None,
                    },
                ),
                Artifact(
                    name="daily_change_report",
                    source="Change Analysis Service",
                    content="Detected changes.",
                    metadata={
                        "change_report": {
                            "has_history": False,
                            "current_timestamp": snapshot["timestamp"],
                            "new_issues": snapshot["assigned_issues"],
                        }
                    },
                ),
            ),
            payload={"mode": "daily_context", "limit": 5},
        )


if __name__ == "__main__":
    unittest.main()
