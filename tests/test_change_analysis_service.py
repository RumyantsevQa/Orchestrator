import unittest
from datetime import UTC, datetime

from app.services.change_analysis import ChangeAnalysisService
from app.services.daily_models import DailyIssueSnapshot, DailySnapshot


class ChangeAnalysisServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = ChangeAnalysisService(
            now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
            stale_days=3,
        )

    def test_first_run_has_insufficient_history(self):
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[self.issue("SCRUM-1", "Login")],
        )

        report = self.service.compare(current=current, previous=None)

        self.assertFalse(report.has_history)
        self.assertEqual(report.new_issues, [])
        self.assertEqual(report.current_timestamp, current.timestamp)

    def test_detects_new_removed_and_closed_issues(self):
        previous = DailySnapshot(
            timestamp="2026-07-29T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[
                self.issue("SCRUM-1", "Login", status="In Progress"),
                self.issue("SCRUM-2", "Old task", status="To Do"),
            ],
        )
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[
                self.issue("SCRUM-1", "Login", status="Done", status_category="done"),
                self.issue("SCRUM-3", "New task", status="To Do"),
            ],
        )

        report = self.service.compare(current=current, previous=previous)

        self.assertTrue(report.has_history)
        self.assertEqual([issue.key for issue in report.new_issues], ["SCRUM-3"])
        self.assertEqual([issue.key for issue in report.removed_issues], ["SCRUM-2"])
        self.assertEqual([issue.key for issue in report.closed_issues], ["SCRUM-1"])

    def test_detects_field_changes(self):
        previous = DailySnapshot(
            timestamp="2026-07-29T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[
                self.issue(
                    "SCRUM-1",
                    "Login",
                    status="To Do",
                    assignee="Ilya",
                    priority="Medium",
                    sprint="Sprint 4",
                    due_date="2026-07-31",
                    comment_count=1,
                    description_hash="aaa",
                )
            ],
        )
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[
                self.issue(
                    "SCRUM-1",
                    "Login",
                    status="In Progress",
                    assignee="QA Lead",
                    priority="High",
                    sprint="Sprint 5",
                    due_date="2026-08-01",
                    comment_count=3,
                    description_hash="bbb",
                )
            ],
        )

        report = self.service.compare(current=current, previous=previous)

        self.assertEqual(report.status_changes[0].after, "In Progress")
        self.assertEqual(report.assignee_changes[0].after, "QA Lead")
        self.assertEqual(report.priority_changes[0].after, "High")
        self.assertEqual(report.sprint_changes[0].after, "Sprint 5")
        self.assertEqual(report.due_date_changes[0].after, "2026-08-01")
        self.assertEqual(report.comment_count_changes[0].after, "3")
        self.assertEqual(report.description_changes[0].after, "bbb")

    def test_detects_long_unchanged_issues(self):
        current = DailySnapshot(
            timestamp="2026-07-30T09:00:00+00:00",
            project="SCRUM",
            assigned_issues=[
                self.issue(
                    "SCRUM-1",
                    "Login",
                    updated="2026-07-20T09:00:00+00:00",
                )
            ],
        )

        report = self.service.compare(current=current, previous=None)

        self.assertEqual([issue.key for issue in report.unchanged_stale_issues], ["SCRUM-1"])

    def issue(
        self,
        key: str,
        summary: str,
        status: str = "To Do",
        status_category: str = "new",
        assignee: str = "Ilya",
        priority: str = "Medium",
        sprint: str = "Sprint 5",
        due_date: str = "",
        updated: str = "2026-07-30T08:00:00+00:00",
        comment_count: int = 0,
        description_hash: str = "",
    ) -> DailyIssueSnapshot:
        return DailyIssueSnapshot(
            key=key,
            project=key.split("-", 1)[0],
            summary=summary,
            status=status,
            status_category=status_category,
            priority=priority,
            assignee=assignee,
            updated=updated,
            sprint=sprint,
            due_date=due_date,
            comment_count=comment_count,
            description_hash=description_hash,
        )


if __name__ == "__main__":
    unittest.main()
