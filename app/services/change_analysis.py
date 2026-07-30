from datetime import UTC, datetime, timedelta

from app.core.artifacts import Artifact, PipelineTrace
from app.services.base import BaseService, ServiceRequest
from app.services.daily_models import (
    ChangeReport,
    DailyIssueSnapshot,
    DailySnapshot,
    IssueFieldChange,
)


class ChangeAnalysisService(BaseService):
    """Compares previous and current daily snapshots and reports factual changes."""

    name = "Change Analysis Service"
    capabilities = {
        "change.daily.analyze": "Compare daily snapshots and produce a change report.",
    }

    def __init__(self, now: datetime | None = None, stale_days: int = 3):
        self.now = now
        self.stale_days = stale_days

    def execute(
        self,
        capability: str,
        request: ServiceRequest,
        trace: PipelineTrace | None = None,
    ) -> Artifact:
        if trace:
            trace.add(self.name, f"Executed capability {capability}")

        if capability != "change.daily.analyze":
            raise ValueError(f"Unsupported change capability: {capability}")

        return self._analyze(request)

    def _analyze(self, request: ServiceRequest) -> Artifact:
        snapshot_error = self._artifact_named(request, "daily_snapshot_error")

        if snapshot_error:
            return Artifact(
                name="daily_change_error",
                source=self.name,
                content=f"Daily changes were not analyzed: {snapshot_error.content}",
                metadata={
                    "success": False,
                    "reason": snapshot_error.metadata.get("reason", "snapshot_error"),
                    "error": snapshot_error.content,
                },
            )

        snapshot_artifact = self._artifact_named(request, "daily_snapshots")

        if not snapshot_artifact:
            return Artifact(
                name="daily_change_error",
                source=self.name,
                content="Daily changes were not analyzed: snapshots were not collected.",
                metadata={"success": False, "reason": "missing_snapshots"},
            )

        current = DailySnapshot.from_dict(
            snapshot_artifact.metadata["current_snapshot"]
        )
        previous_raw = snapshot_artifact.metadata.get("previous_snapshot")
        previous = DailySnapshot.from_dict(previous_raw) if previous_raw else None
        report = self.compare(current=current, previous=previous)

        return Artifact(
            name="daily_change_report",
            source=self.name,
            content=self._summary(report),
            metadata={
                "success": True,
                "change_report": report.to_dict(),
            },
        )

    def compare(
        self,
        current: DailySnapshot,
        previous: DailySnapshot | None,
    ) -> ChangeReport:
        """Return factual differences between two snapshots."""

        stale = self._stale_issues(current.assigned_issues)

        if previous is None:
            return ChangeReport(
                has_history=False,
                current_timestamp=current.timestamp,
                unchanged_stale_issues=stale,
            )

        current_by_key = current.issues_by_key()
        previous_by_key = previous.issues_by_key()
        new_keys = sorted(set(current_by_key) - set(previous_by_key))
        removed_keys = sorted(set(previous_by_key) - set(current_by_key))
        common_keys = sorted(set(current_by_key) & set(previous_by_key))
        status_changes = self._field_changes(
            common_keys,
            previous_by_key,
            current_by_key,
            "status",
        )

        return ChangeReport(
            has_history=True,
            current_timestamp=current.timestamp,
            previous_timestamp=previous.timestamp,
            new_issues=[current_by_key[key] for key in new_keys],
            removed_issues=[previous_by_key[key] for key in removed_keys],
            closed_issues=[
                current_by_key[change.key]
                for change in status_changes
                if not self._is_done_status(change.before)
                and self._is_done_status(change.after)
            ],
            status_changes=status_changes,
            assignee_changes=self._field_changes(
                common_keys,
                previous_by_key,
                current_by_key,
                "assignee",
            ),
            priority_changes=self._field_changes(
                common_keys,
                previous_by_key,
                current_by_key,
                "priority",
            ),
            sprint_changes=self._field_changes(
                common_keys,
                previous_by_key,
                current_by_key,
                "sprint",
            ),
            due_date_changes=self._field_changes(
                common_keys,
                previous_by_key,
                current_by_key,
                "due_date",
            ),
            comment_count_changes=self._field_changes(
                common_keys,
                previous_by_key,
                current_by_key,
                "comment_count",
            ),
            description_changes=self._field_changes(
                common_keys,
                previous_by_key,
                current_by_key,
                "description_hash",
            ),
            unchanged_stale_issues=stale,
        )

    def _field_changes(
        self,
        keys: list[str],
        previous_by_key: dict[str, DailyIssueSnapshot],
        current_by_key: dict[str, DailyIssueSnapshot],
        field: str,
    ) -> list[IssueFieldChange]:
        changes = []

        for key in keys:
            before = getattr(previous_by_key[key], field)
            after = getattr(current_by_key[key], field)

            if before == after:
                continue

            changes.append(
                IssueFieldChange(
                    key=key,
                    summary=current_by_key[key].summary,
                    field=field,
                    before=str(before or ""),
                    after=str(after or ""),
                )
            )

        return changes

    def _stale_issues(
        self,
        issues: list[DailyIssueSnapshot],
    ) -> list[DailyIssueSnapshot]:
        cutoff = self._now() - timedelta(days=self.stale_days)

        return [
            issue
            for issue in issues
            if not self._is_done_issue(issue)
            and self._updated_value(issue)
            and self._updated_value(issue) < cutoff
        ]

    def _summary(self, report: ChangeReport) -> str:
        if not report.has_history:
            return "Insufficient historical data. Current snapshot was saved."

        change_count = sum(
            [
                len(report.new_issues),
                len(report.removed_issues),
                len(report.status_changes),
                len(report.assignee_changes),
                len(report.priority_changes),
                len(report.sprint_changes),
                len(report.due_date_changes),
                len(report.comment_count_changes),
                len(report.description_changes),
            ]
        )

        return f"Detected {change_count} factual changes since previous snapshot."

    def _artifact_named(self, request: ServiceRequest, name: str) -> Artifact | None:
        for artifact in request.artifacts:
            if artifact.name == name:
                return artifact

        return None

    def _is_done_issue(self, issue: DailyIssueSnapshot) -> bool:
        return (
            issue.status_category.lower() == "done"
            or self._is_done_status(issue.status)
        )

    def _is_done_status(self, status: str) -> bool:
        return status.strip().lower() in {
            "done",
            "closed",
            "готово",
            "закрыто",
            "выполнено",
        }

    def _updated_value(self, issue: DailyIssueSnapshot) -> datetime | None:
        text = issue.updated.replace("Z", "+00:00")

        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    def _now(self) -> datetime:
        return self.now or datetime.now(UTC)
