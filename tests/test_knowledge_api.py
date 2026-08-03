import tempfile
import unittest
from pathlib import Path

from app.core.artifacts import Artifact
from app.knowledge_api import KnowledgeAPI, KnowledgeContextRequest
from app.services.memory import MemoryService


class FakeJiraService:
    def __init__(self, artifact: Artifact):
        self.artifact = artifact

    def execute(self, capability, request, trace=None):
        self.capability = capability
        self.request = request
        return self.artifact


class KnowledgeAPITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.index_path = self.root / "index.json"
        self._write(
            "Projects/Auth.md",
            "\n".join(
                [
                    "---",
                    "tags: [auth, qa]",
                    "aliases: [authorization]",
                    "---",
                    "# Authorization",
                    "## SCRUM-42",
                    "Email confirmation flow.",
                ]
            ),
        )
        self._write(
            "QASkills/Knowledge/Testing/Web Authentication And Session Heuristics.md",
            "\n".join(
                [
                    "# Web Authentication And Session Heuristics",
                    "",
                    "Status: current",
                    "",
                    "Type: heuristic",
                    "",
                    "Confidence: high (>90%)",
                    "",
                    "Authority: user-approved Notion QA migration decision",
                    "",
                    "Available to: AnalyzeFeature, GenerateTestCases, RiskAnalysis",
                    "",
                    "## Rule",
                    "",
                    "Test authentication as a state machine and verify server-side authorization.",
                ]
            ),
        )
        self._write(
            "QASkills/Knowledge/REST/API Contract Review.md",
            "\n".join(
                [
                    "# API Contract Review",
                    "",
                    "Status: current",
                    "",
                    "Type: heuristic",
                    "",
                    "Confidence: high (>90%)",
                    "",
                    "Authority: user-approved Notion QA migration decision",
                    "",
                    "Available to: APIInvestigation, GenerateTestCases",
                    "",
                    "## Rule",
                    "",
                    "Check authentication headers, authorization status codes, and token boundaries.",
                ]
            ),
        )
        self._write(
            "qaos-core/.venv/lib/python/site-packages/fastapi/.agents/skills/fastapi/SKILL.md",
            "\n".join(
                [
                    "# FastAPI",
                    "",
                    "OAuth authentication token API dependency note.",
                ]
            ),
        )
        self._write(
            "Archive/Superseded/Archived Login Notes.md",
            "\n".join(
                [
                    "# Archived Login Notes",
                    "",
                    "Status: superseded",
                    "",
                    "Available to: GenerateTestCases",
                ]
            ),
        )
        self._write(
            "QASkills/Skills/AnalyzeFeature/SKILL.md",
            "\n".join(
                [
                    "---",
                    "name: analyze-feature",
                    "description: Analyze feature behavior for QA.",
                    "---",
                    "# Analyze Feature",
                    "",
                    "## Knowledge Dependencies",
                    "",
                    "Required:",
                    "",
                    "- [[QASkills/Knowledge/QA/Evidence First]]",
                    "",
                    "Conditional:",
                    "",
                    "- Web session, authentication, storage, or browser behavior: [[QASkills/Knowledge/Testing/Web Authentication And Session Heuristics]]",
                ]
            ),
        )
        self._write(
            "QASkills/Skills/GenerateTestCases/SKILL.md",
            "\n".join(
                [
                    "---",
                    "name: generate-test-cases",
                    "description: Generate QA checks from evidence.",
                    "---",
                    "# Generate Test Cases",
                    "",
                    "## Knowledge Dependencies",
                    "",
                    "Conditional:",
                    "",
                    "- Web authentication, session, cookie, token, or storage coverage: [[QASkills/Knowledge/Testing/Web Authentication And Session Heuristics]]",
                ]
            ),
        )
        self._write(
            "QASkills/Skills/RiskAnalysis/SKILL.md",
            "\n".join(
                [
                    "---",
                    "name: risk-analysis",
                    "description: Analyze QA risk from evidence.",
                    "---",
                    "# Risk Analysis",
                    "",
                    "## Knowledge Dependencies",
                    "",
                    "Conditional:",
                    "",
                    "- Web authentication, session, storage, or browser risk: [[QASkills/Knowledge/Testing/Web Authentication And Session Heuristics]]",
                ]
            ),
        )
        self._write(
            "QASkills/Skills/APIInvestigation/SKILL.md",
            "\n".join(
                [
                    "---",
                    "name: api-investigation",
                    "description: Investigate REST APIs, headers, authentication, status codes, and API test design.",
                    "---",
                    "# API Investigation",
                    "",
                    "## Knowledge Dependencies",
                    "",
                    "Required:",
                    "",
                    "- [[QASkills/Knowledge/REST/API Contract Review]]",
                ]
            ),
        )
        self._write(
            "QASkills/Knowledge/QA/Evidence First.md",
            "# Evidence First\nEvery claim must be grounded in evidence.",
        )
        self._write(
            "QASkills/Knowledge/QA/Human Controlled Knowledge.md",
            "# Human Controlled Knowledge\nDurable knowledge requires confirmation.",
        )
        self._write(
            "PROJECT_RULES.md",
            "# Project Rules\nNo irreversible actions without approval.",
        )
        self.memory = MemoryService(
            vault_path=str(self.vault),
            index_path=str(self.index_path),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_search_uses_existing_memory_service_index(self):
        api = KnowledgeAPI(memory_service=self.memory, jira_service=self._jira_error())

        results = api.search("authorization")

        self.assertEqual(1, len(results))
        self.assertEqual("Authorization", results[0]["document"]["title"])
        self.assertIn("aliases", results[0]["reasons"])

    def test_read_returns_document_content(self):
        api = KnowledgeAPI(memory_service=self.memory, jira_service=self._jira_error())

        document = api.read("Authorization")

        self.assertEqual("Authorization", document["info"]["title"])
        self.assertIn("Email confirmation flow", document["content"])

    def test_ingest_saves_markdown_and_refreshes_index(self):
        api = KnowledgeAPI(memory_service=self.memory, jira_service=self._jira_error())
        source = self.root / "Auth Notes.md"
        source.write_text("# Auth Notes\nNew auth documentation.", encoding="utf-8")

        saved = api.ingest(source, target_folder="Imported")
        results = api.search("Auth Notes")

        self.assertEqual("Auth Notes", saved["title"])
        self.assertTrue(saved["path"].startswith("Imported/"))
        self.assertIn(
            saved["path"],
            [result["document"]["path"] for result in results],
        )

    def test_list_and_show_skills_read_real_skill_files(self):
        api = KnowledgeAPI(memory_service=self.memory, jira_service=self._jira_error())

        skills = api.list_skills()
        skill = api.show_skill("AnalyzeFeature")

        self.assertEqual(4, len(skills))
        self.assertEqual("analyze-feature", skill["name"])
        self.assertIn("Analyze feature behavior", skill["description"])
        self.assertIn("Required", skill["knowledge_dependencies"])
        self.assertIn("# Analyze Feature", skill["content"])

    def test_build_context_returns_structured_knowledge_pack(self):
        jira_service = FakeJiraService(
            Artifact(
                name="jira_issue",
                source="Jira Service",
                content="Jira Issue SCRUM-42",
                metadata={
                    "issue": {
                        "key": "SCRUM-42",
                        "summary": "Implement authorization",
                        "status": "Ready for QA",
                        "priority": "High",
                        "updated": "2026-08-03T10:00:00.000+0000",
                        "comments": [
                            {
                                "id": "1001",
                                "author": "Egor",
                                "created": "2026-08-03",
                                "body": "Please recheck email confirmation.",
                            }
                        ],
                    }
                },
            )
        )
        api = KnowledgeAPI(memory_service=self.memory, jira_service=jira_service)

        pack = api.build_context(
            KnowledgeContextRequest(
                user_goal="testing_strategy",
                query="authorization",
                jira_key="SCRUM-42",
                limit=5,
            )
        )

        self.assertEqual("knowledge_pack", pack["kind"])
        self.assertEqual("testing_strategy", pack["user_goal"])
        self.assertEqual("SCRUM-42", pack["related_jira"]["key"])
        self.assertEqual(1, len(pack["related_jira"]["important_comments"]))
        self.assertGreaterEqual(len(pack["relevant_documents"]), 1)
        self.assertEqual(3, len(pack["related_qa_skills"]))
        self.assertEqual(pack["relevant_documents"], pack["relevant_knowledge"])
        self.assertIn("entry_point", pack)
        self.assertIn("known_risks", pack)
        self.assertTrue(pack["related_qa_skills"][0]["why_selected"])
        self.assertIn("rules", pack)
        self.assertIn("evidence", pack)
        self.assertIn("confidence", pack)
        self.assertNotIn("recommendations", pack)

    def test_build_context_uses_explicit_relationships_for_auth_skills(self):
        api = KnowledgeAPI(memory_service=self.memory, jira_service=self._jira_error())

        pack = api.build_context(
            {
                "goal": "Найди всё про авторизацию.",
                "include": ["knowledge", "skills", "rules"],
                "limit": 5,
            }
        )

        skill_folders = {
            skill["folder"]
            for skill in pack["related_qa_skills"]
        }

        self.assertIn("AnalyzeFeature", skill_folders)
        self.assertIn("GenerateTestCases", skill_folders)
        self.assertIn("RiskAnalysis", skill_folders)
        self.assertTrue(
            all(skill["selection"] == "explicit" for skill in pack["related_qa_skills"])
        )
        self.assertIn("explicit_relationships_found", pack["confidence"]["basis"])
        self.assertTrue(pack["known_risks"])
        self.assertTrue(pack["excluded_documents"])
        self.assertIn("why_excluded", pack["excluded_documents"][0])

    def test_build_context_connects_oauth_to_api_and_test_skills(self):
        api = KnowledgeAPI(memory_service=self.memory, jira_service=self._jira_error())

        pack = api.build_context(
            {
                "goal": "Как протестировать OAuth?",
                "include": ["knowledge", "skills", "rules"],
                "limit": 5,
            }
        )

        skill_folders = {
            skill["folder"]
            for skill in pack["related_qa_skills"]
        }

        self.assertIn("APIInvestigation", skill_folders)
        self.assertIn("GenerateTestCases", skill_folders)
        selected_paths = {
            item["document"]["path"]
            for item in pack["relevant_knowledge"]
        }
        excluded_paths = {
            item["document"]["path"]
            for item in pack["excluded_documents"]
        }

        self.assertFalse(any(".venv" in path for path in selected_paths))
        self.assertTrue(any(".venv" in path for path in excluded_paths))
        self.assertTrue(
            any(
                "OAuth contract" in item["message"]
                for item in pack["missing_information_details"]
            )
        )

    def test_build_context_handles_unavailable_jira_without_reasoning(self):
        api = KnowledgeAPI(memory_service=self.memory, jira_service=self._jira_error())

        pack = api.build_context(
            {
                "goal": "task_preparation",
                "query": "authorization",
                "jira_key": "SCRUM-42",
            }
        )

        self.assertFalse(pack["related_jira"]["available"])
        self.assertIn("Jira is not configured", pack["missing_information"][0])
        self.assertGreaterEqual(len(pack["relevant_documents"]), 1)

    def _write(self, relative_path: str, content: str):
        path = self.vault / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _jira_error(self):
        return FakeJiraService(
            Artifact(
                name="jira_error",
                source="Jira Service",
                content="Jira is not configured.",
                metadata={"connected": False},
            )
        )


if __name__ == "__main__":
    unittest.main()
