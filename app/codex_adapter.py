from typing import Any

from app.knowledge_api import KnowledgeAPI


SUPPORTED_OPERATIONS = {
    "build_context",
    "ingest",
    "list_skills",
    "read",
    "search",
    "show_skill",
}


class CodexAdapter:
    """
    Thin structured entrypoint for external AI agents.

    The adapter does not analyze natural language, make product decisions, or
    know how knowledge is collected. It validates a structured request, routes
    it to KnowledgeAPI, and returns a consistent response envelope.
    """

    def __init__(self, knowledge_api: KnowledgeAPI | None = None):
        self.knowledge_api = knowledge_api or KnowledgeAPI()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        """Route a structured Codex request to the matching KnowledgeAPI operation."""

        if not isinstance(request, dict):
            return self._error(
                operation="",
                error_type="invalid_request",
                message="Request must be a dictionary.",
            )

        operation = str(request.get("operation") or "").strip()

        if not operation:
            return self._error(
                operation="",
                error_type="missing_operation",
                message="Field 'operation' is required.",
            )

        if operation not in SUPPORTED_OPERATIONS:
            return self._error(
                operation=operation,
                error_type="unsupported_operation",
                message=f"Unsupported operation: {operation}.",
            )

        try:
            data = self._dispatch(operation=operation, request=request)
        except FileNotFoundError as error:
            return self._error(
                operation=operation,
                error_type="not_found",
                message=str(error),
            )
        except ValueError as error:
            return self._error(
                operation=operation,
                error_type="invalid_request",
                message=str(error),
            )
        except Exception as error:
            return self._error(
                operation=operation,
                error_type="adapter_error",
                message=str(error),
            )

        return {
            "success": True,
            "operation": operation,
            "data": data,
            "error": None,
        }

    def _dispatch(self, operation: str, request: dict[str, Any]) -> Any:
        if operation == "build_context":
            payload = {
                key: value
                for key, value in request.items()
                if key != "operation"
            }
            return self.knowledge_api.build_context(payload)

        if operation == "search":
            return self.knowledge_api.search(
                query=self._required_text(request, "query"),
                limit=int(request.get("limit") or 5),
            )

        if operation == "read":
            return self.knowledge_api.read(
                self._first_required_text(request, ("path_or_name", "path", "name"))
            )

        if operation == "ingest":
            file_path = self._required_text(request, "file_path")
            target_folder = str(request.get("target_folder") or "").strip()

            if target_folder:
                return self.knowledge_api.ingest(
                    file_path=file_path,
                    target_folder=target_folder,
                )

            return self.knowledge_api.ingest(file_path=file_path)

        if operation == "list_skills":
            return self.knowledge_api.list_skills()

        if operation == "show_skill":
            return self.knowledge_api.show_skill(
                self._first_required_text(request, ("skill_name", "name"))
            )

        raise ValueError(f"Unsupported operation: {operation}.")

    def _required_text(self, request: dict[str, Any], field: str) -> str:
        value = str(request.get(field) or "").strip()

        if not value:
            raise ValueError(f"Field '{field}' is required for this operation.")

        return value

    def _first_required_text(
        self,
        request: dict[str, Any],
        fields: tuple[str, ...],
    ) -> str:
        for field in fields:
            value = str(request.get(field) or "").strip()

            if value:
                return value

        joined = "', '".join(fields)
        raise ValueError(f"One of '{joined}' is required for this operation.")

    def _error(
        self,
        operation: str,
        error_type: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "operation": operation,
            "data": None,
            "error": {
                "type": error_type,
                "message": message,
            },
        }
