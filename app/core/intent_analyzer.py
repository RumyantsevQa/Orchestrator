import re

from app.core.models import UserRequest
from app.core.intent import UserIntent


class IntentAnalyzer:
    """
    Converts a raw user request into a normalized intent.

    The analyzer does not call services and does not decide how the work
    should be executed. It only labels the request for the planner.
    """

    def analyze(self, request: UserRequest) -> UserIntent:
        text = request.text.strip()
        normalized = text.lower()
        issue_key = self._issue_key(text)

        if request.metadata.get("action") == "daily.prepare" or normalized in {
            "prepare daily",
            "daily prepare",
            "подготовка к дейли",
            "подготовь daily",
            "подготовь дейли",
        }:
            return UserIntent(
                name="daily_briefing",
                raw_text=text,
                expected_output="daily_brief",
                confidence=0.95,
                metadata={"query": text},
            )

        if (
            self._looks_like_memory_write(normalized)
            or request.metadata.get("action") == "memory.write"
        ):
            content = str(
                request.metadata.get("content")
                or self._memory_content(text)
            ).strip()
            title = str(
                request.metadata.get("title")
                or self._suggest_title(content or text)
            ).strip()

            return UserIntent(
                name="knowledge_update",
                raw_text=text,
                expected_output="memory_saved",
                confidence=0.85,
                metadata={
                    "title": title,
                    "content": content,
                },
            )

        if ("мои" in normalized and "задач" in normalized) or "my tasks" in normalized:
            return UserIntent(
                name="jira_list_my_tasks",
                raw_text=text,
                expected_output="jira_task_list",
                confidence=0.8,
                metadata={"query": text},
            )

        if "bug report" in normalized or "баг репорт" in normalized:
            return UserIntent(
                name="jira_bug_report",
                raw_text=text,
                expected_output="bug_report_draft",
                confidence=0.8,
                metadata={"issue_key": issue_key, "query": text},
            )

        if "jira" in normalized or issue_key:
            if "whoami" in normalized or "кто я" in normalized:
                return UserIntent(
                    name="jira_whoami",
                    raw_text=text,
                    expected_output="jira_user",
                    confidence=0.95,
                    metadata={"query": text},
                )

            if "projects" in normalized or "проекты" in normalized:
                return UserIntent(
                    name="jira_list_projects",
                    raw_text=text,
                    expected_output="jira_projects",
                    confidence=0.95,
                    metadata={"query": text},
                )

            if " issue " in f" {normalized} " or " задача " in f" {normalized} ":
                return UserIntent(
                    name="jira_get_issue",
                    raw_text=text,
                    expected_output="jira_issue",
                    confidence=0.95,
                    metadata={"issue_key": issue_key, "query": text},
                )

            if "дейли" in normalized or "daily" in normalized:
                return UserIntent(
                    name="jira_daily_issue",
                    raw_text=text,
                    expected_output="jira_daily_context",
                    confidence=0.85,
                    metadata={"issue_key": issue_key, "query": text},
                )

            if "bug report" in normalized or "баг" in normalized:
                return UserIntent(
                    name="jira_bug_report",
                    raw_text=text,
                    expected_output="bug_report_draft",
                    confidence=0.85,
                    metadata={"issue_key": issue_key, "query": text},
                )

            if "анализ" in normalized or "проанализ" in normalized or "analyze" in normalized:
                return UserIntent(
                    name="jira_analyze_issue",
                    raw_text=text,
                    expected_output="jira_issue_analysis",
                    confidence=0.85,
                    metadata={"issue_key": issue_key, "query": text},
                )

            if "мои" in normalized and ("задач" in normalized or "tasks" in normalized):
                return UserIntent(
                    name="jira_list_my_tasks",
                    raw_text=text,
                    expected_output="jira_task_list",
                    confidence=0.8,
                    metadata={"query": text},
                )

            return UserIntent(
                name="jira_find_issue",
                raw_text=text,
                expected_output="jira_issue",
                confidence=0.8,
                metadata={"issue_key": issue_key, "query": text},
            )

        if "анализ" in normalized and "встреч" in normalized:
            return UserIntent(
                name="meeting_analysis",
                raw_text=text,
                expected_output="meeting_analysis",
                confidence=0.85,
                metadata={"query": text},
            )

        if "проанализ" in normalized and ("задач" in normalized or "task" in normalized):
            return UserIntent(
                name="task_analysis",
                raw_text=text,
                expected_output="task_analysis",
                confidence=0.85,
                metadata={"query": text},
            )

        if "структур" in normalized and "vault" in normalized:
            return UserIntent(
                name="memory_vault_structure",
                raw_text=text,
                expected_output="memory_vault_structure",
                confidence=0.9,
            )

        if "документ" in normalized and "проект" in normalized:
            return UserIntent(
                name="memory_list_project_documents",
                raw_text=text,
                expected_output="memory_document_list",
                confidence=0.9,
                metadata={
                    "project_name": self._after_any_marker(
                        text,
                        ["проекта", "проект"],
                    )
                },
            )

        if "документ" in normalized and "тег" in normalized:
            return UserIntent(
                name="memory_list_tagged_documents",
                raw_text=text,
                expected_output="memory_document_list",
                confidence=0.9,
                metadata={"tag": self._after_any_marker(text, ["тегом", "тег"])},
            )

        if "документ" in normalized and "заголов" in normalized:
            return UserIntent(
                name="memory_list_heading_documents",
                raw_text=text,
                expected_output="memory_document_list",
                confidence=0.9,
                metadata={
                    "heading": self._after_any_marker(
                        text,
                        ["заголовком", "заголовок"],
                    )
                },
            )

        if "последн" in normalized and "документ" in normalized:
            return UserIntent(
                name="memory_list_recent",
                raw_text=text,
                expected_output="memory_recent_documents",
                confidence=0.9,
            )

        if "проект" in normalized:
            return UserIntent(
                name="memory_list_projects",
                raw_text=text,
                expected_output="memory_document_list",
                confidence=0.85,
                metadata={"scope": "projects"},
            )

        if "документ" in normalized:
            return UserIntent(
                name="memory_read_document",
                raw_text=text,
                expected_output="memory_document",
                confidence=0.85,
                metadata={"document_name": self._document_name(text)},
            )

        if "дейли" in normalized or "daily" in normalized:
            return UserIntent(
                name="daily_preparation",
                raw_text=text,
                expected_output="daily_briefing",
                confidence=0.9,
            )

        if normalized.startswith("ask "):
            return UserIntent(
                name="knowledge_question",
                raw_text=text,
                expected_output="answer_with_sources",
                confidence=0.9,
                metadata={"query": text[4:].strip()},
            )

        if self._looks_like_search(normalized):
            return UserIntent(
                name="memory_search",
                raw_text=text,
                expected_output="source_pack",
                confidence=0.8,
                metadata={"query": self._search_query(text)},
            )

        if self._looks_like_question(normalized):
            return UserIntent(
                name="knowledge_question",
                raw_text=text,
                expected_output="answer_with_sources",
                confidence=0.8,
                metadata={"query": text},
            )

        return UserIntent(
            name="general_request",
            raw_text=text,
            expected_output="answer",
            confidence=0.6,
        )

    def _document_name(self, text: str) -> str:
        normalized = text.strip()

        for marker in [
            "Открой документ",
            "открой документ",
            "Покажи документ",
            "покажи документ",
            "Прочитай документ",
            "прочитай документ",
        ]:
            if normalized.startswith(marker):
                return normalized[len(marker) :].strip()

        return normalized

    def _after_marker(self, text: str, marker: str) -> str:
        normalized = text.strip()
        lower = normalized.lower()
        index = lower.rfind(marker.lower())

        if index == -1:
            return normalized

        return normalized[index + len(marker) :].strip().strip('"').strip("'")

    def _after_any_marker(self, text: str, markers: list[str]) -> str:
        for marker in markers:
            value = self._after_marker(text, marker)

            if value != text.strip().strip('"').strip("'"):
                return value

        return text.strip().strip('"').strip("'")

    def _looks_like_search(self, normalized: str) -> bool:
        return normalized.startswith(("найди ", "искать ", "find ", "search "))

    def _search_query(self, text: str) -> str:
        stripped = text.strip()
        lower = stripped.lower()

        for marker in ["найди", "искать", "find", "search"]:
            if lower.startswith(marker):
                return stripped[len(marker) :].strip()

        return stripped

    def _looks_like_question(self, normalized: str) -> bool:
        if normalized.endswith("?"):
            return True

        return normalized.startswith(
            (
                "что ",
                "как ",
                "почему ",
                "зачем ",
                "где ",
                "когда ",
                "what ",
                "how ",
                "why ",
                "where ",
                "when ",
            )
        )

    def _looks_like_memory_write(self, normalized: str) -> bool:
        return normalized.startswith(
            (
                "запомни",
                "сохрани вывод",
                "сохрани это",
                "добавь в память",
                "remember ",
                "save this",
            )
        )

    def _memory_content(self, text: str) -> str:
        stripped = text.strip()
        lowered = stripped.lower()

        for marker in [
            "запомни это",
            "запомни",
            "сохрани вывод",
            "сохрани это",
            "добавь в память",
            "remember this",
            "remember",
            "save this",
        ]:
            if lowered.startswith(marker):
                return stripped[len(marker) :].strip().lstrip(":").strip()

        return ""

    def _suggest_title(self, text: str) -> str:
        first_line = text.strip().splitlines()[0] if text.strip() else "Knowledge Update"
        title = first_line.strip("# ").strip()

        return title[:80] if title else "Knowledge Update"

    def _issue_key(self, text: str) -> str:
        match = re.search(r"(?<![A-Z0-9-])([A-Z][A-Z0-9]+-\d+)\b", text.upper())

        return match.group(1) if match else ""
