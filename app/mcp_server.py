import json
import sys
from typing import Any

from app.codex_adapter import CodexAdapter


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "qaskills-knowledge"
SERVER_VERSION = "0.1.0"


TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "search",
        "description": "Search indexed QASkills knowledge metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query prepared by Codex.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results.",
                    "default": 5,
                    "minimum": 1,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read",
        "description": "Read one Markdown document by vault-relative path or name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path_or_name": {
                    "type": "string",
                    "description": "Vault-relative path or document title/name.",
                },
            },
            "required": ["path_or_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ingest",
        "description": "Import a Markdown file into the configured knowledge vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Local Markdown file path to import.",
                },
                "target_folder": {
                    "type": "string",
                    "description": "Optional target folder inside the vault.",
                    "default": "QASkills/Memory/Inbox",
                },
            },
            "required": ["file_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_skills",
        "description": "List QA Skills available in the configured knowledge vault.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "show_skill",
        "description": "Return one QA Skill with full source content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "QA Skill folder name or declared skill name.",
                },
            },
            "required": ["skill_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "build_context",
        "description": "Build a structured Knowledge Pack for Codex.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Structured user goal chosen by Codex.",
                },
                "query": {
                    "type": "string",
                    "description": "Knowledge query prepared by Codex.",
                },
                "jira_key": {
                    "type": "string",
                    "description": "Optional Jira issue key, for example SCRUM-42.",
                },
                "include": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["jira", "knowledge", "skills", "rules"],
                    },
                    "description": "Knowledge sources to include.",
                    "default": ["jira", "knowledge", "skills", "rules"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of knowledge documents.",
                    "default": 5,
                    "minimum": 1,
                },
            },
            "required": ["goal"],
            "additionalProperties": False,
        },
    },
)


class QASkillsMCPServer:
    """
    Minimal local MCP server exposing KnowledgeAPI operations as tools.

    The server intentionally contains no natural-language understanding and no
    product workflow logic. Codex chooses the tool and arguments; QASkills
    returns structured knowledge through CodexAdapter.
    """

    def __init__(self, adapter: CodexAdapter | None = None):
        self.adapter = adapter or CodexAdapter()

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC MCP message."""

        method = message.get("method")
        request_id = message.get("id")

        if method == "notifications/initialized":
            return None

        if request_id is None:
            return None

        if method == "initialize":
            return self._response(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            )

        if method == "tools/list":
            return self._response(request_id, {"tools": list(TOOL_DEFINITIONS)})

        if method == "tools/call":
            return self._response(request_id, self._call_tool(message))

        if method == "ping":
            return self._response(request_id, {})

        return self._jsonrpc_error(
            request_id=request_id,
            code=-32601,
            message=f"Method not found: {method}",
        )

    def _call_tool(self, message: dict[str, Any]) -> dict[str, Any]:
        params = message.get("params") or {}
        tool_name = str(params.get("name") or "").strip()
        arguments = params.get("arguments") or {}

        if not isinstance(arguments, dict):
            return self._tool_result(
                payload={
                    "success": False,
                    "operation": tool_name,
                    "data": None,
                    "error": {
                        "type": "invalid_request",
                        "message": "Tool arguments must be an object.",
                    },
                },
                is_error=True,
            )

        request = {
            **arguments,
            "operation": tool_name,
        }
        result = self.adapter.handle(request)

        return self._tool_result(
            payload=result,
            is_error=not bool(result.get("success")),
        )

    def _tool_result(self, payload: dict[str, Any], is_error: bool) -> dict[str, Any]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        payload,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    ),
                }
            ],
            "isError": is_error,
        }

    def _response(self, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _jsonrpc_error(
        self,
        request_id: Any,
        code: int,
        message: str,
    ) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }


def run_stdio() -> None:
    """Run the QASkills MCP server over newline-delimited stdio JSON-RPC."""

    server = QASkillsMCPServer()

    for line in sys.stdin:
        raw = line.strip()

        if not raw:
            continue

        try:
            message = json.loads(raw)
            response = server.handle_message(message)
        except Exception as error:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(error),
                },
            }

        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio()
