import tempfile
import unittest
from pathlib import Path

from app.index.manager import IndexManager


class IndexManagerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault = self.root / "vault"
        self.index_path = self.root / "index.json"
        self.vault.mkdir()

        (self.vault / "Project.md").write_text(
            "\n".join(
                [
                    "---",
                    "aliases:",
                    "  - QASkills Project",
                    "tags: [QA, project]",
                    "---",
                    "# QASkills",
                    "",
                    "## Planner",
                    "",
                    "### Details",
                ]
            ),
            encoding="utf-8",
        )
        (self.vault / "Other.md").write_text(
            "# Other\n\n## Notes",
            encoding="utf-8",
        )

        self.manager = IndexManager(
            vault_path=str(self.vault),
            index_path=str(self.index_path),
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_rebuild_saves_metadata_index(self):
        index = self.manager.rebuild()

        self.assertTrue(self.index_path.exists())
        self.assertEqual(len(index.documents), 2)
        self.assertEqual(index.documents[1].title, "QASkills")
        self.assertIn("Planner", index.documents[1].headings["h2"])
        self.assertIn("QASkills Project", index.documents[1].aliases)
        self.assertIn("QA", index.documents[1].tags)

    def test_documents_load_from_saved_index_without_rescan(self):
        self.manager.rebuild()
        (self.vault / "Late.md").write_text("# Late", encoding="utf-8")

        fresh_manager = IndexManager(
            vault_path=str(self.vault),
            index_path=str(self.index_path),
        )

        documents = fresh_manager.documents()

        self.assertEqual(len(documents), 2)

    def test_filters_use_index_metadata(self):
        self.manager.rebuild()

        self.assertEqual(
            [document.title for document in self.manager.documents_with_tag("QA")],
            ["QASkills"],
        )
        self.assertEqual(
            [
                document.title
                for document in self.manager.documents_with_heading("Planner")
            ],
            ["QASkills"],
        )
        self.assertEqual(
            [
                document.title
                for document in self.manager.documents_by_name("QASkills Project")
            ],
            ["QASkills"],
        )

    def test_vault_structure_counts_folders(self):
        (self.vault / "Folder").mkdir()
        (self.vault / "Folder" / "Nested.md").write_text("# Nested", encoding="utf-8")

        structure = self.manager.rebuild().documents

        self.assertEqual(len(structure), 3)
        self.assertEqual(self.manager.vault_structure()["."], 2)
        self.assertEqual(self.manager.vault_structure()["Folder"], 1)


if __name__ == "__main__":
    unittest.main()
