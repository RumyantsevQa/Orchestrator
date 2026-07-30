from datetime import UTC, date, datetime

from app.core.artifacts import Artifact, PipelineTrace
from app.services.base import BaseService, ServiceRequest
from app.services.daily_models import ChangeReport, DailyIssueSnapshot, DailySnapshot


DAILY_MEMORY_CATEGORY_TITLES = {
    "jira_keys": "Linked Jira notes",
    "projects": "Project knowledge",
    "open_questions": "Open questions",
    "yesterday_conclusions": "Yesterday's conclusions",
    "test_ideas": "Test ideas",
}


class DailyBriefService(BaseService):
    """Builds a readable QA daily briefing from snapshots and factual changes."""

    name = "Daily Brief Service"
    capabilities = {
        "daily.prepare": "Prepare an analytical daily briefing from snapshot changes.",
    }

    def __init__(self, now: datetime | None = None):
        self.now = now

    def execute(
        self,
        capability: str,
        request: ServiceRequest,
        trace: PipelineTrace | None = None,
    ) -> Artifact:
        if trace:
            trace.add(self.name, f"Executed capability {capability}")

        if capability != "daily.prepare":
            raise ValueError(f"Unsupported daily capability: {capability}")

        return self._prepare(request)

    def _prepare(self, request: ServiceRequest) -> Artifact:
        blocking_error = self._first_artifact_named(
            request,
            ["daily_change_error", "daily_snapshot_error", "jira_error"],
        )

        if blocking_error:
            return Artifact(
                name="daily_brief",
                source=self.name,
                content=(
                    "Daily Brief unavailable.\n"
                    f"{blocking_error.content}\n\n"
                    "Suggested action: fix Jira configuration or connectivity, "
                    "then run qaskills prepare daily again."
                ),
                metadata={"success": False, "reason": blocking_error.name},
            )

        snapshots = self._artifact_named(request, "daily_snapshots")
        changes = self._artifact_named(request, "daily_change_report")

        if not snapshots or not changes:
            return Artifact(
                name="daily_brief",
                source=self.name,
                content=(
                    "Daily Brief unavailable.\n"
                    "Snapshot or change analysis data is missing from the pipeline."
                ),
                metadata={"success": False, "reason": "missing_daily_artifacts"},
            )

        current = DailySnapshot.from_dict(snapshots.metadata["current_snapshot"])
        previous_raw = snapshots.metadata.get("previous_snapshot")
        previous = DailySnapshot.from_dict(previous_raw) if previous_raw else None
        report = ChangeReport.from_dict(changes.metadata["change_report"])
        memory_context = self._artifact_named(request, "daily_memory_context")
        content = self._build_report(
            current=current,
            previous=previous,
            report=report,
            memory_context=memory_context,
        )

        return Artifact(
            name="daily_brief",
            source=self.name,
            content=content,
            metadata={
                "success": True,
                "has_history": report.has_history,
                "issue_count": len(current.assigned_issues),
                "new_count": len(report.new_issues),
                "closed_count": len(report.closed_issues),
                "stale_count": len(report.unchanged_stale_issues),
                "knowledge_source_count": (
                    memory_context.metadata.get("document_count", 0)
                    if memory_context
                    else 0
                ),
            },
        )

    def _build_report(
        self,
        current: DailySnapshot,
        previous: DailySnapshot | None,
        report: ChangeReport,
        memory_context: Artifact | None,
    ) -> str:
        first_name = "Ilya"
        sprint = self._sprint_name(current)
        lines = [
            f"🌅 Good morning, {first_name}",
            "",
            "Today's Daily Brief",
            "",
            f"Project: {current.project or 'Not detected'}",
            f"Sprint: {sprint or 'Not detected'}",
            f"Assigned: {len(current.assigned_issues)} issue{'' if len(current.assigned_issues) == 1 else 's'}",
            f"Snapshot: {self._friendly_timestamp(current.timestamp)}",
        ]

        if previous:
            lines.append(f"Compared with: {self._friendly_timestamp(previous.timestamp)}")

        lines.extend(["", "Current Work:"])
        lines.extend(self._issue_lines(current.assigned_issues))
        lines.extend(["", "Obsidian Knowledge:"])
        lines.extend(self._memory_context_lines(memory_context))

        if not report.has_history:
            lines.extend(
                [
                    "",
                    "Historical context:",
                    "• Insufficient historical data. This is the first saved Jira snapshot.",
                    "• QASkills will start detecting changes from the next run.",
                    "",
                    "Waiting:",
                ]
            )
            lines.extend(self._waiting_lines(report.unchanged_stale_issues))
            lines.extend(["", "Risks:"])
            lines.extend(self._risk_lines(current, report))
            lines.extend(["", "Suggested questions:"])
            lines.extend(self._question_lines(report))
            lines.extend(["", "Suggested Daily Report"])
            lines.append(
                '"Insufficient historical data. I saved the current Jira snapshot '
                'and will compare it with the next run. Today I will focus on the '
                'currently assigned Jira work."'
            )

            return "\n".join(lines)

        lines.extend(["", self._history_section_title(current, previous)])
        lines.extend(self._yesterday_lines(report))
        lines.extend(["", self._new_section_title(current, previous)])
        lines.extend(self._new_issue_lines(report.new_issues))
        lines.extend(["", "Removed from assignment:"])
        lines.extend(self._removed_issue_lines(report.removed_issues))
        lines.extend(["", "Changed:"])
        lines.extend(self._change_lines(report))
        lines.extend(["", "Waiting:"])
        lines.extend(self._waiting_lines(report.unchanged_stale_issues))
        lines.extend(["", "Risks:"])
        lines.extend(self._risk_lines(current, report))
        lines.extend(["", "Needs attention:"])
        lines.extend(self._attention_lines(current, report))
        lines.extend(["", "Suggested questions:"])
        lines.extend(self._question_lines(report))
        lines.extend(["", "Suggested Daily Report"])
        lines.append(self._suggested_daily_report(report))

        return "\n".join(lines)

    def _issue_lines(self, issues: list[DailyIssueSnapshot]) -> list[str]:
        if not issues:
            return ["• No Jira issues assigned to you right now."]

        return [
            (
                f"• {issue.key} {issue.summary}\n"
                f"  Status: {issue.status} | Priority: {issue.priority} | "
                f"Due: {issue.due_date or 'No due date'} | "
                f"Updated: {self._friendly_timestamp(issue.updated)}"
            )
            for issue in issues[:10]
        ]

    def _yesterday_lines(self, report: ChangeReport) -> list[str]:
        lines = []

        for issue in report.closed_issues:
            lines.append(f"• Closed {issue.key}: {issue.summary}")

        for change in report.status_changes:
            if any(issue.key == change.key for issue in report.closed_issues):
                continue

            lines.append(
                f"• {change.key} moved from {change.before or 'empty'} to {change.after or 'empty'}"
            )

        for issue in report.new_issues:
            lines.append(f"• New assignment {issue.key}: {issue.summary}")

        return lines or ["• No factual changes detected since the previous snapshot."]

    def _new_issue_lines(self, issues: list[DailyIssueSnapshot]) -> list[str]:
        if not issues:
            return ["• No new assigned issues detected."]

        return [f"• {issue.key} {issue.summary}" for issue in issues]

    def _removed_issue_lines(self, issues: list[DailyIssueSnapshot]) -> list[str]:
        if not issues:
            return ["• No issues disappeared from your assignment."]

        return [f"• {issue.key} {issue.summary}" for issue in issues]

    def _change_lines(self, report: ChangeReport) -> list[str]:
        lines = []
        grouped_changes = [
            ("Status", report.status_changes),
            ("Assignee", report.assignee_changes),
            ("Priority", report.priority_changes),
            ("Sprint", report.sprint_changes),
            ("Due date", report.due_date_changes),
            ("Comments", report.comment_count_changes),
            ("Description", report.description_changes),
        ]

        for label, changes in grouped_changes:
            for change in changes:
                before = "changed" if change.field == "description_hash" else change.before
                after = "changed" if change.field == "description_hash" else change.after
                lines.append(
                    f"• {label}: {change.key} {before or 'empty'} → {after or 'empty'}"
                )

        return lines or ["• No field-level changes detected."]

    def _waiting_lines(self, issues: list[DailyIssueSnapshot]) -> list[str]:
        if not issues:
            return ["• No long-unchanged assigned issues detected."]

        return [
            (
                f"• {issue.key} unchanged since "
                f"{self._friendly_timestamp(issue.updated)}: {issue.summary}"
            )
            for issue in issues
        ]

    def _risk_lines(
        self,
        current: DailySnapshot,
        report: ChangeReport,
    ) -> list[str]:
        risks = []
        high_priority_open = [
            issue
            for issue in current.assigned_issues
            if issue.priority.lower() in {"high", "highest", "critical"}
            and not self._is_done(issue)
        ]
        overdue = self._overdue_issues(current.assigned_issues)

        if high_priority_open:
            verb = "remains" if len(high_priority_open) == 1 else "remain"
            risks.append(
                (
                    f"• {len(high_priority_open)} high-priority assigned "
                    f"{self._plural(len(high_priority_open), 'issue')} {verb} open."
                )
            )

        if overdue:
            risks.append(
                f"• {len(overdue)} assigned {self._plural(len(overdue), 'issue')} are overdue."
            )

        if report.unchanged_stale_issues:
            risks.append(
                (
                    f"• {len(report.unchanged_stale_issues)} assigned "
                    f"{self._plural(len(report.unchanged_stale_issues), 'issue')} "
                    "have not changed for several days."
                )
            )

        if report.priority_changes:
            risks.append("• Priority changed since previous snapshot; re-check QA focus.")

        return risks or ["• No immediate Jira risks detected from snapshots."]

    def _attention_lines(
        self,
        current: DailySnapshot,
        report: ChangeReport,
    ) -> list[str]:
        attention = []

        for issue in self._overdue_issues(current.assigned_issues):
            attention.append(f"• {issue.key} is overdue: {issue.summary}")

        for issue in report.unchanged_stale_issues:
            attention.append(
                f"• {issue.key} has had no activity since {self._friendly_timestamp(issue.updated)}."
            )

        for change in report.priority_changes:
            attention.append(
                f"• {change.key} priority changed from {change.before} to {change.after}."
            )

        return attention or ["• No specific follow-up required from snapshot comparison."]

    def _question_lines(self, report: ChangeReport) -> list[str]:
        questions = []

        for issue in report.unchanged_stale_issues[:3]:
            questions.append(f"• Clarify current status for {issue.key}.")

        for change in report.due_date_changes[:3]:
            questions.append(f"• Confirm due date impact for {change.key}.")

        for change in report.assignee_changes[:3]:
            questions.append(f"• Confirm ownership change for {change.key}.")

        return questions or ["• No snapshot-backed questions suggested."]

    def _suggested_daily_report(self, report: ChangeReport) -> str:
        parts = []

        if report.closed_issues:
            closed = ", ".join(issue.key for issue in report.closed_issues[:3])
            parts.append(f"Since the previous snapshot, {closed} moved to done.")

        if report.status_changes:
            changed = ", ".join(change.key for change in report.status_changes[:3])
            parts.append(f"Status changed for {changed}.")

        if report.new_issues:
            new = ", ".join(issue.key for issue in report.new_issues[:3])
            parts.append(f"Newly assigned: {new}.")

        if report.unchanged_stale_issues:
            stale = ", ".join(issue.key for issue in report.unchanged_stale_issues[:3])
            verb = "has" if len(report.unchanged_stale_issues[:3]) == 1 else "have"
            parts.append(f"Needs attention: {stale} {verb} had no recent activity.")

        if not parts:
            parts.append("No factual Jira changes were detected since the previous snapshot.")

        return f'"{" ".join(parts)}"'

    def _memory_context_lines(self, artifact: Artifact | None) -> list[str]:
        if not artifact:
            return [
                "• No related Obsidian knowledge found.",
                (
                    "  Checked knowledge was not available in this pipeline run."
                ),
            ]

        document_count = int(artifact.metadata.get("document_count") or 0)

        if document_count == 0:
            return [
                "• No related Obsidian knowledge found.",
                (
                    "  Checked Jira keys, project notes, open questions, "
                    "yesterday's conclusions, and test ideas."
                ),
            ]

        lines = [f"• Found {document_count} related Obsidian source(s)."]
        categories = artifact.metadata.get("categories", {})

        for category, title in DAILY_MEMORY_CATEGORY_TITLES.items():
            items = categories.get(category, [])

            if not items:
                continue

            lines.append(f"• {title}:")

            for item in items[:3]:
                lines.append(f"  - {item['title']} ({item['path']})")
                snippets = item.get("snippets") or []

                if snippets:
                    lines.append(f"    Evidence: {snippets[0]}")
                    continue

                matched_terms = item.get("matched_terms") or []

                if matched_terms:
                    lines.append(f"    Match: {', '.join(matched_terms[:3])}")

        return lines

    def _history_section_title(
        self,
        current: DailySnapshot,
        previous: DailySnapshot | None,
    ) -> str:
        if previous and self._is_previous_day(current.timestamp, previous.timestamp):
            return "Yesterday:"

        return "Since previous snapshot:"

    def _new_section_title(
        self,
        current: DailySnapshot,
        previous: DailySnapshot | None,
    ) -> str:
        if previous and self._is_previous_day(current.timestamp, previous.timestamp):
            return "New today:"

        return "New since previous snapshot:"

    def _overdue_issues(self, issues: list[DailyIssueSnapshot]) -> list[DailyIssueSnapshot]:
        today = self._now().date()
        overdue = []

        for issue in issues:
            due_date = self._parse_date(issue.due_date)

            if due_date and due_date < today and not self._is_done(issue):
                overdue.append(issue)

        return overdue

    def _first_artifact_named(
        self,
        request: ServiceRequest,
        names: list[str],
    ) -> Artifact | None:
        for name in names:
            artifact = self._artifact_named(request, name)

            if artifact:
                return artifact

        return None

    def _artifact_named(self, request: ServiceRequest, name: str) -> Artifact | None:
        for artifact in request.artifacts:
            if artifact.name == name:
                return artifact

        return None

    def _sprint_name(self, snapshot: DailySnapshot) -> str:
        for issue in snapshot.assigned_issues:
            if issue.sprint:
                return issue.sprint

        return ""

    def _is_done(self, issue: DailyIssueSnapshot) -> bool:
        return issue.status_category.lower() == "done" or issue.status.lower() in {
            "done",
            "closed",
            "готово",
            "закрыто",
            "выполнено",
        }

    def _friendly_timestamp(self, value: str) -> str:
        parsed = self._parse_datetime(value)

        if not parsed:
            return value or "Unknown"

        return parsed.date().isoformat()

    def _parse_date(self, value: str) -> date | None:
        if not value:
            return None

        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _parse_datetime(self, value: str) -> datetime | None:
        if not value:
            return None

        text = value.replace("Z", "+00:00")

        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    def _is_previous_day(self, current: str, previous: str) -> bool:
        current_date = self._parse_datetime(current)
        previous_date = self._parse_datetime(previous)

        if not current_date or not previous_date:
            return False

        return (current_date.date() - previous_date.date()).days == 1

    def _plural(self, count: int, word: str) -> str:
        return word if count == 1 else f"{word}s"

    def _now(self) -> datetime:
        return self.now or datetime.now(UTC)
