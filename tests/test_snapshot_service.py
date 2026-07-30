import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from app.core.artifacts import Artifact
from app.core.intent import UserIntent
from app.core.task_plan import TaskPlan
from app.services.base import ServiceRequest
from app.services.snapshot import SnapshotService


class SnapshotServiceTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name)
        self.intent = UserIntent(
            name="daily_briefing",
            raw_text="prepare daily",
            expected_output="daily_brief",
            confidence=0.95,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_first_run_saves_snapshot_without_previous(self):
        service = SnapshotService(
            vault_path=str(self.vault),
            now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        )

        artifact = service.execute(
            "snapshot.daily.save",
            self.request_with_issues([self.raw_issue("SCRUM-1", "Login", "To Do")]),
        )

        self.assertTrue(artifact.metadata["success"])
        self.assertIsNone(artifact.metadata["previous_snapshot"])
        self.assertEqual(
            artifact.metadata["current_snapshot"]["assigned_issues"][0]["key"],
            "SCRUM-1",
        )
        self.assertTrue((self.vault / artifact.metadata["path"]).exists())

    def test_repeated_run_loads_previous_snapshot(self):
        first = SnapshotService(
            vault_path=str(self.vault),
            now=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
        )
        first.execute(
            "snapshot.daily.save",
            self.request_with_issues([self.raw_issue("SCRUM-1", "Login", "To Do")]),
        )
        second = SnapshotService(
            vault_path=str(self.vault),
            now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        )

        artifact = second.execute(
            "snapshot.daily.save",
            self.request_with_issues(
                [self.raw_issue("SCRUM-1", "Login", "In Progress")]
            ),
        )

        self.assertIsNotNone(artifact.metadata["previous_snapshot"])
        self.assertEqual(
            artifact.metadata["previous_snapshot"]["assigned_issues"][0]["status"],
            "To Do",
        )
        self.assertEqual(len(second.history()), 2)

    def test_empty_project_snapshot_is_saved(self):
        service = SnapshotService(
            vault_path=str(self.vault),
            now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        )

        artifact = service.execute("snapshot.daily.save", self.request_with_issues([]))

        self.assertEqual(artifact.metadata["current_snapshot"]["project"], "")
        self.assertEqual(artifact.metadata["current_snapshot"]["assigned_issues"], [])

    def test_jira_error_does_not_save_snapshot(self):
        service = SnapshotService(
            vault_path=str(self.vault),
            now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        )

        artifact = service.execute(
            "snapshot.daily.save",
            self.request_with_artifacts(
                [
                    Artifact(
                        name="jira_error",
                        source="Jira Service",
                        content="Jira authentication failed.",
                    )
                ]
            ),
        )

        self.assertEqual(artifact.name, "daily_snapshot_error")
        self.assertFalse(artifact.metadata["success"])
        self.assertFalse(service.snapshot_folder.exists())

    def request_with_issues(self, issues: list[dict]) -> ServiceRequest:
        return self.request_with_artifacts(
            [
                Artifact(
                    name="jira_assigned_issues",
                    source="Jira Service",
                    content=f"Fetched {len(issues)} issues.",
                    metadata={
                        "issues": issues,
                        "user": {"displayName": "Ilya QA"},
                    },
                )
            ]
        )

    def request_with_artifacts(self, artifacts: list[Artifact]) -> ServiceRequest:
        return ServiceRequest(
            user_text="prepare daily",
            intent=self.intent,
            plan=TaskPlan(
                goal="prepare daily",
                intent=self.intent,
                steps=[],
                response_contract="daily_brief",
                context_budget=2000,
            ),
            artifacts=tuple(artifacts),
        )

    def raw_issue(
        self,
        key: str,
        summary: str,
        status: str,
        priority: str = "Medium",
    ) -> dict:
        return {
            "key": key,
            "fields": {
                "summary": summary,
                "status": {
                    "name": status,
                    "statusCategory": {
                        "key": "done" if status == "Done" else "indeterminate",
                    },
                },
                "priority": {"name": priority},
                "assignee": {"displayName": "Ilya QA"},
                "updated": "2026-07-30T08:00:00.000+0000",
                "duedate": "",
                "labels": ["qa"],
                "description": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": summary}],
                        }
                    ],
                },
                "comment": {"total": 2, "comments": []},
                "project": {"key": key.split("-", 1)[0]},
                "customfield_10020": [{"name": "QAOS Sprint 5"}],
            },
        }


if __name__ == "__main__":
    unittest.main()
