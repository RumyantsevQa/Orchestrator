import json
import unittest

from app.mcp_server import QASkillsMCPServer


class FakeCodexAdapter:
    def __init__(self):
        self.requests = []

    def handle(self, request):
        self.requests.append(request)

        if request["operation"] == "show_skill" and request.get("skill_name") == "Missing":
            return {
                "success": False,
                "operation": "show_skill",
                "data": None,
                "error": {
                    "type": "not_found",
                    "message": "Missing",
                },
            }

        return {
            "success": True,
            "operation": request["operation"],
            "data": {
                "echo": request,
            },
            "error": None,
        }


class QASkillsMCPServerTest(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeCodexAdapter()
        self.server = QASkillsMCPServer(adapter=self.adapter)

    def test_initialize_advertises_tools_capability(self):
        response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )

        self.assertEqual("2.0", response["jsonrpc"])
        self.assertEqual(1, response["id"])
        self.assertIn("tools", response["result"]["capabilities"])
        self.assertEqual("qaskills-knowledge", response["result"]["serverInfo"]["name"])

    def test_tools_list_exposes_only_knowledge_api_operations(self):
        response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )

        tools = {tool["name"] for tool in response["result"]["tools"]}

        self.assertEqual(
            {
                "build_context",
                "ingest",
                "list_skills",
                "read",
                "search",
                "show_skill",
            },
            tools,
        )

    def test_tool_call_routes_to_codex_adapter(self):
        response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "build_context",
                    "arguments": {
                        "goal": "task_preparation",
                        "query": "SCRUM-42",
                        "jira_key": "SCRUM-42",
                    },
                },
            }
        )

        payload = self._payload(response)

        self.assertFalse(response["result"]["isError"])
        self.assertTrue(payload["success"])
        self.assertEqual(
            [
                {
                    "operation": "build_context",
                    "goal": "task_preparation",
                    "query": "SCRUM-42",
                    "jira_key": "SCRUM-42",
                }
            ],
            self.adapter.requests,
        )

    def test_tool_errors_are_returned_as_mcp_tool_errors(self):
        response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "show_skill",
                    "arguments": {
                        "skill_name": "Missing",
                    },
                },
            }
        )

        payload = self._payload(response)

        self.assertTrue(response["result"]["isError"])
        self.assertFalse(payload["success"])
        self.assertEqual("not_found", payload["error"]["type"])

    def test_invalid_arguments_are_returned_as_mcp_tool_errors(self):
        response = self.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": "Demo2",
                },
            }
        )

        payload = self._payload(response)

        self.assertTrue(response["result"]["isError"])
        self.assertFalse(payload["success"])
        self.assertEqual("invalid_request", payload["error"]["type"])
        self.assertEqual([], self.adapter.requests)

    def test_unknown_jsonrpc_method_returns_jsonrpc_error(self):
        response = self.server.handle_message(
            {"jsonrpc": "2.0", "id": 6, "method": "resources/list", "params": {}}
        )

        self.assertEqual(-32601, response["error"]["code"])

    def _payload(self, response):
        return json.loads(response["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
