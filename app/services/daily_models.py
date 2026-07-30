import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DailyIssueSnapshot:
    """A normalized Jira issue state saved inside a daily snapshot."""

    key: str
    project: str
    summary: str
    status: str
    status_category: str
    priority: str
    assignee: str
    updated: str
    sprint: str
    due_date: str
    labels: list[str] = field(default_factory=list)
    story_points: float | None = None
    description_hash: str = ""
    comment_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "project": self.project,
            "summary": self.summary,
            "status": self.status,
            "status_category": self.status_category,
            "priority": self.priority,
            "assignee": self.assignee,
            "updated": self.updated,
            "sprint": self.sprint,
            "due_date": self.due_date,
            "labels": self.labels,
            "story_points": self.story_points,
            "description_hash": self.description_hash,
            "comment_count": self.comment_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyIssueSnapshot":
        return cls(
            key=str(data.get("key") or ""),
            project=str(data.get("project") or ""),
            summary=str(data.get("summary") or ""),
            status=str(data.get("status") or ""),
            status_category=str(data.get("status_category") or ""),
            priority=str(data.get("priority") or ""),
            assignee=str(data.get("assignee") or ""),
            updated=str(data.get("updated") or ""),
            sprint=str(data.get("sprint") or ""),
            due_date=str(data.get("due_date") or ""),
            labels=list(data.get("labels") or []),
            story_points=data.get("story_points"),
            description_hash=str(data.get("description_hash") or ""),
            comment_count=int(data.get("comment_count") or 0),
        )


@dataclass(frozen=True)
class DailySnapshot:
    """Persisted state of the QA engineer's assigned Jira work."""

    timestamp: str
    project: str
    assigned_issues: list[DailyIssueSnapshot]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "timestamp": self.timestamp,
            "project": self.project,
            "assigned_issues": [
                issue.to_dict()
                for issue in self.assigned_issues
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailySnapshot":
        return cls(
            timestamp=str(data.get("timestamp") or ""),
            project=str(data.get("project") or ""),
            assigned_issues=[
                DailyIssueSnapshot.from_dict(issue)
                for issue in data.get("assigned_issues", [])
            ],
        )

    def issues_by_key(self) -> dict[str, DailyIssueSnapshot]:
        return {issue.key: issue for issue in self.assigned_issues}


@dataclass(frozen=True)
class IssueFieldChange:
    """A factual field-level change between two snapshots."""

    key: str
    summary: str
    field: str
    before: str
    after: str

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "summary": self.summary,
            "field": self.field,
            "before": self.before,
            "after": self.after,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IssueFieldChange":
        return cls(
            key=str(data.get("key") or ""),
            summary=str(data.get("summary") or ""),
            field=str(data.get("field") or ""),
            before=str(data.get("before") or ""),
            after=str(data.get("after") or ""),
        )


@dataclass(frozen=True)
class ChangeReport:
    """Difference report produced from previous and current daily snapshots."""

    has_history: bool
    current_timestamp: str
    previous_timestamp: str = ""
    new_issues: list[DailyIssueSnapshot] = field(default_factory=list)
    removed_issues: list[DailyIssueSnapshot] = field(default_factory=list)
    closed_issues: list[DailyIssueSnapshot] = field(default_factory=list)
    status_changes: list[IssueFieldChange] = field(default_factory=list)
    assignee_changes: list[IssueFieldChange] = field(default_factory=list)
    priority_changes: list[IssueFieldChange] = field(default_factory=list)
    sprint_changes: list[IssueFieldChange] = field(default_factory=list)
    due_date_changes: list[IssueFieldChange] = field(default_factory=list)
    comment_count_changes: list[IssueFieldChange] = field(default_factory=list)
    description_changes: list[IssueFieldChange] = field(default_factory=list)
    unchanged_stale_issues: list[DailyIssueSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_history": self.has_history,
            "current_timestamp": self.current_timestamp,
            "previous_timestamp": self.previous_timestamp,
            "new_issues": [issue.to_dict() for issue in self.new_issues],
            "removed_issues": [issue.to_dict() for issue in self.removed_issues],
            "closed_issues": [issue.to_dict() for issue in self.closed_issues],
            "status_changes": [change.to_dict() for change in self.status_changes],
            "assignee_changes": [
                change.to_dict()
                for change in self.assignee_changes
            ],
            "priority_changes": [
                change.to_dict()
                for change in self.priority_changes
            ],
            "sprint_changes": [change.to_dict() for change in self.sprint_changes],
            "due_date_changes": [
                change.to_dict()
                for change in self.due_date_changes
            ],
            "comment_count_changes": [
                change.to_dict()
                for change in self.comment_count_changes
            ],
            "description_changes": [
                change.to_dict()
                for change in self.description_changes
            ],
            "unchanged_stale_issues": [
                issue.to_dict()
                for issue in self.unchanged_stale_issues
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChangeReport":
        return cls(
            has_history=bool(data.get("has_history")),
            current_timestamp=str(data.get("current_timestamp") or ""),
            previous_timestamp=str(data.get("previous_timestamp") or ""),
            new_issues=[
                DailyIssueSnapshot.from_dict(issue)
                for issue in data.get("new_issues", [])
            ],
            removed_issues=[
                DailyIssueSnapshot.from_dict(issue)
                for issue in data.get("removed_issues", [])
            ],
            closed_issues=[
                DailyIssueSnapshot.from_dict(issue)
                for issue in data.get("closed_issues", [])
            ],
            status_changes=[
                IssueFieldChange.from_dict(change)
                for change in data.get("status_changes", [])
            ],
            assignee_changes=[
                IssueFieldChange.from_dict(change)
                for change in data.get("assignee_changes", [])
            ],
            priority_changes=[
                IssueFieldChange.from_dict(change)
                for change in data.get("priority_changes", [])
            ],
            sprint_changes=[
                IssueFieldChange.from_dict(change)
                for change in data.get("sprint_changes", [])
            ],
            due_date_changes=[
                IssueFieldChange.from_dict(change)
                for change in data.get("due_date_changes", [])
            ],
            comment_count_changes=[
                IssueFieldChange.from_dict(change)
                for change in data.get("comment_count_changes", [])
            ],
            description_changes=[
                IssueFieldChange.from_dict(change)
                for change in data.get("description_changes", [])
            ],
            unchanged_stale_issues=[
                DailyIssueSnapshot.from_dict(issue)
                for issue in data.get("unchanged_stale_issues", [])
            ],
        )


def stable_text_hash(text: str) -> str:
    """Return a stable short hash for snapshot comparison."""

    normalized = " ".join(text.split())

    if not normalized:
        return ""

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
