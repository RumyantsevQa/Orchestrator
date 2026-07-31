import re

from app.core.artifacts import Artifact, PipelineTrace
from app.services.base import BaseService, ServiceRequest
from app.services.jira_client import (
    JiraClient,
    JiraConfigurationError,
    JiraCredentials,
    JiraRequestError,
    adf_to_text,
)


class JiraService(BaseService):
    """
    Jira workspace boundary used by the unified QASkills pipeline.

    Live read-only commands call Jira Cloud REST API through JiraClient. The
    existing workspace capabilities remain available for local QA workflows
    that are not backed by live Jira data yet.
    """

    name = "Jira Service"
    capabilities = {
        "jira.whoami": "Show the authenticated Jira user.",
        "jira.list_projects": "List Jira projects visible to the user.",
        "jira.get_issue": "Read a Jira issue from Jira Cloud.",
        "jira.list_assigned_issues": "List Jira issues assigned to the user.",
        "jira.list_my_tasks": "List the user's Jira tasks.",
        "jira.find_issue": "Find a Jira issue by key.",
        "jira.analyze_issue": "Prepare QA analysis for a Jira issue.",
        "jira.create_bug_report_template": "Prepare a bug report draft.",
        "jira.prepare_daily_for_issue": "Prepare daily context for a Jira issue.",
    }

    def __init__(
        self,
        credentials: JiraCredentials | None = None,
        client: JiraClient | None = None,
    ):
        self.credentials = credentials
        self.client = client

    def execute(
        self,
        capability: str,
        request: ServiceRequest,
        trace: PipelineTrace | None = None,
    ) -> Artifact:
        if trace:
            trace.add(self.name, f"Executed capability {capability}")

        if capability == "jira.whoami":
            return self._whoami()

        if capability == "jira.list_projects":
            return self._projects()

        if capability == "jira.get_issue":
            return self._live_issue(request)

        if capability == "jira.list_assigned_issues":
            return self._assigned_issues(request)

        if capability == "jira.list_my_tasks":
            return self._list_my_tasks(request)

        if capability == "jira.find_issue":
            return self._find_issue(request)

        if capability == "jira.analyze_issue":
            return self._analyze_issue(request)

        if capability == "jira.create_bug_report_template":
            return self._bug_report_template(request)

        if capability == "jira.prepare_daily_for_issue":
            return self._daily_for_issue(request)

        raise ValueError(f"Unsupported Jira capability: {capability}")

    def _whoami(self) -> Artifact:
        try:
            user = self._client().whoami()
        except (JiraConfigurationError, JiraRequestError) as error:
            return self._error_artifact(error)

        lines = [
            "Jira User",
            f"Display name: {user.get('displayName') or 'Unavailable'}",
            f"Account ID: {user.get('accountId') or 'Unavailable'}",
            f"Email: {user.get('emailAddress') or 'Unavailable'}",
        ]

        return Artifact(
            name="jira_user",
            source=self.name,
            content="\n".join(lines),
            metadata={
                "capability": "jira.whoami",
                "connected": True,
                "account_id": user.get("accountId", ""),
            },
        )

    def _projects(self) -> Artifact:
        try:
            projects = self._client().projects()
        except (JiraConfigurationError, JiraRequestError) as error:
            return self._error_artifact(error)

        lines = ["Jira Projects"]

        if not projects:
            lines.append("No visible Jira projects were returned.")
        else:
            for project in projects:
                key = project.get("key") or "?"
                name = project.get("name") or "Unnamed project"
                lines.append(f"- {key}: {name}")

        return Artifact(
            name="jira_projects",
            source=self.name,
            content="\n".join(lines),
            metadata={
                "capability": "jira.list_projects",
                "connected": True,
                "count": len(projects),
            },
        )

    def _live_issue(self, request: ServiceRequest) -> Artifact:
        issue_key = self._issue_key(request)

        try:
            issue = self._client().issue(issue_key)
        except (JiraConfigurationError, JiraRequestError) as error:
            return self._error_artifact(error)

        fields = issue.get("fields", {})
        description = adf_to_text(fields.get("description"))
        issue_key = issue.get("key") or issue_key
        lines = [
            f"Jira Issue {issue_key}",
            f"Summary: {fields.get('summary') or 'Unavailable'}",
            f"Status: {self._named_value(fields.get('status'))}",
            f"Assignee: {self._user_value(fields.get('assignee'), fallback='Unassigned')}",
            f"Priority: {self._named_value(fields.get('priority'))}",
            f"Reporter: {self._user_value(fields.get('reporter'))}",
        ]

        if description:
            lines.extend(["", "Description:", description])

        return Artifact(
            name="jira_issue",
            source=self.name,
            content="\n".join(lines),
            metadata={
                "capability": "jira.get_issue",
                "connected": True,
                "issue_key": issue_key,
                "issue": {
                    "key": issue_key,
                    "summary": fields.get("summary") or "",
                    "updated": str(fields.get("updated") or ""),
                    "status": self._named_value(fields.get("status")),
                    "assignee": self._user_value(
                        fields.get("assignee"),
                        fallback="Unassigned",
                    ),
                    "priority": self._named_value(fields.get("priority")),
                    "reporter": self._user_value(fields.get("reporter")),
                    "description": description,
                    "comments": self._comments(fields.get("comment")),
                    "links": self._issue_links(fields.get("issuelinks")),
                },
            },
        )

    def _assigned_issues(self, request: ServiceRequest) -> Artifact:
        max_results = int(request.payload.get("max_results", 25))

        try:
            client = self._client()
            user = client.whoami()
            issues = client.assigned_issues(max_results=max_results)
        except (JiraConfigurationError, JiraRequestError) as error:
            return self._error_artifact(error)

        display_name = user.get("displayName") or "Jira user"

        return Artifact(
            name="jira_assigned_issues",
            source=self.name,
            content=(
                f"Fetched {len(issues)} Jira issues assigned to {display_name}."
            ),
            metadata={
                "capability": "jira.list_assigned_issues",
                "connected": True,
                "count": len(issues),
                "issues": issues,
                "user": user,
            },
        )

    def _list_my_tasks(self, request: ServiceRequest) -> Artifact:
        max_results = int(request.payload.get("max_results", 10))

        try:
            client = self._client()
            user = client.whoami()
            issues = client.assigned_issues(max_results=max_results)
        except JiraConfigurationError:
            return Artifact(
                name="jira_workspace",
                source=self.name,
                content=(
                    "Jira workspace is ready.\n"
                    "Live Jira is not configured. Add JIRA_URL, JIRA_EMAIL, "
                    "and JIRA_API_TOKEN to use live Jira data.\n"
                    "Available paths:\n"
                    "- Find a task by key.\n"
                    "- Prepare QA analysis for a task.\n"
                    "- Create a bug report template.\n"
                    "- Prepare daily notes for a selected task."
                ),
                metadata={
                    "capability": "jira.list_my_tasks",
                    "connected": False,
                    "items": [],
                },
            )
        except JiraRequestError as error:
            return self._error_artifact(error)

        display_name = user.get("displayName") or "Jira user"
        lines = [f"Live Jira tasks for {display_name}"]

        if not issues:
            lines.append("No assigned Jira issues were returned.")
        else:
            for issue in issues[:max_results]:
                fields = issue.get("fields", {})
                fields = fields if isinstance(fields, dict) else {}
                lines.append(
                    (
                        f"- {issue.get('key') or '?'} "
                        f"{fields.get('summary') or 'Untitled'} "
                        f"[{self._named_value(fields.get('status'))}, "
                        f"{self._named_value(fields.get('priority'))}]"
                    )
                )

        return Artifact(
            name="jira_workspace",
            source=self.name,
            content="\n".join(lines),
            metadata={
                "capability": "jira.list_my_tasks",
                "connected": True,
                "items": issues,
            },
        )

    def _find_issue(self, request: ServiceRequest) -> Artifact:
        issue_key = self._issue_key(request)
        title = f"Jira task {issue_key}" if issue_key else "Jira task"

        try:
            issue = self._client().issue(issue_key)
        except JiraConfigurationError:
            return Artifact(
                name="jira_issue",
                source=self.name,
                content=(
                    f"{title}\n"
                    "Live Jira is not configured. Add JIRA_URL, JIRA_EMAIL, "
                    "and JIRA_API_TOKEN to read this task from Jira."
                ),
                metadata={
                    "capability": "jira.find_issue",
                    "connected": False,
                    "issue_key": issue_key,
                },
            )
        except JiraRequestError as error:
            return self._error_artifact(error)

        fields = issue.get("fields", {})
        description = adf_to_text(fields.get("description"))
        resolved_key = issue.get("key") or issue_key
        lines = [
            f"Jira Issue {resolved_key}",
            f"Summary: {fields.get('summary') or 'Unavailable'}",
            f"Status: {self._named_value(fields.get('status'))}",
            f"Assignee: {self._user_value(fields.get('assignee'), fallback='Unassigned')}",
            f"Priority: {self._named_value(fields.get('priority'))}",
            f"Reporter: {self._user_value(fields.get('reporter'))}",
        ]

        if description:
            lines.extend(["", "Description:", description])

        return Artifact(
            name="jira_issue",
            source=self.name,
            content="\n".join(lines),
            metadata={
                "capability": "jira.find_issue",
                "connected": True,
                "issue_key": resolved_key,
                "issue": {
                    "key": resolved_key,
                    "summary": fields.get("summary") or "",
                    "updated": str(fields.get("updated") or ""),
                    "status": self._named_value(fields.get("status")),
                    "assignee": self._user_value(
                        fields.get("assignee"),
                        fallback="Unassigned",
                    ),
                    "priority": self._named_value(fields.get("priority")),
                    "reporter": self._user_value(fields.get("reporter")),
                    "description": description,
                    "comments": self._comments(fields.get("comment")),
                    "links": self._issue_links(fields.get("issuelinks")),
                },
            },
        )

    def _analyze_issue(self, request: ServiceRequest) -> Artifact:
        issue_key = self._issue_key(request)

        return Artifact(
            name="jira_issue_analysis",
            source=self.name,
            content=(
                f"QA task analysis workspace for {issue_key or 'the selected task'}:\n"
                "- Clarify acceptance criteria and changed areas.\n"
                "- Identify affected user paths and integrations.\n"
                "- Map risks to checks and regression scope.\n"
                "- Use memory sources before generating final recommendations."
            ),
            metadata={
                "capability": "jira.analyze_issue",
                "connected": False,
                "issue_key": issue_key,
            },
        )

    def _bug_report_template(self, request: ServiceRequest) -> Artifact:
        issue_key = self._issue_key(request)

        return Artifact(
            name="jira_bug_report_template",
            source=self.name,
            content=(
                "Bug Report Draft\n"
                f"Related task: {issue_key or 'not specified'}\n\n"
                "Title:\n"
                "Steps to reproduce:\n"
                "Actual result:\n"
                "Expected result:\n"
                "Environment:\n"
                "Evidence:\n"
                "Severity / Priority:\n"
                "Notes for developer:"
            ),
            metadata={
                "capability": "jira.create_bug_report_template",
                "connected": False,
                "issue_key": issue_key,
            },
        )

    def _daily_for_issue(self, request: ServiceRequest) -> Artifact:
        issue_key = self._issue_key(request)

        return Artifact(
            name="jira_daily_context",
            source=self.name,
            content=(
                f"Daily preparation for {issue_key or 'the selected Jira task'}:\n"
                "- Current task status.\n"
                "- Blockers or missing decisions.\n"
                "- QA risk and next validation step.\n"
                "- Questions for developers or product."
            ),
            metadata={
                "capability": "jira.prepare_daily_for_issue",
                "connected": False,
                "issue_key": issue_key,
            },
        )

    def _issue_key(self, request: ServiceRequest) -> str:
        raw = str(request.payload.get("issue_key") or request.user_text)
        match = re.search(r"(?<![A-Z0-9-])([A-Z][A-Z0-9]+-\d+)\b", raw.upper())

        return match.group(1) if match else ""

    def _client(self) -> JiraClient:
        if self.client:
            return self.client

        if not self.credentials:
            raise JiraConfigurationError(["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"])

        self.client = JiraClient(self.credentials)
        return self.client

    def _error_artifact(
        self,
        error: JiraConfigurationError | JiraRequestError,
    ) -> Artifact:
        if isinstance(error, JiraConfigurationError):
            message = (
                "Jira is not configured. Missing: "
                f"{', '.join(error.missing)}.\n"
                "Create a .env file with JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN."
            )
            status_code = None
        else:
            message = error.message
            status_code = error.status_code

        return Artifact(
            name="jira_error",
            source=self.name,
            content=message,
            metadata={
                "connected": False,
                "success": False,
                "status_code": status_code,
            },
        )

    def _named_value(self, value: object) -> str:
        if isinstance(value, dict):
            return str(value.get("name") or "Unavailable")

        return "Unavailable"

    def _user_value(self, value: object, fallback: str = "Unavailable") -> str:
        if not isinstance(value, dict):
            return fallback

        return str(value.get("displayName") or value.get("accountId") or fallback)

    def _comments(self, value: object) -> list[dict[str, str]]:
        if not isinstance(value, dict):
            return []

        comments = []

        for item in value.get("comments", []):
            if not isinstance(item, dict):
                continue

            comments.append(
                {
                    "id": str(item.get("id") or ""),
                    "author": self._user_value(item.get("author")),
                    "created": str(item.get("created") or ""),
                    "updated": str(item.get("updated") or ""),
                    "body": adf_to_text(item.get("body")),
                }
            )

        return comments

    def _issue_links(self, value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []

        links = []

        for item in value:
            if not isinstance(item, dict):
                continue

            link_type = item.get("type", {})
            linked_issue = item.get("outwardIssue") or item.get("inwardIssue") or {}

            if not isinstance(linked_issue, dict):
                continue

            fields = linked_issue.get("fields", {})
            fields = fields if isinstance(fields, dict) else {}
            links.append(
                {
                    "type": self._named_value(link_type),
                    "key": str(linked_issue.get("key") or ""),
                    "summary": str(fields.get("summary") or ""),
                    "status": self._named_value(fields.get("status")),
                }
            )

        return links
