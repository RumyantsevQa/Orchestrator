import json
import tempfile
import unittest
from pathlib import Path

from app.work_context.models import PersonalSeenState, SeenEntityState
from app.work_context.storage import SeenStateStorage


class SeenStateStorageTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.state_path = self.root / "personal_seen_state.json"
        self.storage = SeenStateStorage(self.state_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_missing_file_loads_empty_state(self):
        state = self.storage.load()

        self.assertEqual(state.schema_version, 1)
        self.assertEqual(state.entities, {})

    def test_state_survives_new_storage_instance(self):
        entity = SeenEntityState(
            source="jira",
            entity_type="issue",
            entity_id="SCRUM-7",
            last_seen_at="2026-07-31T10:00:00+03:00",
            source_updated_at="2026-07-31T09:30:00+03:00",
            status_seen="In Review",
            priority_seen="Highest",
            summary_fingerprint="summary-1",
            description_fingerprint="description-1",
            links_fingerprint="links-1",
            comments_seen=["10001", "10002"],
            last_workflow="prepare_task",
            recommendation_fingerprints=["rec-1"],
        )

        self.storage.upsert(entity)
        loaded = SeenStateStorage(self.state_path).load()

        self.assertEqual(
            loaded.get("jira", "issue", "SCRUM-7"),
            entity,
        )

    def test_seen_entity_requires_identity_fields(self):
        for field_name in ["source", "entity_type", "entity_id"]:
            kwargs = {
                "source": "jira",
                "entity_type": "issue",
                "entity_id": "SCRUM-7",
                "last_seen_at": "2026-07-31T10:00:00+03:00",
            }
            kwargs[field_name] = " "

            with self.subTest(field_name=field_name):
                with self.assertRaises(ValueError):
                    SeenEntityState(**kwargs)

    def test_invalid_entity_is_skipped_when_loading_state(self):
        self.state_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "entities": [
                        {
                            "source": "",
                            "entity_type": "issue",
                            "entity_id": "BROKEN-1",
                            "last_seen_at": "2026-07-31T10:00:00+03:00",
                        },
                        {
                            "source": "jira",
                            "entity_type": "issue",
                            "entity_id": "SCRUM-7",
                            "last_seen_at": "2026-07-31T10:00:00+03:00",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        state = self.storage.load()

        self.assertIsNone(state.get("", "issue", "BROKEN-1"))
        self.assertIsNotNone(state.get("jira", "issue", "SCRUM-7"))
        self.assertEqual(len(state.entities), 1)

    def test_corrupted_file_loads_empty_state(self):
        self.state_path.write_text("{not json", encoding="utf-8")

        state = self.storage.load()

        self.assertEqual(state.entities, {})

    def test_unknown_schema_version_loads_empty_state(self):
        self.state_path.write_text(
            json.dumps({"schema_version": 999, "entities": []}),
            encoding="utf-8",
        )

        state = self.storage.load()

        self.assertEqual(state.entities, {})

    def test_full_jira_payload_is_not_persisted(self):
        raw_state = {
            "schema_version": 1,
            "entities": [
                {
                    "source": "jira",
                    "entity_type": "issue",
                    "entity_id": "SCRUM-7",
                    "last_seen_at": "2026-07-31T10:00:00+03:00",
                    "fields": {
                        "summary": "Full Jira payload must not be stored.",
                        "description": "Full description body.",
                    },
                    "comment": {
                        "comments": [
                            {"body": "Full comment body must not be stored."}
                        ]
                    },
                    "comments_seen": ["10001"],
                }
            ],
        }

        state = PersonalSeenState.from_dict(raw_state)
        self.storage.save(state)
        persisted = self.state_path.read_text(encoding="utf-8")

        self.assertIn("comments_seen", persisted)
        self.assertNotIn("Full Jira payload", persisted)
        self.assertNotIn("Full description body", persisted)
        self.assertNotIn("Full comment body", persisted)


if __name__ == "__main__":
    unittest.main()
