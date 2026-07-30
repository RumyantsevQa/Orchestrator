import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.core.artifacts import Artifact, PipelineTrace
from app.services.base import BaseService, ServiceRequest
from app.services.daily_models import (
    DailyIssueSnapshot,
    DailySnapshot,
    stable_text_hash,
)
from app.services.jira_client import adf_to_text


class SnapshotService(BaseService):
    """Stores and loads daily Jira snapshots as local QASkills artifacts."""

    name = "Snapshot Service"
    capabilities = {
        "snapshot.daily.save": "Save current Jira state and load previous snapshot.",
    }

    def __init__(
        self,
        vault_path: str,
        folder: str = "QASkills/Memory/Snapshots/Daily",
        now: datetime | None = None,
    ):
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.folder = folder
        self.now = now

    def execute(
        self,
        capability: str,
        request: ServiceRequest,
        trace: PipelineTrace | None = None,
    ) -> Artifact:
        if trace:
            trace.add(self.name, f"Executed capability {capability}")

        if capability != "snapshot.daily.save":
            raise ValueError(f"Unsupported snapshot capability: {capability}")

        return self._save_daily_snapshot(request)

    def latest_snapshot(self) -> DailySnapshot | None:
        """Return the newest persisted daily snapshot."""

        snapshots = self.history()

        return snapshots[-1] if snapshots else None

    def snapshot_for_date(self, target_date: date) -> DailySnapshot | None:
        """Return the latest snapshot saved on the given date."""

        matches = [
            snapshot
            for snapshot in self.history()
            if self._snapshot_date(snapshot) == target_date
        ]

        return matches[-1] if matches else None

    def history(self) -> list[DailySnapshot]:
        """Return persisted snapshot history sorted by timestamp."""

        snapshots = []

        for path in sorted(self.snapshot_folder.glob("daily_snapshot_*.json")):
            try:
                snapshots.append(
                    DailySnapshot.from_dict(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                )
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue

        return sorted(snapshots, key=lambda snapshot: snapshot.timestamp)

    @property
    def snapshot_folder(self) -> Path:
        return self.vault_path / self.folder

    def _save_daily_snapshot(self, request: ServiceRequest) -> Artifact:
        jira_error = self._artifact_named(request, "jira_error")

        if jira_error:
            return Artifact(
                name="daily_snapshot_error",
                source=self.name,
                content=f"Daily snapshot was not saved: {jira_error.content}",
                metadata={
                    "success": False,
                    "reason": "jira_error",
                    "error": jira_error.content,
                },
            )

        jira_data = self._artifact_named(request, "jira_assigned_issues")

        if not jira_data:
            return Artifact(
                name="daily_snapshot_error",
                source=self.name,
                content="Daily snapshot was not saved: Jira issues were not collected.",
                metadata={"success": False, "reason": "missing_jira_artifact"},
            )

        previous_snapshot = self.latest_snapshot()
        current_snapshot = self._snapshot_from_jira_artifact(jira_data)
        path = self._save_snapshot(current_snapshot)

        return Artifact(
            name="daily_snapshots",
            source=self.name,
            content=(
                "Daily snapshot saved. "
                f"Current issues: {len(current_snapshot.assigned_issues)}. "
                f"Previous snapshot: {'yes' if previous_snapshot else 'no'}."
            ),
            metadata={
                "success": True,
                "path": str(path.relative_to(self.vault_path)),
                "current_snapshot": current_snapshot.to_dict(),
                "previous_snapshot": (
                    previous_snapshot.to_dict()
                    if previous_snapshot
                    else None
                ),
            },
        )

    def _snapshot_from_jira_artifact(self, artifact: Artifact) -> DailySnapshot:
        issues = [
            self._issue_snapshot(issue)
            for issue in artifact.metadata.get("issues", [])
        ]
        timestamp = self._now().isoformat(timespec="microseconds")

        return DailySnapshot(
            timestamp=timestamp,
            project=self._project_name(issues),
            assigned_issues=sorted(issues, key=lambda issue: issue.key),
        )

    def _issue_snapshot(self, issue: dict[str, Any]) -> DailyIssueSnapshot:
        fields = self._fields(issue)
        description = adf_to_text(fields.get("description"))

        return DailyIssueSnapshot(
            key=str(issue.get("key") or ""),
            project=self._project(issue),
            summary=str(fields.get("summary") or "Untitled issue"),
            status=self._named_value(fields.get("status"), fallback="Unknown"),
            status_category=self._status_category(fields.get("status")),
            priority=self._named_value(fields.get("priority"), fallback="Unspecified"),
            assignee=self._user_value(fields.get("assignee"), fallback="Unassigned"),
            updated=str(fields.get("updated") or ""),
            sprint=self._sprint_name(fields),
            due_date=str(fields.get("duedate") or ""),
            labels=sorted(str(label) for label in fields.get("labels") or []),
            story_points=self._story_points(fields),
            description_hash=stable_text_hash(description),
            comment_count=self._comment_count(fields),
        )

    def _save_snapshot(self, snapshot: DailySnapshot) -> Path:
        self.snapshot_folder.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_folder / self._snapshot_filename(snapshot)
        path.write_text(
            json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return path

    def _snapshot_filename(self, snapshot: DailySnapshot) -> str:
        parsed = self._parse_datetime(snapshot.timestamp) or self._now()
        return f"daily_snapshot_{parsed.strftime('%Y%m%dT%H%M%S%fZ')}.json"

    def _artifact_named(self, request: ServiceRequest, name: str) -> Artifact | None:
        for artifact in request.artifacts:
            if artifact.name == name:
                return artifact

        return None

    def _fields(self, issue: dict[str, Any]) -> dict[str, Any]:
        fields = issue.get("fields")

        return fields if isinstance(fields, dict) else {}

    def _project(self, issue: dict[str, Any]) -> str:
        fields = self._fields(issue)
        project = fields.get("project")

        if isinstance(project, dict):
            return str(project.get("key") or project.get("name") or "")

        key = str(issue.get("key") or "")

        if "-" in key:
            return key.split("-", 1)[0]

        return ""

    def _project_name(self, issues: list[DailyIssueSnapshot]) -> str:
        projects = sorted({issue.project for issue in issues if issue.project})

        if not projects:
            return ""

        return projects[0] if len(projects) == 1 else "Mixed"

    def _named_value(self, value: object, fallback: str) -> str:
        if isinstance(value, dict):
            return str(value.get("name") or fallback)

        return fallback

    def _user_value(self, value: object, fallback: str) -> str:
        if isinstance(value, dict):
            return str(value.get("displayName") or value.get("accountId") or fallback)

        return fallback

    def _status_category(self, value: object) -> str:
        if not isinstance(value, dict):
            return ""

        category = value.get("statusCategory")

        if isinstance(category, dict):
            return str(category.get("key") or category.get("name") or "")

        return ""

    def _sprint_name(self, fields: dict[str, Any]) -> str:
        for key, value in fields.items():
            if "sprint" not in key.lower():
                continue

            extracted = self._extract_sprint_name(value)

            if extracted:
                return extracted

        for value in fields.values():
            extracted = self._extract_sprint_name(value, require_marker=True)

            if extracted:
                return extracted

        return ""

    def _extract_sprint_name(self, value: Any, require_marker: bool = False) -> str:
        if isinstance(value, dict):
            name = str(value.get("name") or "").strip()

            if not name:
                return ""

            has_sprint_shape = (
                "state" in value
                or "boardId" in value
                or "sprint" in name.lower()
            )

            return name if not require_marker or has_sprint_shape else ""

        if isinstance(value, list):
            for item in value:
                extracted = self._extract_sprint_name(
                    item,
                    require_marker=require_marker,
                )

                if extracted:
                    return extracted

        if isinstance(value, str):
            match = re.search(r"name=([^,\]]+)", value)

            if match:
                return match.group(1).strip()

            return value.strip() if "sprint" in value.lower() else ""

        return ""

    def _story_points(self, fields: dict[str, Any]) -> float | None:
        for key, value in fields.items():
            if "story" not in key.lower() or "point" not in key.lower():
                continue

            if isinstance(value, int | float):
                return float(value)

        return None

    def _comment_count(self, fields: dict[str, Any]) -> int:
        comments = fields.get("comment")

        if not isinstance(comments, dict):
            return 0

        total = comments.get("total")

        if isinstance(total, int):
            return total

        items = comments.get("comments")

        return len(items) if isinstance(items, list) else 0

    def _snapshot_date(self, snapshot: DailySnapshot) -> date | None:
        parsed = self._parse_datetime(snapshot.timestamp)

        return parsed.date() if parsed else None

    def _parse_datetime(self, value: str) -> datetime | None:
        text = value.replace("Z", "+00:00")

        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    def _now(self) -> datetime:
        return self.now or datetime.now(UTC)
