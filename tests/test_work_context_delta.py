import unittest

from app.work_context import current_jira_issue_state
from app.work_context.comparison import compare_seen_state
from app.work_context.models import CurrentEntityState, SeenEntityState


class WorkContextDeltaTest(unittest.TestCase):
    def test_jira_issue_state_extracts_minimal_comparable_facts(self):
        state = current_jira_issue_state(
            {
                "key": "scrum-7",
                "summary": "Registration with email confirmation",
                "updated": "2026-07-31T09:00:00+03:00",
                "status": "Ready for QA",
                "priority": "High",
                "description": "Full Jira description must not be kept as text.",
                "comments": [
                    {
                        "id": "10001",
                        "author": "Developer",
                        "created": "2026-07-31T08:00:00+03:00",
                        "body": "Please re-check email confirmation.",
                    }
                ],
                "links": [
                    {
                        "type": "relates to",
                        "key": "SCRUM-8",
                        "summary": "Login",
                        "status": "In Progress",
                    }
                ],
            }
        )

        self.assertEqual(state.source, "jira")
        self.assertEqual(state.entity_type, "issue")
        self.assertEqual(state.entity_id, "SCRUM-7")
        self.assertEqual(state.status, "Ready for QA")
        self.assertEqual(state.priority, "High")
        self.assertEqual(state.comment_ids, ["10001"])
        self.assertNotEqual(
            state.summary_fingerprint,
            "Registration with email confirmation",
        )
        self.assertNotIn("Full Jira description", state.description_fingerprint)

    def test_comment_without_id_uses_fingerprint_identifier(self):
        state = current_jira_issue_state(
            {
                "key": "SCRUM-7",
                "comments": [
                    {
                        "author": "Developer",
                        "created": "2026-07-31T08:00:00+03:00",
                        "body": "No Jira comment id in fixture.",
                    }
                ],
            }
        )

        self.assertEqual(len(state.comment_ids), 1)
        self.assertEqual(len(state.comment_ids[0]), 16)

    def test_delta_reports_no_changes_for_same_seen_state(self):
        current = CurrentEntityState(
            source="jira",
            entity_type="issue",
            entity_id="SCRUM-7",
            source_updated_at="2026-07-31T09:00:00+03:00",
            status="Ready for QA",
            priority="High",
            summary_fingerprint="summary-1",
            description_fingerprint="description-1",
            links_fingerprint="links-1",
            comment_ids=["10001"],
        )
        previous = SeenEntityState(
            source=current.source,
            entity_type=current.entity_type,
            entity_id=current.entity_id,
            last_seen_at="2026-07-31T08:00:00+03:00",
            source_updated_at=current.source_updated_at,
            status_seen=current.status,
            priority_seen=current.priority,
            summary_fingerprint=current.summary_fingerprint,
            description_fingerprint=current.description_fingerprint,
            links_fingerprint=current.links_fingerprint,
            comments_seen=current.comment_ids,
            last_workflow="prepare_task",
        )

        delta = compare_seen_state(previous, current)

        self.assertTrue(delta.has_previous)
        self.assertFalse(delta.has_changes)
        self.assertEqual(delta.field_changes, [])
        self.assertEqual(delta.new_comment_ids, [])
        self.assertEqual(delta.previous_workflow, "prepare_task")

    def test_delta_reports_field_changes_and_new_comments(self):
        previous = SeenEntityState(
            source="jira",
            entity_type="issue",
            entity_id="SCRUM-7",
            last_seen_at="2026-07-31T08:00:00+03:00",
            source_updated_at="2026-07-31T08:00:00+03:00",
            status_seen="In Progress",
            priority_seen="Medium",
            summary_fingerprint="summary-1",
            description_fingerprint="description-1",
            links_fingerprint="links-1",
            comments_seen=["10001"],
            last_workflow="prepare_task",
        )
        current = CurrentEntityState(
            source="jira",
            entity_type="issue",
            entity_id="SCRUM-7",
            source_updated_at="2026-07-31T09:00:00+03:00",
            status="Ready for QA",
            priority="High",
            summary_fingerprint="summary-2",
            description_fingerprint="description-1",
            links_fingerprint="links-2",
            comment_ids=["10001", "10002"],
        )

        delta = compare_seen_state(previous, current)
        changed_fields = {
            change.field
            for change in delta.field_changes
        }

        self.assertTrue(delta.has_changes)
        self.assertEqual(
            changed_fields,
            {"status", "priority", "summary", "links"},
        )
        self.assertEqual(delta.new_comment_ids, ["10002"])
        self.assertEqual(delta.source_updated_at, current.source_updated_at)

    def test_comparison_rejects_different_entities(self):
        previous = SeenEntityState(
            source="jira",
            entity_type="issue",
            entity_id="SCRUM-7",
            last_seen_at="2026-07-31T08:00:00+03:00",
        )
        current = CurrentEntityState(
            source="jira",
            entity_type="issue",
            entity_id="SCRUM-8",
        )

        with self.assertRaises(ValueError):
            compare_seen_state(previous, current)


if __name__ == "__main__":
    unittest.main()
