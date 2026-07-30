import re
from datetime import datetime
from pathlib import Path

from app.core.artifacts import Artifact, PipelineTrace
from app.index.manager import IndexManager
from app.index.models import IndexedDocument
from app.services.base import BaseService, ServiceRequest


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "in",
    "is",
    "me",
    "my",
    "of",
    "on",
    "show",
    "the",
    "to",
    "what",
    "with",
    "а",
    "в",
    "где",
    "для",
    "и",
    "как",
    "какие",
    "какой",
    "мне",
    "мы",
    "о",
    "об",
    "от",
    "по",
    "покажи",
    "про",
    "расскажи",
    "что",
}
QUERY_ALIASES = {
    "архитектура": ["architecture"],
    "архитектуре": ["architecture"],
    "архитектуру": ["architecture"],
    "архитектурные": ["architecture"],
    "индекс": ["index"],
    "индекса": ["index"],
    "миграция": ["migration"],
    "миграции": ["migration"],
    "миграцию": ["migration"],
    "проект": ["project", "qaskills"],
    "проекты": ["project", "qaskills"],
    "qa": ["qa"],
}
DAILY_KNOWLEDGE_CATEGORIES = {
    "open_questions": [
        "open question",
        "open questions",
        "question",
        "questions",
        "blocked",
        "blocker",
        "clarify",
        "уточнить",
        "вопрос",
        "вопросы",
        "открытые вопросы",
        "блокер",
    ],
    "yesterday_conclusions": [
        "yesterday",
        "conclusion",
        "conclusions",
        "итог",
        "итоги",
        "вывод",
        "выводы",
        "вчера",
    ],
    "test_ideas": [
        "test idea",
        "test ideas",
        "test cases",
        "checklist",
        "проверить",
        "тестовая идея",
        "тестовые идеи",
        "чеклист",
        "тест-кейсы",
        "сценарии",
    ],
}
DAILY_CATEGORY_LABELS = {
    "jira_keys": "Jira key notes",
    "projects": "Project knowledge",
    "open_questions": "Open questions",
    "yesterday_conclusions": "Yesterday's conclusions",
    "test_ideas": "Test ideas",
}


class MemoryDocument:
    """Markdown document loaded from the memory vault."""

    def __init__(self, info: IndexedDocument, content: str):
        self.info = info
        self.content = content

    def to_dict(self) -> dict:
        return {
            "info": self.info.to_dict(),
            "content": self.content,
        }


