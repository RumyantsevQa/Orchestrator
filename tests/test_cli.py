import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from app.core.models import OrchestratorResponse
from main import main


class CliReleaseCandidateTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault = self.root / "vault"
        self.index_path = self.root / "document_index.json"
        self.vault.mkdir()

        (self.vault / "Architecture.md").write_text(
            "\n".join(
                [
                    "---",
                    "aliases: [QASkills Architecture]",
                    "tags: [architecture, QA, qaskills]",
                    "---",
                    "# QASkills Architecture",
                    "",
                    "## Document Index",
                    "",
                    "Metadata-only memory index.",
                ]
            ),
            encoding="utf-8",
        )
        (self.vault / "Projects").mkdir()
        (self.vault / "Projects" / "Daily.md").write_text(
            "\n".join(
                [
                    "---",
                    "tags: [daily, qa]",
                    "---",
                    "# Daily Preparation",
                    "",
                    "## Morning",
                    "",
                    "Briefing notes.",
                ]
            ),
            encoding="utf-8",
        )

        self.env = {
            "QASKILLS_MEMORY_VAULT_PATH": str(self.vault),
            "QASKILLS_DOCUMENT_INDEX_PATH": str(self.index_path),
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()

        with patch.dict(os.environ, self.env, clear=False):
            with redirect_stdout(output):
                code = main(list(args))

        return code, output.getvalue()

    def test_help_is_grouped_by_product_area(self):
        code, output = self.run_cli("help")

        self.assertEqual(code, 0)
        self.assertIn("Knowledge", output)
        self.assertIn("Search", output)
        self.assertIn("Questions", output)
        self.assertIn("Navigation", output)
        self.assertIn("Diagnostics", output)

    def test_status_shows_vault_index_and_document_count(self):
        code, output = self.run_cli("status")

        self.assertEqual(code, 0)
        self.assertIn("Vault", output)
        self.assertIn("Document Index", output)
        self.assertIn("Documents Count", output)
        self.assertIn("2", output)

    def test_find_searches_metadata_with_russian_aliases(self):
        code, output = self.run_cli("find", "архитектура")

        self.assertEqual(code, 0)
        self.assertIn("Found", output)
        self.assertIn("QASkills Architecture", output)
        self.assertIn("architecture", output)

    def test_find_no_match_uses_single_error_block(self):
        code, output = self.run_cli("find", "missing-topic-999")

        self.assertEqual(code, 1)
        self.assertIn("Nothing Found", output)
        self.assertIn("По запросу 'missing-topic-999' ничего не найдено.", output)
        self.assertNotIn("Search: missing-topic-999", output)
        self.assertEqual(output.count("QASkills\n"), 1)

    def test_ask_prepares_grounded_source_pack(self):
        code, output = self.run_cli("ask", "Что", "мы", "решили", "про", "архитектуру?")

        self.assertEqual(code, 0)
        self.assertIn("Search", output)
        self.assertIn("Source Pack", output)
        self.assertIn("Key Sources", output)
        self.assertIn("Grouped Sources", output)
        self.assertIn("Recommended Reading Order", output)
        self.assertIn("source documents", output)
        self.assertIn("QASkills Architecture", output)
        self.assertIn("Architecture", output)

    def test_ask_no_match_keeps_single_ask_flow(self):
        code, output = self.run_cli("ask", "missing-topic-999")

        self.assertEqual(code, 1)
        self.assertIn("Ask", output)
        self.assertIn("Источники не найдены в локальном индексе.", output)
        self.assertNotIn("Nothing Found", output)
        self.assertEqual(output.count("QASkills\n"), 1)

    def test_demo_completes(self):
        code, output = self.run_cli("demo")

        self.assertEqual(code, 0)
        self.assertIn("Welcome to QASkills Demo", output)
        self.assertIn("Vault connected", output)
        self.assertIn("Demo completed", output)

    def test_workspace_menu_is_available_as_single_entrypoint(self):
        code, output = self.run_cli("workspace")

        self.assertEqual(code, 0)
        self.assertIn("Workspace", output)
        self.assertIn("Подготовиться к Daily", output)
        self.assertIn("Работа с Jira", output)
        self.assertIn("Сохранить новое знание", output)

    def test_remember_saves_note_to_vault_and_refreshes_index(self):
        code, output = self.run_cli(
            "remember",
            "Daily decision: use QASkills workspace",
        )

        self.assertEqual(code, 0)
        self.assertIn("Knowledge Saved", output)
        self.assertIn("Document Index", output)

        saved_notes = list((self.vault / "QASkills" / "Memory" / "Inbox").glob("*.md"))

        self.assertEqual(len(saved_notes), 1)

        find_code, find_output = self.run_cli("find", "Daily decision")

        self.assertEqual(find_code, 0)
        self.assertIn("Daily decision", find_output)

    def test_jira_workspace_uses_unified_pipeline_without_live_api(self):
        code, output = self.run_cli("jira", "SCRUM-42")

        self.assertEqual(code, 0)
        self.assertIn("Jira Issue", output)
        self.assertIn("Memory Service", output)
        self.assertIn("Jira Service", output)
        self.assertIn("Live Jira data is not connected", output)

    @patch("main.Orchestrator")
    def test_prepare_daily_uses_unified_pipeline_action(self, orchestrator_cls):
        orchestrator = orchestrator_cls.return_value
        orchestrator.process.return_value = OrchestratorResponse(
            success=True,
            message="Today's Daily Brief\nSuggested Daily Report",
            data={
                "artifacts": [
                    {
                        "name": "daily_brief",
                        "metadata": {"success": True},
                    }
                ]
            },
        )

        code, output = self.run_cli("prepare", "daily")

        self.assertEqual(code, 0)
        self.assertIn("Daily Brief", output)
        self.assertIn("Suggested Daily Report", output)
        request = orchestrator.process.call_args.args[0]
        self.assertEqual(request.metadata["action"], "daily.prepare")


if __name__ == "__main__":
    unittest.main()
