from app.core.artifacts import Artifact, PipelineTrace
from app.core.intent import UserIntent
from app.core.models import OrchestratorResponse, UserRequest
from app.core.task_plan import TaskPlan


class ResponseComposer:
    """Builds the final response returned to the user."""

    def compose(
        self,
        request: UserRequest,
        intent: UserIntent,
        plan: TaskPlan,
        artifacts: list[Artifact],
        llm_artifact: Artifact | None,
        trace: PipelineTrace,
    ) -> OrchestratorResponse:
        trace.add("Response Composer", "Composed final user response")

        message = (
            self._compose_generated_response(llm_artifact, artifacts)
            if llm_artifact
            else self._compose_service_response(artifacts)
        )

        return OrchestratorResponse(
            success=True,
            message=message,
            data={
                "request": request.text,
                "intent": {
                    "name": intent.name,
                    "expected_output": intent.expected_output,
                    "confidence": intent.confidence,
                },
                "plan": plan.to_dict(),
                "artifacts": [artifact.to_dict() for artifact in artifacts],
                "llm_artifact": llm_artifact.to_dict() if llm_artifact else None,
                "pipeline": trace.to_dicts(),
            },
        )

    def _compose_service_response(self, artifacts: list[Artifact]) -> str:
        if not artifacts:
            return "No service artifacts were produced."

        if len(artifacts) == 1 and artifacts[0].source == "Memory Service":
            return self._compose_memory_response(artifacts[0])

        if len(artifacts) == 1 and artifacts[0].source == "Jira Service":
            return artifacts[0].content

        daily_brief = self._artifact_named(artifacts, "daily_brief")

        if daily_brief:
            return daily_brief.content

        search_artifact = self._artifact_named(artifacts, "memory_search_results")

        if search_artifact:
            if len(artifacts) == 1:
                return self._compose_source_pack_response(search_artifact)

            return self._compose_workspace_response(search_artifact, artifacts)

        lines = ["Service results:"]
        lines.extend(
            f"- {artifact.source}: {artifact.content}"
            for artifact in artifacts
        )

        return "\n".join(lines)

    def _compose_generated_response(
        self,
        llm_artifact: Artifact,
        artifacts: list[Artifact],
    ) -> str:
        lines = [llm_artifact.content]

        provider_success = llm_artifact.metadata.get("provider_success")
        provider = llm_artifact.metadata.get("provider")
        provider_error = llm_artifact.metadata.get("provider_error")

        if provider_success is False:
            lines.append("")
            lines.append("Provider status:")
            lines.append(f"- {provider}: {provider_error or 'unavailable'}")

        skill_artifact = self._artifact_named(artifacts, "skill_guidance")

        if skill_artifact and provider_success is False:
            lines.append("")
            lines.append("Skill guidance:")
            lines.append(skill_artifact.content)

        workspace_artifacts = self._workspace_artifacts(artifacts)

        if workspace_artifacts and provider_success is False:
            lines.append("")
            lines.append("Workspace artifacts:")
            lines.extend(
                f"- {artifact.source}: {artifact.content}"
                for artifact in workspace_artifacts
            )

        search_artifact = self._artifact_named(artifacts, "memory_search_results")

        if search_artifact:
            lines.append("")
            lines.append(self._compose_source_pack_response(search_artifact))

        return "\n".join(lines)

    def _compose_memory_response(self, artifact: Artifact) -> str:
        if artifact.name == "memory_vault_structure":
            structure = artifact.metadata.get("structure", {})

            if not structure:
                return "Структура Vault: ничего не найдено."

            visible_items = self._visible_vault_structure_items(structure)
            shown_items = visible_items[:30]
            hidden_count = len(visible_items) - len(shown_items)
            lines = [
                (
                    f"Структура Vault: {len(structure)} папок "
                    f"(показано {len(shown_items)} пользовательских)"
                )
            ]

            for folder, count in shown_items:
                lines.append(f"- {folder}: {count} markdown-файлов")

            if hidden_count > 0:
                lines.append(f"...и ещё {hidden_count} папок.")

            return "\n".join(lines)

        if artifact.name in {"memory_documents", "memory_recent_documents"}:
            documents = artifact.metadata.get("documents", [])
            title = (
                "Последние документы"
                if artifact.name == "memory_recent_documents"
                else "Документы"
            )

            if artifact.metadata.get("scope") == "projects":
                title = "Проекты"

            if artifact.metadata.get("project_name"):
                title = f"Документы проекта {artifact.metadata['project_name']}"

            if artifact.metadata.get("tag"):
                title = f"Документы с тегом {artifact.metadata['tag']}"

            if artifact.metadata.get("heading"):
                title = f"Документы с заголовком {artifact.metadata['heading']}"

            if not documents:
                return f"{title}: ничего не найдено."

            lines = [f"{title}: {len(documents)}"]

            for document in documents[:20]:
                lines.append(
                    (
                        f"- {document['title']} "
                        f"({document['path']}, {document['size']} bytes, "
                        f"modified {document['modified_at']})"
                    )
                )

            if len(documents) > 20:
                lines.append(f"...и ещё {len(documents) - 20}.")

            return "\n".join(lines)

        if artifact.name == "memory_document":
            document = artifact.metadata["document"]
            info = document["info"]

            return "\n".join(
                [
                    f"Документ: {info['title']}",
                    f"Путь: {info['path']}",
                    f"Папка: {info['folder'] or '.'}",
                    f"Размер: {info['size']} bytes",
                    f"Изменён: {info['modified_at']}",
                    "",
                    document["content"],
                ]
            )

        if artifact.name == "memory_document_not_found":
            return artifact.content

        if artifact.name == "memory_search_results":
            return self._compose_source_pack_response(artifact)

        if artifact.name in {"memory_document_saved", "memory_write_failed"}:
            return artifact.content

        return artifact.content

    def _compose_workspace_response(
        self,
        search_artifact: Artifact,
        artifacts: list[Artifact],
    ) -> str:
        lines = [
            self._compose_source_pack_response(search_artifact),
            "",
            "Workspace Results",
        ]

        for artifact in self._workspace_artifacts(artifacts):
            lines.append(f"- {artifact.source}:")
            lines.extend(f"  {line}" for line in artifact.content.splitlines())

        return "\n".join(lines)

    def _workspace_artifacts(self, artifacts: list[Artifact]) -> list[Artifact]:
        return [
            artifact
            for artifact in artifacts
            if artifact.name not in {"memory_search_results", "skill_guidance"}
        ]

    def _compose_source_pack_response(self, artifact: Artifact) -> str:
        query = artifact.metadata.get("query", "")
        results = artifact.metadata.get("results", [])

        if not results:
            return (
                "Source Pack\n"
                "Источники не найдены в локальном индексе.\n"
                f"Query: {query}"
            )

        lines = [
            "Source Pack",
            f"Question: {query}",
            f"Found {len(results)} source documents.",
            "",
            "Key Sources",
        ]

        for index, result in enumerate(results[:3], start=1):
            document = result["document"]
            lines.append(f"{index}. {document['title']}")
            lines.append(f"   path: {document['path']}")
            lines.append(
                f"   score {result['score']} · match: {', '.join(result['reasons'])}"
            )

            if document.get("tags"):
                lines.append(f"   tags: {', '.join(document['tags'])}")

        groups: dict[str, list[dict]] = {}

        for result in results:
            document = result["document"]
            groups.setdefault(self._source_group(document), []).append(result)

        lines.append("")
        lines.append("Grouped Sources")

        for group, group_results in groups.items():
            lines.append(f"{group} ({len(group_results)})")

            for result in group_results:
                document = result["document"]
                lines.append(f"  - {document['title']} — {document['path']}")

        lines.append("")
        lines.append("Recommended Reading Order")

        for index, result in enumerate(results, start=1):
            document = result["document"]
            lines.append(f"{index}. {document['title']} — {document['path']}")

        return "\n".join(lines)

    def _source_group(self, document: dict) -> str:
        path = str(document.get("path", "")).lower()
        tags = {str(tag).lower() for tag in document.get("tags", [])}
        title = str(document.get("title", "")).lower()

        if "memory/projects" in path or "project" in tags:
            return "Project Memory"

        if "investigations" in path or "investigation" in tags or "audit" in tags:
            return "Investigations"

        if "03 architecture" in path or "architecture" in tags or title.startswith("adr"):
            return "Architecture"

        if "knowledge" in path:
            return "Knowledge Base"

        return "Reference"

    def _artifact_named(
        self,
        artifacts: list[Artifact],
        name: str,
    ) -> Artifact | None:
        for artifact in artifacts:
            if artifact.name == name:
                return artifact

        return None

    def _visible_vault_structure_items(
        self,
        structure: dict[str, int],
    ) -> list[tuple[str, int]]:
        items = [
            (folder, count)
            for folder, count in structure.items()
            if self._is_user_facing_folder(folder)
        ]

        return items or list(structure.items())[:30]

    def _is_user_facing_folder(self, folder: str) -> bool:
        technical_parts = {
            ".agents",
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".qaos",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "site-packages",
        }
        parts = folder.split("/")

        return not any(
            part.startswith(".qaos")
            or part in technical_parts
            or part.endswith(".dist-info")
            for part in parts
        )
