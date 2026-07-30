import unittest
from datetime import UTC, datetime

from app.core.artifacts import Artifact
from app.core.intent import UserIntent
from app.core.task_plan import TaskPlan
from app.services.base import ServiceRequest
from app.services.daily_brief import DailyBriefService
from app.services.daily_models import ChangeReport, DailyIssueSnapshot, DailySnapshot


class DailyBriefServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = DailyBriefService(
            now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
        )

    def test_first_run_reports_insufficient_history(self):
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[self.issue("SCRUM-1", "Authentication", "In Progress")],
        )
        report = ChangeReport(
            has_history=False,
            current_timestamp=current.timestamp,
        )

        artifact = self.service.execute(
            "daily.prepare",
            self.request(current=current, previous=None, report=report),
        )

        self.assertTrue(artifact.metadata["success"])
        self.assertIn("Insufficient historical data", artifact.content)
        self.assertNotIn("Yesterday:", artifact.content)
        self.assertIn("QASkills will start detecting changes", artifact.content)

    def test_repeated_run_uses_difference_report(self):
        previous = DailySnapshot(
            timestamp="2026-07-29T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[self.issue("SCRUM-1", "Authentication", "To Do")],
        )
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[
                self.issue("SCRUM-1", "Authentication", "In Progress"),
                self.issue("SCRUM-2", "Regression", "To Do"),
            ],
        )
        report = ChangeReport(
            has_history=True,
            current_timestamp=current.timestamp,
            previous_timestamp=previous.timestamp,
            new_issues=[current.assigned_issues[1]],
            status_changes=[
                self.change("SCRUM-1", "Authentication", "status", "To Do", "In Progress")
            ],
        )

        artifact = self.service.execute(
            "daily.prepare",
            self.request(current=current, previous=previous, report=report),
        )

        self.assertIn("Compared with: 2026-07-29", artifact.content)
        self.assertIn("SCRUM-1 moved from To Do to In Progress", artifact.content)
        self.assertIn("New assignment SCRUM-2", artifact.content)
        self.assertIn("Suggested Daily Report", artifact.content)

    def test_daily_brief_includes_obsidian_knowledge_sources(self):
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[self.issue("SCRUM-1", "Authentication", "In Progress")],
        )
        report = ChangeReport(
            has_history=False,
            current_timestamp=current.timestamp,
        )
        artifact = self.service.execute(
            "daily.prepare",
            self.request_with_artifacts(
                [
                    *self.daily_artifacts(current=current, previous=None, report=report),
                    Artifact(
                        name="daily_memory_context",
                        source="Memory Service",
                        content="Found 1 related Obsidian knowledge source.",
                        metadata={
                            "document_count": 1,
                            "categories": {
                                "jira_keys": [
                                    {
                                        "title": "SCRUM-1 Auth Daily",
                                        "path": "QASkills/Memory/Projects/SCRUM-1 Auth Daily.md",
                                        "matched_terms": ["SCRUM-1"],
                                        "snippets": ["# SCRUM-1 Auth Daily"],
                                    }
                                ],
                                "projects": [],
                                "open_questions": [
                                    {
                                        "title": "SCRUM-1 Auth Daily",
                                        "path": "QASkills/Memory/Projects/SCRUM-1 Auth Daily.md",
                                        "matched_terms": ["open questions"],
                                        "snippets": ["## Open questions"],
                                    }
                                ],
                                "yesterday_conclusions": [],
                                "test_ideas": [],
                            },
                        },
                    ),
                ]
            ),
        )

        self.assertEqual(artifact.metadata["knowledge_source_count"], 1)
        self.assertIn("Obsidian Knowledge", artifact.content)
        self.assertIn("Linked Jira notes", artifact.content)
        self.assertIn("SCRUM-1 Auth Daily", artifact.content)
        self.assertIn("Evidence: # SCRUM-1 Auth Daily", artifact.content)

    def test_daily_brief_reports_missing_obsidian_knowledge(self):
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[self.issue("SCRUM-1", "Authentication", "In Progress")],
        )
        report = ChangeReport(
            has_history=False,
            current_timestamp=current.timestamp,
        )
        artifact = self.service.execute(
            "daily.prepare",
            self.request_with_artifacts(
                [
                    *self.daily_artifacts(current=current, previous=None, report=report),
                    Artifact(
                        name="daily_memory_context",
                        source="Memory Service",
                        content="No related Obsidian knowledge found.",
                        metadata={"document_count": 0, "categories": {}},
                    ),
                ]
            ),
        )

        self.assertEqual(artifact.metadata["knowledge_source_count"], 0)
        self.assertIn("No related Obsidian knowledge found", artifact.content)

    def test_empty_project_and_no_tasks_are_clear(self):
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="",
            assigned_issues=[],
        )
        report = ChangeReport(
            has_history=False,
            current_timestamp=current.timestamp,
        )

        artifact = self.service.execute(
            "daily.prepare",
            self.request(current=current, previous=None, report=report),
        )

        self.assertIn("Project: Not detected", artifact.content)
        self.assertIn("Assigned: 0 issues", artifact.content)
        self.assertIn("No Jira issues assigned", artifact.content)

    def test_jira_error_returns_unavailable_brief(self):
        artifact = self.service.execute(
            "daily.prepare",
            self.request_with_artifacts(
                [
                    Artifact(
                        name="daily_change_error",
                        source="Change Analysis Service",
                        content="Daily changes were not analyzed: Jira authentication failed.",
                    )
                ]
            ),
        )

        self.assertFalse(artifact.metadata["success"])
        self.assertIn("Daily Brief unavailable", artifact.content)
        self.assertIn("Jira authentication failed", artifact.content)

    def request(
        self,
        current: DailySnapshot,
        previous: DailySnapshot | None,
        report: ChangeReport,
    ) -> ServiceRequest:
        return self.request_with_artifacts(
            self.daily_artifacts(current=current, previous=previous, report=report)
        )

    def daily_artifacts(
        self,
        current: DailySnapshot,
        previous: DailySnapshot | None,
        report: ChangeReport,
    ) -> list[Artifact]:
        return [
            Artifact(
                name="daily_snapshots",
                source="Snapshot Service",
                content="Daily snapshot saved.",
                metadata={
                    "current_snapshot": current.to_dict(),
                    "previous_snapshot": previous.to_dict() if previous else None,
                },
            ),
            Artifact(
                name="daily_change_report",
                source="Change Analysis Service",
                content="Detected changes.",
                metadata={"change_report": report.to_dict()},
            ),
        ]

    def request_with_artifacts(self, artifacts: list[Artifact]) -> ServiceRequest:
        intent = UserIntent(
            name="daily_briefing",
            raw_text="prepare daily",
            expected_output="daily_brief",
            confidence=0.95,
        )

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
            artifacts=tuple(artifacts),
        )

    def issue(
        self,
        key: str,
        summary: str,
        status: str,
        priority: str = "Medium",
        updated: str = "2026-07-30T08:00:00+00:00",
    ) -> DailyIssueSnapshot:
        return DailyIssueSnapshot(
            key=key,
            project=key.split("-", 1)[0],
            summary=summary,
            status=status,
            status_category="done" if status == "Done" else "indeterminate",
            priority=priority,
            assignee="Ilya QA",
            updated=updated,
            sprint="QAOS Sprint 5",
            due_date="",
        )

    def change(self, key: str, summary: str, field: str, before: str, after: str):
        from app.services.daily_models import IssueFieldChange

        return IssueFieldChange(
            key=key,
            summary=summary,
            field=field,
            before=before,
            after=after,
        )


if __name__ == "__main__":
    unittest.main()