class MemoryService(BaseService):
    """Service for reading indexed Markdown documents from an Obsidian vault."""

    name = "Memory Service"
    capabilities = {
        "memory.list_documents": "List indexed Markdown documents.",
        "memory.read_document": "Read a Markdown document by path or name.",
        "memory.list_recent": "List recently modified Markdown documents.",
        "memory.search": "Search indexed Markdown metadata.",
        "memory.write_document": "Save a new Markdown note to the memory vault.",
        "memory.vault_structure": "Show indexed vault folder structure.",
    }

    def __init__(self, vault_path: str, index_path: str):
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.index_manager = IndexManager(
            vault_path=str(self.vault_path),
            index_path=index_path,
        )

    def execute(
        self,
        capability: str,
        request: ServiceRequest,
        trace: PipelineTrace | None = None,
    ) -> Artifact:
        if trace:
            trace.add(self.name, f"Executed capability {capability}")

        if capability == "memory.list_documents":
            return self._list_documents_artifact(request)

        if capability == "memory.read_document":
            return self._read_document_artifact(request)

        if capability == "memory.list_recent":
            return self._list_recent_artifact(request)

        if capability == "memory.search":
            return self._search_artifact(request)

        if capability == "memory.write_document":
            return self._write_document_artifact(request)

        if capability == "memory.vault_structure":
            return self._vault_structure_artifact()

        raise ValueError(f"Unsupported memory capability: {capability}")

    def rebuild_index(self) -> None:
        """Rebuild and persist the document index."""

        self.index_manager.rebuild()

    def list_documents(
        self,
        scope: str | None = None,
        project_name: str | None = None,
        tag: str | None = None,
        heading: str | None = None,
    ) -> list[IndexedDocument]:
        """Return indexed document metadata with optional metadata filters."""

        if tag:
            return self.index_manager.documents_with_tag(tag)

        if heading:
            return self.index_manager.documents_with_heading(heading)

        if scope == "projects" or project_name:
            return self.index_manager.documents_in_projects(project_name)

        return self.index_manager.documents()

    def read_document_by_path(self, path: str) -> MemoryDocument:
        """Read a Markdown document by vault-relative path."""

        document_info = self.index_manager.document_by_path(path)

        if not document_info:
            raise FileNotFoundError(path)

        return self._read_indexed_document(document_info)

    def read_document_by_name(self, name: str) -> MemoryDocument:
        """Read the first indexed document whose title, filename, or alias matches."""

        matches = self.index_manager.documents_by_name(
            self._normalize_document_name(name)
        )

        if not matches:
            raise FileNotFoundError(name)

        return self._read_indexed_document(
            sorted(matches, key=lambda document: document.path.lower())[0]
        )

    def list_recent(self, limit: int = 10) -> list[IndexedDocument]:
        """Return recently modified Markdown documents from saved metadata."""

        return self.index_manager.recent_documents(limit=limit)

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[tuple[int, IndexedDocument, list[str]]]:
        """Search indexed metadata and return ranked documents."""

        query_normalized = query.strip().lower()
        tokens = self._query_tokens(query)
        scored = []

        for document in self.index_manager.documents():
            score, reasons = self._score_document(document, query_normalized, tokens)

            if score:
                scored.append((score, document, reasons))

        return sorted(
            scored,
            key=lambda item: (-item[0], item[1].path.lower()),
        )[:limit]

    def write_document(
        self,
        title: str,
        content: str,
        folder: str = "QASkills/Memory/Inbox",
    ) -> IndexedDocument:
        """Persist a new Markdown note in the vault and refresh the index."""

        title = self._clean_title(title)
        content = content.strip()

        if not title:
            raise ValueError("Document title is required.")

        if not content:
            raise ValueError("Document content is required.")

        relative_folder = self._safe_relative_folder(folder)
        target_folder = self._resolve_relative_path(relative_folder)
        target_folder.mkdir(parents=True, exist_ok=True)

        file_path = self._unique_note_path(target_folder, title)
        file_path.write_text(
            self._note_text(title=title, content=content),
            encoding="utf-8",
        )

        self.rebuild_index()

        indexed = self.index_manager.document_by_path(
            str(file_path.relative_to(self.vault_path))
        )

        if not indexed:
            raise FileNotFoundError(str(file_path))

        return indexed

    def vault_structure(self) -> dict[str, int]:
        """Return folder-level Markdown counts from saved metadata."""

        return self.index_manager.vault_structure()

    def _list_documents_artifact(self, request: ServiceRequest) -> Artifact:
        scope = request.payload.get("scope")
        project_name = request.payload.get("project_name")
        tag = request.payload.get("tag")
        heading = request.payload.get("heading")
        documents = self.list_documents(
            scope=scope,
            project_name=project_name,
            tag=tag,
            heading=heading,
        )

        return Artifact(
            name="memory_documents",
            source=self.name,
            content=f"Found {len(documents)} indexed Markdown documents.",
            metadata={
                "capability": "memory.list_documents",
                "document_count": len(documents),
                "documents": [document.to_dict() for document in documents],
                "scope": scope,
                "project_name": project_name,
                "tag": tag,
                "heading": heading,
            },
        )

    def _read_document_artifact(self, request: ServiceRequest) -> Artifact:
        path = request.payload.get("path")
        name = request.payload.get("name")

        try:
            document = (
                self.read_document_by_path(str(path))
                if path
                else self.read_document_by_name(str(name or request.user_text))
            )
        except FileNotFoundError as error:
            return Artifact(
                name="memory_document_not_found",
                source=self.name,
                content=f"Document not found: {error.args[0]}",
                metadata={
                    "capability": "memory.read_document",
                    "found": False,
                    "path": path,
                    "name": name,
                },
            )

        return Artifact(
            name="memory_document",
            source=self.name,
            content=document.content,
            metadata={
                "capability": "memory.read_document",
                "found": True,
                "document": document.to_dict(),
            },
        )

    def _list_recent_artifact(self, request: ServiceRequest) -> Artifact:
        limit = int(request.payload.get("limit", 10))
        documents = self.list_recent(limit=limit)

        return Artifact(
            name="memory_recent_documents",
            source=self.name,
            content=f"Found {len(documents)} recently modified Markdown documents.",
            metadata={
                "capability": "memory.list_recent",
                "document_count": len(documents),
                "documents": [document.to_dict() for document in documents],
                "limit": limit,
            },
        )

    def _search_artifact(self, request: ServiceRequest) -> Artifact:
        if request.payload.get("mode") == "daily_context":
            return self._daily_context_artifact(request)

        query = str(request.payload.get("query") or request.user_text)
        limit = int(request.payload.get("limit", 5))
        results = self.search(query=query, limit=limit)
        lines = [f"Found {len(results)} source documents for: {query}"]

        for score, document, reasons in results:
            lines.append(
                (
                    f"- {document.title} ({document.path}); "
                    f"score {score}; match: {', '.join(reasons)}"
                )
            )

        return Artifact(
            name="memory_search_results",
            source=self.name,
            content="\n".join(lines),
            metadata={
                "capability": "memory.search",
                "query": query,
                "document_count": len(results),
                "results": [
                    {
                        "score": score,
                        "reasons": reasons,
                        "document": document.to_dict(),
                    }
                    for score, document, reasons in results
                ],
            },
        )

    def _daily_context_artifact(self, request: ServiceRequest) -> Artifact:
        limit = int(request.payload.get("limit", 12))
        issue_keys = self._daily_issue_keys(request)
        projects = self._daily_projects(request)
        categories: dict[str, list[dict]] = {
            key: []
            for key in DAILY_CATEGORY_LABELS
        }
        documents_by_path: dict[str, dict] = {}

        for document in self.index_manager.documents():
            content = self._safe_document_text(document)
            matches, score = self._daily_matches(
                document=document,
                content=content,
                issue_keys=issue_keys,
                projects=projects,
            )

            if not matches:
                continue

            document_entry = documents_by_path.setdefault(
                document.path,
                {
                    "title": document.title,
                    "path": document.path,
                    "score": 0,
                    "categories": [],
                    "snippets": [],
                },
            )
            document_entry["score"] += score

            for category, terms in matches.items():
                snippets = self._daily_snippets(
                    document=document,
                    content=content,
                    terms=terms,
                )
                category_entry = {
                    "title": document.title,
                    "path": document.path,
                    "score": score,
                    "matched_terms": terms,
                    "snippets": snippets,
                }
                categories[category].append(category_entry)

                if category not in document_entry["categories"]:
                    document_entry["categories"].append(category)

                for snippet in snippets:
                    if snippet not in document_entry["snippets"]:
                        document_entry["snippets"].append(snippet)

        for category, items in categories.items():
            categories[category] = sorted(
                items,
                key=lambda item: (-item["score"], item["path"].lower()),
            )[:limit]

        documents = sorted(
            documents_by_path.values(),
            key=lambda item: (-item["score"], item["path"].lower()),
        )[:limit]

        return Artifact(
            name="daily_memory_context",
            source=self.name,
            content="\n".join(
                self._daily_context_lines(
                    documents=documents,
                    categories=categories,
                    issue_keys=issue_keys,
                    projects=projects,
                )
            ),
            metadata={
                "capability": "memory.search",
                "mode": "daily_context",
                "document_count": len(documents),
                "documents": documents,
                "categories": categories,
                "issue_keys": sorted(issue_keys),
                "projects": sorted(projects),
            },
        )

    def _vault_structure_artifact(self) -> Artifact:
        structure = self.vault_structure()

        return Artifact(
            name="memory_vault_structure",
            source=self.name,
            content=f"Found {len(structure)} indexed folders.",
            metadata={
                "capability": "memory.vault_structure",
                "structure": structure,
            },
        )

    def _write_document_artifact(self, request: ServiceRequest) -> Artifact:
        title = str(request.payload.get("title") or "").strip()
        content = str(request.payload.get("content") or "").strip()
        folder = str(
            request.payload.get("folder")
            or "QASkills/Memory/Inbox"
        ).strip()

        try:
            document = self.write_document(
                title=title,
                content=content,
                folder=folder,
            )
        except ValueError as error:
            return Artifact(
                name="memory_write_failed",
                source=self.name,
                content=str(error),
                metadata={
                    "capability": "memory.write_document",
                    "saved": False,
                    "title": title,
                    "folder": folder,
                },
            )

        return Artifact(
            name="memory_document_saved",
            source=self.name,
            content=f"Saved note \"{document.title}\" to {document.path}.",
            metadata={
                "capability": "memory.write_document",
                "saved": True,
                "document": document.to_dict(),
            },
        )

    def _read_indexed_document(self, document: IndexedDocument) -> MemoryDocument:
        file_path = self._resolve_relative_path(document.path)

        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(document.path)

        return MemoryDocument(
            info=document,
            content=file_path.read_text(encoding="utf-8"),
        )

    def _resolve_relative_path(self, path: str) -> Path:
        file_path = (self.vault_path / path).resolve()

        if self.vault_path != file_path and self.vault_path not in file_path.parents:
            raise FileNotFoundError(path)

        return file_path

    def _safe_relative_folder(self, folder: str) -> str:
        normalized = folder.strip().strip("/")

        if not normalized:
            return "QASkills/Memory/Inbox"

        target = (self.vault_path / normalized).resolve()

        if self.vault_path != target and self.vault_path not in target.parents:
            raise ValueError("Folder must stay inside the memory vault.")

        return normalized

    def _clean_title(self, title: str) -> str:
        return title.strip().strip("#").strip()

    def _unique_note_path(self, folder: Path, title: str) -> Path:
        slug = self._slug(title)
        candidate = folder / f"{slug}.md"
        index = 2

        while candidate.exists():
            candidate = folder / f"{slug}-{index}.md"
            index += 1

        return candidate

    def _slug(self, title: str) -> str:
        slug = re.sub(r"[^A-Za-zА-Яа-я0-9 _-]+", "", title)
        slug = re.sub(r"\s+", " ", slug).strip()

        return slug or datetime.now().strftime("Knowledge Update %Y-%m-%d %H%M")

    def _note_text(self, title: str, content: str) -> str:
        created_at = datetime.now().isoformat(timespec="seconds")

        return "\n".join(
            [
                "---",
                "tags: [qaskills-memory]",
                f"created: {created_at}",
                "---",
                f"# {title}",
                "",
                content,
                "",
            ]
        )

    def _normalize_document_name(self, name: str) -> str:
        return name.strip().strip('"').strip("'")

    def _daily_issue_keys(self, request: ServiceRequest) -> set[str]:
        keys: set[str] = set()
        snapshots = self._artifact_named(request, "daily_snapshots")
        changes = self._artifact_named(request, "daily_change_report")

        if snapshots:
            for snapshot in [
                snapshots.metadata.get("current_snapshot", {}),
                snapshots.metadata.get("previous_snapshot") or {},
            ]:
                for issue in snapshot.get("assigned_issues", []):
                    key = str(issue.get("key") or "").strip()

                    if key:
                        keys.add(key)

        if changes:
            report = changes.metadata.get("change_report", {})

            for field in [
                "new_issues",
                "removed_issues",
                "closed_issues",
                "unchanged_stale_issues",
            ]:
                for issue in report.get(field, []):
                    key = str(issue.get("key") or "").strip()

                    if key:
                        keys.add(key)

            for field in [
                "status_changes",
                "assignee_changes",
                "priority_changes",
                "sprint_changes",
                "due_date_changes",
                "comment_count_changes",
                "description_changes",
            ]:
                for change in report.get(field, []):
                    key = str(change.get("key") or "").strip()

                    if key:
                        keys.add(key)

        return keys

    def _daily_projects(self, request: ServiceRequest) -> set[str]:
        projects: set[str] = set()
        snapshots = self._artifact_named(request, "daily_snapshots")

        if snapshots:
            for snapshot in [
                snapshots.metadata.get("current_snapshot", {}),
                snapshots.metadata.get("previous_snapshot") or {},
            ]:
                project = str(snapshot.get("project") or "").strip()

                if project:
                    projects.add(project)

                for issue in snapshot.get("assigned_issues", []):
                    issue_project = str(issue.get("project") or "").strip()

                    if issue_project:
                        projects.add(issue_project)

        for key in self._daily_issue_keys(request):
            if "-" in key:
                projects.add(key.split("-", 1)[0])

        return projects

    def _daily_matches(
        self,
        document: IndexedDocument,
        content: str,
        issue_keys: set[str],
        projects: set[str],
    ) -> tuple[dict[str, list[str]], int]:
        matches: dict[str, list[str]] = {}
        text = self._daily_search_text(document=document, content=content)
        score = 0
        key_matches = self._matched_terms(text, issue_keys)

        if key_matches:
            matches["jira_keys"] = key_matches
            score += 100 + len(key_matches) * 10

        project_matches = self._matched_terms(text, projects)

        if project_matches:
            matches["projects"] = project_matches
            score += 40 + len(project_matches) * 5

        for category, terms in DAILY_KNOWLEDGE_CATEGORIES.items():
            category_matches = self._matched_terms(text, set(terms))

            if category_matches:
                matches[category] = category_matches
                score += 30 + len(category_matches) * 5

        return matches, score

    def _daily_search_text(self, document: IndexedDocument, content: str) -> str:
        metadata_parts = [
            document.title,
            document.path,
            document.folder,
            *document.aliases,
            *document.tags,
            *[
                title
                for titles in document.headings.values()
                for title in titles
            ],
        ]

        return " ".join([*metadata_parts, content]).lower()

    def _matched_terms(self, text: str, terms: set[str]) -> list[str]:
        return sorted(
            {
                term
                for term in terms
                if term and term.lower() in text
            },
            key=lambda term: term.lower(),
        )

    def _safe_document_text(self, document: IndexedDocument) -> str:
        try:
            return self._read_indexed_document(document).content
        except FileNotFoundError:
            return ""

    def _daily_snippets(
        self,
        document: IndexedDocument,
        content: str,
        terms: list[str],
    ) -> list[str]:
        snippets: list[str] = []
        terms_lower = [term.lower() for term in terms]

        for line in content.splitlines():
            cleaned = line.strip().strip("-*").strip()

            if not cleaned or cleaned == "---":
                continue

            lowered = cleaned.lower()

            if any(term in lowered for term in terms_lower):
                snippets.append(cleaned)

            if len(snippets) >= 2:
                return snippets

        for title in [
            heading
            for headings in document.headings.values()
            for heading in headings
        ]:
            lowered = title.lower()

            if any(term in lowered for term in terms_lower):
                snippets.append(title)

            if len(snippets) >= 2:
                return snippets

        return snippets

    def _daily_context_lines(
        self,
        documents: list[dict],
        categories: dict[str, list[dict]],
        issue_keys: set[str],
        projects: set[str],
    ) -> list[str]:
        if not documents:
            return [
                "No related Obsidian knowledge found.",
                (
                    "Checked Jira keys, project names, open questions, "
                    "yesterday's conclusions, and test ideas."
                ),
            ]

        lines = [
            f"Found {len(documents)} related Obsidian knowledge source(s).",
            f"Jira keys checked: {', '.join(sorted(issue_keys)) or 'none'}",
            f"Projects checked: {', '.join(sorted(projects)) or 'none'}",
        ]

        for category, label in DAILY_CATEGORY_LABELS.items():
            items = categories.get(category, [])

            if items:
                lines.append(f"{label}: {len(items)}")

        return lines

    def _artifact_named(self, request: ServiceRequest, name: str) -> Artifact | None:
        for artifact in request.artifacts:
            if artifact.name == name:
                return artifact

        return None

    def _query_tokens(self, query: str) -> list[str]:
        import re

        raw_tokens = re.findall(r"[A-Za-zА-Яа-я0-9_#/-]+", query.lower())
        tokens = []

        for token in raw_tokens:
            normalized = token.strip().lstrip("#")

            if not normalized or normalized in STOP_WORDS:
                continue

            tokens.append(normalized)
            tokens.extend(QUERY_ALIASES.get(normalized, []))

        return list(dict.fromkeys(tokens))

    def _score_document(
        self,
        document: IndexedDocument,
        query: str,
        tokens: list[str],
    ) -> tuple[int, list[str]]:
        score = 0
        reasons = []
        fields = {
            "title": [document.title],
            "aliases": document.aliases,
            "headings": [
                title
                for titles in document.headings.values()
                for title in titles
            ],
            "tags": document.tags,
            "path": [document.path],
        }
        weights = {
            "title": 60,
            "aliases": 50,
            "headings": 40,
            "tags": 35,
            "path": 25,
        }

        for field, values in fields.items():
            joined = " ".join(values).lower()
            matched_terms = [token for token in tokens if token in joined]

            if query and query in joined:
                score += weights[field]
                reasons.append(field)
                continue

            if matched_terms:
                score += min(weights[field], weights[field] // 2 + len(matched_terms) * 5)
                reasons.append(field)

        return score, reasons
