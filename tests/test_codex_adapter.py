import unittest
from pathlib import Path

from app.codex_adapter import CodexAdapter


class FakeKnowledgeAPI:
    def __init__(self):
        self.calls = []

    def build_context(self, request):
        self.calls.append(("build_context", request))
        return {
            "kind": "knowledge_pack",
            "user_goal": request.get("goal"),
            "query": request.get("query"),
        }

    def search(self, query, limit=5):
        self.calls.append(("search", query, limit))
        return [{"document": {"title": query}, "score": 10}]

    def read(self, path_or_name):
        self.calls.append(("read", path_or_name))
        return {"path": path_or_name, "content": "Document content"}

    def ingest(self, file_path, target_folder="QASkills/Memory/Inbox"):
        self.calls.append(("ingest", file_path, target_folder))
        return {"path": f"{target_folder}/{Path(file_path).name}"}

    def list_skills(self):
        self.calls.append(("list_skills",))
        return [{"name": "AnalyzeFeature"}]

    def show_skill(self, skill_name):
        self.calls.append(("show_skill", skill_name))
        if skill_name == "Missing":
            raise FileNotFoundError(skill_name)
        if skill_name == "Broken":
            raise RuntimeError("Knowledge API failed")
        return {"name": skill_name, "content": "# Skill"}


class CodexAdapterTest(unittest.TestCase):
    def setUp(self):
        self.api = FakeKnowledgeAPI()
        self.adapter = CodexAdapter(knowledge_api=self.api)

    def test_build_context_forwards_structured_payload(self):
        response = self.adapter.handle(
            {
                "operation": "build_context",
                "goal": "task_preparation",
                "query": "SCRUM-42",
                "jira_key": "SCRUM-42",
            }
        )

        self.assertTrue(response["success"])
        self.assertEqual("build_context", response["operation"])
        self.assertEqual("knowledge_pack", response["data"]["kind"])
        self.assertEqual(
            (
                "build_context",
                {
                    "goal": "task_preparation",
                    "query": "SCRUM-42",
                    "jira_key": "SCRUM-42",
                },
            ),
            self.api.calls[0],
        )

    def test_search_forwards_query_and_limit(self):
        response = self.adapter.handle(
            {"operation": "search", "query": "Demo2", "limit": 3}
        )

        self.assertTrue(response["success"])
        self.assertEqual([("search", "Demo2", 3)], self.api.calls)
        self.assertEqual("Demo2", response["data"][0]["document"]["title"])

    def test_read_accepts_path_or_name_aliases(self):
        response = self.adapter.handle(
            {"operation": "read", "name": "QASkills"}
        )

        self.assertTrue(response["success"])
        self.assertEqual([("read", "QASkills")], self.api.calls)
        self.assertEqual("QASkills", response["data"]["path"])

    def test_ingest_forwards_file_path_and_target_folder(self):
        response = self.adapter.handle(
            {
                "operation": "ingest",
                "file_path": "/tmp/meeting.md",
                "target_folder": "Meetings",
            }
        )

        self.assertTrue(response["success"])
        self.assertEqual([("ingest", "/tmp/meeting.md", "Meetings")], self.api.calls)
        self.assertEqual("Meetings/meeting.md", response["data"]["path"])

    def test_list_skills_routes_to_knowledge_api(self):
        response = self.adapter.handle({"operation": "list_skills"})

        self.assertTrue(response["success"])
        self.assertEqual([("list_skills",)], self.api.calls)
        self.assertEqual("AnalyzeFeature", response["data"][0]["name"])

    def test_show_skill_routes_to_knowledge_api(self):
        response = self.adapter.handle(
            {"operation": "show_skill", "skill_name": "AnalyzeFeature"}
        )

        self.assertTrue(response["success"])
        self.assertEqual([("show_skill", "AnalyzeFeature")], self.api.calls)
        self.assertEqual("# Skill", response["data"]["content"])

    def test_missing_operation_returns_structured_error(self):
        response = self.adapter.handle({"query": "Demo2"})

        self.assertFalse(response["success"])
        self.assertEqual("missing_operation", response["error"]["type"])
        self.assertEqual([], self.api.calls)

    def test_unsupported_operation_returns_structured_error(self):
        response = self.adapter.handle({"operation": "reason_about_issue"})

        self.assertFalse(response["success"])
        self.assertEqual("unsupported_operation", response["error"]["type"])
        self.assertEqual([], self.api.calls)

    def test_missing_required_field_returns_structured_error(self):
        response = self.adapter.handle({"operation": "search"})

        self.assertFalse(response["success"])
        self.assertEqual("invalid_request", response["error"]["type"])
        self.assertEqual([], self.api.calls)

    def test_not_found_is_returned_as_structured_error(self):
        response = self.adapter.handle(
            {"operation": "show_skill", "skill_name": "Missing"}
        )

        self.assertFalse(response["success"])
        self.assertEqual("not_found", response["error"]["type"])
        self.assertEqual([("show_skill", "Missing")], self.api.calls)

    def test_unexpected_api_error_is_returned_as_structured_error(self):
        response = self.adapter.handle(
            {"operation": "show_skill", "skill_name": "Broken"}
        )

        self.assertFalse(response["success"])
        self.assertEqual("adapter_error", response["error"]["type"])
        self.assertEqual("Knowledge API failed", response["error"]["message"])
        self.assertEqual([("show_skill", "Broken")], self.api.calls)

    def test_non_dict_request_is_rejected_without_calling_api(self):
        response = self.adapter.handle("search Demo2")

        self.assertFalse(response["success"])
        self.assertEqual("invalid_request", response["error"]["type"])
        self.assertEqual([], self.api.calls)


if __name__ == "__main__":
    unittest.main()
